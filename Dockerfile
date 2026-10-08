# syntax=docker/dockerfile:1
#
# HIWIN RA6 (default: RA610-1476) ROS 2 Humble + MoveIt 2 + ros2_control image.
#
#   docker build -t hiwin_ros2:humble .
#   docker compose up robot          # real robot (set ROBOT_IP in .env)
#   docker compose up sim            # mock hardware, RViz only
#
ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO}-ros-base-jammy

ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO} \
    DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ROS2_WS=/ros2_ws

# Pinned upstream sources (bump deliberately).
ARG HIWIN_CLIENT_LIB_REPO=https://github.com/HIWINCorporation/hiwin_robot_client_library.git
ARG HIWIN_CLIENT_LIB_REF=dd2936379125f62ecada98649ee5b7051aad7b1b
ARG ETHERCAT_DRIVER_REPO=https://github.com/ICube-Robotics/ethercat_driver_ros2.git
ARG ETHERCAT_DRIVER_REF=1390be742986f4e898ca112e49bb24805be9899a
ARG ETHERLAB_REPO=https://gitlab.com/etherlab.org/ethercat.git
ARG ETHERLAB_BRANCH=stable-1.5

# ---------------------------------------------------------------------------
# System build tools + libs that are not expressed as rosdep keys
#   libi2c-dev : required by hiwin_driver (cabinet IO over SMBus)
#   autoconf/automake/libtool : EtherLab userspace build
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        autoconf automake libtool pkg-config \
        build-essential cmake git ca-certificates \
        libi2c-dev \
        python3-colcon-common-extensions python3-rosdep python3-vcstool \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# EtherLab (IgH EtherCAT master) userspace library only.
# ethercat_interface hard-codes /usr/local/etherlab for headers + libethercat.
# The kernel module (ec_master) must be installed on the HOST, not here.
# ---------------------------------------------------------------------------
RUN git clone --depth 1 --branch ${ETHERLAB_BRANCH} ${ETHERLAB_REPO} /tmp/etherlab \
    && cd /tmp/etherlab \
    && ./bootstrap \
    && ./configure --prefix=/usr/local/etherlab --disable-kernel --disable-8139too --disable-eoe \
    && make -j"$(nproc)" \
    && make install \
    && echo /usr/local/etherlab/lib > /etc/ld.so.conf.d/etherlab.conf \
    && ldconfig \
    && rm -rf /tmp/etherlab

# ---------------------------------------------------------------------------
# hiwin_robot_client_library (hrsdk) -> system install, as in the upstream
# README. hiwin_driver finds it with plain find_package(), not via package.xml,
# so it must live in a prefix CMake always searches (/usr/local).
# ---------------------------------------------------------------------------
RUN git clone ${HIWIN_CLIENT_LIB_REPO} /tmp/hiwin_robot_client_library \
    && git -C /tmp/hiwin_robot_client_library checkout --detach ${HIWIN_CLIENT_LIB_REF} \
    && cmake -S /tmp/hiwin_robot_client_library -B /tmp/hiwin_robot_client_library/build \
         -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local \
    && cmake --build /tmp/hiwin_robot_client_library/build -j"$(nproc)" \
    && cmake --install /tmp/hiwin_robot_client_library/build \
    && ldconfig \
    && rm -rf /tmp/hiwin_robot_client_library

# ---------------------------------------------------------------------------
# Workspace sources
# ---------------------------------------------------------------------------
WORKDIR ${ROS2_WS}

RUN git clone ${ETHERCAT_DRIVER_REPO} src/ethercat_driver_ros2 \
    && git -C src/ethercat_driver_ros2 checkout --detach ${ETHERCAT_DRIVER_REF} \
    && rm -rf src/*/.git

COPY . src/hiwin_ros2

# ---------------------------------------------------------------------------
# ROS dependencies (MoveIt 2, ros2_control, RViz, ...)
# gazebo_ros_control is only referenced by hiwin_rs4_moveit_config and would
# pull the whole Gazebo Classic stack. warehouse_ros_mongo has no Humble apt
# package and is only used by the optional warehouse_db launch file.
# ---------------------------------------------------------------------------
RUN apt-get update \
    && rosdep update --rosdistro ${ROS_DISTRO} \
    && rosdep install --from-paths src --ignore-src -y --rosdistro ${ROS_DISTRO} \
        --skip-keys "gazebo_ros_control warehouse_ros_mongo" \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
RUN . /opt/ros/${ROS_DISTRO}/setup.sh \
    && colcon build \
        --cmake-args -DCMAKE_BUILD_TYPE=Release \
        --event-handlers console_cohesion+ \
    && rm -rf build log

# Operator tooling not pulled in by any package.xml (ros2 control list_controllers, ...).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-${ROS_DISTRO}-ros2controlcli \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Runtime defaults. Override with -e / compose environment.
# Mock hardware is the default so a bare `docker run` can never move a robot.
# ---------------------------------------------------------------------------
ENV RA_TYPE=ra610_1476 \
    ROBOT_IP=0.0.0.0 \
    CABINET=gc2 \
    USE_FAKE_HARDWARE=true \
    LAUNCH_RVIZ=true \
    QT_X11_NO_MITSHM=1

COPY <<'EOF' /ros_entrypoint.sh
#!/bin/bash
# Source ROS 2 + the workspace, expand ${VAR} placeholders in the CMD args
# (no eval: only ${NAME} tokens are substituted), then exec.
set -e
source "/opt/ros/${ROS_DISTRO}/setup.bash"
if [ -f "${ROS2_WS}/install/setup.bash" ]; then
  source "${ROS2_WS}/install/setup.bash"
fi

expand() {
  local s="$1"
  while [[ "$s" =~ ^(.*)\$\{([A-Za-z_][A-Za-z0-9_]*)\}(.*)$ ]]; do
    s="${BASH_REMATCH[1]}${!BASH_REMATCH[2]}${BASH_REMATCH[3]}"
  done
  printf '%s' "$s"
}

args=()
for a in "$@"; do
  args+=("$(expand "$a")")
done

exec "${args[@]}"
EOF
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["ros2", "launch", "hiwin_ra6_moveit_config", "ra6_moveit.launch.py", \
     "ra_type:=${RA_TYPE}", "robot_ip:=${ROBOT_IP}", "cabinet:=${CABINET}", \
     "use_fake_hardware:=${USE_FAKE_HARDWARE}", "launch_rviz:=${LAUNCH_RVIZ}"]
