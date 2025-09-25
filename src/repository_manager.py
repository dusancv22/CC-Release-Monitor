"""
Repository manager for handling multiple GitHub repositories.
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Repository:
    """Repository configuration."""
    owner: str
    name: str
    display_name: str
    description: str
    latest_content_source: str = "release"
    changelog_path: str = "CHANGELOG.md"
    
    @property
    def full_name(self) -> str:
        """Get the full repository name (owner/name)."""
        return f"{self.owner}/{self.name}"
    
    @property
    def short_name(self) -> str:
        """Get a short identifier for the repository."""
        return self.name.lower().replace("-", "_")


# Define available repositories
REPOSITORIES = {
    "claude_code": Repository(
        owner="anthropics",
        name="claude-code",
        display_name="Claude Code",
        description="Anthropic's official CLI for Claude",
        latest_content_source="changelog",
    ),
    "codex": Repository(
        owner="openai",
        name="codex",
        display_name="OpenAI Codex",
        description="OpenAI's Codex AI system"
    )
}


class RepositoryManager:
    """Manages repository selection and user context."""
    
    def __init__(self):
        """Initialize the repository manager."""
        self.user_selections: Dict[int, str] = {}  # user_id -> repo_key
        self.default_repo = "claude_code"
        
    def get_repository(self, repo_key: str) -> Optional[Repository]:
        """Get repository by key."""
        return REPOSITORIES.get(repo_key)
    
    def get_user_repository(self, user_id: int) -> Repository:
        """Get the currently selected repository for a user."""
        repo_key = self.get_user_repo_key(user_id)
        return REPOSITORIES[repo_key]

    def get_user_repo_key(self, user_id: int) -> str:
        """Get the repository key for a user (with default)."""
        return self.user_selections.get(user_id, self.default_repo)
    
    def set_user_repository(self, user_id: int, repo_key: str) -> bool:
        """Set the selected repository for a user."""
        if repo_key not in REPOSITORIES:
            logger.error(f"Invalid repository key: {repo_key}")
            return False
        
        self.user_selections[user_id] = repo_key
        logger.info(f"User {user_id} selected repository: {repo_key}")
        return True
    
    def get_available_repositories(self) -> Dict[str, Repository]:
        """Get all available repositories."""
        return REPOSITORIES.copy()
    
    def get_repository_display_info(self, repo_key: str) -> Tuple[str, str]:
        """Get display name and description for a repository."""
        repo = self.get_repository(repo_key)
        if repo:
            return repo.display_name, repo.description
        return "Unknown", "Unknown repository"
    
    def clear_user_selection(self, user_id: int) -> None:
        """Clear the repository selection for a user."""
        if user_id in self.user_selections:
            del self.user_selections[user_id]
            logger.info(f"Cleared repository selection for user {user_id}")


# Global instance
repository_manager = RepositoryManager()