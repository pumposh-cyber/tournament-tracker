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
    updated_at = db.Column(db.DateTime,
                           default=datetime.now,
                           onupdate=datetime.now)


class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)

    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)


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

    def __repr__(self):
        return f"<ChecklistItem {self.item_text} - {'✓' if self.is_checked else '○'}>"
