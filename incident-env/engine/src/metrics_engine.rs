#[derive(Debug, Clone)]
pub struct MetricsEngine {
    sigma: f32,
}

impl MetricsEngine {
    pub fn new(sigma: f32) -> Self {
        Self { sigma }
    }

    pub fn deterministic_noise(&self, tick: u32, index: usize) -> f32 {
        let phase = (tick as f32 * 0.17) + (index as f32 * 0.31);
        self.sigma * phase.sin()
    }
}
