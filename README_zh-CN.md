# Telegram Transfer

一个基于 Telethon 的 Telegram 文件传输工具，支持文件夹上传、下载和同步功能。

## 特性

- 文件夹上传、下载和同步
- 断点续传功能
- 同步支持
- 实时进度显示
- 文件完整性验证
- 会话管理支持
- Topic Group 支持
- 自动忽略系统文件（.DS_Store, __pycache__ 等）

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/ooopus/telegramTransfer.git
cd telegramTransfer
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置：
创建一个 `config.toml` 文件：
```toml
# Telegram API凭据
[api]
id = ""  # 从 https://my.telegram.org 获取
hash = ""

# 会话配置
[session]
dir = "~/.config/telegramTransfer/sessions"  # 会话文件存储目录
name = "default"  # 默认会话名称

# 文件传输相关配置
[transfer]
chunk_size = 2097152
retry_times = 3
timeout = 300
# 上传顺序: name_asc(按文件名升序), name_desc(按文件名降序), 
# size_asc(按大小升序), size_desc(按大小降序), none(不排序)
upload_order = "none"

# 日志配置
[logging]
level = "INFO"  # 可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL

# 文件过滤规则
[filters]
exclude = [
    ".DS_Store",
    "Thumbs.db",
    ".git/",
    "__pycache__/",
    "*.pyc",
    ".*.swp",
    ".env"
]
include = ["*"]
```

API ID 和 Hash 可以从 https://my.telegram.org 获取。

## 使用方法

### 基本命令

```bash
# 上传文件夹
python -m telegramTransfer upload /path/to/folder --to username

# 上传到 Topic Group
python -m telegramTransfer upload /path/to/folder --to https://t.me/c/2257928502/336

# 下载文件夹
python -m telegramTransfer download /path/to/folder --from username

# 同步文件夹到云端
python -m telegramTransfer upload /path/to/folder --to username --sync

# 同步文件夹到本地
python -m telegramTransfer download /path/to/folder --from username --sync
```

### 命令参数

- `folder`: 要处理的文件夹路径
- `--to`: 目标用户/频道，支持以下格式：
  - 数字 ID（例如：4639628806）
  - 用户名（例如：@username）
  - Topic Group 链接（例如：https://t.me/c/2257928502/336）
- `--from`: 源用户/频道，支持与 --to 相同的格式
- `--caption`: 文件描述模板，支持以下变量：
  - {path}: 文件相对路径
  - {size}: 文件大小
  - {mtime}: 文件修改时间
- `--session`: 指定会话名称
- `--new-session`: 强制创建新会话
- `--api-id`: Telegram API ID
- `--api-hash`: Telegram API Hash
- `--sync`: 启用同步模式

### 高级功能

1. 断点续传：
   - 传输中断后重新运行命令即可从断点处继续
   - 支持文件完整性验证
   - 自动跳过已上传的文件
   - 自动处理重复文件

2. Topic Group 支持：
   - 支持上传文件到指定的 Topic
   - 自动处理私有频道 ID 转换
   - 保持消息在正确的 Topic 中

3. 文件过滤：
   - 自动忽略系统文件和临时文件
   - 支持自定义过滤规则
   - 支持通配符匹配

4. 会话管理：
   - 多账号支持
   - 会话持久化
   - 自动登录
   - 支持两步验证

5. 文件验证：
   - 上传前后自动验证
   - 检测文件大小不一致
   - 显示详细的验证结果
   - 自动处理文件冲突

## 注意事项

1. 首次使用需要进行登录验证
2. 建议使用稳定的网络连接
3. 大文件传输可能受到 Telegram 限制
4. 请遵守 Telegram 服务条款
5. 文件名中的特殊字符会被正确处理
6. 同步模式会删除目标位置上的多余文件

## 许可证

本项目基于 GNU General Public License v3 (GPLv3) 许可证开源。