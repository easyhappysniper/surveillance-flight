"""邮件发送模块 — QQ邮箱 SMTP"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger("surveillance")

# 从环境变量读取配置
SMTP_HOST = os.getenv("QQ_SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("QQ_SMTP_PORT", "465"))
SENDER = os.getenv("QQ_EMAIL", "")
PASSWORD = os.getenv("QQ_SMTP_CODE", "")
RECIPIENT = os.getenv("RECIPIENT_EMAIL", "kesijin9@gmail.com")


def send_report(html_body: str, subject: str = "") -> bool:
    """发送 HTML 格式报告邮件"""
    if not SENDER or not PASSWORD:
        log.error("未配置 QQ_EMAIL / QQ_SMTP_CODE 环境变量，跳过邮件发送")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject or "🛫 航班价格监控报告"
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 尝试 SSL (465) 和 TLS (587)
    for use_ssl in [True, False]:
        port = SMTP_PORT if use_ssl else 587
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(SMTP_HOST, port, timeout=15)
            else:
                server = smtplib.SMTP(SMTP_HOST, port, timeout=15)
                server.starttls()
            server.login(SENDER, PASSWORD)
            server.sendmail(SENDER, [RECIPIENT], msg.as_string())
            server.quit()
            log.info(f"邮件已发送 → {RECIPIENT} (port {port})")
            return True
        except smtplib.SMTPAuthenticationError:
            log.error("QQ邮箱认证失败，请检查 QQ_EMAIL / QQ_SMTP_CODE 是否正确")
            return False
        except Exception as e:
            if use_ssl:
                log.warning(f"SMTP port {port} 失败: {e}，尝试 587...")
            else:
                log.error(f"邮件发送失败 (port {port}): {e}")
                return False
