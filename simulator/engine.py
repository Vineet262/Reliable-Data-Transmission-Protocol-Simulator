"""
simulator/engine.py
High-level entry point that dispatches simulation requests to the
appropriate protocol module and assembles comparison results.
"""
from __future__ import annotations
from typing import Optional

from simulator import stop_and_wait, go_back_n, selective_repeat
from simulator.models import SimulationResult

# Input validation limits
MAX_PACKETS = 100
MAX_WINDOW = 20
MAX_LOSS_PROB = 0.50
MAX_DELAY_MS = 5000.0
MAX_TIMEOUT_MS = 10000.0
MIN_TIMEOUT_MS = 1.0


def validate_config(config: dict) -> list[str]:
    """Return a list of error strings. Empty list means valid."""
    errors: list[str] = []

    n = config.get("total_packets")
    if not isinstance(n, int) or not (1 <= n <= MAX_PACKETS):
        errors.append(f"total_packets must be an integer in [1, {MAX_PACKETS}]")

    ploss = config.get("packet_loss_prob", 0)
    if not isinstance(ploss, (int, float)) or not (0 <= ploss <= MAX_LOSS_PROB):
        errors.append(f"packet_loss_prob must be in [0, {MAX_LOSS_PROB}]")

    aloss = config.get("ack_loss_prob", 0)
    if not isinstance(aloss, (int, float)) or not (0 <= aloss <= MAX_LOSS_PROB):
        errors.append(f"ack_loss_prob must be in [0, {MAX_LOSS_PROB}]")

    delay = config.get("delay_ms", 200)
    if not isinstance(delay, (int, float)) or not (0 <= delay <= MAX_DELAY_MS):
        errors.append(f"delay_ms must be in [0, {MAX_DELAY_MS}]")

    timeout = config.get("timeout_ms", 600)
    if not isinstance(timeout, (int, float)) or not (MIN_TIMEOUT_MS <= timeout <= MAX_TIMEOUT_MS):
        errors.append(f"timeout_ms must be in [{MIN_TIMEOUT_MS}, {MAX_TIMEOUT_MS}]")

    w = config.get("window_size", 4)
    if not isinstance(w, int) or not (1 <= w <= MAX_WINDOW):
        errors.append(f"window_size must be an integer in [1, {MAX_WINDOW}]")

    seed = config.get("seed")
    if seed is not None and not isinstance(seed, int):
        errors.append("seed must be an integer or null")

    return errors


def run_simulation(config: dict) -> SimulationResult:
    """
    Run a single protocol simulation based on config['protocol'].
    Raises ValueError for invalid config.
    """
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))

    protocol = config.get("protocol", "stop_and_wait")
    kwargs = {
        "total_packets": int(config["total_packets"]),
        "packet_loss_prob": float(config.get("packet_loss_prob", 0.10)),
        "ack_loss_prob": float(config.get("ack_loss_prob", 0.05)),
        "delay_ms": float(config.get("delay_ms", 200.0)),
        "timeout_ms": float(config.get("timeout_ms", 600.0)),
        "seed": config.get("seed"),
    }
    window_size = int(config.get("window_size", 4))

    if protocol == "stop_and_wait":
        return stop_and_wait.run(**kwargs)
    elif protocol == "go_back_n":
        return go_back_n.run(**kwargs, window_size=window_size)
    elif protocol == "selective_repeat":
        return selective_repeat.run(**kwargs, window_size=window_size)
    else:
        raise ValueError(f"Unknown protocol: {protocol!r}")


def run_comparison(config: dict) -> dict:
    """
    Run all three protocols with the same base configuration and random seed.
    Returns a dict with keys 'stop_and_wait', 'go_back_n', 'selective_repeat',
    each containing the serialisable result dict.
    """
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))

    base = dict(config)
    results = {}

    for proto in ("stop_and_wait", "go_back_n", "selective_repeat"):
        base["protocol"] = proto
        r = run_simulation(base)
        results[proto] = _result_to_dict(r)

    # Automatically generate interpretation from actual results
    results["interpretation"] = _generate_interpretation(results)
    return results


def _result_to_dict(r: SimulationResult) -> dict:
    return {
        "simulation_id": r.simulation_id,
        "protocol": r.protocol,
        "config": r.config,
        "events": r.events,
        "total_packets": r.total_packets,
        "delivered_packets": r.delivered_packets,
        "acked_packets": r.acked_packets,
        "dropped_data_packets": r.dropped_data_packets,
        "dropped_ack_packets": r.dropped_ack_packets,
        "total_attempts": r.total_attempts,
        "retransmissions": r.retransmissions,
        "timeouts": r.timeouts,
        "completion_time_ms": r.completion_time_ms,
        "throughput_bps": r.throughput_bps,
        "delivery_ratio": r.delivery_ratio,
        "efficiency": r.efficiency,
        "payload_size_bytes": r.payload_size_bytes,
        "status": r.status,
        "failure_reason": r.failure_reason,
    }


def _generate_interpretation(results: dict) -> str:
    """Build a plain-text interpretation from actual measured results."""
    protocols = ["stop_and_wait", "go_back_n", "selective_repeat"]
    labels = {
        "stop_and_wait": "Stop-and-Wait",
        "go_back_n": "Go-Back-N",
        "selective_repeat": "Selective Repeat",
    }

    completed = {p: results[p]["status"] == "completed" for p in protocols}

    # Fastest (lowest completion time among completed)
    times = {p: results[p]["completion_time_ms"] for p in protocols if completed[p]}
    fastest = min(times, key=times.get) if times else None

    # Fewest retransmissions
    retxs = {p: results[p]["retransmissions"] for p in protocols if completed[p]}
    fewest_retx = min(retxs, key=retxs.get) if retxs else None

    loss = results["stop_and_wait"]["config"].get("packet_loss_prob", 0)
    loss_pct = round(loss * 100)

    lines = []

    if fastest:
        lines.append(
            f"**Fastest protocol:** {labels[fastest]} completed the transfer in "
            f"{times[fastest]:.0f} ms simulated time."
        )
    else:
        lines.append("No protocol completed the transfer successfully.")

    if fewest_retx is not None:
        lines.append(
            f"**Fewest retransmissions:** {labels[fewest_retx]} required only "
            f"{retxs[fewest_retx]} retransmission(s)."
        )

    if loss_pct > 0:
        lines.append(
            f"**Effect of {loss_pct}% packet loss:** Higher loss increases retransmissions "
            "and completion time for all protocols. Stop-and-Wait is most affected because "
            "it idles the channel waiting for each acknowledgement."
        )

    if times.get("stop_and_wait") and (times.get("go_back_n") or times.get("selective_repeat")):
        sw_time = times.get("stop_and_wait", float("inf"))
        best_sw = min(times.get("go_back_n", float("inf")),
                      times.get("selective_repeat", float("inf")))
        if best_sw < sw_time:
            ratio = round(sw_time / best_sw, 1)
            lines.append(
                f"**Sliding-window advantage:** Go-Back-N or Selective Repeat finished up to "
                f"{ratio}× faster than Stop-and-Wait because they keep the channel busy with "
                "multiple in-flight packets instead of waiting for one ACK at a time."
            )

    if completed.get("selective_repeat") and completed.get("go_back_n"):
        sr_retx = results["selective_repeat"]["retransmissions"]
        gbn_retx = results["go_back_n"]["retransmissions"]
        if sr_retx <= gbn_retx:
            lines.append(
                f"**Selective Repeat efficiency:** SR needed {sr_retx} retransmission(s) "
                f"vs. GBN's {gbn_retx} because SR only resends the specific lost packet, "
                "not all outstanding packets in the window."
            )
        else:
            lines.append(
                f"**Go-Back-N note:** In this run GBN had {gbn_retx} retransmission(s) vs. "
                f"SR's {sr_retx}. This can happen when individual timeouts in SR trigger "
                "repeated retransmissions for different packets."
            )

    return "\n\n".join(lines) if lines else "Run the comparison to see the interpretation."
