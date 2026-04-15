import os
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session
from flask_login import current_user
from app import app, db
from models import Tournament, ChecklistItem, TripBooking, TournamentAnnouncement
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
        tournaments = [t for t in Tournament.query.filter(Tournament.is_cancelled == False).order_by(Tournament.date_start.asc()).all() if t.date_end >= now]
    elif filter_type == "past":
        tournaments = [t for t in Tournament.query.filter(Tournament.is_cancelled == False).order_by(Tournament.date_start.desc()).all() if t.date_end < now]
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

    # Build timeline
    timeline_days = []
    if tournament.date_start:
        travel_day = tournament.date_start - timedelta(days=1)
        timeline_days.append({"date": travel_day.strftime("%a, %b %-d"), "label": "Travel Day", "icon": "car", "color": "blue"})
        for i in range(day_count):
            d = tournament.date_start + timedelta(days=i)
            label = "Day 1" if day_count == 1 else f"Day {i+1}"
            timeline_days.append({"date": d.strftime("%a, %b %-d"), "label": label, "icon": "volleyball", "color": "green"})
        return_day = tournament.date_start + timedelta(days=day_count)
        timeline_days.append({"date": return_day.strftime("%a, %b %-d"), "label": "Return Home", "icon": "house", "color": "gray"})

    # Days until tournament and travel day detection
    days_until = (tournament.date_start - now).days if tournament.date_start else None
    travel_date = tournament.date_start - timedelta(days=1) if tournament.date_start else None
    is_travel_day = (travel_date and travel_date.date() == now.date())

    # Navigation URLs
    venue_query = f"{tournament.venue}, {tournament.city}".replace(" ", "+")
    home_query = f"{HOME_LOCATION['latitude']},{HOME_LOCATION['longitude']}"
    gmaps_url = f"https://www.google.com/maps/dir/{home_query}/{venue_query}"
    waze_url = f"https://waze.com/ul?q={venue_query}&navigate=yes"

    checklist_items = ChecklistItem.query.filter_by(tournament_id=tournament_id).all()
    auto_open_chat = not booking and not checklist_items

    return render_template(
        "detail.html",
        tournament=tournament, now=now,
        distance=distance, drive_time=drive_time,
        weather=weather, day_count=day_count,
        home_city=HOME_LOCATION["city"],
        home_address=HOME_LOCATION.get("address", HOME_LOCATION["city"]),
        weather_desc=weather_code_to_description,
        weather_icon=weather_code_to_icon,
        booking=booking,
        timeline_days=timeline_days,
        days_until=days_until,
        is_travel_day=is_travel_day,
        gmaps_url=gmaps_url,
        waze_url=waze_url,
        auto_open_chat=auto_open_chat,
    )

@app.route("/trip/<int:tournament_id>")
@require_login
def trip_dashboard(tournament_id):
    return redirect(url_for("tournament_detail", tournament_id=tournament_id))

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
        return redirect(url_for("tournament_detail", tournament_id=tournament_id))
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
    return render_template("add.html", auto_open_chat=True, chat_mode="add_tournament")

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

# ── Announcements ────────────────────────────────────────────────

@app.route("/tournament/<int:tournament_id>/announcements/import", methods=["GET", "POST"])
@require_login
def import_announcements(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    extracted = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "parse":
            raw = request.form.get("whatsapp_text", "").strip()
            if not raw:
                error = "Paste some WhatsApp text first."
            else:
                try:
                    import json
                    import google.generativeai as genai
                    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    prompt = f"""You are parsing a WhatsApp group chat export for a youth volleyball tournament parent group.

Extract the most important messages — coach instructions, logistics, schedule info, hotel/car reminders, and any key updates.
Ignore casual chatter, emoji reactions, "thanks", "👍" replies, and off-topic messages.

For each important message return:
- author: person's name (first name only)
- date: date/time string as it appears in the chat (e.g. "Apr 14, 8:12 AM")
- text: the message, cleaned up but not paraphrased — keep specifics
- pinned: true if this is critical logistics (report time, hotel, venue, schedule, uniform, parking). false otherwise.

Return ONLY a JSON array. No explanation, no markdown fences. Example:
[{{"author":"Coach Mike","date":"Apr 14, 7:00 AM","text":"Report time is 7:00 AM Friday at Gate 5. Wear full uniform.","pinned":true}}]

WhatsApp chat:
{raw[:6000]}"""

                    response = model.generate_content(prompt)
                    raw_json = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                    extracted = json.loads(raw_json)
                except Exception as e:
                    error = f"Parse error: {str(e)}"

        elif action == "save":
            import json
            items_json = request.form.get("items_json", "[]")
            try:
                items = json.loads(items_json)
                saved = 0
                for item in items:
                    if not item.get("text", "").strip():
                        continue
                    ann = TournamentAnnouncement(
                        tournament_id=tournament_id,
                        author=item.get("author", ""),
                        text=item.get("text", ""),
                        is_pinned=bool(item.get("pinned", False)),
                        source_date=item.get("date", ""),
                    )
                    db.session.add(ann)
                    saved += 1
                db.session.commit()
                flash(f"{saved} announcement{'s' if saved != 1 else ''} saved.", "success")
                return redirect(url_for("tournament_detail", tournament_id=tournament_id))
            except Exception as e:
                error = f"Save error: {str(e)}"

    existing = TournamentAnnouncement.query.filter_by(tournament_id=tournament_id).order_by(TournamentAnnouncement.created_at.desc()).all()
    return render_template("import_announcements.html", tournament=tournament, extracted=extracted, error=error, existing=existing)


@app.route("/tournament/<int:tournament_id>/announcements/<int:ann_id>/delete", methods=["POST"])
@require_login
def delete_announcement(tournament_id, ann_id):
    ann = TournamentAnnouncement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    return redirect(url_for("import_announcements", tournament_id=tournament_id))


@app.route("/tournament/<int:tournament_id>/announcements/<int:ann_id>/pin", methods=["POST"])
@require_login
def toggle_pin_announcement(tournament_id, ann_id):
    ann = TournamentAnnouncement.query.get_or_404(ann_id)
    ann.is_pinned = not ann.is_pinned
    db.session.commit()
    return redirect(url_for("import_announcements", tournament_id=tournament_id))


@app.route("/api/chat", methods=["POST"])
@require_login
def api_chat():
    import json as _json
    import google.generativeai as genai
    data = request.get_json(silent=True) or {}
    message       = (data.get("message") or "").strip()
    history       = data.get("history") or []
    tournament_id = data.get("tournament_id")
    mode          = data.get("mode") or ""

    if not message:
        return {"error": "No message"}, 400

    # ── Add Tournament mode ──
    if mode == "add_tournament":
        context_parts = [
            "You are VolleyAI helping a parent add a new volleyball tournament entry.",
            f"Team: {TEAM_INFO['name']}. Player: {TEAM_INFO['player_name']}, #{TEAM_INFO['player_number']}.",
            "Gather: event name, start date (ask for exact date), dates display (e.g. 'May 9-10, 2026'), "
            "day(s) (e.g. 'Sat-Sun'), city, venue. Be friendly and conversational.",
            "When you have at minimum event name + start date + city, append on its own line at the end of your reply:",
            'FILL:{"event":"...","date":"YYYY-MM-DD","dates_display":"...","days":"...","city":"...","venue":"..."}',
            "Only include FILL: once you have confirmed the details with the user.",
            "If the user pastes an announcement, extract all details from it.",
            "Keep replies short and warm. Use **bold** for key info.",
        ]
        system_ctx = "\n".join(context_parts)
        prompt = system_ctx + "\n\n"
        for h in history[-10:]:
            role = "Parent" if h.get("role") == "user" else "VolleyAI"
            prompt += f"{role}: {h.get('text', '')}\n"
        prompt += f"Parent: {message}\nVolleyAI:"
        try:
            import json as _json
            import google.generativeai as genai
            genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
            model = genai.GenerativeModel("gemini-2.5-flash")
            raw = model.generate_content(prompt).text.strip()
            fill_form = None
            display_text = raw
            if "FILL:" in raw:
                parts = raw.split("FILL:", 1)
                display_text = parts[0].strip()
                try:
                    fill_form = _json.loads(parts[1].strip().split("\n")[0])
                    display_text += "\n\nI've filled in the form below — scroll down to review and click **Add Tournament**!"
                except Exception:
                    pass
            return {"response": display_text, "fill_form": fill_form}
        except Exception as e:
            logging.error(f"Chat error (add mode): {e}")
            return {"response": "I'm having trouble connecting right now. Please try again."}, 200

    context_parts = [
        "You are VolleyAI, a helpful assistant for parents of youth volleyball players.",
        f"The team is {TEAM_INFO['name']}. Player: {TEAM_INFO['player_name']}, "
        f"#{TEAM_INFO['player_number']}, {TEAM_INFO['player_position']}.",
        "Be concise, warm, and practical. Use **bold** for key info. "
        "Keep responses under 200 words unless more detail is truly needed.",
    ]

    if tournament_id:
        t = Tournament.query.get(tournament_id)
        if t:
            context_parts.append(f"\nTournament: {t.event}")
            context_parts.append(f"Dates: {t.dates_display} | City: {t.city} | Venue: {t.venue}")
            if t.notes:
                context_parts.append(f"Notes: {t.notes}")
            booking = TripBooking.query.filter_by(tournament_id=t.id).first()
            if booking:
                context_parts += [
                    f"\nHotel: {booking.hotel_name} — {booking.hotel_address}",
                    f"Check-in: {booking.hotel_checkin} | Check-out: {booking.hotel_checkout}",
                    f"Conf: {booking.hotel_conf} | PIN: {booking.hotel_pin} | Priceline: {booking.hotel_priceline}",
                    f"Perks: {booking.hotel_perks}" if booking.hotel_perks else "",
                    f"Cancel deadline: {booking.hotel_cancel_deadline}" if booking.hotel_cancel_deadline else "",
                    f"\nCar: {booking.car_company} {booking.car_type} ({booking.car_models})",
                    f"Pick-up: {booking.car_pickup} at {booking.car_location}",
                    f"Drop-off: {booking.car_dropoff} | Total: {booking.car_total} | Conf: {booking.car_conf}",
                    f"Coach notes: {booking.coach_notes}" if booking.coach_notes else "",
                    f"Parking: {booking.parking_tips}" if booking.parking_tips else "",
                    f"Food: {booking.food_notes}" if booking.food_notes else "",
                ]
            pinned = TournamentAnnouncement.query.filter_by(tournament_id=t.id, is_pinned=True).all()
            recent = TournamentAnnouncement.query.filter_by(tournament_id=t.id)\
                .order_by(TournamentAnnouncement.created_at.desc()).limit(5).all()
            all_anns = list({a.id: a for a in pinned + recent}.values())[:8]
            if all_anns:
                ann_lines = "\n".join(f"- [{a.author}] {a.text}" for a in all_anns)
                context_parts.append(f"\nRecent announcements:\n{ann_lines}")

    system_ctx = "\n".join(p for p in context_parts if p)
    prompt = system_ctx + "\n\n"
    for h in history[-10:]:
        role = "Parent" if h.get("role") == "user" else "VolleyAI"
        prompt += f"{role}: {h.get('text', '')}\n"
    prompt += f"Parent: {message}\nVolleyAI:"

    try:
        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return {"response": response.text.strip()}
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return {"response": "I'm having trouble connecting right now. Please try again in a moment."}, 200
