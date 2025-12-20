#!/usr/bin/env python3
"""Extract and format transcript for a video clip.

Usage:
    python extract_transcript.py --start HH:MM:SS --end HH:MM:SS [options]

Example:
    python extract_transcript.py \
        --start 00:38:03 \
        --end 00:38:50 \
        --buffer 5 \
        --title "No Dark GPUs" \
        --source "No Dark GPUs, No Bear Market" \
        --output "01_no_dark_gpus/No Dark GPUs Transcript.txt"
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_timestamp(ts: str) -> float:
    """Convert timestamp string to seconds."""
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
    """Convert seconds to timestamp string."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_transcript(raw_text: str) -> str:
    """Format raw transcript text nicely."""
    text = ' '.join(raw_text.split())

    # Split into sentences
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


def extract_transcript(
    segments: list[dict],
    start: str,
    end: str,
    buffer: float = 5.0
) -> tuple[str, str, str]:
    """Extract transcript for a clip with buffer.

    Args:
        segments: List of segment dicts from segments.json
        start: Video start timestamp
        end: Video end timestamp
        buffer: Seconds of buffer before/after

    Returns:
        Tuple of (formatted_text, buffered_start, buffered_end)
    """
    start_sec = parse_timestamp(start)
    end_sec = parse_timestamp(end)

    # Apply buffer
    buffered_start_sec = max(0, start_sec - buffer)
    buffered_end_sec = end_sec + buffer

    # Extract text from segments in range
    texts = []
    for seg in segments:
        seg_start = parse_timestamp(seg['start'])
        if buffered_start_sec <= seg_start <= buffered_end_sec:
            texts.append(seg['text'])

    raw_text = ' '.join(texts)
    formatted_text = format_transcript(raw_text)

    return (
        formatted_text,
        seconds_to_timestamp(buffered_start_sec),
        seconds_to_timestamp(buffered_end_sec)
    )


def main():
    parser = argparse.ArgumentParser(
        description='Extract and format transcript for a video clip'
    )
    parser.add_argument('--start', '-s', required=True, help='Video start timestamp (HH:MM:SS)')
    parser.add_argument('--end', '-e', required=True, help='Video end timestamp (HH:MM:SS)')
    parser.add_argument('--buffer', '-b', type=float, default=5.0, help='Buffer seconds (default: 5)')
    parser.add_argument('--title', '-t', required=True, help='Clip title')
    parser.add_argument('--source', required=True, help='Source video title')
    parser.add_argument('--output', '-o', required=True, help='Output file path')
    parser.add_argument('--segments', default='segments.json', help='Path to segments.json')

    args = parser.parse_args()

    # Load segments
    segments_path = Path(args.segments)
    if not segments_path.exists():
        print(f"Error: segments.json not found: {segments_path}", file=sys.stderr)
        print("Run parse_vtt.py first to generate segments.json", file=sys.stderr)
        sys.exit(1)

    with open(segments_path, 'r', encoding='utf-8') as f:
        segments = json.load(f)

    # Extract transcript
    formatted_text, buff_start, buff_end = extract_transcript(
        segments,
        args.start,
        args.end,
        args.buffer
    )

    if not formatted_text.strip():
        print(f"Warning: No transcript found for range {args.start} - {args.end}", file=sys.stderr)

    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write transcript file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"{args.title} - Transcript\n")
        f.write(f"Source: {args.source}\n")
        f.write(f"Video: {args.start} - {args.end}\n\n")
        f.write("---\n\n")
        f.write(formatted_text)
        f.write("\n")

    print(f"Transcript extracted: {output_path}")
    print(f"  Video range: {args.start} - {args.end}")
    print(f"  With buffer: {buff_start[:8]} - {buff_end[:8]}")
    print(f"  Words: {len(formatted_text.split())}")


if __name__ == '__main__':
    main()
