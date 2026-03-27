"""Shared SSE parsing utility for test modules."""

import json


def parse_sse(body: bytes) -> list[dict | str]:
    """Parse an SSE response body into a list of payloads.

    Returns strings for non-JSON events (e.g. "[DONE]"), dicts for JSON ones.
    """
    events = []
    for line in body.decode().splitlines():
        if line.startswith("data: "):
            payload = line[len("data: "):]
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                events.append(payload)
    return events
