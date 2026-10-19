# HIWIN RA6 ROS 2 (Docker)

Run a HIWIN RA6 robot (default: RA610-1476) with ROS 2 Humble and MoveIt 2 from a
single Docker image. Nothing has to be installed on the host except Docker.

Supported robot types: `ra605_710`, `ra610_1355`, `ra610_1476`, `ra610_1869`.

## 1. Requirements

- Ubuntu 22.04 (or WSL2 with WSLg) with Docker Engine and the `docker compose` plugin
- Python 3 (for `run.py`, no extra packages)
- A desktop session (`DISPLAY` set) if you want to see RViz
- For a real robot: the robot connected to a HIWIN GC2 cabinet, reachable over the network

## 2. Quick start

```bash
git clone https://github.com/alianlbj23/hiwin_ros2.git
cd hiwin_ros2
./run.py
```

`run.py` shows a menu. The first time you pick *Simulation* or *Real robot* it
offers to build the image (10-20 minutes, once).

```
========== HIWIN RA6 Docker launcher ==========
 Settings: type=ra610_1476  IP=unset  RViz=true
  0) Settings (robot type / controller IP / RViz / domain ID)
  1) Simulation (mock hardware + RViz)
  2) Real robot (GC2 cabinet)
  3) Shell inside the container
  4) Build / rebuild the image
  5) Follow container logs
  6) Status
  7) Stop containers
  q) Quit
```

| Option | What it does |
|---|---|
| 0 | Change robot type, controller IP, RViz on/off, ROS_DOMAIN_ID. Saved to `.env`, remembered next time. |
| 1 | Start MoveIt with a simulated robot. Safe anywhere, no robot needed. RViz opens if enabled. |
| 2 | Start MoveIt connected to the real robot. Asks for the controller IP once, then asks you to confirm before connecting. |
| 3 | Open a terminal inside the container with ROS 2 already set up. Use it for `ros2 topic echo`, your own nodes, etc. |
| 4 | Build or rebuild the Docker image. |
| 5 | Show the live log of the running container. |
| 6 | Show which containers are running and whether the image exists. |
| 7 | Stop everything. |

Press `Ctrl+C` in the launcher to stop a running simulation or robot session.

### Simulation

1. `./run.py` → `1`
2. Press Enter to accept the current settings (or `n` to change them).
3. Wait for `You can start planning now!` in the log. RViz opens with the robot.
4. In RViz, drag the end-effector marker and press **Plan & Execute** in the MotionPlanning panel.

### Real robot

1. Make sure the GC2 cabinet is on, the robot is in a safe pose and the E-stop is within reach.
2. `./run.py` → `2`
3. Enter the controller IP when asked (asked only the first time).
4. Read the warning and answer `y`.
5. Wait for `You can start planning now!`. The robot now follows every trajectory sent through MoveIt.

Motion speed is limited to 10 % of the robot's maximum by default. Raise it in RViz
(Velocity Scaling) only after testing in simulation.

## 3. Without the menu (docker compose)

```bash
docker build -t hiwin_ros2:humble .      # once
cp .env.example .env                     # edit ROBOT_IP / RA_TYPE if needed
xhost +local:root                        # let RViz open a window

docker compose up sim                    # simulation
docker compose up robot                  # real robot
docker compose run --rm shell            # terminal inside the container
docker compose down                      # stop
```

Settings in `.env`:

| Variable | Default | Meaning |
|---|---|---|
| `RA_TYPE` | `ra610_1476` | Robot model |
| `ROBOT_IP` | *(empty)* | GC2 controller IP, required for `robot` |
| `LAUNCH_RVIZ` | `true` | Open RViz |
| `ROS_DOMAIN_ID` | `0` | Must match other ROS 2 machines you want to talk to |

## 4. Talking to the robot from your own code

The container uses the host network, so any ROS 2 Humble node on the same machine
(or on the same LAN with the same `ROS_DOMAIN_ID`) sees the topics below directly.
No extra configuration is needed.

To try it from a second terminal on the host:

```bash
./run.py            # → 3 (shell inside the container)
ros2 topic list
ros2 topic echo /joint_states
```

Planning group name: `manipulator`. Joint names: `joint_1` … `joint_6`.
Base frame: `base_link`. Flange frame: `link_6`. Named pose: `home`.

## 5. What is published when the system is running

### Topics

| Topic | Type | Content |
|---|---|---|
| `/joint_states` | `sensor_msgs/msg/JointState` | Current joint positions and velocities, 500 Hz |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | Transform tree `base_link` → `link_1` … `link_6` |
| `/robot_description` | `std_msgs/msg/String` | Robot URDF (latched) |
| `/manipulator_controller/controller_state` | `control_msgs/msg/JointTrajectoryControllerState` | Desired vs. actual joint state while a trajectory runs |
| `/manipulator_controller/joint_trajectory` | `trajectory_msgs/msg/JointTrajectory` | Publish here to send a trajectory directly, bypassing MoveIt |
| `/dynamic_joint_states` | `control_msgs/msg/DynamicJointState` | Same data as `/joint_states` with interface names |
| `/monitored_planning_scene` | `moveit_msgs/msg/PlanningScene` | MoveIt's current scene, published on every change |
| `/planning_scene` | `moveit_msgs/msg/PlanningScene` | Publish here to modify the scene |
| `/planning_scene_world` | `moveit_msgs/msg/PlanningSceneWorld` | Publish here to add world objects |
| `/collision_object` | `moveit_msgs/msg/CollisionObject` | Publish here to add or remove obstacles |
| `/attached_collision_object` | `moveit_msgs/msg/AttachedCollisionObject` | Publish here to attach an object to the robot |
| `/display_planned_path` | `moveit_msgs/msg/DisplayTrajectory` | Last planned trajectory (shown in RViz) |
| `/motion_plan_request` | `moveit_msgs/msg/MotionPlanRequest` | Last planning request |
| `/trajectory_execution_event` | `std_msgs/msg/String` | Publish `stop` here to abort the running trajectory |
| `/display_contacts` | `visualization_msgs/msg/MarkerArray` | Collision contact markers for RViz |

### Actions

| Action | Type | Use |
|---|---|---|
| `/move_action` | `moveit_msgs/action/MoveGroup` | Plan and (optionally) execute a motion. Main entry point for MoveIt clients. |
| `/execute_trajectory` | `moveit_msgs/action/ExecuteTrajectory` | Execute an already planned trajectory |
| `/manipulator_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | Send a joint trajectory directly to the controller |

### Services

| Service | Type | Use |
|---|---|---|
| `/plan_kinematic_path` | `moveit_msgs/srv/GetMotionPlan` | Plan only, return the trajectory |
| `/compute_ik` | `moveit_msgs/srv/GetPositionIK` | Inverse kinematics |
| `/compute_fk` | `moveit_msgs/srv/GetPositionFK` | Forward kinematics |
| `/compute_cartesian_path` | `moveit_msgs/srv/GetCartesianPath` | Straight-line Cartesian path through waypoints |
| `/get_planning_scene` | `moveit_msgs/srv/GetPlanningScene` | Read the current scene and robot state |
| `/apply_planning_scene` | `moveit_msgs/srv/ApplyPlanningScene` | Modify the scene and wait until applied |
| `/query_planner_interface` | `moveit_msgs/srv/QueryPlannerInterfaces` | List available planners (`ompl`, `chomp`, `pilz_industrial_motion_planner`) |
| `/controller_manager/list_controllers` | `controller_manager_msgs/srv/ListControllers` | Check that `joint_state_broadcaster` and `manipulator_controller` are `active` |

## 6. Checking that everything is up

Inside the container shell (`./run.py` → `3`):

```bash
ros2 control list_controllers
# joint_state_broadcaster  ... active
# manipulator_controller   ... active

ros2 topic hz /joint_states          # about 500 Hz
ros2 action list                     # /move_action, /execute_trajectory, ...
```

## 7. Troubleshooting

| Symptom | What to do |
|---|---|
| RViz window does not appear | Run `xhost +local:root` on the host and make sure `DISPLAY` is set. Or set RViz to `false` in Settings and use the topics only. |
| `ros2 node list` shows only a few nodes | Run `ros2 node list --no-daemon`, or `ros2 daemon stop` and try again. |
| Real robot: no connection | Check `ping <controller IP>` from the host, and that the cabinet is in the mode that accepts external control. |
| `No 3D sensor plugin(s) defined for octomap updates` in the log | Harmless. It only means no depth camera is configured. |
| Start fails with the image missing | `./run.py` → `4` to build it. |

## License

See [LICENSE](LICENSE). Based on
[HIWINCorporation/hiwin_ros2](https://github.com/HIWINCorporation/hiwin_ros2).
