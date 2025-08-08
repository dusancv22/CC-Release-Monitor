# PLANNING.md

## Project Overview

The **Claude Code Release Monitor** is a Telegram bot designed to automatically monitor the `anthropics/claude-code` GitHub repository for new releases and send instant notifications to subscribers. The project focuses on local machine deployment without cloud dependencies, providing a reliable, self-hosted solution for developers who want to stay informed about Claude Code updates.

**Key Value Proposition:**
- Automated monitoring eliminates manual checking
- Instant Telegram notifications with rich formatting
- Local deployment ensures privacy and control
- Zero cloud service dependencies or costs
- Configurable notification preferences and scheduling

**Project Goals:**
- Monitor Claude Code releases every 4-6 hours automatically
- Send formatted Telegram notifications with release details
- Maintain version history and detect changes reliably  
- Provide simple local deployment with minimal setup
- Support multiple users with individual preferences

## Technology Stack

### Core Technologies
- **Language**: Python 3.9+
- **Bot Framework**: python-telegram-bot 20.7+
- **HTTP Client**: requests 2.31.0 for GitHub API
- **Scheduling**: schedule 1.2.0 for automated monitoring
- **Configuration**: python-dotenv 1.0.0 for environment management

### Supporting Libraries
```txt
python-telegram-bot==20.7
requests==2.31.0
schedule==1.2.0
python-dotenv==1.0.0
pytest==7.4.0
pytest-cov==4.1.0
black==23.7.0
flake8==6.0.0
```

### Development Tools
- **Testing**: pytest with coverage reporting
- **Code Quality**: black (formatting) + flake8 (linting)
- **Storage**: JSON files for configuration and version tracking
- **Deployment**: Local machine with systemd service or background process
- **Process Management**: Signal handling for graceful shutdown

### Infrastructure
- **Hosting**: Local machine (Windows/Linux/macOS)
- **Storage**: File-based JSON storage (no database required)
- **Network**: GitHub API + Telegram Bot API
- **Security**: Environment variables for API keys

## User Personas

### Primary User: Claude Code Developer
- **Description**: Software developer actively using Claude Code CLI tool
- **Demographics**: Technical professional, familiar with command-line tools
- **Needs**: 
  - Stay updated with latest Claude Code features and fixes
  - Receive notifications without constant manual checking
  - Understand what changed in each release
  - Quick access to download links and changelogs
- **Pain Points**:
  - Missing important updates and bug fixes
  - Manual checking of GitHub releases is time-consuming
  - Difficulty tracking which features are new
  - No centralized notification system
- **Technical Comfort**: High - comfortable with API keys, environment variables, local deployment

### Secondary User: Development Team Manager
- **Description**: Team lead managing developers using Claude Code
- **Needs**:
  - Keep team informed about updates that affect workflows
  - Coordinate team updates to new versions
  - Monitor for security or critical bug fixes
- **Pain Points**:
  - Team members update at different times
  - Lack of visibility into release impact
  - Manual coordination for version updates

## Features

### Completed Features
*(None yet - project in initial planning phase)*

### In-Progress Features
- **Repository Structure**: Setting up project foundation with proper Python package structure (Added 2025-08-08)
- **Documentation Framework**: Creating comprehensive documentation structure (Added 2025-08-08)

### Planned Features

#### Core Functionality
- **GitHub Release Monitoring**: Automated checking of `anthropics/claude-code` releases using GitHub API with rate limiting and error handling (Priority: High)
- **Version Comparison**: Smart detection of new releases with semantic version parsing and change tracking (Priority: High)
- **Telegram Notifications**: Rich formatted messages with release details, changelogs, and download links (Priority: High)
- **Local Data Storage**: JSON-based storage for version history, user preferences, and configuration (Priority: High)

#### User Management
- **User Registration**: `/start` command for user onboarding and subscription setup (Priority: High)
- **Subscription Management**: `/subscribe` and `/unsubscribe` commands for notification control (Priority: Medium)
- **User Preferences**: Configurable notification timing and content filtering (Priority: Medium)
- **Multi-User Support**: Support for multiple subscribers with individual settings (Priority: Medium)

#### Automation & Scheduling
- **Automated Monitoring**: Scheduled checks every 30 minutes (configurable) with background processing (Priority: High)
- **Manual Commands**: `/check`, `/last_release`, and `/status` for immediate information (Priority: Medium)
- **Health Monitoring**: System status reporting and error recovery mechanisms (Priority: Medium)
- **Quiet Hours**: Configurable time periods for notification suppression (Priority: Low)

#### Advanced Features
- **Retry Logic**: Robust error handling with exponential backoff for API failures (Priority: Medium)
- **Rate Limit Management**: GitHub API rate limit tracking and optimization (Priority: Medium)
- **Changelog Parsing**: Automatic extraction and formatting of release notes (Priority: Low)
- **Admin Commands**: Advanced management commands for system maintenance (Priority: Low)

## Architecture

### System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Telegram Bot  │◄───│  Release Monitor │◄───│  GitHub API     │
│   (User Input)  │    │  (Core Logic)    │    │  (Data Source)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Config Files  │    │  Version Storage │    │  Request Cache  │
│   (Settings)    │    │  (JSON File)     │    │  (Rate Limits)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Architecture Principles:**
- **Modularity**: Separate concerns (bot, monitoring, storage, notifications)
- **Reliability**: Robust error handling and graceful degradation
- **Configurability**: Environment-based configuration with sensible defaults
- **Maintainability**: Clean code structure with comprehensive logging

### Database Schema

**File-Based Storage Structure:**

```json
// data/releases.json - Release tracking
{
  "last_checked": "2025-08-08T10:30:00Z",
  "current_version": "v1.2.3",
  "releases": [
    {
      "version": "v1.2.3",
      "published_at": "2025-08-08T10:00:00Z",
      "name": "Release Name",
      "body": "Release notes content...",
      "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.2.3",
      "tarball_url": "https://api.github.com/repos/anthropics/claude-code/tarball/v1.2.3",
      "notified": true
    }
  ]
}

// data/users.json - User management
{
  "users": [
    {
      "chat_id": 123456789,
      "username": "john_doe",
      "subscribed": true,
      "joined_at": "2025-08-08T09:00:00Z",
      "preferences": {
        "quiet_hours": {
          "enabled": true,
          "start": "22:00",
          "end": "08:00",
          "timezone": "UTC"
        },
        "notification_types": ["new_release", "security_updates"],
        "format": "detailed"
      }
    }
  ]
}

// data/config.json - Runtime configuration
{
  "check_interval_minutes": 30,
  "max_retries": 3,
  "retry_delay_seconds": 60,
  "github_api_timeout": 30,
  "telegram_api_timeout": 20,
  "log_level": "INFO",
  "last_startup": "2025-08-08T08:00:00Z"
}
```

### API Structure

**GitHub API Integration:**
- **Primary Endpoint**: `GET /repos/anthropics/claude-code/releases/latest`
- **Secondary Endpoint**: `GET /repos/anthropics/claude-code/releases?per_page=10`
- **Rate Limits**: 60 requests/hour (unauthenticated), 5000 requests/hour (with token)
- **Headers**: `User-Agent`, `Accept`, `Authorization` (optional)

**Telegram Bot API Integration:**
- **Send Message**: `POST /bot{token}/sendMessage`
- **Webhook Support**: Not required (polling-based)
- **Message Formatting**: Markdown v2 for rich formatting
- **Error Handling**: Retry logic for failed message delivery

### Routing

**Bot Command Structure:**
```
/start          - User registration and welcome message
/help           - Command help and usage instructions  
/subscribe      - Enable release notifications
/unsubscribe    - Disable release notifications
/status         - Show subscription and system status
/check          - Manually trigger release check
/last_release   - Show information about latest release
/preferences    - Configure notification preferences
/version        - Show bot version and uptime
```

**Internal Module Routing:**
- `bot.py` → Handles all Telegram interactions and command routing
- `github_monitor.py` → Manages GitHub API calls and release detection
- `scheduler.py` → Controls automated monitoring timing and execution
- `notifications.py` → Formats and sends notification messages
- `storage.py` → Handles all file-based data persistence

### State Management

**In-Memory State:**
- Current bot instance and handlers
- Active scheduled jobs and timers
- GitHub API rate limit tracking
- User session data (temporary)

**Persistent State:**
- Release version history (JSON file)
- User subscriptions and preferences (JSON file)
- Configuration settings (JSON file)
- Error logs and system health data (log files)

**State Synchronization:**
- Atomic file writes for data consistency
- File locking for concurrent access protection
- Backup creation before updates
- Validation on state load/save operations

## Authentication System

### Telegram Bot Authentication
- **Bot Token**: Secure token from @BotFather stored in environment variables
- **Chat ID Validation**: Verification of authorized users for sensitive commands
- **Command Authorization**: Basic rate limiting per user to prevent spam

### GitHub API Authentication  
- **Optional Token**: Personal access token for higher rate limits (5000 vs 60 requests/hour)
- **Public Repository Access**: No authentication required for basic release monitoring
- **Rate Limit Headers**: Monitoring of `X-RateLimit-Remaining` and `X-RateLimit-Reset`

### Security Measures
- **Environment Variables**: All sensitive tokens stored in `.env` file (not in repository)
- **Input Validation**: Sanitization of all user inputs and API responses
- **Error Message Filtering**: No sensitive information exposed in error messages
- **File Permissions**: Restricted access to data files (600 permissions on Unix systems)

## UI/UX Patterns

### Message Formatting Standards
```markdown
🚀 **New Claude Code Release!**

**Version:** `v1.2.3`
**Released:** January 15, 2024 10:30 UTC

📋 **What's New:**
• Improved error handling in code generation
• Enhanced syntax highlighting support
• Bug fixes for Windows compatibility

🔗 **Quick Links:**
• [Download Release](https://github.com/anthropics/claude-code/releases/tag/v1.2.3)
• [Full Changelog](https://github.com/anthropics/claude-code/releases/tag/v1.2.3)
• [Installation Guide](https://docs.claude.ai/installation)

---
💡 Use `/unsubscribe` to stop notifications
```

### Command Response Patterns
- **Success Responses**: ✅ Confirmation with specific action taken
- **Error Responses**: ❌ Clear error description with suggested resolution  
- **Status Responses**: 📊 Structured information with current state
- **Help Responses**: 💡 Actionable instructions with examples

### User Interaction Flow
1. **Initial Setup**: `/start` → Welcome + auto-subscription prompt
2. **Regular Usage**: Passive notifications + occasional manual `/check`
3. **Preference Changes**: `/preferences` → Interactive configuration
4. **Problem Resolution**: Error notification → `/status` → troubleshooting

## Business Rules

### Release Detection Logic
- **New Release Criteria**: Version tag differs from stored latest version
- **Version Parsing**: Semantic versioning support (major.minor.patch)
- **Pre-release Handling**: Optional inclusion of beta/alpha releases
- **Duplicate Prevention**: Track notified releases to prevent duplicate notifications

### Notification Rules
- **Timing**: Respect user quiet hours (22:00-08:00 local time by default)
- **Frequency**: Maximum one notification per release per user
- **Priority**: Critical security updates bypass quiet hours
- **Throttling**: Maximum 1 notification per minute per user to prevent spam

### Data Retention
- **Release History**: Keep last 50 releases for comparison and history
- **User Data**: Retain preferences and subscription status indefinitely
- **Logs**: Rotate logs daily, keep 30 days of history
- **Error Data**: Keep error logs for 7 days for debugging

### Error Handling Policies
- **GitHub API Failures**: Retry up to 3 times with exponential backoff
- **Telegram API Failures**: Queue messages for retry (up to 24 hours)
- **Storage Failures**: Create backups before write operations
- **System Failures**: Log errors and continue operation when possible

## Integration Points

### External APIs
- **GitHub Releases API**
  - Endpoint: `api.github.com/repos/anthropics/claude-code/releases`
  - Purpose: Release monitoring and version detection
  - Rate Limits: 60/hour (unauthenticated), 5000/hour (authenticated)
  - Error Handling: Exponential backoff, fallback to cached data

- **Telegram Bot API**
  - Endpoint: `api.telegram.org/bot{token}/`
  - Purpose: Message sending and command handling
  - Rate Limits: 30 messages/second per bot
  - Error Handling: Message queuing, retry logic

### System Integrations
- **Operating System Services**
  - Systemd (Linux): Service management and auto-restart
  - Task Scheduler (Windows): Background process execution
  - Launchd (macOS): Daemon management and scheduling

- **File System**
  - Configuration files: Environment variables, JSON settings
  - Data storage: Release history, user preferences
  - Logging: Structured logs with rotation and archival

## Performance Considerations

### Optimization Strategies
- **API Caching**: Cache GitHub API responses for 5 minutes to reduce calls
- **Conditional Requests**: Use `If-Modified-Since` headers when supported
- **Batch Processing**: Process multiple users in single notification cycle
- **Memory Management**: Periodic cleanup of cached data and logs

### Resource Usage Targets
- **Memory**: < 50MB resident memory usage
- **CPU**: < 5% CPU usage during idle periods
- **Storage**: < 10MB for data files (excluding logs)
- **Network**: < 1MB/day bandwidth usage under normal operation

### Monitoring Metrics
- **Response Times**: GitHub API calls < 2 seconds, Telegram API < 5 seconds
- **Success Rates**: >99% for notification delivery, >95% for release detection
- **Uptime**: >99.5% availability (excluding maintenance windows)
- **Error Rates**: <1% error rate for all API operations

## Environment Variables

### Required Configuration
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# GitHub API Configuration (Optional)
GITHUB_API_TOKEN=your_github_personal_access_token

# Application Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
CHECK_INTERVAL_MINUTES=30         # Release check frequency
MAX_RETRIES=3                     # API retry attempts
RETRY_DELAY_SECONDS=60            # Delay between retries

# Notification Configuration
ENABLE_NOTIFICATIONS=true         # Global notification toggle
QUIET_HOURS_START=22              # Hour (0-23) to start quiet period
QUIET_HOURS_END=8                 # Hour (0-23) to end quiet period
DEFAULT_TIMEZONE=UTC              # Default timezone for new users

# Storage Configuration
DATA_DIRECTORY=./data             # Directory for data files
LOG_DIRECTORY=./logs              # Directory for log files
BACKUP_ENABLED=true               # Enable automatic backups
```

### Optional Configuration
```env
# Advanced Features
ADMIN_CHAT_ID=your_telegram_chat_id  # Admin notifications
WEBHOOK_URL=                         # Optional webhook endpoint
METRICS_ENABLED=false                # Enable metrics collection
SENTRY_DSN=                          # Error tracking service

# Development Settings
DEBUG_MODE=false                     # Enable debug logging
MOCK_GITHUB_API=false               # Use mock responses for testing
DISABLE_SCHEDULING=false            # Disable automated checks
```

## Testing Strategy

### Unit Testing (Target: >90% Coverage)
- **Module Testing**: Individual function and class testing for all core modules
- **Mock Integration**: Mock external APIs for isolated testing
- **Edge Cases**: Error conditions, rate limits, invalid data
- **Data Validation**: Configuration parsing, JSON schema validation

### Integration Testing
- **GitHub API Integration**: Real API calls with test repository
- **Telegram Bot Integration**: Message sending and command processing
- **File System Integration**: Data persistence and configuration loading
- **Error Scenario Testing**: Network failures, API downtime, invalid responses

### End-to-End Testing
- **Complete Workflow**: Release detection → notification delivery → user interaction
- **Multi-User Scenarios**: Multiple subscribers with different preferences
- **Long-Running Tests**: 24-hour stability testing with scheduled checks
- **Performance Testing**: Memory leaks, CPU usage under load

### Testing Frameworks and Tools
```txt
pytest==7.4.0              # Test framework
pytest-cov==4.1.0          # Coverage reporting
pytest-mock==3.11.1        # Mocking utilities
pytest-asyncio==0.21.1     # Async test support
responses==0.23.3          # HTTP request mocking
freezegun==1.2.2           # Time mocking for scheduling tests
```

## Deployment

### Local Machine Setup
1. **Environment Preparation**
   ```bash
   # Install Python 3.9+
   python --version
   
   # Clone repository
   git clone <repository_url>
   cd CC-Release-Monitor
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Configure environment
   cp .env.example .env
   # Edit .env with your tokens
   ```

2. **Service Installation** (Linux/systemd)
   ```ini
   [Unit]
   Description=Claude Code Release Monitor
   After=network.target
   
   [Service]
   Type=simple
   User=your_username
   WorkingDirectory=/path/to/CC-Release-Monitor
   ExecStart=/usr/bin/python3 run.py
   Restart=always
   RestartSec=10
   Environment=PYTHONPATH=/path/to/CC-Release-Monitor
   
   [Install]
   WantedBy=multi-user.target
   ```

3. **Windows Service Setup**
   - Use Task Scheduler for automated startup
   - Configure as background task with system account
   - Set restart policies for failure recovery

### Project File Structure
```
CC-Release-Monitor/
├── src/
│   ├── __init__.py
│   ├── bot.py                    # Main bot class and command handlers
│   ├── github_monitor.py         # GitHub API integration and release detection
│   ├── config.py                 # Configuration management and validation
│   ├── notifications.py          # Message formatting and delivery
│   ├── scheduler.py              # Task scheduling and automation
│   ├── storage.py                # Data persistence and file management
│   └── utils.py                  # Utility functions and helpers
├── tests/
│   ├── __init__.py
│   ├── test_bot.py               # Bot functionality tests
│   ├── test_github_monitor.py    # GitHub integration tests
│   ├── test_notifications.py     # Notification system tests
│   ├── test_storage.py           # Data persistence tests
│   └── fixtures/                 # Test data and mock responses
├── data/                         # Runtime data (created automatically)
│   ├── releases.json             # Release history and version tracking
│   ├── users.json                # User subscriptions and preferences
│   └── config.json               # Runtime configuration
├── logs/                         # Application logs (created automatically)
├── docs/
│   ├── setup.md                  # Installation and setup guide
│   ├── user-guide.md             # User manual and commands
│   └── api-reference.md          # Technical API documentation
├── deploy/
│   ├── systemd/                  # Linux service files
│   ├── windows/                  # Windows service configuration
│   └── docker/                   # Optional containerization (future)
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
├── .gitignore                    # Git ignore patterns
├── README.md                     # Project overview and quick start
├── PLANNING.md                   # This comprehensive planning document
└── run.py                        # Application entry point
```

### Deployment Checklist
- [ ] Python 3.9+ installed and verified
- [ ] All dependencies installed via requirements.txt
- [ ] Environment variables configured in .env file
- [ ] Telegram bot token obtained and tested
- [ ] GitHub API token configured (optional but recommended)
- [ ] Data directory permissions set correctly (600 on Unix)
- [ ] Service/scheduler configuration completed
- [ ] Initial test run successful (`python run.py --test`)
- [ ] Automated startup configured and tested
- [ ] Log rotation and monitoring configured

## Constraints & Non-Goals

### Project Constraints
- **No Cloud Dependencies**: Must run entirely on local machine without external hosting
- **Single Repository Focus**: Only monitors `anthropics/claude-code`, not extensible to other repositories
- **File-Based Storage**: No database server required, all data in JSON files
- **Python Ecosystem**: Implementation must use Python 3.9+ and standard libraries
- **Resource Limits**: Must operate within reasonable resource constraints for personal machines

### Technical Limitations
- **Network Dependency**: Requires stable internet connection for GitHub and Telegram APIs
- **Local Storage**: Data limited by local disk space (though minimal usage expected)
- **Rate Limits**: Subject to GitHub API rate limits (5000/hour with token, 60/hour without)
- **Single Process**: No multi-process or distributed architecture

### Explicit Non-Goals
- **Multi-Repository Monitoring**: Will not support monitoring multiple GitHub repositories
- **Web Interface**: No web-based management interface or dashboard
- **Database Storage**: Will not implement database storage (PostgreSQL, SQLite, etc.)
- **Cloud Deployment**: No support for AWS, Azure, GCP, or other cloud platforms
- **Mobile App**: No mobile application or responsive web interface
- **Advanced Analytics**: No release trend analysis, statistics, or reporting features
- **Integration with CI/CD**: No integration with GitHub Actions, Jenkins, or other CI/CD systems
- **Custom Release Filtering**: No advanced filtering based on release content, size, or metadata
- **Multi-Language Support**: Interface will be English-only
- **High Availability**: No failover, load balancing, or distributed deployment
- **Enterprise Features**: No multi-tenant support, SSO, or enterprise management

### Scope Boundaries
- **User Management**: Basic subscription management only, no advanced user roles or permissions
- **Notification Channels**: Telegram only, no email, SMS, Discord, or other notification methods
- **Release Processing**: Basic version detection only, no changelog analysis or impact assessment
- **System Integration**: Basic local deployment only, no system package management or automatic updates

## Development Guidelines

### Coding Standards
- **Style Guide**: Follow PEP 8 Python style guide with black formatting
- **Line Length**: Maximum 88 characters (black default)
- **Import Organization**: isort for consistent import sorting
- **Documentation**: Docstrings for all public functions and classes using Google style
- **Type Hints**: Use type hints for all function parameters and return values

### Code Quality Requirements
```python
# Example function with proper documentation and type hints
async def check_for_new_release(github_client: GitHubClient) -> Optional[Release]:
    """
    Check GitHub API for new Claude Code releases.
    
    Args:
        github_client: Configured GitHub API client instance
        
    Returns:
        Release object if new release found, None otherwise
        
    Raises:
        GitHubAPIError: If API request fails after all retries
        RateLimitExceededError: If rate limit exceeded
    """
    try:
        latest_release = await github_client.get_latest_release()
        return latest_release if self._is_new_release(latest_release) else None
    except Exception as e:
        logger.error(f"Failed to check for release: {e}")
        raise
```

### Version Control Practices
- **Branch Strategy**: Main branch for production-ready code, feature branches for development
- **Commit Messages**: Conventional commit format (feat:, fix:, docs:, refactor:, test:)
- **Pull Requests**: Required for all changes with code review
- **Tags**: Semantic versioning for releases (v1.0.0, v1.1.0, etc.)

### Testing Requirements
- **Coverage**: Minimum 90% test coverage for all modules
- **Test Types**: Unit tests, integration tests, and end-to-end tests
- **Mock Usage**: Mock external APIs and services in unit tests
- **Test Data**: Use fixtures and factories for consistent test data
- **Continuous Testing**: Run tests on every commit and pull request

### Error Handling Patterns
```python
# Standard error handling pattern
try:
    result = await api_call()
    return result
except SpecificAPIError as e:
    logger.warning(f"API error occurred: {e}")
    # Implement specific recovery logic
    return fallback_response()
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    # Implement general error handling
    raise ServiceError(f"Operation failed: {e}") from e
```

### Logging Standards
```python
import logging

# Use structured logging with consistent format
logger = logging.getLogger(__name__)

# Log levels usage:
logger.debug("Detailed information for debugging")
logger.info("General information about operation")
logger.warning("Something unexpected but recoverable happened")  
logger.error("Error that prevented operation completion")
logger.critical("Serious error that may cause system failure")
```

### Configuration Management
- **Environment Variables**: Use for all configuration with sensible defaults
- **Configuration Validation**: Validate all configuration on startup
- **Documentation**: Document all configuration options with examples
- **Sensitive Data**: Never commit API keys, tokens, or credentials

### Performance Guidelines
- **Async Operations**: Use asyncio for I/O bound operations (API calls)
- **Caching**: Implement appropriate caching for frequently accessed data
- **Resource Cleanup**: Proper cleanup of resources (files, network connections)
- **Memory Usage**: Monitor and optimize memory usage for long-running processes

---

*Document created: 2025-08-08*  
*Last updated: 2025-08-08*  
*Version: 1.0.0*  
*Status: Initial comprehensive planning phase*