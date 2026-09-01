# -*- coding: utf-8 -*-
"""
\u91d1\u80e1\u6768\u6218\u961f\u62db\u65b0\u62a5\u540d - \u817e\u8baf\u4e91\u4e91\u51fd\u6570(SCF)\u63a5\u6536\u7aef

\u529f\u80fd\uff1a\u63a5\u6536\u524d\u7aef POST \u7684\u62a5\u540d\u6570\u636e\uff0c\u6821\u9a8c\u5b66\u53f7\u683c\u5f0f\uff0c
\u9632\u6b62\u540c\u4e00\u5b66\u53f7 1 \u5c0f\u65f6\u5185\u91cd\u590d\u62a5\u540d\uff0c
\u5e76\u901a\u8fc7 QQ \u90ae\u7bb1 SMTP \u53d1\u9001\u901a\u77e5\u90ae\u4ef6\u3002

\u73af\u5883\u53d8\u91cf\uff08\u5728\u4e91\u51fd\u6570\u63a7\u5236\u53f0\u914d\u7f6e\uff09\uff1a
  QQ_MAIL       \u53d1\u4fe1 QQ \u90ae\u7bb1\u5730\u5740\uff08\u5fc5\u586b\uff09
  QQ_AUTH_CODE  QQ \u90ae\u7bb1 SMTP \u6388\u6743\u7801\uff08\u5fc5\u586b\uff0c\u4e0d\u662f\u767b\u5f55\u5bc6\u7801\uff09
  TO_MAIL       \u6536\u4ef6\u90ae\u7bb1\uff08\u53ef\u9009\uff0c\u9ed8\u8ba4\u4e0e QQ_MAIL \u76f8\u540c\uff09

\u90e8\u7f72\u8981\u70b9\uff1a
  1. \u8fd0\u884c\u73af\u5883\u9009 Python 3.6 \u6216\u66f4\u9ad8
  2. \u6267\u884c\u8d85\u65f6\u5efa\u8bae\u8bbe\u4e3a 30 \u79d2\uff08SMTP \u53d1\u9001\u9700\u8981\u65f6\u95f4\uff09
  3. \u521b\u5efa\u300c\u51fd\u6570 URL\u300d\u89e6\u53d1\u5668\uff0c\u9274\u6743\u65b9\u5f0f\u9009\u514d\u9274\u6743
  4. \u65e0\u9700\u5355\u72ec\u914d\u7f6e CORS\uff1a\u672c\u4ee3\u7801\u5df2\u8fd4\u56de\u8de8\u57df\u54cd\u5e94\u5934\u5e76\u5904\u7406 OPTIONS \u9884\u68c0
  5. 1 \u5c0f\u65f6\u91cd\u590d\u6821\u9a8c\u4e3a\u5c3d\u529b\u800c\u4e3a\uff1a\u4e91\u51fd\u6570\u5b9e\u4f8b\u53ef\u80fd\u88ab\u56de\u6536/\u6269\u5bb9\uff0c\u6781\u7aef\u5e76\u53d1\u4e0b\u53ef\u80fd\u6f0f\u5224
"""
import os
import re
import json
import base64
import time
import threading
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SID_HOUR = 3600
SID_FILE = "/tmp/jinyang_sid.json"
SID_RE = re.compile(r"^(200\d|201\d|202\d|203\d|204\d|205\d|2060)\d{6}$")

MSG_INVALID_SID = "\u5b66\u53f7\u683c\u5f0f\u4e0d\u6b63\u786e\uff0810 \u4f4d\u6570\u5b57\uff0c\u524d\u56db\u4f4d\u4e3a\u5165\u5b66\u5e74\u4efd\uff09"
MSG_DUP_SID = "\u8be5\u5b66\u53f71\u5c0f\u65f6\u5185\u5df2\u62a5\u540d\uff0c\u8bf71\u5c0f\u65f6\u540e\u518d\u8bd5"

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

_RECENT = {}
_LOCK = threading.Lock()


def _load_recent():
    global _RECENT
    try:
        with open(SID_FILE, "r", encoding="utf-8") as f:
            _RECENT = json.load(f)
    except Exception:
        _RECENT = {}


def _save_recent():
    try:
        with open(SID_FILE, "w", encoding="utf-8") as f:
            json.dump(_RECENT, f)
    except Exception:
        pass


def _check_dup(sid):
    global _RECENT
    with _LOCK:
        now = time.time()
        _load_recent()
        _RECENT = {k: v for k, v in _RECENT.items() if now - v < SID_HOUR}
        return sid in _RECENT


def _record_sid(sid):
    with _LOCK:
        _RECENT[sid] = time.time()
        _save_recent()


def _load_env(name, default=""):
    return os.environ.get(name, "") or default


def _parse_body(event):
    body = event.get("body", "") or ""
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception:
            body = ""
    body = body.strip()
    if not body:
        return {}
    try:
        if body.startswith("{"):
            return json.loads(body)
        return {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}
    except Exception:
        return {}


def _send_mail(qq_mail, auth_code, to_mail, subject, content):
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("\u91d1\u80e1\u6768\u6218\u961f\u62db\u65b0", qq_mail))
    msg["To"] = to_mail
    server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
    server.login(qq_mail, auth_code)
    server.sendmail(qq_mail, [to_mail], msg.as_string())
    server.quit()


def _ok(data):
    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": CORS,
        "body": json.dumps(data, ensure_ascii=False),
    }


def _fail(message, code=400):
    return {
        "isBase64Encoded": False,
        "statusCode": code,
        "headers": CORS,
        "body": json.dumps({"success": False, "message": message}, ensure_ascii=False),
    }


def main_handler(event, context):
    method = (event.get("httpMethod") or "").upper()
    if method == "OPTIONS":
        return {"isBase64Encoded": False, "statusCode": 200, "headers": CORS, "body": ""}

    qq_mail = _load_env("QQ_MAIL")
    auth_code = _load_env("QQ_AUTH_CODE")
    to_mail = _load_env("TO_MAIL") or qq_mail
    if not qq_mail or not auth_code:
        return _fail("\u670d\u52a1\u7aef\u672a\u914d\u7f6e\u90ae\u7bb1\uff0c\u8bf7\u8054\u7cfb\u7ba1\u7406\u5458", 500)

    data = _parse_body(event)
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    sid = str(data.get("sid", "")).strip()
    college = str(data.get("college", "")).strip()
    org = str(data.get("org", "")).strip()
    intro = str(data.get("intro", "")).strip() or "\u672a\u586b\u5199"
    botcheck = str(data.get("botcheck", "")).strip()
    if botcheck:
        return _ok({"success": True, "message": "ok"})

    if not name or not phone or not sid or not college or not org:
        return _fail("\u5fc5\u586b\u5b57\u6bb5\u7f3a\u5931")

    if not SID_RE.match(sid):
        return _fail(MSG_INVALID_SID, 400)

    if _check_dup(sid):
        return _fail(MSG_DUP_SID, 409)

    content = "\n".join([
        "\u3010\u91d1\u80e1\u6768\u6218\u961f\u62db\u65b0\u62a5\u540d\u3011",
        "\u59d3\u540d\uff1a" + name,
        "\u5b66\u53f7\uff1a" + sid,
        "\u624b\u673a\u53f7\uff1a" + phone,
        "\u5b66\u9662\uff1a" + college,
        "\u610f\u5411\u7ec4\u522b\uff1a" + org,
        "\u81ea\u6211\u4ecb\u7ecd\uff1a" + intro,
    ])
    subject = "\u91d1\u80e1\u6768\u6218\u961f\u62db\u65b0\u62a5\u540d - " + name
    try:
        _send_mail(qq_mail, auth_code, to_mail, subject, content)
    except Exception as exc:
        return _fail("\u90ae\u4ef6\u53d1\u9001\u5931\u8d25\uff1a" + str(exc), 500)

    _record_sid(sid)
    return _ok({"success": True, "message": "ok"})
