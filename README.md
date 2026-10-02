# Spotter Labs - Fuel-Optimized Route Planner API

A production-grade Django REST API that calculates driving routes between two US locations, identifies cost-effective fuel stops based on retail fuel prices, respects vehicle range constraints (500 miles max range, 10 MPG), and provides the total money spent on fuel.

---

## Highlights & Architectural Decisions

1. **Routing Strategy (Strictly 1 Free API Call)**:
   - Uses **OSRM (Open Source Routing Machine)** public demo cluster.
   - Fetches the entire route geometry, distance, and duration in **exactly 1 single HTTP request** without requiring API keys or rate limits.

2. **Next-Cheaper-Station Fuel Optimization Algorithm**:
   - Vehicle starts at mile 0 with a **full tank (500 miles range / 50 gallons)**.
   - Fuel consumed from the starting tank is priced at the cheapest reachable station near the origin.
   - Instead of naive heuristic fill-ups that overpay, the algorithm looks ahead up to 500 miles for the first cheaper station:
     - **If a cheaper station exists ahead**: purchases **only enough fuel** to reach that cheaper station.
     - **If no cheaper station exists ahead**: recognizes the current stop as a local price minimum and fills to the maximum 500-mile capacity.
     - **If destination is within reach**: buys only what is strictly needed to reach the destination.
   - **Infeasible Route Detection**: If any segment between reachable stations exceeds 500 miles, the API responds with **HTTP 422 Unprocessable Entity** rather than pretending the vehicle could travel beyond tank capacity.

3. **Spatial Corridor Projection**:
   - Stations from `fuel-prices-for-be-assessment.xlsx` (7,524 US fuel stations) are indexed in SQLite.
   - Corridor matching projects candidate stations directly onto polyline line segments using planar vector projection, accurately calculating perpendicular distance and mile markers along the highway.

4. **US Geocoding & Validation**:
   - Geocoding powered by OpenStreetMap Nominatim with strict `countrycodes=us`.
   - Filters out commercial POIs (cafes, shops) and validates against the contiguous USA bounding box (`lat: 24.39 to 49.38`, `lon: -125.0 to -66.93`).
   - Uses an in-memory cache to prevent Nominatim rate-limits on repeated queries.
   - Rejects identical start and finish inputs (`HTTP 400`).

---

## Project Structure

```text
Spotter_Labs_Assignment/
├── core/
│   ├── settings.py           # Project settings, DB path config, cache
│   ├── urls.py               # Main URL router
│   └── wsgi.py
├── trips/
│   ├── management/
│   │   └── commands/
│   │       └── load_fuel_stations.py # Ingestion command (atomic, CommandError)
│   ├── services/
│   │   ├── geocoding.py      # Nominatim geocoder + US bounds + caching
│   │   ├── osrm.py           # OSRM client (single call) & polyline decoder
│   │   ├── corridor.py       # Segment projection & corridor search
│   │   └── optimizer.py      # Next-cheaper-station greedy optimizer
│   ├── models.py             # FuelStation model with spatial indexes
│   ├── admin.py              # Django admin registration
│   ├── views.py              # plan_route and health_check API endpoints
│   ├── urls.py               # /api/route/ and /api/health/
│   └── tests.py              # Comprehensive test suite
├── fuel-prices-for-be-assessment.xlsx # Excel fuel prices dataset
├── Dockerfile                # Multi-stage containerization
├── docker-compose.yml        # Docker compose service with persisted volume
├── entrypoint.sh             # Auto-migrates and loads fuel stations
├── requirements.txt          # Python dependencies
├── manage.py
└── README.md
```

---

## Quickstart with Docker (1 Command)

```bash
docker compose up --build
```
The container will:
1. Run all migrations.
2. Ingest all 7,524 stations from the included Excel file into SQLite with atomic transactions.
3. Start the server at `http://127.0.0.1:8000/`.

---

## Quickstart Locally

```bash
# 1. Virtual environment & dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Database migrations & load stations
python manage.py migrate
python manage.py load_fuel_stations --clear

# 3. Run test suite
python manage.py test

# 4. Start local development server
python manage.py runserver
```

---

## API Reference

### 1. Plan Route
- **Endpoint:** `POST /api/route/`
- **Headers:** `Content-Type: application/json`

#### Request Body
```json
{
  "start": "Austin, TX",
  "finish": "Dallas, TX"
}
```

#### Response (`200 OK`)
```json
{
  "start": {
    "name": "Austin, TX",
    "display_name": "Austin, Travis County, Texas, United States",
    "lat": 30.2711286,
    "lon": -97.7436995
  },
  "finish": {
    "name": "Dallas, TX",
    "display_name": "Dallas, Dallas County, Texas, United States",
    "lat": 32.7762719,
    "lon": -96.7968559
  },
  "trip": {
    "distance_miles": 195.2,
    "duration_hours": 3.12,
    "mpg": 10.0,
    "max_vehicle_range_miles": 500.0
  },
  "fuel_optimization": {
    "total_fuel_cost_usd": 54.85,
    "total_gallons_consumed": 19.52,
    "total_gallons_purchased_en_route": 0.0,
    "origin_fuel_price_usd": 2.81,
    "total_stops": 0,
    "stops": []
  },
  "map": {
    "encoded_polyline": "...",
    "geojson": {
      "type": "LineString",
      "coordinates": [[-97.7436, 30.2711], ...]
    }
  }
}
```

### 2. Health Check
- **Endpoint:** `GET /api/health/`
- **Response:** `{"status": "healthy", "service": "fuel-route-optimizer"}`
