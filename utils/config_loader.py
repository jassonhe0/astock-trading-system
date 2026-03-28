# -*- coding: utf-8 -*-
"""配置管理器 - 加载 config.yaml / config.local.yaml"""
import os
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).parent.parent


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> dict:
    base_path = _ROOT / "config.yaml"
    local_path = _ROOT / "config.local.yaml"
    with open(base_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, local)
    # 环境变量覆盖
    if ts_token := os.getenv("TUSHARE_TOKEN"):
        cfg.setdefault("data", {}).setdefault("tushare", {})["token"] = ts_token
    if broker_pwd := os.getenv("BROKER_PASSWORD"):
        cfg.setdefault("broker", {})["password"] = broker_pwd
    return cfg


# 单例
_config: dict | None = None


def get_config() -> dict:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get(key_path: str, default: Any = None) -> Any:
    """点分路径访问，如 get('risk.stop_loss_ratio')"""
    cfg = get_config()
    keys = key_path.split(".")
    val = cfg
    for k in keys:
        if not isinstance(val, dict):
            return default
        val = val.get(k, default)
    return val
