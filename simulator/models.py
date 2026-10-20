"""
simulator/models.py
Data models for packets, events, and simulation state.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    # Data packet events
    PACKET_SENT = "PACKET_SENT"
    PACKET_RECEIVED = "PACKET_RECEIVED"
    PACKET_DROPPED = "PACKET_DROPPED"
    PACKET_DUPLICATE = "PACKET_DUPLICATE"
    PACKET_BUFFERED = "PACKET_BUFFERED"          # SR out-of-order buffer
    PACKET_DELIVERED = "PACKET_DELIVERED"         # handed to application

    # ACK events
    ACK_SENT = "ACK_SENT"
    ACK_RECEIVED = "ACK_RECEIVED"
    ACK_DROPPED = "ACK_DROPPED"
    ACK_DUPLICATE = "ACK_DUPLICATE"

    # Control events
    TIMEOUT = "TIMEOUT"
    RETRANSMIT = "RETRANSMIT"
    WINDOW_ADVANCE = "WINDOW_ADVANCE"
    TRANSFER_COMPLETE = "TRANSFER_COMPLETE"
    TRANSFER_FAILED = "TRANSFER_FAILED"
    SIM_INFO = "SIM_INFO"


@dataclass
class Packet:
    """Represents one data packet in the simulation."""
    seq: int                        # sequence number / absolute ID
    payload: str = ""               # sample payload
    attempt: int = 1                # current attempt number (1-based)
    send_time: float = 0.0          # simulated send timestamp (ms)
    delivered: bool = False         # delivered to receiver application
    acked: bool = False             # acknowledged by sender
    retransmit_count: int = 0       # retransmissions (attempt - 1)


@dataclass(order=True)
class SimEvent:
    """
    A discrete simulation event processed in chronological order.
    Events with equal timestamps are ordered by tie-breaker.
    """
    time: float                     # simulated time in ms
    tie: int = field(compare=True)  # insertion order for stable sort
    etype: EventType = field(compare=False, default=EventType.SIM_INFO)
    seq: Optional[int] = field(compare=False, default=None)       # packet seq
    ack_seq: Optional[int] = field(compare=False, default=None)   # ACK number
    description: str = field(compare=False, default="")
    dropped: bool = field(compare=False, default=False)
    attempt: int = field(compare=False, default=1)
    window_base: Optional[int] = field(compare=False, default=None)
    window_end: Optional[int] = field(compare=False, default=None)


@dataclass
class SimulationResult:
    """Complete result returned by the protocol engine."""
    simulation_id: str = ""
    protocol: str = ""
    config: dict = field(default_factory=dict)

    # Events in chronological order
    events: list[dict] = field(default_factory=list)

    # Packet-level stats
    total_packets: int = 0
    delivered_packets: int = 0
    acked_packets: int = 0
    dropped_data_packets: int = 0
    dropped_ack_packets: int = 0
    total_attempts: int = 0
    retransmissions: int = 0
    timeouts: int = 0

    # Performance
    completion_time_ms: float = 0.0
    throughput_bps: float = 0.0
    delivery_ratio: float = 0.0
    efficiency: float = 0.0
    payload_size_bytes: int = 1024  # documented assumption

    # Status
    status: str = "pending"         # pending | completed | failed
    failure_reason: str = ""
