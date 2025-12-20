#!/usr/bin/env python3
"""Extract and curate transcript for a video clip.

This script finds proper sentence boundaries around the target timestamps,
ensuring the transcript starts and ends with complete sentences.
Handles unpunctuated auto-generated captions.

Usage:
    python extract_transcript.py --start HH:MM:SS --end HH:MM:SS [options]

Example:
    python extract_transcript.py \
        --start 00:38:03 \
        --end 00:38:50 \
        --title "No Dark GPUs" \
        --source "No Dark GPUs, No Bear Market" \
        --output "01_no_dark_gpus/No Dark GPUs Transcript.txt"

Output includes recommended video timestamps that contain the curated transcript.
"""

import argparse
import json
import re
import sys
from pathlib import Path


# Common sentence starters that indicate a new thought
SENTENCE_STARTERS = {
    'so', 'and', 'but', 'now', 'well', 'because', 'if', 'when', 'the',
    'we', 'i', 'you', 'they', 'it', 'that', 'this', 'what', 'how', 'why',
    'one', 'our', 'my', 'there', 'here', 'for', 'from', 'think', 'unlike'
}

# Phrases that typically end thoughts (before pause)
THOUGHT_ENDERS = {
    'company', 'companies', 'market', 'markets', 'business', 'people',
    'money', 'time', 'product', 'products', 'years', 'not', 'right',
    'do', 'did', 'done', 'know', 'think', 'believe', 'way', 'here',
    'there', 'ever', 'never', 'always', 'important', 'possible'
}


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


def looks_like_sentence_start(text: str, prev_text: str = None) -> bool:
    """Check if text looks like the start of a new sentence/thought."""
    if not text:
        return False

    text_lower = text.lower().strip()
    first_word = text_lower.split()[0] if text_lower.split() else ''

    # Check if starts with a common sentence starter
    if first_word in SENTENCE_STARTERS:
        return True

    # Check if previous text ends with a thought-ending word
    if prev_text:
        prev_lower = prev_text.lower().strip()
        last_word = prev_lower.split()[-1] if prev_lower.split() else ''
        if last_word in THOUGHT_ENDERS:
            return True

    return False


def find_sentence_boundaries(
    segments: list[dict],
    target_start_sec: float,
    target_end_sec: float,
    search_window: float = 15.0,
    min_pause: float = 0.3
) -> tuple[int, int]:
    """Find segment indices that form complete thoughts around target range.

    Args:
        segments: List of segment dicts with 'start', 'end', 'text'
        target_start_sec: Target start time in seconds
        target_end_sec: Target end time in seconds
        search_window: How far before/after to search for boundaries
        min_pause: Minimum pause duration to consider as thought boundary

    Returns:
        Tuple of (start_index, end_index) for segments to include
    """
    # Find segments in the target range
    target_indices = []
    for i, seg in enumerate(segments):
        seg_start = parse_timestamp(seg['start'])
        if target_start_sec <= seg_start <= target_end_sec:
            target_indices.append(i)

    if not target_indices:
        # Find closest segment to target
        min_dist = float('inf')
        closest_idx = 0
        for i, seg in enumerate(segments):
            seg_start = parse_timestamp(seg['start'])
            dist = abs(seg_start - target_start_sec)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        target_indices = [closest_idx]

    # Find sentence start: search backwards from first target segment
    start_idx = target_indices[0]

    for i in range(start_idx, max(0, start_idx - 30), -1):
        if i == 0:
            start_idx = 0
            break

        prev_seg = segments[i - 1]
        curr_seg = segments[i]

        prev_end = parse_timestamp(prev_seg['end'])
        curr_start = parse_timestamp(curr_seg['start'])
        pause_duration = curr_start - prev_end

        # Check for pause + sentence starter pattern
        if pause_duration >= min_pause:
            if looks_like_sentence_start(curr_seg['text'], prev_seg['text']):
                start_idx = i
                break

        # Check for significant pause (indicates thought boundary)
        if pause_duration >= 0.8:
            start_idx = i
            break

    # Find sentence end: search forwards from last target segment
    end_idx = target_indices[-1]

    for i in range(end_idx, min(len(segments) - 1, end_idx + 30)):
        curr_seg = segments[i]
        next_seg = segments[i + 1] if i + 1 < len(segments) else None

        if next_seg:
            curr_end = parse_timestamp(curr_seg['end'])
            next_start = parse_timestamp(next_seg['start'])
            pause_duration = next_start - curr_end

            # Check for pause after current segment
            if pause_duration >= min_pause:
                # Check if next segment starts a new thought
                if looks_like_sentence_start(next_seg['text'], curr_seg['text']):
                    end_idx = i
                    break

            # Significant pause indicates thought end
            if pause_duration >= 0.8:
                end_idx = i
                break
        else:
            end_idx = i
            break

    return start_idx, end_idx


def add_punctuation(text: str) -> str:
    """Add basic punctuation to unpunctuated text based on patterns."""
    # Common patterns that indicate sentence boundaries
    # Pattern: thought-ender word + sentence-starter word
    patterns = [
        (r'(\w+)\s+(so\s)', r'\1. \2'),
        (r'(\w+)\s+(and\s+(?:we|i|you|they|the|this|that)\s)', r'\1. \2'),
        (r'(\w+)\s+(but\s)', r'\1. \2'),
        (r'(\w+)\s+(now\s)', r'\1. \2'),
        (r'(\w+)\s+(because\s+(?:we|i|you|they|the|our)\s)', r'\1. \2'),
        (r'(\w+)\s+(if\s+you\s)', r'\1. \2'),
        (r'(\w+)\s+(unlike\s)', r'\1. \2'),
    ]

    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def format_sentences(raw_text: str) -> str:
    """Split text into sentences and format nicely.

    Handles both punctuated and unpunctuated text.
    """
    # Clean up whitespace
    text = ' '.join(raw_text.split())

    # Try to add punctuation if text seems unpunctuated
    period_count = text.count('.')
    word_count = len(text.split())

    if period_count < word_count / 30:  # Very few periods relative to words
        text = add_punctuation(text)

    # Split on sentence boundaries (period/question/exclamation followed by space and capital)
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

    # If no splits happened and text is long, try splitting on other patterns
    if len(sentences) == 1 and word_count > 30:
        # Try splitting on "so " or "and we" or "because"
        sentences = re.split(r'\.\s+', text)

    formatted = []
    for s in sentences:
        s = s.strip()
        if s:
            # Ensure first letter is capitalized
            if len(s) > 1:
                s = s[0].upper() + s[1:]
            elif s:
                s = s.upper()

            # Ensure sentence ends with punctuation
            if s and s[-1] not in '.!?':
                s += '.'

            formatted.append(s)

    return '\n\n'.join(formatted)


def extract_curated_transcript(
    segments: list[dict],
    target_start: str,
    target_end: str,
    video_padding: float = 2.0
) -> dict:
    """Extract a curated transcript with proper sentence boundaries.

    Args:
        segments: List of segment dicts from segments.json
        target_start: Target start timestamp (where the insight begins)
        target_end: Target end timestamp (where the insight ends)
        video_padding: Seconds to add before/after for video timestamps

    Returns:
        Dict with:
            - 'transcript': Formatted transcript text
            - 'transcript_start': Timestamp of first segment
            - 'transcript_end': Timestamp of last segment
            - 'video_start': Recommended video start (with padding)
            - 'video_end': Recommended video end (with padding)
            - 'word_count': Number of words
    """
    target_start_sec = parse_timestamp(target_start)
    target_end_sec = parse_timestamp(target_end)

    # Find thought boundaries
    start_idx, end_idx = find_sentence_boundaries(
        segments, target_start_sec, target_end_sec
    )

    # Extract segments
    selected_segments = segments[start_idx:end_idx + 1]

    if not selected_segments:
        return {
            'transcript': '',
            'transcript_start': target_start,
            'transcript_end': target_end,
            'video_start': target_start,
            'video_end': target_end,
            'word_count': 0
        }

    # Build raw text
    raw_text = ' '.join(seg['text'] for seg in selected_segments)

    # Format into sentences
    formatted_text = format_sentences(raw_text)

    # Get actual timestamps from segments
    transcript_start_sec = parse_timestamp(selected_segments[0]['start'])
    transcript_end_sec = parse_timestamp(selected_segments[-1]['end'])

    # Calculate video timestamps with padding
    video_start_sec = max(0, transcript_start_sec - video_padding)
    video_end_sec = transcript_end_sec + video_padding

    return {
        'transcript': formatted_text,
        'transcript_start': seconds_to_timestamp(transcript_start_sec),
        'transcript_end': seconds_to_timestamp(transcript_end_sec),
        'video_start': seconds_to_timestamp(video_start_sec),
        'video_end': seconds_to_timestamp(video_end_sec),
        'word_count': len(formatted_text.split())
    }


def main():
    parser = argparse.ArgumentParser(
        description='Extract curated transcript with proper sentence boundaries'
    )
    parser.add_argument('--start', '-s', required=True,
                        help='Target start timestamp (HH:MM:SS) - where the insight begins')
    parser.add_argument('--end', '-e', required=True,
                        help='Target end timestamp (HH:MM:SS) - where the insight ends')
    parser.add_argument('--padding', '-p', type=float, default=2.0,
                        help='Video padding in seconds (default: 2.0)')
    parser.add_argument('--title', '-t', required=True, help='Clip title')
    parser.add_argument('--source', required=True, help='Source video title')
    parser.add_argument('--output', '-o', required=True, help='Output file path')
    parser.add_argument('--segments', default='segments.json', help='Path to segments.json')
    parser.add_argument('--json', action='store_true',
                        help='Also output JSON with timestamps')

    args = parser.parse_args()

    # Load segments
    segments_path = Path(args.segments)
    if not segments_path.exists():
        print(f"Error: segments.json not found: {segments_path}", file=sys.stderr)
        print("Run parse_vtt.py first to generate segments.json", file=sys.stderr)
        sys.exit(1)

    with open(segments_path, 'r', encoding='utf-8') as f:
        segments = json.load(f)

    # Extract curated transcript
    result = extract_curated_transcript(
        segments,
        args.start,
        args.end,
        args.padding
    )

    if not result['transcript'].strip():
        print(f"Warning: No transcript found for range {args.start} - {args.end}",
              file=sys.stderr)

    # Create output directory if needed
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write transcript file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"{args.title} - Transcript\n")
        f.write(f"Source: {args.source}\n")
        f.write(f"Video: {result['video_start'][:8]} - {result['video_end'][:8]}\n\n")
        f.write("---\n\n")
        f.write(result['transcript'])
        f.write("\n")

    # Optionally write JSON with all info
    if args.json:
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print(f"  JSON: {json_path}")

    print(f"Transcript extracted: {output_path}")
    print(f"  Target range: {args.start} - {args.end}")
    print(f"  Curated transcript: {result['transcript_start'][:8]} - {result['transcript_end'][:8]}")
    print(f"  Video timestamps: {result['video_start'][:8]} - {result['video_end'][:8]}")
    print(f"  Words: {result['word_count']}")

    # Output video timestamps for easy copy-paste
    print(f"\nVIDEO_START={result['video_start'][:8]}")
    print(f"VIDEO_END={result['video_end'][:8]}")


if __name__ == '__main__':
    main()
