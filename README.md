# Claude Code Release Monitor

A locally-hosted Telegram bot that automatically monitors the `anthropics/claude-code` GitHub repository for new releases and sends instant notifications to subscribers. Designed for developers who want reliable, private, and cost-free release monitoring without cloud dependencies.

## Why Local Hosting?

**Complete Control & Privacy**
- Your bot runs entirely on your machine - no third-party servers
- All data stays local - release history, user preferences, configurations
- Full control over monitoring schedules and notification timing

**Zero Ongoing Costs**
- No monthly cloud hosting fees or subscription costs
- No database hosting charges or API usage limits
- One-time setup with your own Telegram bot token

**Simple & Reliable**
- Minimal setup - just Python, a Telegram bot token, and basic configuration
- Runs continuously in the background with automatic recovery
- No complex deployment pipelines or server management

**Perfect for Personal Use**
- Ideal for individual developers or small teams
- Lightweight resource usage on any modern computer
- Works on Windows, macOS, and Linux

## Features

- **🔍 Automated Monitoring**: Checks for new Claude Code releases every 30 minutes (configurable)
- **📱 Rich Telegram Notifications**: Formatted messages with release details, changelogs, and download links
- **🏠 Local Machine Deployment**: No cloud dependencies, runs entirely on your computer
- **⚙️ Configurable Settings**: Customizable check intervals, quiet hours, and notification preferences
- **📝 File-Based Storage**: Simple JSON files for data persistence - no database required
- **👥 Multi-User Support**: Share with team members or family using the same bot instance
- **🛡️ Error Recovery**: Robust handling of network issues, API rate limits, and system restarts
- **🔧 Manual Commands**: Instant release checks and status updates via Telegram commands

## Local Hosting Benefits

### For Developers
- Stay informed about Claude Code updates without constant GitHub checking
- Get notified immediately when bug fixes or new features are released
- Private monitoring - no data shared with external services
- Full control over notification timing and content

### For Teams
- Keep everyone informed about Claude Code updates
- Coordinate version updates across team members
- No per-user costs or account management overhead
- Simple shared deployment on office machine or personal server

### Technical Advantages
- **No Vendor Lock-in**: Your bot, your rules, your infrastructure
- **Unlimited Usage**: No API quotas or usage restrictions beyond GitHub/Telegram limits
- **Data Sovereignty**: All monitoring data stays on your local system
- **Customizable**: Easy to modify and extend for your specific needs

## Prerequisites

- **Python 3.9+**: Modern Python installation with pip package manager
- **Telegram Bot Token**: Free bot token from [@BotFather](https://t.me/BotFather) on Telegram
- **Internet Connection**: Required for GitHub API and Telegram API access
- **Basic System Requirements**: 
  - 50MB RAM (typical usage)
  - 10MB disk space for code and data
  - Always-on computer for continuous monitoring (optional - can run on-demand)

## Quick Start Guide

### 1. Get Your Telegram Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Choose a name and username for your bot
4. Save the bot token (looks like `123456789:ABCdefGhIjKlMnOpQrStUvWxYz`)

### 2. Install the Bot
```bash
# Clone the repository
git clone <repository_url>
cd CC-Release-Monitor

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your bot token
```

### 3. Configure Settings
Edit `.env` file with your settings:
```env
# Required: Your Telegram bot token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: GitHub token for higher rate limits (recommended)
GITHUB_API_TOKEN=your_github_token_here

# Optional: Monitoring configuration
CHECK_INTERVAL_MINUTES=30
LOG_LEVEL=INFO
```

### 4. Run the Bot
```bash
# Start the bot
python run.py

# Or run in background (Linux/macOS)
nohup python run.py &

# Or run as Windows service
# See docs/setup.md for service installation
```

### 5. Subscribe to Notifications
1. Find your bot on Telegram by username
2. Send `/start` to begin
3. Send `/subscribe` to enable notifications
4. Send `/help` to see all available commands

## Available Commands

- `/start` - Initialize bot and get welcome message
- `/help` - Show all available commands and usage
- `/subscribe` - Enable release notifications
- `/unsubscribe` - Disable release notifications  
- `/status` - Check subscription status and bot health
- `/check` - Manually check for new releases now
- `/last_release` - Show details of the latest Claude Code release
- `/preferences` - Configure notification settings (future)

## Project Status

**Current Phase**: 🚧 Repository Setup & Documentation  
**Development Progress**: Planning complete, implementation in progress

This project follows a structured 6-phase implementation plan:
1. ✅ **Repository & Documentation** - Project structure and documentation
2. 🔄 **Core Bot Infrastructure** - Basic Telegram bot functionality  
3. ⏳ **GitHub Integration** - Release monitoring and API integration
4. ⏳ **Notification System** - Rich message formatting and user management
5. ⏳ **Scheduling & Automation** - Automated monitoring and health checks
6. ⏳ **Testing & Documentation** - Comprehensive testing and user guides

**📋 Full Implementation Plan**: See [Implementation Plan](cc-release-monitor-implementation-plan.md) for detailed development roadmap and technical specifications.

## Repository Structure

```
CC-Release-Monitor/
├── src/                          # Main application code
│   ├── bot.py                   # Telegram bot interface and commands
│   ├── github_monitor.py        # GitHub API integration and release detection
│   ├── notifications.py         # Message formatting and delivery
│   ├── config.py                # Configuration management
│   └── utils.py                 # Utility functions and helpers
├── data/                        # Local data storage (auto-created)
│   ├── releases.json           # Release history and version tracking
│   ├── users.json              # User preferences and subscriptions
│   └── config.json             # Runtime configuration
├── tests/                       # Test suite for reliability
├── docs/                        # User and technical documentation
├── requirements.txt             # Python dependencies
├── .env.example                # Environment configuration template
├── run.py                      # Application entry point
└── README.md                   # This file
```

## Why Choose This Approach?

### vs. Cloud-Hosted Solutions
- **No Monthly Costs**: Cloud hosting can cost $5-50+/month for always-on services
- **No Vendor Dependencies**: Your bot won't disappear if a service shuts down
- **Complete Privacy**: No third parties have access to your notification preferences
- **Unlimited Scaling**: Add as many users as you want without per-user fees

### vs. Manual GitHub Checking
- **Automated Monitoring**: Never miss important updates while you're busy
- **Rich Notifications**: Get formatted release notes directly in Telegram
- **Team Coordination**: Keep everyone informed with shared notifications
- **Historical Tracking**: Maintain local history of all releases

### vs. GitHub's Built-in Notifications
- **Telegram Integration**: Notifications where you actually see them
- **Rich Formatting**: Better presentation of release information
- **Customizable Timing**: Control when and how you receive notifications
- **Multi-User Support**: Share notifications with team or family

## Contributing

We welcome contributions to improve the Claude Code Release Monitor! This project is designed for:
- Bug fixes and reliability improvements
- Documentation enhancements
- New notification features and formatting options
- Cross-platform compatibility improvements

**Getting Started with Development**:
1. Read the [Implementation Plan](cc-release-monitor-implementation-plan.md)
2. Check the current project status above
3. Look for open issues or suggest new features
4. Follow the established code structure and testing standards

## Support & Troubleshooting

**Common Issues**:
- **Bot not responding**: Check bot token in `.env` file
- **No notifications**: Verify `/subscribe` was sent and bot is running
- **GitHub rate limits**: Add `GITHUB_API_TOKEN` to `.env` for higher limits
- **Permission errors**: Ensure bot has permission to write to `data/` directory

**Need Help?**:
- Check the logs in the console output
- Use `/status` command to check bot health
- Review configuration in `.env` file
- See full troubleshooting guide in `docs/` folder (coming soon)

## License

This project is designed for personal and team use. Feel free to modify and adapt it for your specific needs while keeping the local-hosting philosophy that makes it cost-effective and privacy-focused.

---

**🏠 Built for Local Hosting** | **💰 Zero Cloud Costs** | **🔒 Complete Privacy Control** | **⚡ Real-Time Notifications**
