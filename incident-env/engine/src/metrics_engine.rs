// Metrics engine for service telemetry

pub struct MetricsEngine {
    pub history_window: usize,
}

impl MetricsEngine {
    pub fn new() -> Self {
        MetricsEngine {
            history_window: 60,
        }
    }
    
    pub fn add_noise(&self, value: f32, amount: f32) -> f32 {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        let noise = rng.gen_range(-amount..amount);
        (value + noise).max(0.0).min(1.0)
    }
}
