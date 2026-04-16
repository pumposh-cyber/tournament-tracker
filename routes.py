import os
import logging
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import current_user
from app import app, db
from models import Tournament, ChecklistItem, TripBooking, TournamentAnnouncement, UserPreferences
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

    # Use user's saved home address if set, otherwise fall back to default
    prefs = _get_prefs()
    display_home = prefs.home_address or HOME_LOCATION.get("address", HOME_LOCATION["city"])

    return render_template(
        "detail.html",
        tournament=tournament, now=now,
        distance=distance, drive_time=drive_time,
        weather=weather, day_count=day_count,
        home_city=display_home,
        home_address=display_home,
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
            import json, zipfile, io, base64
            from google import genai as _genai

            raw = request.form.get("whatsapp_text", "").strip()
            uploaded = request.files.get("upload_file")
            image_data = None  # (bytes, mime_type) for vision requests

            # ── Handle uploaded file ──
            if uploaded and uploaded.filename:
                fname = uploaded.filename.lower()
                content_bytes = uploaded.read()
                if fname.endswith(".zip"):
                    # WhatsApp export zip — extract the .txt chat file
                    try:
                        with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                            txt_files = [n for n in zf.namelist()
                                         if n.endswith(".txt") and not n.startswith("__MACOSX")]
                            if txt_files:
                                raw = zf.read(txt_files[0]).decode("utf-8", errors="replace")
                            else:
                                error = "No .txt file found inside the zip."
                    except Exception as e:
                        error = f"Could not open zip: {e}"
                elif fname.endswith(".txt"):
                    raw = content_bytes.decode("utf-8", errors="replace")
                elif any(fname.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                    mime = "image/jpeg" if fname.endswith((".jpg", ".jpeg")) else \
                           "image/png" if fname.endswith(".png") else \
                           "image/gif" if fname.endswith(".gif") else "image/webp"
                    image_data = (content_bytes, mime)
                else:
                    error = "Unsupported file type. Use .txt, .zip, or an image screenshot."

            if not raw and not image_data and not error:
                error = "Paste some WhatsApp text, or drop a file."

            if not error:
                try:
                    _gclient = _genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

                    # Pre-filter raw chat to last 7 days before sending to Gemini.
                    # WhatsApp format: [M/D/YY, H:MM:SS AM/PM] Name: message
                    # This ensures we never send old messages (Jan, Feb...) — only this week.
                    if raw:
                        import re as _re
                        cutoff = datetime.now() - timedelta(days=7)
                        filtered_lines = []
                        current_msg_lines = []
                        current_msg_in_window = False
                        _date_pat = _re.compile(r'^\[(\d{1,2}/\d{1,2}/\d{2,4}),')
                        for line in raw.splitlines():
                            m = _date_pat.match(line)
                            if m:
                                # Flush previous message
                                if current_msg_in_window and current_msg_lines:
                                    filtered_lines.extend(current_msg_lines)
                                current_msg_lines = [line]
                                try:
                                    msg_date = datetime.strptime(m.group(1), "%m/%d/%y")
                                except ValueError:
                                    try:
                                        msg_date = datetime.strptime(m.group(1), "%m/%d/%Y")
                                    except ValueError:
                                        msg_date = cutoff  # fallback: include
                                current_msg_in_window = msg_date >= cutoff
                            else:
                                current_msg_lines.append(line)
                        # Flush last message
                        if current_msg_in_window and current_msg_lines:
                            filtered_lines.extend(current_msg_lines)
                        chat_to_send = "\n".join(filtered_lines) if filtered_lines else ""
                    else:
                        chat_to_send = ""

                    EXTRACT_INSTRUCTIONS = """Extract ONLY the most important tournament-related messages from this WhatsApp group chat.

STRICT RULES:
1. ONLY include messages from coaches: "Andrew Nguyen" or "Coach T Rancho". Ignore ALL messages from anyone else — parents, players, unknown senders.
2. Only include messages DIRECTLY about the upcoming tournament — logistics, schedule, hotel, car, venue, court assignments, warm-up times, uniform, parking, bracket, pool assignments, weather warnings, facility info, directions.
3. IGNORE completely: practice absences, sick notices, practice schedules, casual chat, "thanks", reactions, one-word replies — even if from a coach.

For each qualifying message return:
- author: first name only
- date: date/time as it appears (e.g. "Apr 14, 8:12 AM")
- text: message cleaned up but not paraphrased — keep specifics
- pinned: true if critical logistics (report time, hotel, venue, schedule, uniform, parking, bracket)

If no qualifying messages exist, return an empty array [].
Return ONLY a JSON array. No markdown, no explanation. Example:
[{"author":"Coach Mike","date":"Apr 14, 7:00 AM","text":"Report time is 7:00 AM Friday at Gate 5. Wear full uniform.","pinned":true}]"""

                    if image_data:
                        from google.genai import types as _gtypes
                        img_part = _gtypes.Part.from_bytes(data=image_data[0], mime_type=image_data[1])
                        contents = [img_part, EXTRACT_INSTRUCTIONS + "\n\nExtract from the screenshot above."]
                    elif chat_to_send:
                        contents = EXTRACT_INSTRUCTIONS + f"\n\nWhatsApp chat (last 7 days only):\n{chat_to_send[:20000]}"
                    else:
                        contents = None

                    if contents is None:
                        extracted = []
                    else:
                        response = _gclient.models.generate_content(model="gemini-2.5-flash", contents=contents)
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
            from google import genai as _genai
            _gc = _genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
            raw = _gc.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()
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

    prefs = _get_prefs()
    pref_lines = []
    if prefs.home_address:     pref_lines.append(f"Home: {prefs.home_address}")
    if prefs.driving_notes:    pref_lines.append(f"Driving: {prefs.driving_notes}")
    if prefs.hotel_preference: pref_lines.append(f"Hotel pref: {prefs.hotel_preference}")
    if prefs.loyalty_programs: pref_lines.append(f"Loyalty: {prefs.loyalty_programs}")
    if prefs.packing_notes:    pref_lines.append(f"Packing: {prefs.packing_notes}")
    if prefs.scheduling_notes: pref_lines.append(f"Scheduling: {prefs.scheduling_notes}")
    if prefs.weather_notes:    pref_lines.append(f"Weather: {prefs.weather_notes}")
    if prefs.food_notes:       pref_lines.append(f"Food: {prefs.food_notes}")

    player_name = prefs.player_name or TEAM_INFO['player_name']
    player_num  = prefs.player_number or TEAM_INFO['player_number']
    player_pos  = prefs.player_position or TEAM_INFO['player_position']

    context_parts = [
        "You are VolleyAI, a helpful assistant for parents of youth volleyball players.",
        f"The team is {TEAM_INFO['name']}. Player: {player_name}, #{player_num}, {player_pos}.",
        "Be concise, warm, and practical. Use **bold** for key info. "
        "Keep responses under 200 words unless more detail is truly needed.",
    ]
    if pref_lines:
        context_parts.append("User preferences:\n" + "\n".join(pref_lines))

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
        from google import genai as _genai
        _gc = _genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        response = _gc.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return {"response": response.text.strip()}
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return {"response": "I'm having trouble connecting right now. Please try again in a moment."}, 200


def _get_prefs():
    """Return current user's UserPreferences, creating a default row if needed."""
    prefs = UserPreferences.query.filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.session.add(prefs)
        db.session.commit()
    return prefs


@app.route("/preferences", methods=["GET", "POST"])
@require_login
def user_preferences():
    prefs = _get_prefs()
    saved = False
    if request.method == "POST":
        prefs.home_address      = request.form.get("home_address", "").strip()
        prefs.driving_notes     = request.form.get("driving_notes", "").strip()
        prefs.car_preference    = request.form.get("car_preference", "").strip()
        prefs.hotel_preference  = request.form.get("hotel_preference", "").strip()
        prefs.loyalty_programs  = request.form.get("loyalty_programs", "").strip()
        prefs.packing_notes     = request.form.get("packing_notes", "").strip()
        prefs.scheduling_notes  = request.form.get("scheduling_notes", "").strip()
        prefs.weather_notes     = request.form.get("weather_notes", "").strip()
        prefs.food_notes        = request.form.get("food_notes", "").strip()
        prefs.player_name       = request.form.get("player_name", "").strip()
        prefs.player_number     = request.form.get("player_number", "").strip()
        prefs.player_position   = request.form.get("player_position", "").strip()
        db.session.commit()
        saved = True
    return render_template("preferences.html", prefs=prefs, saved=saved)


@app.route("/api/travel_notes/<int:tournament_id>")
@require_login
def api_travel_notes(tournament_id):
    import json as _json
    from utils import HOME_LOCATION
    tournament = Tournament.query.get_or_404(tournament_id)
    tab = request.args.get("tab", "road")  # "road" or "dest"

    prefs = _get_prefs()
    origin = prefs.home_address or HOME_LOCATION.get("address", HOME_LOCATION["city"])
    destination = f"{tournament.venue}, {tournament.city}" if tournament.venue else tournament.city
    city = tournament.city.split(",")[0].strip()

    # Build personalization context from user preferences
    pref_ctx = []
    if prefs.driving_notes:   pref_ctx.append(f"Driving preferences: {prefs.driving_notes}")
    if prefs.food_notes:      pref_ctx.append(f"Food preferences: {prefs.food_notes}")
    if prefs.weather_notes:   pref_ctx.append(f"Weather/gear notes: {prefs.weather_notes}")
    if prefs.car_preference:  pref_ctx.append(f"Car: {prefs.car_preference}")
    pref_str = ("\n" + "\n".join(pref_ctx)) if pref_ctx else ""

    if tab == "road":
        prompt = f"""You are a helpful travel assistant for a family driving from {origin} to {destination} for a youth volleyball tournament.{pref_str}

Suggest 4-6 practical road stops along the way. Include rest stops, gas stations at good points, food options, and any notable landmarks.
Factor in the user's preferences above when choosing food stops or rest points.
Focus on stops that work well for the {origin} → {destination} route specifically.

Return ONLY a JSON array. Each item:
{{"name": "Stop name", "location": "City, State or highway mile marker", "icon": "font-awesome-icon-name", "tip": "One sentence practical tip"}}

Good icon names: utensils, gas-pump, coffee, tree, store, camera, ice-cream, burger, circle-stop
No markdown, no explanation. JSON array only."""
    else:
        pref_ctx2 = []
        if prefs.hotel_preference: pref_ctx2.append(f"Hotel preference: {prefs.hotel_preference}")
        if prefs.food_notes:       pref_ctx2.append(f"Food preferences: {prefs.food_notes}")
        if prefs.packing_notes:    pref_ctx2.append(f"Packing habits: {prefs.packing_notes}")
        pref_str2 = ("\n" + "\n".join(pref_ctx2)) if pref_ctx2 else ""

        prompt = f"""You are a helpful travel assistant for a family visiting {city} for a youth volleyball tournament.{pref_str2}

Suggest 4-6 practical tips for their stay in {city}: nearby restaurants (family friendly), big box stores (Target/Walmart for forgotten gear), quick snacks near the venue, and one fun local thing to do if time allows.
Factor in the user's preferences above.

Return ONLY a JSON array. Each item:
{{"name": "Place or tip name", "location": "Area or address hint", "icon": "font-awesome-icon-name", "tip": "One sentence practical tip"}}

Good icon names: utensils, store, coffee, ice-cream, camera, map-pin, burger, shopping-cart
No markdown, no explanation. JSON array only."""

    try:
        from google import genai as _genai
        _gc = _genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        raw = _gc.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()
        raw = raw.lstrip("```json").lstrip("```").rstrip("```").strip()
        stops = _json.loads(raw)
        return {"stops": stops}
    except Exception as e:
        logging.error(f"travel_notes error: {e}")
        return {"stops": [], "error": str(e)}, 200


# ── Live Tournament Dashboard (TM2Sign integration) ──────────────────────────

# UVAC Far Westerns 2026 config
TM2_EVENT_ID = 2170
TM2_TEAM_ID = 266815

# Warm the cache immediately at startup so the first /live request is instant.
# The background thread then refreshes every 45 s without blocking any request.
from tm2_client import start_live_prefetch, get_cached_schedule, get_live_delta
start_live_prefetch(TM2_EVENT_ID, TM2_TEAM_ID)


@app.route("/live")
def live_dashboard():
    """Publicly accessible live match dashboard — no login required.
    Renders from the server-side cache; no TM2 API call on the request path."""
    data, version = get_cached_schedule()
    if data is None:
        data = {"rounds": [], "team": {}, "event": {},
                "current_match": None, "next_match": None,
                "error": "Data loading, please refresh in a moment."}
        version = 0

    # Pre-format match metadata for the JS delta renderer (no datetimes in JSON)
    def _time(dt):
        try: return dt.strftime("%-I:%M %p")
        except Exception: return "TBD"
    def _day(dt):
        try: return dt.strftime("%a")
        except Exception: return ""

    matches_meta = {}
    for rnd in data.get("rounds", []):
        for m in rnd["matches"]:
            matches_meta[m["id"]] = {
                "id": m["id"],
                "label": m.get("label", ""),
                "opponent": m["opponent"],
                "court": m["court"],
                "our_role": m["our_role"],
                "our_scores": m["our_scores"],
                "opp_scores": m["opp_scores"],
                "sets_won": m["sets_won"],
                "sets_lost": m["sets_lost"],
                "completed": m["completed"],
                "winner": m["winner"],
                "time_fmt": _time(m.get("start_time")),
                "day_fmt": _day(m.get("start_time")),
            }

    # Hotel quick-access: find the nearest active/upcoming tournament's booking
    hotel_info = None
    try:
        today = datetime.now().date()
        upcoming = (Tournament.query
                    .filter(Tournament.is_cancelled == False)
                    .order_by(Tournament.date_start.asc())
                    .all())
        active_t = next(
            (t for t in upcoming if t.date_end.date() >= today),
            None
        )
        if active_t and active_t.trip_booking:
            b = active_t.trip_booking
            hotel_info = {
                "tournament_id": active_t.id,
                "hotel_name": b.hotel_name or "",
                "hotel_address": b.hotel_address or "",
                "hotel_checkin": b.hotel_checkin or "",
                "hotel_checkout": b.hotel_checkout or "",
                "parking_tips": b.parking_tips or "",
                "food_notes": b.food_notes or "",
            }
    except Exception:
        pass  # DB not available (e.g. local dev without DB)

    return render_template("live_dashboard.html",
                           cache_version=version,
                           matches_meta=matches_meta,
                           hotel_info=hotel_info,
                           **data)


@app.route("/live/data")
def live_dashboard_data():
    """Compact delta JSON for the JS poller.
    Pass ?v=<version> — returns {"changed":false} (~30 bytes) when nothing has
    changed since that version, or a scores-only delta when data is new."""
    try:
        since = int(request.args.get("v", 0))
    except (ValueError, TypeError):
        since = 0
    return jsonify(get_live_delta(since))
