"""航班监控系统 — 配置中心"""

# ---- 搜索目标 ----
ORIGIN_AIRPORTS = ["PEK", "PKX"]       # 北京首都 + 大兴
DEST_AIRPORTS = ["CDG", "ORY"]         # 巴黎戴高乐 + 奥利
DATES = ["2026-08-12", "2026-08-13", "2026-08-14"]
MAX_STOPS = 1
ADULTS = 1
MAX_RESULTS = 10            # 每个日期返回前N名

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

# ---- 紧急提醒阈值 (CNY) ----
URGENT_THRESHOLD = 3600
MAX_RESULTS = 15

# ---- 中转签证政策 (中国护照 + 申根学生签) ----
TRANSIT_POLICY = {
    "ICN": "免签(持申根)", "PUS": "免签(持申根)",
    "NRT": "过境签ShorePass", "HND": "过境签ShorePass", "KIX": "过境签",
    "IST": "免签", "SAW": "免签",
    "DXB": "免签", "AUH": "免签", "DOH": "免签",
    "ADD": "落地签免费", "CAI": "⚠可能需过境签",
    "LHR": "⚠需DATV过境签", "LGW": "⚠需过境签",
    "HEL": "申根✅", "CDG": "申根✅", "AMS": "申根✅", "FRA": "申根✅",
    "MUC": "申根✅", "ZRH": "申根✅", "VIE": "申根✅", "MAD": "申根✅",
    "BCN": "申根✅", "FCO": "申根✅", "MXP": "申根✅", "CPH": "申根✅",
    "OSL": "申根✅", "ARN": "申根✅", "BRU": "申根✅", "PRG": "申根✅",
    "SVO": "⚠需过境签", "DME": "⚠需过境签",
    "TPE": "需入台证", "HKG": "免签", "PVG": "国内转",
    "PEK": "国内转", "PKX": "国内转", "CAN": "国内转",
    "CTU": "国内转", "SZX": "国内转", "XMN": "国内转", "SHA": "国内转",
    "EWR": "⚠需C1过境签", "JFK": "⚠需C1过境签", "LAX": "⚠需C1过境签",
    "YVR": "⚠需过境签", "YYZ": "⚠需过境签",
    "SIN": "免签", "KUL": "免签", "BKK": "免签", "DMK": "免签",
    "MNL": "免签转机区", "CGK": "免签",
    "ALA": "免签", "TAS": "免签",
    "UBN": "免签", "FRU": "免签",
    "TLV": "⚠可能需过境签",
}

def get_transit_policy(airport_code: str) -> str:
    return TRANSIT_POLICY.get(airport_code.upper(), "需核实")

# ---- 行李额度 (经济舱，国际航线) ----
BAGGAGE = {
    "TK": "30kg", "CA": "2x23kg", "MU": "2x23kg", "CZ": "2x23kg",
    "HU": "2x23kg", "3U": "2x23kg", "MF": "2x23kg",
    "AF": "1x23kg", "KL": "1x23kg", "LH": "1x23kg",
    "EK": "25kg", "EY": "23kg", "QR": "25kg",
    "SQ": "25kg", "TG": "25kg", "BR": "2x23kg",
    "LX": "1x23kg", "OS": "1x23kg",
    "UA": "1x23kg", "DL": "1x23kg", "AA": "1x23kg",
    "BA": "1x23kg", "VS": "1x23kg",
    "SU": "2x23kg", "SV": "23kg",
}

def get_baggage(airline_code: str) -> str:
    return BAGGAGE.get(airline_code.upper(), "待查")

# ---- 邮件配置 (QQ邮箱 SMTP) ----
# 通过环境变量设置: QQ_EMAIL / QQ_SMTP_CODE
# QQ邮箱 → 设置 → 账户 → POP3/IMAP/SMTP服务 → 生成授权码
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
RECIPIENT_EMAIL = "kesijin9@gmail.com"
