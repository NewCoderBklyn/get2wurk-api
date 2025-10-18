# GET2WURK API (Production Bundle)

Env Vars:
- PUBLIC_API_KEY (required) → clients send as X-API-Key
- CITIBIKE_GBFS_BASE (default provided)
- OPENWEATHER_API_KEY (optional)
- MTA_API_KEY (optional)

Local Docker:
```bash
docker build -t get2wurk-api .
docker run -e PUBLIC_API_KEY=devkey -p 8000:8000 get2wurk-api
# Open http://localhost:8000/docs and use header X-API-Key: devkey
```
