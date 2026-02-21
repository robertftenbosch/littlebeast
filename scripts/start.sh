#!/bin/bash
# Start alles: ROS2 bringup + FastAPI webserver
set -e

echo "=== UGV Rover Start ==="

# Source ROS2
source /opt/ros/humble/setup.bash
source /home/nvidia/robot/install/setup.bash 2>/dev/null || true

LAUNCH_MODE="${1:-teleop}"

# Start ROS2 launch in achtergrond
echo "[1/2] ROS2 starten (modus: $LAUNCH_MODE)..."
case "$LAUNCH_MODE" in
    teleop)
        ros2 launch /home/nvidia/robot/launch/teleop.launch.py &
        ;;
    slam)
        ros2 launch /home/nvidia/robot/launch/slam.launch.py &
        ;;
    nav)
        MAP="${2:-/home/nvidia/robot/maps/map.yaml}"
        ros2 launch /home/nvidia/robot/launch/nav.launch.py map:="$MAP" &
        ;;
    bringup)
        ros2 launch /home/nvidia/robot/launch/bringup.launch.py &
        ;;
    *)
        echo "Gebruik: start.sh [teleop|slam|nav|bringup] [map_path]"
        exit 1
        ;;
esac

ROS_PID=$!

# Wacht even tot ROS2 nodes gestart zijn
sleep 3

# Start FastAPI webserver
echo "[2/2] Webserver starten..."
cd /home/nvidia/robot
python3 -m robot_web.main &
WEB_PID=$!

echo ""
echo "=== Draait ==="
echo "ROS2 PID: $ROS_PID"
echo "Web  PID: $WEB_PID"
echo "Open: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Ctrl+C om te stoppen"

# Wacht op Ctrl+C, stop alles
trap "kill $ROS_PID $WEB_PID 2>/dev/null; exit" INT TERM
wait
