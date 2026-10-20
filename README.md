# 📡 Reliable Data Transmission Protocol Simulator

A web-based interactive simulator for visualizing and comparing **ARQ (Automatic Repeat reQuest)** protocols used in reliable data transmission. Built with **Python (Flask)** on the backend and vanilla **HTML/CSS/JavaScript** on the frontend.

---

## 🚀 Live Demo

Run locally at: `http://127.0.0.1:5000`

---

## 📋 Table of Contents

- [Features](#-features)
- [Protocols Simulated](#-protocols-simulated)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [API Reference](#-api-reference)
- [Simulation Parameters](#-simulation-parameters)
- [Metrics Explained](#-metrics-explained)
- [Running Tests](#-running-tests)
- [Tech Stack](#-tech-stack)

---

## ✨ Features

- 🎛️ **Interactive Simulator** — Configure and run simulations for any of the three ARQ protocols with custom parameters
- 📊 **Side-by-Side Comparison** — Run all three protocols under identical conditions and compare performance metrics
- 📚 **Learning Mode** — Educational explanations of each protocol with animated diagrams
- 📈 **Real-Time Metrics** — View throughput, delivery ratio, efficiency, retransmissions, and completion time
- 🔁 **Full Event Log** — Step-by-step event trace showing every SEND, ACK, DROP, TIMEOUT, and RETRANSMIT
- 🌐 **REST API** — Fully documented JSON API for programmatic simulation access

---

## 🔬 Protocols Simulated

### 1. Stop-and-Wait ARQ
The simplest ARQ protocol. The sender transmits **one packet** and waits for its acknowledgement before sending the next.

- **ACK Type:** Individual (1-bit)
- **Retransmission:** Only the timed-out packet
- **Receiver Buffering:** None
- **Window Size:** Fixed at 1

### 2. Go-Back-N ARQ
A sliding-window protocol. The sender transmits multiple packets within a window. On timeout, **all packets from the oldest unacknowledged** packet onwards are retransmitted.

- **ACK Type:** Cumulative
- **Retransmission:** All unacknowledged in-flight packets
- **Receiver Buffering:** None (out-of-order packets are discarded)
- **Window Size:** Configurable (1–20)

### 3. Selective Repeat ARQ
The most efficient sliding-window protocol. Only **specifically lost or timed-out** packets are retransmitted. The receiver buffers out-of-order packets.

- **ACK Type:** Individual
- **Retransmission:** Only the missing/timed-out packet
- **Receiver Buffering:** Yes (out-of-order packets are held)
- **Window Size:** Configurable (1–20)

---

## 📁 Project Structure

```
reliable-data-transmission-protocol-simulator/
│
├── app.py                      # Flask app & REST API routes
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Pytest configuration
│
├── simulator/                  # Core simulation engine
│   ├── __init__.py
│   ├── engine.py               # Dispatcher, validator, comparison runner
│   ├── models.py               # Packet, SimEvent, SimulationResult dataclasses
│   ├── network.py              # Network layer (loss/delay simulation)
│   ├── metrics.py              # Throughput, efficiency, delivery ratio
│   ├── stop_and_wait.py        # Stop-and-Wait protocol implementation
│   ├── go_back_n.py            # Go-Back-N protocol implementation
│   └── selective_repeat.py     # Selective Repeat protocol implementation
│
├── static/
│   ├── css/
│   │   └── style.css           # Global styles
│   └── js/
│       ├── app.js              # Shared JS utilities
│       ├── simulator.js        # Simulator page logic
│       ├── comparison.js       # Comparison page logic
│       └── learning.js         # Learning page logic
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── simulator.html
│   ├── comparison.html
│   ├── learning.html
│   └── about.html
│
└── tests/                      # Pytest test suite
    ├── test_stop_and_wait.py
    ├── test_go_back_n.py
    ├── test_selective_repeat.py
    ├── test_metrics.py
    └── test_api.py
```

---

## 🛠️ Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Vineet262/Reliable-Data-Transmission-Protocol-Simulator.git
cd Reliable-Data-Transmission-Protocol-Simulator

# 2. Create and activate a virtual environment
python -m venv .venv

# On Windows
.venv\Scripts\activate

# On macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

The app will be available at **http://127.0.0.1:5000**

---

## 🌐 API Reference

All API endpoints return JSON. Base URL: `http://127.0.0.1:5000`

### `GET /api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "Reliable Data Transmission Protocol Simulator",
  "version": "1.0.0"
}
```

---

### `GET /api/protocols`
Returns metadata for all supported protocols.

**Response:**
```json
{
  "success": true,
  "protocols": [
    {
      "id": "stop_and_wait",
      "name": "Stop-and-Wait ARQ",
      "has_window": false,
      "ack_type": "Individual (1-bit / absolute)",
      "retransmission_scope": "Single timed-out packet",
      "receiver_buffering": false,
      "default_window": 1
    },
    ...
  ]
}
```

---

### `POST /api/simulate`
Run a simulation for a specific protocol.

**Request Body:**
```json
{
  "protocol": "go_back_n",
  "total_packets": 20,
  "packet_loss_prob": 0.10,
  "ack_loss_prob": 0.05,
  "delay_ms": 200,
  "timeout_ms": 600,
  "window_size": 4,
  "seed": 42
}
```

**Response:**
```json
{
  "success": true,
  "simulation": {
    "simulation_id": "...",
    "protocol": "go_back_n",
    "total_packets": 20,
    "delivered_packets": 20,
    "retransmissions": 3,
    "timeouts": 2,
    "completion_time_ms": 4600.0,
    "throughput_bps": 3584.0,
    "delivery_ratio": 1.0,
    "efficiency": 0.87,
    "events": [ ... ],
    "status": "completed"
  }
}
```

---

### `POST /api/compare`
Run all three protocols under identical settings and compare results.

**Request Body:** Same as `/api/simulate` (protocol field is ignored).

**Response:**
```json
{
  "success": true,
  "comparison": {
    "stop_and_wait": { ... },
    "go_back_n": { ... },
    "selective_repeat": { ... },
    "interpretation": "**Fastest protocol:** Selective Repeat completed the transfer in 2800 ms..."
  }
}
```

---

## ⚙️ Simulation Parameters

| Parameter | Type | Range | Default | Description |
|-----------|------|--------|---------|-------------|
| `protocol` | string | `stop_and_wait`, `go_back_n`, `selective_repeat` | `stop_and_wait` | ARQ protocol to simulate |
| `total_packets` | int | 1–100 | — | Number of data packets to deliver |
| `packet_loss_prob` | float | 0.0–0.5 | 0.10 | Probability a data packet is dropped |
| `ack_loss_prob` | float | 0.0–0.5 | 0.05 | Probability an ACK is dropped |
| `delay_ms` | float | 0–5000 | 200.0 | One-way propagation delay in ms |
| `timeout_ms` | float | 1–10000 | 600.0 | Sender retransmit timeout in ms |
| `window_size` | int | 1–20 | 4 | Sliding window size (GBN & SR only) |
| `seed` | int \| null | any | null | Random seed for reproducibility |

---

## 📊 Metrics Explained

| Metric | Description |
|--------|-------------|
| **Delivery Ratio** | `delivered_packets / total_packets` — fraction of packets successfully received |
| **Efficiency** | `total_packets / total_attempts` — ratio of useful transmissions to total |
| **Throughput (bps)** | `(delivered_packets × payload_size_bytes × 8) / completion_time_s` |
| **Completion Time** | Total simulated wall-clock time (ms) to deliver all packets |
| **Retransmissions** | Number of packets resent due to loss or timeout |
| **Timeouts** | Number of timer-expiry events that triggered retransmission |

---

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_go_back_n.py -v
```

Test files cover:
- Protocol correctness (all packets delivered)
- Retransmission logic under loss conditions
- Metrics calculation accuracy
- REST API response validation

---

## 🧰 Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, Flask 3.1 |
| Simulation Engine | Pure Python (event-driven, discrete-time) |
| Frontend | HTML5, Vanilla CSS, Vanilla JavaScript |
| Testing | pytest, pytest-flask |
| Version Control | Git / GitHub |

---

## 📖 Background

ARQ protocols are fundamental to reliable communication in networks. This simulator models them as **discrete-event systems**, advancing simulated time at each packet send, propagation delay, ACK, timeout, or retransmission event — giving an accurate picture of how each protocol behaves under real-world network conditions like packet loss and variable delay.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 👤 Author

**Vineet** — [GitHub](https://github.com/Vineet262)