# -*- coding: utf-8 -*-
"""
金胡杨战队招新报名 - 腾讯云云函数(SCF)接收端

功能：接收前端 POST 的报名数据，校验学号格式，
防止同一学号 1 小时内重复报名，
并通过 QQ 邮箱 SMTP 发送通知邮件。

环境变量（在云函数控制台配置）：
  QQ_MAIL       发信 QQ 邮箱地址（必填）
  QQ_AUTH_CODE  QQ 邮箱 SMTP 授权码（必填，不是登录密码）
  TO_MAIL       收件邮箱（可选，默认与 QQ_MAIL 相同）

部署要点：
  1. 运行环境选 Python 3.6 或更高
  2. 执行超时建议设为 30 秒（SMTP 发送需要时间）
  3. 创建「函数 URL」触发器，鉴权方式选免鉴权
  4. 无需单独配置 CORS：本代码已返回跨域响应头并处理 OPTIONS 预检
  5. 1 小时重复校验为尽力而为：云函数实例可能被回收/扩容，极端并发下可能漏判
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

MSG_INVALID_SID = "学号格式不正确（10 位数字，前四位为入学年份）"
MSG_DUP_SID = "该学号1小时内已报名，请1小时后再试"

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
    msg["From"] = formataddr(("金胡杨战队招新", qq_mail))
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
        return _fail("服务端未配置邮箱，请联系管理员", 500)

    data = _parse_body(event)
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    sid = str(data.get("sid", "")).strip()
    college = str(data.get("college", "")).strip()
    org = str(data.get("org", "")).strip()
    intro = str(data.get("intro", "")).strip() or "未填写"
    botcheck = str(data.get("botcheck", "")).strip()
    if botcheck:
        return _ok({"success": True, "message": "ok"})

    if not name or not phone or not sid or not college or not org:
        return _fail("必填字段缺失")

    if not SID_RE.match(sid):
        return _fail(MSG_INVALID_SID, 400)

    if _check_dup(sid):
        return _fail(MSG_DUP_SID, 409)

    content = "\n".join([
        "【金胡杨战队招新报名】",
        "姓名：" + name,
        "学号：" + sid,
        "手机号：" + phone,
        "学院：" + college,
        "意向组别：" + org,
        "自我介绍：" + intro,
    ])
    subject = "金胡杨战队招新报名 - " + name
    try:
        _send_mail(qq_mail, auth_code, to_mail, subject, content)
    except Exception as exc:
        return _fail("邮件发送失败：" + str(exc), 500)

    _record_sid(sid)
    return _ok({"success": True, "message": "ok"})
