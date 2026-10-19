#!/usr/bin/env python3
"""Menu-driven entry point for developing your own ROS 2 packages against the
HIWIN RA6 MoveIt 2 stack. No arguments needed.

    ./dev.py

user_ws/ on the host is mounted at /user_ws inside the `dev` container and built
there as an overlay workspace; /ros2_ws (HIWIN driver + MoveIt) is never modified.
Start the simulation or the real robot with ./run.py first, then use this menu.
ROS_DOMAIN_ID and the other settings are shared with run.py through .env.
"""
import re
import sys

import run  # helpers shared with run.py (compose detection, .env, image handling, X11)

USER_WS = run.ROOT / "user_ws"
SRC = USER_WS / "src"
DEVRC = "/user_ws/.devrc"


# ----------------------------------------------------------------- helpers
def in_dev(script: str, env: dict[str, str]) -> int:
    """Run a bash snippet inside a throw-away dev container with the workspaces sourced.

    `script` must not contain ${VAR} tokens: the image entrypoint expands them
    before bash sees the command.
    """
    cmd = run.compose() + ["run", "--rm", "dev", "bash", "-c", f"source {DEVRC} && {script}"]
    return run.run(cmd, env)


def user_packages() -> dict[str, list[str]]:
    """Map every package under user_ws/src to its console_script executables."""
    pkgs: dict[str, list[str]] = {}
    for pkg_xml in sorted(SRC.glob("*/package.xml")):
        match = re.search(r"<name>\s*([\w-]+)\s*</name>", pkg_xml.read_text())
        if not match:
            continue
        name = match.group(1)
        setup_py = pkg_xml.with_name("setup.py")
        execs: list[str] = []
        if setup_py.exists():
            execs = re.findall(r"[\"']([\w-]+)\s*=\s*[\w.]+:\w+[\"']", setup_py.read_text())
        pkgs[name] = execs
    return pkgs


def pick(prompt: str, items: list[str]) -> str | None:
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    for i, item in enumerate(items, 1):
        print(f"  {i}) {item}")
    val = run.ask(prompt, "1")
    if val.isdigit() and 1 <= int(val) <= len(items):
        return items[int(val) - 1]
    if val in items:
        return val
    print("Invalid choice.")
    return None


# ----------------------------------------------------------------- actions
def do_shell(cfg: dict[str, str]) -> int:
    """Interactive shell in /user_ws with ROS 2, /ros2_ws and /user_ws sourced."""
    if not run.ensure_image():
        return 1
    run.allow_x11()
    print("\nYou are in /user_ws. `colcon build --symlink-install` builds your packages. Type exit to leave.")
    return run.run(run.compose() + ["run", "--rm", "dev"], run.common_env(cfg))


def do_build(cfg: dict[str, str]) -> int:
    if not run.ensure_image():
        return 1
    if not any(SRC.glob("*/package.xml")):
        print(f"No packages found in {SRC}. Put your ROS 2 packages there first.")
        return 1
    return in_dev("colcon build --symlink-install --event-handlers console_cohesion+", run.common_env(cfg))


def do_test(cfg: dict[str, str]) -> int:
    if not run.ensure_image():
        return 1
    return in_dev("colcon test --event-handlers console_cohesion+ && colcon test-result --verbose", run.common_env(cfg))


def do_run(cfg: dict[str, str]) -> int:
    """Pick a package and executable from user_ws and `ros2 run` it in the dev container."""
    if not run.ensure_image():
        return 1
    pkgs = user_packages()
    if not pkgs:
        print(f"No packages found in {SRC}.")
        return 1
    if not (USER_WS / "install").exists():
        print("user_ws is not built yet, building first.")
        if do_build(cfg) != 0:
            return 1
    print("\nPackage:")
    pkg = pick("Select", list(pkgs))
    if pkg is None:
        return 1
    print("\nExecutable:")
    exe = pick("Select", pkgs[pkg]) or run.ask("Executable name")
    if not exe:
        return 1
    extra = run.ask("Extra arguments (e.g. --ros-args -p execute:=true), Enter for none")
    if not re.fullmatch(r"[\w\s.:=/\-]*", extra):
        print("Only letters, digits and . : = / - are allowed in extra arguments.")
        return 1
    if "${" in extra:
        print("${...} is not allowed (the container entrypoint would expand it).")
        return 1
    run.allow_x11()
    print("\nCtrl+C to stop the node.")
    return in_dev(f"ros2 run {pkg} {exe} {extra}".rstrip(), run.common_env(cfg))


def do_clean(cfg: dict[str, str]) -> int:
    """Remove colcon output. Done inside the container because the files are root-owned."""
    if not run.yes_no("Delete user_ws/build, install and log?", False):
        return 0
    if not run.ensure_image():
        return 1
    return in_dev("rm -rf /user_ws/build /user_ws/install /user_ws/log", run.common_env(cfg))


def do_status(cfg: dict[str, str]) -> int:
    print(f"\nImage {run.IMAGE}: {'present' if run.image_exists() else 'not pulled'}")
    print(f"ROS_DOMAIN_ID: {cfg['ROS_DOMAIN_ID']}  (change it in ./run.py or ./dev.py -> Settings)")
    print(f"user_ws built: {'yes' if (USER_WS / 'install').exists() else 'no'}")
    pkgs = user_packages()
    print("Packages in user_ws/src:" if pkgs else f"No packages in {SRC}")
    for name, execs in pkgs.items():
        print(f"  {name}: {', '.join(execs) or '(no console_scripts)'}")
    return run.run(run.compose() + ["ps"])


# ----------------------------------------------------------------- menu
MENU = [
    ("0", "Settings (shared with run.py: ROS_DOMAIN_ID, robot type, ...)", lambda cfg: run.do_settings(cfg)),
    ("1", "Shell in the dev container (/user_ws)", do_shell),
    ("2", "Build user_ws (colcon build)", do_build),
    ("3", "Run a node from user_ws", do_run),
    ("4", "Test user_ws (colcon test)", do_test),
    ("5", "Clean build artefacts", do_clean),
    ("6", "Status", do_status),
]


def main() -> None:
    if not USER_WS.is_dir():
        sys.exit(f"Error: {USER_WS} does not exist.")
    while True:
        cfg = run.load_env()
        print("\n========== HIWIN RA6 dev workspace ==========")
        print(f" ROS_DOMAIN_ID={cfg['ROS_DOMAIN_ID']}  workspace={USER_WS}")
        for key, label, _ in MENU:
            print(f"  {key}) {label}")
        print("  q) Quit")
        choice = run.ask("Select").lower()
        if choice in ("q", "quit", "exit"):
            return
        for key, _, action in MENU:
            if choice == key:
                action(cfg)
                run.pause()
                break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
