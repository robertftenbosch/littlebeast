"""
ROS2 node: cmd_vel → UART motor commands, encoder feedback → odom.

Differentieel aandrijfmodel:
  L = (linear.x - angular.z * wheelbase / 2) * scale
  R = (linear.x + angular.z * wheelbase / 2) * scale
"""

import math
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32
import tf2_ros
import yaml

from .serial_comm import SerialComm


class BaseNode(Node):
    def __init__(self):
        super().__init__('base_node')

        # Laad config
        self.declare_parameter('config_file', '/home/nvidia/robot/config/robot.yaml')
        config_path = self.get_parameter('config_file').get_parameter_value().string_value

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        robot_cfg = self.config['robot']
        serial_cfg = self.config['serial']

        self.wheelbase = robot_cfg['wheelbase']
        self.wheel_radius = robot_cfg['wheel_radius']
        self.max_linear = robot_cfg['max_linear_speed']
        self.max_angular = robot_cfg['max_angular_speed']
        self.encoder_ticks = robot_cfg['encoder_ticks_per_rev']

        # Motor speed schaal: m/s → PWM (0-255)
        self.speed_scale = 255.0 / self.max_linear

        # Serial communicatie
        self.serial = SerialComm(
            port=serial_cfg['port'],
            baudrate=serial_cfg['baudrate'],
            timeout=serial_cfg['timeout'],
        )

        # ROS2 subscribers & publishers
        self.cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_callback, 10
        )
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.battery_pub = self.create_publisher(Float32, '/battery', 10)

        # TF broadcaster
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # Odometrie state
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_feedback_time = time.time()
        self.last_encoder_left = None
        self.last_encoder_right = None

        # Timer voor feedback polling en odom publish
        self.create_timer(0.05, self.update_callback)  # 20Hz

        # Timeout: stop motoren als geen cmd_vel ontvangen
        self.last_cmd_time = time.time()
        self.cmd_timeout = 0.5  # seconden
        self.create_timer(0.1, self.watchdog_callback)

        # Verbind met ESP32
        if self.serial.connect():
            self.get_logger().info('Serial connected')
            # Init-sequentie
            init_cmds = serial_cfg.get('init_commands', [])
            if init_cmds:
                self.serial.init_sequence(init_cmds)
                self.get_logger().info(f'Init sequence sent ({len(init_cmds)} commands)')
        else:
            self.get_logger().error('Serial connection failed!')

    def cmd_vel_callback(self, msg: Twist):
        """Vertaal cmd_vel Twist naar motor PWM commando's."""
        self.last_cmd_time = time.time()

        linear = max(-self.max_linear, min(self.max_linear, msg.linear.x))
        angular = max(-self.max_angular, min(self.max_angular, msg.angular.z))

        # Differentieel model
        left_vel = linear - angular * self.wheelbase / 2.0
        right_vel = linear + angular * self.wheelbase / 2.0

        # Schaal naar PWM
        left_pwm = int(left_vel * self.speed_scale)
        right_pwm = int(right_vel * self.speed_scale)

        self.serial.send_motor(left_pwm, right_pwm)

    def update_callback(self):
        """Lees feedback en publiceer odometrie."""
        feedback = self.serial.get_feedback()
        if not feedback:
            return

        now = time.time()
        dt = now - self.last_feedback_time
        self.last_feedback_time = now

        if dt <= 0 or dt > 1.0:
            return

        # Encoder-based odometrie
        enc_left = feedback.get('L', 0)
        enc_right = feedback.get('R', 0)

        if self.last_encoder_left is not None:
            d_left = (enc_left - self.last_encoder_left)
            d_right = (enc_right - self.last_encoder_right)

            # Ticks naar meters
            dist_per_tick = (2.0 * math.pi * self.wheel_radius) / self.encoder_ticks
            dl = d_left * dist_per_tick
            dr = d_right * dist_per_tick

            # Differentieel model
            d_center = (dl + dr) / 2.0
            d_theta = (dr - dl) / self.wheelbase

            self.theta += d_theta
            self.x += d_center * math.cos(self.theta)
            self.y += d_center * math.sin(self.theta)

        self.last_encoder_left = enc_left
        self.last_encoder_right = enc_right

        # Publiceer odometrie
        self._publish_odom(dt, feedback)

        # Publiceer batterijspanning
        voltage = feedback.get('V')
        if voltage is not None:
            battery_msg = Float32()
            battery_msg.data = float(voltage)
            self.battery_pub.publish(battery_msg)

    def _publish_odom(self, dt: float, feedback: dict):
        """Publiceer Odometry message en TF transform."""
        stamp = self.get_clock().now().to_msg()

        # Quaternion van theta
        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)

        # TF: odom → base_link
        tf = TransformStamped()
        tf.header.stamp = stamp
        tf.header.frame_id = 'odom'
        tf.child_frame_id = 'base_link'
        tf.transform.translation.x = self.x
        tf.transform.translation.y = self.y
        tf.transform.translation.z = 0.0
        tf.transform.rotation.z = qz
        tf.transform.rotation.w = qw
        self.tf_broadcaster.sendTransform(tf)

        # Odometry message
        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw

        # Velocity uit feedback
        enc_left = feedback.get('L', 0)
        enc_right = feedback.get('R', 0)
        dist_per_tick = (2.0 * math.pi * self.wheel_radius) / self.encoder_ticks
        if dt > 0:
            vl = (enc_left * dist_per_tick) / dt if self.last_encoder_left is None else 0.0
            vr = (enc_right * dist_per_tick) / dt if self.last_encoder_right is None else 0.0
            odom.twist.twist.linear.x = (vl + vr) / 2.0
            odom.twist.twist.angular.z = (vr - vl) / self.wheelbase

        self.odom_pub.publish(odom)

    def watchdog_callback(self):
        """Stop motoren als geen recent cmd_vel commando."""
        if time.time() - self.last_cmd_time > self.cmd_timeout:
            self.serial.send_motor(0, 0)

    def destroy_node(self):
        """Cleanup: stop motoren en sluit serial."""
        self.serial.send_motor(0, 0)
        self.serial.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BaseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
