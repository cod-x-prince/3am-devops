use crate::fault_injector::FaultType;
use crate::metrics_engine::MetricsEngine;
use numpy::PyArray1;
use pyo3::prelude::*;
use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
struct ServiceNode {
    id: String,
    health: f32,
    cpu: f32,
    memory: f32,
    error_rate: f32,
    latency_p50: f32,
    latency_p99: f32,
    request_rate: f32,
    status: String,
}

#[derive(Debug, Clone, Serialize)]
struct Connection {
    source: String,
    target: String,
    strength: f32,
}

#[derive(Debug, Clone, Serialize)]
struct ServiceJsonPayload {
    services: Vec<ServiceNode>,
    connections: Vec<Connection>,
    tick: u32,
    active_faults: Vec<String>,
}

#[pyclass]
pub struct RustServiceGraph {
    scenario: String,
    curriculum_level: u32,
    tick: u32,
    max_steps: u32,
    cumulative_reward: f32,
    services: Vec<ServiceNode>,
    connections: Vec<Connection>,
    active_faults: Vec<String>,
    metrics: MetricsEngine,
}

fn clamp01(v: f32) -> f32 {
    v.clamp(0.0, 1.0)
}

fn status_from_health(health: f32) -> String {
    if health >= 0.9 {
        "healthy".to_string()
    } else if health >= 0.7 {
        "degraded".to_string()
    } else if health >= 0.4 {
        "critical".to_string()
    } else {
        "down".to_string()
    }
}

fn recompute_health(service: &mut ServiceNode) {
    let weighted = 1.0
        - (0.30 * service.cpu + 0.25 * service.memory + 0.30 * service.error_rate + 0.15 * service.latency_p99);
    service.health = clamp01(weighted);
    service.status = status_from_health(service.health);
}

impl RustServiceGraph {
    fn make_services(num_services: usize) -> Vec<ServiceNode> {
        (0..num_services)
            .map(|i| ServiceNode {
                id: format!("service_{}", i),
                health: 0.95,
                cpu: 0.20,
                memory: 0.25,
                error_rate: 0.01,
                latency_p50: 0.03,
                latency_p99: 0.06,
                request_rate: 0.50,
                status: "healthy".to_string(),
            })
            .collect()
    }

    fn make_connections(num_services: usize) -> Vec<Connection> {
        let mut out = Vec::new();
        for i in 0..(num_services.saturating_sub(1)) {
            out.push(Connection {
                source: format!("service_{}", i),
                target: format!("service_{}", i + 1),
                strength: 0.5 + ((i % 4) as f32 * 0.1),
            });
        }
        out
    }

    fn inject_fault_internal(&mut self, fault_type: &str, target: usize) {
        let Some(ft) = FaultType::from_name(fault_type) else {
            return;
        };
        if let Some(service) = self.services.get_mut(target) {
            match ft {
                FaultType::CpuSpike => service.cpu = clamp01(service.cpu + 0.40),
                FaultType::MemoryLeak => service.memory = clamp01(service.memory + 0.45),
                FaultType::NetworkPartition => {
                    service.latency_p50 = clamp01(service.latency_p50 + 0.35);
                    service.latency_p99 = clamp01(service.latency_p99 + 0.45);
                }
                FaultType::DbDeadlock => {
                    service.error_rate = clamp01(service.error_rate + 0.50);
                    service.latency_p99 = clamp01(service.latency_p99 + 0.35);
                }
                FaultType::BadDeploy => service.error_rate = clamp01(service.error_rate + 0.60),
                FaultType::ThunderingHerd => {
                    service.cpu = clamp01(service.cpu + 0.25);
                    service.request_rate = clamp01(service.request_rate + 0.30);
                }
                FaultType::CascadeTimeout => {
                    service.latency_p50 = clamp01(service.latency_p50 + 0.40);
                    service.latency_p99 = clamp01(service.latency_p99 + 0.50);
                }
                FaultType::SplitBrain => {
                    service.error_rate = clamp01(service.error_rate + 0.35);
                    service.memory = clamp01(service.memory + 0.20);
                }
            }
            recompute_health(service);
            self.active_faults
                .push(format!("{}(service_{})", fault_type, target));
        }
    }

    fn apply_action(&mut self, target: usize, action_type: u8) {
        if let Some(service) = self.services.get_mut(target) {
            match action_type {
                0 => {
                    service.cpu = 0.15;
                    service.memory = 0.20;
                    service.error_rate = 0.01;
                    service.latency_p50 = 0.02;
                    service.latency_p99 = 0.04;
                }
                1 => {
                    service.cpu = clamp01(service.cpu - 0.15);
                    service.memory = clamp01(service.memory - 0.10);
                }
                2 => service.error_rate = clamp01(service.error_rate - 0.20),
                3 => {
                    service.latency_p50 = clamp01(service.latency_p50 - 0.15);
                    service.latency_p99 = clamp01(service.latency_p99 - 0.20);
                }
                4 => service.error_rate = clamp01(service.error_rate - 0.10),
                5 => {
                    service.error_rate = clamp01(service.error_rate - 0.05);
                    service.latency_p99 = clamp01(service.latency_p99 - 0.10);
                }
                _ => {}
            }
            recompute_health(service);
        }
    }

    fn apply_drift(&mut self) {
        for (idx, service) in self.services.iter_mut().enumerate() {
            let noise = self.metrics.deterministic_noise(self.tick, idx);
            service.cpu = clamp01(service.cpu + noise * 0.20);
            service.memory = clamp01(service.memory + noise * 0.18);
            service.error_rate = clamp01(service.error_rate + noise * 0.15);
            service.latency_p50 = clamp01(service.latency_p50 + noise * 0.12);
            service.latency_p99 = clamp01(service.latency_p99 + noise * 0.14);
            service.request_rate = clamp01(service.request_rate + noise * 0.10);
            recompute_health(service);
        }
    }

    fn propagate_failures(&mut self) -> usize {
        let mut newly_degraded = 0usize;
        for conn in &self.connections {
            let source_idx = conn
                .source
                .trim_start_matches("service_")
                .parse::<usize>()
                .unwrap_or(0);
            let target_idx = conn
                .target
                .trim_start_matches("service_")
                .parse::<usize>()
                .unwrap_or(0);

            if source_idx >= self.services.len() || target_idx >= self.services.len() {
                continue;
            }

            let source_health = self.services[source_idx].health;
            if source_health < 0.6 {
                let before = self.services[target_idx].health;
                let degrade = (0.6 - source_health) * conn.strength * 0.30;
                let target = &mut self.services[target_idx];
                target.error_rate = clamp01(target.error_rate + degrade);
                target.latency_p99 = clamp01(target.latency_p99 + degrade);
                recompute_health(target);
                if before >= 0.7 && target.health < 0.7 {
                    newly_degraded += 1;
                }
            }
        }
        newly_degraded
    }

    fn score_step(&self, action_type: u8, newly_degraded: usize, done: bool) -> f32 {
        let (_, critical, down) = self.status_counts();
        let mut reward = 0.08;
        reward -= 0.07 * critical as f32;
        reward -= 0.12 * down as f32;
        reward -= 0.03 * newly_degraded as f32;
        if action_type == 6 && (critical + down) > 0 {
            reward -= 0.05;
        }
        if done {
            reward += 0.6;
        }
        reward.clamp(-1.0, 1.0)
    }

    fn status_counts(&self) -> (usize, usize, usize) {
        let mut healthy = 0usize;
        let mut critical = 0usize;
        let mut down = 0usize;
        for s in &self.services {
            match s.status.as_str() {
                "healthy" => healthy += 1,
                "critical" => critical += 1,
                "down" => down += 1,
                _ => {}
            }
        }
        (healthy, critical, down)
    }

    fn scenario_bootstrap(&mut self) {
        // Scenario faults are injected by the Python wrapper from JSON configs.
        // Keep Rust defaults neutral so Track A/Track B contract stays in one place.
    }

    fn obs_vec(&self) -> Vec<f32> {
        let mut obs = Vec::with_capacity(self.services.len() * 6);
        for s in &self.services {
            obs.extend_from_slice(&[
                clamp01(s.cpu),
                clamp01(s.memory),
                clamp01(s.error_rate),
                clamp01(s.latency_p50),
                clamp01(s.latency_p99),
                clamp01(s.request_rate),
            ]);
        }
        obs
    }

    fn services_json(&self) -> String {
        let payload = ServiceJsonPayload {
            services: self.services.clone(),
            connections: self.connections.clone(),
            tick: self.tick,
            active_faults: self.active_faults.clone(),
        };
        serde_json::to_string(&payload).unwrap_or_else(|_| "{}".to_string())
    }

    fn is_resolved_internal(&self) -> bool {
        self.services.iter().all(|s| s.health >= 0.9)
    }
}

#[pymethods]
impl RustServiceGraph {
    #[new]
    pub fn new(scenario: &str, curr_level: u32) -> Self {
        let mut graph = Self {
            scenario: scenario.to_string(),
            curriculum_level: curr_level,
            tick: 0,
            max_steps: 50,
            cumulative_reward: 0.0,
            services: Self::make_services(12),
            connections: Self::make_connections(12),
            active_faults: Vec::new(),
            metrics: MetricsEngine::new(0.02),
        };
        graph.scenario_bootstrap();
        graph
    }

    pub fn reset<'py>(&mut self, py: Python<'py>) -> Bound<'py, PyArray1<f32>> {
        self.tick = 0;
        self.cumulative_reward = 0.0;
        self.active_faults.clear();
        self.services = Self::make_services(12);
        self.connections = Self::make_connections(12);
        self.scenario_bootstrap();
        PyArray1::from_vec_bound(py, self.obs_vec())
    }

    pub fn step<'py>(
        &mut self,
        py: Python<'py>,
        target_service_id: usize,
        action_type: u8,
    ) -> (Bound<'py, PyArray1<f32>>, f32, bool) {
        self.tick += 1;
        let target = target_service_id.min(self.services.len().saturating_sub(1));
        self.apply_action(target, action_type);
        self.apply_drift();
        let newly_degraded = self.propagate_failures();
        let done = self.is_resolved_internal() || self.tick >= self.max_steps;
        let reward = self.score_step(action_type, newly_degraded, done);
        self.cumulative_reward += reward;

        (PyArray1::from_vec_bound(py, self.obs_vec()), reward, done)
    }

    pub fn inject_fault(&mut self, fault_type: &str, target: usize) {
        self.inject_fault_internal(fault_type, target);
    }

    pub fn set_max_steps(&mut self, max_steps: u32) {
        self.max_steps = max_steps.max(1);
    }

    pub fn get_service_states_json(&self) -> String {
        self.services_json()
    }

    pub fn get_observation_vector(&self) -> Vec<f32> {
        self.obs_vec()
    }

    pub fn is_resolved(&self) -> bool {
        self.is_resolved_internal()
    }

    pub fn get_status_counts(&self) -> (usize, usize, usize) {
        self.status_counts()
    }

    pub fn get_tick(&self) -> u32 {
        self.tick
    }

    pub fn get_cumulative_reward(&self) -> f32 {
        self.cumulative_reward
    }

    pub fn get_scenario(&self) -> String {
        self.scenario.clone()
    }

    pub fn get_curriculum_level(&self) -> u32 {
        self.curriculum_level
    }
}
