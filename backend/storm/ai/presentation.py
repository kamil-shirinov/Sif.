"""Stable trader-facing formats, derived only from supplied facts."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Report timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def format_utc(value: str) -> str:
    stamp = utc_datetime(value)
    clock = stamp.strftime("%H:%M:%S" if stamp.second else "%H:%M")
    return f"{stamp.day} {MONTHS[stamp.month - 1]}, {clock} UTC"


def number(value) -> str:
    text = format(Decimal(str(value)), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def money(value) -> str:
    amount = Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{'-' if amount < 0 else ''}${abs(amount):,.0f}"


def report_sentences(facts: dict) -> list[str]:
    """One statement per report topic; omit duplicate raw fields and notes."""
    storm, ships = facts["storm"], facts["ships"]
    move = storm["move_bp"]
    verb = "fell" if move < 0 else "rose" if move > 0 else "moved"
    hours = storm.get("market_hours")
    unit = "trading minutes" if hours else "minutes"
    sentences = [
        f"From {format_utc(storm['onset_utc'])} to {format_utc(storm['trough_utc'])}, "
        f"{storm['symbol']} {verb} {number(abs(move))} basis points over "
        f"{number(storm['duration_minutes'])} {unit}."
    ]
    alarms = [e for e in facts["alarm_events"] if e["type"] == "alarm"]
    watches = [e for e in facts["alarm_events"] if e["type"] == "watch"]
    if alarms:
        alarm = alarms[0]
        offset = alarm["minutes_from_onset"]
        timing = "as the move began" if offset == 0 else (
            f"{number(abs(offset))} {'minute' if abs(offset) == 1 else 'minutes'} "
            f"{'after' if offset > 0 else 'before'} the move began")
        sentence = f"The alarm sounded at {format_utc(alarm['time_utc'])}, {timing}"
        if alarm.get("move_ahead_pct") is not None:
            sentence += f"; {number(alarm['move_ahead_pct'])}% of the eventual move was still to come"
        sentences.append(sentence + ".")
    elif watches:
        watch = watches[0]
        sentence = f"No storm alarm was recorded; a calendar watch began at {format_utc(watch['time_utc'])}"
        if watch.get("minutes_before_release") is not None:
            sentence += f", {number(watch['minutes_before_release'])} minutes before the scheduled release"
        sentences.append(sentence + ".")
    else:
        sentences.append("No storm alarm was recorded in this replay.")

    prepared, unprepared = (ships[name]["final_equity_usd"] for name in ("prepared", "unprepared"))
    difference = ships["equity_saved_usd"]
    if prepared == unprepared:
        sentences.append(f"Both ships ended with {money(prepared)} on the synthetic book.")
    else:
        sentences.append(
            f"For the synthetic book, the prepared ship ended with {money(prepared)} versus "
            f"{money(unprepared)} for the unprepared ship, finishing {money(abs(difference))} "
            f"{'ahead' if difference >= 0 else 'behind'}.")

    event = storm.get("scheduled_event")
    exposure = facts["exposure"]
    if hours and hours.get("closed_minutes", 0) > 0:
        sentences.append("The market closed between sessions, so the duration excludes time when it was not trading.")
    elif event:
        sentences.append(f"The scheduled {event['name']} release was at {format_utc(event['time_utc'])}; "
                         "the replay records its timing without attributing the move to it.")
    elif exposure["leverage"] is not None and exposure["margin_buffer_pct"] is not None:
        sentences.append(f"Exposure was {number(exposure['leverage'])} times equity, "
                         f"with a {number(exposure['margin_buffer_pct'])}% margin buffer.")
    elif facts["stress"]:
        sentences.append(f"The recorded stress scenario produced a P&L of {money(facts['stress'][0]['pnl_usd'])}.")
    return sentences
