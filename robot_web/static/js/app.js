/**
 * Main app logic: status WebSocket, mode switching, waypoints.
 */

let statusWs = null;

document.addEventListener('DOMContentLoaded', () => {
    initJoystick();
    initMap();
    initChat();
    connectStatusWs();
    initModeButtons();
    loadWaypoints();
});

// ── Status WebSocket ─────────────────────────────────

function connectStatusWs() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    statusWs = new WebSocket(`${protocol}//${location.host}/ws/status`);

    statusWs.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateStatus(data);
    };

    statusWs.onclose = () => {
        setTimeout(connectStatusWs, 2000);
    };
}

function updateStatus(data) {
    // Batterij
    const batteryEl = document.getElementById('battery');
    if (batteryEl && data.battery !== undefined) {
        batteryEl.textContent = `${data.battery.toFixed(1)} V`;
    }

    // Snelheid
    const speedEl = document.getElementById('speed');
    if (speedEl && data.odom) {
        speedEl.textContent = `${Math.abs(data.odom.linear).toFixed(2)} m/s`;
    }

    // Positie
    const posEl = document.getElementById('position');
    if (posEl && data.odom) {
        posEl.textContent = `x: ${data.odom.x.toFixed(2)}  y: ${data.odom.y.toFixed(2)}`;
    }

    // Mode
    const modeEl = document.getElementById('mode-display');
    if (modeEl && data.mode) {
        modeEl.textContent = data.mode.charAt(0).toUpperCase() + data.mode.slice(1);
    }

    // Update robot positie op kaart
    if (data.odom) {
        robotPos.x = data.odom.x;
        robotPos.y = data.odom.y;
        robotPos.theta = data.odom.theta;
    }

    // Toon/verberg nav controls
    const navControls = document.getElementById('nav-controls');
    const joystickContainer = document.getElementById('joystick-container');
    if (navControls && joystickContainer && data.mode) {
        if (data.mode === 'manual') {
            navControls.style.display = 'none';
            joystickContainer.style.display = 'flex';
        } else {
            navControls.style.display = 'block';
            joystickContainer.style.display = 'none';
        }
    }

    // Update active mode button
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === data.mode);
    });
}

// ── Mode Switching ───────────────────────────────────

function initModeButtons() {
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const mode = btn.dataset.mode;
            try {
                await fetch('/api/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode }),
                });
            } catch (e) {
                console.error('[Mode] Switch error:', e);
            }
        });
    });
}

// ── Waypoints ────────────────────────────────────────

async function loadWaypoints() {
    try {
        const resp = await fetch('/api/waypoints');
        const waypoints = await resp.json();
        renderWaypoints(waypoints);
    } catch (e) {
        // Negeer
    }
}

function renderWaypoints(waypoints) {
    const container = document.getElementById('waypoint-list');
    if (!container) return;
    container.innerHTML = '';

    for (const [name, coords] of Object.entries(waypoints)) {
        const tag = document.createElement('span');
        tag.className = 'waypoint-tag';
        tag.textContent = name;
        tag.title = `x: ${coords.x}, y: ${coords.y}`;
        tag.addEventListener('click', () => {
            sendNavGoal(coords.x, coords.y, coords.theta || 0);
        });
        container.appendChild(tag);
    }
}

async function addWaypointAtRobot() {
    const nameInput = document.getElementById('wp-name');
    const name = nameInput.value.trim();
    if (!name) return;

    try {
        const resp = await fetch('/api/waypoints', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                x: robotPos.x,
                y: robotPos.y,
                theta: robotPos.theta,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            nameInput.value = '';
            loadWaypoints();
        }
    } catch (e) {
        console.error('[Waypoint] Error:', e);
    }
}
