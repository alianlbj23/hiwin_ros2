# HIWIN Robot ROS2

[![License - apache 2.0](https://img.shields.io/:license-Apache%202.0-yellowgreen.svg)](https://opensource.org/licenses/Apache-2.0)
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

This repository provides the ROS2 stack for **HIWIN robots**, allowing integration with the ROS2 ecosystem for easy robot control and simulation.

## Contents
This repository follows branch naming aligned with ROS 2 distributions.
- Stable branches: `humble`, `iron`
- Development branches: `*-devel` (may be unstable)

## Features ##
- **Integration with `ros2_control`:** Direct hardware interface via ROS 2 control for precise control and monitoring.
- **MoveIt 2 Integration:** Enables motion planning, trajectory execution, and manipulation tasks.
- **Robot Drivers:** Built on top of the [hiwin_robot_client_library](https://github.com/HIWINCorporation/hiwin_robot_client_library) (currently under development) to support position control for HIWIN robots.

:warning: **Known Limitations**:warning:
The **hiwin_robot_client_library** is still under development. As a result:
1. The library cannot handle rapid command sequences effectively.
2. Execution times for physical robot movements are significantly longer than planned durations in trajectory commands.

## Packages in the Repository:
- `hiwin_driver` - Provides hardware interfaces for communication with HIWIN robots, including the implementation of dedicated controllers.
- `hiwin_ra6_moveit_config` - MoveIt 2 configuration package for the RA6 series of HIWIN robots. Includes tools for integration with MoveIt 2 for motion planning and control.
- `hiwin_rs4_moveit_config` - MoveIt 2 configuration package for the RS4 series of HIWIN robots. Includes tools for integration with MoveIt 2 for motion planning and control.

## General Requirements
- **Operating System:** Ubuntu 22.04 LTS
- **ROS 2 version:** Humble Hawksbill

## Getting Started
1. **Install ros2 packages**
Follow the steps outlined in the [ROS 2 Humble installation guide](https://docs.ros.org/en/humble/Installation.html).
2. **Source the ROS 2 Environment**
```bash
source /opt/ros/humble/setup.bash
```
3. **Create a ROS 2 Workspace**
```bash
mkdir -p ~/colcon_ws/src
```
4. **Clone the Repository and Build**
```bash
cd ~/colcon_ws

git clone https://github.com/HIWINCorporation/hiwin_ros2.git src/hiwin_ros2

colcon build --symlink-install

source install/setup.sh
```

## Usage
### :warning: **SAFETY FIRST**:warning:
*It is strongly recommended to test your code in simulation before using it on physical hardware.*

### Simulated hardware
To test the robot in a simulated environment:
```bash
ros2 launch hiwin_ra6_moveit_config ra6_moveit.launch.py ra_type:=ra610_1476 use_fake_hardware:=true
```

### Real Robot Control
To connect to and control a physical robot:
```bash
ros2 launch hiwin_ra6_moveit_config ra6_moveit.launch.py ra_type:=ra610_1476 use_fake_hardware:=false robot_ip:=<robot ip>
```
### **HRSS Offline Simulation**  
The **HIWIN Robot System Software (HRSS)** provides tools to control basic robot functions.  
For offline simulation:
1. Download [HRSS Offline](https://www.hiwinsupport.com/download_center.aspx?pid=MAR).
2. Launch the robot simulation:
```bash
ros2 launch hiwin_ra6_moveit_config ra6_moveit.launch.py ra_type:=ra605_710 use_fake_hardware:=false robot_ip:=<workstation ip>
```

## Docker
A ready-to-run image (ROS 2 Humble + MoveIt 2 + ros2_control + `hiwin_driver`) is defined in the [Dockerfile](Dockerfile).
It installs `hiwin_robot_client_library` system-wide and builds `ethercat_driver_ros2` plus this repository in one colcon workspace. Supported `ra_type`
values: `ra605_710`, `ra610_1355`, `ra610_1476`, `ra610_1869` (default `ra610_1476`).

The easiest way is the launcher script (Python 3, no extra dependencies):
```bash
./run.py            # interactive menu
./run.py sim        # mock hardware + RViz
./run.py robot      # real robot; asks for / remembers ROBOT_IP in .env
./run.py shell      # bash inside the container
./run.py build      # (re)build the image
./run.py stop
```

Or by hand:
```bash
# 1. build
docker build -t hiwin_ros2:humble .

# 2. allow RViz to use the host display
xhost +local:root

# 3a. mock hardware
docker compose up sim

# 3b. real robot (GC2 cabinet, TCP)
cp .env.example .env            # set ROBOT_IP
docker compose up robot

# 3c. shell with the workspace sourced
docker compose run --rm shell
```

Everything can also be driven with plain `docker run`:
```bash
docker run --rm -it --net=host --ipc=host \
  -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
  -e RA_TYPE=ra610_1476 -e USE_FAKE_HARDWARE=false -e ROBOT_IP=<robot ip> \
  hiwin_ros2:humble
```
Environment variables: `RA_TYPE`, `ROBOT_IP`, `CABINET` (`gc2`|`ecat`), `USE_FAKE_HARDWARE`, `LAUNCH_RVIZ`.
The image defaults to `USE_FAKE_HARDWARE=true`, so a bare `docker run` never commands a real robot.

Notes
- `cabinet:=ecat` additionally needs the IgH EtherCAT master kernel module on the host and the
  `/dev/EtherCAT0`, `/dev/i2c-0`, `/dev/ttyS1` devices passed into the container (see the commented
  block in [docker-compose.yml](docker-compose.yml)). Only the EtherLab userspace library is inside the image.
- `--net=host` is required both for DDS discovery and for the TCP connection to the robot controller.
