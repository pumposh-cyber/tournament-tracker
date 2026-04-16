"""
TM2Sign public API client for fetching team schedules and match results.
All endpoints use the public /api/public/ prefix — no auth required.
"""

import time
import logging
import threading
import hashlib
import json as _json
from datetime import datetime, timezone
from typing import Optional
import requests

log = logging.getLogger(__name__)

BASE_URL = "https://tm2sign.com/api/public"

# ── Simple in-process TTL cache ──────────────────────────────────────────────
_cache: dict = {}
CACHE_TTL = 90  # seconds


def _get(path: str, params: Optional[dict] = None):
    cache_key = (path, tuple(sorted((params or {}).items())))
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["ts"] < CACHE_TTL:
        return cached["data"]

    url = f"{BASE_URL}/{path}"
    try:
        resp = requests.get(url, params=params, timeout=10,
                            headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("TM2 fetch failed %s: %s", url, exc)
        return cached["data"] if cached else []

    _cache[cache_key] = {"ts": time.time(), "data": data}
    return data


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ts_to_local(ts, tz_str: str = "America/Los_Angeles"):
    """Convert a Unix timestamp to a timezone-aware datetime."""
    if not ts:
        return None
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = timezone.utc
    return datetime.fromtimestamp(ts, tz=tz)


def _fmt_time(dt) -> str:
    if not dt:
        return "TBD"
    return dt.strftime("%-I:%M %p")


def _fmt_day(dt) -> str:
    if not dt:
        return ""
    return dt.strftime("%a %b %-d")


# ── Public API ───────────────────────────────────────────────────────────────

def get_event(event_id: int) -> dict:
    return _get(f"events/{event_id}") or {}


def get_team(team_id: int) -> dict:
    return _get(f"scheduler-teams/{team_id}") or {}


def get_rounds(event_division_id: int):
    return _get("scheduler-rounds", {"filter[event_division_id]": event_division_id}) or []


def get_courts(event_id: int):
    """Return {court_id: court_dict}."""
    courts = _get("scheduler-courts", {"filter[event_id]": event_id}) or []
    return {c["id"]: c for c in courts}


def _get_pool_bracket_id_for_team(event_id: int, round_id: int,
                                   team_id: int):
    """Find which pool bracket the team is seeded in for a given round."""
    seeds = _get("scheduler-pool-bracket-seeds",
                 {"filter[event_id]": event_id,
                  "filter[scheduler_round_id]": round_id})
    if not isinstance(seeds, list):
        return None
    for seed in seeds:
        if seed.get("scheduler_team_id") == team_id:
            return seed.get("scheduler_pool_bracket_id")
    return None


def _get_pool_seed_for_team(event_id: int, round_id: int,
                             team_id: int):
    seeds = _get("scheduler-pool-bracket-seeds",
                 {"filter[event_id]": event_id,
                  "filter[scheduler_round_id]": round_id})
    if not isinstance(seeds, list):
        return None
    for seed in seeds:
        if seed.get("scheduler_team_id") == team_id:
            return seed
    return None


def _get_matches_for_bracket(event_id: int, pool_bracket_id: int):
    return _get("scheduler-matches",
                {"filter[event_id]": event_id,
                 "filter[scheduler_pool_bracket_id]": pool_bracket_id}) or []


def _resolve_team_names(team_ids):
    """Bulk-resolve team names. Falls back to team ID if lookup fails."""
    names = {}
    for tid in team_ids:
        if tid:
            t = _get(f"scheduler-teams/{tid}")
            if isinstance(t, dict):
                names[tid] = t.get("name", f"Team {tid}")
    return names


# ── Main schedule builder ─────────────────────────────────────────────────────

def get_team_schedule(event_id: int, team_id: int) -> dict:
    """
    Build a full structured schedule for the given team in the given event.
    Returns:
      {
        "event": {...},
        "team": {...},
        "rounds": [
          {
            "id": ...,
            "name": "Round 1",
            "pool_bracket_label": "Pool 14",
            "role": "playing" | "work_team" | None,
            "matches": [
              {
                "label": "15NDR1G1P14M1",
                "start_time": datetime,
                "end_time": datetime,
                "court": "RSCC 47",
                "court_location": "Reno Sparks Convention Center",
                "our_role": "playing" | "work_team",
                "opponent": "LAVA West 15 Premier CA",  # when playing
                "our_score": [25, 25, None],
                "opp_score": [15, 20, None],
                "sets_won": 2,
                "sets_lost": 0,
                "completed": False,
                "winner": None,  # "us" | "them" | None
              }
            ],
            "standings": {...}  # pool seed info
          }
        ],
        "now": datetime,
        "current_match": {...} | None,
        "next_match": {...} | None,
      }
    """
    now = datetime.now(tz=timezone.utc)

    event = get_event(event_id)
    team = get_team(team_id)
    courts = get_courts(event_id)
    rounds_raw = get_rounds(team.get("event_division_id", 0))

    rounds_out = []

    for rnd in sorted(rounds_raw, key=lambda r: r.get("round_order", 0)):
        round_id = rnd["id"]

        # Find this team's pool bracket for this round
        seed_info = _get_pool_seed_for_team(event_id, round_id, team_id)
        pool_bracket_id = seed_info.get("scheduler_pool_bracket_id") if seed_info else None

        if not pool_bracket_id:
            # Team not yet seeded into this round (happens before round 1 ends)
            rounds_out.append({
                "id": round_id,
                "name": rnd["name"],
                "abbreviation": rnd.get("abbreviation", ""),
                "pool_bracket_id": None,
                "pool_bracket_label": "TBD",
                "matches": [],
                "seed_info": None,
                "status": "pending",
            })
            continue

        matches_raw = _get_matches_for_bracket(event_id, pool_bracket_id)

        # Collect all team IDs we need to resolve
        team_ids_needed = set()
        for m in matches_raw:
            for field in ["position_one_scheduler_team_id",
                          "position_two_scheduler_team_id",
                          "work_team_scheduler_team_id"]:
                v = m.get(field)
                if v and v != team_id:
                    team_ids_needed.add(v)

        team_names = _resolve_team_names(team_ids_needed)
        team_names[team_id] = team.get("name", f"Team {team_id}")

        matches_out = []
        for m in sorted(matches_raw, key=lambda x: x.get("match_order", 0)):
            p1 = m.get("position_one_scheduler_team_id")
            p2 = m.get("position_two_scheduler_team_id")
            work = m.get("work_team_scheduler_team_id")

            start_dt = _ts_to_local(m.get("start_time"), m.get("timezone", "UTC"))
            end_dt = _ts_to_local(m.get("end_time"), m.get("timezone", "UTC"))

            court = courts.get(m.get("scheduler_court_id"), {})

            # Determine our role in this match
            if p1 == team_id or p2 == team_id:
                our_role = "playing"
                if p1 == team_id:
                    our_pos, opp_id = "position_one", p2
                else:
                    our_pos, opp_id = "position_two", p1
                opponent = team_names.get(opp_id, f"Team {opp_id}")

                our_prefix = our_pos
                opp_prefix = "position_one" if our_pos == "position_two" else "position_two"

                our_scores = [m.get(f"{our_prefix}_score_{s}") for s in
                              ["one", "two", "three", "four", "five"]]
                opp_scores = [m.get(f"{opp_prefix}_score_{s}") for s in
                              ["one", "two", "three", "four", "five"]]

                our_sets_won = m.get(f"{our_prefix}_match_set_wins") or 0
                our_sets_lost = m.get(f"{our_prefix}_match_set_losses") or 0

                winning_tid = m.get("winning_scheduler_team_id")
                if winning_tid == team_id:
                    winner = "us"
                elif winning_tid and winning_tid != team_id:
                    winner = "them"
                else:
                    winner = None

            elif work == team_id:
                our_role = "work_team"
                p1_name = team_names.get(p1, f"Team {p1}")
                p2_name = team_names.get(p2, f"Team {p2}")
                opponent = f"{p1_name} vs {p2_name}"
                our_scores = []
                opp_scores = []
                our_sets_won = 0
                our_sets_lost = 0
                winner = None
            else:
                continue  # not involved

            completed = bool(m.get("completed_time"))

            # Trim trailing None scores
            def trim_scores(lst):
                while lst and lst[-1] is None:
                    lst.pop()
                return lst

            matches_out.append({
                "id": m["id"],
                "label": m.get("friendly_label", ""),
                "start_time": start_dt,
                "end_time": end_dt,
                "court": court.get("custom_name") or court.get("name", "TBD"),
                "court_location": court.get("location", ""),
                "our_role": our_role,
                "opponent": opponent,
                "our_scores": trim_scores(our_scores),
                "opp_scores": trim_scores(opp_scores),
                "sets_won": our_sets_won,
                "sets_lost": our_sets_lost,
                "completed": completed,
                "winner": winner,
                "is_published": m.get("is_published", False),
            })

        rounds_out.append({
            "id": round_id,
            "name": rnd["name"],
            "abbreviation": rnd.get("abbreviation", ""),
            "pool_bracket_id": pool_bracket_id,
            "pool_bracket_label": seed_info.get("current_position_friendly_label", ""),
            "matches": matches_out,
            "seed_info": seed_info,
            "status": "active",
        })

    # Determine current and next match
    current_match = None
    next_match = None
    for rnd in rounds_out:
        for m in rnd["matches"]:
            if m["our_role"] != "playing":
                continue
            st = m["start_time"]
            et = m["end_time"]
            if not st:
                continue
            # aware comparison
            st_aware = st if st.tzinfo else st.replace(tzinfo=timezone.utc)
            et_aware = et if (et and et.tzinfo) else (et.replace(tzinfo=timezone.utc) if et else None)

            if st_aware <= now and (not et_aware or et_aware >= now) and not m["completed"]:
                current_match = m
            elif st_aware > now and not next_match:
                next_match = m

    return {
        "event": event,
        "team": team,
        "rounds": rounds_out,
        "now": now,
        "current_match": current_match,
        "next_match": next_match,
    }


# ── Server-side live prefetch (background thread) ─────────────────────────────
#
# Instead of fetching TM2Sign on every /live request (slow, especially on bad
# connections at venues), a daemon thread polls every 45 s and stores the result
# in _live_cache. The /live page renders from cache (instant). The JS poller
# calls /live/data?v=<version> which returns a ~30-byte {"changed":false} when
# nothing changed, or a compact delta of just scores + match IDs when it has.

_live_cache: dict = {"data": None, "version": 0, "hash": ""}
_live_lock = threading.Lock()
_REFRESH_INTERVAL = 45       # seconds between TM2 API polls
_prefetch_started = False
_prefetch_event_id: int = 0
_prefetch_team_id: int = 0


def _volatile_hash(data: dict) -> str:
    """Hash only the parts that change mid-match (scores, current/next pointer)."""
    cm = data.get("current_match")
    nm = data.get("next_match")
    volatile = {
        "cm": cm["id"] if cm else None,
        "nm": nm["id"] if nm else None,
        "s": {
            str(m["id"]): [m["our_scores"], m["opp_scores"],
                           m["sets_won"], m["sets_lost"],
                           m["completed"], m["winner"]]
            for rnd in data.get("rounds", [])
            for m in rnd["matches"]
            if m["our_role"] == "playing"
        },
    }
    return hashlib.md5(
        _json.dumps(volatile, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]


def _do_refresh():
    try:
        fresh = get_team_schedule(_prefetch_event_id, _prefetch_team_id)
        h = _volatile_hash(fresh)
        with _live_lock:
            if h != _live_cache["hash"]:
                _live_cache["version"] += 1
                _live_cache["hash"] = h
            _live_cache["data"] = fresh
    except Exception as exc:
        log.warning("Live prefetch refresh failed: %s", exc)


def _prefetch_worker():
    while True:
        time.sleep(_REFRESH_INTERVAL)
        _do_refresh()


def start_live_prefetch(event_id: int, team_id: int):
    """Start background prefetch. Idempotent — safe to call multiple times."""
    global _prefetch_started, _prefetch_event_id, _prefetch_team_id
    if _prefetch_started:
        return
    _prefetch_started = True
    _prefetch_event_id = event_id
    _prefetch_team_id = team_id
    _do_refresh()   # blocking: warms cache so first /live request is instant
    t = threading.Thread(target=_prefetch_worker, daemon=True)
    t.start()
    log.info("Live prefetch started — event=%d team=%d interval=%ds",
             event_id, team_id, _REFRESH_INTERVAL)


def get_cached_schedule():
    """Return (data, version) from the in-memory live cache."""
    with _live_lock:
        return _live_cache["data"], _live_cache["version"]


def get_live_delta(since_version: int) -> dict:
    """
    Compact delta for the JS poller.
    Returns {"changed": False, "version": n} (~30 bytes) when nothing changed.
    Returns scores dict + current/next match IDs when data has changed.
    """
    with _live_lock:
        version = _live_cache["version"]
        data = _live_cache["data"]

    if since_version >= version or not data:
        return {"changed": False, "version": version}

    cm = data.get("current_match")
    nm = data.get("next_match")

    scores = {}
    for rnd in data.get("rounds", []):
        for m in rnd["matches"]:
            if m["our_role"] == "playing":
                scores[str(m["id"])] = {
                    "our_scores": m["our_scores"],
                    "opp_scores": m["opp_scores"],
                    "sets_won": m["sets_won"],
                    "sets_lost": m["sets_lost"],
                    "completed": m["completed"],
                    "winner": m["winner"],
                }

    return {
        "changed": True,
        "version": version,
        "current_match_id": cm["id"] if cm else None,
        "next_match_id": nm["id"] if nm else None,
        "scores": scores,
    }
