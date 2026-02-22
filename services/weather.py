import httpx
from typing import Optional, Dict, Any, Tuple

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes that indicate active precipitation
# 51-67: drizzle / rain / freezing rain
# 71-77: snow / snow grains
# 80-86: rain showers / snow showers
# 95-99: thunderstorm
PRECIP_CODES = frozenset(range(51, 68)) | frozenset(range(71, 78)) | frozenset(range(80, 87)) | {95, 96, 99}


async def fetch_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "windspeed_10m,winddirection_10m,relativehumidity_2m,precipitation,weathercode",
        "wind_speed_unit": "mph",
        "forecast_days": 1,
        "timezone": "America/New_York",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(OPEN_METEO_URL, params=params)
        r.raise_for_status()
        return r.json()


def parse_weather_hour(
    weather_json: Optional[Dict[str, Any]],
    iso_timestamp: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], bool]:
    """Return (wind_speed_mph, wind_dir_deg, humidity_pct, is_precipitation)."""
    if not weather_json:
        return None, None, None, False

    hourly = weather_json.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return None, None, None, False

    # Find the matching hour; default to the first entry
    idx = 0
    if iso_timestamp:
        target = iso_timestamp[:13]  # e.g. "2026-02-22T16"
        for i, t in enumerate(times):
            if t[:13] == target:
                idx = i
                break

    def _get(field: str, fallback=None):
        vals = hourly.get(field, [])
        return vals[idx] if idx < len(vals) else fallback

    wind_speed  = _get("windspeed_10m")
    wind_dir    = _get("winddirection_10m")
    humidity    = _get("relativehumidity_2m")
    precip      = _get("precipitation", 0.0) or 0.0
    weathercode = int(_get("weathercode", 0) or 0)

    is_precipitation = (weathercode in PRECIP_CODES) or (precip > 0.0)

    return wind_speed, wind_dir, humidity, is_precipitation
