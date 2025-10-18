import httpx
from typing import Optional, Tuple

NOMINATIM = "https://nominatim.openstreetmap.org/search"

async def geocode_one(query: str) -> Optional[Tuple[float, float]]:
    params = {"q": query, "format": "json", "limit": 1, "addressdetails": 0}
    headers = {"User-Agent": "GET2WURK/0.2 (demo)"
    }
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        r = await client.get(NOMINATIM, params=params)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        lat = float(data[0]["lat"]); lon = float(data[0]["lon"])
        return lat, lon
