from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session
from flask_login import current_user
from app import app, db
from models import Tournament, ChecklistItem, TripBooking
from replit_auth import require_login, make_replit_blueprint

app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

TEAM_INFO = {
    "name": "UVAC Urban Volleyball 15 TS",
    "code": "G15UVBAC1NC",
    "age_group": "15s",
    "division": "Hyacinth",
    "rank": 127,
    "points": 163,
    "player_name": "Tiya Raina",
    "player_number": 13,
    "player_position": "Middle Blocker",
    "power_league_url": "https://docs.google.com/spreadsheets/d/1_Xog0a8Lqf6COYTfp0B8575teSsfQoy5/edit?gid=486749021#gid=486749021",
    "ncva_points_url": "https://ncva.com/girls-power-league-points/",
}

@app.context_processor
def inject_team_info():
    return dict(team_info=TEAM_INFO)

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route("/")
def index():
    if not current_user.is_authenticated:
        return render_template("landing.html")
    now = datetime.now()
    filter_type = request.args.get("filter", "upcoming")
    if filter_type == "upcoming":
        cutoff = datetime.combine(now.date() - timedelta(days=4), datetime.min.time())
        tournaments = Tournament.query.filter(Tournament.date_start >= cutoff, Tournament.is_cancelled == False).order_by(Tournament.date_start.asc()).all()
    elif filter_type == "past":
        tournaments = Tournament.query.filter(Tournament.date_start < now, Tournament.is_cancelled == False).order_by(Tournament.date_start.desc()).all()
    elif filter_type == "cancelled":
        tournaments = Tournament.query.filter(Tournament.is_cancelled == True).order_by(Tournament.date_start.asc()).all()
    else:
        tournaments = Tournament.query.order_by(Tournament.date_start.asc()).all()
    return render_template("index.html", tournaments=tournaments, filter_type=filter_type, now=now)

@app.route("/tournament/<int:tournament_id>")
@require_login
def tournament_detail(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    now = datetime.now()
    from utils import get_distance_from_home, estimate_drive_time, get_weather_forecast, weather_code_to_description, weather_code_to_icon, parse_day_count, HOME_LOCATION
    distance = get_distance_from_home(tournament.city)
    drive_time = estimate_drive_time(distance)
    weather = get_weather_forecast(tournament.city, tournament.date_start)
    day_count = parse_day_count(tournament.days, tournament.dates_display)
    booking = TripBooking.query.filter_by(tournament_id=tournament_id).first()
    return render_template("detail.html", tournament=tournament, now=now, distance=distance, drive_time=drive_time, weather=weather, day_count=day_count, home_city=HOME_LOCATION["city"], weather_desc=weather_code_to_description, weather_icon=weather_code_to_icon, booking=booking)

@app.route("/trip/<int:tournament_id>")
@require_login
def trip_dashboard(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    now = datetime.now()
    booking = TripBooking.query.filter_by(tournament_id=tournament_id).first()
    from utils import get_distance_from_home, estimate_drive_time, get_weather_forecast, weather_code_to_description, weather_code_to_icon, parse_day_count, HOME_LOCATION
    distance = get_distance_from_home(tournament.city)
    drive_time = estimate_drive_time(distance)
    weather = get_weather_forecast(tournament.city, tournament.date_start)
    day_count = parse_day_count(tournament.days, tournament.dates_display)
    timeline_days = []
    if tournament.date_start:
        travel_day = tournament.date_start - timedelta(days=1)
        timeline_days.append({"date": travel_day.strftime("%a, %b %-d"), "label": "Travel Day", "icon": "car", "color": "blue"})
        for i in range(day_count):
            d = tournament.date_start + timedelta(days=i)
            timeline_days.append({"date": d.strftime("%a, %b %-d"), "label": f"Tournament Day {i+1}", "icon": "volleyball", "color": "green"})
        return_day = tournament.date_start + timedelta(days=day_count)
        timeline_days.append({"date": return_day.strftime("%a, %b %-d"), "label": "Return Home", "icon": "house", "color": "gray"})
    return render_template("trip_dashboard.html", tournament=tournament, booking=booking, now=now, distance=distance, drive_time=drive_time, weather=weather, day_count=day_count, home_city=HOME_LOCATION["city"], weather_desc=weather_code_to_description, weather_icon=weather_code_to_icon, timeline_days=timeline_days)

@app.route("/trip/<int:tournament_id>/booking", methods=["GET", "POST"])
@require_login
def trip_booking(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    booking = TripBooking.query.filter_by(tournament_id=tournament_id).first()
    if request.method == "POST":
        if not booking:
            booking = TripBooking(tournament_id=tournament_id)
            db.session.add(booking)
        for field in ["hotel_name","hotel_address","hotel_phone","hotel_checkin","hotel_checkout","hotel_conf","hotel_pin","hotel_priceline","hotel_perks","hotel_cancel_deadline","car_company","car_type","car_models","car_pickup","car_dropoff","car_location","car_total","car_conf","car_perks","car_notes","coach_notes","parking_tips","food_notes","weather_alert"]:
            setattr(booking, field, request.form.get(field, "").strip())
        db.session.commit()
        flash("Trip booking details saved!", "success")
        return redirect(url_for("trip_dashboard", tournament_id=tournament_id))
    return render_template("trip_booking_form.html", tournament=tournament, booking=booking)

@app.route("/add", methods=["GET", "POST"])
@require_login
def add_tournament():
    if request.method == "POST":
        date_str = request.form.get("date", "")
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("add_tournament"))
        dates_display = request.form.get("dates_display", "").strip() or parsed_date.strftime("%b %d, %Y")
        tournament = Tournament(event=request.form.get("event","").strip(), dates_display=dates_display, date_start=parsed_date, days=request.form.get("days","").strip(), city=request.form.get("city","").strip(), venue=request.form.get("venue","").strip(), hotel_recommendation=request.form.get("hotel_recommendation","").strip(), hotel_link_notes=request.form.get("hotel_link_notes","").strip(), car_rental_recommendation=request.form.get("car_rental_recommendation","").strip(), hotel_booking_status=request.form.get("hotel_booking_status","").strip(), car_booking_status=request.form.get("car_booking_status","").strip(), notes=request.form.get("notes","").strip())
        db.session.add(tournament)
        db.session.commit()
        flash("Tournament added successfully!", "success")
        return redirect(url_for("index"))
    return render_template("add.html")

@app.route("/edit/<int:tournament_id>", methods=["GET", "POST"])
@require_login
def edit_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    if request.method == "POST":
        date_str = request.form.get("date", "")
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(url_for("edit_tournament", tournament_id=tournament_id))
        dates_display = request.form.get("dates_display","").strip() or parsed_date.strftime("%b %d, %Y")
        tournament.event = request.form.get("event","").strip()
        tournament.dates_display = dates_display
        tournament.date_start = parsed_date
        tournament.days = request.form.get("days","").strip()
        tournament.city = request.form.get("city","").strip()
        tournament.venue = request.form.get("venue","").strip()
        tournament.hotel_recommendation = request.form.get("hotel_recommendation","").strip()
        tournament.hotel_link_notes = request.form.get("hotel_link_notes","").strip()
        tournament.car_rental_recommendation = request.form.get("car_rental_recommendation","").strip()
        tournament.hotel_booking_status = request.form.get("hotel_booking_status","").strip()
        tournament.car_booking_status = request.form.get("car_booking_status","").strip()
        tournament.notes = request.form.get("notes","").strip()
        db.session.commit()
        flash("Tournament updated successfully!", "success")
        return redirect(url_for("tournament_detail", tournament_id=tournament.id))
    return render_template("edit.html", tournament=tournament)

@app.route("/cancel/<int:tournament_id>", methods=["POST"])
@require_login
def cancel_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    tournament.is_cancelled = True
    tournament.cancellation_reason = request.form.get("cancellation_reason","NCVA schedule change").strip()
    db.session.commit()
    flash(f"'{tournament.event}' has been marked as cancelled.", "success")
    return redirect(url_for("tournament_detail", tournament_id=tournament.id))

@app.route("/restore/<int:tournament_id>", methods=["POST"])
@require_login
def restore_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    tournament.is_cancelled = False
    tournament.cancellation_reason = ""
    db.session.commit()
    flash(f"'{tournament.event}' has been restored.", "success")
    return redirect(url_for("tournament_detail", tournament_id=tournament.id))

@app.route("/delete/<int:tournament_id>", methods=["POST"])
@require_login
def delete_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    db.session.delete(tournament)
    db.session.commit()
    flash("Tournament deleted.", "success")
    return redirect(url_for("index"))

DEFAULT_CHECKLIST = {
    "Essential Volleyball Gear": ["Jersey(s) and extra uniform shirt","Shorts / spandex (at least 2 pairs)","Knee pads","Volleyball shoes (game pair)","Backup athletic shoes or slides","Team socks (multiple pairs)","Warm-up jacket or hoodie","Hair ties / headband if needed","Athletic tape, pre-wrap, ankle brace (if used)"],
    "Hydration and Nutrition": ["Large water bottle (filled)","Electrolyte packets or sports drink","Easy carbs: bananas, granola bars, bagels","Protein snacks: nuts, protein bars, yogurt","Quick sugar for between sets (fruit snacks, dates)","Packed lunch or plan for nearby food","Small cooler with ice pack"],
    "Recovery and Injury Prevention": ["Foam roller or massage ball","Stretch band / resistance band","Pain relief cream or spray","Ice packs or instant cold packs","Ibuprofen or basic first-aid meds","Bandaids / blister care","Extra socks to change between matches"],
    "Travel and Comfort Items": ["Backpack or volleyball bag","Phone + charger + portable battery","Tournament schedule screenshot or printout","Cash / card for food and parking","Blanket or small chair for seating","Change of clothes for after matches","Toiletries for hotel","Sleepwear"],
    "Parent / Family Logistics": ["Directions to venue and parking info","Hotel confirmation","Emergency contacts","Snacks and water for siblings","Entertainment for downtime (book, tablet, headphones)"],
}
CATEGORY_ICONS = {"Essential Volleyball Gear":"fa-volleyball","Hydration and Nutrition":"fa-bottle-water","Recovery and Injury Prevention":"fa-kit-medical","Travel and Comfort Items":"fa-suitcase-rolling","Parent / Family Logistics":"fa-users"}

def init_checklist_for_tournament(tournament_id):
    order = 0
    for category, items in DEFAULT_CHECKLIST.items():
        for item_text in items:
            db.session.add(ChecklistItem(tournament_id=tournament_id, category=category, item_text=item_text, is_checked=False, sort_order=order))
            order += 1
    db.session.commit()

@app.route("/checklist/<int:tournament_id>")
@require_login
def tournament_checklist(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    items = ChecklistItem.query.filter_by(tournament_id=tournament_id).order_by(ChecklistItem.sort_order).all()
    if not items:
        init_checklist_for_tournament(tournament_id)
        items = ChecklistItem.query.filter_by(tournament_id=tournament_id).order_by(ChecklistItem.sort_order).all()
    categories = {}
    for item in items:
        categories.setdefault(item.category, []).append(item)
    total = len(items)
    checked = sum(1 for i in items if i.is_checked)
    return render_template("checklist.html", tournament=tournament, categories=categories, category_icons=CATEGORY_ICONS, total=total, checked=checked)

@app.route("/checklist/<int:tournament_id>/toggle/<int:item_id>", methods=["POST"])
@require_login
def toggle_checklist_item(tournament_id, item_id):
    item = ChecklistItem.query.get_or_404(item_id)
    item.is_checked = not item.is_checked
    db.session.commit()
    return redirect(url_for("tournament_checklist", tournament_id=tournament_id))

@app.route("/checklist/<int:tournament_id>/reset", methods=["POST"])
@require_login
def reset_checklist(tournament_id):
    ChecklistItem.query.filter_by(tournament_id=tournament_id).delete()
    db.session.commit()
    init_checklist_for_tournament(tournament_id)
    flash("Checklist has been reset.", "success")
    return redirect(url_for("tournament_checklist", tournament_id=tournament_id))
