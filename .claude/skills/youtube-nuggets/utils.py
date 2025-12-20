"""Shared utilities for youtube-nuggets skill."""

import re
from typing import List, Dict


def parse_timestamp(ts: str) -> float:
    """Convert timestamp string to seconds.

    Args:
        ts: Timestamp in format "HH:MM:SS.mmm" or "HH:MM:SS"

    Returns:
        Total seconds as float
    """
    # Handle both "00:38:03.670" and "00:38:03" formats
    ts = ts.strip()
    if '.' in ts:
        time_part, ms_part = ts.rsplit('.', 1)
        ms = int(ms_part) / 1000
    else:
        time_part = ts
        ms = 0

    parts = time_part.split(':')
    if len(parts) == 3:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    elif len(parts) == 2:
        h, m, s = 0, int(parts[0]), int(parts[1])
    else:
        raise ValueError(f"Invalid timestamp format: {ts}")

    return h * 3600 + m * 60 + s + ms


def seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to timestamp string.

    Args:
        seconds: Total seconds

    Returns:
        Timestamp in format "HH:MM:SS.mmm"
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_transcript(raw_text: str) -> str:
    """Format raw transcript text nicely.

    - Capitalize first letter of sentences
    - Each sentence on its own line
    - Blank lines between sentences

    Args:
        raw_text: Raw transcript text

    Returns:
        Formatted transcript
    """
    # Clean up the text
    text = ' '.join(raw_text.split())

    # Split into sentences (on . ! ?)
    sentences = re.split(r'(?<=[.!?])\s+', text)

    formatted = []
    for s in sentences:
        s = s.strip()
        if s:
            # Capitalize first letter
            if len(s) > 1:
                s = s[0].upper() + s[1:]
            else:
                s = s.upper()
            formatted.append(s)

    return '\n\n'.join(formatted)


def time_in_range(ts: str, start: str, end: str) -> bool:
    """Check if timestamp is within range.

    Args:
        ts: Timestamp to check
        start: Range start
        end: Range end

    Returns:
        True if ts is within [start, end]
    """
    ts_sec = parse_timestamp(ts)
    start_sec = parse_timestamp(start)
    end_sec = parse_timestamp(end)
    return start_sec <= ts_sec <= end_sec


def add_buffer(ts: str, buffer_seconds: float, add: bool = True) -> str:
    """Add or subtract buffer from timestamp.

    Args:
        ts: Original timestamp
        buffer_seconds: Seconds to add/subtract
        add: If True, add buffer; if False, subtract

    Returns:
        New timestamp string
    """
    seconds = parse_timestamp(ts)
    if add:
        seconds += buffer_seconds
    else:
        seconds = max(0, seconds - buffer_seconds)
    return seconds_to_timestamp(seconds)
