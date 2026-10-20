"""
simulator/stop_and_wait.py
Stop-and-Wait ARQ implementation using discrete-event simulation.

Protocol summary
----------------
1. Sender transmits ONE packet and starts a timeout timer.
2. Receiver accepts the packet (if not a duplicate) and sends an ACK.
3. Sender advances to the next packet only after receiving the correct ACK.
4. On timeout the sender retransmits the current packet.

Sequence numbers
----------------
We use absolute packet IDs (0 … n-1) internally for clear visualisation.
Duplicate detection uses a 1-bit alternating bit convention: the expected
sequence number flips between the packet's ID and (ID XOR 1) is NOT needed
here because we track receiver_expected directly.  The receiver simply
compares the arriving seq with receiver_expected.

ACK convention
--------------
ACK(k) means "packet k received successfully; send packet k+1 next."

Maximum retries
---------------
A configurable MAX_RETRIES safety limit prevents infinite loops on 100%
loss. If reached, the transfer is marked FAILED.
"""
from __future__ import annotations
import heapq
import uuid
from typing import Optional

from simulator.models import EventType, SimEvent, SimulationResult
from simulator.network import NetworkChannel
from simulator.metrics import compute_metrics

MAX_RETRIES: int = 50  # per-packet retry safety limit


def run(
    total_packets: int,
    packet_loss_prob: float = 0.10,
    ack_loss_prob: float = 0.05,
    delay_ms: float = 200.0,
    timeout_ms: float = 600.0,
    seed: Optional[int] = None,
) -> SimulationResult:
    """Run a complete Stop-and-Wait ARQ simulation."""

    # ── Validate inputs ──────────────────────────────────────────────────────
    if total_packets < 1:
        raise ValueError("total_packets must be >= 1")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be > 0")

    channel = NetworkChannel(packet_loss_prob, ack_loss_prob, delay_ms, seed)

    result = SimulationResult(
        simulation_id=str(uuid.uuid4()),
        protocol="stop_and_wait",
        config={
            "total_packets": total_packets,
            "packet_loss_prob": packet_loss_prob,
            "ack_loss_prob": ack_loss_prob,
            "delay_ms": delay_ms,
            "timeout_ms": timeout_ms,
            "seed": seed,
        },
        total_packets=total_packets,
    )

    events: list[SimEvent] = []
    _tie = 0  # monotone tie-breaker

    def push(evt: SimEvent) -> None:
        nonlocal _tie
        evt.tie = _tie
        _tie += 1
        heapq.heappush(events, evt)

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
    current_seq: int = 0          # next packet to send
    retries: int = 0              # retries for current packet
    now: float = 0.0              # current simulation time
    # Each packet has a "timeout cookie" – an integer that becomes stale
    # when the packet is acked before the timer fires.
    timeout_cookie: dict[int, int] = {}  # seq -> expected cookie value
    cookie_counter: int = 0

    delivered: set[int] = set()
    sender_acked: set[int] = set()

    def schedule_timeout(seq: int, send_time: float) -> None:
        nonlocal cookie_counter
        cookie_counter += 1
        timeout_cookie[seq] = cookie_counter
        push(SimEvent(
            time=send_time + timeout_ms,
            etype=EventType.TIMEOUT,
            seq=seq,
            description=f"Timeout for packet {seq}",
            attempt=retries + 1,
            window_base=seq,
            window_end=seq,
            tie=0,  # overwritten by push()
        ))
        # Store cookie in event — we tag it via a custom attr via description hack
        # Instead store cookie in global map checked at processing time

    def send_packet(seq: int, current_time: float, attempt: int) -> None:
        dropped = channel.will_drop_packet()
        result.total_attempts += 1
        if attempt > 1:
            result.retransmissions += 1

        evt = SimEvent(
            time=current_time,
            etype=EventType.RETRANSMIT if attempt > 1 else EventType.PACKET_SENT,
            seq=seq,
            dropped=dropped,
            attempt=attempt,
            description=(
                f"{'Retransmit' if attempt > 1 else 'Send'} packet {seq} "
                f"(attempt {attempt})"
                + (" — DROPPED by network" if dropped else "")
            ),
            window_base=seq,
            window_end=seq,
            tie=0,
        )
        log(evt)

        if dropped:
            result.dropped_data_packets += 1
            # timeout already scheduled or will be below
        else:
            arrival = channel.arrival_time(current_time)
            push(SimEvent(
                time=arrival,
                etype=EventType.PACKET_RECEIVED,
                seq=seq,
                dropped=False,
                attempt=attempt,
                description=f"Packet {seq} arrived at receiver",
                window_base=seq,
                window_end=seq,
                tie=0,
            ))
        # Always schedule timeout after sending
        schedule_timeout(seq, current_time)

    # ── Kick off first packet ─────────────────────────────────────────────────
    send_packet(current_seq, now, attempt=1)

    # ── Event loop ────────────────────────────────────────────────────────────
    while events:
        evt = heapq.heappop(events)
        now = evt.time

        if evt.etype == EventType.PACKET_RECEIVED:
            seq = evt.seq
            log(evt)

            if seq in delivered:
                # Duplicate — receiver sends ACK again but does not re-deliver
                dup_evt = SimEvent(
                    time=now,
                    etype=EventType.PACKET_DUPLICATE,
                    seq=seq,
                    description=f"Duplicate packet {seq} discarded",
                    tie=0,
                )
                log(dup_evt)
                # Still send ACK (receiver re-acks to unblock sender)
                _send_ack(seq, now, result, channel, events, log, push, sender_acked)
            else:
                delivered.add(seq)
                result.delivered_packets += 1
                deliver_evt = SimEvent(
                    time=now,
                    etype=EventType.PACKET_DELIVERED,
                    seq=seq,
                    description=f"Packet {seq} delivered to application",
                    tie=0,
                )
                log(deliver_evt)
                _send_ack(seq, now, result, channel, events, log, push, sender_acked)

        elif evt.etype == EventType.ACK_RECEIVED:
            ack_seq = evt.ack_seq
            log(evt)

            if ack_seq in sender_acked:
                # Duplicate ACK — ignore (already advanced)
                dup = SimEvent(
                    time=now,
                    etype=EventType.ACK_DUPLICATE,
                    ack_seq=ack_seq,
                    description=f"Duplicate ACK({ack_seq}) ignored",
                    tie=0,
                )
                log(dup)
                continue

            if ack_seq == current_seq:
                # Valid new ACK
                sender_acked.add(ack_seq)
                result.acked_packets += 1
                # Invalidate timeout cookie
                timeout_cookie.pop(current_seq, None)
                retries = 0

                win_evt = SimEvent(
                    time=now,
                    etype=EventType.WINDOW_ADVANCE,
                    seq=current_seq,
                    ack_seq=ack_seq,
                    description=f"ACK({ack_seq}) received — advancing to packet {current_seq + 1}",
                    window_base=current_seq + 1,
                    window_end=current_seq + 1,
                    tie=0,
                )
                log(win_evt)

                current_seq += 1

                if current_seq >= total_packets:
                    # All done
                    done_evt = SimEvent(
                        time=now,
                        etype=EventType.TRANSFER_COMPLETE,
                        description="All packets delivered and acknowledged",
                        tie=0,
                    )
                    log(done_evt)
                    result.status = "completed"
                    result.completion_time_ms = now
                    break
                else:
                    # Send next packet
                    send_packet(current_seq, now, attempt=1)

        elif evt.etype == EventType.TIMEOUT:
            seq = evt.seq
            # Check if this timeout is stale (packet already acked)
            if seq in sender_acked or seq in timeout_cookie and timeout_cookie.get(seq) is None:
                continue
            if seq != current_seq:
                continue  # stale for a previous packet

            log(evt)
            result.timeouts += 1
            retries += 1

            if retries > MAX_RETRIES:
                fail_evt = SimEvent(
                    time=now,
                    etype=EventType.TRANSFER_FAILED,
                    seq=seq,
                    description=(
                        f"Packet {seq} exceeded max retries ({MAX_RETRIES}). "
                        "Transfer failed."
                    ),
                    tie=0,
                )
                log(fail_evt)
                result.status = "failed"
                result.failure_reason = (
                    f"Packet {seq} exceeded {MAX_RETRIES} retransmission attempts."
                )
                result.completion_time_ms = now
                break

            send_packet(current_seq, now, attempt=retries + 1)

    if result.status == "pending":
        result.status = "completed" if result.delivered_packets == total_packets else "failed"
        result.completion_time_ms = now

    compute_metrics(result)
    return result


def _send_ack(
    seq: int,
    now: float,
    result: SimulationResult,
    channel: NetworkChannel,
    events: list,
    log,
    push,
    sender_acked: set,
) -> None:
    """Helper: receiver sends an ACK for packet *seq*."""
    dropped = channel.will_drop_ack()
    ack_evt = SimEvent(
        time=now,
        etype=EventType.ACK_SENT,
        seq=seq,
        ack_seq=seq,
        dropped=dropped,
        description=f"ACK({seq}) sent" + (" — DROPPED" if dropped else ""),
        tie=0,
    )
    log(ack_evt)

    if dropped:
        result.dropped_ack_packets += 1
    else:
        arrival = channel.arrival_time(now)
        push(SimEvent(
            time=arrival,
            etype=EventType.ACK_RECEIVED,
            seq=seq,
            ack_seq=seq,
            description=f"ACK({seq}) received at sender",
            tie=0,
        ))
