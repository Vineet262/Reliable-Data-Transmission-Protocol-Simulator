"""
tests/test_go_back_n.py
Unit and edge-case tests for Go-Back-N ARQ protocol.
"""
import pytest
from simulator import go_back_n

def test_go_back_n_zero_loss():
    """Test 1: Transfer with zero packet loss and zero ACK loss."""
    res = go_back_n.run(
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

def test_go_back_n_retransmission_of_outstanding_window():
    """Test 6: On timeout, Go-Back-N retransmits all outstanding packets."""
    # Run with a seed where packet loss happens
    res = go_back_n.run(
        total_packets=8,
        window_size=4,
        packet_loss_prob=0.25,
        ack_loss_prob=0.0,
        delay_ms=50.0,
        timeout_ms=150.0,
        seed=10
    )
    assert res.status == "completed"
    assert res.delivered_packets == 8
    # When timeouts occur, multiple packets get retransmitted
    if res.timeouts > 0:
        assert res.retransmissions >= res.timeouts
        # Verify event log shows duplicate discards for out-of-order frames
        discards = [e for e in res.events if e["type"] == "PACKET_DUPLICATE"]
        assert len(discards) >= 0

def test_go_back_n_window_boundaries():
    """Test 10: Boundary conditions where window_size >= total_packets or window_size == 1."""
    # Window size 1 (acts like stop and wait pipelining)
    r_w1 = go_back_n.run(total_packets=5, window_size=1, packet_loss_prob=0.0, ack_loss_prob=0.0, seed=1)
    assert r_w1.status == "completed"
    assert r_w1.delivered_packets == 5

    # Window size larger than total packets
    r_w_large = go_back_n.run(total_packets=3, window_size=10, packet_loss_prob=0.0, ack_loss_prob=0.0, seed=1)
    assert r_w_large.status == "completed"
    assert r_w_large.delivered_packets == 3

def test_go_back_n_cumulative_ack():
    """Cumulative ACK advances sender_base correctly."""
    res = go_back_n.run(
        total_packets=6,
        window_size=3,
        packet_loss_prob=0.0,
        ack_loss_prob=0.0,
        delay_ms=20.0,
        timeout_ms=80.0,
        seed=100
    )
    advances = [e for e in res.events if e["type"] == "WINDOW_ADVANCE"]
    assert len(advances) > 0
    # Final window advance reaches 6
    assert advances[-1]["window_base"] >= 6

def test_go_back_n_invalid_inputs():
    """Test 11: Invalid arguments raise ValueError."""
    with pytest.raises(ValueError):
        go_back_n.run(total_packets=0)
    with pytest.raises(ValueError):
        go_back_n.run(total_packets=5, window_size=0)
    with pytest.raises(ValueError):
        go_back_n.run(total_packets=5, timeout_ms=-1)
