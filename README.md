# Telegram Transfer

A Telegram file transfer tool based on Telethon, supporting folder upload, download, and synchronization.

## Features

- Folder upload, download, and synchronization
- Resume broken transfers
- Sync support
- Real-time progress display
- File integrity verification
- Session management
- Topic Group support
- Auto-ignore system files (.DS_Store, __pycache__, etc.)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ooopus/telegramTransfer.git
cd telegramTransfer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configuration:
Create a `config.toml` file:
```toml
[api]
id = ""
hash = ""

[session]
dir = "~/.config/telegramTransfer/sessions"
name = "default"

[transfer]
chunk_size = 2097152
retry_times = 3
timeout = 300
upload_order = "none" # name_asc, name_desc, size_asc, size_desc, none

[logging]
level = "INFO"

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

Get your API ID and Hash from https://my.telegram.org.

## Usage

### Basic Commands

```bash
# Upload folder
python -m telegramTransfer upload /path/to/folder --to username

# Upload to Topic Group
python -m telegramTransfer upload /path/to/folder --to https://t.me/c/2257928502/336

# Download folder
python -m telegramTransfer download /path/to/folder --from username

# Sync folder to cloud
python -m telegramTransfer upload /path/to/folder --to username --sync

# Sync folder to local
python -m telegramTransfer download /path/to/folder --from username --sync
```

### Command Arguments

- `folder`: Path to the folder to process
- `--to`: Target user/channel, supports the following formats:
  - Numeric ID (e.g., 4639628806)
  - Username (e.g., @username)
  - Topic Group Link (e.g., https://t.me/c/2257928502/336)
- `--from`: Source user/channel, supports the same formats as --to
- `--caption`: File description template, supports the following variables:
  - {path}: Relative file path
  - {size}: File size
  - {mtime}: File modification time
- `--session`: Specify session name
- `--new-session`: Force create new session
- `--api-id`: Telegram API ID
- `--api-hash`: Telegram API Hash
- `--sync`: Enable sync mode

### Advanced Features

1. Resume Broken Transfers:
   - Continue from where it left off after interruption
   - File integrity verification
   - Auto-skip uploaded files
   - Auto-handle duplicate files

2. Topic Group Support:
   - Upload files to specific Topics
   - Auto-handle private channel ID conversion
   - Keep messages in correct Topics

3. File Filtering:
   - Auto-ignore system and temporary files
   - Custom filter rules
   - Wildcard pattern matching

4. Session Management:
   - Multi-account support
   - Session persistence
   - Automatic login
   - Two-factor authentication support

5. File Verification:
   - Auto-verify before and after upload
   - Detect file size inconsistencies
   - Display detailed verification results
   - Auto-handle file conflicts

## Notes

1. First-time use requires login verification
2. Stable network connection recommended
3. Large file transfers may be limited by Telegram
4. Please comply with Telegram's Terms of Service
5. Special characters in filenames are handled correctly
6. Sync mode will delete excess files at the destination

## License

This project is open-sourced under the GNU General Public License v3 (GPLv3).