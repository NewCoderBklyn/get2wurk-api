import os
from fastapi import FastAPI, HTTPException, Depends, Header, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.openapi.utils import get_openapi

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

# ✅ API key setup
API_KEY = os.getenv("PUBLIC_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_key(x_api_key: str = Security(api_key_header)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ✅ Instantiate app first
app = FastAPI(title="GET2WURK API", version="0.2.0")

# ✅ Define custom OpenAPI *after* app exists
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="GET2WURK API",
        version="0.2.0",
        routes=app.routes,
    )
    openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    openapi_schema["components"]["securitySchemes"]["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return openapi_schema

# ✅ Attach schema generator
app.openapi = custom_openapi
app.openapi_schema = None
