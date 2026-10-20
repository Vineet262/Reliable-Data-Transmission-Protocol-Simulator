"""
simulator/go_back_n.py
Go-Back-N ARQ implementation using discrete-event simulation.

Protocol summary
----------------
Sender window size W: up to W packets may be in-flight simultaneously.

Cumulative ACK convention:
  ACK(k) means "all packets up to and including k have been received;
  send packet k+1 next."

Receiver rule:
  The receiver expects packets in strict order. Out-of-order packets are
  discarded (NAK-free). The receiver only sends ACK for the highest
  in-order packet.

Timeout / retransmission:
  A per-window timer is maintained for the oldest unacknowledged packet
  (sender_base). On timeout, ALL packets from sender_base to
  next_seq - 1 are retransmitted (Go-Back-N rule).

Window advance:
  When ACK(k) is received, sender_base advances to k + 1. New packets
  are injected to fill the window.

Sequence numbers:
  Absolute IDs 0 … n-1 are used internally for clear visualisation.
  Real implementations use modular arithmetic; this is documented.

Maximum retries:
  Per-round-trip retry counter prevents infinite loops.
"""
from __future__ import annotations
import heapq
import uuid
from typing import Optional

from simulator.models import EventType, SimEvent, SimulationResult
from simulator.network import NetworkChannel
from simulator.metrics import compute_metrics

MAX_RETRIES: int = 50          # safety limit per per-window retransmission round


def run(
    total_packets: int,
    window_size: int = 4,
    packet_loss_prob: float = 0.10,
    ack_loss_prob: float = 0.05,
    delay_ms: float = 200.0,
    timeout_ms: float = 600.0,
    seed: Optional[int] = None,
) -> SimulationResult:
    """Run a complete Go-Back-N ARQ simulation."""

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
        protocol="go_back_n",
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
    sender_base: int = 0        # oldest unacked packet
    next_seq: int = 0           # next packet index to send
    receiver_expected: int = 0  # next in-order packet expected at receiver

    delivered: set[int] = set()
    sender_acked_upto: int = -1   # highest cumulative ACK received

    # Per-window timeout cookie (invalidated on window advance)
    window_cookie: int = 0
    current_cookie: int = 0      # active cookie; timeout with old cookie is stale

    retry_rounds: int = 0        # how many full go-back-n retransmission rounds
    now: float = 0.0

    # ── Helpers ───────────────────────────────────────────────────────────────
    def schedule_window_timeout(from_time: float) -> None:
        nonlocal window_cookie
        window_cookie += 1
        push(SimEvent(
            time=from_time + timeout_ms,
            etype=EventType.TIMEOUT,
            seq=sender_base,
            description=f"Timeout — retransmit from packet {sender_base}",
            window_base=sender_base,
            window_end=next_seq - 1,
            tie=0,
        ))
        # Store active cookie so we can distinguish stale timeouts
        # We embed it in the description – instead we use a module-level counter

    def tx_packet(seq: int, t: float, attempt: int) -> None:
        dropped = channel.will_drop_packet()
        result.total_attempts += 1
        if attempt > 1:
            result.retransmissions += 1

        etype = EventType.RETRANSMIT if attempt > 1 else EventType.PACKET_SENT
        evt = SimEvent(
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
        )
        log(evt)

        if not dropped:
            push(SimEvent(
                time=channel.arrival_time(t),
                etype=EventType.PACKET_RECEIVED,
                seq=seq,
                dropped=False,
                attempt=attempt,
                description=f"Packet {seq} arrived at receiver",
                window_base=sender_base,
                window_end=sender_base + window_size - 1,
                tie=0,
            ))

    def fill_window(t: float, first_attempt_for_new: int = 1) -> None:
        """Send new packets to fill the window up to window_size."""
        nonlocal next_seq
        while next_seq < total_packets and next_seq < sender_base + window_size:
            tx_packet(next_seq, t, attempt=first_attempt_for_new)
            next_seq += 1

    # ── Initial transmissions ────────────────────────────────────────────────
    fill_window(now)
    if sender_base < total_packets:
        schedule_window_timeout(now)
        current_cookie = window_cookie

    # ── Event loop ────────────────────────────────────────────────────────────
    while heap:
        evt = heapq.heappop(heap)
        now = evt.time

        if evt.etype == EventType.PACKET_RECEIVED:
            seq = evt.seq
            log(evt)

            if seq == receiver_expected:
                # In-order packet
                if seq not in delivered:
                    delivered.add(seq)
                    result.delivered_packets += 1
                    log(SimEvent(
                        time=now,
                        etype=EventType.PACKET_DELIVERED,
                        seq=seq,
                        description=f"Packet {seq} delivered to application",
                        tie=0,
                    ))
                receiver_expected += 1

                # Send cumulative ACK
                dropped = channel.will_drop_ack()
                log(SimEvent(
                    time=now,
                    etype=EventType.ACK_SENT,
                    seq=seq,
                    ack_seq=seq,
                    dropped=dropped,
                    description=f"ACK({seq}) sent (cumulative)" + (" — DROPPED" if dropped else ""),
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
            else:
                # Out-of-order — discard (GBN rule)
                log(SimEvent(
                    time=now,
                    etype=EventType.PACKET_DUPLICATE,
                    seq=seq,
                    description=(
                        f"Packet {seq} discarded (out-of-order; expected {receiver_expected})"
                    ),
                    tie=0,
                ))
                # Re-send last cumulative ACK for last in-order packet
                if receiver_expected > 0:
                    last_acked = receiver_expected - 1
                    dropped = channel.will_drop_ack()
                    log(SimEvent(
                        time=now,
                        etype=EventType.ACK_SENT,
                        seq=last_acked,
                        ack_seq=last_acked,
                        dropped=dropped,
                        description=(
                            f"Re-ACK({last_acked}) sent (cumulative, discard NAK-free)"
                            + (" — DROPPED" if dropped else "")
                        ),
                        tie=0,
                    ))
                    if dropped:
                        result.dropped_ack_packets += 1
                    else:
                        push(SimEvent(
                            time=channel.arrival_time(now),
                            etype=EventType.ACK_RECEIVED,
                            seq=last_acked,
                            ack_seq=last_acked,
                            description=f"Re-ACK({last_acked}) received at sender",
                            tie=0,
                        ))

        elif evt.etype == EventType.ACK_RECEIVED:
            ack_seq = evt.ack_seq
            log(evt)

            if ack_seq <= sender_acked_upto:
                # Duplicate / stale cumulative ACK
                log(SimEvent(
                    time=now,
                    etype=EventType.ACK_DUPLICATE,
                    ack_seq=ack_seq,
                    description=f"Duplicate/stale ACK({ack_seq}) ignored",
                    tie=0,
                ))
                continue

            # Advance window
            old_base = sender_base
            sender_acked_upto = ack_seq
            result.acked_packets += ack_seq - sender_base + 1
            sender_base = ack_seq + 1
            retry_rounds = 0

            log(SimEvent(
                time=now,
                etype=EventType.WINDOW_ADVANCE,
                seq=ack_seq,
                ack_seq=ack_seq,
                description=(
                    f"Window advance: base {old_base} → {sender_base} "
                    f"(ACK({ack_seq}) received)"
                ),
                window_base=sender_base,
                window_end=sender_base + window_size - 1,
                tie=0,
            ))

            if sender_base >= total_packets:
                log(SimEvent(
                    time=now,
                    etype=EventType.TRANSFER_COMPLETE,
                    description="All packets delivered and acknowledged",
                    tie=0,
                ))
                result.status = "completed"
                result.completion_time_ms = now
                break

            # Fill window with new packets
            fill_window(now)

            # Reset timeout for new window base
            current_cookie = window_cookie + 1
            schedule_window_timeout(now)
            current_cookie = window_cookie

        elif evt.etype == EventType.TIMEOUT:
            # Check for stale timeout: if sender_base has advanced past the event's base
            if evt.window_base is not None and evt.window_base < sender_base:
                continue  # stale — window already advanced past this
            if sender_base >= total_packets:
                continue

            log(evt)
            result.timeouts += 1
            retry_rounds += 1

            if retry_rounds > MAX_RETRIES:
                log(SimEvent(
                    time=now,
                    etype=EventType.TRANSFER_FAILED,
                    seq=sender_base,
                    description=(
                        f"Exceeded max retries ({MAX_RETRIES}). Transfer failed."
                    ),
                    tie=0,
                ))
                result.status = "failed"
                result.failure_reason = (
                    f"Exceeded {MAX_RETRIES} go-back-n retransmission rounds."
                )
                result.completion_time_ms = now
                break

            # Go-Back-N: retransmit all from sender_base to next_seq-1
            retx_end = next_seq
            next_seq = sender_base  # reset next_seq for retransmission
            for seq in range(sender_base, retx_end):
                tx_packet(seq, now, attempt=retry_rounds + 1)
                next_seq = seq + 1

            # Re-schedule timeout
            schedule_window_timeout(now)
            current_cookie = window_cookie

    if result.status == "pending":
        result.status = "completed" if result.delivered_packets == total_packets else "failed"
        result.completion_time_ms = now

    compute_metrics(result)
    return result
