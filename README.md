# Spotter Labs - Fuel-Optimized Route Planner API

A production-ready Django REST API that calculates driving routes between two US locations, identifies cost-effective fuel stops based on retail fuel prices, respects vehicle range constraints (500 miles max range, 10 MPG), and provides the total money spent on fuel.

---

## Key Features & Constraints Met

1. **Start & Finish Within the USA**:
   - Geocodes human-readable locations (e.g., `"Austin, TX"`, `"Denver, CO"`) using Nominatim with `countrycodes=us`.
   - Filters out non-geographic entities (restaurants, shops) and validates against the contiguous USA bounding box (`lat: 24.39 to 49.38`, `lon: -125.0 to -66.93`).

2. **100% Free Routing API with Exactly 1 Call**:
   - Integrates **OSRM (Open Source Routing Machine)**.
   - Requires **no API key / registration**.
   - Fetches the entire route geometry, distance, and duration in **exactly 1 single HTTP request**.

3. **Fuel Price Dataset & Local Spatial Index**:
   - Ingests `fuel-prices-for-be-assessment.xlsx` (7,524 US fuel stations) into SQLite with coordinates.
   - Performs corridor spatial lookups in local memory and SQLite (~2 ms) without hitting external rate limits.

4. **Greedy Fuel Optimization Algorithm**:
   - **Max Vehicle Range**: 500 miles.
   - **Fuel Economy**: 10 Miles Per Gallon (MPG).
   - Starts with a full tank (500-mile range).
   - Strategically refills at the cheapest reachable stations along the road, outputting gallons refueled and dollar cost per stop.

5. **Compact Map Geometry**:
   - Returns both Google-compatible `encoded_polyline` and sampled GeoJSON LineString (reduced from 3.2 MB down to ~23 KB for fast responses).

---

## Project Structure

```text
Spotter_Labs_Assignment/
├── core/
│   ├── settings.py           # Project settings & .env loading
│   ├── urls.py               # Main URL router
│   └── wsgi.py
├── trips/
│   ├── management/
│   │   └── commands/
│   │       └── load_fuel_stations.py # Ingestion command for Excel data
│   ├── services/
│   │   ├── geocoding.py      # Nominatim geocoder + US boundary checks
│   │   ├── osrm.py           # OSRM client (single call) & polyline decoder
│   │   ├── corridor.py       # Haversine distance & corridor search
│   │   └── optimizer.py      # Fuel stop optimizer (500 mi range, 10 MPG)
│   ├── models.py             # FuelStation model with spatial indexes
│   ├── views.py              # plan_route API endpoint
│   ├── urls.py               # /api/route/ URL pattern
│   └── tests.py              # Unit tests
├── requirements.txt          # Dependencies
├── manage.py
└── README.md
```

---

## Setup & Running Locally

### 1. Set Up Environment

```bash
git clone https://github.com/Dhakal29/Spotter_Labs_Assignment.git
cd Spotter_Labs_Assignment

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

### 3. Run Migrations & Load Fuel Stations

```bash
python manage.py migrate
python manage.py load_fuel_stations --clear
```

### 4. Run Automated Tests

```bash
python manage.py test trips
```

### 5. Start Development Server

```bash
python manage.py runserver
```

---

## API Reference

### Plan Route

- **Endpoint:** `POST /api/route/`
- **Headers:** `Content-Type: application/json`

#### Request
```json
{
  "start": "Dallas, TX",
  "finish": "Denver, CO"
}
```

#### Response (`200 OK`)
```json
{
  "start": {
    "name": "Dallas, TX",
    "display_name": "Dallas, Dallas County, Texas, United States",
    "lat": 32.7762719,
    "lon": -96.7968559
  },
  "finish": {
    "name": "Denver, CO",
    "display_name": "Denver, Colorado, United States",
    "lat": 39.7392364,
    "lon": -104.984862
  },
  "trip": {
    "distance_miles": 795.05,
    "duration_hours": 14.33,
    "mpg": 10.0,
    "max_vehicle_range_miles": 500.0
  },
  "fuel_optimization": {
    "total_fuel_cost_usd": 101.52,
    "total_gallons_purchased": 36.65,
    "total_stops": 2,
    "stops": [
      {
        "stop_number": 1,
        "station_name": "7-ELEVEN #218",
        "address": "US-287, MM 176",
        "city": "Harrold",
        "state": "TX",
        "price_per_gallon": 2.687,
        "mile_along_route": 160.8,
        "gallons_refueled": 19.82,
        "cost_usd": 53.26,
        "coordinates": {
          "latitude": 34.0841,
          "longitude": -99.0345
        }
      }
    ]
  },
  "map": {
    "encoded_polyline": "u`_wEz}mpQ...",
    "geojson": {
      "type": "LineString",
      "coordinates": [[-96.7968, 32.7762], ...]
    }
  }
}
```
