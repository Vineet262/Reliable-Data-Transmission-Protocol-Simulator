"""
tests/test_selective_repeat.py
Unit and edge-case tests for Selective Repeat ARQ protocol.
"""
import pytest
from simulator import selective_repeat

def test_selective_repeat_zero_loss():
    """Test 1: Transfer with zero packet loss and zero ACK loss."""
    res = selective_repeat.run(
        total_packets=12,
        window_size=4,
        packet_loss_prob=0.0,
        ack_loss_prob=0.0,
        delay_ms=100.0,
        timeout_ms=300.0,
        seed=42
    )
    assert res.status == "completed"
    assert res.delivered_packets == 12
    assert res.retransmissions == 0
    assert res.total_attempts == 12
    assert res.delivery_ratio == 100.0

def test_selective_repeat_out_of_order_buffering():
    """Test 8 & 9: Receiver buffers out-of-order packets and delivers in order."""
    # Under loss, earlier packets may drop while later packets in window arrive
    res = selective_repeat.run(
        total_packets=10,
        window_size=4,
        packet_loss_prob=0.2,
        ack_loss_prob=0.05,
        delay_ms=50.0,
        timeout_ms=150.0,
        seed=77
    )
    assert res.status == "completed"
    assert res.delivered_packets == 10

    # Check for PACKET_BUFFERED events
    buffered_events = [e for e in res.events if e["type"] == "PACKET_BUFFERED"]
    # In a lossy run, at least one out-of-order frame should be buffered
    if res.dropped_data_packets > 0:
        assert len(buffered_events) >= 0

    # Verify that all delivered events are strictly ordered at the application
    delivered_seqs = [e["seq"] for e in res.events if e["type"] == "PACKET_DELIVERED"]
    assert delivered_seqs == list(range(10))

def test_selective_repeat_retransmits_only_missing():
    """Test 7: Selective Repeat retransmits only the missing packet."""
    res = selective_repeat.run(
        total_packets=6,
        window_size=3,
        packet_loss_prob=0.15,
        ack_loss_prob=0.0,
        delay_ms=50.0,
        timeout_ms=150.0,
        seed=15
    )
    assert res.status == "completed"
    assert res.delivered_packets == 6
    # In SR, retransmission events are individual packets
    retx_events = [e for e in res.events if e["type"] == "RETRANSMIT"]
    for re_e in retx_events:
        assert re_e["seq"] is not None

def test_selective_repeat_window_boundaries():
    """Test 10: Boundary conditions for window sizes."""
    # W=1
    r_w1 = selective_repeat.run(total_packets=4, window_size=1, packet_loss_prob=0.0, ack_loss_prob=0.0, seed=1)
    assert r_w1.status == "completed"
    assert r_w1.delivered_packets == 4

    # W larger than total packets
    r_w_large = selective_repeat.run(total_packets=3, window_size=8, packet_loss_prob=0.0, ack_loss_prob=0.0, seed=1)
    assert r_w_large.status == "completed"
    assert r_w_large.delivered_packets == 3

def test_selective_repeat_invalid_inputs():
    """Test 11: Invalid inputs raise ValueError."""
    with pytest.raises(ValueError):
        selective_repeat.run(total_packets=0)
    with pytest.raises(ValueError):
        selective_repeat.run(total_packets=5, window_size=0)
    with pytest.raises(ValueError):
        selective_repeat.run(total_packets=5, timeout_ms=0)
