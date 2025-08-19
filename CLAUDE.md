# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CC Release Monitor is a locally-hosted Telegram bot that monitors the `anthropics/claude-code` repository for new commits and changelog updates. The bot provides automatic notifications when changes are detected and runs entirely on the user's machine with optional system tray integration.

## Key Commands

### Development Commands
- `pip install -r requirements.txt` - Install dependencies (Python 3.9+ required)
- `python simple_bot.py` - Run bot in console mode
- `python tray_bot.py` - Run bot with system tray integration

### Windows Batch Launchers
- `start_bot.bat` - Console mode (visible window)
- `start_bot_tray_silent.bat` - Silent mode (system tray only)

### Testing
- `python -m pytest` - Run test suite
- `python -m pytest tests/test_config.py` - Run specific test file
- `black .` - Code formatting
- `flake8` - Linting

## Architecture

### Core Components

**Configuration System** (`src/config.py`):
- Environment-based configuration with `.env.example` template
- Required: `TELEGRAM_BOT_TOKEN`
- Optional: `GITHUB_API_TOKEN` (for higher rate limits)
- Configurable monitoring intervals, logging levels, and storage paths

**GitHub Integration** (`src/github_client.py`):
- Rate-limited API client with retry logic
- Supports both authenticated and anonymous access
- Handles releases, commits, and file content fetching

**Version Management** (`src/version_manager.py`):
- JSON-based persistent storage in `./data/` directory
- Tracks releases, commits, and changelog changes
- Maintains monitoring state and statistics

**Bot Implementation** (`simple_bot.py`):
- Main Telegram bot with comprehensive command set
- Async/await pattern with APScheduler for background monitoring
- Markdown-formatted responses with error handling

**System Tray Integration** (`tray_bot.py`):
- Optional pystray-based system tray application
- Runs bot as background process with tray controls
- Windows-optimized with hidden console mode

### Bot Commands Architecture

Commands are organized into functional groups:
- **Basic**: `/start`, `/help`, `/status`
- **Manual Checks**: `/check`, `/commits`, `/commit <sha>`, `/changelog`, `/changelog_latest`
- **Monitoring Control**: `/start_monitoring`, `/stop_monitoring`
- **Information**: `/latest`, `/version`

### Data Flow

1. **Configuration Loading**: Environment variables → Config class validation
2. **GitHub Monitoring**: Scheduled checks → API calls → Data parsing → Version comparison
3. **Change Detection**: New releases/commits → Notification formatting → User alerts
4. **Persistence**: State management → JSON storage → Statistics tracking

## Development Guidelines

### Python Path Configuration
The project uses hardcoded Python paths in batch files (`C:\Users\Dusan\miniconda3\python.exe`). When deploying to different environments, update:
- `start_bot.bat` line 20
- `tray_bot.py` line 73

### Environment Setup
1. Copy `.env.example` to `.env` and configure tokens
2. Ensure `./data/` and `./logs/` directories are writable
3. Verify Python executable paths in launcher scripts

### Rate Limiting
- Anonymous GitHub API: 60 requests/hour
- Authenticated API: 5,000 requests/hour
- Bot makes ~144 calls/day when monitoring actively
- Implement exponential backoff for API failures

### Error Handling Patterns
- Configuration errors raise `ConfigError` exceptions
- GitHub API errors use custom `GitHubAPIError` and `RateLimitError`
- All bot commands include try-catch with user-friendly error messages
- Logging configured for both file and console output

### Testing Patterns
Tests use pytest with environment variable mocking for configuration testing. Focus areas:
- Configuration validation and defaults
- Rate limit handling
- Error scenarios for GitHub API
- Bot command response formatting

### System Integration
The bot supports two deployment modes:
- **Console Mode**: Visible window with direct output
- **Tray Mode**: Background process with system tray icon and logging

System tray implementation requires `pystray` and `pillow` packages and gracefully degrades to hidden mode if unavailable.