import math
import json
import requests
from datetime import datetime, timedelta

HOME_LOCATION = {
    "city": "Milpitas, CA",
    "address": "Milpitas, CA 95035",
    "latitude": 37.4323,
    "longitude": -121.8996,
}

CITY_COORDINATES = {
    "san mateo": (37.5585, -122.2711),
    "sacramento": (38.5816, -121.4944),
    "roseville": (38.7521, -121.2880),
    "roseville / sacramento": (38.7521, -121.2880),
    "bay area": (37.5585, -122.2711),
    "bay area / sacramento": (37.8044, -122.2712),
    "reno": (39.5296, -119.8138),
    "reno, nv": (39.5296, -119.8138),
    "san francisco": (37.7749, -122.4194),
    "san jose": (37.3382, -121.8863),
    "oakland": (37.8044, -122.2712),
    "fresno": (36.7378, -119.7871),
    "los angeles": (34.0522, -118.2437),
    "san diego": (32.7157, -117.1611),
    "phoenix": (33.4484, -112.0740),
    "las vegas": (36.1699, -115.1398),
    "denver": (39.7392, -104.9903),
    "seattle": (47.6062, -122.3321),
    "portland": (45.5152, -122.6784),
    "dallas": (32.7767, -96.7970),
    "austin": (30.2672, -97.7431),
    "atlanta": (33.7490, -84.3880),
    "miami": (25.7617, -80.1918),
    "chicago": (41.8781, -87.6298),
    "tba": None,
}


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_coordinates(city_name):
    if not city_name:
        return None
    city_lower = city_name.lower().strip()
    if city_lower in CITY_COORDINATES:
        return CITY_COORDINATES[city_lower]
    for key, coords in CITY_COORDINATES.items():
        if key in city_lower or city_lower in key:
            return coords
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results"):
                r = data["results"][0]
                return (r["latitude"], r["longitude"])
    except Exception:
        pass
    return None


def get_distance_from_home(city_name):
    coords = get_coordinates(city_name)
    if not coords:
        return None
    distance = haversine_miles(
        HOME_LOCATION["latitude"], HOME_LOCATION["longitude"],
        coords[0], coords[1],
    )
    return round(distance)


def estimate_drive_time(miles):
    if not miles:
        return None
    hours = miles / 55
    if hours < 1:
        return f"{round(hours * 60)} min drive"
    return f"{hours:.1f} hr drive"


def get_weather_forecast(city_name, date_start):
    coords = get_coordinates(city_name)
    if not coords:
        return None

    now = datetime.now()
    days_until = (date_start - now).days

    if days_until > 15:
        return {"type": "historical_avg", "message": "Weather forecast available closer to event date"}

    if days_until < -1:
        return {"type": "past", "message": "Event has passed"}

    try:
        params = {
            "latitude": coords[0],
            "longitude": coords[1],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "America/Los_Angeles",
            "temperature_unit": "fahrenheit",
        }

        if days_until >= 0:
            params["forecast_days"] = min(days_until + 3, 16)
            url = "https://api.open-meteo.com/v1/forecast"
        else:
            params["start_date"] = date_start.strftime("%Y-%m-%d")
            params["end_date"] = now.strftime("%Y-%m-%d")
            url = "https://api.open-meteo.com/v1/forecast"

        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()
        daily = data.get("daily", {})
        times = daily.get("time", [])
        target_date = date_start.strftime("%Y-%m-%d")

        forecast_days = []
        for i, t in enumerate(times):
            if t >= target_date:
                forecast_days.append({
                    "date": t,
                    "high": daily["temperature_2m_max"][i],
                    "low": daily["temperature_2m_min"][i],
                    "precip_chance": daily["precipitation_probability_max"][i],
                    "weather_code": daily["weather_code"][i],
                })
                if len(forecast_days) >= 3:
                    break

        if not forecast_days:
            return None

        return {
            "type": "forecast",
            "days": forecast_days,
        }

    except Exception:
        return None


def weather_code_to_description(code):
    if code is None:
        return "Unknown"
    descriptions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }
    return descriptions.get(code, "Unknown")


def weather_code_to_icon(code):
    if code is None:
        return "?"
    if code <= 1:
        return "sun"
    if code <= 3:
        return "cloud-sun"
    if code in (45, 48):
        return "smog"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "cloud-rain"
    if code in (71, 73, 75):
        return "snowflake"
    if code >= 95:
        return "bolt"
    return "cloud"


def parse_day_count(days_str, dates_display):
    if not days_str and not dates_display:
        return 1

    if days_str:
        import re
        m = re.search(r"(\d+)\s*day", days_str.lower())
        if m:
            return int(m.group(1))
        if "sun" in days_str.lower() and ("sat" in days_str.lower() or "fri" in days_str.lower()):
            parts = days_str.lower().split("–") if "–" in days_str else days_str.lower().split("-")
            if len(parts) == 2:
                day_map = {"fri": 5, "sat": 6, "sun": 7, "mon": 8}
                start = None
                end = None
                for key, val in day_map.items():
                    if key in parts[0]:
                        start = val
                    if key in parts[1]:
                        end = val
                if start and end:
                    return end - start + 1

    if dates_display:
        import re
        dates_clean = dates_display.replace("\u2013", "-").replace("\u2014", "-")
        m = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})", dates_clean)
        if m:
            return int(m.group(2)) - int(m.group(1)) + 1

    return 1
