---
name: youtube-nuggets
description: Extract the most meaningful, engaging clips from YouTube videos. Use when user provides a YouTube URL and wants to find highlights, best moments, controversial takes, or valuable segments. Supports specifying number of clips or topic focus.
allowed-tools: Bash,Read,Write,Glob
---

# YouTube Nuggets Extractor

Extract the most valuable clips ("nuggets") from YouTube videos automatically. Analyzes transcripts to find high-value segments based on controversy, insightful analysis, or user-specified topics.

## When to Use This Skill

Activate when the user:
- Wants to extract "best clips", "highlights", or "nuggets" from a YouTube video
- Asks to find "interesting moments" or "valuable segments"
- Wants controversial takes, insights, or specific topics from a video
- Provides a YouTube URL and mentions clips, segments, or highlights

## Dependencies Check

**ALWAYS check dependencies first:**

```bash
# Check for yt-dlp
command -v yt-dlp || echo "MISSING: yt-dlp"

# Check for ffmpeg
command -v ffmpeg || echo "MISSING: ffmpeg"
```

### Install Missing Dependencies

**yt-dlp:**
```bash
# macOS
brew install yt-dlp

# Linux
sudo apt update && sudo apt install -y yt-dlp

# pip (universal)
pip3 install yt-dlp
```

**ffmpeg:**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt update && sudo apt install -y ffmpeg
```

## Input Requirements

- **Required**: YouTube URL
- **Optional** (ask user if not specified for long videos >30 min):
  - Number of clips (default: 3-5 based on video length)
  - Topic focus keywords
  - Min/max clip duration (default: 30s-180s)

## Complete Workflow

### Phase 1: Setup

```bash
# Get video info
VIDEO_URL="USER_PROVIDED_URL"
VIDEO_TITLE=$(yt-dlp --print "%(title)s" "$VIDEO_URL" | tr '/:?*"<>|\\' '-')
VIDEO_DURATION=$(yt-dlp --print "%(duration)s" "$VIDEO_URL")
VIDEO_ID=$(yt-dlp --print "%(id)s" "$VIDEO_URL")

echo "Video: $VIDEO_TITLE"
echo "Duration: $((VIDEO_DURATION / 60)) minutes"

# Create output folder
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
SLUG=$(echo "$VIDEO_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | cut -c1-50)
OUTPUT_DIR="./clips/${TIMESTAMP}_${SLUG}"
mkdir -p "$OUTPUT_DIR"

echo "Output folder: $OUTPUT_DIR"
```

### Phase 2: Get Transcript

**Priority order: Manual subtitles → Auto-generated → Whisper**

```bash
cd "$OUTPUT_DIR"

# Check available subtitles
yt-dlp --list-subs "$VIDEO_URL"

# Try manual subtitles first
if yt-dlp --write-sub --sub-langs "en" --skip-download -o "transcript" "$VIDEO_URL" 2>/dev/null; then
    echo "Manual subtitles downloaded"
elif yt-dlp --write-auto-sub --sub-langs "en" --skip-download -o "transcript" "$VIDEO_URL" 2>/dev/null; then
    echo "Auto-generated subtitles downloaded"
else
    echo "No subtitles available - Whisper transcription required"
    # Ask user before proceeding with Whisper (downloads audio)
fi
```

**Convert VTT to timestamped text:**

```bash
VTT_FILE=$(ls transcript*.vtt 2>/dev/null | head -n 1)

python3 << 'PYTHON_SCRIPT'
import re
import sys

def parse_vtt(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match timestamps and text
    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n(.*?)(?=\n\n|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)

    segments = []
    seen_text = set()

    for start, end, text in matches:
        # Clean text
        text = re.sub(r'<[^>]+>', '', text)  # Remove tags
        text = text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        text = ' '.join(text.split())  # Normalize whitespace

        if text and text not in seen_text:
            seen_text.add(text)
            segments.append({
                'start': start,
                'end': end,
                'text': text
            })

    return segments

segments = parse_vtt("$VTT_FILE")

# Write full transcript with timestamps
with open('full_transcript.txt', 'w') as f:
    for seg in segments:
        f.write(f"[{seg['start'][:8]}] {seg['text']}\n")

# Write segments JSON for analysis
import json
with open('segments.json', 'w') as f:
    json.dump(segments, f, indent=2)

print(f"Parsed {len(segments)} segments")
PYTHON_SCRIPT
```

### Phase 3: Analyze Content

**Read the transcript and identify valuable segments.**

Use Claude's analysis to score segments based on:

1. **Controversy Signals** (weight: 0.30)
   - "I disagree", "controversial", "unpopular opinion"
   - Strong language: "absolutely", "never", "always"
   - Debate markers: "push back", "challenge that"

2. **Insight Signals** (weight: 0.35)
   - Statistics, data points, percentages
   - Predictions: "will happen", "in X years"
   - Frameworks: "the way I see it", "my model"
   - Expert knowledge, technical depth

3. **Engagement Signals** (weight: 0.20)
   - Rhetorical questions
   - Stories: "let me tell you", "for example"
   - Emotional peaks, emphasis
   - Direct address: "think about it"

4. **Topic Match** (weight: 0.15, or 0.40 if user specified topics)
   - Keyword presence
   - Semantic relevance

**Analysis approach:**
1. Read `full_transcript.txt`
2. Identify natural topic boundaries (every 2-5 minutes typically)
3. Score each segment
4. Select top N segments (user-specified or auto: 3-5)
5. Determine optimal clip boundaries (include context, avoid mid-sentence cuts)

**Output analysis as JSON:**
```json
{
  "clips": [
    {
      "title": "Controversial Take on AI Regulation",
      "start_time": "00:23:45",
      "end_time": "00:26:30",
      "score": 0.87,
      "why": "Speaker makes bold claim that AI regulation will backfire, cites specific data, directly challenges mainstream view"
    }
  ]
}
```

### Phase 4: Extract Clips

**For each identified segment:**

```bash
CLIP_NUM=1
START_TIME="00:23:45"
END_TIME="00:26:30"
CLIP_TITLE="Controversial Take on AI Regulation"
SAFE_TITLE=$(echo "$CLIP_TITLE" | tr '/:?*"<>|\\' '-')

# Create clip folder
CLIP_DIR="$OUTPUT_DIR/$(printf '%02d' $CLIP_NUM)_$(echo "$SAFE_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | cut -c1-40)"
mkdir -p "$CLIP_DIR"

# Download video clip
yt-dlp -f 'bestvideo[height<=1080]+bestaudio/best[height<=1080]' \
  --download-sections "*${START_TIME}-${END_TIME}" \
  --force-keyframes-at-cuts \
  --merge-output-format mp4 \
  -o "$CLIP_DIR/${SAFE_TITLE} Video.%(ext)s" \
  "$VIDEO_URL"

# If above fails, try simpler format
if [ ! -f "$CLIP_DIR/${SAFE_TITLE} Video.mp4" ]; then
  yt-dlp -f 'best[height<=1080]' \
    --download-sections "*${START_TIME}-${END_TIME}" \
    --force-keyframes-at-cuts \
    -o "$CLIP_DIR/${SAFE_TITLE} Video.%(ext)s" \
    "$VIDEO_URL"
fi
```

**Create transcript file:**
Extract the relevant portion from full_transcript.txt for the clip's timeframe and save to `<Title> Transcript.txt`

**Create why file:**
Write the explanation of why this clip was selected to `<Title> Why.txt`

### Phase 5: Generate Metadata

```bash
cat > "$OUTPUT_DIR/metadata.json" << EOF
{
  "source": {
    "url": "$VIDEO_URL",
    "title": "$VIDEO_TITLE",
    "video_id": "$VIDEO_ID",
    "duration_seconds": $VIDEO_DURATION
  },
  "extraction": {
    "date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "output_dir": "$OUTPUT_DIR",
    "clip_count": $TOTAL_CLIPS,
    "topic_filter": $TOPIC_FILTER_JSON
  },
  "clips": $CLIPS_JSON
}
EOF
```

### Phase 6: Summary

Display to user:
- Number of clips extracted
- Total clip duration
- List of clips with titles and timestamps
- Output folder location

```
Extraction Complete!

Source: [Video Title]
Duration: X minutes
Clips Extracted: N

1. "Controversial Take on AI Regulation" (00:23:45 - 00:26:30) - 2:45
2. "Surprising Market Prediction" (01:12:00 - 01:14:30) - 2:30
3. "Heated Debate on Crypto" (01:45:15 - 01:48:00) - 2:45

Output: ./clips/2024-12-20_10-30-00_video-title/
```

## Clip Duration Guidelines

| Video Length | Recommended Clips | Default Clip Length |
|--------------|-------------------|---------------------|
| < 15 min     | 1-2               | 30-60 seconds       |
| 15-30 min    | 2-3               | 45-90 seconds       |
| 30-60 min    | 3-4               | 60-120 seconds      |
| 1-2 hours    | 4-5               | 90-180 seconds      |
| > 2 hours    | 5-7               | 90-180 seconds      |

## Interactive Flow (Long Videos)

For videos > 30 minutes without user guidance, ask:

```
I found a [X] minute video. How would you like to proceed?

A) Extract top 5 clips automatically (recommended)
B) Focus on specific topics - please specify keywords
C) Extract more clips - specify how many
D) Let me scan the transcript first and suggest topics
```

## Error Handling

| Issue | Solution |
|-------|----------|
| No subtitles | Offer Whisper with audio size warning |
| ffmpeg missing | Provide install command |
| Clip download fails | Retry with simpler format `-f best` |
| Private video | Inform user, cannot proceed |
| Very short video | Suggest 1 clip or full download |

## Output File Naming

- Folder: `YYYY-MM-DD_HH-MM-SS_<video-slug>/`
- Clips: `NN_<clip-slug>/`
- Files:
  - `<Title> Video.mp4`
  - `<Title> Transcript.txt`
  - `<Title> Why.txt`

## Example Session

**User**: Extract the best clips from https://www.youtube.com/watch?v=abc123

**Claude**:
1. Checks dependencies (yt-dlp, ffmpeg)
2. Gets video info: "AI Future Podcast - 1:45:00"
3. Downloads transcript
4. Analyzes for top 5 segments
5. Extracts each clip with video, transcript, and rationale
6. Returns summary with folder location

**User**: Get 3 clips about "startup funding" from https://youtube.com/watch?v=xyz789

**Claude**:
1. Same setup
2. Filters transcript for "startup", "funding", "invest", "raise" keywords
3. Scores segments with topic_match weighted higher
4. Extracts exactly 3 most relevant clips
5. Returns summary
