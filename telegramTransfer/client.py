"""TelegramTransferClient类实现

处理Telegram客户端连接、会话管理和文件传输等核心功能。
"""

import os
import hashlib
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.types import Message, Document
from telethon.tl.custom import Dialog
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from loguru import logger
import json
import tomli
from .config import SESSION_DIR


class TelegramTransferClient:
    """Telegram文件传输客户端
    
    处理文件上传、下载和同步等核心功能。
    """
    
    def __init__(self, 
                 session_name: str = None,
                 api_id: int = None,
                 api_hash: str = None,
                 config_path: str = None,
                 session_dir: str = None):
        """初始化客户端
        
        Args:
            session_name: 会话名称
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            config_path: 配置文件路径，默认为脚本所在目录下的config.json
            session_dir: 会话文件存储目录，默认为脚本所在目录下的sessions目录
        """
        # 如果未指定配置文件路径，使用用户目录下的配置
        if config_path is None:
            config_dir = Path.home() / '.config' / 'telegramTransfer'
            self.config_path = str(config_dir / 'config.toml')
        else:
            self.config_path = os.path.expanduser(config_path)
            
        self.config = self._load_config()
        
        # 使用传入的参数或配置文件中的值
        self.api_id = api_id or self.config.get('api', {}).get('id')
        self.api_hash = api_hash or self.config.get('api', {}).get('hash')
        self.session_name = session_name or self.config.get('session', {}).get('name', 'default')
        
        # 设置会话文件存储目录
        if session_dir is None:
            session_dir = Path.home() / '.config' / 'telegramTransfer' / 'sessions'
            self.session_dir = str(session_dir)
        else:
            self.session_dir = os.path.expanduser(session_dir)
        
        # 确保会话目录存在
        os.makedirs(self.session_dir, exist_ok=True)
        
        # 初始化客户端
        self.client = None
        self.me = None
        
        # 传输状态记录
        self.transfer_state = {}
        
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'rb') as f:  # 使用二进制模式打开
                return tomli.load(f) or {}
        return {}
    
    def _save_config(self):
        """保存配置文件"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)
            
    async def connect(self, force_new: bool = False) -> None:
        """连接到Telegram
        
        Args:
            force_new: 是否强制创建新会话
        """
        if not self.api_id or not self.api_hash:
            raise ValueError("需要提供API ID和API Hash")
            
        # 构建会话文件路径
        session_path = SESSION_DIR / f"{self.session_name}.session"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"会话文件路径: {session_path}")
        
        # 如果强制创建新会话，则删除已存在的会话文件
        if force_new and session_path.exists():
            logger.info(f"强制创建新会话，删除已存在的会话文件: {session_path}")
            session_path.unlink()
        
        # 创建客户端
        self.client = TelegramClient(
            str(session_path),
            self.api_id,
            self.api_hash
        )
        logger.info(f'会话文件将保存在: {session_path}')
        
        # 连接并登录
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.info("需要进行账号登录")
                phone = input('请输入手机号 (带国际区号): ')
                await self.client.send_code_request(phone)
                code = input('请输入收到的验证码: ')
                try:
                    await self.client.sign_in(phone, code)
                    logger.info("验证码登录成功")
                except SessionPasswordNeededError:
                    logger.info("需要输入两步验证密码")
                    password = input('请输入两步验证密码: ')
                    await self.client.sign_in(password=password)
                    logger.info("两步验证登录成功")
            
            self.me = await self.client.get_me()
            logger.info(f'已连接到账号: {self.me.first_name}')
            
        except Exception as e:
            logger.error(f"连接失败: {str(e)}")
            await self.disconnect()
            raise
        
    async def disconnect(self) -> None:
        """断开连接"""
        if self.client:
            await self.client.disconnect()
            self.client = None
            self.me = None
            
    async def get_entity_by_id_or_username(self, target: str):
        """通过ID、用户名或链接获取目标实体
        
        Args:
            target: 目标用户/频道的标识，支持以下格式：
                - ID: 4639628806
                - 用户名: @username
                - Topic Group链接: https://t.me/c/2257928502/2
            
        Returns:
            Tuple[Entity, Optional[int]]: (Telegram实体对象, topic_id)
        """
        if not self.client:
            raise RuntimeError("客户端未连接")
            
        # 处理topic group链接
        import re
        topic_group_pattern = r'https://t\.me/c/([0-9]+)/([0-9]+)'
        match = re.match(topic_group_pattern, target)
        if match:
            channel_id = int(match.group(1))
            topic_id = int(match.group(2))
            # 将频道ID转换为负数，因为私有频道ID在Telegram API中是负数
            if channel_id > 0:
                channel_id = -1000000000000 - channel_id
            entity = await self.client.get_entity(channel_id)
            return entity, topic_id
            
        # 尝试解析为数字ID
        try:
            if target.isdigit():
                return await self.client.get_entity(int(target)), None
        except ValueError:
            pass
            
        # 处理@开头的用户名
        if target.startswith('@'):
            target = target[1:]
            
        # 通过用户名获取实体
        return await self.client.get_entity(target), None

    async def upload_file(self, 
                         file_path: str, 
                         target: str,
                         caption: str = None,
                         progress_callback: callable = None) -> Message:
        """上传单个文件
        
        Args:
            file_path: 文件路径
            target: 目标用户/频道
            caption: 文件描述
            progress_callback: 进度回调函数
            
        Returns:
            Message: 已发送的消息对象
        """
        if not self.client:
            raise RuntimeError("客户端未连接")
            
        file_path = Path(file_path).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
            
        # 获取目标对话和topic_id
        entity, topic_id = await self.get_entity_by_id_or_username(target)
        
        # 上传文件，设置 parse_mode=None 禁用自动格式化
        return await self.client.send_file(
            entity,
            str(file_path),
            caption=caption,
            progress_callback=progress_callback,
            reply_to=topic_id,
            parse_mode=None,  # 添加这行，禁用自动格式化
            force_document=True  # 添加这行，强制作为文档发送
        )
        
    async def download_file(self,
                           message: Message,
                           download_path: str,
                           progress_callback: callable = None) -> str:
        """下载单个文件
        
        Args:
            message: 消息对象
            download_path: 下载路径
            progress_callback: 进度回调函数
            
        Returns:
            str: 下载后的文件路径
        """
        if not self.client:
            raise RuntimeError("客户端未连接")
            
        if not message.file:
            raise ValueError("消息中没有文件")
            
        download_path = Path(download_path).expanduser()
        download_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 下载文件
        path = await self.client.download_media(
            message.media,
            str(download_path),
            progress_callback=progress_callback
        )
        
        return path
    
    async def get_file_messages(self, 
                              dialog: Dialog, 
                              limit: int = None,
                              reply_to: int = None) -> List[Message]:
        """获取对话中的文件消息
        
        Args:
            dialog: 对话对象
            limit: 获取消息数量限制
            reply_to: Topic ID（用于 Topic Group）
            
        Returns:
            List[Message]: 文件消息列表
        """
        messages = []
        async for message in self.client.iter_messages(
            dialog, 
            limit=limit,
            reply_to=reply_to  # 添加 reply_to 参数
        ):
            if message.file:
                messages.append(message)
        return messages
    
    def calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件SHA256哈希值
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def scan_folder(self, folder_path: str, ignore_patterns: List[str] = None) -> Dict[str, Dict[str, Any]]:
        """扫描文件夹
        
        Args:
            folder_path: 文件夹路径
            ignore_patterns: 要忽略的文件模式列表，支持通配符
            
        Returns:
            Dict: 文件信息字典
            {
                'relative/path/to/file': {
                    'size': file_size,
                    'mtime': modified_time,
                    'hash': file_hash
                }
            }
        """
        folder_path = Path(folder_path).expanduser()
        files_info = {}
        
        # 默认忽略的系统文件
        default_ignores = [
            '.DS_Store',
            'Thumbs.db',
            '.git/',
            '__pycache__/',
            '*.pyc',
            '.*.swp',
            '.env'
        ]
        
        # 合并默认忽略和自定义忽略规则
        all_ignores = default_ignores + (ignore_patterns or [])
        
        # 编译忽略规则为正则表达式
        import fnmatch
        import re
        ignore_patterns = [re.compile(fnmatch.translate(p)) for p in all_ignores]
        
        for path in folder_path.rglob('*'):
            if path.is_file():
                rel_path = str(path.relative_to(folder_path))
                
                # 检查文件是否应该被忽略
                should_ignore = any(
                    pattern.match(rel_path) 
                    or pattern.match(path.name) 
                    for pattern in ignore_patterns
                )
                
                if not should_ignore:
                    files_info[rel_path] = {
                        'size': path.stat().st_size,
                        'mtime': datetime.fromtimestamp(path.stat().st_mtime),
                        'hash': self.calculate_file_hash(str(path))
                    }
                
        return files_info
    
    def detect_changes(self,
                      old_state: Dict[str, Dict[str, Any]],
                      new_state: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
        """检测文件变更
        
        Args:
            old_state: 旧文件状态
            new_state: 新文件状态
            
        Returns:
            Dict: 变更信息
            {
                'added': [文件列表],
                'modified': [文件列表],
                'deleted': [文件列表]
            }
        """
        changes = {
            'added': [],
            'modified': [],
            'deleted': []
        }
        
        # 检查新增和修改的文件
        for file_path, new_info in new_state.items():
            if file_path not in old_state:
                changes['added'].append(file_path)
            elif new_info['hash'] != old_state[file_path]['hash']:
                changes['modified'].append(file_path)
                
        # 检查删除的文件
        for file_path in old_state:
            if file_path not in new_state:
                changes['deleted'].append(file_path)
                
        return changes