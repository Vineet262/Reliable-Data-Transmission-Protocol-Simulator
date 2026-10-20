"""
simulator/network.py
Simulated network channel that applies configurable packet/ACK loss
and propagation delay. Uses a seeded PRNG for reproducibility.
"""
from __future__ import annotations
import random
from typing import Optional


class NetworkChannel:
    """
    Models an unreliable bidirectional channel.

    - packet_loss_prob : probability a data packet is dropped (0.0–1.0)
    - ack_loss_prob    : probability an ACK is dropped (0.0–1.0)
    - delay_ms         : one-way simulated propagation delay (ms)
    - seed             : optional int for reproducible results
    """

    def __init__(
        self,
        packet_loss_prob: float = 0.10,
        ack_loss_prob: float = 0.05,
        delay_ms: float = 200.0,
        seed: Optional[int] = None,
    ) -> None:
        if not (0.0 <= packet_loss_prob <= 1.0):
            raise ValueError("packet_loss_prob must be in [0, 1]")
        if not (0.0 <= ack_loss_prob <= 1.0):
            raise ValueError("ack_loss_prob must be in [0, 1]")
        if delay_ms < 0:
            raise ValueError("delay_ms must be >= 0")

        self.packet_loss_prob = packet_loss_prob
        self.ack_loss_prob = ack_loss_prob
        self.delay_ms = delay_ms

        self._rng = random.Random(seed)

    def will_drop_packet(self) -> bool:
        """Return True if the next data packet should be dropped."""
        return self._rng.random() < self.packet_loss_prob

    def will_drop_ack(self) -> bool:
        """Return True if the next ACK should be dropped."""
        return self._rng.random() < self.ack_loss_prob

    def arrival_time(self, send_time: float) -> float:
        """Return the simulated arrival time for a transmission."""
        return send_time + self.delay_ms
