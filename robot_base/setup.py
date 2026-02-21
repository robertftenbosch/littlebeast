from setuptools import setup

package_name = 'robot_base'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Robot',
    maintainer_email='robot@local',
    description='UART bridge between ROS2 and UGV Rover ESP32',
    license='MIT',
    entry_points={
        'console_scripts': [
            'base_node = robot_base.base_node:main',
            'gamepad_node = robot_base.gamepad_node:main',
        ],
    },
)
