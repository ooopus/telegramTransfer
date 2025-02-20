"""配置模块

管理Telegram API的配置信息和其他全局配置项
"""

import os
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, Set
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
import tomli
import tomli_w

# 加载环境变量
load_dotenv()

@dataclass
class APIConfig:
    id: int
    hash: str

    def validate(self):
        if not self.id or not self.hash:
            raise ValueError('需要提供API ID和API Hash，请设置环境变量TG_API_ID和TG_API_HASH，或在配置文件中设置')
        try:
            int(str(self.id))
        except ValueError:
            raise ValueError('API ID必须是一个整数')

@dataclass
class SessionConfig:
    dir: Path
    name: str

@dataclass
class LoggingConfig:
    level: str
    valid_levels: Set[str] = frozenset({'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'})

    def validate(self):
        if self.level not in self.valid_levels:
            raise ValueError(f'无效的日志级别，必须是以下之一：{self.valid_levels}')

@dataclass
class TransferConfig:
    chunk_size: int
    retry_times: int
    timeout: float
    upload_order: str = "none"
    
    VALID_ORDERS = {'name_asc', 'name_desc', 'size_asc', 'size_desc', 'none'}

    def validate(self):
        if not isinstance(self.chunk_size, int) or self.chunk_size <= 0:
            raise ValueError('chunk_size必须是一个正整数')
        if not isinstance(self.retry_times, int) or self.retry_times < 0:
            raise ValueError('retry_times必须是一个非负整数')
        if not isinstance(self.timeout, (int, float)) or self.timeout <= 0:
            raise ValueError('timeout必须是一个正数')
        if self.upload_order not in self.VALID_ORDERS:
            raise ValueError(f'upload_order必须是以下之一：{self.VALID_ORDERS}')

def prompt_api_credentials() -> Dict[str, Any]:
    """交互式获取 API 凭据"""
    print("\n请访问 https://my.telegram.org 获取 API 凭据")
    api_id = input("请输入 API ID: ").strip()
    api_hash = input("请输入 API Hash: ").strip()
    
    return {
        "api": {
            "id": api_id,
            "hash": api_hash
        }
    }

@dataclass
class Config:
    api: APIConfig
    session: SessionConfig
    logging: LoggingConfig
    transfer: TransferConfig
    filters: Dict[str, Any]

    @classmethod
    def load(cls) -> 'Config':
        config_data = cls._load_merged_config()
        return cls(
            api=APIConfig(**config_data['api']),
            session=SessionConfig(
                dir=Path(os.path.expanduser(config_data['session']['dir'])),
                name=config_data['session']['name']
            ),
            logging=LoggingConfig(**config_data['logging']),
            transfer=TransferConfig(**config_data['transfer']),
            filters=config_data['filters']
        )

    @staticmethod
    def _load_merged_config() -> Dict[str, Any]:
        # 设置配置文件路径
        config_dir = Path.home() / '.config' / 'telegramTransfer'
        config_file = config_dir / 'config.toml'
        example_config_file = Path(__file__).parent / 'config.toml.example'

        # 确保配置目录存在
        config_dir.mkdir(parents=True, exist_ok=True)

        # 加载默认配置
        if not example_config_file.exists():
            raise FileNotFoundError(f'示例配置文件不存在：{example_config_file}')

        with open(example_config_file, 'rb') as f:
            config = tomli.load(f)

        # 如果配置文件不存在，创建新配置
        if not config_file.exists():
            logger.info(f'配置文件不存在，将从示例文件创建：{config_file}')
            # 获取用户输入的 API 凭据
            user_config = prompt_api_credentials()
            config.update(user_config)
            
            # 保存配置文件
            with open(config_file, 'wb') as f:
                tomli_w.dump(config, f)
            logger.info('已创建配置文件')
        else:
            # 加载现有配置
            with open(config_file, 'rb') as f:
                user_config = tomli.load(f)
                config.update(user_config)

        # 如果配置文件中没有 API 凭据，提示用户输入
        if not config['api']['id'] or not config['api']['hash']:
            user_config = prompt_api_credentials()
            config.update(user_config)
            # 更新配置文件
            with open(config_file, 'wb') as f:
                tomli_w.dump(config, f)
            logger.info('已更新 API 凭据')

        # 从环境变量更新配置
        env_mapping = {
            'TG_API_ID': ('api', 'id'),
            'TG_API_HASH': ('api', 'hash'),
            'TG_SESSION_DIR': ('session', 'dir'),
            'TG_SESSION_NAME': ('session', 'name'),
            'TG_LOG_LEVEL': ('logging', 'level')
        }

        for env_var, (section, key) in env_mapping.items():
            if value := os.getenv(env_var):
                if section not in config:
                    config[section] = {}
                config[section][key] = value

        return config

    def validate(self):
        """验证所有配置项"""
        self.api.validate()
        self.logging.validate()
        self.transfer.validate()

# 全局配置实例
config = Config.load()

def init_config() -> None:
    """初始化配置
    
    - 验证配置有效性
    - 创建必要的目录
    - 设置日志级别
    
    Raises:
        ValueError: 配置无效时抛出
    """
    # 验证配置
    config.validate()
    
    # 创建会话目录
    config.session.dir.mkdir(parents=True, exist_ok=True)
    
    # 设置日志级别
    logger.remove()
    logger.add(lambda msg: print(msg), level=config.logging.level)
    
    logger.info('配置初始化完成')

# 导出常用配置
API_ID = config.api.id
API_HASH = config.api.hash
SESSION_DIR = config.session.dir
SESSION_NAME = config.session.name
LOG_LEVEL = config.logging.level
CHUNK_SIZE = config.transfer.chunk_size
RETRY_TIMES = config.transfer.retry_times
TIMEOUT = config.transfer.timeout
FILE_FILTERS = config.filters