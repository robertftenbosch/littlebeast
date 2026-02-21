"""SLAM launch: bringup + SLAM Toolbox voor kaart maken."""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bringup_launch = os.path.join(pkg_dir, 'launch', 'bringup.launch.py')
    slam_config = os.path.join(pkg_dir, 'config', 'slam_params.yaml')

    return LaunchDescription([
        # Bringup (base + lidar + state publisher)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup_launch),
        ),

        # SLAM Toolbox in mapping mode
        Node(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            parameters=[slam_config],
            output='screen',
        ),
    ])
