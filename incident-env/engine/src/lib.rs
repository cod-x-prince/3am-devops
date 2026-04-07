use pyo3::prelude::*;

mod service_graph;
mod fault_injector;
mod metrics_engine;

use service_graph::RustServiceGraph;

#[pymodule]
fn incident_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RustServiceGraph>()?;
    Ok(())
}
