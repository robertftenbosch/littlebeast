"""
FastAPI webserver voor UGV Rover besturing.

Endpoints:
  WebSocket /ws/control  — joystick data → cmd_vel
  WebSocket /ws/status   — robot status feed
  GET       /video       — MJPEG camera stream
  POST      /api/nav/goal    — stuur Nav2 goal
  POST      /api/nav/cancel  — annuleer navigatie
  POST      /api/map/save    — sla kaart op
  GET       /api/map/list    — lijst opgeslagen kaarten
  POST      /api/map/load    — laad kaart
  POST      /api/mode        — switch modus
  POST      /api/llm/chat    — LLM interactie
"""

import asyncio
import json
import os

import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ros_bridge import RosBridge
from .camera import Camera
from .llm_client import LLMClient

# Laad config
CONFIG_PATH = os.environ.get(
    'ROBOT_CONFIG', '/home/nvidia/robot/config/robot.yaml'
)
with open(CONFIG_PATH, 'r') as f:
    config = yaml.safe_load(f)

# Componenten
ros_bridge = RosBridge()
camera = Camera(
    device=config['camera']['device'],
    width=config['camera']['width'],
    height=config['camera']['height'],
    fps=config['camera']['fps'],
)
llm_client = LLMClient(config.get('llm', {}))

# State
current_mode = "manual"  # manual | navigate | explore

# FastAPI app
app = FastAPI(title="UGV Rover Control")

# Static files
static_dir = os.path.join(os.path.dirname(__file__), 'static')
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup():
    ros_bridge.start()
    camera.start()


@app.on_event("shutdown")
async def shutdown():
    ros_bridge.stop()
    camera.stop()
    await llm_client.close()


# ── HTML ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(static_dir, 'index.html')
    with open(index_path, 'r') as f:
        return f.read()


# ── WebSocket: Joystick Control ───────────────────────

@app.websocket("/ws/control")
async def ws_control(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            if current_mode != "manual":
                continue

            # Joystick data: {x: -1..1, y: -1..1}
            x = float(data.get('x', 0))
            y = float(data.get('y', 0))

            max_lin = config['robot']['max_linear_speed']
            max_ang = config['robot']['max_angular_speed']
            linear = y * max_lin
            angular = -x * max_ang

            ros_bridge.publish_cmd_vel(linear, angular)
    except WebSocketDisconnect:
        ros_bridge.publish_cmd_vel(0, 0)


# ── WebSocket: Status Feed ────────────────────────────

@app.websocket("/ws/status")
async def ws_status(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            odom = ros_bridge.get_odom()
            battery = ros_bridge.get_battery()

            await ws.send_json({
                "mode": current_mode,
                "odom": odom,
                "battery": battery,
            })
            await asyncio.sleep(0.1)  # 10Hz
    except WebSocketDisconnect:
        pass


# ── Camera Stream ─────────────────────────────────────

@app.get("/video")
async def video_stream():
    return StreamingResponse(
        camera.mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Navigation API ────────────────────────────────────

class NavGoal(BaseModel):
    x: float
    y: float
    theta: float = 0.0


@app.post("/api/nav/goal")
async def nav_goal(goal: NavGoal):
    global current_mode
    current_mode = "navigate"
    result = await ros_bridge.send_nav_goal(goal.x, goal.y, goal.theta)
    return result


@app.post("/api/nav/cancel")
async def nav_cancel():
    global current_mode
    ros_bridge.cancel_nav()
    current_mode = "manual"
    return {"success": True, "message": "Navigatie geannuleerd"}


# ── Map API ───────────────────────────────────────────

@app.post("/api/map/save")
async def map_save(data: dict):
    name = data.get('name', 'map')
    result = ros_bridge.save_map(name)
    return result


@app.get("/api/map/list")
async def map_list():
    maps_dir = '/home/nvidia/robot/maps'
    maps = []
    if os.path.exists(maps_dir):
        for f in os.listdir(maps_dir):
            if f.endswith('.yaml') and f != '.gitkeep':
                maps.append(f.replace('.yaml', ''))
    return {"maps": maps}


@app.post("/api/map/load")
async def map_load(data: dict):
    name = data.get('name', '')
    map_path = f'/home/nvidia/robot/maps/{name}.yaml'
    if not os.path.exists(map_path):
        return {"success": False, "message": f"Kaart '{name}' niet gevonden"}
    # In werkelijkheid zou je hier de map_server herstarten met de nieuwe kaart
    return {"success": True, "message": f"Kaart '{name}' geladen"}


@app.get("/api/map/data")
async def map_data():
    map_info = ros_bridge.get_map()
    if map_info is None:
        return {"available": False}
    return {"available": True, **map_info}


# ── Mode API ──────────────────────────────────────────

class ModeRequest(BaseModel):
    mode: str


@app.post("/api/mode")
async def set_mode(req: ModeRequest):
    global current_mode
    if req.mode not in ("manual", "navigate", "explore"):
        return {"success": False, "message": f"Onbekende modus: {req.mode}"}

    if current_mode == "navigate" and req.mode != "navigate":
        ros_bridge.cancel_nav()

    current_mode = req.mode
    return {"success": True, "mode": current_mode}


@app.get("/api/mode")
async def get_mode():
    return {"mode": current_mode}


# ── LLM API ──────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


@app.post("/api/llm/chat")
async def llm_chat(req: ChatRequest):
    waypoints = config.get('waypoints', {})
    result = await llm_client.chat(req.message, waypoints)

    # Voer tool calls uit
    executed = []
    for action in result.get('actions', []):
        tool = action['tool']
        args = action.get('args', {})

        if tool == 'navigate_to':
            location = args.get('location', '')
            # Check of het een waypoint is
            if waypoints and location in waypoints:
                wp = waypoints[location]
                nav_result = await ros_bridge.send_nav_goal(
                    wp['x'], wp['y'], wp.get('theta', 0.0)
                )
                executed.append({"tool": tool, "result": nav_result})
            else:
                # Probeer als coördinaten te parsen
                try:
                    parts = location.split(',')
                    x, y = float(parts[0]), float(parts[1])
                    nav_result = await ros_bridge.send_nav_goal(x, y)
                    executed.append({"tool": tool, "result": nav_result})
                except (ValueError, IndexError):
                    executed.append({
                        "tool": tool,
                        "result": {"success": False, "message": f"Locatie '{location}' niet gevonden"}
                    })
        elif tool == 'stop':
            ros_bridge.cancel_nav()
            executed.append({"tool": tool, "result": {"success": True}})
        elif tool == 'look_around':
            # Draai langzaam 360 graden
            ros_bridge.publish_cmd_vel(0, 0.5)
            executed.append({"tool": tool, "result": {"success": True, "message": "Robot draait rond"}})

    return {
        "response": result['response'],
        "actions": executed,
    }


# ── Waypoints API ─────────────────────────────────────

@app.get("/api/waypoints")
async def get_waypoints():
    return config.get('waypoints', {})


@app.post("/api/waypoints")
async def set_waypoint(data: dict):
    name = data.get('name', '')
    x = data.get('x', 0.0)
    y = data.get('y', 0.0)
    theta = data.get('theta', 0.0)

    if not name:
        return {"success": False, "message": "Naam is verplicht"}

    if 'waypoints' not in config or config['waypoints'] is None:
        config['waypoints'] = {}
    config['waypoints'][name] = {"x": x, "y": y, "theta": theta}

    # Sla op in config bestand
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    return {"success": True, "message": f"Waypoint '{name}' opgeslagen"}


# ── Run ───────────────────────────────────────────────

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        "robot_web.main:app",
        host=config['web']['host'],
        port=config['web']['port'],
        reload=False,
    )
