"""命令行接口实现

处理命令行参数和操作，调用相应的FileTransferManager方法执行任务。
"""

import asyncio
from typing import Optional

import click
from loguru import logger

from .client import TelegramTransferClient
from .manager import FileTransferManager
from .config import API_ID as DEFAULT_API_ID, API_HASH as DEFAULT_API_HASH, init_config

async def handle_transfer(manager: FileTransferManager,
                        operation: str,
                        folder: str,
                        target: str,
                        caption: Optional[str] = None,
                        sync: bool = False) -> dict:
    """处理文件传输操作
    
    Args:
        manager: 文件传输管理器
        operation: 操作类型（upload/download）
        folder: 文件夹路径
        target: 目标用户/频道
        caption: 文件描述模板
        sync: 是否启用同步模式
        
    Returns:
        Dict: 传输结果统计
    """
    if operation == 'upload':
        logger.info(f'开始上传文件夹: {folder}')
        if sync:
            logger.info('启用同步模式')
            return await manager.sync_folder(folder, target, 'to', caption)
        return await manager.upload_folder(folder, target, caption)
        
    else:  # download
        logger.info(f'开始下载文件到: {folder}')
        if sync:
            logger.info('启用同步模式')
            return await manager.sync_folder(folder, target, 'from', caption)
        return await manager.download_folder(target, folder)

def print_result(result: dict) -> None:
    """打印传输结果统计"""
    logger.info('传输完成:')
    logger.info(f'成功: {len(result["success"])} 个文件')
    logger.info(f'失败: {len(result["failed"])} 个文件')
    
    # 添加验证结果展示
    if 'verify_result' in result:
        verify = result['verify_result']
        logger.info('验证结果:')
        logger.info(f'验证成功: {len(verify["verified"])} 个文件')
        logger.info(f'未上传: {len(verify["missing"])} 个文件')
        logger.info(f'不一致: {len(verify["inconsistent"])} 个文件')
        
    if 'deleted' in result:
        logger.info(f'删除: {len(result["deleted"])} 个文件')

@click.command()
@click.argument('operation', type=click.Choice(['upload', 'download']))
@click.argument('folder', type=click.Path(exists=True))
@click.option('--to', help='目标用户/频道（支持ID、用户名或链接，例如：4639628806、@username 或 https://t.me/c/2257928502/2）')
@click.option('--from', 'source', help='源用户/频道（支持ID、用户名或链接，例如：4639628806、@username 或 https://t.me/c/2257928502/2）')
@click.option('--caption', help='文件描述模板')
@click.option('--session', help='会话ID')
@click.option('--new-session', is_flag=True, help='强制新建会话')
@click.option('--api-id', type=int, help='Telegram API ID')
@click.option('--api-hash', help='Telegram API Hash')
@click.option('--sync', is_flag=True, help='启用同步模式')
def cli(operation: str,
       folder: str,
       to: Optional[str],
       source: Optional[str],
       caption: Optional[str],
       session: Optional[str],
       new_session: bool,
       api_id: Optional[int],
       api_hash: Optional[str],
       sync: bool = False):
    """Telegram文件传输工具
    
    支持文件夹上传、下载和同步功能。支持通过ID或用户名指定目标。
    
    示例:
    python -m telegramTransfer upload /path/to/folder --to 4639628806
    python -m telegramTransfer download /path/to/folder --from @channel
    python -m telegramTransfer upload /path/to/folder --to @username --sync
    python -m telegramTransfer upload /path/to/folder --to https://t.me/c/2257928502/2
    """
    # 参数验证
    if operation == 'upload' and not to:
        raise click.UsageError('上传模式需要指定 --to 参数')
    elif operation == 'download' and not source:
        raise click.UsageError('下载模式需要指定 --from 参数')

    
    # 初始化配置
    init_config()
    
    # 初始化客户端
    client = TelegramTransferClient(
        session_name=session,
        api_id=api_id or DEFAULT_API_ID,
        api_hash=api_hash or DEFAULT_API_HASH
    )
    
    # 创建事件循环
    loop = asyncio.get_event_loop()
    
    try:
        # 连接客户端
        loop.run_until_complete(client.connect(force_new=new_session))
        
        # 创建传输管理器
        manager = FileTransferManager(client)
        
        # 执行传输操作
        target = to if operation == 'upload' and to else source
        result = loop.run_until_complete(
            handle_transfer(manager, operation, folder, target, caption, sync)
        )
        
        # 输出结果统计
        print_result(result)
        
    except Exception as e:
        logger.error(f'发生错误: {str(e)}')
        raise click.ClickException(str(e))
        
    finally:
        # 断开连接
        if client:
            loop.run_until_complete(client.disconnect())

if __name__ == '__main__':
    cli()