from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import os
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

logging.basicConfig(level=logging.DEBUG)

IS_DEV = os.environ.get("FLASK_ENV") == "development"


class Base(DeclarativeBase):
    pass


app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-local")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

database_url = os.environ.get("DATABASE_URL", "sqlite:///local.db" if IS_DEV else None)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

if database_url and database_url.startswith("sqlite"):
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}
else:
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        'pool_pre_ping': True,
        "pool_recycle": 300,
    }

db = SQLAlchemy(app, model_class=Base)


def seed_tournaments():
    """Seed initial tournaments and Far Western booking if the DB is empty."""
    from models import Tournament, TripBooking
    from datetime import datetime
    if Tournament.query.count() > 0:
        return
    t1 = Tournament(
        event="NCVA Far Western",
        dates_display="Apr 17-19, 2026",
        date_start=datetime(2026, 4, 17),
        days="Fri-Sun",
        city="Reno, NV",
        venue="Reno-Sparks Convention Center",
        hotel_booking_status="Booked",
        car_booking_status="Booked",
    )
    t2 = Tournament(
        event="NCVA Regional",
        dates_display="May 9-10, 2026",
        date_start=datetime(2026, 5, 9),
        days="Sat-Sun",
        city="Bay Area / Sacramento",
        venue="TBA",
    )
    t3 = Tournament(
        event="NCVA Regional Champs",
        dates_display="May 9-10, 2026",
        date_start=datetime(2026, 5, 9),
        days="Sat-Sun",
        city="TBA",
        venue="TBA",
    )
    db.session.add_all([t1, t2, t3])
    db.session.flush()  # get t1.id

    booking = TripBooking(
        tournament_id=t1.id,
        hotel_name="Extended Stay America Suites",
        hotel_address="9795 Gateway Drive, Reno, NV 89521",
        hotel_phone="775-852-5611",
        hotel_checkin="Thu Apr 16 · 3:00 PM",
        hotel_checkout="Sun Apr 19 · 11:00 AM",
        hotel_conf="5601396408",
        hotel_pin="4389",
        hotel_priceline="267-464-443-96",
        hotel_perks="Breakfast included,Free parking,Free WiFi,Full kitchen",
        hotel_cancel_deadline="Thu Apr 16 at 5:59 PM · 29% penalty after",
        car_company="Alamo",
        car_type="Full-size SUV AWD/4×4",
        car_models="Chevy Tahoe / Ford Expedition",
        car_location="SJC – 1659 Airport Blvd, San Jose, CA",
        car_pickup="Thu Apr 16 · 12:00 PM",
        car_dropoff="Mon Apr 20 · 12:00 PM",
        car_total="$420.31",
        car_conf="ALM-99284756",
        car_perks="Unlimited mileage,AWD/4×4",
        coach_notes="Skip heavy camp setup — RSCC has tables & chairs inside. Report time 7:00 AM for AM wave. Wear full uniform on Day 1.",
        parking_tips="Lot C (916 spaces, Gates 5 & 6) is largest and closest. Arrive before 6:45 AM for AM wave parking.",
        food_notes="Food court in Section B: pizza, burgers, chicken tenders. Pack lunch for Day 1 — lines are long opening morning.",
        weather_alert="",
    )
    db.session.add(booking)
    db.session.commit()
    logging.info("Seeded tournaments with Far Western booking")


with app.app_context():
    import models  # noqa: F401
    db.create_all()
    logging.info("Database tables created")
    if IS_DEV:
        seed_tournaments()

import routes  # noqa: F401  — registers all URL routes
