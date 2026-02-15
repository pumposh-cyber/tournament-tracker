import sys
import re
from datetime import datetime
from app import app
from models import Tournament
from app import db

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def parse_date_range(date_str):
    date_str = date_str.replace("\u2013", "-").replace("\u2014", "-").strip()

    m = re.match(r"(\w+)\s+(\d{1,2})(?:\s*-\s*\d{1,2})?,?\s*(\d{4})", date_str)
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = int(m.group(3))
        month = MONTH_MAP.get(month_str)
        if month:
            return datetime(year, month, day)

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def import_excel(filepath):
    import openpyxl
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active

    rows = list(ws.iter_rows(min_row=1, values_only=True))
    if not rows:
        print("No data found in spreadsheet.")
        return

    headers = [str(h).strip() if h else "" for h in rows[0]]
    print(f"Found columns: {headers}")

    with app.app_context():
        db.create_all()
        existing = Tournament.query.count()
        if existing > 0:
            print(f"Clearing {existing} existing records...")
            Tournament.query.delete()
            db.session.commit()

        count = 0
        for row in rows[1:]:
            data = {}
            for i, header in enumerate(headers):
                data[header] = row[i] if i < len(row) else None

            date_str = str(data.get("Dates", "") or "")
            parsed_date = parse_date_range(date_str)
            if not parsed_date:
                print(f"Skipping row with unparseable date: '{date_str}'")
                continue

            tournament = Tournament(
                event=str(data.get("Event", "") or "").strip(),
                dates_display=date_str.strip(),
                date_start=parsed_date,
                days=str(data.get("Day(s)", "") or "").strip(),
                city=str(data.get("City", "") or "").strip(),
                venue=str(data.get("Venue", "") or "").strip(),
                hotel_recommendation=str(data.get("Hotel Recommendation", "") or "").strip(),
                hotel_link_notes=str(data.get("Hotel Link / Notes", "") or "").strip(),
                car_rental_recommendation=str(data.get("Car Rental Recommendation", "") or "").strip(),
                hotel_booking_status=str(data.get("Hotel Booking Status", "") or "").strip(),
                car_booking_status=str(data.get("Car Booking Status", "") or "").strip(),
                notes=str(data.get("Notes / Status", "") or "").strip(),
            )
            db.session.add(tournament)
            count += 1

        db.session.commit()
        print(f"Successfully imported {count} tournaments.")


def import_csv(filepath):
    import csv
    with app.app_context():
        db.create_all()
        existing = Tournament.query.count()
        if existing > 0:
            print(f"Clearing {existing} existing records...")
            Tournament.query.delete()
            db.session.commit()

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                date_str = row.get("Dates", "").strip()
                parsed_date = parse_date_range(date_str)
                if not parsed_date:
                    print(f"Skipping row with unparseable date: '{date_str}'")
                    continue

                tournament = Tournament(
                    event=row.get("Event", row.get("Events", "")).strip(),
                    dates_display=date_str,
                    date_start=parsed_date,
                    days=row.get("Day(s)", "").strip(),
                    city=row.get("City", "").strip(),
                    venue=row.get("Venue", "").strip(),
                    hotel_recommendation=row.get("Hotel Recommendation", "").strip(),
                    hotel_link_notes=row.get("Hotel Link / Notes", "").strip(),
                    car_rental_recommendation=row.get("Car Rental Recommendation", "").strip(),
                    hotel_booking_status=row.get("Hotel Booking Status", "").strip(),
                    car_booking_status=row.get("Car Booking Status", "").strip(),
                    notes=row.get("Notes / Status", row.get("Notes", "")).strip(),
                )
                db.session.add(tournament)
                count += 1

            db.session.commit()
            print(f"Successfully imported {count} tournaments.")


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "attached_assets/Urban_15U_Merged_Tournament_Planner_2026_1771138119187.xlsx"

    if filepath.endswith(".xlsx"):
        import_excel(filepath)
    else:
        import_csv(filepath)
