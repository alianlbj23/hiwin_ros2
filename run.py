#!/usr/bin/env python3
"""Menu-driven launcher for the HIWIN RA6 Docker image. No arguments needed.

    ./run.py

Robot type, controller IP, RViz switch and ROS_DOMAIN_ID are remembered in
.env (git-ignored), so the next run only needs Enter.
"""
import ipaddress
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
IMAGE = "hiwin_ros2:humble"
RA_TYPES = ["ra605_710", "ra610_1355", "ra610_1476", "ra610_1869"]
DEFAULTS = {"RA_TYPE": "ra610_1476", "ROBOT_IP": "", "LAUNCH_RVIZ": "true", "ROS_DOMAIN_ID": "0"}


# ----------------------------------------------------------------- helpers
def ask(prompt: str, default: str = "") -> str:
    """Prompt for a line of input; Enter returns the default. Ctrl+C/EOF exits."""
    hint = f" (Enter = {default})" if default else ""
    try:
        val = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or default


def yes_no(prompt: str, default: bool) -> bool:
    val = ask(f"{prompt} [{'Y/n' if default else 'y/N'}]").lower()
    if val in ("y", "yes"):
        return True
    if val in ("n", "no"):
        return False
    return default


def pause() -> None:
    ask("\nPress Enter to return to the menu")


def run(cmd: list[str], env: dict | None = None) -> int:
    """Run a command in the repo root with extra environment variables, echoing it first."""
    shown = " ".join(f"{k}={v}" for k, v in (env or {}).items())
    print(f"\n$ {shown} {' '.join(cmd)}".replace("$  ", "$ "))
    try:
        return subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}).returncode
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


def compose() -> list[str]:
    """Return the compose command: the docker plugin if present, else legacy docker-compose."""
    if shutil.which("docker") is None:
        sys.exit("Error: docker not found. Install Docker Engine first.")
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    sys.exit("Error: neither 'docker compose' nor 'docker-compose' is available.")


def load_env() -> dict[str, str]:
    """Read .env on top of DEFAULTS. Unknown keys are kept so hand edits survive."""
    cfg = dict(DEFAULTS)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.split("#", 1)[0].strip()
    return cfg


def save_env(cfg: dict[str, str]) -> None:
    lines = ["# Maintained by run.py; manual edits are fine."]
    lines += [f"{k}={cfg.get(k, DEFAULTS[k])}" for k in DEFAULTS]
    ENV_FILE.write_text("\n".join(lines) + "\n")


def valid_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def image_exists() -> bool:
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0


def ensure_image() -> bool:
    """Make sure the image exists, offering to build it if not."""
    if image_exists():
        return True
    if yes_no(f"Image {IMAGE} not found. Build it now (takes 10-20 min)?", True):
        return do_build() == 0
    print("Cannot start without the image.")
    return False


def allow_x11() -> None:
    """Let the root user inside the container open windows on the host X server."""
    if not os.environ.get("DISPLAY"):
        print("Note: DISPLAY is not set, RViz will not be shown.")
    elif shutil.which("xhost"):
        subprocess.run(["xhost", "+local:root"], capture_output=True)
    else:
        print("Note: xhost not found. If RViz cannot open a window, run `xhost +local:root`.")


# ----------------------------------------------------------------- prompts
def choose_ra_type(cfg: dict[str, str]) -> str:
    print("\nRobot type:")
    for i, t in enumerate(RA_TYPES, 1):
        mark = "  <- current" if t == cfg["RA_TYPE"] else ""
        print(f"  {i}) {t}{mark}")
    while True:
        val = ask("Select", cfg["RA_TYPE"])
        if val.isdigit() and 1 <= int(val) <= len(RA_TYPES):
            return RA_TYPES[int(val) - 1]
        if val in RA_TYPES:
            return val
        print("Invalid choice.")


def choose_ip(cfg: dict[str, str]) -> str:
    while True:
        val = ask("HIWIN controller (GC2) IP", cfg["ROBOT_IP"])
        if valid_ip(val):
            return val
        print("Not a valid IP address, try again.")


def common_env(cfg: dict[str, str]) -> dict[str, str]:
    """Environment passed to every compose service (see docker-compose.yml)."""
    return {k: cfg[k] for k in ("RA_TYPE", "LAUNCH_RVIZ", "ROS_DOMAIN_ID")}


def show_settings(cfg: dict[str, str], with_ip: bool) -> None:
    ip = f"  IP={cfg['ROBOT_IP'] or 'unset'}" if with_ip else ""
    print(f"\nCurrent settings: type={cfg['RA_TYPE']}{ip}  RViz={cfg['LAUNCH_RVIZ']}")


# ----------------------------------------------------------------- actions
def do_build() -> int:
    return run(["docker", "build", "-t", IMAGE, "."])


def do_settings(cfg: dict[str, str]) -> int:
    """Settings sub-menu. Every change is written to .env immediately."""
    while True:
        print("\n---------- Settings ----------")
        print(f"  1) Robot type     : {cfg['RA_TYPE']}")
        print(f"  2) Controller IP  : {cfg['ROBOT_IP'] or 'unset'}")
        print(f"  3) Launch RViz    : {cfg['LAUNCH_RVIZ']}")
        print(f"  4) ROS_DOMAIN_ID  : {cfg['ROS_DOMAIN_ID']}")
        print("  5) Reset to defaults")
        print("  Enter) Back to main menu")
        choice = ask("Select")
        if choice == "":
            return 0
        if choice == "1":
            cfg["RA_TYPE"] = choose_ra_type(cfg)
        elif choice == "2":
            cfg["ROBOT_IP"] = choose_ip(cfg)
        elif choice == "3":
            cfg["LAUNCH_RVIZ"] = "true" if yes_no("Launch RViz?", cfg["LAUNCH_RVIZ"] == "true") else "false"
        elif choice == "4":
            val = ask("ROS_DOMAIN_ID (0-232)", cfg["ROS_DOMAIN_ID"])
            if val.isdigit() and 0 <= int(val) <= 232:
                cfg["ROS_DOMAIN_ID"] = val
            else:
                print("Invalid value.")
                continue
        elif choice == "5":
            if yes_no("Reset all settings (this clears the IP)?", False):
                cfg.update(DEFAULTS)
        else:
            print("Invalid choice.")
            continue
        save_env(cfg)
        print(f"Saved to {ENV_FILE.name}")


def do_sim(cfg: dict[str, str]) -> int:
    """Mock hardware + MoveIt (+ RViz). Safe to run anywhere."""
    if not ensure_image():
        return 1
    show_settings(cfg, with_ip=False)
    if not yes_no("Use these settings?", True):
        do_settings(cfg)
    if cfg["LAUNCH_RVIZ"] == "true":
        allow_x11()
    print("\nStarting simulation. Ctrl+C to stop.")
    return run(compose() + ["up", "sim"], common_env(cfg))


def do_robot(cfg: dict[str, str]) -> int:
    """Real robot through the GC2 cabinet. Requires a controller IP and a confirmation."""
    if not ensure_image():
        return 1
    if not cfg["ROBOT_IP"]:
        print("\nNo controller IP configured yet.")
        cfg["ROBOT_IP"] = choose_ip(cfg)
        save_env(cfg)
    show_settings(cfg, with_ip=True)
    if not yes_no("Use these settings?", True):
        do_settings(cfg)
        if not cfg["ROBOT_IP"]:
            print("No IP configured, aborting.")
            return 0
    print(f"\nWARNING: about to connect to a REAL robot  type={cfg['RA_TYPE']}  IP={cfg['ROBOT_IP']}")
    print("         Check the workspace is clear and the E-stop is within reach.")
    print("         MoveIt velocity scaling defaults to 0.1.")
    if not yes_no("Continue?", False):
        print("Cancelled.")
        return 0
    if cfg["LAUNCH_RVIZ"] == "true":
        allow_x11()
    print("\nStarting real robot stack. Ctrl+C to stop.")
    return run(compose() + ["up", "robot"], {**common_env(cfg), "ROBOT_IP": cfg["ROBOT_IP"]})


def do_shell(cfg: dict[str, str]) -> int:
    if not ensure_image():
        return 1
    allow_x11()
    print("\nThe workspace is already sourced inside the container. Type exit to leave.")
    return run(compose() + ["run", "--rm", "shell"], common_env(cfg))


def do_logs() -> int:
    print("\nCtrl+C to stop following logs.")
    return run(compose() + ["logs", "-f", "--tail", "200"])


def do_stop() -> int:
    return run(compose() + ["down", "--remove-orphans"])


def do_status() -> int:
    rc = run(compose() + ["ps"])
    print(f"\nImage {IMAGE}: {'built' if image_exists() else 'not built'}")
    return rc


# ----------------------------------------------------------------- menu
MENU = [
    ("0", "Settings (robot type / controller IP / RViz / domain ID)", lambda cfg: do_settings(cfg)),
    ("1", "Simulation (mock hardware + RViz)", lambda cfg: do_sim(cfg)),
    ("2", "Real robot (GC2 cabinet)", lambda cfg: do_robot(cfg)),
    ("3", "Shell inside the container", lambda cfg: do_shell(cfg)),
    ("4", "Build / rebuild the image", lambda cfg: do_build()),
    ("5", "Follow container logs", lambda cfg: do_logs()),
    ("6", "Status", lambda cfg: do_status()),
    ("7", "Stop containers", lambda cfg: do_stop()),
]


def main() -> None:
    os.chdir(ROOT)
    while True:
        cfg = load_env()
        print("\n========== HIWIN RA6 Docker launcher ==========")
        print(f" Settings: type={cfg['RA_TYPE']}  IP={cfg['ROBOT_IP'] or 'unset'}  RViz={cfg['LAUNCH_RVIZ']}")
        for key, label, _ in MENU:
            print(f"  {key}) {label}")
        print("  q) Quit")
        choice = ask("Select").lower()
        if choice in ("q", "quit", "exit"):
            return
        for key, _, action in MENU:
            if choice == key:
                action(cfg)
                pause()
                break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
