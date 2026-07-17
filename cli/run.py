#!/usr/bin/env python3
"""Orvibo 局域网控制 CLI 入口（跨平台）
直接 python run.py list 即可使用
"""
import sys
import os
import importlib.util

# 确保能找到同目录模块
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

if __name__ == "__main__":
    import asyncio
    from main import main
    asyncio.run(main())
