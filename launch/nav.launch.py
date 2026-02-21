"""Navigation launch: bringup + Nav2 stack met opgeslagen kaart."""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bringup_launch = os.path.join(pkg_dir, 'launch', 'bringup.launch.py')
    nav2_config = os.path.join(pkg_dir, 'config', 'nav2_params.yaml')

    map_file = LaunchConfiguration('map')

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(pkg_dir, 'maps', 'map.yaml'),
            description='Path naar kaart YAML bestand',
        ),

        # Bringup (base + lidar + state publisher)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup_launch),
        ),

        # Map server
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            parameters=[nav2_config, {'yaml_filename': map_file}],
            output='screen',
        ),

        # AMCL localisatie
        Node(
            package='nav2_amcl',
            executable='amcl',
            name='amcl',
            parameters=[nav2_config],
            output='screen',
        ),

        # Nav2 controller
        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            parameters=[nav2_config],
            output='screen',
        ),

        # Nav2 planner
        Node(
            package='nav2_planner',
            executable='planner_server',
            name='planner_server',
            parameters=[nav2_config],
            output='screen',
        ),

        # Nav2 behavior server (recovery)
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            name='behavior_server',
            parameters=[nav2_config],
            output='screen',
        ),

        # Nav2 BT navigator
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            name='bt_navigator',
            parameters=[nav2_config],
            output='screen',
        ),

        # Nav2 smoother
        Node(
            package='nav2_smoother',
            executable='smoother_server',
            name='smoother_server',
            parameters=[nav2_config],
            output='screen',
        ),

        # Lifecycle manager - navigatie
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_navigation',
            parameters=[nav2_config],
            output='screen',
        ),

        # Lifecycle manager - localisatie
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_localization',
            parameters=[{
                'use_sim_time': False,
                'autostart': True,
                'node_names': ['map_server', 'amcl'],
            }],
            output='screen',
        ),
    ])
