"""下载相关功能实现"""

import os
import json
from typing import Dict, Any
from datetime import datetime

from loguru import logger
from tqdm import tqdm

class DownloadMixin:
    """下载功能Mixin类"""
    
    async def download_folder(self,
                            source: str,
                            download_path: str,
                            limit: int = None) -> Dict[str, Any]:
        """下载文件夹"""
        download_path = os.path.expanduser(download_path)
        os.makedirs(download_path, exist_ok=True)
        
        # 获取所有文件消息
        entity = await self.client.get_entity_by_id_or_username(source)
        messages = await self.client.get_file_messages(entity, limit)
        
        if not messages:
            logger.warning("没有找到文件消息")
            return {'success': [], 'failed': []}
        
        # 计算总大小
        total_size = sum(message.file.size for message in messages if message.file)
        overall_progress = tqdm(
            total=total_size,
            desc="总体进度",
            unit='B',
            unit_scale=True,
            position=0
        )
        
        transfer_key = self._get_transfer_key(source, download_path)
        downloaded = self.state.get(transfer_key, {}).get('downloaded', [])
        
        success = []
        failed = []
        
        for message in messages:
            if not message.file:
                continue
                
            try:
                file_name = await self._download_single_file(
                    message, download_path, downloaded, transfer_key
                )
                success.append(file_name)
                
            except Exception as e:
                logger.error(f"下载失败 {message.file.name}: {str(e)}")
                failed.append(message.file.name)
                
        return {'success': success, 'failed': failed}
        
    async def _download_single_file(self, message, download_path, downloaded, transfer_key):
        """下载单个文件"""
        metadata = None
        if message.message:
            try:
                metadata = json.loads(message.message)
            except json.JSONDecodeError:
                pass
                
        if metadata and 'original_path' in metadata:
            file_name = metadata['original_path']
            file_path = os.path.join(download_path, file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
        else:
            file_name = message.file.name or f"file_{message.id}"
            file_path = os.path.join(download_path, file_name)
            
        if file_name in downloaded:
            logger.info(f"跳过已下载的文件: {file_name}")
            return file_name
            
        callback = self._create_progress_callback(
            f"下载 {file_name}",
            message.file.size
        )
        
        await self.client.download_file(
            message,
            file_path,
            progress_callback=callback
        )
        
        downloaded.append(file_name)
        self.state[transfer_key] = {
            'downloaded': downloaded,
            'last_update': datetime.now().isoformat()
        }
        
        return file_name