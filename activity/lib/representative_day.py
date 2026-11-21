#!/usr/bin/env python3
"""Shared single-representative-weekday extraction for MAST weekly diaries.

MAST emits a WEEKLY continuous-time schedule: leg/activity times are WEEK-minutes
(0..10080+) that span multiple diary days. Day index = start_time_min // 1440
(0=Mon, 1=Tue, ... 6=Sun); the activities_full/activities `day` column is the same
index + 1 (1=Mon .. 7=Sun).

To build a single representative 24h WEEKDAY MATSim day we must NOT overlay all days
with `% 1440` (that squashes multi-day chains). Instead pick ONE day per person and
keep only that day's legs, converting week-minutes -> time-of-day = start - day*1440.
Since 2026-10-22 (Validation_2026 stage 3, second pass) that day is Monday for every
person (REP_DAY, rule "fixed" of pick_day); persons without legs on Monday stay home.

Both the plan writers (build_studyarea.py, build_matsim_pop.py) and the validator
(validate_studyarea.py) import this so the PLAN FILE and the VALIDATION metrics are
computed from the exact same single-day chains.
"""

MAX_MIN = 1800   # allow up to 30h (108000s) for legitimate late returns; MATSim supports >24h


def leg_day(leg):
    """Week-day index (0=Mon .. 6=Sun) of a leg, from its week-minute start."""
    return int(leg["start_time_min"]) // 1440


def is_weekday(day_idx):
    """True for Mon-Fri (index 0..4, mod 7 so a wrapped next-Mon still counts)."""
    return (day_idx % 7) < 5


def _complete_chain(day_legs):
    """A day whose first leg leaves HOME and whose last leg returns HOME."""
    return day_legs[0]["previous_purpose"] == "HOME" and day_legs[-1]["next_purpose"] == "HOME"


REP_DAY = 0          # the representative weekday of the chain: Monday (rule "fixed", Validation_2026 stage 3 second pass, 2026-10-22)
REP_DAY_RULE = "fixed"   # "fixed": REP_DAY for every person; "best": the earlier rule (earliest complete weekday with legs)


def pick_day(legs, rule=None):
    """Choose the single representative day index for a person's legs.

    Rule "fixed" (the chain's rule since 2026-10-22, Validation_2026/3_abit/VALIDATION_REPORT.md section 7): the representative
    weekday is MONDAY (REP_DAY) for every person.  A person without legs on Monday is a non-traveller on the representative
    day (a home-only plan in MATSim).  The weekly model places the discretionary activities with a Monday weight and a
    free-day weight (MarylandDayOfWeekDiscretionaryAssignment), so the share of persons travelling on Monday and the tour
    rates per traveller on Monday are the calibrated quantities; the share of travellers is then the model's own
    (0.86 of persons in the survey), and the weekly school-day probability of a student equals the survey value because
    every weekday is a school day with that probability.

    Rule "best" (the rule of the first pass): prefer a Mon-Fri day; among candidates prefer a complete home->...->home
    chain, then the EARLIEST day.  This counts every person with a tour anywhere in the week as a traveller on the
    representative day (model traveller share 0.91-0.93 against 0.86 in the survey) and makes a student's representative
    day preferentially a school day (so the weekly school-day probability had to be lowered by a factor of 0.8 to meet
    the daily rate).  Kept for comparison.

    Returns None if the person has no legs on the representative day (rule "fixed") or no legs at all (rule "best").
    """
    rule = rule or REP_DAY_RULE
    by_day = {}
    for lg in legs:
        try:
            d = int(lg["start_time_min"]) // 1440
        except (ValueError, KeyError, TypeError):
            continue
        by_day.setdefault(d, []).append(lg)
    if not by_day:
        return None
    if rule == "fixed":
        return REP_DAY if REP_DAY in by_day else None
    for d in by_day:
        by_day[d].sort(key=lambda r: int(r["start_time_min"]))
    days = sorted(by_day)
    weekdays = [d for d in days if is_weekday(d)]
    cand = weekdays if weekdays else days
    # rank: complete chain (True>False), then earliest day (-d); no busiest-day bias
    return max(cand, key=lambda d: (_complete_chain(by_day[d]), -d))


def single_day_legs(legs):
    """Return (chosen_day_index, [legs on that day]) sorted by time-of-day.

    Each returned leg gets `_tod_start` / `_tod_end` = week-minute - day*1440
    (time-of-day within the representative day). Returns (None, []) if no legs.
    """
    best = pick_day(legs)
    if best is None:
        return None, []
    dl = [lg for lg in legs if _has_day(lg, best)]
    dl.sort(key=lambda r: int(r["start_time_min"]))
    off = best * 1440
    for lg in dl:
        lg["_tod_start"] = int(lg["start_time_min"]) - off
        lg["_tod_end"] = int(lg["end_time"]) - off
    return best, dl


def _has_day(lg, day):
    try:
        return int(lg["start_time_min"]) // 1440 == day
    except (ValueError, KeyError, TypeError):
        return False


def hhmmss(m):
    """Minutes-of-day -> HH:MM:SS, clamped to [0, 30h]. Departures only (never negative)."""
    m = int(round(m))
    if m < 0:
        m = 0
    if m > MAX_MIN:
        m = MAX_MIN
    return f"{m // 60:02d}:{m % 60:02d}:00"
