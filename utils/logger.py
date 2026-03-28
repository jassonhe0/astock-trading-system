# -*- coding: utf-8 -*-
"""统一日志配置 —— loguru 可用则用，否则降级标准 logging"""
import sys
import logging
from pathlib import Path


def _std_logger():
    logger = logging.getLogger("astockanalysis")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    try:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        fh = logging.FileHandler(log_dir / "system.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


try:
    from loguru import logger as _loguru
    # 确认是真实loguru，不是mock
    _loguru.remove()
    _USE_LOGURU = True
except Exception:
    _USE_LOGURU = False

if _USE_LOGURU:
    try:
        from utils.config_loader import get
        level = get("logging.level", "INFO")
        log_dir = Path(get("logging.path", "logs/"))
        log_dir.mkdir(parents=True, exist_ok=True)
        _loguru.add(
            sys.stdout,
            level=level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> - {message}",
            colorize=True,
        )
        _loguru.add(
            str(log_dir / "system_{time:YYYY-MM-DD}.log"),
            level=level,
            rotation=get("logging.rotation", "1 day"),
            retention=get("logging.retention", "30 days"),
            encoding="utf-8",
        )
        log = _loguru
    except Exception:
        log = _std_logger()
else:
    log = _std_logger()
