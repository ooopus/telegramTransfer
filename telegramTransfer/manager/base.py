"""FileTransferManager基类实现"""

import os
import json
from datetime import datetime
from typing import Dict, Any

from loguru import logger
from tqdm import tqdm

from ..client import TelegramTransferClient
from .upload import UploadMixin
from .download import DownloadMixin
from .sync import SyncMixin

class FileTransferManager(UploadMixin, DownloadMixin, SyncMixin):
    """文件传输管理器
    
    处理文件夹级别的传输操作，包括：
    - 文件夹上传
    - 文件夹下载
    - 文件夹同步
    - 断点续传
    - 进度追踪
    """
    
    def __init__(self, client: TelegramTransferClient):
        """初始化传输管理器
        
        Args:
            client: TelegramTransferClient实例
        """
        self.client = client
        self.state = {}  # 直接使用内存字典存储状态
        
    def _get_transfer_key(self, folder_path: str, target: str) -> str:
        """生成传输任务的唯一标识"""
        return f"{folder_path}:{target}"
        
    def _create_progress_callback(self, desc: str, total: int, overall_progress=None):
        """创建进度回调函数
        
        Args:
            desc: 进度条描述
            total: 文件总大小
            overall_progress: 总体进度条对象
        """
        pbar = tqdm(total=total, desc=desc, unit='B', unit_scale=True)
        last_value = [0]
        
        def callback(current, total):
            update_size = current - last_value[0]
            pbar.update(update_size)
            if overall_progress:
                overall_progress.update(update_size)
            last_value[0] = current
            
        return callback