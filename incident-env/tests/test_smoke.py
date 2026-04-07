import pytest
from incident_core import RustServiceGraph

def test_rust_service_graph():
    g = RustServiceGraph("bad_deploy", 1)
    obs = g.reset()
    assert obs.shape == (72,)  # 12 services * 6 metrics
