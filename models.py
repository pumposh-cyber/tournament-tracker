from datetime import datetime
from app import db
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)
    __table_args__ = (UniqueConstraint('user_id', 'browser_session_key', 'provider', name='uq_user_browser_session_key_provider'),)


class Tournament(db.Model):
    __tablename__ = "tournaments"
    id = db.Column(db.Integer, primary_key=True)
    event = db.Column(db.String(200), nullable=False)
    dates_display = db.Column(db.String(100), nullable=False)
    date_start = db.Column(db.DateTime, nullable=False)
    days = db.Column(db.String(100), default="")
    city = db.Column(db.String(200), nullable=False)
    venue = db.Column(db.String(300), nullable=False)
    hotel_recommendation = db.Column(db.String(300), default="")
    hotel_link_notes = db.Column(db.Text, default="")
    car_rental_recommendation = db.Column(db.String(300), default="")
    hotel_booking_status = db.Column(db.String(100), default="")
    car_booking_status = db.Column(db.String(100), default="")
    notes = db.Column(db.Text, default="")
    is_cancelled = db.Column(db.Boolean, default=False)
    cancellation_reason = db.Column(db.Text, default="")

    @property
    def is_upcoming(self):
        return self.date_start >= datetime.now()

    @property
    def formatted_date(self):
        return self.dates_display

    def __repr__(self):
        return f"<Tournament {self.event} - {self.dates_display}>"


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    item_text = db.Column(db.String(300), nullable=False)
    is_checked = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    tournament = db.relationship("Tournament", backref=db.backref("checklist_items", lazy=True, cascade="all, delete-orphan"))


class TripBooking(db.Model):
    """Stores detailed trip booking info (hotel + car) for each tournament."""
    __tablename__ = "trip_bookings"
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Hotel
    hotel_name = db.Column(db.String(300), default="")
    hotel_address = db.Column(db.String(300), default="")
    hotel_phone = db.Column(db.String(50), default="")
    hotel_checkin = db.Column(db.String(100), default="")
    hotel_checkout = db.Column(db.String(100), default="")
    hotel_conf = db.Column(db.String(100), default="")
    hotel_pin = db.Column(db.String(50), default="")
    hotel_priceline = db.Column(db.String(100), default="")
    hotel_perks = db.Column(db.Text, default="")
    hotel_cancel_deadline = db.Column(db.String(200), default="")

    # Car
    car_company = db.Column(db.String(100), default="")
    car_type = db.Column(db.String(200), default="")
    car_models = db.Column(db.String(300), default="")
    car_pickup = db.Column(db.String(100), default="")
    car_dropoff = db.Column(db.String(100), default="")
    car_location = db.Column(db.String(300), default="")
    car_total = db.Column(db.String(50), default="")
    car_conf = db.Column(db.String(100), default="")
    car_perks = db.Column(db.Text, default="")
    car_notes = db.Column(db.Text, default="")

    # Coach / venue tips
    coach_notes = db.Column(db.Text, default="")
    parking_tips = db.Column(db.Text, default="")
    food_notes = db.Column(db.Text, default="")
    weather_alert = db.Column(db.Text, default="")

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    tournament = db.relationship("Tournament", backref=db.backref("trip_booking", uselist=False, cascade="all, delete-orphan"))
