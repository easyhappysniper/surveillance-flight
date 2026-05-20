"""航班监控系统 — 配置中心"""

# ---- 搜索目标 ----
ORIGIN_AIRPORTS = ["PEK", "PKX"]       # 北京首都 + 大兴
DEST_AIRPORTS = ["CDG", "ORY"]         # 巴黎戴高乐 + 奥利
DATES = ["2026-08-12", "2026-08-13", "2026-08-14"]
MAX_STOPS = 1
BUDGET_CNY = 4000
ADULTS = 1

# ---- 搜索引擎优先级 ----
# "letsfg" 在国内可直接用，"fli" 需 VPN
ENGINES = ["letsfg", "fli"]

# ---- 搜索参数 ----
SEARCH_DELAY = 2.0         # 每次搜索间隔秒数，避免限流
MAX_RETRIES = 2            # 单次搜索最大重试
RETRY_BACKOFF = [1, 2]     # 重试退避秒数
SEARCH_TIMEOUT = 120       # 单次搜索超时秒数

# ---- 货币换算 (到 CNY) ----
CURRENCY_RATES = {
    "CNY": 1.0,
    "RMB": 1.0,
    "USD": 7.25,
    "EUR": 7.85,
    "GBP": 9.20,
    "HKD": 0.93,
    "JPY": 0.048,
    "KRW": 0.0054,
    "IDR": 0.00046,
    "THB": 0.20,
    "SGD": 5.40,
    "AED": 1.97,
    "QAR": 1.99,
    "SAR": 1.93,
    "INR": 0.087,
    "ZAR": 0.39,
    "MYR": 1.56,
    "PHP": 0.13,
    "VND": 0.00029,
    "TWD": 0.23,
}

# ---- 航班来源标识 ----
# LetsFG 返回结果中 airlines 字段映射
AIRLINE_NAMES = {
    "MU": "中国东航", "CZ": "中国南航", "CA": "中国国航",
    "HU": "海南航空", "3U": "四川航空", "MF": "厦门航空",
    "AF": "法国航空", "KL": "荷兰皇家航空", "LH": "汉莎航空",
    "TK": "土耳其航空", "EK": "阿联酋航空", "EY": "阿提哈德航空",
    "QR": "卡塔尔航空", "SV": "沙特航空", "SU": "俄罗斯航空",
    "BA": "英国航空", "LX": "瑞士航空", "OS": "奥地利航空",
    "SK": "北欧航空", "AY": "芬兰航空", "AZ": "意大利航空",
}

# ---- 存档与日志 ----
ARCHIVE_DIR = "archive"
LOG_DIR = "logs"
TIMEZONE = "Asia/Shanghai"

# ---- 报告时段 (北京时间) ----
REPORT_HOURS = [8, 12, 20]

# ---- 邮件配置 (QQ邮箱 SMTP) ----
# 通过环境变量设置: QQ_EMAIL / QQ_SMTP_CODE
# QQ邮箱 → 设置 → 账户 → POP3/IMAP/SMTP服务 → 生成授权码
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
RECIPIENT_EMAIL = "kesijin9@gmail.com"
