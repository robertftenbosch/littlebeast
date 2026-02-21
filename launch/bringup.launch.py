"""Bringup launch: base_node + robot_state_publisher + LiDAR driver."""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    urdf_file = os.path.join(pkg_dir, 'robot_description', 'urdf', 'ugv_rover.urdf')
    config_file = os.path.join(pkg_dir, 'config', 'robot.yaml')

    with open(urdf_file, 'r') as f:
        robot_description = f.read()

    return LaunchDescription([
        # Robot state publisher (URDF → TF)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen',
        ),

        # Base node (UART ↔ ROS2)
        Node(
            package='robot_base',
            executable='base_node',
            name='base_node',
            parameters=[{'config_file': config_file}],
            output='screen',
        ),

        # LiDAR driver
        # Pas aan op basis van je LiDAR model
        # Voorbeeld voor ldlidar:
        # Node(
        #     package='ldlidar_stl_ros2',
        #     executable='ldlidar_stl_ros2_node',
        #     name='lidar',
        #     parameters=[os.path.join(pkg_dir, 'config', 'lidar_params.yaml')],
        #     output='screen',
        # ),

        # Statische TF: base_link → laser (als backup, normaal via URDF)
        # Node(
        #     package='tf2_ros',
        #     executable='static_transform_publisher',
        #     arguments=['0.05', '0', '0.09', '0', '0', '0', 'base_link', 'laser'],
        # ),
    ])
