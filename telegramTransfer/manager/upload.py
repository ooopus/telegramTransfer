"""上传相关功能实现"""

import os
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime

from loguru import logger
from tqdm import tqdm

class UploadMixin:
    """上传功能Mixin类"""
    
    async def verify_upload_status(self, folder_path: str, target: str) -> Dict[str, Any]:
        """验证上传状态
        
        通过对比本地文件和远程消息，验证文件是否全部上传成功
        
        Args:
            folder_path: 文件夹路径
            target: 目标用户/频道
            
        Returns:
            Dict: 验证结果统计
        """
        folder_path = os.path.expanduser(folder_path)
        transfer_key = self._get_transfer_key(folder_path, target)
        
        # 获取本地文件信息
        local_files = self.client.scan_folder(folder_path)
        if not local_files:
            return {'verified': [], 'missing': [], 'inconsistent': []}
            
        # 获取远程消息
        entity, topic_id = await self.client.get_entity_by_id_or_username(target)
        # 指定 reply_to 参数为 topic_id
        messages = await self.client.get_file_messages(entity, reply_to=topic_id)
        
        # 构建远程文件映射
        remote_files = {}
        for msg in messages:
            if not msg.file or not msg.message:
                continue
            try:
                metadata = json.loads(msg.message)
                if 'original_path' in metadata:
                    remote_files[metadata['original_path']] = {
                        'size': msg.file.size,
                        'mtime': datetime.fromisoformat(metadata['mtime']),
                        'message_id': msg.id
                    }
                    logger.debug(f"找到远程文件: {metadata['original_path']}, 大小: {msg.file.size}")
            except json.JSONDecodeError:
                logger.debug(f"消息 {msg.id} 的元数据解析失败: {msg.message}")
                continue
        
        # 验证结果
        verified = []  # 验证成功的文件
        missing = []   # 未上传的文件
        inconsistent = []   # 不一致的文件
        
        # 对比文件
        for rel_path, local_info in local_files.items():
            logger.debug(f"检查本地文件: {rel_path}, 大小: {local_info['size']}")
            if rel_path not in remote_files:
                logger.debug(f"文件 {rel_path} 在远程未找到")
                missing.append(rel_path)
                continue
                
            remote_info = remote_files[rel_path]
            if remote_info['size'] != local_info['size']:
                logger.debug(f"文件 {rel_path} 大小不一致: 本地={local_info['size']}, 远程={remote_info['size']}")
                inconsistent.append(rel_path)
            else:
                verified.append(rel_path)
        
        # 更新传输状态
        self.state[transfer_key] = {
            'uploaded': verified,
            'last_verify': datetime.now().isoformat(),
            'missing': missing,
            'inconsistent': inconsistent
        }
        
        return {
            'verified': verified,
            'missing': missing,
            'inconsistent': inconsistent
        }

    async def upload_folder(self, folder_path: str, target: str, caption_template: str = None) -> Dict[str, Any]:
        """上传文件夹"""
        folder_path = os.path.expanduser(folder_path)
        if not os.path.isdir(folder_path):
            raise NotADirectoryError(f"路径不是文件夹: {folder_path}")
        
        # 在开始上传前进行初始校验
        logger.info("开始初始状态校验...")
        initial_verify = await self.verify_upload_status(folder_path, target)
        if initial_verify['verified']:
            logger.info(f"发现 {len(initial_verify['verified'])} 个文件已存在于目标位置")
            logger.info("已存在的文件列表:")
            for file in initial_verify['verified']:
                logger.info(f"  - {file}")
        
        # 扫描文件夹
        files_info = self.client.scan_folder(folder_path)
        if not files_info:
            logger.warning("文件夹为空")
            return {'success': [], 'failed': []}
        
        # 根据配置对文件进行排序
        upload_order = self.client.config.get('transfer', {}).get('upload_order', 'none')
        sorted_files = self._sort_files(files_info, upload_order)
        
        # 计算所有文件的总大小
        total_size = sum(info['size'] for info in files_info.values())
        overall_progress = tqdm(
            total=total_size,
            desc="总体进度",
            unit='B',
            unit_scale=True,
            position=0
        )
        
        # 获取未完成的传输
        transfer_key = self._get_transfer_key(folder_path, target)
        uploaded = self.state.get(transfer_key, {}).get('uploaded', [])
        
        # 更新总进度条，跳过已上传的文件
        skipped_size = sum(
            files_info[rel_path]['size'] 
            for rel_path in uploaded 
            if rel_path in files_info
        )
        overall_progress.update(skipped_size)
        
        success = []
        failed = []
        
        try:
            for rel_path, info in files_info.items():
                # 使用验证结果中的已验证文件列表
                if rel_path in initial_verify['verified']:
                    logger.info(f"跳过已验证的文件: {rel_path}")
                    success.append(rel_path)
                    continue
                    
                try:
                    await self._upload_single_file(
                        folder_path, rel_path, info, target, 
                        caption_template, transfer_key, uploaded,
                        overall_progress=overall_progress
                    )
                    success.append(rel_path)
                    
                except Exception as e:
                    logger.error(f"上传失败 {rel_path}: {str(e)}")
                    failed.append(rel_path)
        finally:
            overall_progress.close()
            
        # 在所有文件上传完成后进行一次验证
        logger.info("开始验证上传状态...")
        verify_result = await self.verify_upload_status(folder_path, target)
        
        if verify_result['missing'] or verify_result['inconsistent']:
            if verify_result['missing']:
                logger.warning(f"发现 {len(verify_result['missing'])} 个文件未上传:")
                for file in verify_result['missing']:
                    logger.warning(f"  - 未上传: {file}")
                    
            if verify_result['inconsistent']:
                logger.warning(f"发现 {len(verify_result['inconsistent'])} 个文件不一致:")
                for file in verify_result['inconsistent']:
                    logger.warning(f"  - 不一致: {file}")
        else:
            logger.info("所有文件验证通过")
        
        return {
            'success': verify_result['verified'],
            'failed': verify_result['missing'] + verify_result['inconsistent'],
            'verify_result': verify_result
        }

    async def _upload_single_file(self, folder_path, rel_path, info, target, 
                                caption_template, transfer_key, uploaded, 
                                overall_progress=None):
        """上传单个文件"""
        file_path = os.path.join(folder_path, rel_path)
        metadata = {
            'original_path': rel_path,
            'size': info['size'],
            'mtime': info['mtime'].isoformat()
        }
        caption = json.dumps(metadata) if not caption_template else caption_template.format(
            path=rel_path,
            size=info['size'],
            mtime=info['mtime'].isoformat()
        )
        
        callback = self._create_progress_callback(
            f"上传 {rel_path}",
            info['size'],
            overall_progress=overall_progress
        )
        
        await self.client.upload_file(
            file_path,
            target,
            caption=caption,
            progress_callback=callback
        )
        
        # 更新状态
        uploaded.append(rel_path)
        self.state[transfer_key] = {
            'uploaded': uploaded,
            'last_update': datetime.now().isoformat()
        }

    def _sort_files(self, files_info: Dict[str, Dict], order: str) -> List[Tuple[str, Dict]]:
        """根据指定顺序对文件进行排序
        
        Args:
            files_info: 文件信息字典
            order: 排序方式
            
        Returns:
            List[Tuple[str, Dict]]: 排序后的文件列表
        """
        items = list(files_info.items())
        
        if order == 'none':
            return items
            
        if order == 'name_asc':
            return sorted(items, key=lambda x: x[0])
        elif order == 'name_desc':
            return sorted(items, key=lambda x: x[0], reverse=True)
        elif order == 'size_asc':
            return sorted(items, key=lambda x: x[1]['size'])
        elif order == 'size_desc':
            return sorted(items, key=lambda x: x[1]['size'], reverse=True)
        
        return items  # 默认不排序