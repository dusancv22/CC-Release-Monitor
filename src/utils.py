"""
Utility functions for CC Release Monitor.
"""

import os
import json
import logging
import hashlib
from typing import Any, Dict, Optional, Union, List
from pathlib import Path
from datetime import datetime, timezone
import asyncio


logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO", log_directory: str = "./logs") -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_directory: Directory for log files
    """
    # Create log directory
    Path(log_directory).mkdir(parents=True, exist_ok=True)
    
    # Configure log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Set up file handler
    log_file = Path(log_directory) / f"cc_release_monitor_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logger.info(f"Logging initialized - Level: {log_level}, File: {log_file}")


def load_json_file(file_path: Union[str, Path], default: Any = None) -> Any:
    """
    Load JSON data from file.
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid
        
    Returns:
        Loaded JSON data or default value
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.debug(f"JSON file not found: {file_path}")
        return default
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {e}")
        return default
    except Exception as e:
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return default


def save_json_file(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save
        file_path: Path to save file
        indent: JSON indentation
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {e}")
        return False


def get_file_hash(file_path: Union[str, Path]) -> Optional[str]:
    """
    Get MD5 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        MD5 hash string or None if error
    """
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {file_path}: {e}")
        return None


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid URL, False otherwise
    """
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename for safe file system usage.
    
    Args:
        filename: Original filename
        max_length: Maximum filename length
        
    Returns:
        Sanitized filename
    """
    import re
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()
    return sanitized or "unnamed_file"


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """
    Format datetime object to string.
    
    Args:
        dt: Datetime object
        format_str: Format string
        
    Returns:
        Formatted datetime string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(format_str)


def parse_datetime(dt_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """
    Parse datetime string to datetime object.
    
    Args:
        dt_str: Datetime string
        format_str: Format string
        
    Returns:
        Datetime object or None if parsing fails
    """
    try:
        return datetime.strptime(dt_str, format_str).replace(tzinfo=timezone.utc)
    except ValueError as e:
        logger.error(f"Error parsing datetime '{dt_str}': {e}")
        return None


def get_utc_now() -> datetime:
    """
    Get current UTC datetime.
    
    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def is_quiet_hours(current_hour: int, start_hour: int, end_hour: int) -> bool:
    """
    Check if current time is within quiet hours.
    
    Args:
        current_hour: Current hour (0-23)
        start_hour: Quiet hours start (0-23)
        end_hour: Quiet hours end (0-23)
        
    Returns:
        True if within quiet hours
    """
    if start_hour <= end_hour:
        # Same day quiet hours (e.g., 22:00 to 8:00 next day doesn't apply here)
        return start_hour <= current_hour < end_hour
    else:
        # Overnight quiet hours (e.g., 22:00 to 8:00 next day)
        return current_hour >= start_hour or current_hour < end_hour


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks of specified size.
    
    Args:
        lst: List to split
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


async def retry_async(func, max_retries: int = 3, delay: float = 1.0, 
                     exponential_backoff: bool = True, exceptions: tuple = (Exception,)):
    """
    Retry async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        exponential_backoff: Whether to use exponential backoff
        exceptions: Exceptions to catch and retry on
        
    Returns:
        Function result
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                await asyncio.sleep(current_delay)
                if exponential_backoff:
                    current_delay *= 2
            else:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
    
    if last_exception:
        raise last_exception


def create_backup_filename(original_path: Union[str, Path], suffix: str = "backup") -> Path:
    """
    Create backup filename with timestamp.
    
    Args:
        original_path: Original file path
        suffix: Backup suffix
        
    Returns:
        Backup file path
    """
    original = Path(original_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{original.stem}_{suffix}_{timestamp}{original.suffix}"
    return original.parent / backup_name


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj