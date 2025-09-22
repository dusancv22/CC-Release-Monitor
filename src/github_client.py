"""
GitHub API client for CC Release Monitor.
"""

import logging
import requests
import time
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone
from urllib.parse import urljoin

from .config import Config
from .utils import retry_async

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """GitHub API error exception."""
    pass


class RateLimitError(GitHubAPIError):
    """Rate limit error exception."""
    pass


class GitHubClient:
    """GitHub API client for fetching release information."""
    
    def __init__(self, config: Config):
        """
        Initialize GitHub client.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.base_url = "https://api.github.com"
        self.repo = config.github_repo
        self.session = requests.Session()
        
        # Set up headers
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CC-Release-Monitor-Bot/1.0",
        })
        
        # Add auth header if token is provided
        if config.github_api_token:
            self.session.headers["Authorization"] = f"token {config.github_api_token}"
            logger.info("GitHub client initialized with authentication token")
        else:
            logger.info("GitHub client initialized without authentication (rate limited)")
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
        self.rate_limit_remaining = None
        self.rate_limit_reset_time = None
    
    def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
    
    def _check_rate_limit(self, response: requests.Response) -> None:
        """Check and handle rate limit headers."""
        self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
        reset_time = response.headers.get("X-RateLimit-Reset")
        
        if reset_time:
            self.rate_limit_reset_time = datetime.fromtimestamp(int(reset_time), tz=timezone.utc)
        
        logger.debug(f"Rate limit remaining: {self.rate_limit_remaining}")
        
        if self.rate_limit_remaining == 0:
            reset_in = (self.rate_limit_reset_time - datetime.now(timezone.utc)).total_seconds()
            raise RateLimitError(f"Rate limit exceeded. Resets in {reset_in:.0f} seconds")
    
    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request to GitHub API.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            GitHubAPIError: If request fails
            RateLimitError: If rate limit is exceeded
        """
        self._wait_for_rate_limit()
        
        try:
            self.last_request_time = time.time()
            response = self.session.get(url, params=params, timeout=30)
            
            # Check rate limit
            self._check_rate_limit(response)
            
            if response.status_code == 404:
                raise GitHubAPIError(f"Repository not found: {self.repo}")
            elif response.status_code == 403:
                if "rate limit" in response.text.lower():
                    raise RateLimitError("Rate limit exceeded")
                else:
                    raise GitHubAPIError(f"Access forbidden: {response.text}")
            elif response.status_code != 200:
                raise GitHubAPIError(f"GitHub API error {response.status_code}: {response.text}")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise GitHubAPIError("Request timeout")
        except requests.exceptions.ConnectionError:
            raise GitHubAPIError("Connection error")
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"Request failed: {e}")
        except ValueError as e:
            raise GitHubAPIError(f"Invalid JSON response: {e}")
    
    def get_latest_release(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest release from the repository.
        
        Returns:
            Latest release data or None if no releases found
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/releases/latest"
        
        try:
            logger.debug(f"Fetching latest release from {url}")
            data = self._make_request(url)
            logger.info(f"Successfully fetched latest release: {data.get('tag_name', 'unknown')}")
            return data
            
        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                logger.warning(f"No releases found for repository {self.repo}")
                return None
            raise
    
    def get_releases(self, per_page: int = 30, page: int = 1) -> List[Dict[str, Any]]:
        """
        Get releases from the repository.
        
        Args:
            per_page: Number of releases per page (max 100)
            page: Page number to fetch
            
        Returns:
            List of release data
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/releases"
        params = {
            "per_page": min(per_page, 100),
            "page": page
        }
        
        logger.debug(f"Fetching releases from {url} (page {page}, per_page {per_page})")
        data = self._make_request(url, params)
        
        if not isinstance(data, list):
            raise GitHubAPIError("Expected list of releases")
        
        logger.info(f"Successfully fetched {len(data)} releases")
        return data
    
    def get_release_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        """
        Get specific release by tag name.
        
        Args:
            tag: Release tag name
            
        Returns:
            Release data or None if not found
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/releases/tags/{tag}"
        
        try:
            logger.debug(f"Fetching release by tag: {tag}")
            data = self._make_request(url)
            logger.info(f"Successfully fetched release: {tag}")
            return data
            
        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                logger.warning(f"Release not found: {tag}")
                return None
            raise
    
    def compare_commits(self, base: str, head: str) -> Dict[str, Any]:
        """
        Compare two commits/tags/branches.
        
        Args:
            base: Base commit/tag/branch
            head: Head commit/tag/branch
            
        Returns:
            Comparison data
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/compare/{base}...{head}"
        
        logger.debug(f"Comparing {base}...{head}")
        data = self._make_request(url)
        logger.info(f"Successfully compared {base}...{head}")
        return data
    
    def get_repository_info(self) -> Dict[str, Any]:
        """
        Get repository information.
        
        Returns:
            Repository data
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}"
        
        logger.debug(f"Fetching repository info for {self.repo}")
        data = self._make_request(url)
        logger.info(f"Successfully fetched repository info")
        return data
    
    async def get_latest_release_async(self) -> Optional[Dict[str, Any]]:
        """
        Async version of get_latest_release with retry logic.
        
        Returns:
            Latest release data or None if no releases found
        """
        async def fetch_release():
            return self.get_latest_release()
        
        try:
            return await retry_async(
                fetch_release,
                max_retries=self.config.max_retries,
                delay=self.config.retry_delay_seconds,
                exceptions=(GitHubAPIError, RateLimitError)
            )
        except Exception as e:
            logger.error(f"Failed to fetch latest release after retries: {e}")
            return None
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            Rate limit information
        """
        return {
            "remaining": self.rate_limit_remaining,
            "reset_time": self.rate_limit_reset_time.isoformat() if self.rate_limit_reset_time else None,
            "authenticated": bool(self.config.github_api_token),
            "repo": self.repo
        }
    
    def get_commits(self, per_page: int = 10, page: int = 1, branch: str = None) -> List[Dict[str, Any]]:
        """
        Get commits from the repository.
        
        Args:
            per_page: Number of commits per page (max 100)
            page: Page number to fetch
            branch: Branch name to get commits from (default: repository default branch)
            
        Returns:
            List of commit data
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/commits"
        params = {
            "per_page": min(per_page, 100),
            "page": page
        }
        
        if branch:
            params["sha"] = branch
        
        logger.debug(f"Fetching commits from {url} (page {page}, per_page {per_page}, branch {branch or 'default'})")
        data = self._make_request(url, params)
        
        if not isinstance(data, list):
            raise GitHubAPIError("Expected list of commits")
        
        logger.info(f"Successfully fetched {len(data)} commits")
        return data
    
    def get_commit(self, commit_sha: str) -> Optional[Dict[str, Any]]:
        """
        Get specific commit by SHA.
        
        Args:
            commit_sha: Commit SHA
            
        Returns:
            Commit data or None if not found
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/commits/{commit_sha}"
        
        try:
            logger.debug(f"Fetching commit: {commit_sha}")
            data = self._make_request(url)
            logger.info(f"Successfully fetched commit: {commit_sha[:8]}")
            return data
            
        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                logger.warning(f"Commit not found: {commit_sha}")
                return None
            raise
    
    async def get_commits_async(self, per_page: int = 10, page: int = 1, branch: str = None) -> List[Dict[str, Any]]:
        """
        Async version of get_commits with retry logic.
        
        Args:
            per_page: Number of commits per page
            page: Page number to fetch
            branch: Branch name to get commits from
            
        Returns:
            List of commit data
        """
        async def fetch_commits():
            return self.get_commits(per_page, page, branch)
        
        try:
            return await retry_async(
                fetch_commits,
                max_retries=self.config.max_retries,
                delay=self.config.retry_delay_seconds,
                exceptions=(GitHubAPIError, RateLimitError)
            )
        except Exception as e:
            logger.error(f"Failed to fetch commits after retries: {e}")
            return []

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to GitHub API.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            repo_info = self.get_repository_info()
            repo_name = repo_info.get("full_name", "unknown")
            stars = repo_info.get("stargazers_count", 0)
            
            return True, f"Connected to {repo_name} ({stars} stars)"
            
        except GitHubAPIError as e:
            return False, f"Connection failed: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    async def get_commit_async(self, commit_sha: str) -> Optional[Dict[str, Any]]:
        """
        Async version of get_commit with retry logic.
        
        Args:
            commit_sha: Commit SHA
            
        Returns:
            Commit data or None if not found
        """
        async def fetch_commit():
            return self.get_commit(commit_sha)
        
        try:
            return await retry_async(
                fetch_commit,
                max_retries=self.config.max_retries,
                delay=self.config.retry_delay_seconds,
                exceptions=(GitHubAPIError, RateLimitError)
            )
        except Exception as e:
            logger.error(f"Failed to fetch commit {commit_sha} after retries: {e}")
            return None
    
    def get_file_last_commit(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get the last commit that modified a specific file.
        
        Args:
            file_path: Path to file in repository
            
        Returns:
            Commit data with timestamp, or None if not found
        """
        url = f"{self.base_url}/repos/{self.repo}/commits"
        params = {"path": file_path, "per_page": 1}
        
        try:
            logger.debug(f"Fetching last commit for file: {file_path}")
            response = self._make_request(url, params)
            
            if response and len(response) > 0:
                logger.info(f"Found last commit for file: {file_path}")
                return response[0]
            return None
            
        except GitHubAPIError as e:
            logger.debug(f"Error fetching commits for file {file_path}: {e}")
            return None
    
    def get_file_content(self, file_path: str, branch: str = None) -> Optional[str]:
        """
        Get file content from the repository.
        
        Args:
            file_path: Path to the file in the repository
            branch: Branch to get file from (default: repository default branch)
            
        Returns:
            File content as string or None if not found
            
        Raises:
            GitHubAPIError: If request fails
        """
        url = f"{self.base_url}/repos/{self.repo}/contents/{file_path}"
        params = {}
        
        if branch:
            params["ref"] = branch
        
        try:
            logger.debug(f"Fetching file content: {file_path} from branch {branch or 'default'}")
            data = self._make_request(url, params)
            
            # GitHub API returns file content in base64
            import base64
            content = data.get('content', '')
            if content:
                # Decode base64 content
                content_bytes = base64.b64decode(content)
                content_str = content_bytes.decode('utf-8', errors='ignore')
                logger.info(f"Successfully fetched file content: {file_path}")
                return content_str
            else:
                logger.warning(f"Empty content for file: {file_path}")
                return None
                
        except GitHubAPIError as e:
            if "not found" in str(e).lower():
                logger.warning(f"File not found: {file_path}")
                return None
            raise
    
    async def get_file_last_commit_async(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Async version to get the last commit that modified a specific file.
        
        Args:
            file_path: Path to file in repository
            
        Returns:
            Commit data with timestamp, or None if not found
        """
        async def fetch_last_commit():
            return self.get_file_last_commit(file_path)
        
        try:
            return await retry_async(
                fetch_last_commit,
                max_retries=self.config.max_retries,
                delay=self.config.retry_delay_seconds,
                exceptions=(GitHubAPIError, RateLimitError)
            )
        except Exception as e:
            logger.error(f"Failed to fetch last commit for {file_path} after retries: {e}")
            return None
    
    async def get_file_content_async(self, file_path: str, branch: str = None) -> Optional[str]:
        """
        Async version of get_file_content with retry logic.
        
        Args:
            file_path: Path to the file in the repository
            branch: Branch to get file from
            
        Returns:
            File content as string or None if not found
        """
        async def fetch_file_content():
            return self.get_file_content(file_path, branch)
        
        try:
            return await retry_async(
                fetch_file_content,
                max_retries=self.config.max_retries,
                delay=self.config.retry_delay_seconds,
                exceptions=(GitHubAPIError, RateLimitError)
            )
        except Exception as e:
            logger.error(f"Failed to fetch file content {file_path} after retries: {e}")
            return None