"""
tests/test_api.py
Integration tests for Flask endpoints, validation, and HTML page routes.
"""
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    """GET /api/health returns 200 OK."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"

def test_protocols_endpoint(client):
    """GET /api/protocols lists all supported ARQ protocols."""
    res = client.get("/api/protocols")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    proto_ids = [p["id"] for p in data["protocols"]]
    assert "stop_and_wait" in proto_ids
    assert "go_back_n" in proto_ids
    assert "selective_repeat" in proto_ids

def test_simulate_endpoint_valid(client):
    """POST /api/simulate executes successfully with valid parameters."""
    payload = {
        "protocol": "go_back_n",
        "total_packets": 10,
        "window_size": 4,
        "packet_loss_prob": 0.05,
        "ack_loss_prob": 0.0,
        "delay_ms": 100,
        "timeout_ms": 300,
        "seed": 42
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    sim = data["simulation"]
    assert sim["protocol"] == "go_back_n"
    assert len(sim["events"]) > 0
    assert "throughput_bps" in sim

def test_simulate_endpoint_invalid(client):
    """POST /api/simulate returns 400 for out-of-bounds parameters."""
    # Negative packets & excessive loss probability
    payload = {
        "protocol": "stop_and_wait",
        "total_packets": -5,
        "packet_loss_prob": 0.95
    }
    res = client.post("/api/simulate", json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert len(data["errors"]) >= 1

def test_compare_endpoint(client):
    """Test 15: POST /api/compare executes all three protocols under shared configuration."""
    payload = {
        "total_packets": 10,
        "window_size": 4,
        "packet_loss_prob": 0.10,
        "ack_loss_prob": 0.05,
        "delay_ms": 50,
        "timeout_ms": 150,
        "seed": 42
    }
    res = client.post("/api/compare", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    cmp_res = data["comparison"]
    assert "stop_and_wait" in cmp_res
    assert "go_back_n" in cmp_res
    assert "selective_repeat" in cmp_res
    assert "interpretation" in cmp_res
    assert len(cmp_res["interpretation"]) > 0

def test_page_routes(client):
    """Web HTML routes render properly with HTTP 200."""
    for path in ["/", "/simulator", "/comparison", "/learning", "/about"]:
        res = client.get(path)
        assert res.status_code == 200
        assert b"Reliable Data Transmission" in res.data
