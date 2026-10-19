"""Minimal MoveIt 2 client: move one joint by a few degrees through /move_action.

MoveIt (move_group) runs in the `sim` or `robot` container; this node runs in the
`dev` container and only talks to it over ROS 2, so nothing in /ros2_ws is touched.

    ros2 run hiwin_user_py move_demo                       # plan only (default)
    ros2 run hiwin_user_py move_demo --ros-args -p execute:=true
    ros2 run hiwin_user_py move_demo --ros-args -p joint:=joint_2 -p delta_deg:=-5.0

Humble has no moveit_py, so the MoveGroup action is used directly. A named pose
(e.g. `home`) is not expressible in the action; send joint values instead.
"""
import math
import sys

import rclpy
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint, MoveItErrorCodes
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState

SERVER_TIMEOUT_S = 10.0
JOINT_STATE_TIMEOUT_S = 10.0
RESULT_TIMEOUT_S = 60.0


def build_goal(
    group: str,
    joint_positions: dict[str, float],
    *,
    execute: bool,
    velocity_scaling: float,
    acceleration_scaling: float,
    planning_time: float = 5.0,
) -> MoveGroup.Goal:
    """Return a MoveGroup goal that drives `group` to `joint_positions` (radians).

    Pure function so it can be unit-tested without a running ROS graph.
    """
    if not 0.0 < velocity_scaling <= 1.0 or not 0.0 < acceleration_scaling <= 1.0:
        raise ValueError("velocity/acceleration scaling must be in (0, 1]")
    if not joint_positions:
        raise ValueError("joint_positions must not be empty")

    goal = MoveGroup.Goal()
    req = goal.request
    req.group_name = group
    req.num_planning_attempts = 5
    req.allowed_planning_time = planning_time
    req.max_velocity_scaling_factor = velocity_scaling
    req.max_acceleration_scaling_factor = acceleration_scaling
    # Empty start_state + is_diff -> plan from the robot's current state.
    req.start_state.is_diff = True

    constraints = Constraints()
    for name, position in joint_positions.items():
        jc = JointConstraint()
        jc.joint_name = name
        jc.position = float(position)
        jc.tolerance_above = 0.01
        jc.tolerance_below = 0.01
        jc.weight = 1.0
        constraints.joint_constraints.append(jc)
    req.goal_constraints.append(constraints)

    goal.planning_options.plan_only = not execute
    goal.planning_options.replan = False
    return goal


class MoveDemo(Node):
    def __init__(self) -> None:
        super().__init__("move_demo")
        self.declare_parameter("group", "manipulator")
        self.declare_parameter("joint", "joint_1")
        self.declare_parameter("delta_deg", 10.0)
        self.declare_parameter("execute", False)
        self.declare_parameter("velocity_scaling", 0.1)
        self.declare_parameter("acceleration_scaling", 0.1)

        self._joint_state: JointState | None = None
        self.create_subscription(JointState, "/joint_states", self._on_joint_state, 10)
        self._client = ActionClient(self, MoveGroup, "/move_action")

    def _on_joint_state(self, msg: JointState) -> None:
        self._joint_state = msg

    def wait_for_joint_state(self) -> JointState:
        deadline = self.get_clock().now().nanoseconds + int(JOINT_STATE_TIMEOUT_S * 1e9)
        while self._joint_state is None:
            if self.get_clock().now().nanoseconds > deadline:
                raise TimeoutError("no /joint_states received; is the sim/robot container running?")
            rclpy.spin_once(self, timeout_sec=0.1)
        return self._joint_state

    def run(self) -> int:
        """Plan (and optionally execute) the move. Returns a process exit code."""
        group = self.get_parameter("group").value
        joint = self.get_parameter("joint").value
        delta_deg = float(self.get_parameter("delta_deg").value)
        execute = bool(self.get_parameter("execute").value)

        self.get_logger().info(f"waiting up to {SERVER_TIMEOUT_S:.0f}s for /move_action ...")
        if not self._client.wait_for_server(timeout_sec=SERVER_TIMEOUT_S):
            self.get_logger().error("/move_action not available; start the sim/robot first")
            return 1

        state = self.wait_for_joint_state()
        if joint not in state.name:
            self.get_logger().error(f"joint {joint!r} not in /joint_states {list(state.name)}")
            return 1
        current = dict(zip(state.name, state.position))
        target = dict(current)
        target[joint] = current[joint] + math.radians(delta_deg)
        self.get_logger().info(
            f"{joint}: {math.degrees(current[joint]):.1f} deg -> {math.degrees(target[joint]):.1f} deg "
            f"({'EXECUTE' if execute else 'plan only'})"
        )

        goal = build_goal(
            group,
            target,
            execute=execute,
            velocity_scaling=float(self.get_parameter("velocity_scaling").value),
            acceleration_scaling=float(self.get_parameter("acceleration_scaling").value),
        )
        send = self._client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send, timeout_sec=SERVER_TIMEOUT_S)
        handle = send.result()
        if handle is None or not handle.accepted:
            self.get_logger().error("goal rejected by move_group")
            return 1

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=RESULT_TIMEOUT_S)
        if result_future.result() is None:
            self.get_logger().error(f"no result within {RESULT_TIMEOUT_S:.0f}s")
            return 1
        result = result_future.result().result
        code = result.error_code.val
        if code != MoveItErrorCodes.SUCCESS:
            self.get_logger().error(f"move_group failed, MoveItErrorCodes.val={code}")
            return 1
        n_points = len(result.planned_trajectory.joint_trajectory.points)
        self.get_logger().info(
            f"SUCCESS: {n_points} trajectory points, planning took {result.planning_time:.2f}s"
            + ("" if execute else " (not executed: pass -p execute:=true to move the robot)")
        )
        return 0


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MoveDemo()
    try:
        rc = node.run()
    except (TimeoutError, KeyboardInterrupt) as exc:
        node.get_logger().error(str(exc) or "interrupted")
        rc = 1
    finally:
        node.destroy_node()
        rclpy.shutdown()
    sys.exit(rc)


if __name__ == "__main__":
    main()
