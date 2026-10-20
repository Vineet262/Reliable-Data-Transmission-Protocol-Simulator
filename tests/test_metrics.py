"""
tests/test_metrics.py
Unit tests for metric calculation accuracy and zero-division handling.
"""
from simulator.models import SimulationResult
from simulator.metrics import compute_metrics, PAYLOAD_SIZE_BYTES

def test_metrics_standard_calculation():
    """Test 13: Accurate throughput, delivery ratio, and efficiency."""
    res = SimulationResult(
        total_packets=10,
        delivered_packets=10,
        total_attempts=12,
        completion_time_ms=2000.0  # 2.0 seconds
    )
    compute_metrics(res)

    assert res.delivery_ratio == 100.0
    # 10 packets * 1024 * 8 bits = 81,920 bits / 2.0s = 40,960 bps
    assert res.throughput_bps == 40960.0
    # 10 delivered / 12 attempts = 83.33% efficiency
    assert res.efficiency == 83.33

def test_metrics_zero_elapsed_time():
    """Zero elapsed time does not trigger division by zero."""
    res = SimulationResult(
        total_packets=5,
        delivered_packets=5,
        total_attempts=5,
        completion_time_ms=0.0
    )
    compute_metrics(res)
    assert res.throughput_bps == 0.0
    assert res.delivery_ratio == 100.0

def test_metrics_zero_attempts():
    """Zero attempts or zero packets handled safely."""
    res = SimulationResult(
        total_packets=0,
        delivered_packets=0,
        total_attempts=0,
        completion_time_ms=100.0
    )
    compute_metrics(res)
    assert res.delivery_ratio == 0.0
    assert res.efficiency == 0.0
    assert res.throughput_bps == 0.0
