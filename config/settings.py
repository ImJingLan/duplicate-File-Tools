"""
应用全局配置模块
"""
import os
import json
import logging
import logging.handlers
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

PATTERNS_FILE = DATA_DIR / "patterns.json"
HISTORY_FILE = DATA_DIR / "history.json"
USER_PREFS_FILE = CONFIG_DIR / "user_preferences.json"

DEFAULT_SCAN_PATHS = []
DEFAULT_SCAN_MIN_SIZE = 0
DEFAULT_SCAN_EXCLUDE_PATTERNS = []

DEFAULT_DEDUP_MODE = "keep_best"
DEFAULT_STAGING_DIR = str(DATA_DIR / "staging")

DEFAULT_OUTPUT_DIR = str(DATA_DIR / "scan_results")

CHUNK_SIZE = 64 * 1024

MAX_HISTORY_RECORDS = 1000


def setup_logging(app_name="gui_dedup", log_level="INFO", log_to_file=True,
                  log_to_console=True, max_bytes=10 * 1024 * 1024, backup_count=5):
    """
    配置日志系统

    Args:
        app_name: 应用名称，用于日志记录器命名
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否输出到文件
        log_to_console: 是否输出到控制台
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的历史日志文件数
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        console_handler.setFormatter(fmt)
        root_logger.addHandler(console_handler)

    if log_to_file:
        app_log_path = LOGS_DIR / "app.log"
        file_handler = logging.handlers.RotatingFileHandler(
            str(app_log_path), maxBytes=max_bytes, backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)

        error_log_path = LOGS_DIR / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            str(error_log_path), maxBytes=max_bytes, backupCount=backup_count,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(fmt)
        root_logger.addHandler(error_handler)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return root_logger


def load_user_preferences():
    """加载用户偏好设置"""
    defaults = {
        "scan_paths": DEFAULT_SCAN_PATHS,
        "min_size": DEFAULT_SCAN_MIN_SIZE,
        "exclude_patterns": DEFAULT_SCAN_EXCLUDE_PATTERNS,
        "dedup_mode": DEFAULT_DEDUP_MODE,
        "staging_dir": DEFAULT_STAGING_DIR,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "language": "zh_CN",
        "theme": "light",
    }
    if USER_PREFS_FILE.exists():
        try:
            with open(USER_PREFS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
        except (json.JSONDecodeError, IOError):
            pass
    return defaults


def save_user_preferences(prefs):
    """保存用户偏好设置"""
    USER_PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)
