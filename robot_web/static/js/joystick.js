/**
 * Virtuele joystick via nipple.js.
 * Stuurt x,y data via WebSocket naar /ws/control.
 */

let joystickWs = null;
let joystickManager = null;
let joystickData = { x: 0, y: 0 };
let joystickSendInterval = null;

function initJoystick() {
    const zone = document.getElementById('joystick-zone');
    if (!zone || typeof nipplejs === 'undefined') return;

    joystickManager = nipplejs.create({
        zone: zone,
        mode: 'static',
        position: { left: '50%', top: '50%' },
        color: '#e94560',
        size: 150,
    });

    joystickManager.on('move', (evt, data) => {
        if (!data.vector) return;
        // nipple.js vector: x = links/rechts, y = voor/achter
        joystickData.x = data.vector.x;
        joystickData.y = data.vector.y;
    });

    joystickManager.on('end', () => {
        joystickData.x = 0;
        joystickData.y = 0;
    });

    connectJoystickWs();
}

function connectJoystickWs() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    joystickWs = new WebSocket(`${protocol}//${location.host}/ws/control`);

    joystickWs.onopen = () => {
        console.log('[Joystick] WebSocket connected');
        // Stuur joystick data op 20Hz
        joystickSendInterval = setInterval(() => {
            if (joystickWs.readyState === WebSocket.OPEN) {
                joystickWs.send(JSON.stringify(joystickData));
            }
        }, 50);
    };

    joystickWs.onclose = () => {
        console.log('[Joystick] WebSocket disconnected');
        clearInterval(joystickSendInterval);
        // Reconnect na 2 seconden
        setTimeout(connectJoystickWs, 2000);
    };

    joystickWs.onerror = (err) => {
        console.error('[Joystick] WebSocket error', err);
    };
}
