"""主入口模块

允许通过 python -m telegramTransfer 方式运行程序
"""

from .cli import cli

if __name__ == '__main__':
    cli()