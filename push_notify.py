import sys
import os
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "push_config.txt")

SENDKEY = ""
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                SENDKEY = line.split("=")[-1].strip()
                break

MESSAGE = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
if not MESSAGE:
    sys.exit(0)
if not SENDKEY:
    print("[推送跳过] SendKey 未配置")
    sys.exit(0)

lines = MESSAGE.strip().split("\n")
title = lines[0].strip()[:80] if lines else "513330 预警"
body  = "\n".join(lines)

try:
    resp = requests.post(
        f"https://sctapi.ftqq.com/{SENDKEY}.send",
        json={"title": title, "desp": body},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") == 0:
        print("[推送成功] Server酱")
    else:
        print(f"[推送失败] {data.get('message', 'unknown')}")
except Exception as e:
    print(f"[推送异常] {e}")
