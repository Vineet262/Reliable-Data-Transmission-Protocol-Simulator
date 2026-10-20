"""
simulator/selective_repeat.py
Selective Repeat ARQ implementation using discrete-event simulation.

Protocol summary
----------------
Sender window size W: up to W packets may be in-flight simultaneously.
Receiver window size W (same as sender window for this implementation).

Individual ACK convention:
  ACK(k) means "packet k specifically received."

Receiver rule:
  Valid packets within the receiver window are accepted and buffered.
  Packets outside the receiver window are discarded.
  Buffered packets are delivered to the application in order when the
  leading expected packet arrives.

Timeout / retransmission:
  Each in-flight packet has its own independent timer. On expiry, ONLY
  that specific packet is retransmitted (Selective Repeat rule).

Window size safety:
  For correct operation, window size W ≤ N/2 where N is the sequence-
  number space. With absolute IDs we document this constraint but do
  not enforce modular wrap for clarity. A warning is emitted if W > 10.

Sequence numbers:
  Absolute IDs 0 … n-1 are used internally for clear visualisation.

Maximum retries:
  Per-packet retry counter prevents infinite loops.
"""
from __future__ import annotations
import heapq
import uuid
from typing import Optional

from simulator.models import EventType, SimEvent, SimulationResult
from simulator.network import NetworkChannel
from simulator.metrics import compute_metrics

MAX_RETRIES_PER_PACKET: int = 50  # safety limit


def run(
    total_packets: int,
    window_size: int = 4,
    packet_loss_prob: float = 0.10,
    ack_loss_prob: float = 0.05,
    delay_ms: float = 200.0,
    timeout_ms: float = 600.0,
    seed: Optional[int] = None,
) -> SimulationResult:
    """Run a complete Selective Repeat ARQ simulation."""

    # ── Validate inputs ──────────────────────────────────────────────────────
    if total_packets < 1:
        raise ValueError("total_packets must be >= 1")
    if window_size < 1:
        raise ValueError("window_size must be >= 1")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be > 0")

    channel = NetworkChannel(packet_loss_prob, ack_loss_prob, delay_ms, seed)

    result = SimulationResult(
        simulation_id=str(uuid.uuid4()),
        protocol="selective_repeat",
        config={
            "total_packets": total_packets,
            "window_size": window_size,
            "packet_loss_prob": packet_loss_prob,
            "ack_loss_prob": ack_loss_prob,
            "delay_ms": delay_ms,
            "timeout_ms": timeout_ms,
            "seed": seed,
        },
        total_packets=total_packets,
    )

    heap: list[SimEvent] = []
    _tie = 0

    def push(evt: SimEvent) -> None:
        nonlocal _tie
        evt.tie = _tie
        _tie += 1
        heapq.heappush(heap, evt)

    def log(e: SimEvent) -> None:
        result.events.append({
            "time": round(e.time, 3),
            "type": e.etype.value,
            "seq": e.seq,
            "ack_seq": e.ack_seq,
            "dropped": e.dropped,
            "attempt": e.attempt,
            "description": e.description,
            "window_base": e.window_base,
            "window_end": e.window_end,
        })

    # ── State ─────────────────────────────────────────────────────────────────
    sender_base: int = 0            # oldest unacked packet
    next_seq: int = 0               # next packet to send
    # Per-packet state
    acked: dict[int, bool] = {}     # sender-side: has ACK been received?
    retries: dict[int, int] = {}    # per-packet retry count
    # Per-packet timeout cookies (int per seq, incremented on each send)
    tx_cookie: dict[int, int] = {}  # seq -> current cookie
    cookie_gen: int = 0

    # Receiver state
    recv_buffer: dict[int, bool] = {}   # seq -> buffered (not yet delivered)
    recv_delivered: set[int] = set()    # delivered to application
    recv_base: int = 0                  # next expected seq for in-order delivery

    now: float = 0.0

    # ── Helpers ───────────────────────────────────────────────────────────────
    def new_cookie(seq: int) -> int:
        nonlocal cookie_gen
        cookie_gen += 1
        tx_cookie[seq] = cookie_gen
        return cookie_gen

    def schedule_timeout(seq: int, t: float, cookie: int) -> None:
        push(SimEvent(
            time=t + timeout_ms,
            etype=EventType.TIMEOUT,
            seq=seq,
            description=f"Timeout for packet {seq} (cookie {cookie})",
            attempt=retries.get(seq, 0) + 1,
            window_base=sender_base,
            window_end=sender_base + window_size - 1,
            tie=0,
        ))

    def tx_packet(seq: int, t: float) -> None:
        attempt = retries.get(seq, 0) + 1
        retries[seq] = attempt
        dropped = channel.will_drop_packet()
        result.total_attempts += 1
        if attempt > 1:
            result.retransmissions += 1

        etype = EventType.RETRANSMIT if attempt > 1 else EventType.PACKET_SENT
        log(SimEvent(
            time=t,
            etype=etype,
            seq=seq,
            dropped=dropped,
            attempt=attempt,
            description=(
                f"{'Retransmit' if attempt > 1 else 'Send'} packet {seq} "
                f"(attempt {attempt}, window [{sender_base}–{sender_base+window_size-1}])"
                + (" — DROPPED" if dropped else "")
            ),
            window_base=sender_base,
            window_end=sender_base + window_size - 1,
            tie=0,
        ))

        if not dropped:
            push(SimEvent(
                time=channel.arrival_time(t),
                etype=EventType.PACKET_RECEIVED,
                seq=seq,
                dropped=False,
                attempt=attempt,
                description=f"Packet {seq} arrived at receiver",
                window_base=recv_base,
                window_end=recv_base + window_size - 1,
                tie=0,
            ))

        cookie = new_cookie(seq)
        schedule_timeout(seq, t, cookie)

    def fill_window(t: float) -> None:
        nonlocal next_seq
        while next_seq < total_packets and next_seq < sender_base + window_size:
            if not acked.get(next_seq, False):
                acked[next_seq] = False
                tx_packet(next_seq, t)
            next_seq += 1

    def try_deliver_in_order() -> float:
        """Deliver buffered packets in order; return last delivered time (now)."""
        nonlocal recv_base
        while recv_base in recv_buffer and recv_base not in recv_delivered:
            recv_delivered.add(recv_base)
            result.delivered_packets += 1
            log(SimEvent(
                time=now,
                etype=EventType.PACKET_DELIVERED,
                seq=recv_base,
                description=f"Packet {recv_base} delivered to application (in order)",
                tie=0,
            ))
            recv_base += 1
        return now

    def advance_sender_window() -> None:
        """Slide sender window past consecutively acked packets."""
        nonlocal sender_base
        old_base = sender_base
        while acked.get(sender_base, False) and sender_base < total_packets:
            sender_base += 1
        if sender_base != old_base:
            log(SimEvent(
                time=now,
                etype=EventType.WINDOW_ADVANCE,
                description=f"Sender window advanced: base {old_base} → {sender_base}",
                window_base=sender_base,
                window_end=sender_base + window_size - 1,
                tie=0,
            ))

    # ── Initial transmissions ────────────────────────────────────────────────
    fill_window(now)

    # ── Event loop ────────────────────────────────────────────────────────────
    while heap:
        evt = heapq.heappop(heap)
        now = evt.time

        if evt.etype == EventType.PACKET_RECEIVED:
            seq = evt.seq
            log(evt)

            # Check receiver window bounds
            if seq < recv_base or seq >= recv_base + window_size:
                # Outside receiver window — discard
                log(SimEvent(
                    time=now,
                    etype=EventType.PACKET_DUPLICATE,
                    seq=seq,
                    description=(
                        f"Packet {seq} outside receiver window "
                        f"[{recv_base}–{recv_base+window_size-1}] — discarded"
                    ),
                    tie=0,
                ))
                # For packets below recv_base, re-send ACK (might help unblock sender)
                if seq < recv_base:
                    dropped = channel.will_drop_ack()
                    log(SimEvent(
                        time=now,
                        etype=EventType.ACK_SENT,
                        seq=seq,
                        ack_seq=seq,
                        dropped=dropped,
                        description=f"Re-ACK({seq}) sent (duplicate)" + (" — DROPPED" if dropped else ""),
                        tie=0,
                    ))
                    if dropped:
                        result.dropped_ack_packets += 1
                    else:
                        push(SimEvent(
                            time=channel.arrival_time(now),
                            etype=EventType.ACK_RECEIVED,
                            seq=seq,
                            ack_seq=seq,
                            description=f"Re-ACK({seq}) received at sender",
                            tie=0,
                        ))
                continue

            if seq in recv_delivered or recv_buffer.get(seq, False):
                # Duplicate within window — re-ACK but don't re-buffer
                log(SimEvent(
                    time=now,
                    etype=EventType.PACKET_DUPLICATE,
                    seq=seq,
                    description=f"Packet {seq} already buffered/delivered — re-ACK",
                    tie=0,
                ))
            else:
                # New valid packet: buffer it
                recv_buffer[seq] = True
                if seq == recv_base:
                    # May trigger in-order delivery
                    try_deliver_in_order()
                else:
                    # Out-of-order but within window — buffer
                    log(SimEvent(
                        time=now,
                        etype=EventType.PACKET_BUFFERED,
                        seq=seq,
                        description=(
                            f"Packet {seq} buffered (out-of-order; "
                            f"expecting {recv_base})"
                        ),
                        tie=0,
                    ))

            # Send individual ACK
            dropped = channel.will_drop_ack()
            log(SimEvent(
                time=now,
                etype=EventType.ACK_SENT,
                seq=seq,
                ack_seq=seq,
                dropped=dropped,
                description=f"ACK({seq}) sent (individual)" + (" — DROPPED" if dropped else ""),
                tie=0,
            ))
            if dropped:
                result.dropped_ack_packets += 1
            else:
                push(SimEvent(
                    time=channel.arrival_time(now),
                    etype=EventType.ACK_RECEIVED,
                    seq=seq,
                    ack_seq=seq,
                    description=f"ACK({seq}) received at sender",
                    tie=0,
                ))

        elif evt.etype == EventType.ACK_RECEIVED:
            ack_seq = evt.ack_seq
            log(evt)

            if acked.get(ack_seq, False):
                # Duplicate individual ACK
                log(SimEvent(
                    time=now,
                    etype=EventType.ACK_DUPLICATE,
                    ack_seq=ack_seq,
                    description=f"Duplicate ACK({ack_seq}) ignored",
                    tie=0,
                ))
                continue

            # Mark this specific packet as acked
            acked[ack_seq] = True
            result.acked_packets += 1
            # Invalidate its timeout cookie
            tx_cookie.pop(ack_seq, None)

            advance_sender_window()
            fill_window(now)

            if sender_base >= total_packets and result.delivered_packets >= total_packets:
                log(SimEvent(
                    time=now,
                    etype=EventType.TRANSFER_COMPLETE,
                    description="All packets delivered and acknowledged",
                    tie=0,
                ))
                result.status = "completed"
                result.completion_time_ms = now
                break

        elif evt.etype == EventType.TIMEOUT:
            seq = evt.seq

            # Stale check: if already acked, ignore
            if acked.get(seq, False):
                continue
            # Stale check: if seq is beyond total packets
            if seq >= total_packets:
                continue
            # Stale check: outside sender window (packet was never in window here)
            if seq < sender_base or seq >= sender_base + window_size:
                continue

            log(evt)
            result.timeouts += 1

            # Check per-packet retry limit
            current_retries = retries.get(seq, 0)
            if current_retries >= MAX_RETRIES_PER_PACKET:
                log(SimEvent(
                    time=now,
                    etype=EventType.TRANSFER_FAILED,
                    seq=seq,
                    description=(
                        f"Packet {seq} exceeded {MAX_RETRIES_PER_PACKET} retransmissions. "
                        "Transfer failed."
                    ),
                    tie=0,
                ))
                result.status = "failed"
                result.failure_reason = (
                    f"Packet {seq} exceeded {MAX_RETRIES_PER_PACKET} retransmission attempts."
                )
                result.completion_time_ms = now
                break

            # Selective Repeat: retransmit ONLY this packet
            tx_packet(seq, now)

    if result.status == "pending":
        result.status = "completed" if result.delivered_packets == total_packets else "failed"
        result.completion_time_ms = now

    compute_metrics(result)
    return result
