"""
simulator/metrics.py
Calculates performance metrics from simulation results.

Documented metric definitions
------------------------------
payload_size_bytes : assumed payload per packet (default 1024 bytes = 8192 bits)

total_attempts     : all data-packet transmissions, including retransmissions
retransmissions    : attempts AFTER the first transmission (attempt > 1)
delivery_ratio     : (unique packets delivered / total packets) × 100
throughput_bps     : (unique payload bits delivered) / (completion_time seconds)
                     Returns 0 when completion_time == 0.
efficiency         : (unique payload bits) / (total bits transmitted) × 100
                     total bits = total_attempts × payload_size_bytes × 8
                     Returns 0 when total_attempts == 0.
"""
from __future__ import annotations
from simulator.models import SimulationResult

PAYLOAD_SIZE_BYTES: int = 1024  # documented assumption for all metric calculations


def compute_metrics(result: SimulationResult) -> SimulationResult:
    """
    Populate throughput, delivery_ratio, and efficiency on *result* in-place.
    Returns the same object for chaining.
    """
    result.payload_size_bytes = PAYLOAD_SIZE_BYTES
    bits_per_packet = PAYLOAD_SIZE_BYTES * 8  # 8192 bits

    # Delivery ratio (%)
    if result.total_packets > 0:
        result.delivery_ratio = round(
            result.delivered_packets / result.total_packets * 100, 2
        )
    else:
        result.delivery_ratio = 0.0

    # Throughput (bits per second)
    elapsed_s = result.completion_time_ms / 1000.0
    if elapsed_s > 0 and result.delivered_packets > 0:
        result.throughput_bps = round(
            result.delivered_packets * bits_per_packet / elapsed_s, 2
        )
    else:
        result.throughput_bps = 0.0

    # Protocol efficiency (%)
    if result.total_attempts > 0:
        total_tx_bits = result.total_attempts * bits_per_packet
        useful_bits = result.delivered_packets * bits_per_packet
        result.efficiency = round(useful_bits / total_tx_bits * 100, 2)
    else:
        result.efficiency = 0.0

    return result
