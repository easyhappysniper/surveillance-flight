"""邮件发送模块 — 优先 Gmail SMTP (国际可用)，QQ邮箱备用"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger("surveillance")

# 环境变量: GMAIL_EMAIL / GMAIL_APP_PASSWORD (推荐，GitHub Actions 可用)
# 或 QQ_EMAIL / QQ_SMTP_CODE (仅中国IP可用)
# 收件人: RECIPIENT_EMAIL (默认 kesijin9@gmail.com)

RECIPIENT = os.getenv("RECIPIENT_EMAIL", "kesijin9@gmail.com")


def send_report(html_body: str, subject: str = "") -> bool:
    """发送 HTML 格式报告邮件，自动选择可用 SMTP"""
    if not subject:
        from datetime import datetime
        subject = f"🛫 北京→巴黎 机票监控 {datetime.now().strftime('%m/%d %H:%M')}"

    # 方案1: Gmail SMTP (国际可用)
    gmail_user = os.getenv("GMAIL_EMAIL", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    if gmail_user and gmail_pass:
        ok = _try_smtp("smtp.gmail.com", 587, gmail_user, gmail_pass, RECIPIENT, html_body, subject, use_tls=True)
        if ok:
            return True

    # 方案2: QQ邮箱 SMTP (仅中国IP)
    qq_user = os.getenv("QQ_EMAIL", "")
    qq_pass = os.getenv("QQ_SMTP_CODE", "")
    if qq_user and qq_pass:
        ok = _try_smtp("smtp.qq.com", 465, qq_user, qq_pass, RECIPIENT, html_body, subject, use_ssl=True)
        if ok:
            return True

    log.error("所有 SMTP 方案均失败，请检查 GMAIL_APP_PASSWORD 或 QQ_SMTP_CODE")
    return False


def _try_smtp(host: str, port: int, user: str, password: str, to: str,
              html: str, subject: str, use_ssl: bool = False, use_tls: bool = False) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            if use_tls:
                server.starttls()
        server.login(user, password)
        server.sendmail(user, [to], msg.as_string())
        server.quit()
        log.info(f"邮件已发送 → {to} (via {host})")
        return True
    except smtplib.SMTPAuthenticationError:
        log.error(f"{host} 认证失败，请检查账号和授权码")
        return False
    except Exception as e:
        log.warning(f"{host}:{port} 发送失败: {e}")
        return False
