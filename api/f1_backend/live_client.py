from datetime import datetime, timezone
import json
import logging
import os
import threading
import time
import urllib.parse

import requests
from fastf1.exceptions import F1AuthError
from fastf1.internals.f1account import get_token, token_manager
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect as ws_connect

from .utils import get_historical_team_color

logger = logging.getLogger(__name__)

NEGOTIATE_URL = "https://livetiming.formula1.com/signalrcore/negotiate"
SIGNALR_URL = "wss://livetiming.formula1.com/signalrcore"

LIVE_TOPICS = [
    "SessionInfo",
    "SessionStatus",
    "ExtrapolatedClock",
    "LapCount",
    "TrackStatus",
    "WeatherData",
    "DriverList",
    "TimingData",
    "TimingAppData",
    "TimingStats",
    "RaceControlMessages",
]

TRACK_STATUS_MAP = {
    "1": ("GREEN", "Track Clear"),
    "2": ("YELLOW", "Yellow Flag"),
    "4": ("SC", "Safety Car"),
    "5": ("RED", "Red Flag"),
    "6": ("VSC", "Virtual Safety Car"),
    "7": ("VSC_ENDING", "VSC Ending"),
}

_FINALIZED_STATUSES = {"Finalised", "Ends", "Finished", "Inactive"}
_LIVE_CACHE_TTL = 3.5
_IDLE_CACHE_TTL = 15.0


class LiveAuthError(Exception):
    """Raised when Formula 1 live timing authentication fails or is unavailable."""


class LiveUpstreamError(Exception):
    """Raised when the Formula 1 SignalR upstream times out or returns invalid data."""


class SnapshotCache:
    """Thread-safe in-memory cache for coalescing burst live timing snapshot requests."""

    def __init__(
        self,
        live_ttl: float = _LIVE_CACHE_TTL,
        idle_ttl: float = _IDLE_CACHE_TTL,
    ):
        self._lock = threading.Lock()
        self._live_ttl = live_ttl
        self._idle_ttl = idle_ttl
        self._timestamp: float = 0.0
        self._data: dict | None = None

    def _effective_ttl(self, raw: dict) -> float:
        status = ""
        session_status = raw.get("SessionStatus")
        if isinstance(session_status, dict):
            status = str(session_status.get("Status") or "").strip()
        if not status:
            session_info = raw.get("SessionInfo")
            if isinstance(session_info, dict):
                status = str(session_info.get("SessionStatus") or "").strip()
        clock = raw.get("ExtrapolatedClock")
        extrapolating = (
            bool(clock.get("Extrapolating")) if isinstance(clock, dict) else False
        )
        if status in ("Started", "Aborted") or (
            extrapolating and status not in _FINALIZED_STATUSES
        ):
            return self._live_ttl
        return self._idle_ttl

    def get(self) -> dict | None:
        with self._lock:
            if self._data is None:
                return None
            ttl = self._effective_ttl(self._data)
            if (time.monotonic() - self._timestamp) < ttl:
                return self._data
            return None

    def set(self, data: dict) -> None:
        with self._lock:
            self._data = data
            self._timestamp = time.monotonic()

    def clear(self) -> None:
        with self._lock:
            self._data = None
            self._timestamp = 0.0


_snapshot_cache = SnapshotCache()
_fetch_lock = threading.Lock()


def clear_cache() -> None:
    """Clear the in-memory live snapshot cache (primarily for tests)."""
    _snapshot_cache.clear()


def has_f1_credentials() -> bool:
    """Return True if F1 credentials or a cached F1 auth token exist."""
    if os.environ.get("F1_USERNAME") and os.environ.get("F1_PASSWORD"):
        return True
    try:
        token_path = getattr(token_manager, "_token_path", None)
        return bool(token_path and os.path.isfile(token_path))
    except Exception:
        return False


def _get_auth_token(force_renew: bool = False) -> str:
    """Obtain the F1TV subscription JWT without logging or exposing secrets."""
    try:
        tok = get_token(force_renew=force_renew)
    except F1AuthError as exc:
        raise LiveAuthError(
            "Formula 1 account authentication failed or is not configured."
        ) from exc
    except Exception as exc:
        raise LiveAuthError(
            "Formula 1 account authentication failed or is not configured."
        ) from exc

    value = getattr(tok, "value", None)
    if not value:
        raise LiveAuthError(
            "Formula 1 account authentication failed or is not configured."
        )
    return value


def _fetch_once(token_value: str, timeout: float) -> dict:
    """Execute one synchronous SignalR Core negotiate -> Subscribe -> snapshot cycle."""
    sess = requests.Session()
    try:
        sess.options(NEGOTIATE_URL, timeout=min(5.0, timeout))
        r_neg = sess.post(
            f"{NEGOTIATE_URL}?negotiateVersion=1",
            headers={
                "Authorization": f"Bearer {token_value}",
                "Content-Type": "application/json",
            },
            timeout=min(5.0, timeout),
        )
    except requests.RequestException as exc:
        raise LiveUpstreamError(
            f"SignalR negotiation failed: {type(exc).__name__}"
        ) from exc

    if r_neg.status_code != 200:
        raise LiveUpstreamError(
            f"SignalR negotiate failed with HTTP {r_neg.status_code}"
        )

    try:
        neg = r_neg.json()
    except ValueError as exc:
        raise LiveUpstreamError("Invalid JSON from SignalR negotiate.") from exc

    conn_token = neg.get("connectionToken") or neg.get("connectionId")
    if not conn_token:
        raise LiveUpstreamError("SignalR negotiate response missing connectionToken.")

    ws_url = f"{SIGNALR_URL}?{urllib.parse.urlencode({'id': conn_token})}"
    ws_headers = {"Authorization": f"Bearer {token_value}"}
    if sess.cookies:
        ws_headers["Cookie"] = "; ".join(f"{c.name}={c.value}" for c in sess.cookies)

    try:
        with ws_connect(
            ws_url,
            additional_headers=ws_headers,
            open_timeout=timeout,
            close_timeout=2.0,
            max_size=16 * 1024 * 1024,
        ) as ws:
            ws.send('{"protocol":"json","version":1}\x1e')
            hs_raw = ws.recv(timeout=timeout)
            for frame in str(hs_raw).split("\x1e"):
                if frame.strip():
                    hs = json.loads(frame)
                    if hs.get("error"):
                        raise LiveUpstreamError(
                            f"SignalR handshake error: {hs['error']}"
                        )
                    break

            sub_payload = (
                json.dumps(
                    {
                        "type": 1,
                        "invocationId": "1",
                        "target": "Subscribe",
                        "arguments": [LIVE_TOPICS],
                    }
                )
                + "\x1e"
            )
            ws.send(sub_payload)

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                remaining = max(0.25, deadline - time.monotonic())
                raw_msg = ws.recv(timeout=remaining)
                for frame in str(raw_msg).split("\x1e"):
                    if not frame.strip():
                        continue
                    parsed = json.loads(frame)
                    if (
                        parsed.get("type") == 3
                        and str(parsed.get("invocationId")) == "1"
                    ):
                        if parsed.get("error"):
                            raise LiveUpstreamError(
                                f"SignalR Subscribe error: {parsed['error']}"
                            )
                        result = parsed.get("result")
                        if isinstance(result, dict) and result:
                            return result
                        raise LiveUpstreamError(
                            "Empty snapshot received from F1 SignalR hub."
                        )

            raise LiveUpstreamError("Timed out waiting for F1 SignalR snapshot.")
    except LiveUpstreamError:
        raise
    except TimeoutError as exc:
        raise LiveUpstreamError("Timed out waiting for F1 SignalR snapshot.") from exc
    except (WebSocketException, OSError, ValueError) as exc:
        raise LiveUpstreamError(
            f"SignalR WebSocket error: {type(exc).__name__}"
        ) from exc


def _is_auth_error_message(message: str) -> bool:
    lowered = message.lower()
    return (
        "401" in lowered
        or "unauthorized" in lowered
        or "forbidden" in lowered
        or "403" in lowered
    )


def fetch_raw_snapshot(timeout: float = 8.0, force_refresh: bool = False) -> dict:
    """Fetch a raw F1 live timing snapshot, using a short-lived in-memory cache."""
    if not force_refresh:
        cached = _snapshot_cache.get()
        if cached is not None:
            return cached

    with _fetch_lock:
        if not force_refresh:
            cached = _snapshot_cache.get()
            if cached is not None:
                return cached

        token_value = _get_auth_token(force_renew=False)
        try:
            data = _fetch_once(token_value, timeout=timeout)
        except LiveUpstreamError as exc:
            if _is_auth_error_message(str(exc)):
                token_value = _get_auth_token(force_renew=True)
                try:
                    data = _fetch_once(token_value, timeout=timeout)
                except LiveUpstreamError as retry_exc:
                    if _is_auth_error_message(str(retry_exc)):
                        raise LiveAuthError(
                            "Formula 1 live timing rejected the auth token."
                        ) from retry_exc
                    raise
            else:
                raise

        _snapshot_cache.set(data)
        return data


def _as_indexed_list(val) -> list:
    """Normalize a list or numeric-keyed SignalR dict into an ordered list."""
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        items = [(k, v) for k, v in val.items() if k != "_kf"]
        items.sort(
            key=lambda pair: (
                (0, int(pair[0])) if str(pair[0]).isdigit() else (1, str(pair[0]))
            )
        )
        return [v for _, v in items]
    return []


def _extract_val(field) -> str:
    """Extract a string Value from either a raw scalar or a SignalR {Value: ...} dict."""
    if isinstance(field, dict):
        val = field.get("Value")
        return "" if val is None else str(val)
    if field is None:
        return ""
    return str(field)


def _to_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_int(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _parse_lap_time_seconds(val: str) -> float | None:
    """Parse lap time strings like '1:34.224' or '59.123' into seconds."""
    if not val:
        return None
    text = str(val).strip()
    if not text:
        return None
    try:
        parts = text.split(":")
        if len(parts) == 1:
            secs = float(parts[0])
            return secs if secs > 0 else None
        if len(parts) == 2:
            secs = int(parts[0]) * 60 + float(parts[1])
            return secs if secs > 0 else None
        if len(parts) == 3:
            secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            return secs if secs > 0 else None
    except (TypeError, ValueError):
        return None
    return None


def _sanitize_team_color(raw_color, team_name: str) -> str:
    if raw_color:
        cleaned = str(raw_color).strip().lstrip("#")
        if len(cleaned) == 6 and cleaned.lower() not in ("nan", "none", "null"):
            return cleaned.upper()
    if team_name:
        return get_historical_team_color(team_name)
    return "777777"


def _resolve_gap_and_interval(
    td: dict, session_part: int | None, position: int | None
) -> tuple[str, str, bool]:
    """Extract (gap, interval, catching) across Race, Qualifying, and Practice schemas."""
    gap = _extract_val(td.get("GapToLeader"))
    raw_interval = td.get("IntervalToPositionAhead")
    interval = _extract_val(raw_interval)
    catching = (
        bool(raw_interval.get("Catching")) if isinstance(raw_interval, dict) else False
    )

    if position == 1:
        if not gap or gap.upper().startswith("LAP "):
            return "LEADER", "", False
        if interval.upper().startswith("LAP "):
            interval = ""

    if not gap and not interval:
        stats = _as_indexed_list(td.get("Stats"))
        chosen_stat = None
        if stats:
            knocked_out = bool(td.get("KnockedOut", False))
            if (
                not knocked_out
                and session_part
                and 1 <= session_part <= len(stats)
                and isinstance(stats[session_part - 1], dict)
            ):
                chosen_stat = stats[session_part - 1]
            else:
                best_lap_times = _as_indexed_list(td.get("BestLapTimes"))
                best_idx = None
                for idx, entry in enumerate(best_lap_times):
                    if isinstance(entry, dict) and entry.get("Value"):
                        best_idx = idx
                if (
                    best_idx is not None
                    and best_idx < len(stats)
                    and isinstance(stats[best_idx], dict)
                ):
                    chosen_stat = stats[best_idx]
            if chosen_stat is None:
                for entry in reversed(stats):
                    if isinstance(entry, dict) and (
                        entry.get("TimeDiffToFastest")
                        or entry.get("TimeDifftoPositionAhead")
                        or entry.get("TimeDiffToPositionAhead")
                    ):
                        chosen_stat = entry
                        break
        if chosen_stat:
            gap = str(chosen_stat.get("TimeDiffToFastest") or "")
            interval = str(
                chosen_stat.get("TimeDifftoPositionAhead")
                or chosen_stat.get("TimeDiffToPositionAhead")
                or ""
            )

    if not gap and not interval:
        gap = _extract_val(td.get("TimeDiffToFastest"))
        interval = _extract_val(
            td.get("TimeDifftoPositionAhead") or td.get("TimeDiffToPositionAhead")
        )

    if position == 1 and not gap:
        gap = "LEADER"

    return gap, interval, catching


def _normalize_sectors(raw_sectors) -> list[dict]:
    sectors = []
    for sec in _as_indexed_list(raw_sectors)[:3]:
        if not isinstance(sec, dict):
            continue
        segments = [
            _to_int(seg.get("Status")) or 0
            for seg in _as_indexed_list(sec.get("Segments"))
            if isinstance(seg, dict)
        ]
        sectors.append(
            {
                "value": str(sec.get("Value") or ""),
                "previous_value": str(sec.get("PreviousValue") or ""),
                "overall_fastest": bool(sec.get("OverallFastest", False)),
                "personal_fastest": bool(sec.get("PersonalFastest", False)),
                "stopped": bool(sec.get("Stopped", False)),
                "segments": segments,
            }
        )
    return sectors


def _normalize_stints(raw_stints) -> list[dict]:
    stints = []
    for st in _as_indexed_list(raw_stints):
        if not isinstance(st, dict):
            continue
        compound = str(st.get("Compound") or "UNKNOWN").strip().upper() or "UNKNOWN"
        stints.append(
            {
                "compound": compound,
                "total_laps": _to_int(st.get("TotalLaps")) or 0,
                "start_laps": _to_int(st.get("StartLaps")) or 0,
                "is_new": str(st.get("New", "")).strip().lower() == "true",
            }
        )
    return stints


def normalize_snapshot(raw: dict, fetched_at: str | None = None) -> dict:
    """Normalize a raw F1 SignalR snapshot dict into F1 PitWall's live JSON contract."""
    raw = raw if isinstance(raw, dict) else {}

    session_info = (
        raw.get("SessionInfo") if isinstance(raw.get("SessionInfo"), dict) else {}
    )
    meeting = (
        session_info.get("Meeting")
        if isinstance(session_info.get("Meeting"), dict)
        else {}
    )
    country = meeting.get("Country") if isinstance(meeting.get("Country"), dict) else {}
    circuit = meeting.get("Circuit") if isinstance(meeting.get("Circuit"), dict) else {}

    session_status_obj = (
        raw.get("SessionStatus") if isinstance(raw.get("SessionStatus"), dict) else {}
    )
    session_status = (
        str(session_status_obj.get("Status") or "").strip()
        or str(session_info.get("SessionStatus") or "").strip()
        or "Unknown"
    )

    clock_obj = (
        raw.get("ExtrapolatedClock")
        if isinstance(raw.get("ExtrapolatedClock"), dict)
        else {}
    )
    extrapolating = bool(clock_obj.get("Extrapolating", False))
    is_live = session_status in ("Started", "Aborted") or (
        extrapolating and session_status not in _FINALIZED_STATUSES
    )

    timing_data = (
        raw.get("TimingData") if isinstance(raw.get("TimingData"), dict) else {}
    )
    session_part = _to_int(timing_data.get("SessionPart"))

    lap_count_obj = raw.get("LapCount")
    lap_count = None
    if isinstance(lap_count_obj, dict):
        cur_lap = _to_int(lap_count_obj.get("CurrentLap"))
        tot_lap = _to_int(lap_count_obj.get("TotalLaps"))
        if cur_lap is not None or tot_lap is not None:
            lap_count = {"current_lap": cur_lap, "total_laps": tot_lap}

    session = {
        "meeting_name": meeting.get("Name") or "",
        "official_name": meeting.get("OfficialName") or "",
        "location": meeting.get("Location") or "",
        "country": country.get("Name") or "",
        "circuit": circuit.get("ShortName") or "",
        "round_number": _to_int(meeting.get("Number")),
        "session_name": session_info.get("Name") or "",
        "session_type": session_info.get("Type") or "",
        "session_key": _to_int(session_info.get("Key")),
        "path": session_info.get("Path") or "",
        "session_status": session_status,
        "is_live": is_live,
        "session_part": session_part,
        "gmt_offset": str(session_info.get("GmtOffset") or ""),
        "start_date": str(session_info.get("StartDate") or ""),
        "end_date": str(session_info.get("EndDate") or ""),
        "clock": {
            "remaining": str(clock_obj.get("Remaining") or ""),
            "extrapolating": extrapolating,
            "utc": str(clock_obj.get("Utc") or ""),
        },
        "lap_count": lap_count,
    }

    ts_obj = raw.get("TrackStatus") if isinstance(raw.get("TrackStatus"), dict) else {}
    raw_ts = str(ts_obj.get("Status") or "1").strip()
    ts_code, ts_label = TRACK_STATUS_MAP.get(
        raw_ts, ("UNKNOWN", str(ts_obj.get("Message") or "Unknown"))
    )
    track_status = {
        "code": ts_code,
        "label": ts_label,
        "raw_status": raw_ts,
        "message": str(ts_obj.get("Message") or ts_label),
    }

    w_obj = raw.get("WeatherData") if isinstance(raw.get("WeatherData"), dict) else {}
    weather = {
        "air_temp": _to_float(w_obj.get("AirTemp")),
        "track_temp": _to_float(w_obj.get("TrackTemp")),
        "humidity": _to_float(w_obj.get("Humidity")),
        "pressure": _to_float(w_obj.get("Pressure")),
        "wind_speed": _to_float(w_obj.get("WindSpeed")),
        "wind_direction": _to_int(w_obj.get("WindDirection")),
        "rainfall": str(w_obj.get("Rainfall", "0")).strip().lower()
        not in ("0", "", "false", "none"),
    }

    driver_list = (
        raw.get("DriverList") if isinstance(raw.get("DriverList"), dict) else {}
    )
    td_lines = (
        timing_data.get("Lines") if isinstance(timing_data.get("Lines"), dict) else {}
    )
    timing_app = (
        raw.get("TimingAppData") if isinstance(raw.get("TimingAppData"), dict) else {}
    )
    ta_lines = (
        timing_app.get("Lines") if isinstance(timing_app.get("Lines"), dict) else {}
    )
    timing_stats = (
        raw.get("TimingStats") if isinstance(raw.get("TimingStats"), dict) else {}
    )
    ts_lines = (
        timing_stats.get("Lines") if isinstance(timing_stats.get("Lines"), dict) else {}
    )

    all_numbers = {
        str(k)
        for k in (*td_lines.keys(), *driver_list.keys())
        if str(k) != "_kf" and str(k).strip()
    }

    standings = []
    for num in all_numbers:
        dl = driver_list.get(num) if isinstance(driver_list.get(num), dict) else {}
        td = td_lines.get(num) if isinstance(td_lines.get(num), dict) else {}
        ta = ta_lines.get(num) if isinstance(ta_lines.get(num), dict) else {}
        tstat = ts_lines.get(num) if isinstance(ts_lines.get(num), dict) else {}

        position = (
            _to_int(td.get("Position"))
            or _to_int(td.get("Line"))
            or _to_int(dl.get("Line"))
        )
        team_name = str(dl.get("TeamName") or "").strip()
        team_color = _sanitize_team_color(dl.get("TeamColour"), team_name)

        gap, interval, catching = _resolve_gap_and_interval(td, session_part, position)

        best_lap_obj = td.get("BestLapTime")
        best_lap_time = _extract_val(best_lap_obj)
        best_lap_number = (
            _to_int(best_lap_obj.get("Lap")) if isinstance(best_lap_obj, dict) else None
        )

        last_lap_obj = td.get("LastLapTime")
        last_lap_time = _extract_val(last_lap_obj)
        last_lap_overall = (
            bool(last_lap_obj.get("OverallFastest", False))
            if isinstance(last_lap_obj, dict)
            else False
        )
        last_lap_personal = (
            bool(last_lap_obj.get("PersonalFastest", False))
            if isinstance(last_lap_obj, dict)
            else False
        )

        q_times = [
            {
                "part": idx + 1,
                "value": _extract_val(item),
                "lap": _to_int(item.get("Lap")) if isinstance(item, dict) else None,
            }
            for idx, item in enumerate(_as_indexed_list(td.get("BestLapTimes")))
        ]

        speeds_obj = td.get("Speeds") if isinstance(td.get("Speeds"), dict) else {}
        speeds = {
            "i1": _extract_val(speeds_obj.get("I1")),
            "i2": _extract_val(speeds_obj.get("I2")),
            "fl": _extract_val(speeds_obj.get("FL")),
            "st": _extract_val(speeds_obj.get("ST")),
        }

        stints = _normalize_stints(ta.get("Stints"))
        current_stint = stints[-1] if stints else None
        compound = current_stint["compound"] if current_stint else "UNKNOWN"
        tyre_age = current_stint["total_laps"] if current_stint else 0
        tyre_new = current_stint["is_new"] if current_stint else False

        pit_stops = _to_int(td.get("NumberOfPitStops"))
        if pit_stops is None:
            pit_stops = max(0, len(stints) - 1) if stints else 0

        tla = str(dl.get("Tla") or "").strip() or num
        full_name = (
            str(dl.get("FullName") or "").strip()
            or str(dl.get("BroadcastName") or "").strip()
            or num
        )
        first_name = str(dl.get("FirstName") or "").strip()
        last_name = str(dl.get("LastName") or "").strip()

        best_sectors = [
            {
                "value": str(bs.get("Value") or "").strip(),
                "position": _to_int(bs.get("Position")),
                "overall_fastest": _to_int(bs.get("Position")) == 1,
            }
            for bs in _as_indexed_list(tstat.get("BestSectors"))[:3]
            if isinstance(bs, dict)
        ]

        standings.append(
            {
                "driver_number": num,
                "abbreviation": tla,
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "team_name": team_name,
                "team_color": team_color,
                "position": position,
                "line": _to_int(td.get("Line")) or _to_int(dl.get("Line")),
                "gap": gap,
                "interval": interval,
                "catching": catching,
                "best_lap_time": best_lap_time,
                "best_lap_number": best_lap_number,
                "last_lap_time": last_lap_time,
                "last_lap_overall_fastest": last_lap_overall,
                "last_lap_personal_fastest": last_lap_personal,
                "q_times": q_times,
                "sectors": _normalize_sectors(td.get("Sectors")),
                "best_sectors": best_sectors,
                "speeds": speeds,
                "number_of_laps": _to_int(td.get("NumberOfLaps")),
                "compound": compound,
                "tyre_age": tyre_age,
                "tyre_new": tyre_new,
                "stints": stints,
                "pit_stops": pit_stops,
                "in_pit": bool(td.get("InPit", False)),
                "pit_out": bool(td.get("PitOut", False)),
                "retired": bool(td.get("Retired", False)),
                "stopped": bool(td.get("Stopped", False)),
                "did_not_start": False,
                "knocked_out": bool(td.get("KnockedOut", False)),
                "cutoff": bool(td.get("Cutoff", False)),
                "has_fastest_lap": False,
            }
        )

    standings.sort(
        key=lambda d: (
            d["position"] if d["position"] is not None else 999,
            d["line"] if d["line"] is not None else 999,
            int(d["driver_number"]) if d["driver_number"].isdigit() else 999,
        )
    )

    fastest_num = None
    fastest_secs = None
    for row in standings:
        secs = _parse_lap_time_seconds(row["best_lap_time"])
        if secs is not None and (fastest_secs is None or secs < fastest_secs):
            fastest_secs = secs
            fastest_num = row["driver_number"]
    if fastest_num is not None:
        for row in standings:
            row["has_fastest_lap"] = row["driver_number"] == fastest_num

    is_race_like = (session["session_type"] or "").lower() in ("race", "sprint")
    race_started = bool(
        (lap_count and (lap_count.get("current_lap") or 0) >= 1)
        or any((row.get("number_of_laps") or 0) > 0 for row in standings)
        or session_status in _FINALIZED_STATUSES
    )
    if is_race_like and race_started:
        for row in standings:
            if (
                (row["retired"] or row["stopped"])
                and (row["number_of_laps"] is None or row["number_of_laps"] == 0)
                and not row["best_lap_time"]
                and not row["last_lap_time"]
                and not row["gap"]
            ):
                row["did_not_start"] = True

    rcm_obj = (
        raw.get("RaceControlMessages")
        if isinstance(raw.get("RaceControlMessages"), dict)
        else {}
    )
    rc_raw = _as_indexed_list(rcm_obj.get("Messages"))
    race_control = [
        {
            "utc": str(msg.get("Utc") or ""),
            "category": str(msg.get("Category") or ""),
            "flag": str(msg.get("Flag") or ""),
            "scope": str(msg.get("Scope") or ""),
            "sector": _to_int(msg.get("Sector")),
            "lap": _to_int(msg.get("Lap")),
            "message": str(msg.get("Message") or ""),
        }
        for msg in reversed(rc_raw)
        if isinstance(msg, dict)
    ]

    best_sectors_summary = []
    for s_idx in range(3):
        winner = None
        best_pos_one = None
        min_secs = None
        for row in standings:
            bs_list = row.get("best_sectors") or []
            if s_idx >= len(bs_list):
                continue
            bs = bs_list[s_idx]
            val = bs.get("value") or ""
            if not val:
                continue
            if bs.get("position") == 1 and best_pos_one is None:
                best_pos_one = (row, val)
            secs = _parse_lap_time_seconds(val)
            if secs is not None and (min_secs is None or secs < min_secs):
                min_secs = secs
                winner = (row, val)
        chosen = best_pos_one or winner
        if chosen is not None:
            w_row, w_val = chosen
            best_sectors_summary.append(
                {
                    "sector": s_idx + 1,
                    "driver_number": w_row["driver_number"],
                    "abbreviation": w_row["abbreviation"],
                    "team_color": w_row["team_color"],
                    "value": w_val,
                }
            )

    return {
        "session": session,
        "track_status": track_status,
        "weather": weather,
        "standings": standings,
        "best_sectors": best_sectors_summary,
        "race_control": race_control,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
    }
