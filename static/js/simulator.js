/**
 * simulator.js
 * Controls playback, discrete-event timeline rendering, and real-time animation.
 */

// Simulation Playback State
let currentSimulation = null;
let currentEventIndex = 0;
let playbackTimer = null;
let isPaused = false;
let playbackDelayMs = 500; // Animation speed, distinct from network delay

// Active flying packet DOM nodes
const activePackets = new Map();

document.addEventListener('DOMContentLoaded', () => {
    initFormListeners();
    initControlButtons();
    initLogFilters();
    renderRecentHistory();
});

function initFormListeners() {
    const protoSelect = document.getElementById('configProtocol');
    const windowGroup = document.getElementById('windowSizeGroup');
    const windowInput = document.getElementById('configWindowSize');

    function updateWindowVisibility() {
        const proto = protoSelect.value;
        if (proto === 'stop_and_wait') {
            windowGroup.style.opacity = '0.5';
            windowInput.disabled = true;
            windowInput.value = '1';
        } else {
            windowGroup.style.opacity = '1';
            windowInput.disabled = false;
            if (windowInput.value === '1') windowInput.value = '4';
        }
    }

    protoSelect.addEventListener('change', updateWindowVisibility);
    updateWindowVisibility();

    // Animation speed slider
    const speedSlider = document.getElementById('animSpeed');
    const speedLabel = document.getElementById('speedLabel');
    if (speedSlider) {
        speedSlider.addEventListener('input', () => {
            const val = parseFloat(speedSlider.value);
            // val is multiplier: 0.5x, 1x, 2x, 4x
            playbackDelayMs = Math.round(500 / val);
            if (speedLabel) speedLabel.textContent = `${val}x`;
            if (playbackTimer && !isPaused) {
                clearInterval(playbackTimer);
                playbackTimer = setInterval(advanceOneStep, playbackDelayMs);
            }
        });
    }
}

function initControlButtons() {
    document.getElementById('btnRunSim').addEventListener('click', handleRunSimulation);
    document.getElementById('btnPause').addEventListener('click', handlePause);
    document.getElementById('btnResume').addEventListener('click', handleResume);
    document.getElementById('btnStep').addEventListener('click', handleStepForward);
    document.getElementById('btnReset').addEventListener('click', handleReset);
}

function initLogFilters() {
    const filterInput = document.getElementById('logFilterText');
    const filterType = document.getElementById('logFilterType');
    const filterRetx = document.getElementById('logFilterRetxOnly');

    function applyFilter() {
        const query = (filterInput?.value || '').toLowerCase().trim();
        const typeVal = filterType?.value || 'ALL';
        const retxOnly = filterRetx?.checked || false;

        const rows = document.querySelectorAll('#eventLogTableBody tr');
        rows.forEach(tr => {
            const text = tr.textContent.toLowerCase();
            const rowType = tr.getAttribute('data-event-type') || '';
            const isRetx = tr.getAttribute('data-is-retx') === 'true';

            let show = true;
            if (query && !text.includes(query)) show = false;
            if (typeVal !== 'ALL' && rowType !== typeVal) show = false;
            if (retxOnly && !isRetx) show = false;

            tr.style.display = show ? '' : 'none';
        });
    }

    filterInput?.addEventListener('input', applyFilter);
    filterType?.addEventListener('change', applyFilter);
    filterRetx?.addEventListener('change', applyFilter);
}

async function handleRunSimulation() {
    const form = document.getElementById('simConfigForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    // Collect and convert form inputs
    const payload = {
        protocol: document.getElementById('configProtocol').value,
        total_packets: parseInt(document.getElementById('configTotalPackets').value, 10),
        packet_loss_prob: parseFloat(document.getElementById('configPacketLoss').value) / 100.0,
        ack_loss_prob: parseFloat(document.getElementById('configAckLoss').value) / 100.0,
        delay_ms: parseFloat(document.getElementById('configDelay').value),
        timeout_ms: parseFloat(document.getElementById('configTimeout').value),
        window_size: parseInt(document.getElementById('configWindowSize').value, 10),
    };

    const seedRaw = document.getElementById('configSeed').value.trim();
    if (seedRaw !== '') {
        payload.seed = parseInt(seedRaw, 10);
    }

    setControlsState({ running: true, paused: false });
    clearVisualization();

    try {
        const res = await fetch('/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!data.success) {
            showAlert('simAlertContainer', data.errors.join('<br>'), 'danger');
            setControlsState({ running: false, paused: false });
            return;
        }

        currentSimulation = data.simulation;
        currentEventIndex = 0;
        isPaused = false;

        // Persist to session history
        SimHistory.save(currentSimulation);
        renderRecentHistory();

        // Render summary metrics shell
        updateMetrics(currentSimulation);
        setupWindowDisplay(currentSimulation);

        // Start playback loop
        if (playbackTimer) clearInterval(playbackTimer);
        playbackTimer = setInterval(advanceOneStep, playbackDelayMs);

    } catch (err) {
        console.error(err);
        showAlert('simAlertContainer', 'Failed to communicate with simulation server.', 'danger');
        setControlsState({ running: false, paused: false });
    }
}

function handlePause() {
    if (!currentSimulation) return;
    isPaused = true;
    if (playbackTimer) clearInterval(playbackTimer);
    setControlsState({ running: true, paused: true });
}

function handleResume() {
    if (!currentSimulation) return;
    isPaused = false;
    if (playbackTimer) clearInterval(playbackTimer);
    playbackTimer = setInterval(advanceOneStep, playbackDelayMs);
    setControlsState({ running: true, paused: false });
}

function handleStepForward() {
    if (!currentSimulation) return;
    handlePause();
    advanceOneStep();
}

function handleReset() {
    if (playbackTimer) clearInterval(playbackTimer);
    playbackTimer = null;
    currentSimulation = null;
    currentEventIndex = 0;
    isPaused = false;
    clearVisualization();
    resetMetrics();
    setControlsState({ running: false, paused: false });
}

function setControlsState({ running, paused }) {
    document.getElementById('btnRunSim').disabled = running && !paused;
    document.getElementById('btnPause').disabled = !running || paused;
    document.getElementById('btnResume').disabled = !running || !paused;
    document.getElementById('btnStep').disabled = !running;
    document.getElementById('btnReset').disabled = !running && currentEventIndex === 0;
}

function advanceOneStep() {
    if (!currentSimulation || currentEventIndex >= currentSimulation.events.length) {
        if (playbackTimer) clearInterval(playbackTimer);
        playbackTimer = null;
        setControlsState({ running: false, paused: false });
        if (currentSimulation) {
            // Final metrics update to ensure full state
            updateMetrics(currentSimulation);
            showCompletionNotification(currentSimulation);
        }
        return;
    }

    const evt = currentSimulation.events[currentEventIndex];
    processEvent(evt);
    appendEventLogRow(evt, currentEventIndex + 1);

    // Update progress bar
    const progress = Math.round(((currentEventIndex + 1) / currentSimulation.events.length) * 100);
    const pbar = document.getElementById('simProgressBar');
    if (pbar) {
        pbar.style.width = `${progress}%`;
        pbar.textContent = `${progress}%`;
    }

    currentEventIndex++;
}

/**
 * Process event visually on sender, network track, receiver
 */
function processEvent(evt) {
    const channelTrackForward = document.getElementById('forwardTrack');
    const channelTrackReverse = document.getElementById('reverseTrack');
    const senderBox = document.getElementById('senderNodeBox');
    const receiverBox = document.getElementById('receiverNodeBox');

    // Pulse node box
    if (evt.type.startsWith('PACKET_') || evt.type === 'TIMEOUT' || evt.type === 'WINDOW_ADVANCE') {
        senderBox.classList.add('sender-active');
        setTimeout(() => senderBox.classList.remove('sender-active'), 300);
    }
    if (evt.type.startsWith('ACK_') || evt.type === 'PACKET_DELIVERED' || evt.type === 'PACKET_BUFFERED') {
        receiverBox.classList.add('receiver-active');
        setTimeout(() => receiverBox.classList.remove('receiver-active'), 300);
    }

    // Packet flight animation
    if (evt.type === 'PACKET_SENT' || evt.type === 'RETRANSMIT') {
        spawnFlightPacket(evt.seq, 'data', evt.dropped, channelTrackForward);
    } else if (evt.type === 'ACK_SENT') {
        spawnFlightPacket(evt.ack_seq, 'ack', evt.dropped, channelTrackReverse);
    }

    // Update window slot states
    updateWindowSlot(evt);
}

function spawnFlightPacket(seq, kind, dropped, container) {
    if (!container) return;
    const pkt = document.createElement('div');
    pkt.className = `packet-entity ${kind} ${dropped ? 'dropped' : ''}`;
    pkt.innerHTML = `<i class="bi ${kind === 'data' ? 'bi-box-seam' : 'bi-check-circle'}"></i> ${kind === 'data' ? 'P' : 'ACK'}${seq}`;

    pkt.style.left = kind === 'data' ? '5%' : '90%';
    container.appendChild(pkt);

    // Animate across track
    requestAnimationFrame(() => {
        pkt.style.transition = `left ${playbackDelayMs * 0.9}ms linear, opacity ${playbackDelayMs * 0.5}ms ease`;
        if (dropped) {
            // Drop halfway
            pkt.style.left = '48%';
            setTimeout(() => {
                pkt.classList.add('dropped');
                pkt.innerHTML = `<i class="bi bi-x-octagon"></i> DROPPED`;
                setTimeout(() => pkt.remove(), 400);
            }, playbackDelayMs * 0.45);
        } else {
            pkt.style.left = kind === 'data' ? '90%' : '5%';
            setTimeout(() => pkt.remove(), playbackDelayMs * 0.9);
        }
    });
}

function setupWindowDisplay(sim) {
    const senderStrip = document.getElementById('senderWindowStrip');
    const receiverStrip = document.getElementById('receiverWindowStrip');
    if (!senderStrip || !receiverStrip) return;

    senderStrip.innerHTML = '';
    receiverStrip.innerHTML = '';

    const total = sim.total_packets;
    for (let i = 0; i < total; i++) {
        const sSlot = document.createElement('div');
        sSlot.id = `sender-slot-${i}`;
        sSlot.className = 'window-slot';
        sSlot.textContent = i;
        senderStrip.appendChild(sSlot);

        const rSlot = document.createElement('div');
        rSlot.id = `receiver-slot-${i}`;
        rSlot.className = 'window-slot';
        rSlot.textContent = i;
        receiverStrip.appendChild(rSlot);
    }
}

function updateWindowSlot(evt) {
    if (evt.seq !== null && evt.seq !== undefined) {
        const sSlot = document.getElementById(`sender-slot-${evt.seq}`);
        const rSlot = document.getElementById(`receiver-slot-${evt.seq}`);

        if (evt.type === 'PACKET_SENT' || evt.type === 'RETRANSMIT') {
            if (sSlot) sSlot.className = 'window-slot sent';
        } else if (evt.type === 'PACKET_DELIVERED') {
            if (rSlot) rSlot.className = 'window-slot acked';
        } else if (evt.type === 'PACKET_BUFFERED') {
            if (rSlot) rSlot.className = 'window-slot buffered';
        }
    }

    if (evt.ack_seq !== null && evt.ack_seq !== undefined) {
        if (evt.type === 'ACK_RECEIVED') {
            const sSlot = document.getElementById(`sender-slot-${evt.ack_seq}`);
            if (sSlot) sSlot.className = 'window-slot acked';
        }
    }

    // Highlight active window range if provided
    if (evt.window_base !== null && evt.window_base !== undefined && evt.window_end !== null && evt.window_end !== undefined) {
        const total = currentSimulation ? currentSimulation.total_packets : 20;
        for (let i = 0; i < total; i++) {
            const sSlot = document.getElementById(`sender-slot-${i}`);
            if (sSlot) {
                if (i >= evt.window_base && i <= evt.window_end) {
                    sSlot.classList.add('in-window');
                } else {
                    sSlot.classList.remove('in-window');
                }
            }
        }
    }
}

function appendEventLogRow(evt, index) {
    const tbody = document.getElementById('eventLogTableBody');
    if (!tbody) return;

    const tr = document.createElement('tr');
    tr.setAttribute('data-event-type', evt.type);
    const isRetx = evt.type === 'RETRANSMIT' || evt.type === 'TIMEOUT';
    tr.setAttribute('data-is-retx', isRetx ? 'true' : 'false');

    const badge = getEventBadgeHtml(evt.type);
    const idLabel = evt.seq !== null && evt.seq !== undefined ? `Pkt #${evt.seq}` : (evt.ack_seq !== null ? `ACK #${evt.ack_seq}` : '-');

    tr.innerHTML = `
        <td class="font-mono text-slate-400">#${index}</td>
        <td class="font-mono text-cyan">${evt.time.toFixed(1)} ms</td>
        <td>${badge}</td>
        <td class="font-mono fw-semibold">${idLabel}</td>
        <td class="text-slate-300">${escapeHtml(evt.description)}</td>
        <td class="font-mono small text-slate-400">${evt.attempt ? 'Attempt ' + evt.attempt : '-'}</td>
    `;

    tbody.appendChild(tr);

    // Auto scroll event log to bottom
    const scrollContainer = document.querySelector('.log-scroll-area');
    if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
}

function updateMetrics(sim) {
    document.getElementById('metricDelivered').textContent = `${sim.delivered_packets} / ${sim.total_packets}`;
    document.getElementById('metricAcked').textContent = sim.acked_packets;
    document.getElementById('metricAttempts').textContent = sim.total_attempts;
    document.getElementById('metricRetransmissions').textContent = sim.retransmissions;
    document.getElementById('metricTimeouts').textContent = sim.timeouts;
    document.getElementById('metricDroppedData').textContent = sim.dropped_data_packets;
    document.getElementById('metricDroppedAck').textContent = sim.dropped_ack_packets;
    document.getElementById('metricTime').textContent = `${sim.completion_time_ms.toFixed(0)} ms`;
    document.getElementById('metricThroughput').textContent = formatThroughput(sim.throughput_bps);
    document.getElementById('metricDeliveryRatio').textContent = `${sim.delivery_ratio.toFixed(1)}%`;
    document.getElementById('metricEfficiency').textContent = `${sim.efficiency.toFixed(1)}%`;

    const statusBadge = document.getElementById('metricStatus');
    if (statusBadge) {
        if (sim.status === 'completed') {
            statusBadge.className = 'badge bg-success';
            statusBadge.textContent = 'Completed';
        } else if (sim.status === 'failed') {
            statusBadge.className = 'badge bg-danger';
            statusBadge.textContent = 'Failed';
        } else {
            statusBadge.className = 'badge bg-secondary';
            statusBadge.textContent = 'In Progress';
        }
    }
}

function resetMetrics() {
    ['metricDelivered', 'metricAcked', 'metricAttempts', 'metricRetransmissions',
     'metricTimeouts', 'metricDroppedData', 'metricDroppedAck', 'metricTime',
     'metricThroughput', 'metricDeliveryRatio', 'metricEfficiency'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '-';
    });
    const statusBadge = document.getElementById('metricStatus');
    if (statusBadge) {
        statusBadge.className = 'badge bg-secondary';
        statusBadge.textContent = 'Idle';
    }
    const pbar = document.getElementById('simProgressBar');
    if (pbar) {
        pbar.style.width = '0%';
        pbar.textContent = '0%';
    }
}

function clearVisualization() {
    const fTrack = document.getElementById('forwardTrack');
    const rTrack = document.getElementById('reverseTrack');
    if (fTrack) fTrack.querySelectorAll('.packet-entity').forEach(e => e.remove());
    if (rTrack) rTrack.querySelectorAll('.packet-entity').forEach(e => e.remove());

    const tbody = document.getElementById('eventLogTableBody');
    if (tbody) tbody.innerHTML = '';

    const alertContainer = document.getElementById('simAlertContainer');
    if (alertContainer) alertContainer.innerHTML = '';
}

function showCompletionNotification(sim) {
    const type = sim.status === 'completed' ? 'success' : 'danger';
    const msg = sim.status === 'completed'
        ? `<strong>Transfer Completed!</strong> Successfully transferred ${sim.delivered_packets} packets in ${sim.completion_time_ms.toFixed(0)} ms simulated time with ${sim.retransmissions} retransmission(s).`
        : `<strong>Transfer Incomplete:</strong> ${sim.failure_reason || 'Safety limit reached or packets lost.'}`;
    showAlert('simAlertContainer', msg, type);
}

function renderRecentHistory() {
    const container = document.getElementById('recentHistoryList');
    if (!container) return;

    const list = SimHistory.getAll();
    if (!list || list.length === 0) {
        container.innerHTML = '<p class="text-muted small mb-0">No past simulations in this browser session.</p>';
        return;
    }

    container.innerHTML = list.slice(0, 5).map(item => `
        <div class="d-flex align-items-center justify-content-between p-2 mb-2 rounded bg-dark border border-secondary-subtle">
            <div>
                <span class="fw-semibold text-white small">${formatProtocolName(item.protocol)}</span>
                <span class="badge ${item.status === 'completed' ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'} ms-1 x-small">${item.status}</span>
                <div class="x-small text-slate-400">
                    ${item.config.total_packets || '-'} pkts | Loss: ${Math.round((item.config.packet_loss_prob || 0) * 100)}% | Time: ${Math.round(item.completion_time_ms || 0)} ms
                </div>
            </div>
            <div class="text-end">
                <span class="font-mono text-cyan small">${formatThroughput(item.throughput_bps)}</span>
                <div class="x-small text-slate-500">${new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
            </div>
        </div>
    `).join('');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
