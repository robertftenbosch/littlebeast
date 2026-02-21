"""Teleop launch: bringup + gamepad node (geen navigatie/SLAM)."""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bringup_launch = os.path.join(pkg_dir, 'launch', 'bringup.launch.py')
    config_file = os.path.join(pkg_dir, 'config', 'robot.yaml')

    return LaunchDescription([
        # Bringup (base + lidar + state publisher)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup_launch),
        ),

        # Joy driver (gamepad input)
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            output='screen',
        ),

        # Gamepad → cmd_vel
        Node(
            package='robot_base',
            executable='gamepad_node',
            name='gamepad_node',
            parameters=[{'config_file': config_file}],
            output='screen',
        ),
    ])
