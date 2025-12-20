#!/usr/bin/env python3
"""Generate SRT subtitles and burn them into a video clip.

This script creates subtitled videos optimized for social media sharing.
Uses ffmpeg's subtitles filter with styling for better readability.

Usage:
    python burn_subtitles.py --video VIDEO.mp4 --segments segments.json \
        --start HH:MM:SS --end HH:MM:SS --output VIDEO_subtitled.mp4

Example:
    python burn_subtitles.py \
        --video "01_clip/Video.mp4" \
        --segments segments.json \
        --start 00:28:36 \
        --end 00:29:27 \
        --output "01_clip/Video Subtitled.mp4"
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ANSI colors for terminal output
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_stage(message: str):
    """Print a stage indicator."""
    print(f"{Colors.CYAN}{Colors.BOLD}[SUBTITLES]{Colors.RESET} {message}")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.GREEN}  ✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}  ✗ {message}{Colors.RESET}")


def parse_timestamp(ts: str) -> float:
    """Convert timestamp string (HH:MM:SS.mmm or HH:MM:SS) to seconds."""
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


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def clean_text(text: str) -> str:
    """Clean text for subtitle display."""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Capitalize first letter if lowercase
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def generate_srt(
    segments: list[dict],
    video_start_sec: float,
    video_end_sec: float,
    transcript_start_sec: float = None,
    transcript_end_sec: float = None,
    time_offset: float = 0.0,
    max_chars_per_line: int = 42,
    max_lines: int = 2,
    min_display_time: float = 1.5,
    max_display_time: float = 5.0
) -> str:
    """Generate SRT content from segments within the video time range.

    Args:
        segments: List of segment dicts with 'start', 'end', 'text'
        video_start_sec: Video start time in seconds (for calculating relative positions)
        video_end_sec: Video end time in seconds (absolute from source)
        transcript_start_sec: Start of transcript content (defaults to video_start_sec)
        transcript_end_sec: End of transcript content (defaults to video_end_sec)
        time_offset: Seconds to shift subtitles (negative = earlier, positive = later).
                     YouTube transcripts often need -0.5 to -1.0 to sync with audio.
        max_chars_per_line: Maximum characters per subtitle line
        max_lines: Maximum lines per subtitle block
        min_display_time: Minimum seconds to display each subtitle
        max_display_time: Maximum seconds to display each subtitle

    Returns:
        SRT formatted string
    """
    # Use transcript bounds for filtering if provided, otherwise use video bounds
    filter_start = transcript_start_sec if transcript_start_sec is not None else video_start_sec
    filter_end = transcript_end_sec if transcript_end_sec is not None else video_end_sec

    # Filter segments within the transcript range
    clip_segments = []
    for seg in segments:
        seg_start = parse_timestamp(seg['start'])
        seg_end = parse_timestamp(seg['end'])

        # Include segments that overlap with TRANSCRIPT range (not video range)
        if seg_start < filter_end and seg_end > filter_start:
            clip_segments.append({
                'original_start': seg_start,
                'original_end': seg_end,
                'text': clean_text(seg['text'])
            })

    if not clip_segments:
        return ""

    # Calculate the sync offset: we want the first subtitle to start at 0:00
    # (or very close to it) since the video's audio starts immediately
    first_seg_start = clip_segments[0]['original_start']
    sync_offset = video_start_sec - first_seg_start  # This will be negative

    # Apply timing adjustments to all segments
    for seg in clip_segments:
        # Adjust timing: original_start - video_start + sync_offset + time_offset
        # sync_offset makes first subtitle start at 0, time_offset fine-tunes sync
        relative_start = max(0, seg['original_start'] - video_start_sec + sync_offset + time_offset)
        relative_end = seg['original_end'] - video_start_sec + sync_offset + time_offset
        seg['start'] = relative_start
        seg['end'] = relative_end

    # Group segments into subtitle blocks (combine short segments)
    subtitle_blocks = []
    current_block = None

    for seg in clip_segments:
        if current_block is None:
            current_block = {
                'start': seg['start'],
                'end': seg['end'],
                'text': seg['text']
            }
        else:
            # Combine if gap is small and total length is reasonable
            gap = seg['start'] - current_block['end']
            combined_text = current_block['text'] + ' ' + seg['text']

            if gap < 0.5 and len(combined_text) <= max_chars_per_line * max_lines:
                current_block['end'] = seg['end']
                current_block['text'] = combined_text
            else:
                subtitle_blocks.append(current_block)
                current_block = {
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text']
                }

    if current_block:
        subtitle_blocks.append(current_block)

    # Fix subtitle timing: extend each block to show until next one starts
    # This ensures subtitles are visible for a reasonable duration
    clip_duration = video_end_sec - video_start_sec
    for i, block in enumerate(subtitle_blocks):
        # Determine end time: either next subtitle start, or a reasonable duration
        if i + 1 < len(subtitle_blocks):
            next_start = subtitle_blocks[i + 1]['start']
            # End slightly before next subtitle starts (0.05s gap)
            proposed_end = next_start - 0.05
        else:
            # Last subtitle: extend to end of clip
            proposed_end = clip_duration

        # Calculate display duration based on text length
        # Roughly 15 chars per second reading speed
        text_length = len(block['text'])
        reading_time = max(min_display_time, text_length / 15.0)
        reading_time = min(reading_time, max_display_time)

        # Use the shorter of: time until next subtitle, or calculated reading time
        duration = min(proposed_end - block['start'], reading_time)
        duration = max(duration, min_display_time)  # But at least min_display_time

        block['end'] = block['start'] + duration

    # Format as SRT with word wrapping
    srt_lines = []
    for i, block in enumerate(subtitle_blocks, 1):
        start_time = seconds_to_srt_time(block['start'])
        end_time = seconds_to_srt_time(block['end'])

        # Word wrap text
        words = block['text'].split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_chars_per_line:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)

                # Limit to max_lines
                if len(lines) >= max_lines:
                    break

        if current_line and len(lines) < max_lines:
            lines.append(' '.join(current_line))

        text = '\n'.join(lines)

        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(text)
        srt_lines.append("")

    return '\n'.join(srt_lines)


def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    font_size: int = 24,
    font_name: str = "Arial",
    primary_color: str = "&HFFFFFF",  # White
    outline_color: str = "&H000000",  # Black outline
    back_color: str = "&HA0000000",   # Semi-transparent black
    border_style: int = 4,            # Background box
    margin_v: int = 30                # Vertical margin from bottom
) -> bool:
    """Burn subtitles into video using ffmpeg.

    Args:
        video_path: Input video file
        srt_path: SRT subtitle file
        output_path: Output video file
        font_size: Subtitle font size
        font_name: Font family name
        primary_color: Text color (ASS format)
        outline_color: Outline color (ASS format)
        back_color: Background color (ASS format)
        border_style: 1=outline, 3=opaque box, 4=shadow+outline
        margin_v: Vertical margin in pixels

    Returns:
        True if successful
    """
    # Build force_style string for subtitle formatting
    # ASS style format: https://fileformats.fandom.com/wiki/SubStation_Alpha
    force_style = (
        f"FontSize={font_size},"
        f"FontName={font_name},"
        f"PrimaryColour={primary_color},"
        f"OutlineColour={outline_color},"
        f"BackColour={back_color},"
        f"BorderStyle={border_style},"
        f"Outline=2,"
        f"Shadow=1,"
        f"MarginV={margin_v},"
        f"Alignment=2"  # Bottom center
    )

    # Escape special characters in path for ffmpeg filter
    # ffmpeg requires : and \ to be escaped in filter strings
    srt_escaped = srt_path.replace('\\', '/').replace(':', r'\:')

    # Build ffmpeg command
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vf', f"subtitles='{srt_escaped}':force_style='{force_style}'",
        '-c:a', 'copy',  # Copy audio without re-encoding
        '-y',  # Overwrite output
        output_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return True
        else:
            print_error(f"ffmpeg error: {result.stderr[-500:]}")
            return False

    except Exception as e:
        print_error(f"Exception: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Generate subtitled video from segments'
    )
    parser.add_argument('--video', '-v', required=True,
                        help='Input video file')
    parser.add_argument('--segments', '-s', required=True,
                        help='Path to segments.json')
    parser.add_argument('--start', required=True,
                        help='Video start timestamp (HH:MM:SS)')
    parser.add_argument('--end', required=True,
                        help='Video end timestamp (HH:MM:SS)')
    parser.add_argument('--output', '-o', required=True,
                        help='Output video file path')
    parser.add_argument('--font-size', type=int, default=24,
                        help='Subtitle font size (default: 24)')
    parser.add_argument('--keep-srt', action='store_true',
                        help='Keep the generated SRT file')
    parser.add_argument('--transcript-start',
                        help='Transcript start timestamp (defaults to --start). '
                             'Use when video has buffer before speech starts.')
    parser.add_argument('--transcript-end',
                        help='Transcript end timestamp (defaults to --end). '
                             'Use when video has buffer after speech ends.')
    parser.add_argument('--offset', type=float, default=0.0,
                        help='Fine-tune subtitle timing in seconds. '
                             'Negative = earlier, positive = later. '
                             'Default: 0 (auto-sync aligns first subtitle to video start)')

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.video).exists():
        print_error(f"Video not found: {args.video}")
        sys.exit(1)

    if not Path(args.segments).exists():
        print_error(f"Segments file not found: {args.segments}")
        sys.exit(1)

    print_stage(f"Creating subtitled video")

    # Load segments
    with open(args.segments, 'r', encoding='utf-8') as f:
        segments = json.load(f)

    # Parse timestamps
    video_start_sec = parse_timestamp(args.start)
    video_end_sec = parse_timestamp(args.end)

    # Parse optional transcript bounds
    transcript_start_sec = parse_timestamp(args.transcript_start) if args.transcript_start else None
    transcript_end_sec = parse_timestamp(args.transcript_end) if args.transcript_end else None

    # Generate SRT content
    srt_content = generate_srt(
        segments,
        video_start_sec,
        video_end_sec,
        transcript_start_sec,
        transcript_end_sec,
        time_offset=args.offset
    )

    if not srt_content:
        print_error("No subtitles generated - check time range")
        sys.exit(1)

    # Write SRT file (temporary or permanent)
    output_path = Path(args.output)
    if args.keep_srt:
        srt_path = output_path.with_suffix('.srt')
    else:
        # Use temp file
        srt_fd, srt_path = tempfile.mkstemp(suffix='.srt')
        os.close(srt_fd)
        srt_path = Path(srt_path)

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

    subtitle_count = srt_content.count('\n\n')
    print_success(f"Generated {subtitle_count} subtitle blocks")

    # Burn subtitles
    output_path.parent.mkdir(parents=True, exist_ok=True)

    success = burn_subtitles(
        video_path=args.video,
        srt_path=str(srt_path),
        output_path=args.output,
        font_size=args.font_size
    )

    # Cleanup temp SRT if not keeping
    if not args.keep_srt and srt_path.exists():
        srt_path.unlink()

    if success:
        size_mb = Path(args.output).stat().st_size / (1024 * 1024)
        print_success(f"Created: {output_path.name} ({size_mb:.1f} MB)")
    else:
        print_error("Failed to create subtitled video")
        sys.exit(1)


if __name__ == '__main__':
    main()
