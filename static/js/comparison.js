/**
 * comparison.js
 * Multi-protocol comparison orchestrator and Chart.js visualization.
 */

let chartRetx = null;
let chartTime = null;
let chartThroughput = null;
let chartDelivery = null;

document.addEventListener('DOMContentLoaded', () => {
    initComparisonForm();
    // Auto-run default comparison on page load
    runComparison();
});

function initComparisonForm() {
    const form = document.getElementById('comparisonConfigForm');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        runComparison();
    });

    const btnRerun = document.getElementById('btnRerunComparison');
    if (btnRerun) {
        btnRerun.addEventListener('click', runComparison);
    }
}

async function runComparison() {
    const btn = document.getElementById('btnSubmitCompare');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Simulating...';
    }

    const payload = {
        total_packets: parseInt(document.getElementById('cmpTotalPackets').value, 10),
        packet_loss_prob: parseFloat(document.getElementById('cmpPacketLoss').value) / 100.0,
        ack_loss_prob: parseFloat(document.getElementById('cmpAckLoss').value) / 100.0,
        delay_ms: parseFloat(document.getElementById('cmpDelay').value),
        timeout_ms: parseFloat(document.getElementById('cmpTimeout').value),
        window_size: parseInt(document.getElementById('cmpWindowSize').value, 10),
    };

    const seedRaw = document.getElementById('cmpSeed').value.trim();
    if (seedRaw !== '') {
        payload.seed = parseInt(seedRaw, 10);
    } else {
        payload.seed = 42; // default common seed for fair reproducibility
    }

    try {
        const res = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!data.success) {
            showAlert('cmpAlertContainer', data.errors.join('<br>'), 'danger');
            return;
        }

        const cmp = data.comparison;
        renderMetricCards(cmp);
        renderComparisonTable(cmp);
        renderCharts(cmp);
        renderInterpretation(cmp.interpretation);

    } catch (err) {
        console.error(err);
        showAlert('cmpAlertContainer', 'Failed to communicate with comparison endpoint.', 'danger');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-play-fill me-1"></i> Run Comparison';
        }
    }
}

function renderMetricCards(cmp) {
    const protos = ['stop_and_wait', 'go_back_n', 'selective_repeat'];
    const prefixMap = {
        'stop_and_wait': 'sw',
        'go_back_n': 'gbn',
        'selective_repeat': 'sr'
    };

    protos.forEach(p => {
        const d = cmp[p];
        const pfx = prefixMap[p];
        const elTime = document.getElementById(`${pfx}Time`);
        const elRetx = document.getElementById(`${pfx}Retx`);
        const elThroughput = document.getElementById(`${pfx}Throughput`);
        const elDelivery = document.getElementById(`${pfx}Delivery`);
        const elEfficiency = document.getElementById(`${pfx}Efficiency`);

        if (elTime) elTime.textContent = `${d.completion_time_ms.toFixed(0)} ms`;
        if (elRetx) elRetx.textContent = d.retransmissions;
        if (elThroughput) elThroughput.textContent = formatThroughput(d.throughput_bps);
        if (elDelivery) elDelivery.textContent = `${d.delivery_ratio.toFixed(1)}%`;
        if (elEfficiency) elEfficiency.textContent = `${d.efficiency.toFixed(1)}%`;
    });
}

function renderComparisonTable(cmp) {
    const tbody = document.getElementById('comparisonTableBody');
    if (!tbody) return;

    const protos = [
        { id: 'stop_and_wait', name: 'Stop-and-Wait ARQ', win: '1' },
        { id: 'go_back_n', name: 'Go-Back-N ARQ', win: cmp.go_back_n.config.window_size },
        { id: 'selective_repeat', name: 'Selective Repeat ARQ', win: cmp.selective_repeat.config.window_size }
    ];

    tbody.innerHTML = protos.map(p => {
        const d = cmp[p.id];
        return `
            <tr>
                <td class="fw-bold text-white">${p.name}</td>
                <td class="font-mono text-center">${p.win}</td>
                <td class="font-mono text-center text-slate-300">${d.total_attempts}</td>
                <td class="font-mono text-center ${d.retransmissions > 0 ? 'text-warning' : 'text-success'}">${d.retransmissions}</td>
                <td class="font-mono text-center text-danger">${d.timeouts}</td>
                <td class="font-mono text-center text-cyan">${d.completion_time_ms.toFixed(0)} ms</td>
                <td class="font-mono text-center text-white fw-semibold">${formatThroughput(d.throughput_bps)}</td>
                <td class="font-mono text-center text-success">${d.delivery_ratio.toFixed(1)}%</td>
                <td class="font-mono text-center text-info">${d.efficiency.toFixed(1)}%</td>
                <td class="text-center">
                    <span class="badge ${d.status === 'completed' ? 'bg-success' : 'bg-danger'}">${d.status}</span>
                </td>
            </tr>
        `;
    }).join('');
}

function renderCharts(cmp) {
    const labels = ['Stop-and-Wait', 'Go-Back-N', 'Selective Repeat'];
    const colors = ['#3b82f6', '#f59e0b', '#10b981'];

    const retxData = [
        cmp.stop_and_wait.retransmissions,
        cmp.go_back_n.retransmissions,
        cmp.selective_repeat.retransmissions
    ];

    const timeData = [
        cmp.stop_and_wait.completion_time_ms,
        cmp.go_back_n.completion_time_ms,
        cmp.selective_repeat.completion_time_ms
    ];

    const throughputData = [
        cmp.stop_and_wait.throughput_bps / 1000.0, // in Kbps
        cmp.go_back_n.throughput_bps / 1000.0,
        cmp.selective_repeat.throughput_bps / 1000.0
    ];

    const deliveryData = [
        cmp.stop_and_wait.delivery_ratio,
        cmp.go_back_n.delivery_ratio,
        cmp.selective_repeat.delivery_ratio
    ];

    // Common Chart Options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        },
        scales: {
            x: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#94a3b8', font: { family: 'Inter' } }
            },
            y: {
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono' } },
                beginAtZero: true
            }
        }
    };

    // 1. Retransmissions Chart
    if (chartRetx) chartRetx.destroy();
    const ctxRetx = document.getElementById('chartRetransmissions')?.getContext('2d');
    if (ctxRetx) {
        chartRetx = new Chart(ctxRetx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Retransmissions',
                    data: retxData,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: commonOptions
        });
    }

    // 2. Completion Time Chart
    if (chartTime) chartTime.destroy();
    const ctxTime = document.getElementById('chartTime')?.getContext('2d');
    if (ctxTime) {
        chartTime = new Chart(ctxTime, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Completion Time (ms)',
                    data: timeData,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: commonOptions
        });
    }

    // 3. Throughput Chart
    if (chartThroughput) chartThroughput.destroy();
    const ctxTp = document.getElementById('chartThroughput')?.getContext('2d');
    if (ctxTp) {
        chartThroughput = new Chart(ctxTp, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Throughput (Kbps)',
                    data: throughputData,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: commonOptions
        });
    }

    // 4. Delivery Ratio Chart
    if (chartDelivery) chartDelivery.destroy();
    const ctxDel = document.getElementById('chartDelivery')?.getContext('2d');
    if (ctxDel) {
        chartDelivery = new Chart(ctxDel, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Packet Delivery Ratio (%)',
                    data: deliveryData,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    ...commonOptions.scales,
                    y: { ...commonOptions.scales.y, max: 100 }
                }
            }
        });
    }
}

function renderInterpretation(text) {
    const el = document.getElementById('dynamicInterpretationBox');
    if (!el) return;
    if (!text) {
        el.innerHTML = '<p class="text-muted mb-0">No interpretation available.</p>';
        return;
    }
    // Convert markdown bold to html
    const formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    el.innerHTML = formatted.split('\n\n').map(p => `<p class="mb-2 text-slate-300 leading-relaxed">${p}</p>`).join('');
}
