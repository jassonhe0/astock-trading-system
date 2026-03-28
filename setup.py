#!/usr/bin/env python3
"""
项目初始化脚本 - 创建所有必要目录和初始文件
运行: python setup.py
"""
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

DIRS = [
    "data",
    "data/cache",
    "logs",
    "strategies",
    "backtest_results",
    "core",
    "broker",
    "ui",
    "utils",
]

def create_structure():
    print("🚀 初始化 A股量化交易系统目录结构...")
    for d in DIRS:
        path = PROJECT_ROOT / d
        path.mkdir(parents=True, exist_ok=True)
        init_file = path / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# -*- coding: utf-8 -*-\n")
        print(f"  ✅ {d}/")

    # 复制配置文件
    config_src = PROJECT_ROOT / "config.yaml"
    config_local = PROJECT_ROOT / "config.local.yaml"
    if not config_local.exists() and config_src.exists():
        shutil.copy(config_src, config_local)
        print("  ✅ config.local.yaml (请填入你的账户信息)")

    # 创建 .env
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        env_file.write_text(
            "# 环境变量\nTUSHARE_TOKEN=\nBROKER_PASSWORD=\n"
        )
        print("  ✅ .env")

    print("\n✨ 初始化完成！")
    print("📋 下一步:")
    print("   1. 编辑 config.local.yaml，填入同花顺账号密码")
    print("   2. pip install -r requirements.txt")
    print("   3. python main.py --help")

if __name__ == "__main__":
    create_structure()
