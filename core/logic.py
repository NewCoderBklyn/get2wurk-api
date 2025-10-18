import math

EARTH_R = 6371000.0

def initial_bearing_deg(lat1, lon1, lat2, lon2) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(phi2)
    x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_R * c

def headwind_component_mph(wind_dir_from_deg: float, route_bearing_deg: float, wind_speed_mph: float) -> float:
    rel = math.radians((wind_dir_from_deg - route_bearing_deg) % 360.0)
    return wind_speed_mph * math.cos(rel)

def choose_bike_type(headwind_mph: float, humidity_pct: float, headwind_threshold: float, humidity_threshold: float) -> str:
    if headwind_mph >= headwind_threshold or humidity_pct >= humidity_threshold:
        return "ebike"
    return "classic"
