"""小克的耳朵 — 让桌面版 Claude 看到电脑上正在播放的音乐 (Windows)

原理: 读取 Windows 系统媒体会话 (SMTC)。只要播放器能在系统音量弹窗里
显示歌名(网易云/QQ音乐/Spotify/浏览器都支持),这里就能读到。

依赖: pip install mcp winsdk
运行: 由 Claude Desktop 通过 claude_desktop_config.json 自动拉起,无需手动运行。
"""

from mcp.server.fastmcp import FastMCP
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
)

mcp = FastMCP("now-playing", host="0.0.0.0", port=8010)

STATUS = {0: "已关闭", 1: "已打开", 2: "切换中", 3: "已停止", 4: "播放中", 5: "已暂停"}


async def _get_session():
    mgr = await SessionManager.request_async()
    return mgr.get_current_session()


def _fmt(td):
    s = int(td.total_seconds())
    return f"{s // 60}:{s % 60:02d}"


@mcp.tool()
async def now_playing() -> str:
    """查看电脑上正在播放的歌曲:歌名、歌手、专辑、播放进度、用的哪个播放器。想陪嘉嘉听歌、聊她在听什么的时候用这个。"""
    session = await _get_session()
    if session is None:
        return "现在没有播放任何媒体。"
    props = await session.try_get_media_properties_async()
    info = session.get_playback_info()
    tl = session.get_timeline_properties()

    lines = [
        f"歌名: {props.title or '未知'}",
        f"歌手: {props.artist or props.album_artist or '未知'}",
    ]
    if props.album_title:
        lines.append(f"专辑: {props.album_title}")
    lines.append(f"状态: {STATUS.get(int(info.playback_status), '未知')}")
    try:
        if tl.end_time.total_seconds() > 0:
            lines.append(f"进度: {_fmt(tl.position)} / {_fmt(tl.end_time)}")
    except Exception:
        pass
    lines.append(f"播放器: {session.source_app_user_model_id or '未知'}")
    return "\n".join(lines)


@mcp.tool()
async def play_pause() -> str:
    """播放/暂停切换(嘉嘉让你暂停或继续放歌时用)。"""
    session = await _get_session()
    if session is None:
        return "没有可控制的媒体会话。"
    ok = await session.try_toggle_play_pause_async()
    return "切换了播放/暂停。" if ok else "这个播放器不允许远程控制。"


@mcp.tool()
async def next_track() -> str:
    """切到下一首。"""
    session = await _get_session()
    if session is None:
        return "没有可控制的媒体会话。"
    ok = await session.try_skip_next_async()
    return "切到下一首了。" if ok else "这个播放器不允许切歌。"


@mcp.tool()
async def previous_track() -> str:
    """回到上一首。"""
    session = await _get_session()
    if session is None:
        return "没有可控制的媒体会话。"
    ok = await session.try_skip_previous_async()
    return "回到上一首了。" if ok else "这个播放器不允许切歌。"


@mcp.tool()
async def play_song(song_id: str) -> str:
    """在电脑的网易云客户端播放指定歌曲。传网易云歌曲 ID(数字,可通过 DJ 的 play_music 或 get_lyrics 搜到)。嘉嘉说"放某首歌"时:先用 DJ 工具搜到 ID,再调这个真正开始播放。"""
    import os
    sid = "".join(ch for ch in str(song_id) if ch.isdigit())
    if not sid:
        return "song_id 需要是网易云的数字 ID。"
    try:
        os.startfile("orpheus://song/" + sid)
        return "已唤起网易云客户端播放 (ID: " + sid + ")。若只打开未自动播,再调一次 play_pause 按下播放。"
    except Exception as e:
        return "唤起网易云客户端失败: " + str(e) + "(电脑上装了网易云客户端吗?)"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")  # 走隧道挂成连接器,全端(含手机)可用
