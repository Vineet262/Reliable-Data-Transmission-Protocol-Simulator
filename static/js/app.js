/**
 * app.js
 * Common client-side utilities and simulation history management.
 */

const HISTORY_STORAGE_KEY = 'arq_simulation_history_v1';
const MAX_HISTORY_ENTRIES = 25;

/**
 * Storage API for Simulation History (Local Browser Storage)
 */
const SimHistory = {
    getAll() {
        try {
            const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            console.warn("Storage unavailable:", e);
            return [];
        }
    },

    save(runData) {
        try {
            const history = this.getAll();
            const entry = {
                id: runData.simulation_id || ('sim_' + Date.now()),
                protocol: runData.protocol,
                timestamp: new Date().toISOString(),
                config: runData.config || {},
                status: runData.status,
                completion_time_ms: runData.completion_time_ms,
                total_attempts: runData.total_attempts,
                retransmissions: runData.retransmissions,
                throughput_bps: runData.throughput_bps,
                delivery_ratio: runData.delivery_ratio,
                efficiency: runData.efficiency
            };
            // Prepend new run and keep up to MAX_HISTORY_ENTRIES
            history.unshift(entry);
            if (history.length > MAX_HISTORY_ENTRIES) {
                history.pop();
            }
            localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
            return entry;
        } catch (e) {
            console.warn("Failed to persist run to storage:", e);
            return null;
        }
    },

    clear() {
        try {
            localStorage.removeItem(HISTORY_STORAGE_KEY);
            return true;
        } catch (e) {
            console.warn("Failed to clear history:", e);
            return false;
        }
    }
};

/**
 * Format bits per second to human-readable string (bps, Kbps, Mbps)
 */
function formatThroughput(bps) {
    if (!bps || bps <= 0) return '0 bps';
    if (bps >= 1_000_000) return (bps / 1_000_000).toFixed(2) + ' Mbps';
    if (bps >= 1_000) return (bps / 1_000).toFixed(2) + ' Kbps';
    return bps.toFixed(1) + ' bps';
}

/**
 * Format protocol identifier into readable title
 */
function formatProtocolName(protoId) {
    switch (protoId) {
        case 'stop_and_wait': return 'Stop-and-Wait ARQ';
        case 'go_back_n': return 'Go-Back-N ARQ';
        case 'selective_repeat': return 'Selective Repeat ARQ';
        default: return protoId || 'Unknown Protocol';
    }
}

/**
 * Generate colored badge HTML for an event type
 */
function getEventBadgeHtml(type) {
    switch (type) {
        case 'PACKET_SENT':
            return '<span class="packet-badge badge-transit"><i class="bi bi-arrow-right-short"></i> PKT SENT</span>';
        case 'PACKET_RECEIVED':
            return '<span class="packet-badge badge-transit"><i class="bi bi-box-arrow-in-down"></i> PKT RECV</span>';
        case 'PACKET_DELIVERED':
            return '<span class="packet-badge badge-delivered"><i class="bi bi-check-circle-fill"></i> DELIVERED</span>';
        case 'PACKET_DROPPED':
            return '<span class="packet-badge badge-dropped"><i class="bi bi-x-octagon-fill"></i> PKT DROPPED</span>';
        case 'PACKET_DUPLICATE':
            return '<span class="packet-badge badge-dropped"><i class="bi bi-files"></i> PKT DISCARD</span>';
        case 'PACKET_BUFFERED':
            return '<span class="packet-badge badge-buffered"><i class="bi bi-inbox-fill"></i> BUFFERED</span>';
        case 'ACK_SENT':
            return '<span class="packet-badge badge-ack"><i class="bi bi-arrow-left-short"></i> ACK SENT</span>';
        case 'ACK_RECEIVED':
            return '<span class="packet-badge badge-delivered"><i class="bi bi-check2-all"></i> ACK RECV</span>';
        case 'ACK_DROPPED':
            return '<span class="packet-badge badge-dropped"><i class="bi bi-x-octagon"></i> ACK DROPPED</span>';
        case 'ACK_DUPLICATE':
            return '<span class="packet-badge badge-timeout"><i class="bi bi-arrow-repeat"></i> ACK DUP</span>';
        case 'TIMEOUT':
            return '<span class="packet-badge badge-timeout"><i class="bi bi-clock-history"></i> TIMEOUT</span>';
        case 'RETRANSMIT':
            return '<span class="packet-badge badge-timeout"><i class="bi bi-arrow-clockwise"></i> RETRANSMIT</span>';
        case 'WINDOW_ADVANCE':
            return '<span class="packet-badge badge-buffered"><i class="bi bi-layout-sidebar-inset-reverse"></i> WIN ADV</span>';
        case 'TRANSFER_COMPLETE':
            return '<span class="packet-badge badge-delivered"><i class="bi bi-trophy-fill"></i> COMPLETED</span>';
        case 'TRANSFER_FAILED':
            return '<span class="packet-badge badge-dropped"><i class="bi bi-exclamation-triangle-fill"></i> FAILED</span>';
        default:
            return `<span class="packet-badge bg-secondary">${type}</span>`;
    }
}

/**
 * Toast / Alert banner helper
 */
function showAlert(containerId, message, type = 'danger') {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="bi ${type === 'danger' ? 'bi-exclamation-octagon' : 'bi-info-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
}
