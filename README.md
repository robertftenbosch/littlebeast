# UGV Rover Control

Waveshare UGV Rover met Jetson Orin Nano, LiDAR en camera.
Handmatige besturing via web/gamepad + autonoom navigeren door een appartement.

## Architectuur

- **ROS2 Humble** — navigatie, SLAM, odometrie, TF
- **FastAPI** — webinterface, camera streaming, WebSocket besturing
- **LLM integratie** — natuurlijke taalcommando's (Ollama/OpenAI/Anthropic)

## Quick Start

```bash
# Eerste keer (op de rover)
./scripts/setup.sh
./scripts/build.sh

# Starten
./scripts/start.sh teleop    # Handmatig rijden
./scripts/start.sh slam      # Kaart maken
./scripts/start.sh nav       # Navigatie met kaart
```

Open `http://<rover-ip>:8000` in je browser.

## Modi

| Modus | Beschrijving |
|-------|-------------|
| Manual | Joystick/gamepad besturing |
| Navigate | Klik doel op kaart → autonoom rijden |
| Explore | Autonome verkenning |

## Structuur

```
robot_base/      — UART ↔ ROS2 bridge (cmd_vel, odom, battery)
robot_description/ — URDF robot model
robot_bringup/   — Launch files en config
robot_web/       — FastAPI server + web UI
config/          — YAML configuratie
launch/          — ROS2 launch files
maps/            — Opgeslagen SLAM kaarten
scripts/         — Setup, build, start scripts
```

## Configuratie

Alle instellingen in `config/robot.yaml`:
- Serial port, baudrate
- Snelheidslimiet
- Camera device
- LLM backend en model
- Waypoints

## Hardware

- Waveshare UGV Rover (ESP32 lower computer)
- NVIDIA Jetson Orin Nano
- LiDAR (LD19/STL27L)
- USB/CSI Camera
- UART verbinding @ 115200 baud
