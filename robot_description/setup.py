import os
from glob import glob
from setuptools import setup

package_name = 'robot_description'

setup(
    name=package_name,
    version='0.1.0',
    packages=[],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Robot',
    maintainer_email='robot@local',
    description='URDF model for UGV Rover',
    license='MIT',
)
