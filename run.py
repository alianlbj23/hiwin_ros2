#!/usr/bin/env python3
"""HIWIN RA6 Docker 啟動器：不用背 docker 指令。

用法：
  ./run.py                 互動選單
  ./run.py sim             mock hardware + RViz
  ./run.py robot           真機（GC2 cabinet，需要 IP）
  ./run.py robot --ip 192.168.0.1 --ra-type ra610_1476
  ./run.py shell           進入容器 bash（已 source workspace）
  ./run.py build           建置映像檔
  ./run.py stop            停止並移除容器
  ./run.py <cmd> --dry-run 只印出會執行的指令

真機 IP 來源順序：--ip > 環境變數 ROBOT_IP > .env 檔 > 互動輸入。
"""
import argparse
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
DEFAULT_RA_TYPE = "ra610_1476"


def die(msg: str, code: int = 1) -> None:
    print(f"錯誤: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], dry_run: bool, env: dict | None = None, check: bool = True) -> int:
    shown = " ".join(cmd)
    if env:
        shown = " ".join(f"{k}={v}" for k, v in env.items()) + " " + shown
    print(f"$ {shown}")
    if dry_run:
        return 0
    full_env = {**os.environ, **(env or {})}
    try:
        return subprocess.run(cmd, cwd=ROOT, env=full_env, check=check).returncode
    except subprocess.CalledProcessError as e:
        return e.returncode
    except KeyboardInterrupt:
        print("\n已中斷。")
        return 130


def compose_cmd() -> list[str]:
    if shutil.which("docker") is None:
        die("找不到 docker，請先安裝 Docker Engine。")
    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if probe.returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    die("找不到 docker compose plugin，也沒有 docker-compose。")


def read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.split("#", 1)[0].strip()
    return values


def write_env_value(key: str, value: str) -> None:
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    out, found = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n")
    print(f"已寫入 {ENV_FILE.name}: {key}={value}")


def valid_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False


def resolve_robot_ip(arg_ip: str | None, dry_run: bool) -> str:
    candidates = [arg_ip, os.environ.get("ROBOT_IP"), read_env_file().get("ROBOT_IP")]
    for ip in candidates:
        if ip and valid_ip(ip):
            return ip
        if ip:
            print(f"忽略無效的 IP: {ip}")
    if dry_run:
        return "0.0.0.0"
    while True:
        ip = input("請輸入 HIWIN 控制器 (GC2) 的 IP: ").strip()
        if valid_ip(ip):
            save = input("要存到 .env 下次直接用嗎? [Y/n] ").strip().lower()
            if save in ("", "y", "yes"):
                write_env_value("ROBOT_IP", ip)
            return ip
        print("格式不對，請重新輸入。")


def image_exists() -> bool:
    r = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True)
    return r.returncode == 0


def ensure_image(dry_run: bool) -> None:
    if dry_run or image_exists():
        return
    ans = input(f"找不到映像檔 {IMAGE}，現在建置嗎（約 10-20 分鐘）? [Y/n] ").strip().lower()
    if ans in ("", "y", "yes"):
        if cmd_build(dry_run) != 0:
            die("建置失敗。")
    else:
        die("沒有映像檔無法啟動。")


def allow_x11(dry_run: bool) -> None:
    if not os.environ.get("DISPLAY"):
        print("提示: 沒有 DISPLAY，RViz 不會顯示。要無頭執行請加 --no-rviz。")
        return
    if shutil.which("xhost") is None:
        print("提示: 找不到 xhost，若 RViz 無法開窗請手動執行 `xhost +local:root`。")
        return
    run(["xhost", "+local:root"], dry_run, check=False)


def common_env(args) -> dict[str, str]:
    env = {
        "RA_TYPE": args.ra_type,
        "LAUNCH_RVIZ": "false" if args.no_rviz else "true",
        "ROS_DOMAIN_ID": str(args.domain_id),
    }
    return env


def cmd_build(dry_run: bool) -> int:
    return run(["docker", "build", "-t", IMAGE, "."], dry_run)


def cmd_sim(args) -> int:
    ensure_image(args.dry_run)
    if not args.no_rviz:
        allow_x11(args.dry_run)
    return run(compose_cmd() + ["up", "sim"], args.dry_run, env=common_env(args), check=False)


def cmd_robot(args) -> int:
    ensure_image(args.dry_run)
    ip = resolve_robot_ip(args.ip, args.dry_run)
    if not args.no_rviz:
        allow_x11(args.dry_run)
    env = {**common_env(args), "ROBOT_IP": ip}
    print(f"\n⚠️  即將連線真實機械手臂  型號={args.ra_type}  IP={ip}")
    print("    請確認周圍安全、急停可用，MoveIt 預設速度縮放 0.1。")
    if not args.dry_run and not args.yes:
        if input("繼續? [y/N] ").strip().lower() not in ("y", "yes"):
            print("已取消。")
            return 0
    return run(compose_cmd() + ["up", "robot"], args.dry_run, env=env, check=False)


def cmd_shell(args) -> int:
    ensure_image(args.dry_run)
    allow_x11(args.dry_run)
    return run(compose_cmd() + ["run", "--rm", "shell"], args.dry_run, env=common_env(args), check=False)


def cmd_stop(args) -> int:
    return run(compose_cmd() + ["down", "--remove-orphans"], args.dry_run, check=False)


def interactive(parser: argparse.ArgumentParser) -> list[str]:
    print("HIWIN RA6 Docker 啟動器")
    print("  1) 模擬 (mock hardware + RViz)")
    print("  2) 真機 (GC2 cabinet)")
    print("  3) 進入容器 shell")
    print("  4) 建置映像檔")
    print("  5) 停止容器")
    print("  q) 離開")
    choice = input("選擇: ").strip().lower()
    mapping = {"1": "sim", "2": "robot", "3": "shell", "4": "build", "5": "stop"}
    if choice in ("q", "quit", ""):
        sys.exit(0)
    if choice not in mapping:
        die("無效選項。")
    argv = [mapping[choice]]
    if choice in ("1", "2"):
        default = DEFAULT_RA_TYPE
        print("手臂型號: " + "  ".join(f"[{i+1}] {t}" for i, t in enumerate(RA_TYPES)))
        sel = input(f"選擇型號 (Enter = {default}): ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(RA_TYPES):
            argv += ["--ra-type", RA_TYPES[int(sel) - 1]]
        elif sel in RA_TYPES:
            argv += ["--ra-type", sel]
    return argv


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    def add_common(sp):
        sp.add_argument("--ra-type", choices=RA_TYPES, default=DEFAULT_RA_TYPE, help=f"手臂型號 (預設 {DEFAULT_RA_TYPE})")
        sp.add_argument("--no-rviz", action="store_true", help="不開 RViz")
        sp.add_argument("--domain-id", type=int, default=int(os.environ.get("ROS_DOMAIN_ID", "0")), help="ROS_DOMAIN_ID")
        sp.add_argument("--dry-run", action="store_true", help="只印指令不執行")

    sp = sub.add_parser("sim", help="mock hardware")
    add_common(sp)
    sp.set_defaults(func=cmd_sim)

    sp = sub.add_parser("robot", help="真機 (GC2)")
    add_common(sp)
    sp.add_argument("--ip", help="控制器 IP (否則讀 ROBOT_IP / .env / 互動輸入)")
    sp.add_argument("-y", "--yes", action="store_true", help="跳過安全確認")
    sp.set_defaults(func=cmd_robot)

    sp = sub.add_parser("shell", help="進入容器 bash")
    add_common(sp)
    sp.set_defaults(func=cmd_shell)

    sp = sub.add_parser("build", help="建置映像檔")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=lambda a: cmd_build(a.dry_run))

    sp = sub.add_parser("stop", help="停止容器")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=cmd_stop)
    return p


def main() -> None:
    parser = build_parser()
    argv = sys.argv[1:] or interactive(parser)
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        sys.exit(1)
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
