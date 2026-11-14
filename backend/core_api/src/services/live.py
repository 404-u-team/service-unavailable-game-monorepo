from typing import Any

from src.api.game_schemas import GameView

HISTORIES = ("history", "business_history")


def history_change(before: list[dict], after: list[dict]) -> dict:
    """Retain the shared tick window and append new samples."""
    if not after:
        return {"drop": len(before), "append": []}
    start = next(
        (i for i, point in enumerate(before) if point["tick"] >= after[0]["tick"]),
        len(before),
    )
    overlap = before[start:]
    if len(overlap) <= len(after) and overlap == after[: len(overlap)]:
        return {"drop": start, "append": after[len(overlap) :]}
    return {"drop": len(before), "append": after}


def live_frame(
    state: GameView, previous: dict | None, sequence: int
) -> tuple[dict, dict]:
    current = state.model_dump(mode="json")
    if previous is None:
        return {"type": "snapshot", "seq": sequence, "state": current}, current

    changes: dict[str, Any] = {}
    histories = {}
    for key, value in current.items():
        if key in HISTORIES:
            if value != previous[key]:
                histories[key] = history_change(previous[key], value)
        elif key == "economy":
            before = previous[key]
            changes[key] = {
                field: amount
                for field, amount in value.items()
                if field != "history" and amount != before[field]
            }
            if value["history"] != before["history"]:
                histories["finance"] = history_change(
                    before["history"], value["history"]
                )
        elif value != previous[key]:
            changes[key] = value
    return {
        "type": "patch",
        "seq": sequence,
        "changes": changes,
        "histories": histories,
    }, current
