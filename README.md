# Reliable Data Transmission Protocol Simulator

> **PBL Academic Project:** Computer Networks & Data Communications  
> **Interactive ARQ Simulation & Analytics Platform**  
> *Explore packet delivery, error recovery, and ARQ protocol performance across unreliable network channels.*

---

## 1. Abstract

Reliable Data Transmission (RDT) is a cornerstone of computer networking, underpinning transport layer protocols such as TCP and link-layer framing standards. In physical networks, frames and packets are subject to bit errors, unpredictable buffer overflow drops, delays, and reordering. Automatic Repeat reQuest (ARQ) protocols guarantee complete and sequential data delivery over unreliable channels using acknowledgement packets and timeout-driven retransmissions. 

This project provides a complete, interactive, web-based simulation and educational benchmarking dashboard implementing the three classic ARQ protocols: **Stop-and-Wait ARQ**, **Go-Back-N ARQ**, and **Selective Repeat ARQ**. Built on a deterministic discrete-event simulation engine in Python, the system enables students, educators, and engineers to observe packet flights, dropped packets, cumulative versus individual acknowledgements, sliding window transitions, and performance metrics (throughput, delay, delivery ratio, and protocol efficiency) under customizable network loss and latency conditions.

---

## 2. Problem Statement

Theoretical networking textbooks (e.g., Kurose & Ross, Tanenbaum) describe ARQ algorithms through static ladder diagrams and mathematical formulas. However, students frequently struggle to internalize dynamic edge cases, such as:
1. Distinguishing between a dropped data packet and a dropped acknowledgement.
2. The cascade effect of out-of-order packet discards in Go-Back-N versus buffer staging in Selective Repeat.
3. The impact of round-trip propagation delay on channel utilization when window size is restricted.
4. Stale timeout hazards and duplicate acknowledgement handling.

Existing tools often rely on heavy simulation suites (e.g., NS-3, OMNeT++) with steep learning curves or simplistic visual applets that execute non-deterministic `sleep()` calls disconnected from genuine network metrics.

---

## 3. Objectives

- **Develop Independent Implementations:** Implement pure Python discrete-event simulation models for Stop-and-Wait, Go-Back-N, and Selective Repeat ARQ protocols.
- **Support Comprehensive Parameterization:** Enable granular configuration of packet counts (1–100), data packet drop probability (0–50%), ACK drop probability (0–50%), one-way transmission delay, timeout durations, and sliding window sizes (1–20).
- **Ensure Deterministic Reproducibility:** Support seeded pseudo-random number generation so faculty and students can repeat identical network drop sequences across protocol comparisons.
- **Live Interactive Visualization:** Render real-time packet flights, drop animations, window slot indicators, and a millisecond-precision event timeline.
- **Empirical Benchmarking & Analytics:** Calculate throughput (bps), protocol efficiency (%), packet delivery ratio (%), retransmission counts, and simulated completion time without confounding animation delays with network latency.
- **Educational Self-Assessment:** Provide interactive quizzes, protocol walkthroughs, and automated performance synthesis.

---

## 4. Scope

- **In Scope:**
  - Discrete-event modeling of uncorrupted packet transfers over lossy, delayed channels.
  - Cumulative acknowledgements (Go-Back-N) and individual acknowledgements (Selective Repeat).
  - Out-of-order packet buffering and sequential in-order delivery to the application layer.
  - Multi-protocol comparative benchmarking under identical channel seeds.
  - RESTful JSON API endpoints for programmatic simulation execution.
  - Full automated testing suite with `pytest`.
- **Out of Scope:**
  - Physical bit-level checksum error correction (e.g., CRC polynomials).
  - Dynamic TCP-style congestion control (e.g., AIMD, Slow Start).

---

## 5. System & Software Requirements

- **Operating System:** Windows 10/11, Linux, or macOS
- **Runtime:** Python 3.11, 3.12, or 3.13
- **Dependencies:** Flask 3.1.0, pytest 8.3.5, pytest-flask 1.3.0
- **Browser:** Modern Chromium (Chrome, Edge), Firefox, or Safari with JavaScript and HTML5 Canvas support.

---

## 6. Architecture & Modular Structure

```
d:/cn/
├── app.py                      # Flask application factory, web routes, REST endpoints
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
├── README.md                   # Comprehensive project documentation
├── simulator/                  # Core Discrete-Event Simulation Engine
│   ├── __init__.py
│   ├── models.py               # Data models: Packet, SimEvent, SimulationResult
│   ├── network.py              # Unreliable NetworkChannel with loss & delay PRNG
│   ├── metrics.py              # Throughput, efficiency, and delivery ratio formulas
│   ├── stop_and_wait.py        # Stop-and-Wait ARQ discrete-event implementation
│   ├── go_back_n.py            # Go-Back-N ARQ with sliding window & cumulative ACKs
│   ├── selective_repeat.py     # Selective Repeat ARQ with buffering & individual ACKs
│   └── engine.py               # Dispatcher, input validator, and comparison synthesizer
├── templates/                  # Jinja2 HTML5 Templates (Dark Navy Aesthetic)
│   ├── base.html               # Navigation bar, common headers, and footer
│   ├── index.html              # Home Dashboard & networking concepts overview
│   ├── simulator.html          # Interactive animation canvas & configuration panel
│   ├── comparison.html         # Side-by-side benchmark with 4 Chart.js analytics
│   ├── learning.html           # Learning Center, diagrams, quizzes with reveal toggles
│   └── about.html              # Project architecture & PBL documentation
├── static/
│   ├── css/
│   │   └── style.css           # Custom styling, dark navy palette, packet colors
│   └── js/
│       ├── app.js              # Storage history API, formatters, alert helpers
│       ├── simulator.js        # Timeline playback loop, packet flights, event table
│       ├── comparison.js       # Chart.js rendering, multi-protocol runner
│       └── learning.js         # Interactive quiz reveal toggles & search filter
├── tests/                      # Automated Test Suite (pytest)
│   ├── test_stop_and_wait.py
│   ├── test_go_back_n.py
│   ├── test_selective_repeat.py
│   ├── test_metrics.py
│   └── test_api.py
└── docs/                       # PBL Documentation Deliverables
    ├── PROJECT_REPORT.md       # Full PBL Project Report
    ├── VIVA_QUESTIONS.md       # 20+ Viva examination questions & answers
    └── DEMO_GUIDE.md           # Step-by-step evaluator demonstration guide
```

---

## 7. Protocol Algorithms & Mechanics

### A. Stop-and-Wait ARQ
1. Sender transmits packet `seq` and schedules a timeout event at `now + timeout_ms`.
2. Sender enters a waiting state; no subsequent packets are transmitted until an acknowledgement arrives.
3. If packet arrives at receiver intact:
   - If `seq == expected`: Delivers packet to application, increments `expected`, sends `ACK(seq)`.
   - If `seq < expected` (duplicate caused by lost/delayed ACK): Discards payload, re-sends `ACK(seq)` to unblock sender.
4. If ACK arrives at sender: Cancels active timer, increments `seq`, and transmits next frame.
5. If timer expires before ACK arrives: Sender increments retransmission count and retransmits packet `seq`.

### B. Go-Back-N ARQ
1. Maintains a sender sliding window `[sender_base, sender_base + W - 1]`.
2. Packets up to window capacity are transmitted in continuous pipeline.
3. Cumulative ACKs: `ACK(k)` confirms all packets up to and including sequence `k`.
4. Receiver operates with window size 1: out-of-order packets are discarded without buffering. The receiver re-acknowledges the last in-order frame.
5. On timeout of the oldest unacknowledged packet (`sender_base`): Sender retransmits **all** outstanding packets currently in flight from `sender_base` to `next_seq - 1`.

### C. Selective Repeat ARQ
1. Maintains both sender window and receiver window of size `W`.
2. Individual ACKs: `ACK(k)` explicitly confirms only packet `k`.
3. Receiver out-of-order buffering: Valid arriving packets within `[recv_base, recv_base + W - 1]` are buffered.
4. When `recv_base` arrives, the receiver delivers all consecutively buffered frames to the application layer and slides `recv_base` forward.
5. Independent timers: Only the specific packet whose timer expired is retransmitted.

---

## 8. Documented Metric Formulations

All metrics follow formal definitions using an assumed packet payload size of **1024 bytes (8192 bits)**:

| Metric | Mathematical Definition | Explanation |
| :--- | :--- | :--- |
| **Transmission Attempts** | $\sum \text{Data Packet Transmissions}$ | Total attempts including original and retransmissions. |
| **Retransmissions** | $\text{Attempts} - \text{Initial Transmissions}$ | Extra packet transmissions caused by drops/timeouts. |
| **Delivery Ratio (%)** | $\frac{\text{Unique Packets Delivered}}{\text{Total Configured Packets}} \times 100$ | Measures transfer completeness (Target: 100%). |
| **Throughput (bps)** | $\frac{\text{Unique Delivered Bits}}{\text{Elapsed Simulated Seconds}}$ | Effective data transmission rate over simulated time. |
| **Protocol Efficiency (%)** | $\frac{\text{Unique Delivered Bits}}{\text{Total Transmitted Data Bits}} \times 100$ | Useful data bits divided by total transmitted data bits. |

*Safety: If elapsed time is 0 or total attempts are 0, formulas safely return 0.0 to prevent division-by-zero crashes.*

---

## 9. REST API Reference

### 1. `GET /api/health`
Health check and service status.
- **Response `200`:** `{"status": "healthy", "service": "...", "version": "1.0.0"}`

### 2. `GET /api/protocols`
Lists supported ARQ protocols, window types, and acknowledgement modes.

### 3. `POST /api/simulate`
Executes a single discrete-event simulation.
- **Request Body (JSON):**
  ```json
  {
    "protocol": "selective_repeat",
    "total_packets": 20,
    "window_size": 4,
    "packet_loss_prob": 0.10,
    "ack_loss_prob": 0.05,
    "delay_ms": 200,
    "timeout_ms": 600,
    "seed": 42
  }
  ```
- **Response `200`:** Full simulation payload with events list, metrics, packet statistics, and completion status.

### 4. `POST /api/compare`
Runs Stop-and-Wait, Go-Back-N, and Selective Repeat under identical configuration and seed.
- **Response `200`:** Results for all three protocols plus auto-generated dynamic interpretation text.

---

## 10. Installation & Execution Guide (Windows)

### Step 1: Open Terminal in Workspace
Open Command Prompt or PowerShell in the project directory (`d:\cn`):

### Step 2: Create and Activate Virtual Environment
```powershell
py -3 -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Required Packages
```powershell
pip install -r requirements.txt
```

### Step 4: Run the Test Suite
```powershell
pytest -v
```
*Expected: 24 passed in < 1 second.*

### Step 5: Launch the Web Application
```powershell
python app.py
```
Open your browser and navigate to:
**`http://127.0.0.1:5000`**

---

## 11. Limitations & Future Enhancements

- **Current Limitations:**
  - Network delay is modeled with static propagation delay rather than stochastic delay distributions (e.g., Pareto or Normal jitter).
  - Sequence numbers are displayed as absolute integers for educational clarity rather than modulo $2^k$ bit fields.
- **Future Enhancements:**
  - Add Congestion Window ($cwnd$) and Slow-Start dynamic modeling (TCP Reno / Cubic simulation).
  - Support bidirectional data flow with piggybacked acknowledgements.
  - Export simulation event traces to Wireshark `.pcap` format.

---

## 12. References

1. Kurose, J. F., & Ross, K. W. (2021). *Computer Networking: A Top-Down Approach* (8th ed.). Pearson.
2. Tanenbaum, A. S., & Wetherall, D. J. (2014). *Computer Networks* (5th ed.). Pearson.
3. RFC 793: *Transmission Control Protocol* (DARPA Internet Program Protocol Specification).
4. RFC 2018: *TCP Selective Acknowledgment Options*.
#   R e l i a b l e - D a t a - T r a n s m i s s i o n - P r o t o c o l - S i m u l a t o r  
 