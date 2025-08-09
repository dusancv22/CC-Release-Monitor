#!/usr/bin/env python3
"""
CC Release Monitor Bot with GitHub Integration.
This implementation includes GitHub API integration for monitoring Claude Code releases.
"""

import logging
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Import our new GitHub integration modules
from src.config import Config, ConfigError
from src.github_client import GitHubClient, GitHubAPIError, RateLimitError
from src.version_manager import VersionManager, VersionError
from src.release_parser import ReleaseParser
from src.utils import setup_logging, format_datetime

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
github_client = GitHubClient(config)
version_manager = VersionManager(config)
release_parser = ReleaseParser()

# Bot token
BOT_TOKEN = config.telegram_bot_token

# Global scheduler and application reference
scheduler = None
bot_application = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        '🤖 *CC Release Monitor Bot*\n\n'
        'I monitor Claude Code releases and notify you when new versions are available.\n\n'
        '*Available commands:*\n'
        '/start - Show this welcome message\n'
        '/help - Show detailed help information\n'
        '/status - Show bot and monitoring status\n'
        '/check - Check for new releases and commits\n'
        '/latest - Show current latest release\n'
        '/commits - Show recent commits\n'
        '/commit <sha> - Show detailed info about a specific commit\n'
        '/changelog - Show recent CHANGELOG.md updates\n'
        '/version - Show version management info\n'
        '/start\\_monitoring - Start automatic background monitoring\n'
        '/stop\\_monitoring - Stop automatic monitoring\n\n'
        '🚀 GitHub integration with automatic monitoring is now active!',
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        '📚 *CC Release Monitor Bot Help*\n\n'
        'This bot monitors the `anthropics/claude-code` repository for new releases and provides notifications.\n\n'
        '*Commands:*\n'
        '• `/start` - Welcome message and overview\n'
        '• `/help` - This help message\n'
        '• `/status` - Bot status and GitHub connection info\n'
        '• `/check` - Check for new releases and commits\n'
        '• `/latest` - Show information about the latest release\n'
        '• `/commits` - Show recent commits from the repository\n'
        '• `/commit <sha>` - Show detailed information about a specific commit\n'
        '• `/changelog` - Show recent CHANGELOG.md updates\n'
        '• `/version` - Show version tracking and history\n'
        '• `/start\\_monitoring` - Start automatic background monitoring\n'
        '• `/stop\\_monitoring` - Stop automatic monitoring\n\n'
        '*Features:*\n'
        '🔔 Automatic release monitoring (background)\n'
        '📝 Commit monitoring for repositories without releases\n'
        '📋 CHANGELOG.md change detection\n'
        '⚡ Manual release and commit checking\n'
        '📊 Version and commit history tracking\n'
        '🔗 GitHub API integration\n'
        '🕒 Rate limit handling\n'
        '⏰ Configurable monitoring intervals\n\n'
        '*Configuration:*\n'
        f'• Repository: `{config.github_repo}`\n'
        f'• Check interval: {config.check_interval_minutes} minutes\n'
        f'• GitHub API: {"Authenticated" if config.github_api_token else "Anonymous"}\n\n'
        '📝 The bot runs locally and stores version data in JSON files.',
        parse_mode='Markdown'
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send bot status information."""
    try:
        # Test GitHub connection
        success, message = github_client.test_connection()
        github_status = "✅ Connected" if success else f"❌ Error: {message}"
        
        # Get rate limit info
        rate_limit = github_client.get_rate_limit_status()
        
        # Get version manager stats
        version_stats = version_manager.get_statistics()
        commit_stats = version_manager.get_commit_statistics()
        monitoring_stats = version_manager.get_monitoring_statistics()
        changelog_stats = version_manager.get_changelog_statistics()
        
        status_message = (
            '📊 *CC Release Monitor Status*\n\n'
            '*System Status:*\n'
            '✅ Bot: Running\n'
            '✅ Telegram: Connected\n'
            f'🔗 GitHub API: {github_status}\n'
            f'📦 Repository: `{config.github_repo}`\n'
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
            '*Automatic Monitoring:*\n'
            f'🔍 Status: {"🟢 Active" if monitoring_stats["monitoring_active"] else "🔴 Inactive"}\n'
            f'📋 Changelog Checks: {changelog_stats["changelog_check_count"]}\n'
            f'📝 Changelog Updates: {changelog_stats["new_changelog_updates_detected"]}\n\n'
            '*Configuration:*\n'
            f'⏱️ Check Interval: {config.check_interval_minutes} min\n'
            f'🔄 Max Retries: {config.max_retries}\n'
            f'📍 Data Directory: `{config.data_directory}`\n\n'
            '🚀 *Version: GitHub Integration + Auto-Monitoring*'
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
    try:
        # Send initial "checking" message
        status_message = await update.message.reply_text(
            '🔍 *Checking for new releases...*\n\n'
            'Please wait while I query the GitHub API.',
            parse_mode='Markdown'
        )
        
        # Get latest release from GitHub
        release_data = await github_client.get_latest_release_async()
        
        if not release_data:
            # No releases found, check for commits instead
            await status_message.edit_text(
                '❌ *No releases found*\n\n'
                f'No releases found for `{config.github_repo}`.\n'
                'Checking for recent commits instead...',
                parse_mode='Markdown'
            )
            
            # Get recent commits
            try:
                commits_data = await github_client.get_commits_async(per_page=10)
                
                if not commits_data:
                    await status_message.edit_text(
                        '❌ *No data found*\n\n'
                        f'No releases or commits found for repository `{config.github_repo}`.\n'
                        'Please verify the repository name.',
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
                        f'🆕 *New Commits Found!*\n\n{commits_message}',
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                else:
                    # Same commits as before
                    latest_commit_summary = release_parser.format_commit_summary(parsed_commits[0])
                    commits_preview = release_parser.format_commits_for_notification(parsed_commits, limit=3)
                    await status_message.edit_text(
                        f'✅ *No new commits*\n\n'
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
                    'Please check the repository name and try again.',
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
                f'🎉 *New Release Found!*\n\n{notification}',
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            # Same version as before
            summary = release_parser.format_release_summary(parsed_release)
            await status_message.edit_text(
                f'✅ *No new releases*\n\n'
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
            'Please check the repository name and try again.',
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
    try:
        # Try to get cached release data first
        cached_release = version_manager.get_latest_release_data()
        
        if cached_release:
            parsed_release = release_parser.parse_release(cached_release)
            summary = release_parser.format_release_summary(parsed_release)
            
            message = (
                f'📦 *Latest Known Release*\n\n'
                f'{summary}\n\n'
                f'🔗 [View on GitHub]({parsed_release["url"]})\n\n'
                f'💾 *Cached data* - Use `/check` to fetch latest from GitHub.'
            )
        else:
            # No cached data, fetch from GitHub
            status_msg = await update.message.reply_text(
                '🔍 *Fetching latest release...*',
                parse_mode='Markdown'
            )
            
            release_data = await github_client.get_latest_release_async()
            
            if not release_data:
                await status_msg.edit_text(
                    '❌ *No releases found*\n\n'
                    f'No releases found for repository `{config.github_repo}`.',
                    parse_mode='Markdown'
                )
                return
            
            parsed_release = release_parser.parse_release(release_data)
            
            # Format detailed release information
            message = release_parser.format_release_for_notification(
                parsed_release, include_body=False
            )
            
            await status_msg.edit_text(
                message,
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
    try:
        # Send initial "fetching" message
        status_message = await update.message.reply_text(
            '🔍 *Fetching recent commits...*\n\n'
            'Please wait while I query the GitHub API.',
            parse_mode='Markdown'
        )
        
        # Get recent commits from GitHub
        commits_data = await github_client.get_commits_async(per_page=10)
        
        if not commits_data:
            await status_message.edit_text(
                '❌ *No commits found*\n\n'
                f'No commits were found for repository `{config.github_repo}`.\n'
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
        header = f'📝 *Recent Commits - {config.github_repo}*\n\n'
        
        if is_new_commit:
            header += '🆕 *Latest commit is new since last check!*\n\n'
        
        full_message = header + commits_message
        
        # Add repository link
        repo_url = f"https://github.com/{config.github_repo}/commits"
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
            'Please check the repository name and try again.',
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
            f'Looking up commit: `{commit_sha}`',
            parse_mode='Markdown'
        )
        
        # Get commit details from GitHub
        try:
            commit_data = await github_client.get_commit_async(commit_sha)
            
            if not commit_data:
                await status_message.edit_text(
                    f'❌ *Commit not found*\n\n'
                    f'Could not find commit `{commit_sha}` in repository `{config.github_repo}`.\n\n'
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
            commit_url = f"https://github.com/{config.github_repo}/commit/{parsed_commit['sha']}"
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
                    f'Commit `{commit_sha}` was not found in repository `{config.github_repo}`.\n\n'
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
    try:
        # Send initial "fetching" message
        status_message = await update.message.reply_text(
            '🔍 *Looking for CHANGELOG.md...*\n\n'
            'Searching for changelog updates.',
            parse_mode='Markdown'
        )
        
        # Try to get CHANGELOG.md content
        try:
            changelog_content = await github_client.get_file_content_async('CHANGELOG.md')
            
            if not changelog_content:
                await status_message.edit_text(
                    '❌ *CHANGELOG.md not found*\n\n'
                    f'No CHANGELOG.md file found in repository `{config.github_repo}`.\n\n'
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
            logger.info(f"DEBUG: Fetched last_commit: {last_commit is not None}")
            
            # Build response message
            response_parts = [
                f'📋 *Recent CHANGELOG Updates - {config.github_repo}*\n'
            ]
            
            # Add timestamp if available
            if last_commit and 'commit' in last_commit:
                commit_date = last_commit['commit']['author']['date']
                logger.info(f"DEBUG: Found commit date: {commit_date}")
                # Parse and format the date nicely
                try:
                    from datetime import datetime
                    dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
                    formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    response_parts.append(f'🕒 *Last Updated:* {formatted_date}\n')
                    logger.info(f"DEBUG: Added formatted timestamp: {formatted_date}")
                except Exception as e:
                    logger.error(f"DEBUG: Date parsing error: {e}")
                    response_parts.append(f'🕒 *Last Updated:* {commit_date}\n')
            else:
                logger.warning(f"DEBUG: No commit data found. last_commit={last_commit}")
            
            for i, entry in enumerate(recent_entries):
                if i > 0:
                    response_parts.append('\n---\n')
                response_parts.append(entry)
            
            # Add GitHub link to changelog
            changelog_url = f"https://github.com/{config.github_repo}/blob/main/CHANGELOG.md"
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
                    f'No CHANGELOG.md file found in repository `{config.github_repo}`.\n\n'
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

async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show version management information."""
    try:
        stats = version_manager.get_statistics()
        history = version_manager.get_version_history(limit=5)
        
        message_parts = ['📊 *Version Management Info*\n']
        
        # Current status
        message_parts.append('*Current Status:*')
        message_parts.append(f'📝 Last Known Version: {stats["last_known_version"] or "None"}')
        message_parts.append(f'🕒 Last Check: {stats["last_check_time"] or "Never"}')
        message_parts.append(f'📊 Total Checks: {stats["check_count"]}')
        message_parts.append(f'📈 New Versions Found: {stats["new_versions_detected"]}')
        
        if stats["time_since_last_check"]:
            hours = stats["time_since_last_check"] / 3600
            message_parts.append(f'⏰ Time Since Last Check: {hours:.1f} hours')
        
        message_parts.append('')
        
        # Recent history
        if history:
            message_parts.append('*Recent Version History:*')
            for entry in history:
                version = entry['version']
                is_new = entry.get('is_new', False)
                check_time = entry.get('check_time', '')
                
                # Format time
                try:
                    if check_time:
                        dt = datetime.fromisoformat(check_time.replace('Z', '+00:00'))
                        time_str = format_datetime(dt, "%m-%d %H:%M")
                    else:
                        time_str = "Unknown"
                except:
                    time_str = "Unknown"
                
                status_icon = "🆕" if is_new else "📝"
                prerelease_icon = " 🧪" if entry.get('prerelease', False) else ""
                
                message_parts.append(f'{status_icon} `{version}`{prerelease_icon} - {time_str}')
        else:
            message_parts.append('*No version history available*')
        
        message_parts.append('')
        message_parts.append('*Storage Info:*')
        message_parts.append(f'💾 Data File: {"✅" if stats["data_file_exists"] else "❌"}')
        message_parts.append(f'📚 History File: {"✅" if stats["history_file_exists"] else "❌"}')
        message_parts.append(f'📁 History Entries: {stats["total_history_entries"]}')
        
        await update.message.reply_text(
            '\n'.join(message_parts),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in version command: {e}")
        await update.message.reply_text(
            '❌ *Error getting version info*\n\n'
            f'An error occurred: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def periodic_monitoring() -> None:
    """Periodic monitoring function that runs in background."""
    global bot_application
    
    if not version_manager.is_monitoring_active():
        logger.debug("Monitoring is disabled, skipping check")
        return
    
    if not bot_application:
        logger.warning("Bot application not available for monitoring")
        return
    
    try:
        logger.info("Starting periodic monitoring check...")
        
        # Track what changed
        changes_detected = []
        
        # 1. Check for new releases
        try:
            release_data = await github_client.get_latest_release_async()
            if release_data:
                is_new_release = version_manager.update_version(release_data)
                if is_new_release:
                    parsed_release = release_parser.parse_release(release_data)
                    notification = release_parser.format_release_for_notification(parsed_release)
                    changes_detected.append(("release", f'🎉 *New Release Found!*\n\n{notification}'))
                    logger.info(f"New release detected during monitoring: {parsed_release.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error checking releases during monitoring: {e}")
        
        # 2. Check for new commits (if no releases or as fallback)
        try:
            commits_data = await github_client.get_commits_async(per_page=5)
            if commits_data:
                latest_commit = commits_data[0]
                is_new_commit = version_manager.update_commit(latest_commit)
                if is_new_commit:
                    parsed_commits = [release_parser.parse_commit(commit) for commit in commits_data[:3]]
                    commits_message = release_parser.format_commits_for_notification(parsed_commits, limit=3)
                    changes_detected.append(("commit", f'🆕 *New Commits Found!*\n\n{commits_message}'))
                    logger.info(f"New commits detected during monitoring: {latest_commit.get('sha', 'Unknown')[:8]}")
        except Exception as e:
            logger.error(f"Error checking commits during monitoring: {e}")
        
        # 3. Check for changelog changes
        try:
            changelog_content = await github_client.get_file_content_async('CHANGELOG.md')
            if changelog_content:
                is_new_changelog = version_manager.update_changelog(changelog_content)
                if is_new_changelog:
                    # Parse recent changelog entries for notification
                    changelog_lines = changelog_content.split('\n')
                    recent_entries = []
                    current_entry = []
                    entry_count = 0
                    max_entries = 2  # Show last 2 changelog entries
                    
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
                            
                        elif current_entry and line:
                            # Add content to current entry (limit length)
                            if len('\n'.join(current_entry)) < 600:  # Limit entry length
                                current_entry.append(line)
                    
                    # Add the last entry if we haven't reached the limit
                    if current_entry and entry_count < max_entries:
                        recent_entries.append('\n'.join(current_entry))
                    
                    if recent_entries:
                        changelog_message = '\n\n---\n\n'.join(recent_entries)
                        from datetime import datetime
                        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                        changes_detected.append(("changelog", f'📋 *CHANGELOG.md Updated!*\n\n🕒 *Update Detected:* {timestamp}\n\n{changelog_message}'))
                        logger.info("New changelog content detected during monitoring")
        except Exception as e:
            logger.debug(f"Changelog not found or error during monitoring: {e}")  # Debug level since changelog may not exist
        
        # Send notifications for any changes detected
        if changes_detected:
            # Get all users (in real implementation, you'd have a user database)
            # For now, we'll just log that we would send notifications
            logger.info(f"Would send notifications for {len(changes_detected)} changes detected")
            
            # In a real implementation, you would:
            # 1. Get list of subscribed users from database
            # 2. Send notification to each user
            # 3. Handle rate limiting and errors
            
            # For demonstration, we'll just log what we would send
            for change_type, message in changes_detected:
                logger.info(f"Notification ({change_type}): {message[:100]}...")
                
                # TODO: In full implementation, send to users:
                # for user_id in subscribed_users:
                #     try:
                #         await bot_application.bot.send_message(
                #             chat_id=user_id,
                #             text=message,
                #             parse_mode='Markdown',
                #             disable_web_page_preview=True
                #         )
                #         await asyncio.sleep(0.1)  # Rate limiting
                #     except Exception as send_error:
                #         logger.error(f"Failed to send notification to {user_id}: {send_error}")
        else:
            logger.debug("No changes detected during monitoring")
            
    except Exception as e:
        logger.error(f"Error in periodic monitoring: {e}")

async def start_monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start automatic monitoring."""
    global scheduler
    
    try:
        if version_manager.is_monitoring_active():
            await update.message.reply_text(
                '✅ *Monitoring Already Active*\n\n'
                'Automatic monitoring is already running.\n\n'
                f'📊 Check interval: {config.check_interval_minutes} minutes\n'
                f'🔍 Monitoring: Releases, Commits, CHANGELOG.md\n\n'
                'Use `/stop\\_monitoring` to stop automatic monitoring.',
                parse_mode='Markdown'
            )
            return
        
        # Enable monitoring in version manager
        version_manager.set_monitoring_active(True)
        
        # Schedule periodic monitoring if not already scheduled
        if scheduler and not scheduler.get_job('periodic_monitoring'):
            scheduler.add_job(
                periodic_monitoring,
                trigger=IntervalTrigger(minutes=config.check_interval_minutes),
                id='periodic_monitoring',
                name='Periodic Repository Monitoring',
                replace_existing=True
            )
            logger.info(f"Scheduled periodic monitoring every {config.check_interval_minutes} minutes")
        
        await update.message.reply_text(
            '🚀 *Automatic Monitoring Started!*\n\n'
            'The bot will now automatically check for:\n'
            '🎯 New releases\n'
            '📝 New commits\n'
            '📋 CHANGELOG.md updates\n\n'
            f'⏱️ Check interval: {config.check_interval_minutes} minutes\n'
            f'📦 Repository: `{config.github_repo}`\n\n'
            'You will receive notifications when changes are detected.\n\n'
            '*Commands:*\n'
            '• `/stop\\_monitoring` - Stop automatic monitoring\n'
            '• `/status` - Check monitoring status\n'
            '• `/check` - Manual check (works independently)',
            parse_mode='Markdown'
        )
        
        # Run an initial check
        await update.message.reply_text(
            '🔍 *Running initial check...*\n\n'
            'Please wait while I perform the first monitoring check.',
            parse_mode='Markdown'
        )
        
        # Schedule the initial check to run after a short delay
        if scheduler:
            scheduler.add_job(
                periodic_monitoring,
                trigger='date',
                run_date=datetime.now().astimezone().replace(second=datetime.now().second + 5),
                id='initial_monitoring_check',
                name='Initial Monitoring Check'
            )
        
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        await update.message.reply_text(
            '❌ *Error Starting Monitoring*\n\n'
            f'Failed to start automatic monitoring: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

async def stop_monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop automatic monitoring."""
    global scheduler
    
    try:
        if not version_manager.is_monitoring_active():
            await update.message.reply_text(
                '⏸️ *Monitoring Already Stopped*\n\n'
                'Automatic monitoring is not currently running.\n\n'
                'Use `/start\\_monitoring` to start automatic monitoring.',
                parse_mode='Markdown'
            )
            return
        
        # Disable monitoring in version manager
        version_manager.set_monitoring_active(False)
        
        # Remove scheduled job
        if scheduler and scheduler.get_job('periodic_monitoring'):
            scheduler.remove_job('periodic_monitoring')
            logger.info("Removed periodic monitoring job from scheduler")
        
        # Get monitoring statistics for the final message
        monitoring_stats = version_manager.get_monitoring_statistics()
        time_active = monitoring_stats.get("time_since_state_change")
        hours_active = time_active / 3600 if time_active else 0
        
        await update.message.reply_text(
            '⏸️ *Automatic Monitoring Stopped*\n\n'
            'Background monitoring has been disabled.\n\n'
            f'📊 *Session Summary:*\n'
            f'⏰ Active for: {hours_active:.1f} hours\n'
            f'📦 Repository: `{config.github_repo}`\n\n'
            '*Manual commands still work:*\n'
            '• `/check` - Manual release/commit check\n'
            '• `/latest` - Show latest release\n'
            '• `/commits` - Show recent commits\n'
            '• `/changelog` - Show CHANGELOG.md\n\n'
            'Use `/start\\_monitoring` to resume automatic monitoring.',
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        await update.message.reply_text(
            '❌ *Error Stopping Monitoring*\n\n'
            f'Failed to stop automatic monitoring: {str(e)}\n\n'
            'Please check the logs for more details.',
            parse_mode='Markdown'
        )

def main() -> None:
    """Start the bot."""
    global scheduler, bot_application
    
    print("Starting CC Release Monitor Bot...")
    print(f"Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:] if len(BOT_TOKEN) > 20 else 'SHORT_TOKEN'}")
    print(f"Monitoring Repository: {config.github_repo}")
    print(f"GitHub API: {'Authenticated' if config.github_api_token else 'Anonymous (rate limited)'}")
    print(f"Data Directory: {config.data_directory}")
    print(f"Check Interval: {config.check_interval_minutes} minutes")
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    bot_application = application  # Store global reference for monitoring
    
    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("latest", latest_command))
    application.add_handler(CommandHandler("commits", commits_command))
    application.add_handler(CommandHandler("commit", commit_command))
    application.add_handler(CommandHandler("changelog", changelog_command))
    application.add_handler(CommandHandler("version", version_command))
    application.add_handler(CommandHandler("start_monitoring", start_monitoring_command))
    application.add_handler(CommandHandler("stop_monitoring", stop_monitoring_command))

    print("Bot handlers registered successfully:")
    print("  /start - Welcome message")
    print("  /help - Show help information")
    print("  /status - Show bot status and GitHub connection")
    print("  /check - Check for new releases and commits")
    print("  /latest - Show latest release information")
    print("  /commits - Show recent commits from repository")
    print("  /commit <sha> - Show detailed info about a specific commit")
    print("  /changelog - Show recent CHANGELOG.md updates")
    print("  /version - Show version tracking info")
    print("  /start_monitoring - Start automatic monitoring")
    print("  /stop_monitoring - Stop automatic monitoring")
    print("")
    
    # Configure scheduler for later start (after event loop is running)
    print(f"Scheduler configured for automatic monitoring (interval: {config.check_interval_minutes} min)")
    
    # Note: Scheduler will start after the event loop is running
    if version_manager.is_monitoring_active():
        print("Automatic monitoring will resume after bot starts...")
        scheduler.add_job(
            periodic_monitoring,
            trigger=IntervalTrigger(minutes=config.check_interval_minutes),
            id='periodic_monitoring',
            name='Periodic Repository Monitoring',
            replace_existing=True
        )
        print(f"Automatic monitoring resumed every {config.check_interval_minutes} minutes")
    else:
        print("Automatic monitoring is disabled. Use /start_monitoring to enable.")
    
    print("")
    print("Starting bot polling...")
    print("Press Ctrl+C to stop the bot")

    # Add post_init callback to start scheduler after event loop is running
    async def post_init(application):
        global scheduler
        if not scheduler.running:
            scheduler.start()
            print("Scheduler started!")
            if version_manager.is_monitoring_active():
                print("Automatic monitoring resumed!")
    
    application.post_init = post_init

    try:
        # Run the bot until the user presses Ctrl-C
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean shutdown
        if scheduler.running:
            scheduler.shutdown()
            print("Scheduler shut down")

if __name__ == '__main__':
    main()