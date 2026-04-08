use pyo3::prelude::*;
use pyo3::types::PyDict;
use numpy::PyArray1;
use rand::prelude::*;
use serde::{Serialize, Deserialize};

const NUM_SERVICES: usize = 12;
const METRICS_PER_SERVICE: usize = 6;

#[derive(Clone, Serialize, Deserialize)]
pub struct ServiceNode {
    pub id: usize,
    pub cpu: f32,
    pub memory: f32,
    pub error_rate: f32,
    pub latency_p50: f32,
    pub latency_p99: f32,
    pub request_rate: f32,
    pub health: f32,
    pub faulty: bool,
}

impl ServiceNode {
    fn new(id: usize) -> Self {
        ServiceNode {
            id,
            cpu: 0.2,
            memory: 0.3,
            error_rate: 0.01,
            latency_p50: 0.05,
            latency_p99: 0.10,
            request_rate: 0.5,
            health: 1.0,
            faulty: false,
        }
    }

    fn compute_health(&mut self) {
        self.health = (1.0 - (0.4 * self.error_rate + 0.3 * self.cpu + 0.3 * self.memory))
            .max(0.0)
            .min(1.0);
    }

    fn status(&self) -> &str {
        if self.health >= 0.9 {
            "healthy"
        } else if self.health >= 0.7 {
            "degraded"
        } else if self.health >= 0.4 {
            "critical"
        } else {
            "down"
        }
    }
}

#[pyclass]
pub struct RustServiceGraph {
    services: Vec<ServiceNode>,
    connections: Vec<(usize, usize)>,
    tick: u32,
    max_ticks: u32,
    rng: StdRng,
    scenario: String,
    curriculum_level: u32,
}

#[pymethods]
impl RustServiceGraph {
    #[new]
    pub fn new(scenario: &str, curr_level: u32) -> Self {
        let rng = StdRng::seed_from_u64(42);
        let mut services: Vec<ServiceNode> = (0..NUM_SERVICES)
            .map(|i| ServiceNode::new(i))
            .collect();
        
        // Build linear chain connections
        let connections: Vec<(usize, usize)> = (0..NUM_SERVICES - 1)
            .map(|i| (i, i + 1))
            .collect();
        
        // Inject initial fault based on scenario
        if scenario == "bad_deploy" {
            services[3].error_rate = 0.8;
            services[3].cpu = 0.9;
            services[3].faulty = true;
            services[3].compute_health();
        }
        
        RustServiceGraph {
            services,
            connections,
            tick: 0,
            max_ticks: 50,
            rng,
            scenario: scenario.to_string(),
            curriculum_level: curr_level,
        }
    }

    pub fn reset<'py>(&mut self, py: Python<'py>) -> Bound<'py, PyArray1<f32>> {
        self.tick = 0;
        
        // Reset all services to healthy state
        for service in &mut self.services {
            service.cpu = 0.2 + self.rng.gen::<f32>() * 0.1;
            service.memory = 0.3 + self.rng.gen::<f32>() * 0.1;
            service.error_rate = 0.01;
            service.latency_p50 = 0.05;
            service.latency_p99 = 0.10;
            service.request_rate = 0.5;
            service.faulty = false;
            service.compute_health();
        }
        
        // Inject fault based on scenario
        if self.scenario == "bad_deploy" {
            self.services[3].error_rate = 0.8;
            self.services[3].cpu = 0.9;
            self.services[3].faulty = true;
            self.services[3].compute_health();
        }
        
        self.get_observation(py)
    }

    pub fn step<'py>(
        &mut self,
        py: Python<'py>,
        action: Vec<i32>,
    ) -> PyResult<(Bound<'py, PyArray1<f32>>, f32, bool, bool, Bound<'py, PyDict>)> {
        self.tick += 1;
        
        let service_id = action[0] as usize;
        let action_type = action[1];
        
        // Apply action
        let mut action_effective = false;
        if service_id < NUM_SERVICES {
            action_effective = self.apply_action(service_id, action_type);
        }
        
        // Propagate failures through connections
        self.propagate_failures();
        
        // Compute reward
        let reward = self.compute_reward(action_effective, action_type);
        
        // Check termination
        let all_healthy = self.services.iter().all(|s| s.health > 0.85);
        let timeout = self.tick >= self.max_ticks;
        let terminated = all_healthy || timeout;
        
        // Build info dict
        let info = PyDict::new_bound(py);
        info.set_item("tick", self.tick)?;
        info.set_item("action_taken", format!("Action{}(service_{})", action_type, service_id))?;
        info.set_item("services_healthy", self.services.iter().filter(|s| s.health > 0.85).count())?;
        info.set_item("services_critical", self.services.iter().filter(|s| s.health < 0.4).count())?;
        info.set_item("services_down", self.services.iter().filter(|s| s.health < 0.2).count())?;
        info.set_item("services_json", self.get_services_json())?;
        
        Ok((self.get_observation(py), reward, terminated, false, info))
    }

    pub fn get_services_json(&self) -> String {
        let services_data: Vec<_> = self.services
            .iter()
            .map(|s| {
                serde_json::json!({
                    "id": format!("service_{}", s.id),
                    "health": s.health,
                    "cpu": s.cpu,
                    "memory": s.memory,
                    "error_rate": s.error_rate,
                    "latency_p50": s.latency_p50,
                    "latency_p99": s.latency_p99,
                    "request_rate": s.request_rate,
                    "status": s.status(),
                })
            })
            .collect();
        
        let connections_data: Vec<_> = self.connections
            .iter()
            .map(|(src, dst)| {
                serde_json::json!({
                    "source": format!("service_{}", src),
                    "target": format!("service_{}", dst),
                    "strength": 0.7,
                })
            })
            .collect();
        
        serde_json::json!({
            "services": services_data,
            "connections": connections_data,
            "tick": self.tick,
            "active_faults": self.get_active_faults(),
        })
        .to_string()
    }
}

impl RustServiceGraph {
    fn get_observation<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<f32>> {
        let mut obs = Vec::with_capacity(NUM_SERVICES * METRICS_PER_SERVICE);
        
        for service in &self.services {
            obs.push(service.cpu);
            obs.push(service.memory);
            obs.push(service.error_rate);
            obs.push(service.latency_p50);
            obs.push(service.latency_p99);
            obs.push(service.request_rate);
        }
        
        PyArray1::from_vec_bound(py, obs)
    }

    fn apply_action(&mut self, service_id: usize, action_type: i32) -> bool {
        let service = &mut self.services[service_id];
        
        match action_type {
            0 => {
                // RestartService
                if service.faulty {
                    service.error_rate = 0.01;
                    service.cpu = 0.2;
                    service.faulty = false;
                    service.compute_health();
                    true
                } else {
                    false
                }
            }
            1 => {
                // ScaleUp
                if service.cpu > 0.7 {
                    service.cpu *= 0.6;
                    service.compute_health();
                    true
                } else {
                    false
                }
            }
            2 => {
                // RollbackDeploy
                if service.error_rate > 0.5 {
                    service.error_rate = 0.01;
                    service.faulty = false;
                    service.compute_health();
                    true
                } else {
                    false
                }
            }
            3 => {
                // RerouteTraffic
                if service.request_rate > 0.8 {
                    service.request_rate *= 0.5;
                    service.cpu *= 0.7;
                    service.compute_health();
                    true
                } else {
                    false
                }
            }
            4 => {
                // ToggleFeatureFlag
                if service.error_rate > 0.3 {
                    service.error_rate *= 0.5;
                    service.compute_health();
                    true
                } else {
                    false
                }
            }
            5 => {
                // TriggerCircuitBreaker
                if service.health < 0.5 {
                    service.request_rate = 0.1;
                    service.cpu *= 0.5;
                    service.compute_health();
                    true
                } else {
                    false
                }
            }
            6 => {
                // NoOp
                false
            }
            _ => false,
        }
    }

    fn propagate_failures(&mut self) {
        // Simple propagation: faulty services affect downstream
        let mut propagation_effects = Vec::new();
        
        for (src, dst) in &self.connections {
            let src_health = self.services[*src].health;
            if src_health < 0.7 {
                let impact = (0.7 - src_health) * 0.3;
                propagation_effects.push((*dst, impact));
            }
        }
        
        for (service_id, impact) in propagation_effects {
            let service = &mut self.services[service_id];
            service.error_rate = (service.error_rate + impact).min(1.0);
            service.latency_p99 = (service.latency_p99 + impact * 0.5).min(1.0);
            service.compute_health();
        }
    }

    fn compute_reward(&self, action_effective: bool, action_type: i32) -> f32 {
        let mean_health: f32 = self.services.iter().map(|s| s.health).sum::<f32>() / NUM_SERVICES as f32;
        let healthy_count = self.services.iter().filter(|s| s.health > 0.85).count();
        
        let mut reward = (mean_health - 0.5) * 0.5; // Base reward from health
        
        // Bonus for fixing issues
        if action_effective {
            reward += 0.3;
        }
        
        // Penalty for unnecessary actions
        if action_type == 6 && healthy_count < NUM_SERVICES {
            reward -= 0.2; // NoOp when problems exist
        }
        
        // Bonus for all services healthy
        if healthy_count == NUM_SERVICES {
            reward += 0.5;
        }
        
        reward.max(-1.0).min(1.0)
    }

    fn get_active_faults(&self) -> Vec<String> {
        self.services
            .iter()
            .filter(|s| s.faulty)
            .map(|s| format!("Fault(service_{})", s.id))
            .collect()
    }
}
