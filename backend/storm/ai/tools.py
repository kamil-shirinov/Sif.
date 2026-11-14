"""Deterministic navigator tools and their OpenAI function schemas."""
from __future__ import annotations

import json

from storm import exposure

from . import scenario as scenarios


def get_exposure(storm_id: str) -> dict:
    bundle = scenarios.load_bundle(storm_id)
    book, mids, paths = scenarios.book_paths(bundle)
    snapshot = exposure.exposure_snapshot(paths["unprepared"], mids, book, bundle["exposure"]["as_of_i"])
    return {"storm_id": storm_id, "symbol": bundle["symbol"], "source": bundle["source"],
            "book_is_synthetic": True, "exposure": snapshot,
            "total_notional_usd": sum(position["notional_usd"] for position in snapshot["positions"]),
            "assumptions": "Synthetic exporter book, long USD; snapshot before the storm; marks at mid without spread or slippage"}


def list_storms() -> dict:
    storms = []
    for path in sorted(scenarios.BUNDLES_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            bundle = scenarios.load_bundle(path.stem)
        except (ValueError, OSError):
            continue
        if bundle["source"] == "scenario":
            continue
        storms.append({key: bundle[key] for key in ("storm_id", "title", "symbol", "source")})
    return {"storms": storms, "count": len(storms), "book_is_synthetic": True}


stress_test = scenarios.stress_test
scenario = scenarios.scenario

_MOVE = {"type": "number", "exclusiveMinimum": -100, "maximum": 1000,
         "description": "Signed pair price move in percent; a drop is negative"}
_MINUTES = {"type": "integer", "minimum": 1, "maximum": 1440}
_SYMBOL = {"type": "string", "enum": list(scenarios.SYMBOLS)}


def _schema(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False}}}


TOOL_SCHEMAS = [
    _schema("get_exposure", "Compute the synthetic book's exposure for an exported replay",
            {"storm_id": {"type": "string"}}, ["storm_id"]),
    _schema("list_storms", "List available replay bundles, with explicit data source labels", {}, []),
    _schema("stress_test", "Deterministic endpoint P&L before liquidation; not a price forecast",
            {"symbol": _SYMBOL, "move_pct": _MOVE, "minutes": _MINUTES},
            ["symbol", "move_pct", "minutes"]),
    _schema("scenario", "Resize a replay path, simulate both ships and return a what-if bundle. "
            "Alarm timing is inherited, not predicted. Base and scenario symbols must match.",
            {"symbol": _SYMBOL, "move_pct": _MOVE, "minutes": _MINUTES,
             "base_storm_id": {"type": "string", "default": scenarios.DEFAULT_STORM}},
            ["symbol", "move_pct", "minutes"]),
]
FUNCTIONS = {"get_exposure": get_exposure, "list_storms": list_storms,
             "stress_test": stress_test, "scenario": scenario}


def execute(name: str, arguments: dict):
    """Allow only registered arguments, including for providers ignoring schemas."""
    schema = next((item["function"]["parameters"] for item in TOOL_SCHEMAS
                   if item["function"]["name"] == name), None)
    if schema is None:
        raise ValueError("Unknown navigator tool")
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object")
    if set(arguments) - schema["properties"].keys():
        raise ValueError("Unexpected tool arguments")
    if set(schema["required"]) - arguments.keys():
        raise ValueError("Missing required tool arguments")
    for key in ("storm_id", "base_storm_id"):
        if key in arguments and not isinstance(arguments[key], str):
            raise ValueError(f"{key} must be a string")
    json.dumps(arguments, allow_nan=False)
    return FUNCTIONS[name](**arguments)
