"""
Release data parser for CC Release Monitor.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse

from .utils import format_datetime, parse_datetime

logger = logging.getLogger(__name__)


class ReleaseParser:
    """Parser for GitHub release data."""
    
    def __init__(self):
        """Initialize release parser."""
        self.markdown_patterns = {
            'headers': re.compile(r'^#+\s+(.+)$', re.MULTILINE),
            'bold': re.compile(r'\*\*(.+?)\*\*'),
            'italic': re.compile(r'\*(.+?)\*'),
            'code': re.compile(r'`(.+?)`'),
            'links': re.compile(r'\[(.+?)\]\((.+?)\)'),
            'list_items': re.compile(r'^[-*+]\s+(.+)$', re.MULTILINE),
            'numbered_items': re.compile(r'^\d+\.\s+(.+)$', re.MULTILINE)
        }
    
    def _escape_markdown(self, text: str) -> str:
        """
        Escape special Markdown characters in text for Telegram's legacy Markdown format.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text safe for Telegram Markdown
        """
        if not text:
            return ""
        
        # Only these characters need escaping in Telegram's legacy Markdown format
        # Note: We don't escape ` here since we use it in code blocks intentionally
        text = text.replace('_', '\\_')  # Prevent italic formatting
        text = text.replace('*', '\\*')  # Prevent bold formatting  
        text = text.replace('[', '\\[')  # Prevent link formatting
        text = text.replace(']', '\\]')  # Prevent link formatting
        
        return text
    
    def parse_release(self, release_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse GitHub release data into structured format.
        
        Args:
            release_data: Raw release data from GitHub API
            
        Returns:
            Parsed release information
        """
        try:
            parsed = {
                'version': self._extract_version(release_data),
                'name': release_data.get('name', ''),
                'tag_name': release_data.get('tag_name', ''),
                'published_at': self._parse_date(release_data.get('published_at')),
                'created_at': self._parse_date(release_data.get('created_at')),
                'url': release_data.get('html_url', ''),
                'api_url': release_data.get('url', ''),
                'tarball_url': release_data.get('tarball_url', ''),
                'zipball_url': release_data.get('zipball_url', ''),
                'body': release_data.get('body', ''),
                'prerelease': release_data.get('prerelease', False),
                'draft': release_data.get('draft', False),
                'author': self._extract_author(release_data),
                'assets': self._parse_assets(release_data.get('assets', [])),
                'changelog': self._parse_changelog(release_data.get('body', '')),
                'summary': self._generate_summary(release_data),
                'formatted_body': self._format_body_for_telegram(release_data.get('body', '')),
                'metadata': self._extract_metadata(release_data)
            }
            
            logger.debug(f"Parsed release: {parsed['version']} ({parsed['name']})")
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing release data: {e}")
            return self._create_fallback_parsed_data(release_data)
    
    def _extract_version(self, release_data: Dict[str, Any]) -> str:
        """Extract version string from release data."""
        tag_name = release_data.get('tag_name', '')
        name = release_data.get('name', '')
        
        # Prefer tag_name, but use name if tag_name is empty
        version = tag_name or name
        
        # Clean up version string
        if version.lower().startswith('v'):
            version = version[1:]
        
        return version or 'unknown'
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string to datetime object."""
        if not date_string:
            return None
        
        try:
            # Parse ISO format with timezone
            if date_string.endswith('Z'):
                date_string = date_string[:-1] + '+00:00'
            
            return datetime.fromisoformat(date_string)
        except ValueError:
            logger.warning(f"Failed to parse date: {date_string}")
            return None
    
    def _extract_author(self, release_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract author information."""
        author_data = release_data.get('author', {})
        
        return {
            'login': author_data.get('login', ''),
            'name': author_data.get('name', ''),
            'url': author_data.get('html_url', ''),
            'avatar_url': author_data.get('avatar_url', ''),
            'type': author_data.get('type', '')
        }
    
    def _parse_assets(self, assets_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse release assets."""
        assets = []
        
        for asset in assets_data:
            parsed_asset = {
                'name': asset.get('name', ''),
                'size': asset.get('size', 0),
                'download_count': asset.get('download_count', 0),
                'content_type': asset.get('content_type', ''),
                'download_url': asset.get('browser_download_url', ''),
                'created_at': self._parse_date(asset.get('created_at')),
                'updated_at': self._parse_date(asset.get('updated_at'))
            }
            assets.append(parsed_asset)
        
        return assets
    
    def _parse_changelog(self, body: str) -> Dict[str, Any]:
        """Parse changelog from release body."""
        if not body:
            return {'sections': [], 'features': [], 'fixes': [], 'changes': []}
        
        sections = []
        features = []
        fixes = []
        changes = []
        
        # Extract headers and their content
        lines = body.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            # Check if it's a header
            header_match = re.match(r'^#+\s+(.+)$', line)
            if header_match:
                # Save previous section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content).strip()
                    })
                
                current_section = header_match.group(1).strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_section:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content).strip()
            })
        
        # Categorize items
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for list items
            if re.match(r'^[-*+]\s+', line) or re.match(r'^\d+\.\s+', line):
                item = re.sub(r'^[-*+\d]+\.?\s+', '', line)
                
                # Categorize based on keywords
                item_lower = item.lower()
                if any(word in item_lower for word in ['add', 'new', 'feature', 'introduce']):
                    features.append(item)
                elif any(word in item_lower for word in ['fix', 'bug', 'issue', 'resolve']):
                    fixes.append(item)
                else:
                    changes.append(item)
        
        return {
            'sections': sections,
            'features': features,
            'fixes': fixes,
            'changes': changes
        }
    
    def _generate_summary(self, release_data: Dict[str, Any]) -> str:
        """Generate a summary of the release."""
        name = release_data.get('name', '')
        tag_name = release_data.get('tag_name', '')
        body = release_data.get('body', '')
        prerelease = release_data.get('prerelease', False)
        
        # Start with version info
        version = tag_name or 'Unknown version'
        summary_parts = [f"Version {version}"]
        
        if prerelease:
            summary_parts.append("(Pre-release)")
        
        if name and name != tag_name:
            summary_parts.append(f"- {name}")
        
        # Extract first line of body as description
        if body:
            first_line = body.split('\n')[0].strip()
            if first_line and len(first_line) < 200:
                # Remove markdown formatting for summary
                clean_line = re.sub(r'[*_`#]', '', first_line)
                if clean_line != version and clean_line.lower() != name.lower():
                    summary_parts.append(f": {clean_line}")
        
        return ' '.join(summary_parts)
    
    def _format_body_for_telegram(self, body: str) -> str:
        """Format release body for Telegram message."""
        if not body:
            return "No release notes provided."
        
        # Limit length
        max_length = 2000  # Telegram message limit is ~4096, leave room for other content
        
        if len(body) > max_length:
            body = body[:max_length] + "..."
        
        # Convert some markdown to Telegram format
        formatted = body
        
        # Convert headers to bold
        formatted = re.sub(r'^#+\s+(.+)$', r'*\1*', formatted, flags=re.MULTILINE)
        
        # Preserve code blocks (Telegram supports them)
        # Convert single backticks to code format
        formatted = re.sub(r'`([^`]+)`', r'`\1`', formatted)
        
        # Convert links to Telegram format
        formatted = re.sub(r'\[(.+?)\]\((.+?)\)', r'[\1](\2)', formatted)
        
        # Clean up excessive newlines
        formatted = re.sub(r'\n\s*\n\s*\n+', r'\n\n', formatted)
        
        return formatted.strip()
    
    def _extract_metadata(self, release_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from release."""
        return {
            'id': release_data.get('id'),
            'node_id': release_data.get('node_id'),
            'target_commitish': release_data.get('target_commitish', ''),
            'draft': release_data.get('draft', False),
            'prerelease': release_data.get('prerelease', False),
            'assets_count': len(release_data.get('assets', [])),
            'reactions': release_data.get('reactions', {}),
            'discussion_url': release_data.get('discussion_url', ''),
            'make_latest': release_data.get('make_latest', '')
        }
    
    def _create_fallback_parsed_data(self, release_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback parsed data when parsing fails."""
        return {
            'version': release_data.get('tag_name', 'unknown'),
            'name': release_data.get('name', ''),
            'tag_name': release_data.get('tag_name', ''),
            'published_at': None,
            'created_at': None,
            'url': release_data.get('html_url', ''),
            'api_url': release_data.get('url', ''),
            'tarball_url': '',
            'zipball_url': '',
            'body': release_data.get('body', ''),
            'prerelease': release_data.get('prerelease', False),
            'draft': release_data.get('draft', False),
            'author': {'login': '', 'name': '', 'url': '', 'avatar_url': '', 'type': ''},
            'assets': [],
            'changelog': {'sections': [], 'features': [], 'fixes': [], 'changes': []},
            'summary': f"Version {release_data.get('tag_name', 'unknown')}",
            'formatted_body': 'Release information could not be parsed.',
            'metadata': {}
        }
    
    def format_release_for_notification(self, parsed_release: Dict[str, Any], 
                                      include_body: bool = True) -> str:
        """
        Format parsed release data for Telegram notification.
        
        Args:
            parsed_release: Parsed release data
            include_body: Whether to include the full release body
            
        Returns:
            Formatted message text
        """
        try:
            # Emoji indicators
            if parsed_release['prerelease']:
                status_emoji = "🧪"  # Pre-release
                status_text = "Pre-release"
            else:
                status_emoji = "🚀"  # Release
                status_text = "Release"
            
            # Build message
            message_parts = []
            
            # Header
            message_parts.append(f"{status_emoji} *New Claude Code {status_text}*")
            message_parts.append("")
            
            # Version info
            version = parsed_release['version']
            name = parsed_release['name']
            
            if name and name != version:
                message_parts.append(f"📦 *{name}* (`{version}`)")
            else:
                message_parts.append(f"📦 *Version {version}*")
            
            # Date
            if parsed_release['published_at']:
                date_str = format_datetime(parsed_release['published_at'], "%Y-%m-%d %H:%M UTC")
                message_parts.append(f"📅 Published: {date_str}")
            
            # Author
            author = parsed_release['author']
            if author and author['login']:
                author_text = f"👤 By: {author['login']}"
                if author['url']:
                    author_text = f"👤 By: [{author['login']}]({author['url']})"
                message_parts.append(author_text)
            
            message_parts.append("")
            
            # Changelog summary
            changelog = parsed_release['changelog']
            if changelog['features'] or changelog['fixes'] or changelog['changes']:
                message_parts.append("📋 *What's New:*")
                
                if changelog['features']:
                    message_parts.append("✨ *New Features:*")
                    for feature in changelog['features'][:3]:  # Limit to 3
                        message_parts.append(f"  • {feature}")
                
                if changelog['fixes']:
                    message_parts.append("🔧 *Bug Fixes:*")
                    for fix in changelog['fixes'][:3]:  # Limit to 3
                        message_parts.append(f"  • {fix}")
                
                if changelog['changes']:
                    message_parts.append("📝 *Changes:*")
                    for change in changelog['changes'][:3]:  # Limit to 3
                        message_parts.append(f"  • {change}")
                
                if len(changelog['features']) + len(changelog['fixes']) + len(changelog['changes']) > 9:
                    message_parts.append("  • ...and more")
                
                message_parts.append("")
            
            # Assets
            assets = parsed_release['assets']
            if assets:
                message_parts.append(f"📎 *Assets:* {len(assets)} files available")
            
            # Links
            message_parts.append(f"🔗 [View Release]({parsed_release['url']})")
            
            # Optional: Include body (truncated)
            if include_body and parsed_release['body']:
                body = parsed_release['formatted_body']
                if body and body != "No release notes provided.":
                    message_parts.append("")
                    message_parts.append("📄 *Release Notes:*")
                    # Limit body length for notification
                    if len(body) > 1000:
                        body = body[:1000] + f"...\n\n[Read more]({parsed_release['url']})"
                    message_parts.append(body)
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Error formatting release for notification: {e}")
            # Fallback message
            return (
                f"🚀 *New Claude Code Release*\n\n"
                f"Version: {parsed_release.get('version', 'unknown')}\n"
                f"View: {parsed_release.get('url', '')}"
            )
    
    def format_release_summary(self, parsed_release: Dict[str, Any]) -> str:
        """
        Format a brief summary of the release.
        
        Args:
            parsed_release: Parsed release data
            
        Returns:
            Brief summary text
        """
        version = parsed_release['version']
        name = parsed_release['name']
        prerelease = parsed_release['prerelease']
        
        summary_parts = []
        
        if prerelease:
            summary_parts.append("🧪 Pre-release:")
        else:
            summary_parts.append("🚀 Release:")
        
        if name and name != version:
            summary_parts.append(f"{name} ({version})")
        else:
            summary_parts.append(version)
        
        if parsed_release['published_at']:
            date_str = format_datetime(parsed_release['published_at'], "%Y-%m-%d")
            summary_parts.append(f"({date_str})")
        
        return " ".join(summary_parts)
    
    def extract_version_number(self, release_data: Dict[str, Any]) -> str:
        """
        Extract clean version number from release data.
        
        Args:
            release_data: Raw or parsed release data
            
        Returns:
            Clean version number
        """
        # Try multiple fields
        for field in ['version', 'tag_name', 'name']:
            value = release_data.get(field, '')
            if value:
                # Clean version string
                clean = value.strip()
                if clean.lower().startswith('v'):
                    clean = clean[1:]
                
                # Validate it looks like a version
                if re.match(r'^\d+(\.\d+)*', clean):
                    return clean
        
        return 'unknown'

    def parse_commit(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse GitHub commit data into structured format.
        
        Args:
            commit_data: Raw commit data from GitHub API
            
        Returns:
            Parsed commit information
        """
        try:
            commit_info = commit_data.get('commit', {})
            author_info = commit_info.get('author', {})
            committer_info = commit_info.get('committer', {})
            github_author = commit_data.get('author', {})
            
            parsed = {
                'sha': commit_data.get('sha', ''),
                'short_sha': commit_data.get('sha', '')[:8],
                'message': commit_info.get('message', ''),
                'subject': self._extract_commit_subject(commit_info.get('message', '')),
                'body': self._extract_commit_body(commit_info.get('message', '')),
                'author': {
                    'name': author_info.get('name', ''),
                    'email': author_info.get('email', ''),
                    'date': self._parse_date(author_info.get('date')),
                    'github_login': github_author.get('login', '') if github_author else '',
                    'github_url': github_author.get('html_url', '') if github_author else '',
                    'avatar_url': github_author.get('avatar_url', '') if github_author else ''
                },
                'committer': {
                    'name': committer_info.get('name', ''),
                    'email': committer_info.get('email', ''),
                    'date': self._parse_date(committer_info.get('date'))
                },
                'url': commit_data.get('html_url', ''),
                'api_url': commit_data.get('url', ''),
                'tree_sha': commit_info.get('tree', {}).get('sha', ''),
                'parents': [parent.get('sha', '') for parent in commit_data.get('parents', [])],
                'files_changed': len(commit_data.get('files', [])),
                'stats': commit_data.get('stats', {}),
                'formatted_message': self._format_commit_message_for_telegram(commit_info.get('message', '')),
                'metadata': self._extract_commit_metadata(commit_data)
            }
            
            logger.debug(f"Parsed commit: {parsed['short_sha']} - {parsed['subject']}")
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing commit data: {e}")
            return self._create_fallback_commit_data(commit_data)

    def _extract_commit_subject(self, message: str) -> str:
        """Extract commit subject (first line) from commit message."""
        if not message:
            return "No message"
        
        lines = message.strip().split('\n')
        subject = lines[0].strip()
        
        # Limit subject length for display
        if len(subject) > 80:
            subject = subject[:77] + "..."
        
        return subject or "No message"

    def _extract_commit_body(self, message: str) -> str:
        """Extract commit body (everything after first line) from commit message."""
        if not message:
            return ""
        
        lines = message.strip().split('\n')
        if len(lines) <= 2:  # Only subject or subject + empty line
            return ""
        
        # Join all lines after the first empty line
        body_lines = []
        found_empty = False
        
        for i, line in enumerate(lines[1:], 1):
            if not line.strip() and not found_empty:
                found_empty = True
                continue
            elif found_empty or line.strip():
                body_lines.append(line)
        
        return '\n'.join(body_lines).strip()

    def _format_commit_message_for_telegram(self, message: str) -> str:
        """Format commit message for Telegram display."""
        if not message:
            return "No commit message"
        
        # Limit total length
        max_length = 500
        if len(message) > max_length:
            message = message[:max_length] + "..."
        
        # Basic formatting - escape special markdown characters but preserve code blocks
        formatted = message.replace('*', '\\*').replace('_', '\\_').replace('[', '\\[').replace(']', '\\]')
        
        # Convert code blocks back
        formatted = re.sub(r'\\`([^`]+)\\`', r'`\1`', formatted)
        
        return formatted.strip()

    def _extract_commit_metadata(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from commit data."""
        stats = commit_data.get('stats', {})
        
        return {
            'node_id': commit_data.get('node_id', ''),
            'parents_count': len(commit_data.get('parents', [])),
            'additions': stats.get('additions', 0),
            'deletions': stats.get('deletions', 0),
            'total_changes': stats.get('total', 0),
            'verified': commit_data.get('commit', {}).get('verification', {}).get('verified', False),
            'merge_commit': len(commit_data.get('parents', [])) > 1
        }

    def _create_fallback_commit_data(self, commit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback commit data when parsing fails."""
        sha = commit_data.get('sha', 'unknown')
        
        return {
            'sha': sha,
            'short_sha': sha[:8],
            'message': 'Commit information could not be parsed',
            'subject': 'Unparseable commit',
            'body': '',
            'author': {'name': 'Unknown', 'email': '', 'date': None, 'github_login': '', 'github_url': '', 'avatar_url': ''},
            'committer': {'name': 'Unknown', 'email': '', 'date': None},
            'url': commit_data.get('html_url', ''),
            'api_url': commit_data.get('url', ''),
            'tree_sha': '',
            'parents': [],
            'files_changed': 0,
            'stats': {},
            'formatted_message': 'Commit information could not be parsed',
            'metadata': {}
        }

    def format_commits_for_notification(self, commits: List[Dict[str, Any]], 
                                      limit: int = 5) -> str:
        """
        Format list of parsed commits for Telegram notification.
        
        Args:
            commits: List of parsed commit data
            limit: Maximum number of commits to include
            
        Returns:
            Formatted message text
        """
        if not commits:
            return "No commits found."
        
        message_parts = []
        message_parts.append("📝 *Recent Commits:*\n")
        
        # Limit commits shown
        commits_to_show = commits[:limit]
        
        for i, commit in enumerate(commits_to_show, 1):
            # Format commit entry
            short_sha = commit['short_sha']
            subject = commit['subject']
            author = commit['author']['name'] or commit['author']['github_login'] or 'Unknown'
            
            # Escape special Markdown characters in subject and author
            subject_escaped = self._escape_markdown(subject)
            author_escaped = self._escape_markdown(author)
            
            # Date formatting
            date_str = "Unknown date"
            if commit['author']['date']:
                try:
                    date_str = format_datetime(commit['author']['date'], "%m-%d %H:%M")
                except Exception as e:
                    logger.error(f"Error formatting commit date: {e}")
                    date_str = "Unknown date"
            
            # Build commit line
            commit_line = f"`{short_sha}` {subject_escaped}"
            if len(commit_line) > 80:
                commit_line = f"`{short_sha}` {subject_escaped[:65]}..."
            
            message_parts.append(f"**{i}.** {commit_line}")
            message_parts.append(f"    👤 {author_escaped} • 📅 {date_str}")
            
            # Add stats if available
            stats = commit.get('metadata', {})
            if stats.get('total_changes', 0) > 0:
                additions = stats.get('additions', 0)
                deletions = stats.get('deletions', 0)
                message_parts.append(f"    📊 +{additions} -{deletions}")
            
            message_parts.append("")  # Empty line between commits
        
        # Add summary if there are more commits
        if len(commits) > limit:
            remaining = len(commits) - limit
            message_parts.append(f"... and {remaining} more commit{'s' if remaining != 1 else ''}")
        
        return "\n".join(message_parts).strip()

    def format_commit_summary(self, commit: Dict[str, Any]) -> str:
        """
        Format a brief summary of a single commit.
        
        Args:
            commit: Parsed commit data
            
        Returns:
            Brief summary text
        """
        short_sha = commit['short_sha']
        subject = commit['subject']
        author = commit['author']['github_login'] or commit['author']['name'] or 'Unknown'
        
        # Truncate subject if too long
        if len(subject) > 50:
            subject = subject[:47] + "..."
        
        return f"📝 `{short_sha}` {subject} - {author}"