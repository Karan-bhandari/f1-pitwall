import datetime
import math
import sys
import traceback
from flask import Blueprint, request, jsonify
import fastf1
import pandas as pd
from ..utils import (
    validate_year,
    error_response,
    get_historical_team_color,
    safe_int as _safe_int,
    safe_float as _safe_float,
    first_str,
)

standings_bp = Blueprint("standings", __name__)


def calculate_schedule_progress(year, ds_round, current_year=None, schedule=None):
    """Calculate season schedule progress using fastf1 event schedule.

    Filters to championship rounds (RoundNumber > 0).
    For past seasons (year < current_year): remaining_rounds = 0, remaining_sprints = 0.
    For current/future seasons (year >= current_year): remaining_rounds = max(0, total_rounds - completed_rounds),
    and counts remaining sprint formats.
    """
    if current_year is None:
        current_year = datetime.datetime.now().year

    completed_rounds = ds_round if ds_round is not None else 0
    total_rounds = 0
    remaining_rounds = 0
    remaining_sprints = 0
    next_round_name = None
    next_round_is_sprint = False

    if schedule is None:
        try:
            schedule = fastf1.get_event_schedule(year, include_testing=False)
        except Exception:
            schedule = None

    if (
        schedule is not None
        and not schedule.empty
        and "RoundNumber" in schedule.columns
    ):
        champ_events = schedule[schedule["RoundNumber"] > 0]
        total_rounds = len(champ_events)

    if total_rounds == 0 and completed_rounds > 0:
        total_rounds = completed_rounds

    if year < current_year:
        remaining_rounds = 0
        remaining_sprints = 0
    else:
        remaining_rounds = max(0, total_rounds - completed_rounds)
        if (
            schedule is not None
            and not schedule.empty
            and "RoundNumber" in schedule.columns
            and "EventFormat" in schedule.columns
        ):
            upcoming = schedule[schedule["RoundNumber"] > completed_rounds]
            remaining_sprints = int(
                upcoming["EventFormat"]
                .astype(str)
                .str.lower()
                .str.contains("sprint", na=False)
                .sum()
            )

            if remaining_rounds > 0:
                next_event = schedule[schedule["RoundNumber"] == completed_rounds + 1]
                if not next_event.empty:
                    next_round_name = str(next_event.iloc[0].get("EventName", ""))
                    next_fmt = str(next_event.iloc[0].get("EventFormat", "")).lower()
                    next_round_is_sprint = "sprint" in next_fmt

    return {
        "total_rounds": total_rounds,
        "completed_rounds": completed_rounds,
        "remaining_rounds": remaining_rounds,
        "remaining_sprints": remaining_sprints,
        "next_round_name": next_round_name,
        "next_round_is_sprint": next_round_is_sprint,
    }


def get_era_points_breakdown(year):
    """Return max points per GP and Sprint for drivers and constructors based on F1 era.

    - 2019..2024: Driver GP max 26 (25 + 1 Fastest Lap). Constructor GP max 44 (25 + 18 + 1).
    - 2025+: Fastest lap point abolished. Driver GP max 25, Constructor GP max 43.
    - 2010..2018: Driver GP max 25, Constructor GP max 43.
    - Sprints: 2022+ is 8 pts (Driver) / 15 pts (Constructor). 2021 is 3 pts (Driver) / 5 pts (Constructor).
    """
    if 2019 <= year <= 2024:
        driver_gp = 26
        constructor_gp = 44
    else:
        driver_gp = 25
        constructor_gp = 43

    if year >= 2022:
        driver_sprint = 8
        constructor_sprint = 15
    elif year == 2021:
        driver_sprint = 3
        constructor_sprint = 5
    else:
        driver_sprint = 0
        constructor_sprint = 0

    return {
        "driver_gp": driver_gp,
        "driver_sprint": driver_sprint,
        "constructor_gp": constructor_gp,
        "constructor_sprint": constructor_sprint,
    }


def get_era_max_points(year, remaining_rounds, remaining_sprints):
    """Era-accurate maximum points remaining for drivers and constructors."""
    if remaining_rounds <= 0:
        return 0, 0

    bd = get_era_points_breakdown(year)
    max_driver = (remaining_rounds * bd["driver_gp"]) + (
        remaining_sprints * bd["driver_sprint"]
    )
    max_constructor = (remaining_rounds * bd["constructor_gp"]) + (
        remaining_sprints * bd["constructor_sprint"]
    )
    return max_driver, max_constructor


def enrich_standings(standings, max_remaining_points, remaining_rounds):
    """Enrich driver or constructor standings with gap_to_leader, interval,

    mathematically_eligible, and is_champion.
    """
    if not standings:
        return []

    enriched = []
    leader_points = standings[0].get("points", 0.0)
    leader_wins = standings[0].get("wins", 0)

    for i, item in enumerate(standings):
        entry = dict(item)
        pos = entry.get("position", i + 1)
        points = entry.get("points", 0.0)
        wins = entry.get("wins", 0)

        if pos == 1 or i == 0:
            entry["gap_to_leader"] = 0.0
            entry["interval"] = 0.0
            entry["mathematically_eligible"] = True
        else:
            prev_points = standings[i - 1].get("points", 0.0)
            entry["gap_to_leader"] = round(float(leader_points - points), 1)
            entry["interval"] = round(float(prev_points - points), 1)

            if remaining_rounds == 0:
                entry["mathematically_eligible"] = False
            else:
                max_possible = points + max_remaining_points
                if max_possible > leader_points:
                    entry["mathematically_eligible"] = True
                elif max_possible == leader_points and (
                    wins + remaining_rounds >= leader_wins
                ):
                    entry["mathematically_eligible"] = True
                else:
                    entry["mathematically_eligible"] = False

        entry["is_champion"] = False
        enriched.append(entry)

    # is_champion: True for P1 iff len(standings) > 0 and
    # (remaining_rounds == 0 or no P2+ entry has mathematically_eligible == True)
    has_other_eligible = any(
        e.get("mathematically_eligible", False) for e in enriched[1:]
    )
    p1_is_champion = (len(enriched) > 0) and (
        remaining_rounds == 0 or not has_other_eligible
    )

    if enriched:
        enriched[0]["is_champion"] = p1_is_champion

    return enriched


def extract_champion(enriched_standings, remaining_rounds, is_driver=True):
    """Extract top-level champion dict for WDC or WCC if crowned."""
    if not enriched_standings:
        return None
    p1 = enriched_standings[0]
    if not p1.get("is_champion"):
        return None

    clinched_early = remaining_rounds > 0
    rounds_to_spare = remaining_rounds

    if is_driver:
        return {
            "driver_code": p1.get("driver_code", ""),
            "driver_name": p1.get("driver_name", ""),
            "team_name": p1.get("team_name", ""),
            "team_color": p1.get("team_color", "e10600"),
            "points": p1.get("points", 0.0),
            "wins": p1.get("wins", 0),
            "clinched_early": clinched_early,
            "rounds_to_spare": rounds_to_spare,
        }
    else:
        return {
            "constructor_name": p1.get("constructor_name", ""),
            "constructor_id": p1.get("constructor_id", ""),
            "team_color": p1.get("team_color", "e10600"),
            "points": p1.get("points", 0.0),
            "wins": p1.get("wins", 0),
            "clinched_early": clinched_early,
            "rounds_to_spare": rounds_to_spare,
        }


def build_entity_scenarios(
    standings,
    max_remaining_points,
    remaining_rounds,
    remaining_sprints,
    next_round_name,
    next_round_is_sprint,
    year,
    is_driver=True,
):
    """Build detailed mathematical scenarios for WDC or WCC."""
    if not standings:
        return None

    clinched = bool(standings[0].get("is_champion", False))
    eligible = [s for s in standings if s.get("mathematically_eligible", False)]
    contenders_count = len(eligible)
    total_competitors = len(standings)

    if not eligible:
        return {
            "clinched": clinched,
            "contenders_count": 0,
            "total_competitors": total_competitors,
            "contenders": [],
        }

    p1 = eligible[0]
    p1_code = p1.get("driver_code" if is_driver else "constructor_name", "P1")
    p1_points = p1.get("points", 0.0)
    p1_wins = p1.get("wins", 0)

    bd = get_era_points_breakdown(year)
    gp_pts = bd["driver_gp"] if is_driver else bd["constructor_gp"]
    sprint_pts = bd["driver_sprint"] if is_driver else bd["constructor_sprint"]
    dnf_divisor = 25 if is_driver else 43

    if contenders_count > 1:
        p2 = eligible[1]
        p2_code = p2.get("driver_code" if is_driver else "constructor_name", "P2")
        p2_points = p2.get("points", 0.0)
        p2_wins = p2.get("wins", 0)
        p2_max = round(p2_points + max_remaining_points, 1)

        # Points P1 needs to guarantee the championship
        points_needed_to_clinch = max(0.0, round(p2_max - p1_points + 1, 1))

        # Check if P1 can clinch at next round
        next_round_max = gp_pts + (sprint_pts if next_round_is_sprint else 0)
        remaining_rounds_after = max(0, remaining_rounds - 1)
        remaining_sprints_after = max(
            0, remaining_sprints - (1 if next_round_is_sprint else 0)
        )
        max_pts_after = (remaining_rounds_after * gp_pts) + (
            remaining_sprints_after * sprint_pts
        )

        p1_next_max = p1_points + next_round_max
        p2_future_max = p2_points + max_pts_after

        can_clinch_next_round = bool(
            p1_next_max > p2_future_max
            or (
                p1_next_max == p2_future_max
                and (p1_wins + 1 > p2_wins + remaining_rounds_after)
            )
        )

        if can_clinch_next_round:
            diff = max_pts_after - (p1_points - p2_points)
            margin = max(1, int(round(diff + 1)))
            round_label = (
                f" at {next_round_name}" if next_round_name else " at the next round"
            )
            p1_scenario = f"Can clinch the championship{round_label} if {p1_code} outscores {p2_code} by {margin} pts."
        else:
            pts_str = (
                int(points_needed_to_clinch)
                if points_needed_to_clinch == int(points_needed_to_clinch)
                else points_needed_to_clinch
            )
            p1_scenario = f"Needs {pts_str} pts across the final {remaining_rounds} rounds to guarantee the championship."
    else:
        points_needed_to_clinch = 0.0
        can_clinch_next_round = False
        p1_scenario = "Championship mathematically clinched!"

    contenders = []
    for item in eligible:
        pos = item.get("position", 1)
        name = item.get("driver_name" if is_driver else "constructor_name", "")
        code = item.get("driver_code" if is_driver else "constructor_name", "")
        team = item.get("team_name", name)
        color = item.get("team_color", "e10600")
        pts = item.get("points", 0.0)
        wins = item.get("wins", 0)
        gap = item.get("gap_to_leader", 0.0)
        max_pos = round(pts + max_remaining_points, 1)

        if pos == 1:
            contenders.append(
                {
                    "position": 1,
                    "name": name,
                    "code": code,
                    "team_name": team,
                    "team_color": color,
                    "points": pts,
                    "wins": wins,
                    "gap_to_leader": gap,
                    "max_possible_points": max_pos,
                    "points_needed_to_clinch": points_needed_to_clinch,
                    "can_clinch_next_round": can_clinch_next_round,
                    "scenario_text": p1_scenario,
                }
            )
        else:
            swing = round(gap / remaining_rounds, 1) if remaining_rounds > 0 else 0.0
            dnfs = math.ceil(gap / dnf_divisor) if gap > 0 else 0
            p2_scenario = (
                f"Needs +{swing} pts/round over {remaining_rounds} rounds "
                f"(~{dnfs} {p1_code} non-score/DNF equivalents)"
            )
            contenders.append(
                {
                    "position": pos,
                    "name": name,
                    "code": code,
                    "team_name": team,
                    "team_color": color,
                    "points": pts,
                    "wins": wins,
                    "gap_to_leader": gap,
                    "max_possible_points": max_pos,
                    "avg_swing_needed_per_round": swing,
                    "leader_dnfs_equivalent": dnfs,
                    "scenario_text": p2_scenario,
                }
            )

    return {
        "clinched": clinched,
        "contenders_count": contenders_count,
        "total_competitors": total_competitors,
        "contenders": contenders,
    }


def build_championship_scenarios(
    year,
    total_rounds,
    completed_rounds,
    remaining_rounds,
    remaining_sprints,
    next_round_name,
    next_round_is_sprint,
    enriched_drivers,
    enriched_constructors,
    max_driver_points_remaining,
    max_constructor_points_remaining,
    current_year=None,
):
    """Construct top-level championship scenarios dict for second-half title fights.

    Only active when year == current_year, remaining_rounds > 0, completed_rounds >= (total_rounds / 2.0),
    and at least one championship (WDC or WCC) is not yet mathematically clinched.
    """
    if current_year is None:
        current_year = datetime.datetime.now().year

    wdc_scenarios = build_entity_scenarios(
        enriched_drivers,
        max_driver_points_remaining,
        remaining_rounds,
        remaining_sprints,
        next_round_name,
        next_round_is_sprint,
        year,
        is_driver=True,
    )

    wcc_scenarios = build_entity_scenarios(
        enriched_constructors,
        max_constructor_points_remaining,
        remaining_rounds,
        remaining_sprints,
        next_round_name,
        next_round_is_sprint,
        year,
        is_driver=False,
    )

    wdc_clinched = bool(wdc_scenarios and wdc_scenarios.get("clinched"))
    wcc_clinched = bool(wcc_scenarios and wcc_scenarios.get("clinched"))
    at_least_one_not_clinched = (not wdc_clinched) or (
        wcc_scenarios is not None and not wcc_clinched
    )

    is_second_half = bool(
        year == current_year
        and remaining_rounds > 0
        and total_rounds > 0
        and completed_rounds >= (total_rounds / 2.0)
        and at_least_one_not_clinched
    )

    return {
        "is_second_half": is_second_half,
        "total_rounds": total_rounds,
        "completed_rounds": completed_rounds,
        "remaining_rounds": remaining_rounds,
        "remaining_sprints": remaining_sprints,
        "next_round_name": next_round_name,
        "max_driver_points_remaining": max_driver_points_remaining,
        "max_constructor_points_remaining": max_constructor_points_remaining,
        "wdc": wdc_scenarios,
        "wcc": wcc_scenarios,
    }


@standings_bp.route("/standings", methods=["GET"])
def get_standings():
    """Get driver and constructor championship standings for a given season.

    Uses fastf1.ergast to fetch the latest standings for the requested year.
    Returns both WDC and WCC data, championship crowning indicators, and
    second-half clinch scenarios.
    """
    year = request.args.get("year", type=int)
    is_valid, error_msg = validate_year(year)
    if not is_valid:
        return error_response(error_msg)

    try:
        ergast = fastf1.ergast.Ergast()

        # Load event schedule once for both round name and schedule progress
        schedule = None
        try:
            schedule = fastf1.get_event_schedule(year, include_testing=False)
        except Exception:
            schedule = None

        # --- Driver Standings ---
        driver_standings_data = []
        ds_round = None
        ds_round_name = None

        ds_res = ergast.get_driver_standings(season=year, limit=1000)
        if ds_res.content and not ds_res.content[0].empty:
            df = ds_res.content[0]
            ds_round = int(ds_res.description["round"].iloc[0])

            for _, row in df.iterrows():
                team_name = first_str(row.get("constructorNames"), "Unknown")
                team_id = first_str(row.get("constructorIds"), "")

                driver_standings_data.append(
                    {
                        "position": _safe_int(
                            row.get("position"), len(driver_standings_data) + 1
                        ),
                        "driver_code": (
                            str(row.get("driverCode", ""))
                            if pd.notna(row.get("driverCode"))
                            else str(row.get("familyName", "??"))[:3].upper()
                        ),
                        "driver_name": f"{row.get('givenName', '')} {row.get('familyName', '')}".strip(),
                        "team_name": team_name,
                        "team_color": get_historical_team_color(team_id),
                        "points": _safe_float(row.get("points")),
                        "wins": _safe_int(row.get("wins")),
                    }
                )

        # Resolve the round name from the event schedule
        if ds_round is not None and schedule is not None and not schedule.empty:
            try:
                round_event = schedule[schedule["RoundNumber"] == ds_round]
                if not round_event.empty:
                    ds_round_name = str(round_event.iloc[0]["EventName"])
            except Exception:
                pass

        # --- Constructor Standings (WCC started in 1958) ---
        constructor_standings_data = []
        if year >= 1958:
            try:
                cs_res = ergast.get_constructor_standings(season=year, limit=1000)
                if cs_res.content and not cs_res.content[0].empty:
                    df = cs_res.content[0]
                    for _, row in df.iterrows():
                        cid = str(row.get("constructorId", ""))
                        constructor_standings_data.append(
                            {
                                "position": _safe_int(
                                    row.get("position"),
                                    len(constructor_standings_data) + 1,
                                ),
                                "constructor_name": str(
                                    row.get("constructorName", "Unknown")
                                ),
                                "constructor_id": cid,
                                "team_color": get_historical_team_color(cid),
                                "points": _safe_float(row.get("points")),
                                "wins": _safe_int(row.get("wins")),
                            }
                        )
            except Exception as e:
                print(
                    f"[STANDINGS] Error fetching constructor standings: {e}",
                    file=sys.stderr,
                )

        # --- Schedule Progress & Clinch Calculations ---
        progress = calculate_schedule_progress(
            year=year, ds_round=ds_round, schedule=schedule
        )

        max_driver_pts, max_constructor_pts = get_era_max_points(
            year=year,
            remaining_rounds=progress["remaining_rounds"],
            remaining_sprints=progress["remaining_sprints"],
        )

        enriched_drivers = enrich_standings(
            standings=driver_standings_data,
            max_remaining_points=max_driver_pts,
            remaining_rounds=progress["remaining_rounds"],
        )

        enriched_constructors = enrich_standings(
            standings=constructor_standings_data,
            max_remaining_points=max_constructor_pts,
            remaining_rounds=progress["remaining_rounds"],
        )

        wdc_champion = extract_champion(
            enriched_drivers, progress["remaining_rounds"], is_driver=True
        )
        wcc_champion = extract_champion(
            enriched_constructors, progress["remaining_rounds"], is_driver=False
        )

        scenarios = build_championship_scenarios(
            year=year,
            total_rounds=progress["total_rounds"],
            completed_rounds=progress["completed_rounds"],
            remaining_rounds=progress["remaining_rounds"],
            remaining_sprints=progress["remaining_sprints"],
            next_round_name=progress["next_round_name"],
            next_round_is_sprint=progress["next_round_is_sprint"],
            enriched_drivers=enriched_drivers,
            enriched_constructors=enriched_constructors,
            max_driver_points_remaining=max_driver_pts,
            max_constructor_points_remaining=max_constructor_pts,
        )

        return (
            jsonify(
                {
                    "year": year,
                    "round": ds_round,
                    "round_name": ds_round_name,
                    "total_rounds": progress["total_rounds"],
                    "remaining_rounds": progress["remaining_rounds"],
                    "drivers": enriched_drivers,
                    "constructors": enriched_constructors,
                    "wdc_champion": wdc_champion,
                    "wcc_champion": wcc_champion,
                    "scenarios": scenarios,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[STANDINGS] Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return error_response("Failed to fetch standings.", 500)
