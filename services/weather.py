import httpx
from typing import Optional, Dict, Any

NWS_POINTS = "https://api.weather.gov/points/{lat},{lon}"

async def fetch_nws_hourly(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    headers = {"User-Agent":"GET2WURK/0.2 (mvp)"}
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        r = await client.get(NWS_POINTS.format(lat=lat, lon=lon))
        r.raise_for_status()
        meta = r.json()
        hourly_url = meta.get("properties", {}).get("forecastHourly")
        if not hourly_url:
            return None
        hr = await client.get(hourly_url)
        hr.raise_for_status()
        return hr.json()

def parse_wind_humidity_hour(hourly_json, iso_timestamp: Optional[str]=None):
    if not hourly_json:
        return None, None, None
    periods = hourly_json.get("properties", {}).get("periods", [])
    if not periods:
        return None, None, None
    p = periods[0] if iso_timestamp is None else next((x for x in periods if x.get("startTime","").startswith(iso_timestamp[:13])), periods[0])
    ws = p.get("windSpeed") or "0 mph"
    try:
        parts = [int(s) for s in ws.replace("mph"," ").replace("to"," ").split() if s.isdigit()]
        wind_speed_mph = max(parts) if parts else 0
    except:
        wind_speed_mph = 0
    wdir_txt = p.get("windDirection") or "N"
    compass = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    degs = [0,22.5,45,67.5,90,112.5,135,157.5,180,202.5,225,247.5,270,292.5,315,337.5]
    if wdir_txt in compass:
        wind_dir_from_deg = degs[compass.index(wdir_txt)]
    else:
        try:
            wind_dir_from_deg = float(wdir_txt)
        except:
            wind_dir_from_deg = 0.0
    humidity_pct = None
    rh = p.get("relativeHumidity")
    if isinstance(rh, dict):
        humidity_pct = rh.get("value")
    return wind_speed_mph, wind_dir_from_deg, humidity_pct
