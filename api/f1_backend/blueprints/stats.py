import datetime
import math
import time
import concurrent.futures
from flask import Blueprint, request, jsonify
import fastf1
from fastf1.ergast import Ergast
import pandas as pd
from ..utils import validate_year, error_response, get_historical_team_color
from .standings import calculate_schedule_progress

stats_bp = Blueprint("stats", __name__)


def _safe_int(val, default=0):
    """Safely convert a value to int, handling NaN, strings, and None."""
    try:
        if pd.isna(val):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    """Safely convert a value to float, handling NaN and None."""
    try:
        if pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val, default=""):
    """Safely convert a value to stripped string, handling None and NaN."""
    if val is None or pd.isna(val):
        return default
    s = str(val).strip()
    return default if s.lower() in ("nan", "none", "null") else s


def safe_ergast_call(fn, *args, **kwargs):
    """Execute Ergast call with exponential backoff on 429/rate limits."""
    for attempt in range(4):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "Too Many Requests" in err_str or "429" in err_str:
                time.sleep(0.5 * (2**attempt))
                continue
            if attempt == 3:
                raise e
            time.sleep(0.2)
    return fn(*args, **kwargs)


def is_dns(status, pos_text):
    """Determine if driver did not start the session."""
    s = _safe_str(status).lower()
    p = _safe_str(pos_text).upper()
    return (
        p in ("W", "G")
        or "did not start" in s
        or "withdrawn" in s
        or "not started" in s
    )


def is_dnf(status, pos_text):
    """Determine if driver retired or unclassified in the race."""
    if is_dns(status, pos_text):
        return False
    s = _safe_str(status)
    p = _safe_str(pos_text).upper()
    if p in ("R", "D"):
        return True
    if s == "Finished" or s == "Lapped" or s.startswith("+"):
        return False
    # Any mechanical failure, accident, collision, retired
    return True


def get_driver_spotlight_stat(driver_dict, completed_rounds):
    """Select the spotlight stat for a driver based on rounds completed and standings position."""
    best_f = driver_dict.get("best_finish")
    races = max(1, driver_dict.get("races_entered", 1))
    pos = driver_dict.get("position", 999)
    wins = driver_dict.get("wins", 0)
    podiums = driver_dict.get("podiums", 0)
    top10s = driver_dict.get("top_10s", 0)
    points = driver_dict.get("points", 0.0)
    ppr = driver_dict.get("points_per_race", 0.0)
    fr = driver_dict.get("finish_rate_pct", 0.0)

    if completed_rounds <= 3:
        val = f"P{best_f}" if best_f is not None else "N/A"
        return {
            "label": "EARLY FORM",
            "value": val,
            "subtext": f"{ppr} pts/race",
            "tier": "early",
        }
    elif pos <= 3 or wins > 0:
        pct = round((podiums / races) * 100)
        return {
            "label": "PODIUM RATE",
            "value": f"{pct}%",
            "subtext": f"{podiums} of {races} GPs",
            "tier": "contender",
        }
    elif pos <= 10 or points > 0:
        pct = round((top10s / races) * 100)
        return {
            "label": "POINTS RATE",
            "value": f"{top10s}/{races}",
            "subtext": f"Top-10 Finishes ({pct}%)",
            "tier": "midfield",
        }
    else:
        val = f"P{best_f}" if best_f is not None else "—"
        return {
            "label": "BEST FINISH",
            "value": val,
            "subtext": f"{fr}% Finish Rate",
            "tier": "backmarker",
        }


def get_constructor_spotlight_stat(constr_dict, completed_rounds):
    """Rule-driven spotlight stat for constructors."""
    best_f = constr_dict.get("best_finish")
    pos = constr_dict.get("position", 999)
    wins = constr_dict.get("wins", 0)
    podiums = constr_dict.get("podiums", 0)
    one_twos = constr_dict.get("one_two_finishes", 0)
    points = constr_dict.get("points", 0.0)
    rel = constr_dict.get("reliability_pct", 0.0)
    cls_entries = constr_dict.get("classified_entries", 0)
    tot_entries = constr_dict.get("total_entries", 0)
    dnfs = constr_dict.get("dnfs", 0)

    if completed_rounds <= 3:
        val = f"P{best_f}" if best_f is not None else "N/A"
        ppr = round(points / max(1, completed_rounds), 1)
        return {
            "label": "EARLY FORM",
            "value": val,
            "subtext": f"{ppr} pts/race",
            "tier": "early",
        }
    elif pos <= 3 or wins > 0:
        sub = f"{wins} Win{'s' if wins != 1 else ''}"
        if one_twos > 0:
            sub += f" • {one_twos} 1-2s"
        return {
            "label": "PODIUMS",
            "value": str(podiums),
            "subtext": sub,
            "tier": "contender",
        }
    elif pos <= 6 or points > 0:
        return {
            "label": "RELIABILITY",
            "value": f"{rel}%",
            "subtext": f"{cls_entries}/{tot_entries} Finishes",
            "tier": "midfield",
        }
    else:
        val = f"P{best_f}" if best_f is not None else "—"
        return {
            "label": "BEST FINISH",
            "value": val,
            "subtext": f"{dnfs} DNF{'s' if dnfs != 1 else ''}",
            "tier": "backmarker",
        }


@stats_bp.route("/season-stats", methods=["GET"])
def get_season_stats():
    year = request.args.get("year", type=int)
    if not year:
        return error_response("Year parameter is required and must be an integer.", 400)

    is_valid, err_msg = validate_year(year)
    if not is_valid:
        return error_response(err_msg, 400)

    current_year = datetime.datetime.now().year
    ergast = Ergast()

    # Parallel Ergast fetching with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        ds_future = executor.submit(
            safe_ergast_call, ergast.get_driver_standings, season=year, limit=1000
        )
        cs_future = (
            executor.submit(
                safe_ergast_call,
                ergast.get_constructor_standings,
                season=year,
                limit=1000,
            )
            if year >= 1958
            else None
        )

        race_futures = [
            executor.submit(
                safe_ergast_call,
                ergast.get_race_results,
                season=year,
                limit=100,
                offset=offset,
            )
            for offset in (0, 100, 200, 300, 400, 500)
        ]

        quali_futures = [
            executor.submit(
                safe_ergast_call,
                ergast.get_qualifying_results,
                season=year,
                limit=100,
                offset=offset,
            )
            for offset in (0, 100, 200, 300, 400, 500)
        ]

        sprint_futures = (
            [
                executor.submit(
                    safe_ergast_call,
                    ergast.get_sprint_results,
                    season=year,
                    limit=100,
                    offset=offset,
                )
                for offset in (0, 100)
            ]
            if year >= 2021
            else []
        )

        schedule_future = executor.submit(
            fastf1.get_event_schedule, year=year, include_testing=False
        )

    # 1. Driver & Constructor Standings
    driver_standings_df = pd.DataFrame()
    ds_round = None
    try:
        ds_res = ds_future.result()
        if ds_res.content and not ds_res.content[0].empty:
            driver_standings_df = ds_res.content[0]
            if hasattr(ds_res, "description") and "round" in ds_res.description.columns:
                ds_round = _safe_int(ds_res.description["round"].iloc[0], None)
    except Exception:
        pass

    constructor_standings_df = pd.DataFrame()
    if cs_future is not None:
        try:
            cs_res = cs_future.result()
            if cs_res.content and not cs_res.content[0].empty:
                constructor_standings_df = cs_res.content[0]
        except Exception:
            pass

    # 2. Race Results aggregation across pages
    # Structure: round_num -> { "info": dict, "drivers": { driver_id: row_dict } }
    races_by_round = {}
    for rf in race_futures:
        try:
            res = rf.result()
            if not res or not hasattr(res, "content") or not res.content:
                continue
            for i, df in enumerate(res.content):
                if df.empty:
                    continue
                desc_row = (
                    res.description.iloc[i].to_dict()
                    if hasattr(res, "description") and i < len(res.description)
                    else {}
                )
                r_num = _safe_int(desc_row.get("round", i + 1))
                if r_num not in races_by_round:
                    races_by_round[r_num] = {
                        "info": desc_row,
                        "drivers": {},
                    }
                for _, row in df.iterrows():
                    d_id = _safe_str(row.get("driverId"))
                    if d_id and d_id not in races_by_round[r_num]["drivers"]:
                        races_by_round[r_num]["drivers"][d_id] = row.to_dict()
        except Exception:
            pass

    # 3. Qualifying Results aggregation
    # Structure: round_num -> { driver_id: row_dict }
    quali_by_round = {}
    for qf in quali_futures:
        try:
            res = qf.result()
            if not res or not hasattr(res, "content") or not res.content:
                continue
            for i, df in enumerate(res.content):
                if df.empty:
                    continue
                desc_row = (
                    res.description.iloc[i].to_dict()
                    if hasattr(res, "description") and i < len(res.description)
                    else {}
                )
                r_num = _safe_int(desc_row.get("round", i + 1))
                if r_num not in quali_by_round:
                    quali_by_round[r_num] = {}
                for _, row in df.iterrows():
                    d_id = _safe_str(row.get("driverId"))
                    if d_id and d_id not in quali_by_round[r_num]:
                        quali_by_round[r_num][d_id] = row.to_dict()
        except Exception:
            pass

    # 4. Sprint Results aggregation
    # Structure: round_num -> { driver_id: row_dict }
    sprint_by_round = {}
    for sf in sprint_futures:
        try:
            res = sf.result()
            if not res or not hasattr(res, "content") or not res.content:
                continue
            for i, df in enumerate(res.content):
                if df.empty:
                    continue
                desc_row = (
                    res.description.iloc[i].to_dict()
                    if hasattr(res, "description") and i < len(res.description)
                    else {}
                )
                r_num = _safe_int(desc_row.get("round", i + 1))
                if r_num not in sprint_by_round:
                    sprint_by_round[r_num] = {}
                for _, row in df.iterrows():
                    d_id = _safe_str(row.get("driverId"))
                    if d_id and d_id not in sprint_by_round[r_num]:
                        sprint_by_round[r_num][d_id] = row.to_dict()
        except Exception:
            pass

    # 5. Schedule & Progress
    schedule = None
    try:
        schedule = schedule_future.result()
    except Exception:
        schedule = None

    completed_rounds_count = max(
        len(races_by_round),
        ds_round if ds_round is not None else 0,
    )
    progress = calculate_schedule_progress(
        year=year,
        ds_round=completed_rounds_count,
        current_year=current_year,
        schedule=schedule,
    )
    total_rounds = progress["total_rounds"]
    completed_rounds = progress["completed_rounds"]
    remaining_rounds = progress["remaining_rounds"]
    is_early_season = completed_rounds <= 3
    is_completed = remaining_rounds == 0

    # 6. Map all drivers and constructors
    # Discovered metadata: driver_id -> metadata
    driver_meta = {}
    # Driver primary team: driver_id -> constructor_id
    driver_primary_teams = {}
    driver_team_counts = {}  # d_id -> { c_id: count }
    constructor_meta = {}  # c_id -> name

    # Seed from standings if available
    if not driver_standings_df.empty:
        for _, row in driver_standings_df.iterrows():
            d_id = _safe_str(row.get("driverId"))
            if not d_id:
                continue
            c_ids = row.get("constructorIds")
            c_names = row.get("constructorNames")
            c_id = ""
            c_name = "Unknown"
            if isinstance(c_ids, list) and c_ids:
                c_id = str(c_ids[0])
            elif pd.notna(c_ids):
                c_id = str(c_ids)
            if isinstance(c_names, list) and c_names:
                c_name = str(c_names[0])
            elif pd.notna(c_names):
                c_name = str(c_names)

            code = _safe_str(row.get("driverCode"))
            if not code:
                code = _safe_str(row.get("familyName", "??"))[:3].upper()

            driver_meta[d_id] = {
                "driver_id": d_id,
                "driver_number": _safe_str(row.get("driverNumber", "??")),
                "driver_code": code,
                "driver_name": f"{_safe_str(row.get('givenName'))} {_safe_str(row.get('familyName'))}".strip(),
                "nationality": _safe_str(row.get("driverNationality")),
                "date_of_birth": _safe_str(row.get("dateOfBirth")),
                "standings_position": _safe_int(row.get("position"), 999),
                "standings_points": _safe_float(row.get("points")),
                "standings_wins": _safe_int(row.get("wins")),
                "team_id": c_id,
                "team_name": c_name,
            }
            if c_id:
                constructor_meta[c_id] = c_name

    # Discover and update from race results
    sorted_rounds = sorted(races_by_round.keys())
    for r_num in sorted_rounds:
        r_drivers = races_by_round[r_num]["drivers"]
        for d_id, row in r_drivers.items():
            c_id = _safe_str(row.get("constructorId"))
            c_name = _safe_str(row.get("constructorName", "Unknown"))
            if c_id:
                constructor_meta[c_id] = c_name
                if d_id not in driver_team_counts:
                    driver_team_counts[d_id] = {}
                driver_team_counts[d_id][c_id] = (
                    driver_team_counts[d_id].get(c_id, 0) + 1
                )

            if d_id not in driver_meta:
                code = _safe_str(row.get("driverCode"))
                if not code:
                    code = _safe_str(row.get("familyName", "??"))[:3].upper()
                driver_meta[d_id] = {
                    "driver_id": d_id,
                    "driver_number": _safe_str(
                        row.get("driverNumber", row.get("number", "??"))
                    ),
                    "driver_code": code,
                    "driver_name": f"{_safe_str(row.get('givenName'))} {_safe_str(row.get('familyName'))}".strip(),
                    "nationality": _safe_str(row.get("driverNationality")),
                    "date_of_birth": _safe_str(row.get("dateOfBirth")),
                    "standings_position": 999,
                    "standings_points": 0.0,
                    "standings_wins": 0,
                    "team_id": c_id,
                    "team_name": c_name,
                }

    # Resolve primary team for each driver
    for d_id, counts in driver_team_counts.items():
        best_team = max(counts.items(), key=lambda x: x[1])[0]
        driver_primary_teams[d_id] = best_team
        if d_id in driver_meta:
            driver_meta[d_id]["team_id"] = best_team
            driver_meta[d_id]["team_name"] = constructor_meta.get(best_team, "Unknown")

    # 7. Seed Constructor Standings Points
    constructor_standings_data = {}
    if not constructor_standings_df.empty:
        for _, row in constructor_standings_df.iterrows():
            c_id = _safe_str(row.get("constructorId"))
            if not c_id:
                continue
            constructor_standings_data[c_id] = {
                "position": _safe_int(row.get("position"), 999),
                "points": _safe_float(row.get("points")),
                "wins": _safe_int(row.get("wins")),
                "name": _safe_str(
                    row.get("constructorName", constructor_meta.get(c_id, c_id))
                ),
            }
            constructor_meta[c_id] = constructor_standings_data[c_id]["name"]

    # 8. Compute Driver-level Performance & Form
    driver_stats = {}
    # We will accumulate:
    # races_entered, classified_finishes, dnfs, wins, podiums, poles, fastest_laps, top_10s
    # grids, finishes, round_points, season_form
    for d_id, meta in driver_meta.items():
        driver_stats[d_id] = {
            "races_entered": 0,
            "classified_finishes": 0,
            "dnfs": 0,
            "wins": 0,
            "podiums": 0,
            "poles": 0,
            "fastest_laps": 0,
            "top_10s": 0,
            "total_points": 0.0,
            "grids": [],
            "finishes": [],
            "season_form": [],
            "teams_entered": set(),
        }

    # Evaluate each round
    for r_num in sorted_rounds:
        r_info = races_by_round[r_num]["info"]
        r_name = _safe_str(r_info.get("raceName", f"Round {r_num}"))
        r_drivers = races_by_round[r_num]["drivers"]
        q_drivers = quali_by_round.get(r_num, {})
        s_drivers = sprint_by_round.get(r_num, {})

        for d_id, row in r_drivers.items():
            if d_id not in driver_stats:
                continue
            st = driver_stats[d_id]
            st["races_entered"] += 1

            c_id = _safe_str(row.get("constructorId"))
            if c_id:
                st["teams_entered"].add(c_id)

            status = _safe_str(row.get("status"))
            pos_text = _safe_str(row.get("positionText"))
            pos = _safe_int(row.get("position"), None)
            grid = _safe_int(row.get("grid"), 0)

            race_pts = _safe_float(row.get("points"), 0.0)
            sprint_pts = _safe_float(s_drivers.get(d_id, {}).get("points"), 0.0)
            round_pts = race_pts + sprint_pts
            st["total_points"] += round_pts

            if grid > 0:
                st["grids"].append(grid)

            driver_dns = is_dns(status, pos_text)
            driver_dnf = is_dnf(status, pos_text)

            if driver_dnf:
                st["dnfs"] += 1
            else:
                st["classified_finishes"] += 1
                if pos is not None and pos > 0:
                    st["finishes"].append(pos)

            if pos == 1 and not driver_dnf:
                st["wins"] += 1
            if pos is not None and 1 <= pos <= 3 and not driver_dnf:
                st["podiums"] += 1
            if pos is not None and 1 <= pos <= 10 and not driver_dnf:
                st["top_10s"] += 1

            # Poles: Qualifying position == 1, or fallback to grid == 1 if quali is empty
            if q_drivers:
                if (
                    d_id in q_drivers
                    and _safe_int(q_drivers[d_id].get("position")) == 1
                ):
                    st["poles"] += 1
            else:
                if grid == 1:
                    st["poles"] += 1

            # Fastest Lap
            fl_rank = str(row.get("fastestLapRank", "")).strip()
            if fl_rank == "1":
                st["fastest_laps"] += 1

            # Determine form category
            if driver_dns:
                cat = "dns"
            elif driver_dnf:
                cat = "dnf"
            elif pos == 1:
                cat = "win"
            elif pos in (2, 3):
                cat = "podium"
            elif pos is not None and pos <= 10:
                cat = "points"
            else:
                cat = "outside"

            st["season_form"].append(
                {
                    "round": r_num,
                    "round_name": r_name,
                    "grid": grid if grid > 0 else None,
                    "position": pos if (pos and pos > 0) else None,
                    "position_text": pos_text,
                    "points": race_pts,
                    "sprint_points": sprint_pts,
                    "total_weekend_points": round_pts,
                    "status": status,
                    "category": cat,
                }
            )

    # 9. Aggregate Constructor Team Totals
    # constructor_id -> dict
    all_c_ids = set(constructor_meta.keys())
    for d_id, st in driver_stats.items():
        all_c_ids.update(st["teams_entered"])

    constructor_stats = {}
    for c_id in all_c_ids:
        c_name = constructor_meta.get(c_id, c_id.replace("_", " ").title())
        s_data = constructor_standings_data.get(c_id, {})
        constructor_stats[c_id] = {
            "constructor_id": c_id,
            "constructor_name": s_data.get("name", c_name),
            "team_color": get_historical_team_color(c_id),
            "position": s_data.get("position", 999),
            "points": s_data.get("points", 0.0),
            "wins": s_data.get("wins", 0),
            "podiums": 0,
            "poles": 0,
            "one_two_finishes": 0,
            "fastest_laps": 0,
            "dnfs": 0,
            "total_entries": 0,
            "classified_entries": 0,
            "reliability_pct": 0.0,
            "best_finish": None,
            "drivers": [],
        }

    # Evaluate team round-by-round statistics
    c_wins_from_races = {}
    c_points_from_races = {}
    for r_num in sorted_rounds:
        r_drivers = races_by_round[r_num]["drivers"]
        q_drivers = quali_by_round.get(r_num, {})
        s_drivers = sprint_by_round.get(r_num, {})

        # Track per-constructor positions in this round for 1-2 finishes and entries
        c_round_finishes = {}
        for d_id, row in r_drivers.items():
            c_id = _safe_str(row.get("constructorId"))
            if not c_id or c_id not in constructor_stats:
                continue
            cs = constructor_stats[c_id]
            cs["total_entries"] += 1

            status = _safe_str(row.get("status"))
            pos_text = _safe_str(row.get("positionText"))
            pos = _safe_int(row.get("position"), None)
            d_dnf = is_dnf(status, pos_text)

            race_pts = _safe_float(row.get("points"), 0.0)
            sprint_pts = _safe_float(s_drivers.get(d_id, {}).get("points"), 0.0)
            c_points_from_races[c_id] = (
                c_points_from_races.get(c_id, 0.0) + race_pts + sprint_pts
            )

            if d_dnf:
                cs["dnfs"] += 1
            else:
                cs["classified_entries"] += 1
                if pos is not None and pos > 0:
                    if c_id not in c_round_finishes:
                        c_round_finishes[c_id] = []
                    c_round_finishes[c_id].append(pos)
                    if cs["best_finish"] is None or pos < cs["best_finish"]:
                        cs["best_finish"] = pos

            if pos == 1 and not d_dnf:
                c_wins_from_races[c_id] = c_wins_from_races.get(c_id, 0) + 1
            if pos is not None and 1 <= pos <= 3 and not d_dnf:
                cs["podiums"] += 1

            fl_rank = str(row.get("fastestLapRank", "")).strip()
            if fl_rank == "1":
                cs["fastest_laps"] += 1

        # Check 1-2 finish for any constructor in this round
        for c_id, finishes in c_round_finishes.items():
            if len(finishes) >= 2 and 1 in finishes and 2 in finishes:
                constructor_stats[c_id]["one_two_finishes"] += 1

        # Check poles from qualifying or grid
        if q_drivers:
            for d_id, qrow in q_drivers.items():
                if _safe_int(qrow.get("position")) == 1:
                    c_id = _safe_str(qrow.get("constructorId"))
                    if c_id in constructor_stats:
                        constructor_stats[c_id]["poles"] += 1
        else:
            for d_id, rrow in r_drivers.items():
                if _safe_int(rrow.get("grid")) == 1:
                    c_id = _safe_str(rrow.get("constructorId"))
                    if c_id in constructor_stats:
                        constructor_stats[c_id]["poles"] += 1

    # Finalize constructor reliability & team points fallback
    for c_id, cs in constructor_stats.items():
        tot = cs["total_entries"]
        cls_e = cs["classified_entries"]
        cs["reliability_pct"] = (
            round((cls_e / max(1, tot)) * 100.0, 1) if tot > 0 else 0.0
        )
        cs["wins"] = max(cs["wins"], c_wins_from_races.get(c_id, 0))
        if cs["points"] == 0.0 and c_points_from_races.get(c_id, 0.0) > 0.0:
            cs["points"] = round(c_points_from_races[c_id], 2)

    # 10. Group teammates by constructor and compute head-to-head
    # For each constructor, find drivers who drove for them
    constructor_drivers_map = {}
    for d_id, st in driver_stats.items():
        meta = driver_meta[d_id]
        c_id = meta.get("team_id")
        if not c_id:
            continue
        if c_id not in constructor_drivers_map:
            constructor_drivers_map[c_id] = []
        constructor_drivers_map[c_id].append(d_id)

    teammate_h2h_by_driver = {}  # d_id -> teammate_h2h dict
    teammate_battles_list = []

    for c_id, d_ids in constructor_drivers_map.items():
        # Sort drivers by races entered with this team, then points
        d_ids_sorted = sorted(
            d_ids,
            key=lambda d: (
                driver_stats[d]["races_entered"],
                driver_meta[d].get("standings_points", driver_stats[d]["total_points"]),
            ),
            reverse=True,
        )

        d1_id = d_ids_sorted[0] if len(d_ids_sorted) > 0 else None
        d2_id = d_ids_sorted[1] if len(d_ids_sorted) > 1 else None
        reserves = d_ids_sorted[2:] if len(d_ids_sorted) > 2 else []

        quali_d1 = 0
        quali_d2 = 0
        race_d1 = 0
        race_d2 = 0

        if d1_id and d2_id:
            # Only count rounds where both teammates participated for this constructor
            for r_num in sorted_rounds:
                r_drivers = races_by_round[r_num]["drivers"]
                q_drivers = quali_by_round.get(r_num, {})

                # Quali H2H
                if d1_id in q_drivers and d2_id in q_drivers:
                    qrow1 = q_drivers[d1_id]
                    qrow2 = q_drivers[d2_id]
                    if (
                        _safe_str(qrow1.get("constructorId")) == c_id
                        and _safe_str(qrow2.get("constructorId")) == c_id
                    ):
                        qpos1 = _safe_int(qrow1.get("position"), 999)
                        qpos2 = _safe_int(qrow2.get("position"), 999)
                        if qpos1 < qpos2:
                            quali_d1 += 1
                        elif qpos2 < qpos1:
                            quali_d2 += 1

                # Race H2H
                if d1_id in r_drivers and d2_id in r_drivers:
                    row1 = r_drivers[d1_id]
                    row2 = r_drivers[d2_id]
                    if (
                        _safe_str(row1.get("constructorId")) == c_id
                        and _safe_str(row2.get("constructorId")) == c_id
                    ):
                        if is_dns(
                            _safe_str(row1.get("status")),
                            _safe_str(row1.get("positionText")),
                        ) or is_dns(
                            _safe_str(row2.get("status")),
                            _safe_str(row2.get("positionText")),
                        ):
                            continue
                        pos1 = _safe_int(row1.get("position"), 999)
                        pos2 = _safe_int(row2.get("position"), 999)
                        if pos1 < pos2:
                            race_d1 += 1
                        elif pos2 < pos1:
                            race_d2 += 1

            # Assign teammate H2H for d1
            meta1 = driver_meta[d1_id]
            meta2 = driver_meta[d2_id]
            teammate_h2h_by_driver[d1_id] = {
                "teammate_code": meta2["driver_code"],
                "teammate_name": meta2["driver_name"],
                "quali_wins": quali_d1,
                "quali_losses": quali_d2,
                "race_wins": race_d1,
                "race_losses": race_d2,
            }
            # Assign teammate H2H for d2
            teammate_h2h_by_driver[d2_id] = {
                "teammate_code": meta1["driver_code"],
                "teammate_name": meta1["driver_name"],
                "quali_wins": quali_d2,
                "quali_losses": quali_d1,
                "race_wins": race_d2,
                "race_losses": race_d1,
            }

        # Any reserve drivers or single drivers
        for extra_id in reserves:
            ref_id = d1_id if d1_id else d2_id
            if ref_id:
                meta_ref = driver_meta[ref_id]
                teammate_h2h_by_driver[extra_id] = {
                    "teammate_code": meta_ref["driver_code"],
                    "teammate_name": meta_ref["driver_name"],
                    "quali_wins": 0,
                    "quali_losses": 0,
                    "race_wins": 0,
                    "race_losses": 0,
                }
            else:
                teammate_h2h_by_driver[extra_id] = {
                    "teammate_code": "—",
                    "teammate_name": "None",
                    "quali_wins": 0,
                    "quali_losses": 0,
                    "race_wins": 0,
                    "race_losses": 0,
                }

        if d1_id and not d2_id:
            teammate_h2h_by_driver[d1_id] = {
                "teammate_code": "—",
                "teammate_name": "None",
                "quali_wins": 0,
                "quali_losses": 0,
                "race_wins": 0,
                "race_losses": 0,
            }

        # Build teammate battle object for this constructor
        if d1_id and d2_id and c_id in constructor_stats:
            cs = constructor_stats[c_id]
            m1 = driver_meta[d1_id]
            m2 = driver_meta[d2_id]
            st1 = driver_stats[d1_id]
            st2 = driver_stats[d2_id]

            p1_pts = m1.get("standings_points", st1["total_points"])
            p2_pts = m2.get("standings_points", st2["total_points"])
            c_pts = cs["points"] if cs["points"] > 0 else (p1_pts + p2_pts)

            p1_share = round((p1_pts / c_pts) * 100.0, 1) if c_pts > 0 else 0.0
            p2_share = round((p2_pts / c_pts) * 100.0, 1) if c_pts > 0 else 0.0

            fin1 = [f for f in st1["finishes"] if f is not None]
            fin2 = [f for f in st2["finishes"] if f is not None]
            avg_fin1 = round(sum(fin1) / len(fin1), 1) if fin1 else None
            avg_fin2 = round(sum(fin2) / len(fin2), 1) if fin2 else None

            reserve_objs = []
            for r_id in reserves:
                rm = driver_meta[r_id]
                rst = driver_stats[r_id]
                reserve_objs.append(
                    {
                        "driver_id": r_id,
                        "driver_code": rm["driver_code"],
                        "driver_name": rm["driver_name"],
                        "driver_number": rm["driver_number"],
                        "races_entered": rst["races_entered"],
                        "points": rm.get("standings_points", rst["total_points"]),
                    }
                )

            teammate_battles_list.append(
                {
                    "constructor_id": c_id,
                    "constructor_name": cs["constructor_name"],
                    "team_color": cs["team_color"],
                    "position": cs["position"],
                    "total_points": c_pts,
                    "driver1": {
                        "driver_id": d1_id,
                        "driver_code": m1["driver_code"],
                        "driver_name": m1["driver_name"],
                        "driver_number": m1["driver_number"],
                        "points": p1_pts,
                        "points_pct": p1_share,
                        "wins": st1["wins"],
                        "podiums": st1["podiums"],
                        "poles": st1["poles"],
                        "avg_finish": avg_fin1,
                        "dnfs": st1["dnfs"],
                    },
                    "driver2": {
                        "driver_id": d2_id,
                        "driver_code": m2["driver_code"],
                        "driver_name": m2["driver_name"],
                        "driver_number": m2["driver_number"],
                        "points": p2_pts,
                        "points_pct": p2_share,
                        "wins": st2["wins"],
                        "podiums": st2["podiums"],
                        "poles": st2["poles"],
                        "avg_finish": avg_fin2,
                        "dnfs": st2["dnfs"],
                    },
                    "quali_h2h": {
                        "d1": quali_d1,
                        "d2": quali_d2,
                        "total": quali_d1 + quali_d2,
                    },
                    "race_h2h": {
                        "d1": race_d1,
                        "d2": race_d2,
                        "total": race_d1 + race_d2,
                    },
                    "reserve_drivers": reserve_objs,
                }
            )

    # Sort teammate battles by constructor rank
    teammate_battles_list.sort(key=lambda b: (b["position"], -b["total_points"]))

    # 11. Compile Final Drivers List
    drivers_list = []
    for d_id, meta in driver_meta.items():
        st = driver_stats[d_id]
        c_id = meta.get("team_id", "")
        c_name = meta.get("team_name", "Unknown")
        team_pts = constructor_stats.get(c_id, {}).get("points", 0.0)

        # Standings position / points priority
        pts = meta.get("standings_points")
        if pts is None or pts == 0.0:
            pts = st["total_points"]

        wins = meta.get("standings_wins")
        if wins is None or wins == 0:
            wins = st["wins"]

        share_pct = 0.0
        if team_pts > 0:
            share_pct = round(min(100.0, max(0.0, (pts / team_pts) * 100.0)), 1)
        elif pts > 0:
            share_pct = 100.0

        races_ent = st["races_entered"]
        cls_fin = st["classified_finishes"]
        dnfs = st["dnfs"]
        finish_rate = round((cls_fin / max(1, races_ent)) * 100.0, 1)

        grids = st["grids"]
        avg_grid = round(sum(grids) / len(grids), 1) if grids else None

        finishes = [f for f in st["finishes"] if f is not None]
        avg_finish = round(sum(finishes) / len(finishes), 1) if finishes else None
        best_finish = min(finishes) if finishes else None

        avg_pos_gained = (
            round(avg_grid - avg_finish, 1)
            if (avg_grid is not None and avg_finish is not None)
            else 0.0
        )
        ppr = round(pts / max(1, races_ent), 1)

        pos = meta.get("standings_position", 999)
        if pos == 999:
            pos = len(drivers_list) + 1

        driver_obj = {
            "position": pos,
            "driver_id": d_id,
            "driver_number": meta["driver_number"],
            "driver_code": meta["driver_code"],
            "driver_name": meta["driver_name"],
            "team_name": c_name,
            "team_id": c_id,
            "team_color": get_historical_team_color(c_id),
            "nationality": meta["nationality"],
            "date_of_birth": (
                meta["date_of_birth"].split()[0] if meta["date_of_birth"] else ""
            ),
            "points": pts,
            "gap_to_leader": 0.0,  # will update after sort
            "team_points_share_pct": share_pct,
            "wins": wins,
            "podiums": st["podiums"],
            "poles": st["poles"],
            "fastest_laps": st["fastest_laps"],
            "top_10s": st["top_10s"],
            "dnfs": dnfs,
            "races_entered": races_ent,
            "classified_finishes": cls_fin,
            "finish_rate_pct": finish_rate,
            "avg_grid": avg_grid,
            "avg_finish": avg_finish,
            "avg_positions_gained": avg_pos_gained,
            "best_finish": best_finish,
            "points_per_race": ppr,
            "teammate_h2h": teammate_h2h_by_driver.get(
                d_id,
                {
                    "teammate_code": "—",
                    "teammate_name": "None",
                    "quali_wins": 0,
                    "quali_losses": 0,
                    "race_wins": 0,
                    "race_losses": 0,
                },
            ),
            "season_form": st["season_form"],
        }
        driver_obj["spotlight_stat"] = get_driver_spotlight_stat(
            driver_obj, completed_rounds
        )
        drivers_list.append(driver_obj)

    # Sort drivers by championship position, then points descending
    drivers_list.sort(key=lambda d: (d["position"], -d["points"], -d["wins"]))
    # Re-normalize positions and compute gap_to_leader
    leader_pts = drivers_list[0]["points"] if drivers_list else 0.0
    for idx, d in enumerate(drivers_list):
        d["position"] = idx + 1
        d["gap_to_leader"] = (
            round(float(leader_pts - d["points"]), 1) if idx > 0 else 0.0
        )

    # 12. Compile Final Constructors List
    constructors_list = []
    # Link drivers to their constructors
    for d in drivers_list:
        c_id = d["team_id"]
        if c_id in constructor_stats:
            constructor_stats[c_id]["drivers"].append(
                {
                    "driver_id": d["driver_id"],
                    "driver_number": d["driver_number"],
                    "driver_code": d["driver_code"],
                    "driver_name": d["driver_name"],
                    "points": d["points"],
                    "share_pct": d["team_points_share_pct"],
                    "wins": d["wins"],
                    "podiums": d["podiums"],
                    "poles": d["poles"],
                    "dnfs": d["dnfs"],
                    "races_entered": d["races_entered"],
                    "avg_finish": d["avg_finish"],
                }
            )

    for c_id, cs in constructor_stats.items():
        cs["spotlight_stat"] = get_constructor_spotlight_stat(cs, completed_rounds)
        constructors_list.append(cs)

    constructors_list.sort(key=lambda c: (c["position"], -c["points"], -c["wins"]))
    c_leader_pts = constructors_list[0]["points"] if constructors_list else 0.0
    for idx, c in enumerate(constructors_list):
        c["position"] = idx + 1
        c["gap_to_leader"] = (
            round(float(c_leader_pts - c["points"]), 1) if idx > 0 else 0.0
        )

    # 13. Points Progression across rounds
    # Top 10 drivers
    top_10_drivers = drivers_list[:10]
    progression_rounds = []
    for r_num in sorted_rounds:
        r_info = races_by_round[r_num]["info"]
        r_name = _safe_str(r_info.get("raceName", f"Round {r_num}"))
        short = (
            _safe_str(r_info.get("locality", ""))[:3].upper()
            or _safe_str(r_info.get("country", ""))[:3].upper()
            or f"R{r_num}"
        )
        progression_rounds.append(
            {
                "round": r_num,
                "round_name": r_name,
                "short_name": short,
            }
        )

    driver_progressions = []
    for d in top_10_drivers:
        d_id = d["driver_id"]
        cum_points = []
        running_pts = 0.0
        for r_num in sorted_rounds:
            r_pts = 0.0
            r_drivers = races_by_round[r_num]["drivers"]
            if d_id in r_drivers:
                r_pts += _safe_float(r_drivers[d_id].get("points"), 0.0)
            if r_num in sprint_by_round and d_id in sprint_by_round[r_num]:
                r_pts += _safe_float(sprint_by_round[r_num][d_id].get("points"), 0.0)
            running_pts += r_pts
            cum_points.append(round(running_pts, 1))

        driver_progressions.append(
            {
                "driver_id": d_id,
                "driver_code": d["driver_code"],
                "driver_name": d["driver_name"],
                "team_color": d["team_color"],
                "cumulative_points": cum_points,
            }
        )

    constructor_progressions = []
    for c in constructors_list:
        c_id = c["constructor_id"]
        cum_points = []
        running_pts = 0.0
        for r_num in sorted_rounds:
            r_pts = 0.0
            r_drivers = races_by_round[r_num]["drivers"]
            for d_id, row in r_drivers.items():
                if _safe_str(row.get("constructorId")) == c_id:
                    r_pts += _safe_float(row.get("points"), 0.0)
            if r_num in sprint_by_round:
                for d_id, srow in sprint_by_round[r_num].items():
                    if _safe_str(srow.get("constructorId")) == c_id:
                        r_pts += _safe_float(srow.get("points"), 0.0)
            running_pts += r_pts
            cum_points.append(round(running_pts, 1))

        constructor_progressions.append(
            {
                "constructor_id": c_id,
                "constructor_name": c["constructor_name"],
                "team_color": c["team_color"],
                "cumulative_points": cum_points,
            }
        )

    points_progression = {
        "rounds": progression_rounds,
        "drivers": driver_progressions,
        "constructors": constructor_progressions,
    }

    # 14. Latest Round & Next Round
    latest_round = None
    if sorted_rounds:
        last_r = sorted_rounds[-1]
        last_info = races_by_round[last_r]["info"]
        last_drivers = races_by_round[last_r]["drivers"]

        # Sort finishers
        sorted_finishers = sorted(
            [
                d
                for d in last_drivers.values()
                if _safe_int(d.get("position"), 999) <= 3
            ],
            key=lambda x: _safe_int(x.get("position"), 999),
        )

        podium_entries = []
        for p_row in sorted_finishers:
            c_id = _safe_str(p_row.get("constructorId"))
            d_code = _safe_str(p_row.get("driverCode"))
            if not d_code:
                d_code = _safe_str(p_row.get("familyName", "??"))[:3].upper()
            podium_entries.append(
                {
                    "position": _safe_int(p_row.get("position")),
                    "driver_code": d_code,
                    "driver_name": f"{_safe_str(p_row.get('givenName'))} {_safe_str(p_row.get('familyName'))}".strip(),
                    "team_name": _safe_str(p_row.get("constructorName", "Unknown")),
                    "team_color": get_historical_team_color(c_id),
                    "status": _safe_str(p_row.get("status")),
                }
            )

        event_name = _safe_str(last_info.get("raceName", f"Round {last_r}"))
        latest_round = {
            "round": last_r,
            "event_name": event_name,
            "event_key": event_name,
            "date": _safe_str(last_info.get("raceDate")),
            "podium": podium_entries,
        }

    next_round = None
    if remaining_rounds > 0 and schedule is not None and not schedule.empty:
        try:
            next_r_num = completed_rounds + 1
            matching = schedule[schedule["RoundNumber"] == next_r_num]
            if not matching.empty:
                nrow = matching.iloc[0]
                ev_name = _safe_str(nrow.get("EventName"))
                ev_fmt = _safe_str(nrow.get("EventFormat")).lower()
                is_sp = "sprint" in ev_fmt
                next_sessions = []
                gmt_offset = None
                for s_idx in range(1, 6):
                    s_name = nrow.get(f"Session{s_idx}")
                    if pd.isna(s_name) or not str(s_name).strip():
                        continue
                    s_local = nrow.get(f"Session{s_idx}Date")
                    s_utc = nrow.get(f"Session{s_idx}DateUtc")
                    utc_iso = None
                    if pd.notna(s_utc):
                        utc_iso = s_utc.isoformat()
                        if (
                            not utc_iso.endswith("Z")
                            and "+" not in utc_iso[10:]
                            and "-" not in utc_iso[10:]
                        ):
                            utc_iso += "Z"
                    elif (
                        pd.notna(s_local)
                        and getattr(s_local, "tzinfo", None) is not None
                    ):
                        utc_iso = s_local.tz_convert("UTC").strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        )

                    local_iso = s_local.isoformat() if pd.notna(s_local) else None
                    if (
                        gmt_offset is None
                        and pd.notna(s_local)
                        and getattr(s_local, "tzinfo", None) is not None
                    ):
                        off = s_local.utcoffset()
                        if off is not None:
                            total_mins = int(off.total_seconds() // 60)
                            sign = "+" if total_mins >= 0 else "-"
                            hrs, mins = divmod(abs(total_mins), 60)
                            gmt_offset = f"{sign}{hrs:02d}:{mins:02d}"

                    next_sessions.append(
                        {
                            "name": str(s_name).strip(),
                            "utc": utc_iso,
                            "local": local_iso,
                        }
                    )
                next_round = {
                    "round": next_r_num,
                    "event_name": ev_name,
                    "event_key": ev_name,
                    "location": _safe_str(nrow.get("Location")),
                    "country": _safe_str(nrow.get("Country")),
                    "date": (
                        nrow["EventDate"].isoformat()
                        if pd.notna(nrow.get("EventDate"))
                        else None
                    ),
                    "is_sprint": is_sp,
                    "gmt_offset": gmt_offset,
                    "sessions": next_sessions,
                }
        except Exception:
            pass

    return (
        jsonify(
            {
                "year": year,
                "completed_rounds": completed_rounds,
                "total_rounds": total_rounds,
                "remaining_rounds": remaining_rounds,
                "is_early_season": is_early_season,
                "is_completed": is_completed,
                "drivers": drivers_list,
                "teammate_battles": teammate_battles_list,
                "constructors": constructors_list,
                "points_progression": points_progression,
                "latest_round": latest_round,
                "next_round": next_round,
            }
        ),
        200,
    )


@stats_bp.route("/driver-career", methods=["GET"])
def get_driver_career():
    driver_id = request.args.get("driver_id", type=str)
    if not driver_id or not driver_id.strip():
        return error_response("driver_id parameter is required.", 400)

    driver_id = driver_id.strip().lower()
    ergast = Ergast()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        info_fut = executor.submit(
            safe_ergast_call, ergast.get_driver_info, driver=driver_id
        )
        starts_fut = executor.submit(
            safe_ergast_call, ergast.get_race_results, driver=driver_id, limit=1
        )
        wins_fut = executor.submit(
            safe_ergast_call,
            ergast.get_race_results,
            driver=driver_id,
            results_position=1,
            limit=1,
        )
        p2_fut = executor.submit(
            safe_ergast_call,
            ergast.get_race_results,
            driver=driver_id,
            results_position=2,
            limit=1,
        )
        p3_fut = executor.submit(
            safe_ergast_call,
            ergast.get_race_results,
            driver=driver_id,
            results_position=3,
            limit=1,
        )
        poles_fut = executor.submit(
            safe_ergast_call,
            ergast.get_qualifying_results,
            driver=driver_id,
            results_position=1,
            limit=1,
        )
        fl_fut = executor.submit(
            safe_ergast_call,
            ergast.get_race_results,
            driver=driver_id,
            fastest_rank=1,
            limit=1,
        )
        seasons_fut = executor.submit(
            safe_ergast_call, ergast.get_seasons, driver=driver_id, limit=100
        )

    # 1. Driver info
    try:
        info_res = info_fut.result()
        if info_res.empty:
            return error_response(f"Driver '{driver_id}' not found.", 404)
        info_row = info_res.iloc[0]
    except Exception as e:
        return error_response(
            f"Could not retrieve info for driver '{driver_id}': {str(e)}", 404
        )

    # 2. Race starts, wins, podiums
    starts = _safe_int(getattr(starts_fut.result(), "total_results", 0))
    wins = _safe_int(getattr(wins_fut.result(), "total_results", 0))
    p2 = _safe_int(getattr(p2_fut.result(), "total_results", 0))
    p3 = _safe_int(getattr(p3_fut.result(), "total_results", 0))
    podiums = wins + p2 + p3

    # 3. Poles (wrap in try/except fallback for pre-1994 or missing)
    try:
        poles = _safe_int(getattr(poles_fut.result(), "total_results", 0))
    except Exception:
        poles = 0

    # 4. Fastest laps
    try:
        fastest_laps = _safe_int(getattr(fl_fut.result(), "total_results", 0))
    except Exception:
        fastest_laps = 0

    # 5. Seasons
    seasons_count = 0
    first_season = None
    latest_season = None
    try:
        seasons_res = seasons_fut.result()
        if not seasons_res.empty and "season" in seasons_res.columns:
            seasons_count = len(seasons_res)
            first_season = _safe_int(seasons_res["season"].min(), None)
            latest_season = _safe_int(seasons_res["season"].max(), None)
    except Exception:
        pass

    driver_name = f"{_safe_str(info_row.get('givenName'))} {_safe_str(info_row.get('familyName'))}".strip()
    driver_code = _safe_str(info_row.get("driverCode"))
    if not driver_code:
        driver_code = _safe_str(info_row.get("familyName", "??"))[:3].upper()

    dob_raw = _safe_str(info_row.get("dateOfBirth"))
    date_of_birth = dob_raw.split()[0] if dob_raw else ""

    return (
        jsonify(
            {
                "driver_id": driver_id,
                "driver_name": driver_name,
                "driver_code": driver_code,
                "driver_number": _safe_str(info_row.get("driverNumber", "??")),
                "nationality": _safe_str(info_row.get("driverNationality")),
                "date_of_birth": date_of_birth,
                "career_starts": starts,
                "career_wins": wins,
                "career_podiums": podiums,
                "career_poles": poles,
                "career_fastest_laps": fastest_laps,
                "seasons_count": seasons_count,
                "first_season": first_season,
                "latest_season": latest_season,
            }
        ),
        200,
    )
