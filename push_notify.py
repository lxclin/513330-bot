"""
推送脚本 — 支持 SMTP 邮件（QQ邮箱/163邮箱/Gmail）
配置见 push_config.txt
"""

import sys, os, smtplib, ssl
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "push_config.txt")

# ==================== 读取配置 ====================
def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    return cfg

# ==================== SMTP 邮件推送 ====================
SMTP_DEFAULTS = {
    "smtp.qq.com":        {"port": 465, "ssl": True},
    "smtp.163.com":       {"port": 465, "ssl": True},
    "smtp.gmail.com":     {"port": 587, "ssl": False},  # STARTTLS
}

def send_email(cfg, title, body):
    host = cfg.get("SMTP_HOST", "")
    port = int(cfg.get("SMTP_PORT", 0))
    user = cfg.get("SMTP_USER", "")
    pwd  = cfg.get("SMTP_PASS", "")
    to   = cfg.get("SEND_TO", user)            # 默认发给自己

    if not host or not user or not pwd:
        return False, "SMTP 配置不完整"

    # 自动补全端口和 SSL
    if host in SMTP_DEFAULTS and not port:
        port = SMTP_DEFAULTS[host]["port"]
        use_ssl = SMTP_DEFAULTS[host]["ssl"]
    else:
        use_ssl = (port == 465)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = formataddr(("513330 日报", user))
    msg["To"] = to

    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx) as s:
                s.login(user, pwd)
                s.sendmail(user, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port) as s:
                s.starttls()
                s.login(user, pwd)
                s.sendmail(user, [to], msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)

# ==================== 主逻辑 ====================
MESSAGE = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
if not MESSAGE:
    sys.exit(0)

cfg = load_config()
mode = cfg.get("MODE", "smtp")  # smtp 或 serverchan

if mode == "serverchan":
    # 保留原 Server酱 兼容
    sendkey = cfg.get("SENDKEY", "")
    if not sendkey:
        print("[推送跳过] SendKey 未配置")
        sys.exit(0)
    import requests
    lines = MESSAGE.strip().split("\n")
    title = lines[0].strip()[:80] if lines else "513330 预警"
    body = "\n".join(lines)
    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{sendkey}.send",
            json={"title": title, "desp": body},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            print("[推送成功] Server酱")
        else:
            print(f"[推送失败] {data.get('message', 'unknown')}")
    except Exception as e:
        print(f"[推送异常] {e}")

else:
    # SMTP 邮件
    lines = MESSAGE.strip().split("\n")
    title = lines[0].strip()[:60] if lines else "513330 日报"
    body = MESSAGE.strip()
    ok, err = send_email(cfg, title, body)
    if ok:
        print("[推送成功] 邮件")
    else:
        print(f"[推送失败] {err}")
