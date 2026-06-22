const API_BASE = "http://127.0.0.1:8000";

// --- Global State ---
let trendChartInstance = null;
let networkInstance = null;
let globeInstance = null;

// --- Utility Functions ---
const fetchJSON = async (url) => {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || `HTTP Error: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Fetch error:", error);
        throw error;
    }
};

// --- Top Actors Table ---
async function loadTopActors() {
    const tbody = document.querySelector("#topActorsTable tbody");
    try {
        const actors = await fetchJSON(`${API_BASE}/top-actors?limit=10`);
        tbody.innerHTML = actors.map((a, i) => `
            <tr>
                <td><span class="rank-badge">#${i + 1}</span></td>
                <td><strong>${a.name}</strong> <span style="color:var(--text-secondary); font-size: 0.8rem;">${a.country_code || ''}</span></td>
                <td>${a.pagerank.toFixed(3)}</td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="3" style="color: #ef4444;">Error loading top actors</td></tr>`;
    }
}

// --- Sentiment Leaderboard ---
async function loadSentimentLeaderboard() {
    const tbody = document.querySelector("#sentimentTable tbody");
    if (!tbody) return;
    try {
        const data = await fetchJSON(`${API_BASE}/sentiment-leaderboard?limit=5`);
        let html = '';
        
        // High Risk / Negative
        data.most_negative.forEach(a => {
            html += `
            <tr>
                <td><span style="color: #f5576c; font-weight: bold;">🔴 High Risk</span></td>
                <td><strong>${a.name}</strong> <span style="color:var(--text-secondary); font-size: 0.8rem;">${a.country_code || ''}</span></td>
                <td style="color: #f5576c;">${a.avg_tone.toFixed(2)}</td>
            </tr>`;
        });
        
        // Low Risk / Positive
        data.most_positive.forEach(a => {
            html += `
            <tr>
                <td><span style="color: #10b981; font-weight: bold;">🟢 Stable</span></td>
                <td><strong>${a.name}</strong> <span style="color:var(--text-secondary); font-size: 0.8rem;">${a.country_code || ''}</span></td>
                <td style="color: #10b981;">+${a.avg_tone.toFixed(2)}</td>
            </tr>`;
        });
        
        tbody.innerHTML = html;
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="3" style="color: #ef4444;">Error loading sentiment</td></tr>`;
    }
}

// --- Sentiment Donut Chart ---
async function loadSentimentDistribution() {
    const ctx = document.getElementById('sentimentDonutChart');
    if (!ctx) return;
    try {
        const data = await fetchJSON(`${API_BASE}/sentiment-distribution`);
        
        new Chart(ctx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Cooperation (Positive Tone)', 'Conflict (Negative Tone)'],
                datasets: [{
                    data: [data.cooperative_count, data.conflict_count],
                    backgroundColor: ['#10b981', '#f5576c'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8' } }
                }
            }
        });
    } catch (e) {
        console.error("Error loading donut chart:", e);
    }
}

// --- Trend Chart (Chart.js) ---
async function loadTrends(countryFilter = "") {
    let url = `${API_BASE}/trends`;
    if (countryFilter) {
        url += `?country=${encodeURIComponent(countryFilter)}`;
    }

    try {
        const data = await fetchJSON(url);
        
        // Prepare data for Chart.js
        const labels = data.map(d => {
            const m = d.month;
            // Format YYYYMM to YYYY-MM
            return `${m.substring(0,4)}-${m.substring(4)}`;
        });
        const counts = data.map(d => d.event_count);
        const tones = data.map(d => d.avg_goldstein);

        const ctx = document.getElementById('trendChart').getContext('2d');

        if (trendChartInstance) {
            trendChartInstance.destroy();
        }

        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = "'Inter', sans-serif";

        trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Event Count',
                        data: counts,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        yAxisID: 'y',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Avg Goldstein Score',
                        data: tones,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'transparent',
                        yAxisID: 'y1',
                        tension: 0.4,
                        borderDash: [5, 5]
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleFont: { size: 14 },
                        bodyFont: { size: 13 },
                        padding: 10,
                        cornerRadius: 8,
                        displayColors: true
                    }
                },
                scales: {
                    x: { grid: { color: 'rgba(255, 255, 255, 0.05)' } },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        title: { display: true, text: 'Count' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: 'Goldstein Scale' }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Failed to load trends:", e);
    }
}

// --- Network Graph (Vis.js) ---
async function loadNetwork(entityName) {
    const errorDiv = document.getElementById("networkError");
    const container = document.getElementById("networkGraph");
    errorDiv.innerText = "";

    if (!entityName) return;

    try {
        const data = await fetchJSON(`${API_BASE}/entity/${encodeURIComponent(entityName)}/network`);
        
        if (data.nodes.length === 0) {
            errorDiv.innerText = "No network data found for this entity.";
            if (networkInstance) { networkInstance.destroy(); networkInstance = null; }
            return;
        }

        // Map Neo4j nodes to Vis.js nodes
        const nodes = new vis.DataSet(data.nodes.map(n => ({
            id: n.id,
            label: n.name,
            group: n.group,
            value: n.value || 1, // Node size based on PageRank
            title: `Actor: ${n.name}\nCountry: ${n.group}\nScore: ${n.value ? n.value.toFixed(3) : 0}`
        })));

        // Map Neo4j edges to Vis.js edges
        const edges = new vis.DataSet(data.edges.map(e => ({
            from: e.from,
            to: e.to,
            title: `Event Code: ${e.title}`, // Tooltip
            color: { color: 'rgba(59, 130, 246, 0.3)', highlight: '#3b82f6' }
        })));

        const networkData = { nodes: nodes, edges: edges };
        
        const options = {
            nodes: {
                shape: 'dot',
                scaling: {
                    min: 10,
                    max: 30,
                    label: { min: 8, max: 20 }
                },
                font: { color: '#f8fafc', face: 'Inter' },
                borderWidth: 2
            },
            edges: {
                smooth: { type: 'continuous' }
            },
            physics: {
                barnesHut: {
                    gravitationalConstant: -2000,
                    centralGravity: 0.3,
                    springLength: 150,
                    springConstant: 0.04
                },
                stabilization: { iterations: 150 }
            },
            interaction: {
                hover: true,
                tooltipDelay: 200
            }
        };

        if (networkInstance) {
            networkInstance.destroy();
        }
        networkInstance = new vis.Network(container, networkData, options);

    } catch (e) {
        errorDiv.innerText = e.message;
        if (networkInstance) { networkInstance.destroy(); networkInstance = null; }
    }
}
// --- 3D Globe ---
function initGlobe() {
    const container = document.getElementById('globeViz');
    if (!container) return;

    globeInstance = Globe()
        (container)
        .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
        .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
        .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
        .arcLabel(d => `${d.source} &rarr; ${d.target}: ${d.event}`)
        .arcStartLat(d => d.startLat)
        .arcStartLng(d => d.startLng)
        .arcEndLat(d => d.endLat)
        .arcEndLng(d => d.endLng)
        .arcColor(d => d.color)
        .arcDashLength(0.5)
        .arcDashGap(0)
        .arcDashInitialGap(0)
        .arcDashAnimateTime(1000)
        .arcStroke(d => d.thickness)
        .arcsTransitionDuration(1000);
        
    window.addEventListener('resize', () => {
        globeInstance.width(container.clientWidth);
        globeInstance.height(container.clientHeight);
    });
}

// --- WebSocket Live Feed ---
function initWebSocket() {
    const wsUrl = API_BASE.replace('http://', 'ws://') + '/ws/live';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("Connected to Live Event Stream");
    };

        ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            showLiveToast(data);

            if (globeInstance && data.Actor1Geo_Lat && data.Actor1Geo_Long && data.ActionGeo_Lat && data.ActionGeo_Long) {
                const arcData = {
                    startLat: data.Actor1Geo_Lat,
                    startLng: data.Actor1Geo_Long,
                    endLat: data.ActionGeo_Lat,
                    endLng: data.ActionGeo_Long,
                    source: data.Actor1Name,
                    target: data.Actor2Name || "Unknown",
                    event: data.EventCode,
                    color: data.is_anomaly ? ['#ff0000', '#ff0000'] : (data.AvgTone > 0 ? ['#00f2fe', '#4facfe'] : ['#f5576c', '#f87171']),
                    thickness: data.is_anomaly ? 3 : Math.min(Math.max(data.NumArticles * 0.1, 0.2), 2)
                };
                
                const currentArcs = globeInstance.arcsData();
                globeInstance.arcsData([...currentArcs, arcData]);
                
                // Point camera to the new event trajectory
                globeInstance.pointOfView({ lat: data.ActionGeo_Lat, lng: data.ActionGeo_Long, altitude: 2 }, 1000);
            }
        } catch (e) {
            console.error("Error parsing live event:", e);
        }
    };

    ws.onclose = () => {
        console.log("WebSocket disconnected. Reconnecting in 5s...");
        setTimeout(initWebSocket, 5000);
    };
}

function showLiveToast(data) {
    // 1. Toast Notification (Brief)
    const toastContainer = document.getElementById("liveFeedContainer");
    if (toastContainer) {
        const toast = document.createElement("div");
        toast.className = "live-toast";
        
        const eventType = data.EventCode.startsWith("06") ? "Cooperation" :
                          data.EventCode.startsWith("07") ? "Aid Provided" :
                          data.EventCode.startsWith("10") ? "Aid Demanded" :
                          data.EventCode.startsWith("12") ? "Cooperation Rejected" :
                          data.EventCode.startsWith("16") ? "Aid Reduced" : "Economic Event";

        toast.innerHTML = `
            <div class="live-indicator"></div>
            <div>
                <strong style="color: #3b82f6;">LIVE:</strong> <strong>${data.Actor1Name} &rarr; ${data.Actor2Name}</strong><br>
                <span style="color: #94a3b8; font-size: 0.8rem;">${eventType} (Tone: ${data.AvgTone.toFixed(2)})</span>
            </div>
        `;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.classList.add("fade-out");
            setTimeout(() => toast.remove(), 500);
        }, 8000);
    }

    // 2. Persistent Live Explorer Feed
    const feedList = document.getElementById("liveFeedList");
    if (feedList) {
        const item = document.createElement("div");
        item.className = data.is_anomaly ? "feed-item anomaly" : "feed-item";
        
        const toneColor = data.AvgTone >= 0 ? "#10b981" : "#f5576c";
        const srcUrl = data.SOURCEURL || "#";
        const linkText = srcUrl !== "#" ? `<a href="${srcUrl}" target="_blank">View Source Article ↗</a>` : "";
        const anomalyBadge = data.is_anomaly ? `<span class="anomaly-badge">⚠️ ANOMALY DETECTED</span>` : "";
        
        item.innerHTML = `
            <div><strong>${data.Actor1Name}</strong> and <strong>${data.Actor2Name}</strong> ${anomalyBadge}</div>
            <div class="feed-item-meta">
                <span>Code: ${data.EventCode}</span>
                <span style="color: ${toneColor}; font-weight:bold;">Tone: ${data.AvgTone.toFixed(2)}</span>
            </div>
            ${linkText}
        `;
        
        feedList.prepend(item);
        
        // Keep only last 50 items to prevent memory bloat
        if (feedList.children.length > 50) {
            feedList.lastChild.remove();
        }
    }
}

// --- Event Listeners & Init ---
document.addEventListener("DOMContentLoaded", () => {
    // Initial loads
    loadTopActors();
    loadTrends();
    loadSentimentLeaderboard();
    loadSentimentDistribution();
    initGlobe();
    initWebSocket();
    
    // Default network view (Optional)
    loadNetwork("UNITED STATES");

    // Trend Filter Button
    document.getElementById("updateTrendsBtn").addEventListener("click", () => {
        const country = document.getElementById("countryFilter").value.trim().toUpperCase();
        loadTrends(country);
    });

    // Network Search Button
    document.getElementById("searchEntityBtn").addEventListener("click", () => {
        const entity = document.getElementById("entitySearch").value.trim().toUpperCase();
        if (entity) {
            loadNetwork(entity);
        }
    });
    
    // Allow enter key
    document.getElementById("entitySearch").addEventListener("keypress", (e) => {
        if(e.key === "Enter") {
            const entity = document.getElementById("entitySearch").value.trim().toUpperCase();
            if (entity) loadNetwork(entity);
        }
    });

    // ML Forecaster Button
    const mlBtn = document.getElementById("mlForecastBtn");
    if (mlBtn) {
        mlBtn.addEventListener("click", runForecast);
    }
});
