# y2b-nuggets

Extract the most valuable clips ("nuggets") from YouTube videos automatically using Claude Code.

## Overview

This project provides a Claude Code skill that analyzes YouTube video transcripts to find high-value segments based on controversy, insightful analysis, or user-specified topics. It then downloads those clips with burned-in subtitles ready for social media sharing.

## Features

- **Smart Clip Detection**: Uses AI to identify the most engaging, controversial, or insightful moments
- **Automatic Subtitles**: Burns subtitles directly into videos using Whisper for accurate timestamps
- **Complete Sentence Boundaries**: Ensures clips start and end with complete thoughts, not mid-sentence
- **Retry Logic**: Handles YouTube's intermittent 403 errors gracefully
- **Progress Reporting**: Clear console output showing each stage of extraction

## Dependencies

Before using, ensure you have these tools installed:

```bash
# Check if installed
command -v yt-dlp || echo "MISSING: yt-dlp"
command -v ffmpeg || echo "MISSING: ffmpeg"
```

### Installation

**macOS (Homebrew):**
```bash
brew install yt-dlp ffmpeg
```

**Linux:**
```bash
sudo apt update && sudo apt install -y yt-dlp ffmpeg
```

**Python (for subtitles with Whisper):**
```bash
pip install stable-ts
```

## Usage

Simply provide Claude Code with a YouTube URL and ask for clips:

```
Extract the best clips from https://www.youtube.com/watch?v=VIDEO_ID
```

Or be more specific:

```
Get 3 clips about "startup funding" from https://youtube.com/watch?v=VIDEO_ID
```

### What Gets Created

For each video, a timestamped folder is created with clips organized like:

```
clips/
└── 2024-01-15_10-30-00_video-title/
    ├── segments.json              # Parsed transcript with timestamps
    ├── full_transcript.txt        # Complete transcript for reference
    └── 01_clip_title/
        ├── Clip Title metadata.json     # Selection rationale & scores
        ├── Clip Title Transcript.txt    # Human-readable transcript
        ├── Clip Title Video.mp4         # Raw video clip
        └── Clip Title Subtitled.mp4     # Video with burned-in captions
```

## How It Works

1. **Fetch Video Info**: Gets video metadata and duration
2. **Download Transcript**: Prioritizes manual subtitles → auto-generated → Whisper
3. **Analyze Content**: Scores segments on controversy, insight, engagement, and relevance
4. **Extract Clips**: For each selected clip:
   - Creates metadata with selection rationale
   - Extracts transcript with proper sentence boundaries
   - Downloads video at exact timestamps
   - Burns in subtitles for social sharing

## Scoring Criteria

Clips are scored on:

| Signal | Weight | Examples |
|--------|--------|----------|
| **Controversy** | 30% | "I disagree", strong opinions, debate markers |
| **Insight** | 35% | Statistics, predictions, frameworks, expert knowledge |
| **Engagement** | 20% | Rhetorical questions, stories, emotional peaks |
| **Topic Match** | 15% | Keyword presence (40% if user specified topics) |

## Available Scripts

The skill includes helper scripts in `.claude/skills/get-y2b-clips/`:

| Script | Purpose |
|--------|---------|
| `parse_vtt.py` | Parse VTT subtitles into segments.json |
| `extract_transcript.py` | Extract transcript with sentence boundary detection |
| `download_clip.py` | Download video clip with retry logic |
| `burn_subtitles.py` | Generate subtitled video with Whisper or YouTube transcript |
| `utils.py` | Shared utilities for timestamp parsing |

## Clip Duration Guidelines

| Video Length | Recommended Clips | Default Clip Length |
|--------------|-------------------|---------------------|
| < 15 min | 1-2 | 30-60 seconds |
| 15-30 min | 2-3 | 45-90 seconds |
| 30-60 min | 3-4 | 60-120 seconds |
| 1-2 hours | 4-5 | 90-180 seconds |
| > 2 hours | 5-7 | 90-180 seconds |
