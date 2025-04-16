"""Telegram Transfer

一个基于Telethon的Telegram文件传输工具，支持文件夹上传、下载和同步功能。
"""

from .cli import cli
from .client import TelegramTransferClient

__version__ = "0.0.0"  # 这个版本号会被 CI 动态更新
__all__ = ["TelegramTransferClient", "cli"]
