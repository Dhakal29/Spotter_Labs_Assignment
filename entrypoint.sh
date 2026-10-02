#!/bin/sh
set -e

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Checking if fuel stations are loaded..."
STATION_COUNT=$(python manage.py shell -c "from trips.models import FuelStation; print(FuelStation.objects.count())" | tail -n 1)
echo "Current fuel stations count: $STATION_COUNT"

if [ "$STATION_COUNT" -lt 5000 ] 2>/dev/null || [ -z "$STATION_COUNT" ]; then
    echo "==> Populating fuel stations dataset from Excel..."
    python manage.py load_fuel_stations --clear
fi

echo "==> Starting server..."
exec "$@"
