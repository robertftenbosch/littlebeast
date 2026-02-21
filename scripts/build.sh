#!/bin/bash
# Colcon build voor alle ROS2 packages
set -e

echo "=== Colcon Build ==="

# Source ROS2
source /opt/ros/humble/setup.bash

cd /home/nvidia/robot

# Build
colcon build --symlink-install --packages-select \
    robot_base \
    robot_description \
    robot_bringup

echo ""
echo "=== Build compleet ==="
echo "Source: source install/setup.bash"
