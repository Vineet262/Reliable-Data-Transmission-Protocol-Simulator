"""
app.py
Flask web application and REST API for Reliable Data Transmission Protocol Simulator.
"""
from __future__ import annotations
import traceback
from flask import Flask, jsonify, render_template, request
from simulator.engine import run_simulation, run_comparison, validate_config, _result_to_dict

app = Flask(__name__)

# Protocol metadata definition
PROTOCOLS = [
    {
        "id": "stop_and_wait",
        "name": "Stop-and-Wait ARQ",
        "description": "Sender transmits one packet and waits for its acknowledgement before sending the next packet.",
        "has_window": False,
        "ack_type": "Individual (1-bit / absolute)",
        "retransmission_scope": "Single timed-out packet",
        "receiver_buffering": False,
        "default_window": 1
    },
    {
        "id": "go_back_n",
        "name": "Go-Back-N ARQ",
        "description": "Sender transmits multiple packets within a sliding window. On timeout, all outstanding packets from the oldest unacknowledged packet are retransmitted.",
        "has_window": True,
        "ack_type": "Cumulative",
        "retransmission_scope": "All unacknowledged in-flight packets",
        "receiver_buffering": False,
        "default_window": 4
    },
    {
        "id": "selective_repeat",
        "name": "Selective Repeat ARQ",
        "description": "Sender transmits multiple packets within a sliding window. Only unacknowledged or timed-out packets are retransmitted. The receiver buffers out-of-order packets.",
        "has_window": True,
        "ack_type": "Individual",
        "retransmission_scope": "Only specifically missing/timed-out packets",
        "receiver_buffering": True,
        "default_window": 4
    }
]

# --- HTML Web Page Routes ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/simulator")
def simulator_page():
    return render_template("simulator.html")

@app.route("/comparison")
def comparison_page():
    return render_template("comparison.html")

@app.route("/learning")
def learning_page():
    return render_template("learning.html")

@app.route("/about")
def about_page():
    return render_template("about.html")


# --- REST API Endpoints ---

@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Reliable Data Transmission Protocol Simulator",
        "version": "1.0.0"
    }), 200

@app.route("/api/protocols", methods=["GET"])
def api_protocols():
    """List available ARQ protocols and characteristics."""
    return jsonify({
        "success": True,
        "protocols": PROTOCOLS
    }), 200

@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """
    Execute a protocol simulation with given parameters.
    Expects JSON payload with configuration keys.
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "errors": ["Request payload must be valid JSON"]
        }), 400

    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "errors": ["Payload must be a JSON object"]
        }), 400

    errors = validate_config(payload)
    if errors:
        return jsonify({
            "success": False,
            "errors": errors
        }), 400

    try:
        sim_result = run_simulation(payload)
        data = _result_to_dict(sim_result)
        return jsonify({
            "success": True,
            "simulation": data
        }), 200
    except ValueError as ve:
        return jsonify({
            "success": False,
            "errors": [str(ve)]
        }), 400
    except Exception as e:
        # Avoid leaking full server stack trace to client
        app.logger.error("Simulation error: %s", traceback.format_exc())
        return jsonify({
            "success": False,
            "errors": ["An internal error occurred during simulation processing."]
        }), 500

@app.route("/api/compare", methods=["POST"])
def api_compare():
    """
    Run Stop-and-Wait, Go-Back-N, and Selective Repeat under identical settings.
    """
    if not request.is_json:
        return jsonify({
            "success": False,
            "errors": ["Request payload must be valid JSON"]
        }), 400

    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify({
            "success": False,
            "errors": ["Payload must be a JSON object"]
        }), 400

    errors = validate_config(payload)
    if errors:
        return jsonify({
            "success": False,
            "errors": errors
        }), 400

    try:
        comparison_data = run_comparison(payload)
        return jsonify({
            "success": True,
            "comparison": comparison_data
        }), 200
    except ValueError as ve:
        return jsonify({
            "success": False,
            "errors": [str(ve)]
        }), 400
    except Exception as e:
        app.logger.error("Comparison error: %s", traceback.format_exc())
        return jsonify({
            "success": False,
            "errors": ["An internal error occurred during comparison processing."]
        }), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
