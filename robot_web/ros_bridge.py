"""
ROS2 ↔ FastAPI bridge.

Draait een rclpy node in een daemon thread zodat FastAPI async endpoints
ROS2 topics kunnen lezen/schrijven.
"""

import asyncio
import math
import threading
import time
from typing import Optional

import numpy as np

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.action import ActionClient
    from geometry_msgs.msg import Twist, PoseStamped
    from nav_msgs.msg import Odometry, OccupancyGrid
    from std_msgs.msg import Float32
    from nav2_msgs.action import NavigateToPose
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


class RosBridge:
    """Bridge tussen FastAPI en ROS2. Thread-safe."""

    def __init__(self):
        self._node: Optional['RosBridgeNode'] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start ROS2 node in achtergrondthread."""
        if not ROS2_AVAILABLE:
            print("[RosBridge] ROS2 niet beschikbaar, draait in stub-modus")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        """ROS2 spin loop in eigen thread."""
        rclpy.init()
        self._node = RosBridgeNode()
        try:
            while self._running:
                rclpy.spin_once(self._node, timeout_sec=0.1)
        finally:
            self._node.destroy_node()
            rclpy.shutdown()

    def stop(self):
        """Stop ROS2 node."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def publish_cmd_vel(self, linear: float, angular: float):
        """Publiceer cmd_vel (thread-safe)."""
        if self._node:
            self._node.publish_cmd_vel(linear, angular)

    async def send_nav_goal(self, x: float, y: float, theta: float = 0.0) -> dict:
        """Stuur navigatiedoel naar Nav2. Returns status dict."""
        if not self._node:
            return {"success": False, "message": "ROS2 niet beschikbaar"}
        return await asyncio.get_event_loop().run_in_executor(
            None, self._node.send_nav_goal, x, y, theta
        )

    def cancel_nav(self):
        """Annuleer huidige navigatie."""
        if self._node:
            self._node.cancel_nav()

    def get_odom(self) -> dict:
        """Haal laatste odometrie op."""
        if not self._node:
            return {"x": 0.0, "y": 0.0, "theta": 0.0, "linear": 0.0, "angular": 0.0}
        return self._node.get_odom()

    def get_battery(self) -> float:
        """Haal batterijspanning op."""
        if not self._node:
            return 0.0
        return self._node.battery_voltage

    def get_map(self) -> Optional[dict]:
        """Haal occupancy grid op als dict met metadata + data."""
        if not self._node or self._node.map_data is None:
            return None
        return self._node.get_map()

    def save_map(self, name: str) -> dict:
        """Sla huidige kaart op."""
        if not self._node:
            return {"success": False, "message": "ROS2 niet beschikbaar"}
        return self._node.save_map(name)


if ROS2_AVAILABLE:
    class RosBridgeNode(Node):
        """ROS2 node die als bridge fungeert."""

        def __init__(self):
            super().__init__('web_bridge')

            # Publishers
            self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

            # Subscribers
            self.create_subscription(Odometry, '/odom', self._odom_cb, 10)
            self.create_subscription(Float32, '/battery', self._battery_cb, 10)
            self.create_subscription(OccupancyGrid, '/map', self._map_cb, 10)

            # Nav2 action client
            self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
            self._nav_goal_handle = None

            # State
            self._odom_lock = threading.Lock()
            self._odom = {"x": 0.0, "y": 0.0, "theta": 0.0, "linear": 0.0, "angular": 0.0}
            self.battery_voltage = 0.0
            self.map_data: Optional[OccupancyGrid] = None

        def publish_cmd_vel(self, linear: float, angular: float):
            msg = Twist()
            msg.linear.x = float(linear)
            msg.angular.z = float(angular)
            self.cmd_vel_pub.publish(msg)

        def _odom_cb(self, msg: Odometry):
            q = msg.pose.pose.orientation
            theta = math.atan2(
                2.0 * (q.w * q.z + q.x * q.y),
                1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            )
            with self._odom_lock:
                self._odom = {
                    "x": msg.pose.pose.position.x,
                    "y": msg.pose.pose.position.y,
                    "theta": theta,
                    "linear": msg.twist.twist.linear.x,
                    "angular": msg.twist.twist.angular.z,
                }

        def _battery_cb(self, msg: Float32):
            self.battery_voltage = msg.data

        def _map_cb(self, msg: OccupancyGrid):
            self.map_data = msg

        def get_odom(self) -> dict:
            with self._odom_lock:
                return self._odom.copy()

        def get_map(self) -> Optional[dict]:
            if self.map_data is None:
                return None
            grid = self.map_data
            return {
                "width": grid.info.width,
                "height": grid.info.height,
                "resolution": grid.info.resolution,
                "origin_x": grid.info.origin.position.x,
                "origin_y": grid.info.origin.position.y,
                "data": list(grid.data),
            }

        def send_nav_goal(self, x: float, y: float, theta: float = 0.0) -> dict:
            if not self.nav_client.wait_for_server(timeout_sec=5.0):
                return {"success": False, "message": "Nav2 server niet beschikbaar"}

            goal = NavigateToPose.Goal()
            goal.pose = PoseStamped()
            goal.pose.header.frame_id = 'map'
            goal.pose.header.stamp = self.get_clock().now().to_msg()
            goal.pose.pose.position.x = float(x)
            goal.pose.pose.position.y = float(y)
            goal.pose.pose.orientation.z = math.sin(theta / 2.0)
            goal.pose.pose.orientation.w = math.cos(theta / 2.0)

            future = self.nav_client.send_goal_async(goal)
            rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

            goal_handle = future.result()
            if not goal_handle or not goal_handle.accepted:
                return {"success": False, "message": "Goal geweigerd door Nav2"}

            self._nav_goal_handle = goal_handle
            return {"success": True, "message": f"Navigatie naar ({x:.2f}, {y:.2f}) gestart"}

        def cancel_nav(self):
            if self._nav_goal_handle:
                self._nav_goal_handle.cancel_goal_async()
                self._nav_goal_handle = None

        def save_map(self, name: str) -> dict:
            """Sla kaart op via map_saver_cli subprocess."""
            import subprocess
            maps_dir = '/home/nvidia/robot/maps'
            try:
                result = subprocess.run(
                    ['ros2', 'run', 'nav2_map_server', 'map_saver_cli',
                     '-f', f'{maps_dir}/{name}', '--ros-args', '-p',
                     'save_map_timeout:=5.0'],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    return {"success": True, "message": f"Kaart '{name}' opgeslagen"}
                return {"success": False, "message": result.stderr}
            except Exception as e:
                return {"success": False, "message": str(e)}
