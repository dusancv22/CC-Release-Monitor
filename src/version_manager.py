"""
Version management for CC Release Monitor.
"""

import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime, timezone

from .config import Config
from .utils import load_json_file, save_json_file, get_utc_now

logger = logging.getLogger(__name__)


class VersionError(Exception):
    """Version management error exception."""
    pass


class SemanticVersion:
    """Semantic version parser and comparator."""
    
    def __init__(self, version_string: str):
        """
        Initialize semantic version.
        
        Args:
            version_string: Version string (e.g., "1.2.3", "v1.2.3-beta.1")
        """
        self.original = version_string
        self.clean = self._clean_version(version_string)
        self.major, self.minor, self.patch, self.prerelease, self.build = self._parse_version(self.clean)
    
    def _clean_version(self, version: str) -> str:
        """Clean version string by removing common prefixes."""
        # Remove 'v' prefix
        if version.lower().startswith('v'):
            version = version[1:]
        return version.strip()
    
    def _parse_version(self, version: str) -> Tuple[int, int, int, Optional[str], Optional[str]]:
        """
        Parse semantic version into components.
        
        Returns:
            Tuple of (major, minor, patch, prerelease, build)
        """
        # Regex for semantic versioning
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$'
        match = re.match(pattern, version)
        
        if not match:
            # Try simpler pattern for non-standard versions
            simple_pattern = r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?'
            simple_match = re.match(simple_pattern, version)
            
            if simple_match:
                major = int(simple_match.group(1))
                minor = int(simple_match.group(2) or 0)
                patch = int(simple_match.group(3) or 0)
                return major, minor, patch, None, None
            else:
                raise VersionError(f"Invalid version format: {version}")
        
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease = match.group(4)
        build = match.group(5)
        
        return major, minor, patch, prerelease, build
    
    def __str__(self) -> str:
        """String representation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    def __repr__(self) -> str:
        """Representation."""
        return f"SemanticVersion('{self.original}')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if not isinstance(other, SemanticVersion):
            return False
        return (self.major, self.minor, self.patch, self.prerelease) == \
               (other.major, other.minor, other.patch, other.prerelease)
    
    def __lt__(self, other) -> bool:
        """Less than comparison."""
        if not isinstance(other, SemanticVersion):
            raise TypeError("Cannot compare SemanticVersion with other types")
        
        # Compare major.minor.patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        
        # Handle prerelease versions
        if self.prerelease is None and other.prerelease is None:
            return False  # Equal
        if self.prerelease is None and other.prerelease is not None:
            return False  # Release > prerelease
        if self.prerelease is not None and other.prerelease is None:
            return True   # prerelease < release
        
        # Both have prerelease, compare lexically
        return self.prerelease < other.prerelease
    
    def __le__(self, other) -> bool:
        """Less than or equal comparison."""
        return self < other or self == other
    
    def __gt__(self, other) -> bool:
        """Greater than comparison."""
        return not self <= other
    
    def __ge__(self, other) -> bool:
        """Greater than or equal comparison."""
        return not self < other
    
    def is_prerelease(self) -> bool:
        """Check if this is a prerelease version."""
        return self.prerelease is not None
    
    def is_stable(self) -> bool:
        """Check if this is a stable version."""
        return self.prerelease is None


class VersionManager:
    """Manages version tracking and comparison."""
    
    def __init__(self, config: Config):
        """
        Initialize version manager.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.data_file = Path(config.data_directory) / "version_data.json"
        self.history_file = Path(config.data_directory) / "version_history.json"
        
        # Ensure data directory exists
        Path(config.data_directory).mkdir(parents=True, exist_ok=True)
        
        self._version_data = self._load_version_data()
        self._history = self._load_history()
        
        # Monitoring state
        self.monitoring_active = False
    
    def _load_version_data(self) -> Dict[str, Any]:
        """Load version data from file."""
        default_data = {
            "last_known_version": None,
            "last_check_time": None,
            "last_release_data": None,
            "check_count": 0,
            "last_notification_sent": None,
            "last_known_commit_sha": None,
            "last_commit_data": None,
            "commit_check_count": 0,
            "last_known_changelog_hash": None,
            "last_changelog_content": None,
            "changelog_check_count": 0
        }
        
        data = load_json_file(self.data_file, default_data)
        logger.debug(f"Loaded version data: {data.get('last_known_version', 'None')}, commit: {data.get('last_known_commit_sha', 'None')}")
        return data
    
    def _save_version_data(self) -> bool:
        """Save version data to file."""
        success = save_json_file(self._version_data, self.data_file)
        if success:
            logger.debug(f"Saved version data: {self._version_data.get('last_known_version', 'None')}")
        return success
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load version history from file."""
        history = load_json_file(self.history_file, [])
        if not isinstance(history, list):
            logger.warning("Invalid history data, starting fresh")
            return []
        return history
    
    def _save_history(self) -> bool:
        """Save version history to file."""
        return save_json_file(self._history, self.history_file)
    
    def _add_to_history(self, version: str, release_data: Dict[str, Any], 
                       check_time: datetime, is_new: bool = False) -> None:
        """
        Add entry to version history.
        
        Args:
            version: Version string
            release_data: Release data from GitHub
            check_time: Time of check
            is_new: Whether this is a new version
        """
        entry = {
            "version": version,
            "check_time": check_time.isoformat(),
            "is_new": is_new,
            "release_date": release_data.get("published_at"),
            "release_url": release_data.get("html_url"),
            "prerelease": release_data.get("prerelease", False),
            "tag_name": release_data.get("tag_name"),
            "name": release_data.get("name")
        }
        
        self._history.append(entry)
        
        # Keep only last 100 entries
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        self._save_history()
        logger.debug(f"Added to history: {version} (new: {is_new})")
    
    def update_version(self, release_data: Dict[str, Any]) -> bool:
        """
        Update version information with new release data.
        
        Args:
            release_data: Release data from GitHub API
            
        Returns:
            True if this is a new version, False if same or older
        """
        current_time = get_utc_now()
        tag_name = release_data.get("tag_name")
        
        if not tag_name:
            logger.warning("No tag_name in release data")
            return False
        
        try:
            new_version = SemanticVersion(tag_name)
        except VersionError as e:
            logger.error(f"Failed to parse version {tag_name}: {e}")
            return False
        
        self._version_data["last_check_time"] = current_time.isoformat()
        self._version_data["check_count"] += 1
        
        last_known = self._version_data.get("last_known_version")
        is_new_version = False
        
        if last_known is None:
            # First time checking
            logger.info(f"First version detected: {new_version}")
            is_new_version = True
        else:
            try:
                last_version = SemanticVersion(last_known)
                if new_version > last_version:
                    logger.info(f"New version detected: {last_version} -> {new_version}")
                    is_new_version = True
                elif new_version < last_version:
                    logger.warning(f"Version went backwards: {last_version} -> {new_version}")
                else:
                    logger.debug(f"No version change: {new_version}")
            except VersionError as e:
                logger.error(f"Failed to parse last known version {last_known}: {e}")
                is_new_version = True  # Assume new if we can't compare
        
        # Update stored data
        if is_new_version or last_known is None:
            self._version_data["last_known_version"] = str(new_version)
            self._version_data["last_release_data"] = release_data
        
        # Always update latest release data for reference
        self._version_data["latest_release_data"] = release_data
        
        # Save data
        self._save_version_data()
        
        # Add to history
        self._add_to_history(str(new_version), release_data, current_time, is_new_version)
        
        return is_new_version
    
    def get_last_known_version(self) -> Optional[str]:
        """Get the last known version."""
        return self._version_data.get("last_known_version")
    
    def get_last_release_data(self) -> Optional[Dict[str, Any]]:
        """Get the last release data."""
        return self._version_data.get("last_release_data")
    
    def get_latest_release_data(self) -> Optional[Dict[str, Any]]:
        """Get the latest release data (may be same as last known)."""
        return self._version_data.get("latest_release_data")
    
    def compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
            
        Raises:
            VersionError: If version strings are invalid
        """
        v1 = SemanticVersion(version1)
        v2 = SemanticVersion(version2)
        
        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        else:
            return 0
    
    def is_newer_version(self, version: str, compare_to: Optional[str] = None) -> bool:
        """
        Check if given version is newer than comparison version.
        
        Args:
            version: Version to check
            compare_to: Version to compare against (defaults to last known version)
            
        Returns:
            True if version is newer
        """
        if compare_to is None:
            compare_to = self.get_last_known_version()
        
        if compare_to is None:
            return True  # Any version is "newer" than no version
        
        try:
            return self.compare_versions(version, compare_to) > 0
        except VersionError:
            return False
    
    def get_version_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get version history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of history entries (most recent first)
        """
        history = list(reversed(self._history))  # Most recent first
        if limit:
            history = history[:limit]
        return history
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get version management statistics.
        
        Returns:
            Statistics dictionary
        """
        last_check = self._version_data.get("last_check_time")
        last_check_dt = None
        if last_check:
            try:
                last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        new_versions = sum(1 for entry in self._history if entry.get("is_new", False))
        
        return {
            "last_known_version": self.get_last_known_version(),
            "last_check_time": last_check,
            "check_count": self._version_data.get("check_count", 0),
            "total_history_entries": len(self._history),
            "new_versions_detected": new_versions,
            "data_file_exists": self.data_file.exists(),
            "history_file_exists": self.history_file.exists(),
            "time_since_last_check": (
                (get_utc_now() - last_check_dt).total_seconds() 
                if last_check_dt else None
            )
        }
    
    def mark_notification_sent(self, version: str) -> None:
        """
        Mark that notification was sent for a version.
        
        Args:
            version: Version for which notification was sent
        """
        self._version_data["last_notification_sent"] = {
            "version": version,
            "time": get_utc_now().isoformat()
        }
        self._save_version_data()
        logger.debug(f"Marked notification sent for version: {version}")
    
    def was_notification_sent(self, version: str) -> bool:
        """
        Check if notification was already sent for a version.
        
        Args:
            version: Version to check
            
        Returns:
            True if notification was already sent
        """
        last_notification = self._version_data.get("last_notification_sent")
        if not last_notification:
            return False
        
        return last_notification.get("version") == version
    
    def update_commit(self, commit_data: Dict[str, Any]) -> bool:
        """
        Update commit information with new commit data.
        
        Args:
            commit_data: Commit data from GitHub API
            
        Returns:
            True if this is a new commit, False if same or older
        """
        current_time = get_utc_now()
        commit_sha = commit_data.get("sha")
        
        if not commit_sha:
            logger.warning("No SHA in commit data")
            return False
        
        self._version_data["last_check_time"] = current_time.isoformat()
        self._version_data["commit_check_count"] = self._version_data.get("commit_check_count", 0) + 1
        
        last_known_sha = self._version_data.get("last_known_commit_sha")
        is_new_commit = False
        
        if last_known_sha is None:
            # First time checking commits
            logger.info(f"First commit detected: {commit_sha[:8]}")
            is_new_commit = True
        elif last_known_sha != commit_sha:
            # New commit detected
            logger.info(f"New commit detected: {last_known_sha[:8] if last_known_sha else 'None'} -> {commit_sha[:8]}")
            is_new_commit = True
        else:
            logger.debug(f"No new commits: {commit_sha[:8]}")
        
        # Update stored data
        if is_new_commit or last_known_sha is None:
            self._version_data["last_known_commit_sha"] = commit_sha
            self._version_data["last_commit_data"] = commit_data
        
        # Always update latest commit data for reference
        self._version_data["latest_commit_data"] = commit_data
        
        # Save data
        self._save_version_data()
        
        # Add to history
        self._add_commit_to_history(commit_sha, commit_data, current_time, is_new_commit)
        
        return is_new_commit

    def _add_commit_to_history(self, commit_sha: str, commit_data: Dict[str, Any], 
                              check_time: datetime, is_new: bool = False) -> None:
        """
        Add commit entry to version history.
        
        Args:
            commit_sha: Commit SHA
            commit_data: Commit data from GitHub
            check_time: Time of check
            is_new: Whether this is a new commit
        """
        commit_info = commit_data.get('commit', {})
        author_info = commit_info.get('author', {})
        
        entry = {
            "type": "commit",
            "commit_sha": commit_sha,
            "short_sha": commit_sha[:8],
            "check_time": check_time.isoformat(),
            "is_new": is_new,
            "message": commit_info.get('message', ''),
            "author_name": author_info.get('name', ''),
            "author_date": author_info.get('date'),
            "commit_url": commit_data.get('html_url'),
            "github_author": commit_data.get('author', {}).get('login', '') if commit_data.get('author') else ''
        }
        
        self._history.append(entry)
        
        # Keep only last 100 entries
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        self._save_history()
        logger.debug(f"Added commit to history: {commit_sha[:8]} (new: {is_new})")

    def get_last_known_commit_sha(self) -> Optional[str]:
        """Get the last known commit SHA."""
        return self._version_data.get("last_known_commit_sha")

    def get_last_commit_data(self) -> Optional[Dict[str, Any]]:
        """Get the last commit data."""
        return self._version_data.get("last_commit_data")

    def get_latest_commit_data(self) -> Optional[Dict[str, Any]]:
        """Get the latest commit data (may be same as last known)."""
        return self._version_data.get("latest_commit_data")

    def get_commit_statistics(self) -> Dict[str, Any]:
        """
        Get commit tracking statistics.
        
        Returns:
            Statistics dictionary
        """
        last_check = self._version_data.get("last_check_time")
        last_check_dt = None
        if last_check:
            try:
                last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        commit_entries = [entry for entry in self._history if entry.get('type') == 'commit']
        new_commits = sum(1 for entry in commit_entries if entry.get("is_new", False))
        
        return {
            "last_known_commit_sha": self.get_last_known_commit_sha(),
            "last_commit_check_time": last_check,
            "commit_check_count": self._version_data.get("commit_check_count", 0),
            "total_commit_entries": len(commit_entries),
            "new_commits_detected": new_commits,
            "time_since_last_commit_check": (
                (get_utc_now() - last_check_dt).total_seconds() 
                if last_check_dt else None
            )
        }

    def reset_data(self, keep_history: bool = True) -> bool:
        """
        Reset version data.
        
        Args:
            keep_history: Whether to keep version history
            
        Returns:
            True if reset was successful
        """
        try:
            # Reset main data
            self._version_data = {
                "last_known_version": None,
                "last_check_time": None,
                "last_release_data": None,
                "check_count": 0,
                "last_notification_sent": None,
                "last_known_commit_sha": None,
                "last_commit_data": None,
                "commit_check_count": 0,
                "last_known_changelog_hash": None,
                "last_changelog_content": None,
                "changelog_check_count": 0,
                "monitoring_active": False
            }
            
            if not keep_history:
                self._history = []
                self._save_history()
            
            success = self._save_version_data()
            
            if success:
                logger.info(f"Version data reset (history kept: {keep_history})")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to reset version data: {e}")
            return False

    def update_changelog(self, changelog_content: str) -> bool:
        """
        Update changelog tracking with new content.
        
        Args:
            changelog_content: Full CHANGELOG.md content
            
        Returns:
            True if this is new changelog content, False if same as before
        """
        import hashlib
        
        current_time = get_utc_now()
        
        # Calculate content hash for change detection
        content_hash = hashlib.md5(changelog_content.encode('utf-8')).hexdigest()
        
        self._version_data["last_check_time"] = current_time.isoformat()
        self._version_data["changelog_check_count"] = self._version_data.get("changelog_check_count", 0) + 1
        
        last_known_hash = self._version_data.get("last_known_changelog_hash")
        is_new_changelog = False
        
        if last_known_hash is None:
            # First time checking changelog
            logger.info("First changelog content detected")
            is_new_changelog = True
        elif last_known_hash != content_hash:
            # Changelog content changed
            logger.info("New changelog content detected")
            is_new_changelog = True
        else:
            logger.debug("No changelog changes detected")
        
        # Update stored data
        if is_new_changelog or last_known_hash is None:
            self._version_data["last_known_changelog_hash"] = content_hash
            self._version_data["last_changelog_content"] = changelog_content
        
        # Save data
        self._save_version_data()
        
        # Add to history
        self._add_changelog_to_history(content_hash, changelog_content, current_time, is_new_changelog)
        
        return is_new_changelog

    def _add_changelog_to_history(self, content_hash: str, changelog_content: str, 
                                 check_time: datetime, is_new: bool = False) -> None:
        """
        Add changelog entry to history.
        
        Args:
            content_hash: Hash of changelog content
            changelog_content: Changelog content
            check_time: Time of check
            is_new: Whether this is new changelog content
        """
        # Extract first few entries for preview
        changelog_lines = changelog_content.split('\n')
        preview_lines = []
        entry_count = 0
        
        for line in changelog_lines[:50]:  # First 50 lines
            line = line.strip()
            if line:
                preview_lines.append(line)
                # Count version entries
                if ((line.startswith('##') and ('v' in line.lower() or 'version' in line.lower() or 
                   any(char.isdigit() for char in line))) or
                   (line.startswith('#') and line.count('#') <= 2 and 
                   ('v' in line.lower() or 'version' in line.lower() or 
                   any(char.isdigit() for char in line)))):
                    entry_count += 1
                    if entry_count >= 3:  # Stop after finding 3 version entries
                        break
        
        preview = '\n'.join(preview_lines)
        
        entry = {
            "type": "changelog",
            "content_hash": content_hash,
            "short_hash": content_hash[:8],
            "check_time": check_time.isoformat(),
            "is_new": is_new,
            "preview": preview[:500] + '...' if len(preview) > 500 else preview,
            "content_length": len(changelog_content),
            "version_entries_found": entry_count
        }
        
        self._history.append(entry)
        
        # Keep only last 100 entries
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        self._save_history()
        logger.debug(f"Added changelog to history: {content_hash[:8]} (new: {is_new})")

    def get_last_known_changelog_hash(self) -> Optional[str]:
        """Get the last known changelog content hash."""
        return self._version_data.get("last_known_changelog_hash")

    def get_last_changelog_content(self) -> Optional[str]:
        """Get the last known changelog content."""
        return self._version_data.get("last_changelog_content")

    def get_changelog_statistics(self) -> Dict[str, Any]:
        """
        Get changelog tracking statistics.
        
        Returns:
            Statistics dictionary
        """
        last_check = self._version_data.get("last_check_time")
        last_check_dt = None
        if last_check:
            try:
                last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        changelog_entries = [entry for entry in self._history if entry.get('type') == 'changelog']
        new_changelog_updates = sum(1 for entry in changelog_entries if entry.get("is_new", False))
        
        return {
            "last_known_changelog_hash": self.get_last_known_changelog_hash(),
            "last_changelog_check_time": last_check,
            "changelog_check_count": self._version_data.get("changelog_check_count", 0),
            "total_changelog_entries": len(changelog_entries),
            "new_changelog_updates_detected": new_changelog_updates,
            "last_changelog_content_length": len(self.get_last_changelog_content() or ''),
            "time_since_last_changelog_check": (
                (get_utc_now() - last_check_dt).total_seconds() 
                if last_check_dt else None
            )
        }

    def set_monitoring_active(self, active: bool) -> None:
        """
        Set monitoring active state.
        
        Args:
            active: Whether monitoring should be active
        """
        self.monitoring_active = active
        self._version_data["monitoring_active"] = active
        self._version_data["monitoring_state_changed"] = get_utc_now().isoformat()
        self._save_version_data()
        logger.info(f"Monitoring state changed to: {active}")

    def is_monitoring_active(self) -> bool:
        """
        Check if monitoring is currently active.
        
        Returns:
            True if monitoring is active
        """
        # Check both memory state and persisted state
        persisted_state = self._version_data.get("monitoring_active", False)
        return self.monitoring_active or persisted_state

    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Statistics dictionary
        """
        state_changed = self._version_data.get("monitoring_state_changed")
        state_changed_dt = None
        if state_changed:
            try:
                state_changed_dt = datetime.fromisoformat(state_changed.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        return {
            "monitoring_active": self.is_monitoring_active(),
            "monitoring_state_changed": state_changed,
            "time_since_state_change": (
                (get_utc_now() - state_changed_dt).total_seconds() 
                if state_changed_dt else None
            )
        }