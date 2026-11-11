# syntax=docker/dockerfile:1
#
# HIWIN RA6 (default: RA610-1476) ROS 2 Humble + MoveIt 2 + ros2_control image.
#
#   docker build -t ghcr.io/alianlbj23/hiwin_ros2:humble .
#   docker compose up robot          # real robot (set ROBOT_IP in .env)
#   docker compose up sim            # mock hardware, RViz only
#
# Targets:
#   base    (default)  ROS 2 + MoveIt + HIWIN workspace         -> :humble
#   desktop            base + XFCE over VNC/noVNC + SSH server  -> :humble-desktop
#   docker build --target desktop -t ghcr.io/alianlbj23/hiwin_ros2:humble-desktop .
# Local builds use the GHCR name too; images are published only by CI, to GHCR.
#
ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO}-ros-base-jammy AS hiwin

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

# ===========================================================================
# Target `desktop`: the same stack plus a remote desktop.
#   XFCE on TigerVNC (VNC_PORT, default 5901), noVNC in the browser
#   (NOVNC_PORT, 8080, http://<host>:8080/vnc.html) and OpenSSH (SSH_PORT, 2222).
#   One login user `ros` (uid 1000, sudo). No password is baked in: the
#   container refuses to start unless VNC_PASSWORD is set (VNC + SSH + sudo).
#   docker compose up -d desktop     (or ./run.py -> 9)
# ===========================================================================
FROM hiwin AS desktop

ENV DESKTOP_USER=ros

# openssh-server generates host keys in its postinst; delete them so no two
# containers share a key. The entrypoint creates them in a persistent volume.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xfce4 xfce4-terminal dbus-x11 x11-xserver-utils adwaita-icon-theme fonts-dejavu-core \
        tigervnc-standalone-server tigervnc-tools \
        novnc websockify \
        openssh-server sudo \
        libgl1-mesa-dri mesa-utils \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/ssh/ssh_host_* \
    && xfwm=/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml \
    && if [ -f "$xfwm" ]; then \
         sed -i 's/name="use_compositing" type="bool" value="true"/name="use_compositing" type="bool" value="false"/' "$xfwm"; \
       fi

# Login user. Every interactive shell (VNC terminal, SSH) sources ROS 2, the
# prebuilt workspace, the user_ws overlay if built, and the runtime settings
# (ROS_DOMAIN_ID, RA_TYPE, DISPLAY, ...) written by the entrypoint.
RUN useradd -m -s /bin/bash -u 1000 -G sudo,dialout ${DESKTOP_USER} \
    && mkdir -p /run/sshd /etc/ssh/keys /home/${DESKTOP_USER}/.vnc \
    && printf '%s\n' \
        '' \
        '# Added by the hiwin_ros2 desktop image.' \
        '[ -f /etc/hiwin_desktop.env ] && source /etc/hiwin_desktop.env' \
        "source /opt/ros/${ROS_DISTRO}/setup.bash" \
        "source ${ROS2_WS}/install/setup.bash" \
        '[ -f /user_ws/install/setup.bash ] && source /user_ws/install/setup.bash' \
        >> /home/${DESKTOP_USER}/.bashrc \
    && chown -R ${DESKTOP_USER}:${DESKTOP_USER} /home/${DESKTOP_USER}

COPY <<'EOF' /etc/ssh/sshd_config.d/hiwin.conf
# Port comes from SSH_PORT (sshd -p in /desktop_entrypoint.sh).
HostKey /etc/ssh/keys/ssh_host_ed25519_key
HostKey /etc/ssh/keys/ssh_host_rsa_key
PermitRootLogin no
AllowUsers ros
PasswordAuthentication yes
KbdInteractiveAuthentication no
X11Forwarding yes
PrintMotd no
EOF

COPY <<'EOF' /desktop_entrypoint.sh
#!/bin/bash
# Start the remote desktop: Xvnc + XFCE, noVNC (websockify) and sshd.
# Settings come from the environment (docker-compose.yml, service `desktop`).
# The container stops when one of the three services exits.
set -euo pipefail

VNC_PORT="${VNC_PORT:-5901}"
NOVNC_PORT="${NOVNC_PORT:-8080}"
SSH_PORT="${SSH_PORT:-2222}"
VNC_DISPLAY="${VNC_DISPLAY:-20}"
VNC_GEOMETRY="${VNC_GEOMETRY:-1920x1080}"
HOME_DIR="/home/${DESKTOP_USER}"

fail() { echo "desktop: $*" >&2; exit 1; }

# ---- validate input ------------------------------------------------------
pw="${VNC_PASSWORD:-}"
if [[ -z "$pw" ]]; then
  fail "VNC_PASSWORD is not set. Set it with ./run.py -> 0 -> 6, or VNC_PASSWORD=... in .env."
fi
if [[ ! "$pw" =~ ^[A-Za-z0-9._@!%+=-]{6,8}$ ]]; then
  fail "VNC_PASSWORD must be 6-8 characters from letters, digits and . _ @ ! % + = -"
fi
for name in VNC_PORT NOVNC_PORT SSH_PORT; do
  val="${!name}"
  if [[ ! "$val" =~ ^[0-9]{4,5}$ ]] || (( val < 1024 || val > 65535 )); then
    fail "$name=$val must be a port number from 1024 to 65535."
  fi
done
if [[ "$VNC_PORT" == "$NOVNC_PORT" || "$VNC_PORT" == "$SSH_PORT" || "$NOVNC_PORT" == "$SSH_PORT" ]]; then
  fail "VNC_PORT, NOVNC_PORT and SSH_PORT must differ."
fi
[[ "$VNC_DISPLAY" =~ ^[0-9]{1,3}$ ]] || fail "VNC_DISPLAY=$VNC_DISPLAY must be a display number (e.g. 20)."
[[ "$VNC_GEOMETRY" =~ ^[0-9]{3,5}x[0-9]{3,5}$ ]] || fail "VNC_GEOMETRY=$VNC_GEOMETRY must look like 1920x1080."

# ---- credentials ---------------------------------------------------------
printf '%s:%s\n' "$DESKTOP_USER" "$pw" | chpasswd
printf '%s\n' "$pw" | vncpasswd -f > "$HOME_DIR/.vnc/passwd"
chmod 600 "$HOME_DIR/.vnc/passwd"
chown "$DESKTOP_USER:$DESKTOP_USER" "$HOME_DIR/.vnc" "$HOME_DIR/.vnc/passwd"
unset pw VNC_PASSWORD

# SSH host keys live in a volume so clients do not see a new key after every restart.
for type in ed25519 rsa; do
  key="/etc/ssh/keys/ssh_host_${type}_key"
  if [[ ! -f "$key" ]]; then
    ssh-keygen -q -t "$type" -N '' -f "$key"
  fi
done

# ---- environment for VNC terminals and SSH logins (sourced by ~/.bashrc) --
# Fast DDS shared memory does not work between user `ros` and the root
# processes in the sim/robot/dev containers (root creates the /dev/shm
# segments 0644, so `ros` cannot write to them): topics are listed but no data
# arrives. Use UDP only; overridable via the container environment.
FASTDDS_BUILTIN_TRANSPORTS="${FASTDDS_BUILTIN_TRANSPORTS:-UDPv4}"
{
  echo "# Written by /desktop_entrypoint.sh at container start."
  for name in ROS_DISTRO ROS2_WS ROS_DOMAIN_ID RA_TYPE ROBOT_IP CABINET USE_FAKE_HARDWARE LAUNCH_RVIZ QT_X11_NO_MITSHM FASTDDS_BUILTIN_TRANSPORTS; do
    if [[ -n "${!name+x}" ]]; then
      printf 'export %s=%q\n' "$name" "${!name}"
    fi
  done
  # SSH sessions without -X draw on the VNC desktop.
  printf 'export DISPLAY="${DISPLAY:-:%s}"\n' "$VNC_DISPLAY"
} > /etc/hiwin_desktop.env

# ---- start services ------------------------------------------------------
runtime_dir="/tmp/runtime-$DESKTOP_USER"
install -d -m 700 -o "$DESKTOP_USER" -g "$DESKTOP_USER" "$runtime_dir"
install -d -m 1777 /tmp/.X11-unix
rm -f "/tmp/.X${VNC_DISPLAY}-lock" "/tmp/.X11-unix/X${VNC_DISPLAY}"

as_user() {
  runuser -u "$DESKTOP_USER" -- env -i \
    HOME="$HOME_DIR" USER="$DESKTOP_USER" LOGNAME="$DESKTOP_USER" SHELL=/bin/bash \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 XDG_RUNTIME_DIR="$runtime_dir" DISPLAY=":$VNC_DISPLAY" \
    "$@"
}

pids=()
stop_all() { kill "${pids[@]}" 2>/dev/null || true; }
trap 'stop_all; exit 0' TERM INT

/usr/sbin/sshd -D -e -p "$SSH_PORT" &
pids+=($!)

as_user Xvnc ":$VNC_DISPLAY" -rfbport "$VNC_PORT" -rfbauth "$HOME_DIR/.vnc/passwd" \
  -SecurityTypes VncAuth -geometry "$VNC_GEOMETRY" -depth 24 -AlwaysShared \
  -desktop "HIWIN RA6 (${RA_TYPE:-ra6})" &
pids+=($!)
for _ in $(seq 50); do
  [[ -S "/tmp/.X11-unix/X$VNC_DISPLAY" ]] && break
  sleep 0.2
done
[[ -S "/tmp/.X11-unix/X$VNC_DISPLAY" ]] || { stop_all; fail "Xvnc did not start on display :$VNC_DISPLAY."; }

# Logging out of XFCE starts a fresh session instead of stopping the container.
as_user bash -c 'while true; do dbus-launch --exit-with-session startxfce4; sleep 1; done' &
pids+=($!)

as_user websockify --web /usr/share/novnc "$NOVNC_PORT" "localhost:$VNC_PORT" &
pids+=($!)

cat <<INFO
==========================================================
 HIWIN RA6 remote desktop (user: $DESKTOP_USER, password: VNC_PASSWORD)
   VNC viewer : <host>:$VNC_PORT
   Browser    : http://<host>:$NOVNC_PORT/vnc.html
   SSH        : ssh -p $SSH_PORT $DESKTOP_USER@<host>
==========================================================
INFO

set +e
wait -n "${pids[@]}"
rc=$?
echo "desktop: a service exited (status $rc), stopping the container." >&2
stop_all
exit 1
EOF
RUN chmod +x /desktop_entrypoint.sh

ENTRYPOINT ["/desktop_entrypoint.sh"]
CMD []

# ===========================================================================
# Default target (plain `docker build .`): the image without the desktop.
# Must stay the last stage.
# ===========================================================================
FROM hiwin AS base
