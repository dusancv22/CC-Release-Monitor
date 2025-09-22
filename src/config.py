"""
Configuration management for CC Release Monitor.
"""

import os
import logging
from typing import Optional, Any, List
from pathlib import Path
from dotenv import load_dotenv


class ConfigError(Exception):
    """Configuration error exception."""
    pass


class Config:
    """Configuration manager for the CC Release Monitor."""
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            env_file: Path to .env file. If None, uses default .env
        """
        # Load environment variables
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self._validate_required_config()
        self._setup_directories()
    
    def _validate_required_config(self) -> None:
        """Validate that all required configuration is present."""
        required_vars = ["TELEGRAM_BOT_TOKEN"]
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please check your .env file or environment configuration."
            )
    
    def _setup_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        directories = [self.data_directory, self.log_directory]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    @property
    def telegram_bot_token(self) -> str:
        """Get Telegram bot token."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ConfigError("TELEGRAM_BOT_TOKEN is required")
        return token
    
    @property
    def github_api_token(self) -> Optional[str]:
        """Get GitHub API token (optional)."""
        return os.getenv("GITHUB_API_TOKEN")
    
    @property
    def github_repo(self) -> str:
        """Get GitHub repository to monitor."""
        return os.getenv("GITHUB_REPO", "anthropics/claude-code")
    
    @property
    def log_level(self) -> str:
        """Get log level."""
        return os.getenv("LOG_LEVEL", "INFO").upper()
    
    @property
    def check_interval_minutes(self) -> int:
        """Get check interval in minutes."""
        try:
            return int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
        except ValueError:
            logging.warning("Invalid CHECK_INTERVAL_MINUTES, using default: 30")
            return 30
    
    @property
    def max_retries(self) -> int:
        """Get maximum number of retries."""
        try:
            return int(os.getenv("MAX_RETRIES", "3"))
        except ValueError:
            logging.warning("Invalid MAX_RETRIES, using default: 3")
            return 3
    
    @property
    def retry_delay_seconds(self) -> int:
        """Get retry delay in seconds."""
        try:
            return int(os.getenv("RETRY_DELAY_SECONDS", "60"))
        except ValueError:
            logging.warning("Invalid RETRY_DELAY_SECONDS, using default: 60")
            return 60
    
    @property
    def enable_notifications(self) -> bool:
        """Get notification enabled status."""
        return os.getenv("ENABLE_NOTIFICATIONS", "true").lower() in ["true", "1", "yes", "on"]
    
    @property
    def quiet_hours_start(self) -> int:
        """Get quiet hours start time (24-hour format)."""
        try:
            hour = int(os.getenv("QUIET_HOURS_START", "22"))
            if 0 <= hour <= 23:
                return hour
            else:
                logging.warning("Invalid QUIET_HOURS_START, using default: 22")
                return 22
        except ValueError:
            logging.warning("Invalid QUIET_HOURS_START, using default: 22")
            return 22
    
    @property
    def quiet_hours_end(self) -> int:
        """Get quiet hours end time (24-hour format)."""
        try:
            hour = int(os.getenv("QUIET_HOURS_END", "8"))
            if 0 <= hour <= 23:
                return hour
            else:
                logging.warning("Invalid QUIET_HOURS_END, using default: 8")
                return 8
        except ValueError:
            logging.warning("Invalid QUIET_HOURS_END, using default: 8")
            return 8
    
    @property
    def default_timezone(self) -> str:
        """Get default timezone."""
        return os.getenv("DEFAULT_TIMEZONE", "UTC")
    
    @property
    def data_directory(self) -> str:
        """Get data directory path."""
        return os.path.abspath(os.getenv("DATA_DIRECTORY", "./data"))
    
    @property
    def authorized_user_ids(self) -> List[int]:
        """List of Telegram user IDs permitted to use the bot."""
        raw_value = os.getenv("AUTHORIZED_USER_IDS", "")
        if not raw_value:
            return []

        ids: List[int] = []
        for part in raw_value.replace(";", ",").split(','):
            candidate = part.strip()
            if not candidate:
                continue
            try:
                ids.append(int(candidate))
            except ValueError:
                logging.warning("Ignoring invalid Telegram user id in AUTHORIZED_USER_IDS: %s", candidate)
        return ids

    @property
    def log_directory(self) -> str:
        """Get log directory path."""
        return os.path.abspath(os.getenv("LOG_DIRECTORY", "./logs"))
    
    @property
    def backup_enabled(self) -> bool:
        """Get backup enabled status."""
        return os.getenv("BACKUP_ENABLED", "true").lower() in ["true", "1", "yes", "on"]
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return os.getenv(key, default)
    
    def __str__(self) -> str:
        """String representation of config (without sensitive data)."""
        return (
            f"Config("
            f"log_level={self.log_level}, "
            f"check_interval={self.check_interval_minutes}min, "
            f"max_retries={self.max_retries}, "
            f"notifications={self.enable_notifications}, "
            f"data_dir={self.data_directory}, "
            f"log_dir={self.log_directory}"
            f")"
        )
