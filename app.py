import os
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from models import RecommendRequest, RecommendResponse, Rationale, CitiBikeStation, RecommendAddrRequest
from core.logic import initial_bearing_deg, headwind_component_mph, choose_bike_type
from services.weather import fetch_nws_hourly, parse_wind_humidity_hour
from services.citibike import (
    fetch_citibike,
    merge_info_status,
    nearest_station,
    nearest_with_ebikes,
    nearest_with_classic,
    nearest_with_docks,
    find_station_by_name,
)
from services.mta import fetch_alerts
from services.geocode import geocode_one

# =========================
# API Key Security (Header)
# =========================
API_KEY = os.getenv("PUBLIC_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_key(x_api_key: str = Security(api_key_header)) -> bool:
    # If a key is configured, require it to match; if no key set, allow all
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ===========
# FastAPI app
# ===========
app = FastAPI(title="GET2WURK API", version="0.2.0")

# CORS (open so your frontend can call it)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check for Render
@app.get("/healthz")
async def healthz():
    return {"ok": True}

# ======================
# Core Recommendation API
# ======================
@app.post("/v1/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest, auth: bool = Security(require_key)):
    # Weather
    hourly = await fetch_nws_hourly(req.origin.lat, req.origin.lon)
    wind_speed_mph, wind_dir_from_deg, humidity_pct = parse_wind_humidity_hour(
        hourly, req.depart_at.isoformat() if req.depart_at else None
    )
    if humidity_pct is None:
        humidity_pct = 50.0  # reasonable fallback

    # Citi Bike data
    try:
        info_json, status_json = await fetch_citibike()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Citi Bike fetch failed: {e}")
    stations = merge_info_status(info_json, status_json)

    # Nearest origin/dest stations
    s_origin = nearest_station(req.origin.lat, req.origin.lon, stations)
    s_dest = nearest_station(req.destination.lat, req.destination.lon, stations)
    if not s_origin or not s_dest:
        raise HTTPException(status_code=404, detail="No nearby Citi Bike stations found.")

    # Preferred destination (your default: W 58 St & 11 Ave) if docks available
    pref_name = getattr(req.prefs, "preferred_dest_station_name", None) or "W 58 St & 11 Ave"
    preferred = find_station_by_name(stations, pref_name)
    if preferred and (preferred.get("docks_available") or 0) > 0:
        s_dest = preferred

    # Wind vs route bearing
    bearing = initial_bearing_deg(req.origin.lat, req.origin.lon, req.destination.lat, req.destination.lon)
    headwind = 0.0
    if wind_speed_mph is not None and wind_dir_from_deg is not None:
        headwind = headwind_component_mph(wind_dir_from_deg, bearing, wind_speed_mph)

    bike_type = "none"
    plan_b_note = None

    # Choose bike type based on thresholds and availability
    if req.prefs.bike_allowed:
        bike_type = choose_bike_type(
            headwind, humidity_pct,
            req.prefs.ebike_headwind_threshold_mph,
            req.prefs.humidity_threshold_pct
        )

        if bike_type == "ebike":
            if (s_origin["ebikes_available"] or 0) == 0:
                alt, dist_m = nearest_with_ebikes(req.origin.lat, req.origin.lon, stations, max_meters=700.0)
                if alt:
                    plan_b_note = f"Origin has 0 e-bikes; nearest with e-bikes is {alt['name']} (~{int(dist_m)} m)."
                    s_origin = alt
                else:
                    if (s_origin["classic_available"] or 0) > 0:
                        bike_type = "classic"
                        plan_b_note = "Origin has no e-bikes; using classic instead."
                    else:
                        bike_type = "none"

        elif bike_type == "classic":
            if (s_origin["classic_available"] or 0) == 0:
                if (s_origin["ebikes_available"] or 0) > 0:
                    bike_type = "ebike"
                    plan_b_note = "No classic bikes at origin; upgraded to e-bike."
                else:
                    alt_e, dist_e = nearest_with_ebikes(req.origin.lat, req.origin.lon, stations, max_meters=700.0)
                    alt_c, dist_c = nearest_with_classic(req.origin.lat, req.origin.lon, stations, max_meters=700.0)
                    pick = None
                    if alt_c and alt_e:
                        pick = alt_c if dist_c <= dist_e else alt_e
                        bike_type = "classic" if pick is alt_c else "ebike"
                    elif alt_c:
                        pick = alt_c; bike_type = "classic"
                    elif alt_e:
                        pick = alt_e; bike_type = "ebike"
                    if pick:
                        plan_b_note = f"Origin empty; nearest with bikes is {pick['name']} (~{int(dist_c if pick is alt_c else dist_e)} m)."
                        s_origin = pick
                    else:
                        bike_type = "none"

    # Destination docks Plan B
    dock_alt_msg = None
    if bike_type in ("classic", "ebike") and (s_dest["docks_available"] or 0) < 3:
        alt_d, dist_d = nearest_with_docks(req.destination.lat, req.destination.lon, stations, min_docks=5, max_meters=700.0)
        if alt_d:
            dock_alt_msg = f"Destination docks low at {s_dest['name']}; nearby with docks: {alt_d['name']} (~{int(dist_d)} m)."

    # MTA alerts
    alerts = await fetch_alerts()

    # Final recommendation & summary
    if bike_type == "none" and not req.prefs.transit_allowed:
        recommendation = "Walking recommended; no bikes available and transit disabled in preferences."
        summary = recommendation
        plan_b = None
    elif bike_type == "none" and req.prefs.transit_allowed:
        recommendation = "Transit fallback recommended (bikes unavailable or weather unfavorable)."
        summary = f"Headwind {headwind:.1f} mph, humidity {humidity_pct:.0f}%. Take subway/bus as Plan A."
        plan_b = f"Nearest origin station {s_origin['name']} has no suitable bikes; consider nearby subway entrance."
    else:
        recommendation = f"Take a {bike_type} from {s_origin['name']} to {s_dest['name']}."
        summary = f"{bike_type.upper()} due to headwind {headwind:.1f} mph and humidity {humidity_pct:.0f}%."
        notes = [n for n in [plan_b_note, dock_alt_msg] if n]
        plan_b = " ".join(notes) if notes else "Transit fallback if docks are full at destination."

    rationale = Rationale(
        wind_speed_mph=wind_speed_mph,
        wind_direction_from_deg=wind_dir_from_deg,
        headwind_mph=headwind,
        humidity_pct=humidity_pct,
        rule_triggered=f"headwind>={req.prefs.ebike_headwind_threshold_mph} or humidity>={req.prefs.humidity_threshold_pct}",
        citibike_origin=CitiBikeStation(
            station_id=s_origin["station_id"], name=s_origin["name"], lat=s_origin["lat"], lon=s_origin["lon"],
            ebikes_available=s_origin["ebikes_available"], classic_available=s_origin["classic_available"], docks_available=s_origin["docks_available"]
        ),
        citibike_destination=CitiBikeStation(
            station_id=s_dest["station_id"], name=s_dest["name"], lat=s_dest["lat"], lon=s_dest["lon"],
            ebikes_available=s_dest["ebikes_available"], classic_available=s_dest["classic_available"], docks_available=s_dest["docks_available"]
        ),
        alerts=alerts
    )

    return RecommendResponse(
        recommendation=recommendation,
        bike_type=bike_type if bike_type in ("classic", "ebike") else "none",
        summary=summary,
        eta_minutes=None,
        rationale=rationale,
        plan_b=plan_b
    )

@app.post("/v1/recommend_addr", response_model=RecommendResponse)
async def recommend_addr(req: RecommendAddrRequest, auth: bool = Security(require_key)):
    o = await geocode_one(req.origin_addr)
    d = await geocode_one(req.destination_addr)
    if not o or not d:
        raise HTTPException(status_code=404, detail="Could not geocode one or both addresses.")
    rr = RecommendRequest(
        origin={"lat": o[0], "lon": o[1]},
        destination={"lat": d[0], "lon": d[1]},
        depart_at=req.depart_at,
        prefs=req.prefs
    )
    return await recommend(rr, auth=auth)

@app.get("/v1/quick")
async def quick(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    preferred_dest_station_name: str = "W 58 St & 11 Ave",
    auth: bool = Security(require_key)
):
    rr = RecommendRequest(
        origin={"lat": origin_lat, "lon": origin_lon},
        destination={"lat": dest_lat, "lon": dest_lon},
    )
    # honor preferred destination station name via prefs
    setattr(rr.prefs, "preferred_dest_station_name", preferred_dest_station_name)
    res = await recommend(rr, auth=auth)
    return f"{res.summary} | {res.recommendation}"
