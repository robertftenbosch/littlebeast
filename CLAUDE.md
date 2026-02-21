# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UGV Rover control system for Waveshare UGV Rover with Jetson Orin Nano. Combines ROS2 Humble (navigation, SLAM, odometry), FastAPI (web control, camera streaming), and LLM integration (natural language robot commands). The README and codebase are a mix of Dutch and English.

## Build & Run Commands

```bash
# First-time setup (installs ROS2 packages, Python deps, serial permissions, symlinks)
./scripts/setup.sh

# Build ROS2 packages with colcon
./scripts/build.sh

# Start the system (launches ROS2 + FastAPI web server)
./scripts/start.sh teleop     # Manual joystick/gamepad control
./scripts/start.sh slam       # SLAM mapping mode
./scripts/start.sh nav <map>  # Autonomous navigation with saved map
./scripts/start.sh bringup    # Base only (no teleop/slam/nav)
```

The build uses `colcon build --symlink-install` targeting packages: `robot_base`, `robot_description`, `robot_bringup`.

Python dependencies are in `requirements.txt` (FastAPI, uvicorn, opencv-python, pyserial, numpy, httpx, pyyaml).

Web UI is served at `http://<rover-ip>:8000`.

## Architecture

Three-layer system:

1. **Hardware Layer** (`robot_base/robot_base/serial_comm.py`): Thread-safe UART communication with ESP32 at 115200 baud. JSON protocol: `{"T":1,"L":100,"R":100}` for motor commands, feedback includes encoder counts and battery voltage. Command queue with maxlen=1 (newest wins).

2. **ROS2 Middleware** (`robot_base/`, `robot_description/`, `launch/`, `config/`): `base_node` converts `/cmd_vel` to differential drive motor commands and publishes `/odom`, `/battery`, and TF (`odom` -> `base_link`). Launch files compose different operational modes. Nav2 stack handles autonomous navigation.

3. **Web Layer** (`robot_web/`): FastAPI app with WebSocket endpoints for joystick control (`/ws/control`) and status streaming (`/ws/status`), REST API for navigation goals, map management, mode switching, and LLM chat. ROS2 node runs in a daemon thread (`ros_bridge.py`) with thread-safe topic/action access.

## Key Design Patterns

- **ROS2-FastAPI bridge**: `ros_bridge.py` runs a ROS2 node in a daemon thread; FastAPI accesses ROS2 via synchronized methods. Graceful fallback if ROS2 is unavailable.
- **Mode management**: Three modes (`manual`, `navigate`, `explore`) controlled via global state in `main.py`, switchable via `POST /api/mode`.
- **Pluggable LLM backend**: `llm_client.py` supports Ollama (local), OpenAI, and Anthropic, selected via `config/robot.yaml`. LLM has tool-calling access to robot actions (navigate_to, stop, look_around, describe_scene).
- **Config-driven**: All settings (serial port, speeds, camera, LLM, waypoints) in `config/robot.yaml`. Override path via `ROBOT_CONFIG` env var (default: `/home/nvidia/robot/config/robot.yaml`).

## Important Config Files

- `config/robot.yaml` — Main robot configuration (hardware, serial, camera, LLM, waypoints)
- `config/nav2_params.yaml` — Nav2 stack parameters (AMCL, planner, controller)
- `config/slam_params.yaml` — SLAM Toolbox parameters
- `config/lidar_params.yaml` — LiDAR driver configuration

## Hardware Constants

- Wheelbase: 0.175m, wheel radius: 0.033m
- Encoder: 1320 ticks/rev
- Differential drive kinematics: `L = (linear.x - angular.z * wheelbase/2) * scale`
- Serial port: `/dev/ttyTHS0` (Jetson Orin Nano UART)

## Frontend

Static files in `robot_web/static/`: `index.html`, `js/app.js` (WebSocket + API), `js/joystick.js` (nipplejs virtual joystick), `js/map.js` (canvas map rendering with click-to-navigate), `js/chat.js` (LLM chat UI).
