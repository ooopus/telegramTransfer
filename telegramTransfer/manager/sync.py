"""同步相关功能实现"""

import os
import json
from typing import Dict, Any
from datetime import datetime

from loguru import logger

class SyncMixin:
    """同步功能Mixin类"""
    
    async def sync_folder(self,
                         folder_path: str,
                         target: str,
                         sync_mode: str = 'to',
                         caption_template: str = None) -> Dict[str, Any]:
        """同步文件夹"""
        folder_path = os.path.expanduser(folder_path)
        if not os.path.isdir(folder_path):
            raise NotADirectoryError(f"路径不是文件夹: {folder_path}")
            
        local_state = self.client.scan_folder(folder_path)
        entity, topic_id = await self.client.get_entity_by_id_or_username(target)
        remote_state = await self._get_remote_state(target)
        
        diff = self._calculate_diff(local_state, remote_state, sync_mode)
        result = await self._process_sync(
            folder_path, target, entity, local_state, remote_state, 
            diff, sync_mode, caption_template
        )
        
        self._save_sync_state(folder_path, target, sync_mode, local_state, remote_state)
        return result
        
    async def _get_remote_state(self, target):
        """获取远程文件状态"""
        entity, topic_id = await self.client.get_entity_by_id_or_username(target)
        messages = await self.client.get_file_messages(entity, reply_to=topic_id)
        remote_state = {}
        duplicate_messages = {}  # 用于存储重复文件的消息
        
        # 第一遍遍历：收集所有文件信息
        for msg in messages:
            if not msg.file or not msg.message:
                continue
            try:
                metadata = json.loads(msg.message)
                if 'original_path' in metadata:
                    path = metadata['original_path']
                    mtime = datetime.fromisoformat(metadata['mtime'])
                    
                    if path not in duplicate_messages:
                        duplicate_messages[path] = []
                    duplicate_messages[path].append({
                        'message': msg,
                        'mtime': mtime,
                        'size': msg.file.size,
                        'message_id': msg.id
                    })
            except json.JSONDecodeError:
                continue
        
        # 第二遍处理：只保留最新的文件，删除旧版本
        for path, msg_list in duplicate_messages.items():
            if len(msg_list) > 1:
                # 按修改时间排序，最新的在前
                sorted_msgs = sorted(msg_list, key=lambda x: x['mtime'], reverse=True)
                # 保留最新的版本
                newest = sorted_msgs[0]
                remote_state[path] = {
                    'size': newest['size'],
                    'mtime': newest['mtime'],
                    'message_id': newest['message_id']
                }
                # 删除旧版本
                for old in sorted_msgs[1:]:
                    try:
                        await old['message'].delete()
                        logger.info(f"已删除重复文件的旧版本: {path} (message_id={old['message_id']})")
                    except Exception as e:
                        logger.error(f"删除重复文件失败: {path} (message_id={old['message_id']}): {str(e)}")
            else:
                # 只有一个版本，直接保存
                msg_info = msg_list[0]
                remote_state[path] = {
                    'size': msg_info['size'],
                    'mtime': msg_info['mtime'],
                    'message_id': msg_info['message_id']
                }
        
        return remote_state
        
    def _calculate_diff(self, local_state, remote_state, sync_mode):
        """计算文件差异"""
        local_files = set(local_state.keys())
        remote_files = set(remote_state.keys())
        
        return {
            'to_download': remote_files - local_files,
            'to_upload': local_files - remote_files,
            'to_delete_local': local_files - remote_files if sync_mode == 'from' else set(),
            'to_delete_remote': remote_files - local_files if sync_mode == 'to' else set()
        }
        
    async def _process_sync(self, folder_path, target, entity, local_state, 
                          remote_state, diff, sync_mode, caption_template):
        """处理同步操作"""
        success = []
        failed = []
        deleted = []
        
        if sync_mode == 'from':
            await self._process_download_sync(
                folder_path, target, remote_state, diff,
                success, failed, deleted
            )
        else:
            await self._process_upload_sync(
                folder_path, target, local_state, diff,
                success, failed, deleted, caption_template
            )
            
        return {'success': success, 'failed': failed, 'deleted': deleted}
        
    def _save_sync_state(self, folder_path, target, sync_mode, local_state, remote_state):
        """保存同步状态"""
        self.state[self._get_transfer_key(folder_path, target)] = {
            'files': local_state if sync_mode == 'to' else remote_state,
            'last_update': datetime.now().isoformat()
        }
    
    async def _process_upload_sync(self, folder_path, target, local_state, diff,
                                 success, failed, deleted, caption_template):
        """处理上传同步"""
        # 处理需要上传的文件
        for rel_path in diff['to_upload']:
            try:
                info = local_state[rel_path]
                await self._upload_single_file(
                    folder_path, rel_path, info, target,
                    caption_template, None, [], None
                )
                success.append(rel_path)
                logger.info(f"已上传文件: {rel_path}")
            except Exception as e:
                logger.error(f"上传失败 {rel_path}: {str(e)}")
                failed.append(rel_path)
        
        # 处理需要删除的远程文件
        entity, topic_id = await self.client.get_entity_by_id_or_username(target)
        messages = await self.client.get_file_messages(entity, reply_to=topic_id)
        
        for msg in messages:
            try:
                if not msg.message:
                    logger.debug(f"跳过无消息内容的文件: message_id={msg.id}")
                    continue
                    
                try:
                    metadata = json.loads(msg.message)
                except json.JSONDecodeError:
                    logger.debug(f"跳过非JSON格式消息: message_id={msg.id}, content={msg.message}")
                    continue
                    
                if not isinstance(metadata, dict):
                    logger.debug(f"跳过非字典格式元数据: message_id={msg.id}")
                    continue
                    
                if 'original_path' not in metadata:
                    logger.debug(f"跳过缺少original_path的消息: message_id={msg.id}")
                    continue
                    
                if metadata['original_path'] in diff['to_delete_remote']:
                    await msg.delete()
                    deleted.append(metadata['original_path'])
                    logger.info(f"已删除远程文件: {metadata['original_path']}")
                    
            except Exception as e:
                logger.error(f"处理消息失败 message_id={msg.id}: {str(e)}")
                continue
    
    async def _process_download_sync(self, folder_path, entity, remote_state, diff,
                                   success, failed, deleted):
        """处理下载同步"""
        # 处理需要下载的文件
        for rel_path in diff['to_download']:
            try:
                info = remote_state[rel_path]
                msg_id = info['message_id']
                message = await self.client.get_messages(entity, ids=msg_id)
                if message and message.file:
                    file_path = os.path.join(folder_path, rel_path)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    await self.client.download_file(message, file_path)
                    success.append(rel_path)
            except Exception as e:
                logger.error(f"下载失败 {rel_path}: {str(e)}")
                failed.append(rel_path)
        
        # 处理需要删除的本地文件
        for rel_path in diff['to_delete_local']:
            try:
                file_path = os.path.join(folder_path, rel_path)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted.append(rel_path)
                    logger.info(f"已删除本地文件: {rel_path}")
            except Exception as e:
                logger.error(f"删除本地文件失败 {rel_path}: {str(e)}")