"""
ROS2 node: Gamepad (Joy) → cmd_vel.

Gebruikt sensor_msgs/Joy van de joy ROS2 package.
Deadman switch: rechter bumper (R1) moet ingedrukt zijn.
Linker stick: vooruit/achteruit (axis 1), links/rechts (axis 0).
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy
import yaml


class GamepadNode(Node):
    def __init__(self):
        super().__init__('gamepad_node')

        # Laad config
        self.declare_parameter('config_file', '/home/nvidia/robot/config/robot.yaml')
        config_path = self.get_parameter('config_file').get_parameter_value().string_value

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        robot_cfg = config['robot']
        self.max_linear = robot_cfg['max_linear_speed']
        self.max_angular = robot_cfg['max_angular_speed']

        # Gamepad mapping (standaard voor veel controllers)
        self.declare_parameter('axis_linear', 1)        # Linker stick Y
        self.declare_parameter('axis_angular', 0)       # Linker stick X
        self.declare_parameter('deadman_button', 5)     # R1 bumper
        self.declare_parameter('deadzone', 0.1)

        self.axis_linear = self.get_parameter('axis_linear').value
        self.axis_angular = self.get_parameter('axis_angular').value
        self.deadman_button = self.get_parameter('deadman_button').value
        self.deadzone = self.get_parameter('deadzone').value

        self.joy_sub = self.create_subscription(Joy, '/joy', self.joy_callback, 10)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info(
            f'Gamepad node started (deadman=button {self.deadman_button})'
        )

    def joy_callback(self, msg: Joy):
        """Vertaal gamepad input naar cmd_vel."""
        twist = Twist()

        # Check deadman switch
        if len(msg.buttons) <= self.deadman_button:
            return
        if not msg.buttons[self.deadman_button]:
            # Deadman niet ingedrukt → stop
            self.cmd_vel_pub.publish(twist)
            return

        # Lees axes
        if len(msg.axes) > max(self.axis_linear, self.axis_angular):
            linear = msg.axes[self.axis_linear]
            angular = msg.axes[self.axis_angular]

            # Deadzone
            if abs(linear) < self.deadzone:
                linear = 0.0
            if abs(angular) < self.deadzone:
                angular = 0.0

            twist.linear.x = linear * self.max_linear
            twist.angular.z = angular * self.max_angular

        self.cmd_vel_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = GamepadNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
