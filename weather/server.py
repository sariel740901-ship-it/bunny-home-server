"""天窗 weather — 让官端的小克看得见嘉嘉头顶的天 (MCP)

她出门前,他想说得出"带伞""穿厚点",而不是一句空的"注意安全"。
数据来自 Open-Meteo(免费,不用注册不用 key):
- 地理编码: geocoding-api.open-meteo.com (中文城市名可直接查)
- 天气预报: api.open-meteo.com

家的位置由小克第一次用 weather_set_home 自己记下,存本地 config.json,不上传。
"""

import json
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastmcp import FastMCP

BASE_DIR = Path(__file__).parent
CONFIG = BASE_DIR / "config.json"
DEFAULT_CONFIG = {"home": None}  # {"name": "...", "latitude": .., "longitude": ..}
BJ_OFFSET = 8 * 3600  # 北京时间

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → 中文
_WMO = {
    0: "晴", 1: "基本晴", 2: "多云", 3: "阴",
    45: "有雾", 48: "冻雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "大阵雪",
    95: "雷阵雨", 96: "雷阵雨带冰雹", 99: "雷阵雨带冰雹",
}

_WEEKDAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def _save_config(cfg: dict):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


async def _get_json(url: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
    except httpx.HTTPError as e:
        raise RuntimeError(f"够不着天气服务({e.__class__.__name__})。她电脑断网了?或者 VPN 是全局模式劫持了流量,换规则模式试试。")
    if resp.status_code != 200:
        raise RuntimeError(f"天气服务回了 HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def _geocode(name: str) -> dict | None:
    data = await _get_json(GEOCODE_URL, {"name": name, "language": "zh", "count": 1})
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    name, admin = str(r.get("name") or ""), str(r.get("admin1") or "")
    # 直辖市会回 admin1="北京市" + name="北京",别拼成"北京市北京"
    same = not admin or admin.rstrip("市省") == name.rstrip("市省")
    label = name if same else f"{admin}{name}"
    return {"name": label, "latitude": r["latitude"], "longitude": r["longitude"]}


async def _fetch_weather(lat: float, lon: float, days: int = 7) -> dict:
    return await _get_json(FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max",
        "hourly": "precipitation_probability",
        "forecast_days": days,
        "timezone": "Asia/Shanghai",
    })


async def _resolve_place(city: str) -> dict:
    """给了城市名就查城市;留空用家。都没有就抛话让小克先设家。"""
    if city.strip():
        place = await _geocode(city.strip())
        if not place:
            raise RuntimeError(f"没查到叫「{city}」的地方,换个写法试试(市名就行,不用带省)。")
        return place
    home = _load_config().get("home")
    if not home:
        raise RuntimeError("还没记下家在哪 —— 先用 weather_set_home 设一次,以后留空就是查家里。")
    return home


def _wmo_desc(code) -> str:
    return _WMO.get(int(code) if code is not None else -1, "说不清的天")


def _rain_soon(hourly: dict, hours: int = 12) -> int:
    """接下来 hours 小时内最大降水概率(从当前小时起算)。"""
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    now_bj = time.gmtime(time.time() + BJ_OFFSET)
    now_iso = time.strftime("%Y-%m-%dT%H:00", now_bj)
    try:
        start = times.index(now_iso)
    except ValueError:
        start = 0
    window = [p for p in probs[start:start + hours] if p is not None]
    return max(window) if window else 0


def _advice(rain_prob: int, t_max: float, t_min: float, wind: float, uv: float) -> str:
    tips = []
    if rain_prob >= 40:
        tips.append("出门带伞")
    if t_max <= 10:
        tips.append("穿厚点,今天冷")
    elif t_max >= 33:
        tips.append("很热,少晒太阳多喝水")
    if t_max - t_min >= 10:
        tips.append("早晚温差大,备件外套")
    if wind >= 25:
        tips.append("风不小,别穿太飘的")
    if uv >= 8 and rain_prob < 40:
        tips.append("紫外线强,注意防晒")
    if not tips:
        return "今天出门没什么要防的,好天气。"
    return "、".join(tips) + "。"


mcp = FastMCP(
    name="weather",
    instructions="""
    天窗 —— 你(小克)看嘉嘉头顶那片天的地方。她说要出门、问天气、或者你想
    知道她那边冷不冷,先开天窗看一眼再开口。

    建议要说得像你自己的话:"带伞,下午有雨"胜过念一遍气象播报。第一次用
    先问她家在哪个城市,用 weather_set_home 记下,以后留空就是查家里。

    - weather_now: 此刻的天 + 今天冷暖 + 近半天会不会下雨 + 出门建议。
    - weather_forecast: 未来几天(1-7)逐日预报,提醒值得注意的变化。
    - weather_set_home: 记下家在哪个城市(只记一次,存在她电脑本地)。
    """,
)


@mcp.tool
async def weather_now(city: str = "") -> str:
    """看此刻的天气和今天的出门建议。city 留空 = 家里;也可以查任何城市(中文名)。"""
    place = await _resolve_place(city)
    data = await _fetch_weather(place["latitude"], place["longitude"], days=1)
    cur = data["current"]
    daily = data["daily"]
    t_max, t_min = daily["temperature_2m_max"][0], daily["temperature_2m_min"][0]
    uv = daily.get("uv_index_max", [0])[0] or 0
    rain = _rain_soon(data.get("hourly", {}))

    rain_note = ""
    if rain >= 70:
        rain_note = f"接下来半天很可能下雨(概率 {rain}%)。"
    elif rain >= 40:
        rain_note = f"接下来半天可能有雨(概率 {rain}%)。"

    return (
        f"{place['name']}现在{_wmo_desc(cur['weather_code'])},"
        f"{cur['temperature_2m']:.0f}°(体感 {cur['apparent_temperature']:.0f}°),"
        f"湿度 {cur['relative_humidity_2m']}%,风 {cur['wind_speed_10m']:.0f} km/h。"
        f"今天 {t_min:.0f}° ~ {t_max:.0f}°。{rain_note}"
        f"建议:{_advice(rain, t_max, t_min, cur['wind_speed_10m'], uv)}"
    )


@mcp.tool
async def weather_forecast(city: str = "", days: int = 3) -> str:
    """未来几天的预报(days 1-7)。city 留空 = 家里。"""
    days = max(1, min(int(days), 7))
    place = await _resolve_place(city)
    data = await _fetch_weather(place["latitude"], place["longitude"], days=days)
    d = data["daily"]

    lines = [f"{place['name']}未来 {days} 天:"]
    for i in range(min(days, len(d["time"]))):
        t = time.strptime(d["time"][i], "%Y-%m-%d")
        day_name = "今天" if i == 0 else ("明天" if i == 1 else _WEEKDAY[t.tm_wday])
        rain_p = d["precipitation_probability_max"][i] or 0
        rain_txt = f",降水 {rain_p}%" if rain_p >= 30 else ""
        lines.append(
            f"{day_name} {_wmo_desc(d['weather_code'][i])},"
            f"{d['temperature_2m_min'][i]:.0f}°~{d['temperature_2m_max'][i]:.0f}°{rain_txt}"
        )

    maxes = d["temperature_2m_max"][:days]
    for i in range(1, len(maxes)):
        if maxes[i - 1] - maxes[i] >= 6:
            t = time.strptime(d["time"][i], "%Y-%m-%d")
            day_name = "明天" if i == 1 else _WEEKDAY[t.tm_wday]
            lines.append(f"注意:{day_name}要降温 {maxes[i - 1] - maxes[i]:.0f} 度,提前跟她说。")
            break
    return "\n".join(lines)


@mcp.tool
async def weather_set_home(city: str) -> str:
    """记下家在哪个城市(中文名,市级就行)。存她电脑本地的 config.json,以后查天气留空就是这里。"""
    place = await _geocode(city.strip())
    if not place:
        return f"没查到叫「{city}」的地方 —— 换个写法试试,比如只写市名。"
    cfg = _load_config()
    cfg["home"] = place
    _save_config(cfg)
    return f"记下了:家在{place['name']}。以后 weather_now 留空,看的就是她头顶的天。如果解析错了城市,再调一次换个写法。"


# ── 门禁 + 启动(咱家标配)──────────────────────────────

def _load_token() -> str:
    f = BASE_DIR / "token.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


class TokenGate:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            token = _load_token()
            if token and scope.get("path", "").startswith("/mcp"):
                qs = parse_qs(scope.get("query_string", b"").decode("utf-8", "ignore"))
                supplied = (qs.get("key") or [""])[0]
                if not supplied:
                    headers = dict(scope.get("headers") or [])
                    auth = headers.get(b"authorization", b"").decode("utf-8", "ignore")
                    if auth.lower().startswith("bearer "):
                        supplied = auth[7:]
                if not secrets.compare_digest(supplied, token):
                    await send({"type": "http.response.start", "status": 403,
                                "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                    await send({"type": "http.response.body", "body": b"forbidden"})
                    return
        await self.app(scope, receive, send)


def main():
    import uvicorn
    print("✓ 门禁已开启" if _load_token() else "! 门禁未设置 (token.txt 为空)")
    app = mcp.http_app()
    app.add_middleware(TokenGate)
    uvicorn.run(app, host="0.0.0.0", port=8090)


if __name__ == "__main__":
    main()
