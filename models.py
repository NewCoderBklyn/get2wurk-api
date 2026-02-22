from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

class Prefs(BaseModel):
    bike_allowed: bool = True
    transit_allowed: bool = True
    ebike_headwind_threshold_mph: float = 9.0
    humidity_threshold_pct: float = 80.0
    preferred_dest_station_name: Optional[str] = None

class RecommendRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    depart_at: Optional[datetime] = None
    prefs: Prefs = Prefs()

class CitiBikeStation(BaseModel):
    station_id: str
    name: str
    lat: float
    lon: float
    ebikes_available: int
    classic_available: int
    docks_available: int

class Rationale(BaseModel):
    wind_speed_mph: Optional[float] = None
    wind_direction_from_deg: Optional[float] = None
    headwind_mph: Optional[float] = None
    humidity_pct: Optional[float] = None
    is_precipitation: Optional[bool] = None
    rule_triggered: Optional[str] = None
    citibike_origin: Optional[CitiBikeStation] = None
    citibike_destination: Optional[CitiBikeStation] = None
    alerts: List[str] = []

class RecommendResponse(BaseModel):
    recommendation: str
    bike_type: Literal["classic","ebike","none"]
    summary: str
    eta_minutes: Optional[int] = None
    rationale: Rationale
    plan_b: Optional[str] = None

class RecommendAddrRequest(BaseModel):
    origin_addr: str
    destination_addr: str
    depart_at: Optional[datetime] = None
    prefs: Prefs = Prefs()
