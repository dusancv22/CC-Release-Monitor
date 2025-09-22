#!/usr/bin/env python3
"""
Multi-Repository Release Monitor Bot with GitHub Integration.
Supports monitoring multiple GitHub repositories including Claude Code and OpenAI Codex.
"""

import logging
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)

# Import our GitHub integration modules
from src.config import Config, ConfigError
from src.github_client import GitHubClient, GitHubAPIError, RateLimitError
from src.version_manager import VersionManager, VersionError
from src.release_parser import ReleaseParser
from src.utils import setup_logging, format_datetime
from src.repository_manager import repository_manager, Repository

# Load environment variables
load_dotenv()

# Initialize configuration
try:
    config = Config()
    setup_logging(config.log_level, config.log_directory)
    logger = logging.getLogger(__name__)
except ConfigError as e:
    print(f"Configuration Error: {e}")
    exit(1)

# Initialize GitHub integration components
github_clients = {}  # Will store per-repository GitHub clients
version_managers = {}  # Will store per-repository version managers
release_parser = ReleaseParser()

# Bot token
BOT_TOKEN = config.telegram_bot_token

# Authorized users (empty list means open access)
AUTHORIZED_USER_IDS = config.authorized_user_ids

# Restrict bot commands to private chats and optionally specific users
PRIVATE_CHAT_FILTER = filters.ChatType.PRIVATE
if AUTHORIZED_USER_IDS:
    COMMAND_ACCESS_FILTER = PRIVATE_CHAT_FILTER & filters.User(AUTHORIZED_USER_IDS)
else:
    COMMAND_ACCESS_FILTER = PRIVATE_CHAT_FILTER

def get_github_client(repo_key: str) -> GitHubClient:
    """Get or create a GitHub client for a specific repository."""
    if repo_key not in github_clients:
        # Create a custom config for this repository
        repo_config = Config()
        repo = repository_manager.get_repository(repo_key)
        if repo:
            # Override the repository in config
            repo_config.github_repo = repo.full_name
            github_clients[repo_key] = GitHubClient(repo_config)
    return github_clients[repo_key]

def get_version_manager(repo_key: str) -> VersionManager:
    """Get or create a version manager for a specific repository."""
    if repo_key not in version_managers:
        # Create a custom config for this repository
        repo_config = Config()
        repo = repository_manager.get_repository(repo_key)
        if repo:
            # Override the repository in config
            repo_config.github_repo = repo.full_name
            # Create separate data directory for each repo
            repo_config.data_directory = os.path.join(
                repo_config.data_directory,
                repo.short_name
            )
            # Ensure directory exists
            os.makedirs(repo_config.data_directory, exist_ok=True)
            version_managers[repo_key] = VersionManager(repo_config)
    return version_managers[repo_key]

def is_authorized_user(update: Update) -> bool:
    """Return True if the incoming update is from an allowed user."""
    if not AUTHORIZED_USER_IDS:
        return True
    user = update.effective_user
    return bool(user and user.id in AUTHORIZED_USER_IDS)

async def handle_unauthorized_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify and log when someone outside the allow-list contacts the bot."""
    user = update.effective_user
    user_info = f"id={getattr(user, 'id', 'unknown')} username={getattr(user, 'username', 'n/a')}"
    logger.warning("Blocked message from unauthorized user: %s", user_info)
    if update.message:
        await update.message.reply_text(
            "Sorry, this bot is private. If you believe this is a mistake, contact the owner.",
            quote=False
        )

def get_repository_keyboard() -> InlineKeyboardMarkup:
    """Create an inline keyboard for repository selection."""
    keyboard = []
    for repo_key, repo in repository_manager.get_available_repositories().items():
        button = InlineKeyboardButton(
            f"📦 {repo.display_name}",
            callback_data=f"select_repo:{repo_key}"
        )
        keyboard.append([button])
    
    return InlineKeyboardMarkup(keyboard)

def get_current_repo_text(user_id: int) -> str:
    """Get text showing the currently selected repository."""
    repo = repository_manager.get_user_repository(user_id)
    return f"📍 *Currently monitoring:* `{repo.full_name}` ({repo.display_name})"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    
    # Show repository selection
    await update.message.reply_text(
        '🤖 *Multi-Repository Release Monitor Bot*\n\n'
        'I can monitor multiple GitHub repositories for new releases and updates.\n\n'
        '*Available Repositories:*\n'
        '• **Claude Code** - Anthropic\'s official CLI\n'
        '• **OpenAI Codex** - OpenAI\'s Codex system\n\n'
        'Please select a repository to monitor:',
        parse_mode='Markdown',
        reply_markup=get_repository_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)

    # Check if user has explicitly selected a repository
    if user_id not in repository_manager.user_selections:
        repo_text = f'📍 *Default repository:* `{repo.full_name}` ({repo.display_name})\n⚠️ Use `/start` or `/switch` to select a different repository'
    else:
        repo_text = get_current_repo_text(user_id)

    await update.message.reply_text(
        '📚 *Multi-Repository Monitor Bot Help*\n\n'
        f'{repo_text}\n\n'
        '*Commands:*\n'
        '• `/start` - Select repository to monitor\n'
        '• `/switch` - Switch to a different repository\n'
        '• `/help` - This help message\n'
        '• `/status` - Bot status and GitHub connection info\n'
        '• `/check` - Check for new releases and commits\n'
        '• `/latest` - Show information about the latest release\n'
        '• `/commits` - Show recent commits from the repository\n'
        '• `/commit <sha>` - Show detailed information about a specific commit\n'
        '• `/changelog` - Show recent CHANGELOG.md updates\n'
        '• `/changelog\\_latest` - Show only the latest changelog entry\n\n'
        '*Features:*\n'
        '🔄 Multi-repository support\n'
        '📝 Commit monitoring for repositories\n'
        '📋 CHANGELOG.md change detection\n'
        '⚡ Manual release and commit checking\n'
        '📊 Version and commit history tracking\n'
        '🔗 GitHub API integration\n'
        '🕒 Rate limit handling\n\n'
        '*Current Configuration:*\n'
        f'• Repository: `{repo.full_name}`\n'
        f'• GitHub API: {"Authenticated" if config.github_api_token else "Anonymous"}\n\n'
        '📝 The bot stores version data separately for each repository.',
        parse_mode='Markdown'
    )

async def switch_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch to a different repository."""
    await update.message.reply_text(
        '🔄 *Switch Repository*\n\n'
        'Select a repository to monitor:',
        parse_mode='Markdown',
        reply_markup=get_repository_keyboard()
    )

async def handle_repository_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle repository selection from inline keyboard."""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Parse the callback data
    if query.data.startswith("select_repo:"):
        repo_key = query.data.replace("select_repo:", "")
        
        # Set the user's repository selection
        if repository_manager.set_user_repository(user_id, repo_key):
            repo = repository_manager.get_repository(repo_key)
            
            # Answer the callback query
            await query.answer(f"Selected: {repo.display_name}")
            
            # Update the message
            await query.edit_message_text(
                f'✅ *Repository Selected*\n\n'
                f'Now monitoring: **{repo.display_name}**\n'
                f'Repository: `{repo.full_name}`\n'
                f'Description: {repo.description}\n\n'
                f'*Available commands:*\n'
                f'/help - Show all commands\n'
                f'/status - Check bot status\n'
                f'/check - Check for new releases\n'
                f'/latest - Show latest release\n'
                f'/commits - Show recent commits\n'
                f'/switch - Switch to different repository\n\n'
                f'You can now use any command to interact with this repository.',
                parse_mode='Markdown'
            )
        else:
            await query.answer("Error selecting repository", show_alert=True)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send bot status information."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    version_manager = get_version_manager(repo_key)

    try:
        # Test GitHub connection for this repository
        success, message = github_client.test_connection()
        github_status = "✅ Connected" if success else f"❌ Error: {message}"

        # Get rate limit info
        rate_limit = github_client.get_rate_limit_status()
        
        # Get version manager stats for this repository
        version_stats = version_manager.get_statistics()
        commit_stats = version_manager.get_commit_statistics()
        changelog_stats = version_manager.get_changelog_statistics()
        
        status_message = (
            f'📊 *Repository Monitor Status*\n\n'
            f'{get_current_repo_text(user_id)}\n\n'
            '*System Status:*\n'
            '✅ Bot: Running\n'
            '✅ Telegram: Connected\n'
            f'🔗 GitHub API: {github_status}\n'
            f'📦 Repository: `{repo.full_name}`\n'
            f'🔑 API Auth: {"Yes" if config.github_api_token else "No (rate limited)"}\n\n'
            '*Rate Limiting:*\n'
            f'⚡ Remaining: {rate_limit["remaining"] or "Unknown"}\n'
            f'🔄 Reset Time: {rate_limit["reset_time"] or "Unknown"}\n\n'
            '*Release Tracking:*\n'
            f'📝 Last Known: {version_stats["last_known_version"] or "None"}\n'
            f'🕒 Last Check: {version_stats["last_check_time"] or "Never"}\n'
            f'📊 Total Checks: {version_stats["check_count"]}\n'
            f'📈 New Versions: {version_stats["new_versions_detected"]}\n\n'
            '*Commit Tracking:*\n'
            f'📝 Last Commit: {commit_stats["last_known_commit_sha"][:8] if commit_stats["last_known_commit_sha"] else "None"}\n'
            f'📊 Commit Checks: {commit_stats["commit_check_count"]}\n'
            f'📈 New Commits: {commit_stats["new_commits_detected"]}\n'
            f'💾 History Entries: {version_stats["total_history_entries"]}\n\n'
            '*Configuration:*\n'
            f'🔄 Max Retries: {config.max_retries}\n'
            f'📍 Data Directory: `{version_manager.data_file.parent}`\n\n'
            '🚀 *Multi-Repository GitHub Integration*'
        )
        
        await update.message.reply_text(status_message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await update.message.reply_text(
            '❌ *Error getting status*\n\n'
            f'An error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually check for new releases."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    version_manager = get_version_manager(repo_key)
    
    try:
        # Check if user has explicitly selected a repository
        if user_id not in repository_manager.user_selections:
            repo_note = f'\n📍 *Note: Using default repository. Use `/switch` to change.*\n'
        else:
            repo_note = ''

        # Send initial "checking" message
        status_message = await update.message.reply_text(
            f'🔍 *Checking for new releases...*\n\n'
            f'Repository: `{repo.full_name}`{repo_note}\n'
            f'Please wait while I query the GitHub API.',
            parse_mode='Markdown'
        )
        
        # Get latest release from GitHub for this repository
        release_data = await github_client.get_latest_release_async()
        
        if not release_data:
            # No releases found, check for commits instead
            await status_message.edit_text(
                '❌ *No releases found*\n\n'
                f'No releases found for `{repo.full_name}`.\n'
                'Checking for recent commits instead...',
                parse_mode='Markdown'
            )
            
            # Get recent commits
            try:
                commits_data = await github_client.get_commits_async(per_page=10)
                
                if not commits_data:
                    await status_message.edit_text(
                        '❌ *No data found*\n\n'
                        f'No releases or commits found for repository `{repo.full_name}`.\n'
                        'Please verify the repository exists and is public.',
                        parse_mode='Markdown'
                    )
                    return
                
                # Parse and check for new commits
                latest_commit = commits_data[0]
                parsed_commits = [release_parser.parse_commit(commit) for commit in commits_data[:5]]
                
                # Check if latest commit is new
                is_new_commit = version_manager.update_commit(latest_commit)
                
                if is_new_commit:
                    # New commit found!
                    commits_message = release_parser.format_commits_for_notification(parsed_commits)
                    await status_message.edit_text(
                        f'🆕 *New Commits Found!*\n\n'
                        f'Repository: `{repo.full_name}`\n\n'
                        f'{commits_message}',
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                else:
                    # Same commits as before
                    latest_commit_summary = release_parser.format_commit_summary(parsed_commits[0])
                    commits_preview = release_parser.format_commits_for_notification(parsed_commits, limit=3)
                    await status_message.edit_text(
                        f'✅ *No new commits*\n\n'
                        f'Repository: `{repo.full_name}`\n'
                        f'Latest commit: {latest_commit_summary}\n'
                        f'This is the same as the last check.\n\n'
                        f'{commits_preview}',
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                
            except Exception as e:
                logger.error(f"Error checking commits: {e}")
                await status_message.edit_text(
                    '❌ *Error checking commits*\n\n'
                    f'Failed to fetch commits: {str(e)}\n\n'
                    'Please try again later.',
                    parse_mode='Markdown'
                )
            return
        
        # Parse release data
        parsed_release = release_parser.parse_release(release_data)
        
        # Check if it's a new version
        is_new = version_manager.update_version(release_data)
        
        if is_new:
            # New version found!
            notification = release_parser.format_release_for_notification(parsed_release)
            await status_message.edit_text(
                f'🎉 *New Release Found!*\n\n'
                f'Repository: `{repo.full_name}`\n\n'
                f'{notification}',
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            # Same version as before
            summary = release_parser.format_release_summary(parsed_release)
            await status_message.edit_text(
                f'✅ *No new releases*\n\n'
                f'Repository: `{repo.full_name}`\n'
                f'Latest release: {summary}\n'
                f'This is the same version as last check.\n\n'
                f'🔗 [View Release]({parsed_release["url"]})',
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        
    except RateLimitError as e:
        await update.message.reply_text(
            '⏱️ *Rate Limit Exceeded*\n\n'
            f'GitHub API rate limit exceeded: {e}\n\n'
            'Please try again later or add a GitHub API token for higher limits.',
            parse_mode='Markdown'
        )
    except GitHubAPIError as e:
        await update.message.reply_text(
            '❌ *GitHub API Error*\n\n'
            f'Failed to fetch release data: {e}\n\n'
            'Please check the repository and try again.',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in check command: {e}")
        await update.message.reply_text(
            '❌ *Error checking releases*\n\n'
            f'An unexpected error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show information about the latest release."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    version_manager = get_version_manager(repo_key)
    
    try:
        # Try to get cached release data first
        cached_release = version_manager.get_latest_release_data()
        
        if cached_release:
            parsed_release = release_parser.parse_release(cached_release)
            summary = release_parser.format_release_summary(parsed_release)
            
            message = (
                f'📦 *Latest Known Release*\n\n'
                f'Repository: `{repo.full_name}`\n\n'
                f'{summary}\n\n'
                f'🔗 [View on GitHub]({parsed_release["url"]})\n\n'
                f'💾 *Cached data* - Use `/check` to fetch latest from GitHub.'
            )
        else:
            # No cached data, fetch from GitHub
            status_msg = await update.message.reply_text(
                f'🔍 *Fetching latest release...*\n\n'
                f'Repository: `{repo.full_name}`',
                parse_mode='Markdown'
            )
            
            release_data = await github_client.get_latest_release_async()
            
            if not release_data:
                await status_msg.edit_text(
                    '❌ *No releases found*\n\n'
                    f'No releases found for repository `{repo.full_name}`.',
                    parse_mode='Markdown'
                )
                return
            
            parsed_release = release_parser.parse_release(release_data)
            
            # Format detailed release information
            message = release_parser.format_release_for_notification(
                parsed_release, include_body=False
            )
            
            await status_msg.edit_text(
                f'Repository: `{repo.full_name}`\n\n' + message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in latest command: {e}")
        await update.message.reply_text(
            '❌ *Error fetching latest release*\n\n'
            f'An error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def commits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent commits from the repository."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    version_manager = get_version_manager(repo_key)
    
    try:
        # Send initial "fetching" message
        status_message = await update.message.reply_text(
            f'🔍 *Fetching recent commits...*\n\n'
            f'Repository: `{repo.full_name}`\n'
            f'Please wait while I query the GitHub API.',
            parse_mode='Markdown'
        )
        
        # Get recent commits from GitHub
        commits_data = await github_client.get_commits_async(per_page=10)
        
        if not commits_data:
            await status_message.edit_text(
                '❌ *No commits found*\n\n'
                f'No commits were found for repository `{repo.full_name}`.\n'
                'This might indicate a private repository or invalid repository name.',
                parse_mode='Markdown'
            )
            return
        
        # Parse commits
        parsed_commits = [release_parser.parse_commit(commit) for commit in commits_data]
        
        # Update latest commit tracking
        if parsed_commits:
            latest_commit = commits_data[0]
            is_new_commit = version_manager.update_commit(latest_commit)
        
        # Format commits for display
        commits_message = release_parser.format_commits_for_notification(parsed_commits, limit=8)
        
        # Build full message
        header = f'📝 *Recent Commits - {repo.full_name}*\n\n'
        
        if is_new_commit:
            header += '🆕 *Latest commit is new since last check!*\n\n'
        
        full_message = header + commits_message
        
        # Add repository link
        repo_url = f"https://github.com/{repo.full_name}/commits"
        full_message += f'\n\n🔗 [View all commits on GitHub]({repo_url})'
        
        await status_message.edit_text(
            full_message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except RateLimitError as e:
        await update.message.reply_text(
            '⏱️ *Rate Limit Exceeded*\n\n'
            f'GitHub API rate limit exceeded: {e}\n\n'
            'Please try again later or add a GitHub API token for higher limits.',
            parse_mode='Markdown'
        )
    except GitHubAPIError as e:
        await update.message.reply_text(
            '❌ *GitHub API Error*\n\n'
            f'Failed to fetch commit data: {e}\n\n'
            'Please check the repository and try again.',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in commits command: {e}")
        await update.message.reply_text(
            '❌ *Error fetching commits*\n\n'
            f'An unexpected error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def commit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed information about a specific commit."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    
    try:
        # Check if SHA was provided
        if not context.args:
            await update.message.reply_text(
                '❌ *Missing commit SHA*\n\n'
                'Please provide a commit SHA hash.\n\n'
                '*Usage:* `/commit <sha>`\n\n'
                '*Example:* `/commit a1b2c3d4`',
                parse_mode='Markdown'
            )
            return
        
        commit_sha = context.args[0]
        
        # Validate SHA length (should be at least 7 characters)
        if len(commit_sha) < 7:
            await update.message.reply_text(
                '❌ *Invalid commit SHA*\n\n'
                'Commit SHA should be at least 7 characters long.\n\n'
                '*Example:* `/commit a1b2c3d4`',
                parse_mode='Markdown'
            )
            return
            
        # Send initial "fetching" message
        status_message = await update.message.reply_text(
            f'🔍 *Fetching commit details...*\n\n'
            f'Repository: `{repo.full_name}`\n'
            f'Looking up commit: `{commit_sha}`',
            parse_mode='Markdown'
        )
        
        # Get commit details from GitHub
        try:
            commit_data = await github_client.get_commit_async(commit_sha)
            
            if not commit_data:
                await status_message.edit_text(
                    f'❌ *Commit not found*\n\n'
                    f'Could not find commit `{commit_sha}` in repository `{repo.full_name}`.\n\n'
                    'Please verify the SHA is correct.',
                    parse_mode='Markdown'
                )
                return
            
            # Parse commit data
            parsed_commit = release_parser.parse_commit(commit_data)
            
            # Get commit stats
            files_changed = len(commit_data.get('files', []))
            additions = commit_data.get('stats', {}).get('additions', 0)
            deletions = commit_data.get('stats', {}).get('deletions', 0)
            total_changes = additions + deletions
            
            # Format commit message (full message, not just first line)
            full_message = commit_data.get('commit', {}).get('message', '')
            message_lines = full_message.split('\n')
            title = message_lines[0] if message_lines else 'No title'
            body = '\n'.join(message_lines[1:]).strip() if len(message_lines) > 1 else ''
            
            # Build response message
            response_parts = [
                f'📝 *Commit Details: {commit_sha[:8]}*\n',
                f'Repository: `{repo.full_name}`\n',
                f'**Author:** {parsed_commit["author_name"]}',
                f'**Date:** {parsed_commit["date"]}',
                f'**SHA:** `{parsed_commit["sha"]}`\n',
                f'**Title:** {title}'
            ]
            
            if body:
                # Truncate body if too long
                if len(body) > 500:
                    body = body[:500] + '...'
                response_parts.append(f'\n**Description:**\n{body}')
            
            response_parts.extend([
                f'\n**Changes:**',
                f'📄 Files changed: {files_changed}',
                f'➕ Additions: {additions}',
                f'➖ Deletions: {deletions}',
                f'📊 Total changes: {total_changes}'
            ])
            
            # Add files changed preview (first few files)
            files = commit_data.get('files', [])
            if files:
                response_parts.append('\n**Files changed:**')
                for i, file_info in enumerate(files[:5]):  # Show first 5 files
                    filename = file_info.get('filename', 'Unknown')
                    status = file_info.get('status', 'modified')
                    status_icon = {'added': '➕', 'modified': '📝', 'removed': '➖'}.get(status, '📝')
                    response_parts.append(f'{status_icon} `{filename}`')
                
                if len(files) > 5:
                    response_parts.append(f'... and {len(files) - 5} more files')
            
            # Add diff preview (first few lines)
            if files and 'patch' in files[0]:
                first_file_patch = files[0].get('patch', '')
                if first_file_patch:
                    # Get first few lines of the diff
                    patch_lines = first_file_patch.split('\n')[:10]
                    if patch_lines:
                        response_parts.append('\n**Diff preview:**')
                        response_parts.append('```diff')
                        response_parts.append('\n'.join(patch_lines))
                        if len(first_file_patch.split('\n')) > 10:
                            response_parts.append('...')
                        response_parts.append('```')
            
            # Add GitHub link
            commit_url = f"https://github.com/{repo.full_name}/commit/{parsed_commit['sha']}"
            response_parts.append(f'\n🔗 [View on GitHub]({commit_url})')
            
            response_message = '\n'.join(response_parts)
            
            await status_message.edit_text(
                response_message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except GitHubAPIError as api_error:
            if 'Not Found' in str(api_error):
                await status_message.edit_text(
                    f'❌ *Commit not found*\n\n'
                    f'Commit `{commit_sha}` was not found in repository `{repo.full_name}`.\n\n'
                    'Please verify the SHA is correct.',
                    parse_mode='Markdown'
                )
            else:
                await status_message.edit_text(
                    f'❌ *GitHub API Error*\n\n'
                    f'Error fetching commit: {api_error}',
                    parse_mode='Markdown'
                )
            
    except RateLimitError as e:
        await update.message.reply_text(
            '⏱️ *Rate Limit Exceeded*\n\n'
            f'GitHub API rate limit exceeded: {e}\n\n'
            'Please try again later or add a GitHub API token for higher limits.',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in commit command: {e}")
        await update.message.reply_text(
            '❌ *Error fetching commit details*\n\n'
            f'An unexpected error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def changelog_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent CHANGELOG.md updates."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    
    try:
        # Send initial "fetching" message
        status_message = await update.message.reply_text(
            f'🔍 *Looking for CHANGELOG.md...*\n\n'
            f'Repository: `{repo.full_name}`\n'
            f'Searching for changelog updates.',
            parse_mode='Markdown'
        )
        
        # Try to get CHANGELOG.md content
        try:
            changelog_content = await github_client.get_file_content_async('CHANGELOG.md')
            
            if not changelog_content:
                await status_message.edit_text(
                    '❌ *CHANGELOG.md not found*\n\n'
                    f'No CHANGELOG.md file found in repository `{repo.full_name}`.\n\n'
                    'The repository may not maintain a changelog file.',
                    parse_mode='Markdown'
                )
                return
            
            # Parse changelog content to get recent entries
            changelog_lines = changelog_content.split('\n')
            
            # Find recent entries (look for version headers like ## v1.2.3 or # Version 1.2.3)
            recent_entries = []
            current_entry = []
            entry_count = 0
            max_entries = 3  # Show last 3 changelog entries
            
            in_entry = False
            
            for line in changelog_lines:
                line = line.strip()
                
                # Check if this is a version header
                if ((line.startswith('##') and ('v' in line.lower() or 'version' in line.lower() or 
                   any(char.isdigit() for char in line))) or
                   (line.startswith('#') and line.count('#') <= 2 and 
                   ('v' in line.lower() or 'version' in line.lower() or 
                   any(char.isdigit() for char in line)))):
                    
                    # Save previous entry if we have one
                    if current_entry and entry_count < max_entries:
                        recent_entries.append('\n'.join(current_entry))
                        entry_count += 1
                    
                    if entry_count >= max_entries:
                        break
                        
                    # Start new entry
                    current_entry = [line]
                    in_entry = True
                    
                elif in_entry and line:
                    # Add content to current entry (limit length)
                    if len('\n'.join(current_entry)) < 800:  # Limit entry length
                        current_entry.append(line)
            
            # Add the last entry if we haven't reached the limit
            if current_entry and entry_count < max_entries:
                recent_entries.append('\n'.join(current_entry))
            
            if not recent_entries:
                await status_message.edit_text(
                    '❌ *No changelog entries found*\n\n'
                    f'CHANGELOG.md exists but no version entries were found.\n\n'
                    'The changelog format may not be recognized.',
                    parse_mode='Markdown'
                )
                return
            
            # Get the actual last update time of CHANGELOG.md from GitHub
            from datetime import datetime
            last_commit = await github_client.get_file_last_commit_async('CHANGELOG.md')
            
            # Build response message
            response_parts = [
                f'📋 *Recent CHANGELOG Updates - {repo.full_name}*\n'
            ]
            
            # Add timestamp if available
            if last_commit and 'commit' in last_commit:
                commit_date = last_commit['commit']['author']['date']
                # Parse and format the date nicely
                try:
                    from datetime import datetime
                    dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    response_parts.append(f'🕒 *Last Updated:* {formatted_date}\n')
                except Exception as e:
                    logger.error(f"Error formatting changelog timestamp: {e}")
                    response_parts.append(f'🕒 *Last Updated:* {commit_date}\n')
            
            for i, entry in enumerate(recent_entries):
                if i > 0:
                    response_parts.append('\n---\n')
                response_parts.append(entry)
            
            # Add GitHub link to changelog
            changelog_url = f"https://github.com/{repo.full_name}/blob/main/CHANGELOG.md"
            response_parts.append(f'\n\n🔗 [View full CHANGELOG.md]({changelog_url})')
            
            response_message = '\n'.join(response_parts)
            
            # Truncate if too long for Telegram
            if len(response_message) > 4000:
                response_message = response_message[:4000] + '...\n\n🔗 [View full CHANGELOG.md]({changelog_url})'
            
            await status_message.edit_text(
                response_message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except GitHubAPIError as api_error:
            if 'Not Found' in str(api_error):
                await status_message.edit_text(
                    '❌ *CHANGELOG.md not found*\n\n'
                    f'No CHANGELOG.md file found in repository `{repo.full_name}`.\n\n'
                    'The repository may not maintain a changelog file.',
                    parse_mode='Markdown'
                )
            else:
                await status_message.edit_text(
                    f'❌ *GitHub API Error*\n\n'
                    f'Error fetching changelog: {api_error}',
                    parse_mode='Markdown'
                )
            
    except RateLimitError as e:
        await update.message.reply_text(
            '⏱️ *Rate Limit Exceeded*\n\n'
            f'GitHub API rate limit exceeded: {e}\n\n'
            'Please try again later or add a GitHub API token for higher limits.',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in changelog command: {e}")
        await update.message.reply_text(
            '❌ *Error fetching changelog*\n\n'
            f'An unexpected error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def changelog_latest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show only the latest CHANGELOG.md entry."""
    user_id = update.effective_user.id
    repo = repository_manager.get_user_repository(user_id)
    repo_key = repository_manager.get_user_repo_key(user_id)
    github_client = get_github_client(repo_key)
    
    try:
        # Send initial "fetching" message
        status_message = await update.message.reply_text(
            f'🔍 *Looking for latest changelog entry...*\n\n'
            f'Repository: `{repo.full_name}`\n'
            f'Fetching the most recent changelog update.',
            parse_mode='Markdown'
        )
        
        # Try to get CHANGELOG.md content
        try:
            changelog_content = await github_client.get_file_content_async('CHANGELOG.md')
            
            if not changelog_content:
                await status_message.edit_text(
                    '❌ *CHANGELOG.md not found*\n\n'
                    f'No CHANGELOG.md file found in repository `{repo.full_name}`.\n\n'
                    'The repository may not maintain a changelog file.',
                    parse_mode='Markdown'
                )
                return
            
            # Parse changelog content to get the latest entry only
            changelog_lines = changelog_content.split('\n')
            
            # Find the first (latest) entry
            latest_entry = []
            in_entry = False
            
            for line in changelog_lines:
                line = line.strip()
                
                # Check if this is a version header
                if ((line.startswith('##') and ('v' in line.lower() or 'version' in line.lower() or 
                   any(char.isdigit() for char in line))) or
                   (line.startswith('#') and line.count('#') <= 2 and 
                   ('v' in line.lower() or 'version' in line.lower() or 
                   any(char.isdigit() for char in line)))):
                    
                    if in_entry:
                        # We found the second header, stop here
                        break
                    else:
                        # Start the first (latest) entry
                        latest_entry = [line]
                        in_entry = True
                        
                elif in_entry and line:
                    # Add content to the latest entry (limit length)
                    if len('\n'.join(latest_entry)) < 1200:  # Slightly larger limit for single entry
                        latest_entry.append(line)
            
            if not latest_entry:
                await status_message.edit_text(
                    '❌ *No changelog entries found*\n\n'
                    f'CHANGELOG.md exists but no version entries were found.\n\n'
                    'The changelog format may not be recognized.',
                    parse_mode='Markdown'
                )
                return
            
            # Get the actual last update time of CHANGELOG.md from GitHub
            from datetime import datetime
            last_commit = await github_client.get_file_last_commit_async('CHANGELOG.md')
            
            # Build response message
            response_parts = [
                f'📋 *Latest CHANGELOG Update - {repo.full_name}*\n'
            ]
            
            # Add timestamp if available
            if last_commit and 'commit' in last_commit:
                commit_date = last_commit['commit']['author']['date']
                # Parse and format the date nicely
                try:
                    from datetime import datetime
                    dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    response_parts.append(f'🕒 *Last Updated:* {formatted_date}\n')
                except Exception as e:
                    logger.error(f"Error formatting changelog timestamp: {e}")
                    response_parts.append(f'🕒 *Last Updated:* {commit_date}\n')
            
            # Add the latest entry
            response_parts.append('\n'.join(latest_entry))
            
            # Add GitHub link to changelog
            changelog_url = f"https://github.com/{repo.full_name}/blob/main/CHANGELOG.md"
            response_parts.append(f'\n\n🔗 [View full CHANGELOG.md]({changelog_url})')
            
            response_message = '\n'.join(response_parts)
            
            # Truncate if too long for Telegram
            if len(response_message) > 4000:
                response_message = response_message[:4000] + '...\n\n🔗 [View full CHANGELOG.md]({changelog_url})'
            
            await status_message.edit_text(
                response_message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except GitHubAPIError as api_error:
            if 'Not Found' in str(api_error):
                await status_message.edit_text(
                    '❌ *CHANGELOG.md not found*\n\n'
                    f'No CHANGELOG.md file found in repository `{repo.full_name}`.\n\n'
                    'The repository may not maintain a changelog file.',
                    parse_mode='Markdown'
                )
            else:
                await status_message.edit_text(
                    f'❌ *GitHub API Error*\n\n'
                    f'Error fetching changelog: {api_error}',
                    parse_mode='Markdown'
                )
    except RateLimitError as e:
        await update.message.reply_text(
            '⏱️ *Rate Limit Exceeded*\n\n'
            f'GitHub API rate limit exceeded: {e}\n\n'
            'Please try again later or add a GitHub API token for higher limits.',
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in changelog_latest command: {e}")
        await update.message.reply_text(
            '❌ *Error fetching latest changelog*\n\n'
            f'An unexpected error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

def main() -> None:
    """Start the bot."""
    
    print("Starting Multi-Repository Release Monitor Bot...")
    print(f"Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:] if len(BOT_TOKEN) > 20 else 'SHORT_TOKEN'}")
    print("\nAvailable Repositories:")
    for key, repo in repository_manager.get_available_repositories().items():
        print(f"  - {repo.display_name}: {repo.full_name}")
    print(f"\nGitHub API: {'Authenticated' if config.github_api_token else 'Anonymous (rate limited)'}")
    print(f"Data Directory: {config.data_directory}")
    if AUTHORIZED_USER_IDS:
        print("Authorized users: " + ", ".join(str(uid) for uid in AUTHORIZED_USER_IDS))
    else:
        print("Authorized users: open (no allow-list configured)")
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("help", help_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("switch", switch_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("status", status, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("check", check_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("latest", latest_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("commits", commits_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("commit", commit_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("changelog", changelog_command, filters=COMMAND_ACCESS_FILTER))
    application.add_handler(CommandHandler("changelog_latest", changelog_latest_command, filters=COMMAND_ACCESS_FILTER))
    
    # Add callback query handler for inline keyboards
    application.add_handler(CallbackQueryHandler(handle_repository_selection))

    if AUTHORIZED_USER_IDS:
        unauthorized_filter = PRIVATE_CHAT_FILTER & (~filters.User(AUTHORIZED_USER_IDS))
        application.add_handler(MessageHandler(unauthorized_filter, handle_unauthorized_message))

    print("\nBot handlers registered successfully:")
    print("  /start - Select repository to monitor")
    print("  /switch - Switch to different repository")
    print("  /help - Show help information")
    print("  /status - Show bot status and GitHub connection")
    print("  /check - Check for new releases and commits")
    print("  /latest - Show latest release information")
    print("  /commits - Show recent commits from repository")
    print("  /commit <sha> - Show detailed info about a specific commit")
    print("  /changelog - Show recent CHANGELOG.md updates")
    print("  /changelog_latest - Show only the latest changelog entry")
    print("")
    
    print("Starting bot polling...")
    print("Press Ctrl+C to stop the bot")

    try:
        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == '__main__':
    main()