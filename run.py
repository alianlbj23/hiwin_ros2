#!/usr/bin/env python3
"""Menu-driven launcher for the HIWIN RA6 Docker image. No arguments needed.

    ./run.py

Robot type, controller IP, RViz switch and ROS_DOMAIN_ID are remembered in
.env (git-ignored), so the next run only needs Enter.

The image is built by GitHub Actions (.github/workflows/docker-image.yml) and
pulled from GHCR; set HIWIN_IMAGE to use another tag or a locally built image.
"""
import ipaddress
import os
import shutil
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
DEFAULT_IMAGE = "ghcr.io/alianlbj23/hiwin_ros2:humble"
IMAGE = os.environ.get("HIWIN_IMAGE", "").strip() or DEFAULT_IMAGE
RA_TYPES = ["ra605_710", "ra610_1355", "ra610_1476", "ra610_1869"]
# TCP port the GC2 controller listens on (hiwin_robot_client_library COMMAND_PORT).
# Used only to detect candidates; the driver itself does the real connection.
HIWIN_COMMAND_PORT = 1503
PROBE_TIMEOUT_S = 0.5
AUTO_SCAN_MIN_PREFIX = 24     # auto-scan only /24 or smaller networks (<= 254 hosts)
MANUAL_SCAN_MAX_HOSTS = 1024  # /22
SCAN_WORKERS = 64
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


# ----------------------------------------------------- controller discovery
def tcp_port_open(ip: str, port: int = HIWIN_COMMAND_PORT, timeout: float = PROBE_TIMEOUT_S) -> bool:
    """True if a TCP connection to ip:port succeeds within `timeout` seconds."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def host_networks(ip_addr_output: str | None = None) -> list[tuple[str, ipaddress.IPv4Network]]:
    """(interface, network) for this PC's IPv4 interfaces, parsed from `ip -4 -o addr`.

    Loopback, Docker/bridge/veth, VPN (tailscale) and single-address (/32) entries are skipped.
    """
    if ip_addr_output is None:
        if shutil.which("ip") is None:
            return []
        try:
            ip_addr_output = subprocess.run(
                ["ip", "-4", "-o", "addr"], capture_output=True, text=True, timeout=5, check=False
            ).stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Note: could not list network interfaces: {exc}")
            return []
    nets: list[tuple[str, ipaddress.IPv4Network]] = []
    for line in ip_addr_output.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[2] != "inet":
            continue
        iface, cidr = parts[1], parts[3]
        if iface == "lo" or iface.startswith(("docker", "br-", "veth", "tailscale", "virbr")):
            continue
        try:
            net = ipaddress.ip_interface(cidr).network
        except ValueError:
            continue
        if isinstance(net, ipaddress.IPv4Network) and net.num_addresses > 2:
            nets.append((iface, net))
    return nets


def neighbour_ips() -> list[str]:
    """IPv4 addresses in the ARP table (`ip -4 neigh`), i.e. devices seen on directly attached networks."""
    if shutil.which("ip") is None:
        return []
    try:
        out = subprocess.run(["ip", "-4", "neigh", "show"], capture_output=True, text=True, timeout=5, check=False).stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Note: could not read the ARP table: {exc}")
        return []
    ips = []
    for line in out.splitlines():
        parts = line.split()
        if parts and valid_ip(parts[0]) and "FAILED" not in parts:
            ips.append(parts[0])
    return ips


def default_gateways(route_output: str | None = None) -> set[str]:
    """IPv4 default-gateway addresses from `ip -4 route show default`. Gateways/NAT boxes can
    accept connections on many ports, so they are flagged in the candidate list."""
    if route_output is None:
        if shutil.which("ip") is None:
            return set()
        try:
            route_output = subprocess.run(
                ["ip", "-4", "route", "show", "default"], capture_output=True, text=True, timeout=5, check=False
            ).stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Note: could not read the routing table: {exc}")
            return set()
    gws = set()
    for line in route_output.splitlines():
        parts = line.split()
        if "via" in parts:
            gw = parts[parts.index("via") + 1]
            if valid_ip(gw):
                gws.add(gw)
    return gws


def scan_network(net: ipaddress.IPv4Network, port: int = HIWIN_COMMAND_PORT) -> list[str]:
    """Hosts in `net` that accept a TCP connection on `port`, in address order."""
    hosts = [str(h) for h in net.hosts()]
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        results = pool.map(lambda ip: tcp_port_open(ip, port), hosts)
        return [ip for ip, ok in zip(hosts, results) if ok]


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def find_candidates(cfg: dict[str, str]) -> dict[str, str]:
    """Candidate controller IPs -> short note. Saved IP first, then every host answering on port 1503."""
    cands: dict[str, str] = {}
    saved = cfg.get("ROBOT_IP", "")
    if saved:
        state = "answers" if tcp_port_open(saved, HIWIN_COMMAND_PORT) else "no answer"
        cands[saved] = f"saved in .env, port {HIWIN_COMMAND_PORT} {state}"
    for ip in neighbour_ips():
        if ip not in cands and tcp_port_open(ip, HIWIN_COMMAND_PORT):
            cands[ip] = f"seen on the network (ARP), port {HIWIN_COMMAND_PORT} answers"
    for iface, net in host_networks():
        if net.prefixlen < AUTO_SCAN_MIN_PREFIX:
            print(f"  {iface} {net}: too large to scan automatically, use 's' with a /24 inside it")
            continue
        print(f"  scanning {net} ({iface}) for port {HIWIN_COMMAND_PORT} ...")
        for ip in scan_network(net, HIWIN_COMMAND_PORT):
            cands.setdefault(ip, f"port {HIWIN_COMMAND_PORT} answers on {iface} ({net})")
    for gw in default_gateways() & cands.keys():
        cands[gw] += "  <- this PC's gateway/router, probably not the robot"
    return cands


def print_ip_help() -> None:
    print(f"""
How to find the controller IP
  - On the GC2 teach pendant open the controller's network settings; the IPv4 address
    shown there is the one to enter. run.py remembers it in .env afterwards.
  - The controller listens on TCP port {HIWIN_COMMAND_PORT}. From this PC:
        ping <ip>                 # is it reachable at all?
        nc -zv <ip> {HIWIN_COMMAND_PORT}           # does the HIWIN service answer?
    This menu runs the same probe for every candidate.
  - `ip -4 addr` lists this PC's own networks. The controller is normally on the same
    subnet as the PC's wired interface (PC 192.168.0.5/24 -> scan 192.168.0.0/24 with 's').
  - Robot not listed? It must be powered on, in a mode that accepts external control,
    and on a network this PC can reach. Enter the IP manually with 'c' if you know it.""")
    if is_wsl():
        print("""  - WSL2 (this machine): in the default NAT mode WSL does not see LAN devices by ARP, so
    automatic discovery usually finds nothing. Enter the IP with 'c' or scan the LAN
    subnet explicitly with 's' (e.g. 192.168.0.0/24); TCP through NAT works.""")


def image_exists() -> bool:
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0


def ensure_image() -> bool:
    """Make sure the image exists locally: offer to pull it, then to build it as a fallback."""
    if image_exists():
        return True
    if yes_no(f"Image {IMAGE} not found. Pull it from the registry now?", True):
        if do_pull() == 0:
            return True
        print("Pull failed. If the GHCR package is private, run `docker login ghcr.io` first.")
    if yes_no("Build the image locally instead (takes 10-20 min)?", False):
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
    """Pick the GC2 controller IP from discovered candidates, a manual entry or a subnet scan."""
    print("\nLooking for HIWIN controllers ...")
    cands = find_candidates(cfg)
    while True:
        ips = list(cands)
        print("\nController IP candidates:")
        for i, ip in enumerate(ips, 1):
            print(f"  {i}) {ip:<15} {cands[ip]}")
        if not ips:
            print("  (none found)")
        print("  c) enter an IP manually")
        print("  s) scan a subnet (e.g. 192.168.0.0/24)")
        print("  r) rescan")
        print("  h) how to find the controller IP")
        val = ask("Select (or type an IP)", "1" if ips else "c").lower()
        if val.isdigit() and 1 <= int(val) <= len(ips):
            return ips[int(val) - 1]
        if val == "h":
            print_ip_help()
        elif val == "r":
            cands = find_candidates(cfg)
        elif val == "s":
            text = ask("Subnet to scan (CIDR)", "192.168.0.0/24")
            try:
                net = ipaddress.ip_network(text, strict=False)
            except ValueError:
                print("Not a valid subnet, expected something like 192.168.0.0/24.")
                continue
            if not isinstance(net, ipaddress.IPv4Network) or net.num_addresses > MANUAL_SCAN_MAX_HOSTS:
                print(f"Only IPv4 networks up to {MANUAL_SCAN_MAX_HOSTS} addresses (/22) can be scanned.")
                continue
            print(f"  scanning {net} for port {HIWIN_COMMAND_PORT} ...")
            found = scan_network(net, HIWIN_COMMAND_PORT)
            for ip in found:
                cands.setdefault(ip, f"port {HIWIN_COMMAND_PORT} answers (scan {net})")
            print(f"  {len(found)} host(s) answer on port {HIWIN_COMMAND_PORT}")
        elif val == "c" or valid_ip(val):
            ip = val if valid_ip(val) else ask("Controller IP")
            if not valid_ip(ip):
                print("Not a valid IP address.")
                continue
            if tcp_port_open(ip, HIWIN_COMMAND_PORT):
                print(f"  {ip}: port {HIWIN_COMMAND_PORT} answers.")
                return ip
            print(f"  {ip}: no answer on port {HIWIN_COMMAND_PORT} (robot off, wrong IP or not reachable from here).")
            if yes_no("Use it anyway?", False):
                return ip
        else:
            print("Invalid choice.")


def common_env(cfg: dict[str, str]) -> dict[str, str]:
    """Environment passed to every compose service (see docker-compose.yml)."""
    return {k: cfg[k] for k in ("RA_TYPE", "LAUNCH_RVIZ", "ROS_DOMAIN_ID")}


def show_settings(cfg: dict[str, str], with_ip: bool) -> None:
    ip = f"  IP={cfg['ROBOT_IP'] or 'unset'}" if with_ip else ""
    print(f"\nCurrent settings: type={cfg['RA_TYPE']}{ip}  RViz={cfg['LAUNCH_RVIZ']}")


# ----------------------------------------------------------------- actions
def do_pull() -> int:
    """Fetch the image built by GitHub Actions (also refreshes a stale local copy)."""
    return run(["docker", "pull", IMAGE])


def do_build() -> int:
    """Local fallback for when the registry is unreachable or the Dockerfile is being changed."""
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
    print(f"\nImage {IMAGE}: {'present' if image_exists() else 'not pulled'}")
    return rc


# ----------------------------------------------------------------- menu
MENU = [
    ("0", "Settings (robot type / controller IP / RViz / domain ID)", lambda cfg: do_settings(cfg)),
    ("1", "Simulation (mock hardware + RViz)", lambda cfg: do_sim(cfg)),
    ("2", "Real robot (GC2 cabinet)", lambda cfg: do_robot(cfg)),
    ("3", "Shell inside the container", lambda cfg: do_shell(cfg)),
    ("4", "Pull / update the image (from GHCR)", lambda cfg: do_pull()),
    ("5", "Follow container logs", lambda cfg: do_logs()),
    ("6", "Status", lambda cfg: do_status()),
    ("7", "Stop containers", lambda cfg: do_stop()),
    ("8", "Build the image locally (fallback)", lambda cfg: do_build()),
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
