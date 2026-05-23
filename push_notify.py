"""
推送脚本 — 支持 SMTP 邮件（QQ邮箱/163邮箱/Gmail）
配置见 push_config.txt
用法: python push_notify.py "消息内容"
      python push_notify.py --file /path/to/output.txt
"""

import sys, os, smtplib, ssl, argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "push_config.txt")


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


SMTP_DEFAULTS = {
    "smtp.qq.com":        {"port": 465, "ssl": True},
    "smtp.163.com":       {"port": 465, "ssl": True},
    "smtp.gmail.com":     {"port": 587, "ssl": False},
}


def send_email(cfg, title, body_html, body_plain=""):
    host = cfg.get("SMTP_HOST", "")
    port = int(cfg.get("SMTP_PORT", 0))
    user = cfg.get("SMTP_USER", "")
    pwd  = cfg.get("SMTP_PASS", "")
    to   = cfg.get("SEND_TO", user)

    if not host or not user or not pwd:
        return False, "SMTP 配置不完整"

    if host in SMTP_DEFAULTS and not port:
        port = SMTP_DEFAULTS[host]["port"]
        use_ssl = SMTP_DEFAULTS[host]["ssl"]
    else:
        use_ssl = (port == 465)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = user
    msg["To"] = to

    if body_plain:
        msg.attach(MIMEText(body_plain.encode("utf-8"), "plain", "utf-8"))
    msg.attach(MIMEText(body_html.encode("utf-8"), "html", "utf-8"))

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


def text_to_html(text):
    """将纯文本转为 HTML，保留格式，emoji 和 box-drawing 字符"""
    import html as _html
    escaped = _html.escape(text)
    return f"""\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family: 'Consolas', 'Monaco', 'Microsoft YaHei', monospace;
             background: #1e1e1e; color: #d4d4d4; padding: 20px; line-height: 1.6;">
<pre style="white-space: pre-wrap; margin: 0; font-size: 14px;">
{escaped}
</pre>
</body></html>"""


def text_summary(text, max_lines=3):
    """提取摘要文本作为 plaintext fallback"""
    lines = text.strip().split("\n")
    return "\n".join(lines[:60])  # 保留足够多行


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("message", nargs="*", help="消息内容")
    parser.add_argument("--file", "-f", help="从文件读取消息内容")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = " ".join(args.message) if args.message else ""

    if not content.strip():
        sys.exit(0)

    cfg = load_config()
    mode = cfg.get("MODE", "smtp")

    from datetime import datetime
    lines = content.strip().split("\n")
    # 取第一行作为标题（去掉 emoji 前缀）
    title = lines[0].strip()
    for prefix in ["🔴 ", "🟡 ", "🟢 "]:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break

    # 根据时间添加时段标签
    hour = datetime.now().hour
    if hour < 12:
        session = "[早盘]"
    elif hour < 15:
        session = "[午盘]"
    else:
        session = "[收盘]"
    title = f"{session} {title[:70]}"

    if mode == "serverchan":
        sendkey = cfg.get("SENDKEY", "")
        if not sendkey:
            print("[推送跳过] SendKey 未配置")
            sys.exit(0)
        import requests
        body_plain = content.strip()
        lines_clean = body_plain.split("\n")
        sc_title = lines_clean[0].strip()[:80] if lines_clean else "513330 预警"
        try:
            resp = requests.post(
                f"https://sctapi.ftqq.com/{sendkey}.send",
                json={"title": sc_title, "desp": body_plain},
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
        body_html = text_to_html(content)
        body_plain = text_summary(content)
        ok, err = send_email(cfg, title, body_html, body_plain)
        if ok:
            print("[推送成功] HTML 邮件")
        else:
            print(f"[推送失败] {err}")


if __name__ == "__main__":
    main()
