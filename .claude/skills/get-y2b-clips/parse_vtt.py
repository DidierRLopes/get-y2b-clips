#!/usr/bin/env python3
"""Parse VTT subtitle file into segments.json and full_transcript.txt.

Usage:
    python parse_vtt.py <vtt_file> [--output-dir <dir>]

Example:
    python parse_vtt.py transcript.en.vtt
    python parse_vtt.py transcript.en.vtt --output-dir ./clips/2024-01-01_video/
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path


# Common HTML entities and artifacts to clean
HTML_ENTITIES = {
    '&gt;': '>',
    '&lt;': '<',
    '&amp;': '&',
    '&quot;': '"',
    '&apos;': "'",
    '&#39;': "'",
}


def clean_text(text: str) -> str:
    """Clean text by removing HTML entities and artifacts.

    Args:
        text: Raw text from VTT

    Returns:
        Cleaned text
    """
    # First, use Python's html.unescape for standard entities
    text = html.unescape(text)

    # Remove speaker indicators like >> or >>>
    text = re.sub(r'^>{1,3}\s*', '', text)

    # Remove any remaining HTML-like artifacts
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up extra whitespace
    text = ' '.join(text.split())

    return text.strip()


def parse_vtt(vtt_path: str) -> list[dict]:
    """Parse VTT file into list of segments with timestamps.

    Args:
        vtt_path: Path to VTT file

    Returns:
        List of dicts with 'start', 'end', 'text' keys
    """
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    segments = []
    current_start = None
    current_end = None
    seen_text = set()

    for line in lines:
        line = line.strip()

        # Check if this is a timestamp line
        time_match = re.match(
            r'^(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})',
            line
        )
        if time_match:
            current_start = time_match.group(1)
            current_end = time_match.group(2)
            continue

        # Skip metadata and empty lines
        if not line:
            continue
        if line.startswith('WEBVTT'):
            continue
        if line.startswith('Kind:'):
            continue
        if line.startswith('Language:'):
            continue

        # Skip lines with tags (word-by-word breakdowns)
        if '<' in line:
            continue

        # This is a text line - clean it up
        text = clean_text(line)
        if text and text not in seen_text and current_start:
            seen_text.add(text)
            segments.append({
                'start': current_start,
                'end': current_end,
                'text': text
            })

    return segments


def main():
    parser = argparse.ArgumentParser(
        description='Parse VTT subtitle file into segments.json and full_transcript.txt'
    )
    parser.add_argument('vtt_file', help='Path to VTT file')
    parser.add_argument(
        '--output-dir', '-o',
        default='.',
        help='Output directory (default: current directory)'
    )

    args = parser.parse_args()

    vtt_path = Path(args.vtt_file)
    if not vtt_path.exists():
        print(f"Error: VTT file not found: {vtt_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse VTT
    segments = parse_vtt(str(vtt_path))

    if not segments:
        print("Error: No segments found in VTT file", file=sys.stderr)
        sys.exit(1)

    # Write segments.json
    segments_path = output_dir / 'segments.json'
    with open(segments_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, indent=2)

    # Write full_transcript.txt (with timestamps for reference)
    transcript_path = output_dir / 'full_transcript.txt'
    with open(transcript_path, 'w', encoding='utf-8') as f:
        for seg in segments:
            f.write(f"[{seg['start']}] {seg['text']}\n")

    print(f"Parsed {len(segments)} segments")
    print(f"  -> {segments_path}")
    print(f"  -> {transcript_path}")


if __name__ == '__main__':
    main()
