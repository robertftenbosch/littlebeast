#!/bin/bash
# Eerste keer setup: installeer alle dependencies
set -e

echo "=== UGV Rover Setup ==="

# ROS2 packages
echo "[1/4] ROS2 packages installeren..."
sudo apt update
sudo apt install -y \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher \
    ros-humble-joy \
    ros-humble-teleop-twist-joy \
    ros-humble-rviz2 \
    ros-humble-tf2-ros \
    ros-humble-tf2-tools \
    ros-humble-nav2-map-server

# Python dependencies
echo "[2/4] Python dependencies installeren..."
pip3 install -r /home/nvidia/robot/requirements.txt

# Serial permissions
echo "[3/4] Serial permissions instellen..."
sudo usermod -aG dialout $USER

# LiDAR driver (pas aan voor jouw model)
echo "[4/4] LiDAR driver..."
echo "LiDAR driver moet handmatig geinstalleerd worden."
echo "Zie: https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2"

echo ""
echo "=== Setup compleet ==="
echo "Log opnieuw in voor serial permissions, dan: ./scripts/build.sh"
