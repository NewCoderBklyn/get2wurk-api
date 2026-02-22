import os
import httpx
from typing import Dict, Any, List, Tuple, Optional
from core.logic import haversine_m

GBFS_BASE = os.getenv("CITIBIKE_GBFS_BASE", "https://gbfs.citibikenyc.com/gbfs/en")
INFO_URL = f"{GBFS_BASE}/station_information.json"
STATUS_URL = f"{GBFS_BASE}/station_status.json"

async def fetch_citibike() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        info = await client.get(INFO_URL)
        status = await client.get(STATUS_URL)
        info.raise_for_status(); status.raise_for_status()
        return info.json(), status.json()

def nearest_station(lat: float, lon: float, stations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    best = None
    best_d = 1e18
    for s in stations:
        slat = s.get("lat"); slon = s.get("lon")
        if slat is None or slon is None:
            continue
        d = haversine_m(lat, lon, slat, slon)
        if d < best_d:
            best = s; best_d = d
    return best

def merge_info_status(info_json: Dict[str, Any], status_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    info_map = {s["station_id"]: s for s in info_json.get("data", {}).get("stations", [])}
    out = []
    for st in status_json.get("data", {}).get("stations", []):
        sid = st.get("station_id")
        base = info_map.get(sid, {})
        ebikes = st.get("num_ebikes_available", 0) or 0
        total  = st.get("num_bikes_available", 0) or 0
        out.append({
            "station_id": sid,
            "name": base.get("name"),
            "lat": base.get("lat"),
            "lon": base.get("lon"),
            "ebikes_available": ebikes,
            "classic_available": max(0, total - ebikes),
            "docks_available": st.get("num_docks_available", 0),
        })
    return out

def nearest_with_ebikes(lat: float, lon: float, stations, max_meters: float = 700.0):
    best, best_d = None, 1e18
    for s in stations:
        if (s.get("ebikes_available") or 0) > 0:
            d = haversine_m(lat, lon, s.get("lat"), s.get("lon"))
            if d < best_d:
                best, best_d = s, d
    return (best, best_d) if best_d <= max_meters else (None, None)

def nearest_with_classic(lat: float, lon: float, stations, max_meters: float = 700.0):
    best, best_d = None, 1e18
    for s in stations:
        if (s.get("classic_available") or 0) > 0:
            d = haversine_m(lat, lon, s.get("lat"), s.get("lon"))
            if d < best_d:
                best, best_d = s, d
    return (best, best_d) if best_d <= max_meters else (None, None)

def nearest_with_docks(lat: float, lon: float, stations, min_docks: int = 3, max_meters: float = 700.0):
    best, best_d = None, 1e18
    for s in stations:
        if (s.get("docks_available") or 0) >= min_docks:
            d = haversine_m(lat, lon, s.get("lat"), s.get("lon"))
            if d < best_d:
                best, best_d = s, d
    return (best, best_d) if best_d <= max_meters else (None, None)

def find_station_by_name(stations, name: str):
    target = (name or "").strip().lower()
    if not target:
        return None
    for s in stations:
        if (s.get("name") or "").strip().lower() == target:
            return s
    for s in stations:
        nm = (s.get("name") or "").lower()
        if target in nm:
            return s
    return None
