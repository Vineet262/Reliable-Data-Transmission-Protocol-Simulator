"""
tests/test_stop_and_wait.py
Unit and edge-case tests for Stop-and-Wait ARQ protocol.
"""
import pytest
from simulator import stop_and_wait

def test_stop_and_wait_zero_loss():
    """Test 1: Transfer with zero packet loss and zero ACK loss."""
    res = stop_and_wait.run(
        total_packets=10,
        packet_loss_prob=0.0,
        ack_loss_prob=0.0,
        delay_ms=100.0,
        timeout_ms=300.0,
        seed=123
    )
    assert res.status == "completed"
    assert res.delivered_packets == 10
    assert res.acked_packets == 10
    assert res.retransmissions == 0
    assert res.timeouts == 0
    assert res.delivery_ratio == 100.0
    assert res.total_attempts == 10

def test_stop_and_wait_retry_limit_exhaustion():
    """Test 2 & 12: 100% packet loss causes retry limit exhaustion."""
    res = stop_and_wait.run(
        total_packets=5,
        packet_loss_prob=1.0,  # 100% drop
        ack_loss_prob=0.0,
        delay_ms=10.0,
        timeout_ms=50.0,
        seed=1
    )
    assert res.status == "failed"
    assert res.delivered_packets == 0
    assert res.retransmissions >= stop_and_wait.MAX_RETRIES

def test_stop_and_wait_lost_ack_causes_retransmission():
    """Test 3 & 4: Lost ACK causes timeout, retransmission, and duplicate discard."""
    # Seed chosen so data passes but ACK drops, or test with high ack loss
    res = stop_and_wait.run(
        total_packets=5,
        packet_loss_prob=0.0,
        ack_loss_prob=0.3,
        delay_ms=50.0,
        timeout_ms=150.0,
        seed=42
    )
    assert res.status == "completed"
    assert res.delivered_packets == 5
    if res.dropped_ack_packets > 0:
        assert res.retransmissions >= res.dropped_ack_packets
        # Check event log has duplicate discards
        dup_events = [e for e in res.events if e["type"] == "PACKET_DUPLICATE"]
        assert len(dup_events) > 0

def test_stop_and_wait_reproducibility():
    """Test 14: Supplying same seed produces identical event sequence."""
    r1 = stop_and_wait.run(total_packets=8, packet_loss_prob=0.2, ack_loss_prob=0.1, delay_ms=100, timeout_ms=300, seed=99)
    r2 = stop_and_wait.run(total_packets=8, packet_loss_prob=0.2, ack_loss_prob=0.1, delay_ms=100, timeout_ms=300, seed=99)
    assert len(r1.events) == len(r2.events)
    assert r1.completion_time_ms == r2.completion_time_ms
    assert r1.total_attempts == r2.total_attempts
    assert r1.retransmissions == r2.retransmissions

def test_stop_and_wait_invalid_inputs():
    """Test 11: Invalid arguments raise ValueError."""
    with pytest.raises(ValueError):
        stop_and_wait.run(total_packets=0)
    with pytest.raises(ValueError):
        stop_and_wait.run(total_packets=5, timeout_ms=0)
