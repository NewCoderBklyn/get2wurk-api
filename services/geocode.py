import re
import httpx
from typing import Optional, Tuple

NOMINATIM = "https://nominatim.openstreetmap.org/search"

# NYC bounding box (generous — includes all 5 boroughs + close suburbs)
_NYC_LAT = (40.49, 40.92)
_NYC_LON = (-74.26, -73.68)

# Convert spoken ordinals to numeric form so Nominatim doesn't route to
# the wrong city (e.g. "Tenth Ave" → Albany instead of Manhattan).
_ORDINALS = {
    "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th",
    "fifth": "5th", "sixth": "6th", "seventh": "7th", "eighth": "8th",
    "ninth": "9th", "tenth": "10th", "eleventh": "11th", "twelfth": "12th",
}
_ORDINAL_RE = re.compile(
    r'\b(' + '|'.join(_ORDINALS.keys()) + r')\b', re.IGNORECASE
)


def _normalize(query: str) -> str:
    return _ORDINAL_RE.sub(lambda m: _ORDINALS[m.group(0).lower()], query)


def _in_nyc(lat: float, lon: float) -> bool:
    return _NYC_LAT[0] <= lat <= _NYC_LAT[1] and _NYC_LON[0] <= lon <= _NYC_LON[1]


async def geocode_one(query: str) -> Optional[Tuple[float, float]]:
    normalized = _normalize(query)
    headers = {"User-Agent": "GET2WURK/0.2 (demo)"}

    # Queries to try in order: normalized first, then with ", Manhattan NY" appended
    candidates = [normalized]
    if normalized != query or "manhattan" not in query.lower():
        candidates.append(normalized + ", Manhattan NY")

    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        last_data = None
        for q in candidates:
            params = {
                "q": q, "format": "json", "limit": 5,
                "addressdetails": 0, "countrycodes": "us",
            }
            r = await client.get(NOMINATIM, params=params)
            r.raise_for_status()
            data = r.json()
            if not data:
                continue
            last_data = data
            # Prefer any result inside the NYC bounding box
            for item in data:
                lat, lon = float(item["lat"]), float(item["lon"])
                if _in_nyc(lat, lon):
                    return lat, lon

        # Nothing in NYC bounding box — fall back to first result from any query
        if last_data:
            return float(last_data[0]["lat"]), float(last_data[0]["lon"])
        return None
