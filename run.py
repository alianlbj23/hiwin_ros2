#!/usr/bin/env python3
"""HIWIN RA6 Docker 啟動器（純選單，不需要參數）。

    ./run.py

選過的型號 / IP / RViz 設定會記在 .env，下次按 Enter 就沿用。
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
    ask("\n按 Enter 回到選單")


def run(cmd: list[str], env: dict | None = None) -> int:
    shown = " ".join(f"{k}={v}" for k, v in (env or {}).items())
    print(f"\n$ {shown} {' '.join(cmd)}".replace("$  ", "$ "))
    try:
        return subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}).returncode
    except KeyboardInterrupt:
        print("\n已中斷。")
        return 130


def compose() -> list[str]:
    if shutil.which("docker") is None:
        sys.exit("錯誤: 找不到 docker，請先安裝 Docker Engine。")
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    sys.exit("錯誤: 找不到 docker compose。")


def load_env() -> dict[str, str]:
    cfg = dict(DEFAULTS)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.split("#", 1)[0].strip()
    return cfg


def save_env(cfg: dict[str, str]) -> None:
    lines = ["# 由 run.py 維護；也可手動編輯。"]
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
    if image_exists():
        return True
    if yes_no(f"找不到映像檔 {IMAGE}，現在建置嗎（約 10-20 分鐘）?", True):
        return do_build() == 0
    print("沒有映像檔無法啟動。")
    return False


def allow_x11() -> None:
    if not os.environ.get("DISPLAY"):
        print("提示: 沒有 DISPLAY，RViz 不會顯示。")
    elif shutil.which("xhost"):
        subprocess.run(["xhost", "+local:root"], capture_output=True)
    else:
        print("提示: 找不到 xhost，若 RViz 無法開窗請手動執行 `xhost +local:root`。")


# ----------------------------------------------------------------- prompts
def choose_ra_type(cfg: dict[str, str]) -> str:
    print("\n手臂型號:")
    for i, t in enumerate(RA_TYPES, 1):
        mark = "  <- 上次" if t == cfg["RA_TYPE"] else ""
        print(f"  {i}) {t}{mark}")
    while True:
        val = ask("選擇", cfg["RA_TYPE"])
        if val.isdigit() and 1 <= int(val) <= len(RA_TYPES):
            return RA_TYPES[int(val) - 1]
        if val in RA_TYPES:
            return val
        print("無效選項。")


def choose_ip(cfg: dict[str, str]) -> str:
    while True:
        val = ask("HIWIN 控制器 (GC2) IP", cfg["ROBOT_IP"])
        if valid_ip(val):
            return val
        print("IP 格式不對，請重新輸入。")


def common_env(cfg: dict[str, str]) -> dict[str, str]:
    return {k: cfg[k] for k in ("RA_TYPE", "LAUNCH_RVIZ", "ROS_DOMAIN_ID")}


# ----------------------------------------------------------------- actions
def do_build() -> int:
    return run(["docker", "build", "-t", IMAGE, "."])


def do_sim(cfg: dict[str, str]) -> int:
    if not ensure_image():
        return 1
    cfg["RA_TYPE"] = choose_ra_type(cfg)
    cfg["LAUNCH_RVIZ"] = "true" if yes_no("開啟 RViz?", cfg["LAUNCH_RVIZ"] == "true") else "false"
    save_env(cfg)
    if cfg["LAUNCH_RVIZ"] == "true":
        allow_x11()
    print("\n啟動模擬，Ctrl+C 結束。")
    return run(compose() + ["up", "sim"], common_env(cfg))


def do_robot(cfg: dict[str, str]) -> int:
    if not ensure_image():
        return 1
    cfg["RA_TYPE"] = choose_ra_type(cfg)
    cfg["ROBOT_IP"] = choose_ip(cfg)
    cfg["LAUNCH_RVIZ"] = "true" if yes_no("開啟 RViz?", cfg["LAUNCH_RVIZ"] == "true") else "false"
    save_env(cfg)
    print(f"\n⚠️  即將連線真實機械手臂  型號={cfg['RA_TYPE']}  IP={cfg['ROBOT_IP']}")
    print("    請確認周圍安全、急停可用，MoveIt 預設速度縮放 0.1。")
    if not yes_no("繼續?", False):
        print("已取消。")
        return 0
    if cfg["LAUNCH_RVIZ"] == "true":
        allow_x11()
    print("\n啟動真機，Ctrl+C 結束。")
    return run(compose() + ["up", "robot"], {**common_env(cfg), "ROBOT_IP": cfg["ROBOT_IP"]})


def do_shell(cfg: dict[str, str]) -> int:
    if not ensure_image():
        return 1
    allow_x11()
    print("\n容器內已 source workspace，輸入 exit 離開。")
    return run(compose() + ["run", "--rm", "shell"], common_env(cfg))


def do_logs() -> int:
    print("\nCtrl+C 結束查看。")
    return run(compose() + ["logs", "-f", "--tail", "200"])


def do_stop() -> int:
    return run(compose() + ["down", "--remove-orphans"])


def do_status() -> int:
    rc = run(compose() + ["ps"])
    print(f"\n映像檔 {IMAGE}: {'已建置' if image_exists() else '尚未建置'}")
    return rc


# ----------------------------------------------------------------- menu
MENU = [
    ("1", "模擬 (mock hardware + RViz)", lambda cfg: do_sim(cfg)),
    ("2", "真機 (GC2 cabinet)", lambda cfg: do_robot(cfg)),
    ("3", "進入容器 shell", lambda cfg: do_shell(cfg)),
    ("4", "建置 / 重建映像檔", lambda cfg: do_build()),
    ("5", "查看容器 log", lambda cfg: do_logs()),
    ("6", "狀態", lambda cfg: do_status()),
    ("7", "停止容器", lambda cfg: do_stop()),
]


def main() -> None:
    os.chdir(ROOT)
    while True:
        cfg = load_env()
        print("\n========== HIWIN RA6 Docker 啟動器 ==========")
        print(f" 目前設定: 型號={cfg['RA_TYPE']}  IP={cfg['ROBOT_IP'] or '未設定'}  RViz={cfg['LAUNCH_RVIZ']}")
        for key, label, _ in MENU:
            print(f"  {key}) {label}")
        print("  q) 離開")
        choice = ask("選擇").lower()
        if choice in ("q", "quit", "exit"):
            return
        for key, _, action in MENU:
            if choice == key:
                action(cfg)
                pause()
                break
        else:
            print("無效選項。")


if __name__ == "__main__":
    main()
