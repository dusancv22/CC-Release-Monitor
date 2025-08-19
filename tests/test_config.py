"""
Tests for configuration module.
"""

import pytest
import os
from unittest.mock import patch
from src.config import Config, ConfigError


class TestConfig:
    """Test cases for Config class."""
    
    def test_config_with_required_token(self):
        """Test config initialization with required token."""
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            config = Config()
            assert config.telegram_bot_token == 'test_token'
    
    def test_config_missing_required_token(self):
        """Test config initialization without required token."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigError):
                Config()
    
    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            config = Config()
            assert config.log_level == 'INFO'
            assert config.check_interval_minutes == 30
            assert config.max_retries == 3
            assert config.retry_delay_seconds == 60
            assert config.enable_notifications is True
            assert config.quiet_hours_start == 22
            assert config.quiet_hours_end == 8
            assert config.default_timezone == 'UTC'
            assert config.backup_enabled is True
    
    def test_custom_values(self):
        """Test custom configuration values."""
        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'LOG_LEVEL': 'DEBUG',
            'CHECK_INTERVAL_MINUTES': '15',
            'MAX_RETRIES': '5',
            'ENABLE_NOTIFICATIONS': 'false',
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            assert config.log_level == 'DEBUG'
            assert config.check_interval_minutes == 15
            assert config.max_retries == 5
            assert config.enable_notifications is False
    
    def test_invalid_numeric_values(self):
        """Test handling of invalid numeric values."""
        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'CHECK_INTERVAL_MINUTES': 'invalid',
            'MAX_RETRIES': 'not_a_number',
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            # Should fall back to defaults
            assert config.check_interval_minutes == 30
            assert config.max_retries == 3
    
    def test_quiet_hours_validation(self):
        """Test quiet hours validation."""
        env_vars = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'QUIET_HOURS_START': '25',  # Invalid hour
            'QUIET_HOURS_END': '-1',   # Invalid hour
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            # Should fall back to defaults
            assert config.quiet_hours_start == 22
            assert config.quiet_hours_end == 8