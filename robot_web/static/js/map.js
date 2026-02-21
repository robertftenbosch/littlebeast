/**
 * Kaart weergave op canvas.
 * Rendert occupancy grid data en staat toe om navigatiedoelen te klikken.
 */

let mapCanvas = null;
let mapCtx = null;
let mapInfo = null;
let robotPos = { x: 0, y: 0, theta: 0 };

function initMap() {
    mapCanvas = document.getElementById('map-canvas');
    if (!mapCanvas) return;
    mapCtx = mapCanvas.getContext('2d');

    // Klik op kaart → navigatiedoel
    mapCanvas.addEventListener('click', onMapClick);

    // Periodiek kaartdata ophalen
    setInterval(fetchMapData, 2000);

    // Kaartlijst laden
    fetchMapList();
}

async function fetchMapData() {
    try {
        const resp = await fetch('/api/map/data');
        const data = await resp.json();
        if (data.available) {
            mapInfo = data;
            renderMap();
        }
    } catch (e) {
        // Kaart nog niet beschikbaar
    }
}

function renderMap() {
    if (!mapInfo || !mapCtx) return;

    const { width, height, data, resolution, origin_x, origin_y } = mapInfo;

    // Schaal canvas naar kaart
    const scaleX = mapCanvas.width / width;
    const scaleY = mapCanvas.height / height;
    const scale = Math.min(scaleX, scaleY);

    mapCtx.clearRect(0, 0, mapCanvas.width, mapCanvas.height);

    // Render occupancy grid
    const imgData = mapCtx.createImageData(width, height);
    for (let i = 0; i < data.length; i++) {
        const val = data[i];
        let color;
        if (val === -1) {
            color = 128; // Onbekend → grijs
        } else if (val === 0) {
            color = 255; // Vrij → wit
        } else {
            color = 0;   // Bezet → zwart
        }
        imgData.data[i * 4] = color;
        imgData.data[i * 4 + 1] = color;
        imgData.data[i * 4 + 2] = color;
        imgData.data[i * 4 + 3] = 255;
    }

    // Render naar offscreen canvas, dan schaal
    const offscreen = document.createElement('canvas');
    offscreen.width = width;
    offscreen.height = height;
    offscreen.getContext('2d').putImageData(imgData, 0, 0);

    mapCtx.save();
    mapCtx.scale(scale, scale);
    // Flip Y-as (ROS kaart heeft origin linksonder)
    mapCtx.translate(0, height);
    mapCtx.scale(1, -1);
    mapCtx.drawImage(offscreen, 0, 0);
    mapCtx.restore();

    // Teken robot positie
    drawRobot(scale, width, height, resolution, origin_x, origin_y);
}

function drawRobot(scale, mapW, mapH, res, ox, oy) {
    if (!mapCtx) return;

    // Wereld → pixel
    const px = ((robotPos.x - ox) / res) * scale;
    const py = mapCanvas.height - ((robotPos.y - oy) / res) * scale;

    mapCtx.save();
    mapCtx.translate(px, py);
    mapCtx.rotate(-robotPos.theta);

    // Robot als driehoek
    mapCtx.fillStyle = '#e94560';
    mapCtx.beginPath();
    mapCtx.moveTo(8, 0);
    mapCtx.lineTo(-6, -5);
    mapCtx.lineTo(-6, 5);
    mapCtx.closePath();
    mapCtx.fill();

    mapCtx.restore();
}

function onMapClick(event) {
    if (!mapInfo) return;

    const rect = mapCanvas.getBoundingClientRect();
    const cx = event.clientX - rect.left;
    const cy = event.clientY - rect.top;

    const { width, height, resolution, origin_x, origin_y } = mapInfo;
    const scaleX = mapCanvas.width / width;
    const scaleY = mapCanvas.height / height;
    const scale = Math.min(scaleX, scaleY);

    // Pixel → wereld
    const worldX = (cx / scale) * resolution + origin_x;
    const worldY = ((mapCanvas.height - cy) / scale) * resolution + origin_y;

    // Stuur navigatiedoel
    sendNavGoal(worldX, worldY);
}

async function sendNavGoal(x, y, theta = 0) {
    try {
        const resp = await fetch('/api/nav/goal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x, y, theta }),
        });
        const data = await resp.json();
        console.log('[Map] Nav goal:', data);
    } catch (e) {
        console.error('[Map] Nav goal error:', e);
    }
}

async function cancelNav() {
    try {
        await fetch('/api/nav/cancel', { method: 'POST' });
    } catch (e) {
        console.error('[Map] Cancel error:', e);
    }
}

async function saveMap() {
    const name = prompt('Kaartnaam:');
    if (!name) return;
    try {
        const resp = await fetch('/api/map/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        const data = await resp.json();
        alert(data.message);
        fetchMapList();
    } catch (e) {
        alert('Fout bij opslaan');
    }
}

async function fetchMapList() {
    try {
        const resp = await fetch('/api/map/list');
        const data = await resp.json();
        const select = document.getElementById('map-select');
        if (!select) return;
        select.innerHTML = '<option value="">-- Kaart laden --</option>';
        for (const m of data.maps) {
            select.innerHTML += `<option value="${m}">${m}</option>`;
        }
    } catch (e) {
        // Negeer
    }
}

async function loadMap() {
    const select = document.getElementById('map-select');
    if (!select || !select.value) return;
    try {
        await fetch('/api/map/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: select.value }),
        });
    } catch (e) {
        console.error('[Map] Load error:', e);
    }
}
