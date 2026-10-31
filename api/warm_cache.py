#!/usr/bin/env python3
# To run or resume caching (defaults to 2026 & 2025):
#   .venv/bin/python api/warm_cache.py
#
# To cache a specific year (e.g. 2024):
#   .venv/bin/python api/warm_cache.py --years 2024
"""Resumable FastF1 cache warming script to build a local dataset.

Downloads and caches session timing, laps, stints, and car telemetry into
`api/instance/fastf1_cache/` so the application serves from a pre-populated
local dataset instead of repeatedly querying the upstream F1 APIs.
Automatically skips sessions whose Stage-2 cache files
(`_extended_timing_data.ff1pkl`, `car_data.ff1pkl`, and
`position_data.ff1pkl`) are already present on disk, so interrupted runs
resume immediately.
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

# Ensure `api/` is on sys.path even when invoked without PYTHONPATH=api
API_DIR = os.path.abspath(os.path.dirname(__file__))
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import fastf1
from f1_backend import _load_dotenv

CACHE_DIR = os.path.abspath(os.path.join(API_DIR, "instance", "fastf1_cache"))


def _quiet_loggers():
    """Silence noisy urllib3/requests_cache/fastf1 debug & info logs so only progress prints."""
    fastf1.set_log_level("ERROR")
    root = logging.getLogger()
    root.setLevel(logging.ERROR)
    for h in root.handlers:
        h.setLevel(logging.ERROR)
    for name in list(logging.root.manager.loggerDict.keys()):
        lg = logging.getLogger(name)
        lg.setLevel(logging.ERROR)
        lg.propagate = False


def _session_is_cached(session) -> bool:
    """Return True if this session already has timing, car_data, and position_data .ff1pkl files."""
    try:
        api_path = session.api_path
        rel_path = api_path.replace("/static/", "").strip("/")
        folder = os.path.join(CACHE_DIR, rel_path)
        return (
            os.path.isfile(os.path.join(folder, "_extended_timing_data.ff1pkl"))
            and os.path.isfile(os.path.join(folder, "car_data.ff1pkl"))
            and os.path.isfile(os.path.join(folder, "position_data.ff1pkl"))
        )
    except Exception:
        return False


def warm_round_batch(year: int, start_round: int, end_round: int, force: bool = False):
    """Download and cache a batch of rounds into the local dataset within a single process."""
    _load_dotenv()
    _quiet_loggers()
    os.makedirs(CACHE_DIR, exist_ok=True)
    fastf1.Cache.configure(cache_dir=CACHE_DIR)

    sched = fastf1.get_event_schedule(year, include_testing=False)
    now = datetime.now()
    all_past = sched[sched["EventDate"] <= now]
    total_completed = len(all_past)
    past = all_past[
        (all_past["RoundNumber"] >= start_round)
        & (all_past["RoundNumber"] <= end_round)
    ]

    for _, ev in past.iterrows():
        r_num = int(ev["RoundNumber"])
        ev_name = str(ev["EventName"])
        print(
            f"\n=== [{year} | Round {r_num:02d}/{total_completed:02d}] {ev_name} ===",
            flush=True,
        )
        event_obj = fastf1.get_event(year, r_num)

        for s_idx in range(1, 6):
            try:
                session = event_obj.get_session(s_idx)
                s_name = session.name
                if not force and _session_is_cached(session):
                    print(
                        f"  [SKIP] S{s_idx}/5 {s_name:<18} -> already cached",
                        flush=True,
                    )
                    continue

                print(
                    f"  [LOAD] S{s_idx}/5 {s_name:<18} -> downloading...",
                    end="",
                    flush=True,
                )
                is_quali = any(
                    k in s_name.lower() for k in ["qualifying", "shootout", "qualy"]
                )
                st = time.time()
                session.load(telemetry=True, weather=False, messages=is_quali)
                elapsed = time.time() - st
                laps_cnt = (
                    len(session.laps)
                    if hasattr(session, "laps") and session.laps is not None
                    else 0
                )
                print(
                    f" DONE ({laps_cnt} laps + telemetry in {elapsed:.1f}s)",
                    flush=True,
                )
            except Exception as e:
                print(f" ERROR ({e})", flush=True)


def main():
    """CLI entry point to build or resume the local FastF1 cache dataset."""
    parser = argparse.ArgumentParser(
        description="Build a local FastF1 dataset so the app does not repeatedly query the upstream API."
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2026, 2025],
        help="Season year(s) to cache (default: 2026 2025)",
    )
    parser.add_argument(
        "--start-round",
        type=int,
        default=1,
        help="Starting round number (default: 1)",
    )
    parser.add_argument(
        "--end-round",
        type=int,
        default=30,
        help="Ending round number (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Rounds per subprocess batch to stay under FastF1's 500 calls/process limit (default: 8)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reload sessions even if .ff1pkl files already exist on disk",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.worker:
        warm_round_batch(args.years[0], args.start_round, args.end_round, args.force)
        return

    _load_dotenv()
    _quiet_loggers()
    try:
        from fastf1.internals.f1account import get_token

        tok = get_token()
        rem_min = round((tok.expires_at - time.time()) / 60, 1)
        print(f"Authenticated with Formula 1 account (token valid for {rem_min}m).")
    except Exception as e:
        print(f"Warning: F1 authentication check failed ({e}). Continuing...")

    t0 = time.time()
    print(
        f"Starting FastF1 cache warm-up for years: {', '.join(map(str, args.years))} "
        f"(cache dir: {CACHE_DIR})",
        flush=True,
    )
    for yr in args.years:
        cur = args.start_round
        while cur <= args.end_round:
            b_end = min(cur + args.batch_size - 1, args.end_round)
            cmd = [
                sys.executable,
                "-u",
                os.path.abspath(__file__),
                "--worker",
                "--years",
                str(yr),
                "--start-round",
                str(cur),
                "--end-round",
                str(b_end),
            ]
            if args.force:
                cmd.append("--force")

            env = os.environ.copy()
            env["PYTHONPATH"] = (
                f"{API_DIR}:{env['PYTHONPATH']}" if "PYTHONPATH" in env else API_DIR
            )

            subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, check=False)
            cur = b_end + 1

    print(
        f"\nAll requested seasons completed in {(time.time() - t0) / 60:.1f} minutes.",
        flush=True,
    )


if __name__ == "__main__":
    main()
