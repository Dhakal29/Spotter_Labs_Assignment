from pathlib import Path
from decimal import Decimal
import openpyxl
import pgeocode
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from trips.models import FuelStation


class Command(BaseCommand):
    help = "Loads fuel stations from the provided Excel file into SQLite with geocoded coordinates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="fuel-prices-for-be-assessment.xlsx",
            help="Path to the Excel file with fuel prices",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing fuel stations before loading",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(
                f"Fuel price file not found at '{file_path}'. "
                "Please ensure 'fuel-prices-for-be-assessment.xlsx' exists in the project root."
            )

        if options["clear"]:
            count = FuelStation.objects.count()
            FuelStation.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing stations."))

        self.stdout.write("Loading US geographical coordinates database...")
        nomi = pgeocode.Nominatim("us")
        geo_df = nomi._data

        # Map (UPPER_CITY, UPPER_STATE) -> (lat, lon)
        city_coords = {}
        for _, row in geo_df.iterrows():
            city = str(row["place_name"]).strip().upper()
            state = str(row["state_code"]).strip().upper()
            if city and state and (city, state) not in city_coords:
                city_coords[(city, state)] = (float(row["latitude"]), float(row["longitude"]))

        self.stdout.write(f"Loaded {len(city_coords)} US city coordinate mappings.")
        self.stdout.write(f"Reading Excel file: {file_path}...")

        wb = openpyxl.load_workbook(file_path, read_only=True)
        sheet = wb.active

        stations_to_create = []
        skipped_non_us = 0
        skipped_unmatched = 0

        # Excel format:
        # Col 0: OPIS Truckstop ID
        # Col 1: Truckstop Name
        # Col 2: Address
        # Col 3: City
        # Col 4: State
        # Col 5: Rack ID
        # Col 6: Retail Price

        for idx, row in enumerate(sheet.iter_rows(values_only=True)):
            if idx == 0:
                continue  # Skip header

            opis_id_raw, name, address, city, state, rack_id, price_raw = row[:7]

            if not city or not state or price_raw is None:
                continue

            city_clean = str(city).strip()
            state_clean = str(state).strip().upper()

            # Coordinates lookup
            coords = city_coords.get((city_clean.upper(), state_clean))
            if not coords:
                # If state is not in US data (e.g. Canadian provinces ON, BC, AB), skip
                if state_clean not in geo_df["state_code"].values:
                    skipped_non_us += 1
                else:
                    skipped_unmatched += 1
                continue

            lat, lon = coords
            price_val = Decimal(str(price_raw))

            station = FuelStation(
                opis_id=int(opis_id_raw) if opis_id_raw else 0,
                name=str(name).strip() if name else "Unknown Station",
                address=str(address).strip() if address else "",
                city=city_clean,
                state=state_clean,
                price=price_val,
                latitude=lat,
                longitude=lon,
            )
            stations_to_create.append(station)

        # Batch insert into database within an atomic transaction
        self.stdout.write(f"Bulk inserting {len(stations_to_create)} stations into database...")
        with transaction.atomic():
            FuelStation.objects.bulk_create(stations_to_create, batch_size=2000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully loaded {len(stations_to_create)} US fuel stations! "
                f"(Skipped {skipped_non_us} non-US stations, {skipped_unmatched} unmatched)."
            )
        )
