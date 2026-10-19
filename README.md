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
offers to pull the prebuilt image from GitHub Container Registry
(`ghcr.io/alianlbj23/hiwin_ros2:humble`, a few GB, once). Nothing is compiled on
your machine.

```
========== HIWIN RA6 Docker launcher ==========
 Settings: type=ra610_1476  IP=unset  RViz=true
  0) Settings (robot type / controller IP / RViz / domain ID)
  1) Simulation (mock hardware + RViz)
  2) Real robot (GC2 cabinet)
  3) Shell inside the container
  4) Pull / update the image (from GHCR)
  5) Follow container logs
  6) Status
  7) Stop containers
  8) Build the image locally (fallback)
  q) Quit
```

| Option | What it does |
|---|---|
| 0 | Change robot type, controller IP (with network scan and help), RViz on/off, ROS_DOMAIN_ID. Saved to `.env`, remembered next time. |
| 1 | Start MoveIt with a simulated robot. Safe anywhere, no robot needed. RViz opens if enabled. |
| 2 | Start MoveIt connected to the real robot. Asks for the controller IP once, then asks you to confirm before connecting. |
| 3 | Open a terminal inside the container with ROS 2 already set up. Use it for `ros2 topic echo`, your own nodes, etc. |
| 4 | Pull the latest image from GHCR. Run it again after a new version was merged. |
| 5 | Show the live log of the running container. |
| 6 | Show which containers are running and whether the image exists. |
| 7 | Stop everything. |
| 8 | Build the image on this machine instead (only needed when GHCR is unreachable or you are editing the Dockerfile). |

Press `Ctrl+C` in the launcher to stop a running simulation or robot session.

To write your own ROS 2 code against the running stack, use the second launcher
`./dev.py` (section 4).

### Simulation

1. `./run.py` → `1`
2. Press Enter to accept the current settings (or `n` to change them).
3. Wait for `You can start planning now!` in the log. RViz opens with the robot.
4. In RViz, drag the end-effector marker and press **Plan & Execute** in the MotionPlanning panel.

### Real robot

1. Make sure the GC2 cabinet is on, the robot is in a safe pose and the E-stop is within reach.
2. `./run.py` → `2`
3. Pick the controller IP when asked (only the first time). `run.py` scans this PC's
   networks for devices answering on the HIWIN port (TCP 1503) and lists them as
   candidates; `c` enters an IP manually, `s` scans a subnet you name, `h` explains
   how to find the IP (teach pendant, `ping`, `nc -zv <ip> 1503`). On WSL2 automatic
   discovery usually finds nothing; use `c` or `s`.
4. Read the warning and answer `y`.
5. Wait for `You can start planning now!`. The robot now follows every trajectory sent through MoveIt.

Motion speed is limited to 10 % of the robot's maximum by default. Raise it in RViz
(Velocity Scaling) only after testing in simulation.

## 3. Without the menu (docker compose)

```bash
docker pull ghcr.io/alianlbj23/hiwin_ros2:humble   # once, and after each release
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
| `HIWIN_IMAGE` | `ghcr.io/alianlbj23/hiwin_ros2:humble` | Image used by `run.py` and compose. Point it at another tag (e.g. `...:humble-<sha>`) or at `hiwin_ros2:humble` after a local `docker compose build`. |
| `ROS_DOMAIN_ID` | `0` | Must match other ROS 2 machines you want to talk to |

### How the image is built

[`.github/workflows/docker-image.yml`](.github/workflows/docker-image.yml) builds the
Dockerfile on every push to `main` (and on manual *Run workflow*) and pushes two tags
to GHCR: `humble` (always the latest `main`) and `humble-<short sha>` (immutable, for
rolling back). Pull `humble` again after a merge to update; build locally only when
changing the Dockerfile.

## 4. Writing your own code (`dev.py` + `user_ws/`)

`user_ws/` is your workspace. It is bind-mounted into a separate `dev` container at
`/user_ws`, so your code and build output stay on your machine, and it is built as an
overlay on top of the prebuilt `/ros2_ws`, which is never modified. Your nodes talk to
MoveIt over ROS 2 (host network), exactly like a second machine would.

```bash
./run.py   # → 1, start the simulation (or 2 for the real robot) and leave it running
./dev.py   # in a second terminal
```

```
========== HIWIN RA6 dev workspace ==========
 ROS_DOMAIN_ID=0  workspace=/path/to/hiwin_ros2/user_ws
  0) Settings (shared with run.py: ROS_DOMAIN_ID, robot type, ...)
  1) Shell in the dev container (/user_ws)
  2) Build user_ws (colcon build)
  3) Run a node from user_ws
  4) Test user_ws (colcon test)
  5) Clean build artefacts
  6) Status
  q) Quit
```

| Option | What it does |
|---|---|
| 0 | Same settings menu as `run.py` (`ROS_DOMAIN_ID`, robot type, IP, RViz). |
| 1 | Open a shell in the dev container. You land in `/user_ws` with ROS 2, `/ros2_ws` and (if built) `/user_ws` sourced. |
| 2 | `colcon build --symlink-install` of everything in `user_ws/src`. With symlink-install, edits to Python files take effect without rebuilding. |
| 3 | Pick a package and executable from `user_ws/src`, optionally add arguments, and `ros2 run` it. Builds first if `user_ws/install` is missing. |
| 4 | `colcon test` + `colcon test-result --verbose`. |
| 5 | Delete `user_ws/build install log` (done inside the container because they are root-owned). |
| 6 | Show image, `ROS_DOMAIN_ID`, whether `user_ws` is built, the packages and executables found, and running containers. |

`ROS_DOMAIN_ID` is the one global setting both menus share. It lives in `.env`
(option `0` in either menu, or edit the file): the sim/robot container and the dev
container must use the same value, and two robots or two people on one network
should use different values.

The template package `user_ws/src/hiwin_user_py` shows the MoveIt 2 round trip.
`move_demo` reads `/joint_states`, asks `move_group` through the `/move_action`
action to move one joint by 10°, and prints the result. It only plans by default;
`execute:=true` makes it move.

Typical session:

```bash
./dev.py → 2                                  # build
./dev.py → 3, pick move_demo                  # plan only, nothing moves
./dev.py → 3, extra args: --ros-args -p execute:=true   # MOVES THE ROBOT (sim or real)
./dev.py → 3, extra args: --ros-args -p joint:=joint_2 -p delta_deg:=-5.0 -p execute:=true
./dev.py → 4                                  # run the package tests
```

#### Layout of `user_ws/`

| Path | What it is |
|---|---|
| `src/hiwin_user_py` | Python template package (`move_demo`). Copy it to start your own. |
| `src/<your_pkg>` | Any further ROS 2 packages you add. |
| `.devrc` | Shell file loaded in the dev container: sources ROS 2, `/ros2_ws` and `/user_ws`. |
| `build/ install/ log/` | colcon output. Created by the container (root-owned on the host), ignored by git, removed with option `5`. |

#### Adding your own package

1. Create it under `user_ws/src/` (`ros2 pkg create --build-type ament_python my_pkg`
   from the dev shell, or copy `hiwin_user_py`).
2. Register executables in `setup.py` under `console_scripts`; `dev.py` lists them.
3. Depend on `moveit_msgs`, `control_msgs`, `sensor_msgs`, ... in `package.xml`. They
   are all in the image already; if you need something that is not, add it to the
   Dockerfile (section 3) so CI rebuilds the image.
4. `./dev.py` → `2`, then `3`.

#### The same without the menu

```bash
docker compose run --rm dev                                   # shell in /user_ws
docker compose run --rm dev bash -c "source /user_ws/.devrc && colcon build --symlink-install"
docker compose run --rm dev bash -c "source /user_ws/.devrc && colcon test && colcon test-result --verbose"
docker compose run --rm dev bash -c "source /user_ws/.devrc && ros2 run hiwin_user_py move_demo"
docker compose run --rm dev bash -c "source /user_ws/.devrc && ros2 run hiwin_user_py move_demo --ros-args -p execute:=true"
```

`.devrc` sources ROS 2, `/ros2_ws/install` and `/user_ws/install` in that order. The
dev container has the same `ROS_DOMAIN_ID` as `sim`/`robot` because all of them read
`.env`. Do not put `${VAR}` in a command passed to the container: the image
entrypoint expands such tokens before bash sees them.

Humble has no `moveit_py`, so from Python use the `moveit_msgs` actions and services
directly (`/move_action`, `/execute_trajectory`, `/compute_ik`, `/plan_kinematic_path`).
C++ `MoveGroupInterface` (`moveit_ros_planning_interface`) is also in the image for
`ament_cmake` packages; load the MoveIt configuration in your launch file with
`MoveItConfigsBuilder("hiwin_ra6", package_name="hiwin_ra6_moveit_config")`.

Limits:

- The containers run as root, so `user_ws/build install log` are root-owned on the
  host (option `5` removes them from inside the container).
- `apt install` inside a container is not kept; packages your code needs go into the
  Dockerfile so CI rebuilds the image.
- A package in `user_ws` with the same name as one in `/ros2_ws` shadows it, but only
  inside the dev container; `sim` and `robot` are unaffected.

## 5. Talking to the robot from your own code

The container uses the host network, so any ROS 2 Humble node on the same machine
(or on the same LAN with the same `ROS_DOMAIN_ID`) sees the topics below directly.
No extra configuration is needed.

To try it from a second terminal on the host:

```bash
./dev.py            # → 1 (shell in the dev container), or ./run.py → 3
ros2 topic list
ros2 topic echo /joint_states
```

Before you publish or call anything, read the next section: it marks which
interfaces make the arm move.

Planning group name: `manipulator`. Joint names: `joint_1` … `joint_6`.
Base frame: `base_link`. Flange frame: `link_6`. Named pose: `home`.

## 6. What is published when the system is running

### ⚠ Interfaces that MOVE the robot

Everything below is served by `move_group` and `ros2_control`. With the real robot
(`./run.py` → `2`) these commands move real hardware at once; there is no extra
confirmation. Test in simulation first and keep the E-stop within reach.

| Interface | Kind | Moves the robot? |
|---|---|---|
| `/move_action` | action `moveit_msgs/action/MoveGroup` | **Yes, unless** `planning_options.plan_only` is `true`. The field defaults to `false`, so a bare goal plans **and executes**. `move_demo` sets it to `true` unless you pass `execute:=true`. |
| `/execute_trajectory` | action `moveit_msgs/action/ExecuteTrajectory` | **Yes, always.** Runs a trajectory you planned earlier (e.g. from `/plan_kinematic_path`). |
| `/manipulator_controller/follow_joint_trajectory` | action `control_msgs/action/FollowJointTrajectory` | **Yes, always.** Goes straight to `ros2_control`, **bypassing MoveIt's collision checking and velocity scaling.** |
| `/manipulator_controller/joint_trajectory` | topic `trajectory_msgs/msg/JointTrajectory` | **Yes, always.** Same as above but fire-and-forget, no result feedback. |
| `/trajectory_execution_event` | topic `std_msgs/msg/String` | No. Publishing `stop` **aborts** the trajectory MoveIt is executing (does not affect trajectories sent directly to the controller). |
| `/plan_kinematic_path`, `/compute_cartesian_path`, `/compute_ik`, `/compute_fk`, `/check_state_validity`, `/get_planning_scene` | services | No. Planning and kinematics only; the result is returned to you, nothing is executed. |
| `/planning_scene`, `/planning_scene_world`, `/collision_object`, `/attached_collision_object`, `/apply_planning_scene` | topics / service | No. They change what MoveIt plans around, but do not move anything by themselves. |
| `/joint_states`, `/tf`, `/tf_static`, `/robot_description`, `/manipulator_controller/*state*`, `/monitored_planning_scene`, `/display_*`, `/motion_plan_request` | topics | No. Read-only status; subscribe freely. |

Rows marked **MOVES** in the tables below are the same four interfaces.

### Topics

| Topic | Type | Content |
|---|---|---|
| `/joint_states` | `sensor_msgs/msg/JointState` | Current joint positions and velocities, 500 Hz |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | Transform tree `base_link` → `link_1` … `link_6` |
| `/robot_description` | `std_msgs/msg/String` | Robot URDF (latched) |
| `/manipulator_controller/controller_state` | `control_msgs/msg/JointTrajectoryControllerState` | Desired vs. actual joint state while a trajectory runs |
| `/manipulator_controller/joint_trajectory` | `trajectory_msgs/msg/JointTrajectory` | **MOVES.** Publish here to send a trajectory directly to the controller, bypassing MoveIt (no collision checking, no result) |
| `/manipulator_controller/state` | `control_msgs/msg/JointTrajectoryControllerState` | Controller state (Humble name; `controller_state` is the newer alias) |
| `/dynamic_joint_states` | `control_msgs/msg/DynamicJointState` | Same data as `/joint_states` with interface names |
| `/monitored_planning_scene` | `moveit_msgs/msg/PlanningScene` | MoveIt's current scene, published on every change |
| `/planning_scene` | `moveit_msgs/msg/PlanningScene` | Publish here to modify the scene |
| `/planning_scene_world` | `moveit_msgs/msg/PlanningSceneWorld` | Publish here to add world objects |
| `/collision_object` | `moveit_msgs/msg/CollisionObject` | Publish here to add or remove obstacles |
| `/attached_collision_object` | `moveit_msgs/msg/AttachedCollisionObject` | Publish here to attach an object to the robot |
| `/display_planned_path` | `moveit_msgs/msg/DisplayTrajectory` | Last planned trajectory (shown in RViz) |
| `/motion_plan_request` | `moveit_msgs/msg/MotionPlanRequest` | Last planning request |
| `/trajectory_execution_event` | `std_msgs/msg/String` | Publish `stop` here to abort the trajectory MoveIt is executing |
| `/display_contacts` | `visualization_msgs/msg/MarkerArray` | Collision contact markers for RViz |

### Actions

| Action | Type | Use |
|---|---|---|
| `/move_action` | `moveit_msgs/action/MoveGroup` | **MOVES unless `planning_options.plan_only=true`.** Plan and execute a motion with collision checking. Main entry point for MoveIt clients; used by `move_demo`. |
| `/execute_trajectory` | `moveit_msgs/action/ExecuteTrajectory` | **MOVES.** Execute an already planned trajectory |
| `/manipulator_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | **MOVES.** Send a joint trajectory directly to the controller, bypassing MoveIt |

### Services

| Service | Type | Use |
|---|---|---|
| `/plan_kinematic_path` | `moveit_msgs/srv/GetMotionPlan` | Plan only, return the trajectory |
| `/compute_ik` | `moveit_msgs/srv/GetPositionIK` | Inverse kinematics |
| `/compute_fk` | `moveit_msgs/srv/GetPositionFK` | Forward kinematics |
| `/compute_cartesian_path` | `moveit_msgs/srv/GetCartesianPath` | Straight-line Cartesian path through waypoints |
| `/get_planning_scene` | `moveit_msgs/srv/GetPlanningScene` | Read the current scene and robot state |
| `/check_state_validity` | `moveit_msgs/srv/GetStateValidity` | Check a robot state for collisions and constraint violations |
| `/get_planner_params`, `/set_planner_params` | `moveit_msgs/srv/GetPlannerParams`, `SetPlannerParams` | Read or tune planner parameters at runtime |
| `/manipulator_controller/query_state` | `control_msgs/srv/QueryTrajectoryState` | Ask the controller for the planned state at a given time |
| `/apply_planning_scene` | `moveit_msgs/srv/ApplyPlanningScene` | Modify the scene and wait until applied |
| `/query_planner_interface` | `moveit_msgs/srv/QueryPlannerInterfaces` | List available planners (`ompl`, `chomp`, `pilz_industrial_motion_planner`) |
| `/controller_manager/list_controllers` | `controller_manager_msgs/srv/ListControllers` | Check that `joint_state_broadcaster` and `manipulator_controller` are `active` |

## 7. Checking that everything is up

Inside a container shell (`./dev.py` → `1` or `./run.py` → `3`):

```bash
ros2 control list_controllers
# joint_state_broadcaster  ... active
# manipulator_controller   ... active

ros2 topic hz /joint_states          # about 500 Hz
ros2 action list                     # /move_action, /execute_trajectory, ...
```

## 8. Troubleshooting

| Symptom | What to do |
|---|---|
| RViz window does not appear | Run `xhost +local:root` on the host and make sure `DISPLAY` is set. Or set RViz to `false` in Settings and use the topics only. |
| `ros2 node list` shows only a few nodes | Run `ros2 node list --no-daemon`, or `ros2 daemon stop` and try again. |
| Real robot: no connection | `./run.py` → `0` → `2` rescans; a working controller shows "port 1503 answers". Otherwise `ping <ip>` and `nc -zv <ip> 1503` from the host, and check the cabinet is on and in the mode that accepts external control. |
| Controller not listed as a candidate | It is on a subnet this PC does not scan automatically (larger than /24, or behind WSL2 NAT). Use `s` with the LAN subnet (e.g. `192.168.0.0/24`) or `c` to enter the IP. |
| `No 3D sensor plugin(s) defined for octomap updates` in the log | Harmless. It only means no depth camera is configured. |
| Start fails with the image missing | `./run.py` → `4` to pull it. |
| `docker pull` is denied / unauthorized | The GHCR package is private. Either make it public (GitHub → Packages → hiwin_ros2 → Package settings → Change visibility) or `docker login ghcr.io` with a token that has `read:packages`. |

## License

See [LICENSE](LICENSE). Based on
[HIWINCorporation/hiwin_ros2](https://github.com/HIWINCorporation/hiwin_ros2).
