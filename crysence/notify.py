"""Pluggable alert backends. Every backend is off until the user configures it
in config.json; nothing here contains any real account, key, or server."""

import os
import json
import time
import base64
import smtplib
import threading
import urllib.request
from email.message import EmailMessage

from .models import logline

_UA = "CrySence/1.0"  # api.resend.com sits behind Cloudflare and 403s a blank UA


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _toast(title, message, image):
    try:
        from winotify import Notification
        icon = image if (image and os.path.exists(image)) else ""
        Notification(app_id="CrySence", title=title, msg=message,
                     icon=icon).show()
    except Exception as e:
        logline("toast failed: " + repr(e))


def _smtp(cfg, title, message, image):
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = cfg.get("from") or cfg.get("user")
    msg["To"] = cfg.get("to")
    msg.set_content(message)
    if image and os.path.exists(image):
        msg.add_attachment(_read(image), maintype="image", subtype="jpeg",
                           filename=os.path.basename(image))
    host, port = cfg["host"], int(cfg.get("port", 587))
    if port == 465:
        srv = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        srv = smtplib.SMTP(host, port, timeout=20)
        if cfg.get("tls", True):
            srv.starttls()
    try:
        if cfg.get("user"):
            srv.login(cfg["user"], cfg.get("password", ""))
        srv.send_message(msg)
    finally:
        srv.quit()


def _ntfy(cfg, title, message, image):
    server = (cfg.get("server") or "https://ntfy.sh").rstrip("/")
    url = f"{server}/{cfg['topic']}"
    headers = {"Title": title, "Message": message, "User-Agent": _UA}
    data = b""
    if image and os.path.exists(image):
        headers["Filename"] = os.path.basename(image)
        data = _read(image)
    else:
        data = message.encode("utf-8")
    if cfg.get("token"):
        headers["Authorization"] = "Bearer " + cfg["token"]
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def _multipart(fields, filefield, filename, filebytes):
    """Build a multipart/form-data body for Telegram sendPhoto."""
    boundary = "----CrySence" + str(int(time.time() * 1000))
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; "
                     f'name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; "
        f'name="{filefield}"; filename="{filename}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n".encode())
    parts.append(filebytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def _telegram(cfg, title, message, image):
    token, chat = cfg["bot_token"], cfg["chat_id"]
    text = f"{title}\n{message}"
    if image and os.path.exists(image):
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        body, boundary = _multipart(
            {"chat_id": chat, "caption": text}, "photo",
            os.path.basename(image), _read(image))
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}",
                   "User-Agent": _UA}
        req = urllib.request.Request(url, data=body, headers=headers,
                                     method="POST")
    else:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = json.dumps({"chat_id": chat, "text": text}).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def _resend(cfg, title, message, image):
    payload = {"from": cfg["from"], "to": [cfg["to"]], "subject": title,
               "text": message}
    if image and os.path.exists(image):
        payload["attachments"] = [{
            "filename": os.path.basename(image),
            "content": base64.b64encode(_read(image)).decode()}]
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=json.dumps(payload).encode(),
        method="POST",
        headers={"Authorization": "Bearer " + cfg["api_key"],
                 "Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


_BACKENDS = {"smtp": _smtp, "ntfy": _ntfy, "telegram": _telegram,
             "resend": _resend}


def _send_all(notif, title, message, image):
    if notif.get("toast", True):
        _toast(title, message, image)
    for name, fn in _BACKENDS.items():
        cfg = notif.get(name) or {}
        if not cfg.get("enabled"):
            continue
        try:
            fn(cfg, title, message, image)
            logline(f"alert sent via {name}")
        except Exception as e:
            logline(f"{name} alert failed: {e!r}")


def send(notif, title, message, image=None):
    """Fire all enabled alert channels on a background thread."""
    threading.Thread(target=_send_all, args=(notif, title, message, image),
                     daemon=True).start()
