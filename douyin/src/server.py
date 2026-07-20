"""Douyin MCP Server - Provides tools for accessing Douyin data."""

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from .client import DouYinApiClient, DataFetchError
from .models import (
    SearchChannelType,
    SearchSortType,
    PublishTimeType,
    HomeFeedTagIdType,
)


def load_cookies() -> str:
    """
    Load cookies from cookies.txt file in project root.

    Returns:
        Cookie string or empty string if file not found
    """
    # Try to find cookies.txt in project root
    # Look for it relative to this file's location
    current_dir = Path(__file__).parent
    project_root = current_dir.parent

    cookies_file = project_root / "cookies.txt"

    if cookies_file.exists():
        return cookies_file.read_text(encoding="utf-8").strip()

    return ""


# Initialize MCP server
mcp = FastMCP(
    name="Douyin MCP",
    instructions="""
    Douyin MCP provides tools to access Douyin (Chinese TikTok) data.

    Available tools:
    - check_login_status: Check if the current session is logged in
    - search_videos: Search for videos by keyword
    - get_video_detail: Get detailed information about a specific video
    - get_video_comments: Get comments for a video
    - get_sub_comments: Get replies to a comment
    - get_user_info: Get user profile information
    - get_user_posts: Get videos posted by a user
    - get_homefeed: Get recommended videos from home feed

    Configuration:
    - Place your Douyin cookies in cookies.txt file in the project root directory

    Note: Signing is handled locally using embedded JavaScript, no external service required.
    """
)

# Global client instance
_client: Optional[DouYinApiClient] = None


def get_client() -> DouYinApiClient:
    """Get or create the API client instance."""
    global _client
    if _client is None:
        cookies = load_cookies()
        if not cookies:
            raise DataFetchError(
                "Cookies not found. Please create cookies.txt file in project root directory."
            )
        _client = DouYinApiClient(cookies=cookies)
    return _client


@mcp.tool
async def check_login_status() -> dict:
    """
    Check if the current Douyin session is logged in.

    Returns:
        dict with 'logged_in' boolean status
    """
    client = get_client()
    try:
        is_logged_in = await client.check_login_status()
        return {"logged_in": is_logged_in}
    except Exception as e:
        return {"logged_in": False, "error": str(e)}


@mcp.tool
async def search_videos(
    keyword: str,
    offset: int = 0,
    count: int = 10,
    search_channel: str = "general",
    sort_type: int = 0,
    publish_time: int = 0,
) -> dict:
    """
    Search for Douyin videos by keyword.

    Args:
        keyword: Search keyword
        offset: Pagination offset (default 0)
        count: Number of results per page (default 10, max 20)
        search_channel: Search type - "general", "video", "user", or "live"
        sort_type: Sort order - 0 (general), 1 (most liked), 2 (latest)
        publish_time: Time filter - 0 (unlimited), 1 (1 day), 7 (1 week), 180 (6 months)

    Returns:
        dict containing search results with video list
    """
    client = get_client()

    # Map string to enum
    channel_map = {
        "general": SearchChannelType.GENERAL,
        "video": SearchChannelType.VIDEO,
        "user": SearchChannelType.USER,
        "live": SearchChannelType.LIVE,
    }
    channel = channel_map.get(search_channel.lower(), SearchChannelType.GENERAL)

    # Map int to enum
    sort_enum = SearchSortType(sort_type) if sort_type in [0, 1, 2] else SearchSortType.GENERAL
    time_enum = PublishTimeType(publish_time) if publish_time in [0, 1, 7, 180] else PublishTimeType.UNLIMITED

    try:
        result = await client.search_info_by_keyword(
            keyword=keyword,
            offset=offset,
            count=count,
            search_channel=channel,
            sort_type=sort_enum,
            publish_time=time_enum,
        )
        return result
    except DataFetchError as e:
        return {"error": str(e), "status_code": -1}


@mcp.tool
async def get_video_detail(aweme_id: str) -> dict:
    """
    Get detailed information about a Douyin video.

    Args:
        aweme_id: The video/aweme ID (numeric string)

    Returns:
        dict containing video details including title, description,
        statistics (likes, comments, shares), author info, and URLs
    """
    client = get_client()

    try:
        video = await client.get_video_by_id(aweme_id)
        if video:
            return {"success": True, "video": asdict(video)}
        return {"success": False, "error": "Video not found"}
    except DataFetchError as e:
        return {"success": False, "error": str(e)}


@mcp.tool
async def get_video_comments(
    aweme_id: str,
    cursor: int = 0,
    count: int = 20,
    source_keyword: str = "",
) -> dict:
    """
    Get comments for a Douyin video.

    Args:
        aweme_id: The video/aweme ID
        cursor: Pagination cursor (default 0)
        count: Number of comments per page (default 20)
        source_keyword: Optional search keyword (used for referer)

    Returns:
        dict containing comments list and pagination metadata
    """
    client = get_client()

    try:
        comments, metadata = await client.get_aweme_comments(
            aweme_id=aweme_id,
            cursor=cursor,
            count=count,
            source_keyword=source_keyword,
        )
        return {
            "success": True,
            "comments": [asdict(c) for c in comments],
            "metadata": metadata,
        }
    except DataFetchError as e:
        return {"success": False, "error": str(e)}


@mcp.tool
async def get_sub_comments(
    comment_id: str,
    cursor: int = 0,
    count: int = 20,
    source_keyword: str = "",
) -> dict:
    """
    Get replies (sub-comments) for a Douyin comment.

    Args:
        comment_id: The parent comment ID
        cursor: Pagination cursor (default 0)
        count: Number of replies per page (default 20)
        source_keyword: Optional search keyword (used for referer)

    Returns:
        dict containing replies list and pagination metadata
    """
    client = get_client()

    try:
        comments, metadata = await client.get_sub_comments(
            comment_id=comment_id,
            cursor=cursor,
            count=count,
            source_keyword=source_keyword,
        )
        return {
            "success": True,
            "comments": [asdict(c) for c in comments],
            "metadata": metadata,
        }
    except DataFetchError as e:
        return {"success": False, "error": str(e)}


@mcp.tool
async def get_user_info(sec_user_id: str) -> dict:
    """
    Get Douyin user profile information.

    Args:
        sec_user_id: The user's security ID (starts with MS4wLjABAAAA)

    Returns:
        dict containing user profile with nickname, avatar, follower count,
        following count, total likes, and video count
    """
    client = get_client()

    try:
        user = await client.get_user_info(sec_user_id)
        if user:
            return {"success": True, "user": asdict(user)}
        return {"success": False, "error": "User not found"}
    except DataFetchError as e:
        return {"success": False, "error": str(e)}


@mcp.tool
async def get_user_posts(
    sec_user_id: str,
    max_cursor: str = "0",
    count: int = 18,
) -> dict:
    """
    Get videos posted by a Douyin user.

    Args:
        sec_user_id: The user's security ID
        max_cursor: Pagination cursor (default "0")
        count: Number of videos per page (default 18)

    Returns:
        dict containing video list and pagination info
    """
    client = get_client()

    try:
        result = await client.get_user_aweme_posts(
            sec_user_id=sec_user_id,
            max_cursor=max_cursor,
            count=count,
        )
        return result
    except DataFetchError as e:
        return {"error": str(e), "status_code": -1}


@mcp.tool
async def get_homefeed(
    tag: str = "all",
    count: int = 20,
    refresh_index: int = 0,
) -> dict:
    """
    Get recommended videos from Douyin home feed.

    Args:
        tag: Content category - one of: "all", "knowledge", "sports", "auto",
             "anime", "game", "movie", "life_vlog", "travel", "mini_drama",
             "food", "agriculture", "music", "animal", "parenting", "fashion"
        count: Number of videos to return (default 20)
        refresh_index: Refresh index for pagination (default 0)

    Returns:
        dict containing recommended video list
    """
    client = get_client()

    # Map tag string to enum
    tag_map = {
        "all": HomeFeedTagIdType.ALL,
        "knowledge": HomeFeedTagIdType.KNOWLEDGE,
        "sports": HomeFeedTagIdType.SPORTS,
        "auto": HomeFeedTagIdType.AUTO,
        "anime": HomeFeedTagIdType.ANIME,
        "game": HomeFeedTagIdType.GAME,
        "movie": HomeFeedTagIdType.MOVIE,
        "life_vlog": HomeFeedTagIdType.LIFE_VLOG,
        "travel": HomeFeedTagIdType.TRAVEL,
        "mini_drama": HomeFeedTagIdType.MINI_DRAMA,
        "food": HomeFeedTagIdType.FOOD,
        "agriculture": HomeFeedTagIdType.AGRICULTURE,
        "music": HomeFeedTagIdType.MUSIC,
        "animal": HomeFeedTagIdType.ANIMAL,
        "parenting": HomeFeedTagIdType.PARENTING,
        "fashion": HomeFeedTagIdType.FASHION,
    }
    tag_enum = tag_map.get(tag.lower(), HomeFeedTagIdType.ALL)

    try:
        result = await client.get_homefeed_aweme_list(
            tag_id=tag_enum,
            count=count,
            refresh_index=refresh_index,
        )
        return result
    except DataFetchError as e:
        return {"error": str(e), "status_code": -1}
