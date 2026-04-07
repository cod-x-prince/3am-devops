use pyo3::prelude::*;
use numpy::PyArray1;

#[pyclass]
pub struct RustServiceGraph {
    num_services: usize,
}

#[pymethods]
impl RustServiceGraph {
    #[new]
    pub fn new(scenario: &str, curr_level: u32) -> Self {
        // stub
        RustServiceGraph { num_services: 12 }
    }

    pub fn reset<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<f32>> {
        let obs = vec![0.0_f32; self.num_services * 6];
        PyArray1::from_vec(py, obs)
    }
}
