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

**CRITICAL: The order of operations is WHY → TRANSCRIPT → VIDEO**

The "Why" justifies the selection, the transcript defines the EXACT timestamps, and the video is downloaded to match those exact timestamps.

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

### Phase 2: Get Transcript with Exact Timestamps

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

**Convert VTT to timestamped text - PRESERVE EXACT TIMESTAMPS:**

```python
import re
import json

def parse_vtt(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    segments = []
    current_start = None
    current_end = None
    seen_text = set()

    for line in lines:
        line = line.strip()

        # Check if this is a timestamp line
        time_match = re.match(r'^(\d{2}:\d{2}:\d{2})\.(\d{3}) --> (\d{2}:\d{2}:\d{2})\.(\d{3})', line)
        if time_match:
            current_start = f"{time_match.group(1)}.{time_match.group(2)}"
            current_end = f"{time_match.group(3)}.{time_match.group(4)}"
            continue

        # Skip metadata and empty lines
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue

        # Skip lines with tags (word-by-word breakdowns)
        if '<' in line:
            continue

        # This is a clean text line
        text = line.strip()
        if text and text not in seen_text and current_start:
            seen_text.add(text)
            segments.append({
                'start': current_start,
                'end': current_end,
                'text': text
            })

    return segments

segments = parse_vtt("transcript.en.vtt")

# Write full transcript with timestamps
with open('full_transcript.txt', 'w') as f:
    for seg in segments:
        f.write(f"[{seg['start']}] {seg['text']}\n")

# Write segments JSON for precise timestamp lookup
with open('segments.json', 'w') as f:
    json.dump(segments, f, indent=2)

print(f"Parsed {len(segments)} segments with exact timestamps")
```

### Phase 3: Analyze Content & Generate "Why" FIRST

**This is the critical phase - identify segments and justify selection BEFORE extracting.**

Read `full_transcript.txt` and analyze using these scoring criteria:

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

**Analysis output - use EXACT timestamps from transcript:**

For each identified clip, record:
1. **Title**: Short descriptive name
2. **Start timestamp**: EXACT timestamp from first line of segment (from segments.json)
3. **End timestamp**: EXACT timestamp from last line of segment (from segments.json)
4. **Why**: Full justification with scores

**IMPORTANT**: The start and end times MUST come from the transcript timestamps. Do not approximate or round. The video will be cut to match these exact times.

### Phase 4: For Each Clip - Create Files in Order

**Order: Why → Transcript → Video**

#### Step 1: Create the "Why" file FIRST

```
WHY THIS CLIP WAS SELECTED
==========================

Title: [Clip Title]
Duration: [calculated from timestamps]

CONTROVERSY SCORE: X/10
-----------------------
[Explanation of controversy signals found]

INSIGHT SCORE: X/10
-------------------
[Key insights delivered, bullet points]

ENGAGEMENT SCORE: X/10
----------------------
[Engagement signals found]

RELEVANCE TO VIDEO TITLE: X/10
-------------------------------
[How it relates to the main topic]

ACTIONABLE TAKEAWAY
-------------------
[What viewers/investors should do with this information]
```

#### Step 2: Extract Transcript with Buffer

Extract transcript text with a 5-second buffer before and after the video timestamps. This ensures all spoken words in the video clip are captured in the transcript (accounting for keyframe cuts).

**Key rules:**
- **Clean text only** - no timestamps in the output
- **5-second buffer** - transcript covers slightly more than the video
- **Proper formatting** - capitalize first letter of sentences, new line for each sentence
- **Readable flow** - sentences separated by blank lines for easy reading

**Formatting the transcript:**
1. Join all segment text together
2. Split on sentence boundaries (. ! ?)
3. Capitalize first letter of each sentence
4. Write each sentence on its own line with blank line between

```python
import json
import re

# Load segments
with open('segments.json', 'r') as f:
    segments = json.load(f)

# Define VIDEO boundaries (what will be downloaded)
video_start = "00:12:06.000"
video_end = "00:14:05.000"

# Define TRANSCRIPT boundaries (5-second buffer)
transcript_start = "00:12:01.000"  # 5s before video
transcript_end = "00:14:10.000"    # 5s after video

# Extract matching segments
clip_text = []
for seg in segments:
    if seg['start'] >= transcript_start and seg['start'] <= transcript_end:
        clip_text.append(seg['text'])

# Join and format nicely
raw_text = ' '.join(clip_text)

# Split into sentences and format
sentences = re.split(r'(?<=[.!?])\s+', raw_text)
formatted_sentences = []
for s in sentences:
    s = s.strip()
    if s:
        # Capitalize first letter
        s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
        formatted_sentences.append(s)

# Write clean, formatted transcript
with open('Clip_Title Transcript.txt', 'w') as f:
    f.write(f"Clip Title - Transcript\n")
    f.write(f"Source: Video Title\n")
    f.write(f"Video: {video_start[:8]} - {video_end[:8]}\n\n---\n\n")
    f.write('\n\n'.join(formatted_sentences))  # Each sentence on new line
```

#### Step 3: Download Video using EXACT timestamps

**CRITICAL**: Use the same timestamps from the transcript extraction.

```bash
START_TIME="00:12:06"  # Must match transcript start
END_TIME="00:14:05"    # Must match transcript end
CLIP_TITLE="Clip Title"
SAFE_TITLE=$(echo "$CLIP_TITLE" | tr '/:?*"<>|\\' '-')

# Create clip folder
CLIP_DIR="$OUTPUT_DIR/01_$(echo "$SAFE_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | cut -c1-40)"
mkdir -p "$CLIP_DIR"

# Download video clip with EXACT timestamps
yt-dlp -f 'bestvideo[height<=1080]+bestaudio/best[height<=1080]' \
  --download-sections "*${START_TIME}-${END_TIME}" \
  --force-keyframes-at-cuts \
  --merge-output-format mp4 \
  -o "$CLIP_DIR/${SAFE_TITLE} Video.%(ext)s" \
  "$VIDEO_URL"
```

### Phase 5: Generate Metadata

```json
{
  "source": {
    "url": "VIDEO_URL",
    "title": "VIDEO_TITLE",
    "video_id": "VIDEO_ID",
    "duration_seconds": DURATION
  },
  "extraction": {
    "date": "ISO_TIMESTAMP",
    "output_dir": "OUTPUT_DIR",
    "clip_count": N,
    "topic_filter": null
  },
  "clips": [
    {
      "index": 1,
      "folder": "01_clip_slug",
      "title": "Clip Title",
      "start_time": "00:12:06.000",
      "end_time": "00:14:05.000",
      "duration_seconds": 119,
      "scores": {
        "controversy": 0.9,
        "insight": 0.9,
        "engagement": 0.8,
        "overall": 0.87
      },
      "summary": "Brief description"
    }
  ]
}
```

### Phase 6: Summary

Display to user:
- Number of clips extracted
- Total clip duration
- List of clips with titles and EXACT timestamps
- Output folder location

## Timestamp Alignment Rules

**These rules ensure video matches transcript exactly:**

1. **Source of truth**: The VTT transcript timestamps are the source of truth
2. **No rounding**: Use timestamps exactly as they appear in segments.json
3. **Verify alignment**: The first and last words in `Transcript.txt` should match the first and last words spoken in `Video.mp4`
4. **Buffer if needed**: If a sentence is cut mid-word, extend to the next segment boundary

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
| Timestamp mismatch | Re-verify against segments.json |

## Output File Naming

- Folder: `YYYY-MM-DD_HH-MM-SS_<video-slug>/`
- Clips: `NN_<clip-slug>/`
- Files:
  - `<Title> Why.txt` (created first)
  - `<Title> Transcript.txt` (created second)
  - `<Title> Video.mp4` (created last)

## Example Session

**User**: Extract the best clips from https://www.youtube.com/watch?v=abc123

**Claude**:
1. Checks dependencies (yt-dlp, ffmpeg)
2. Gets video info: "AI Future Podcast - 1:45:00"
3. Downloads transcript with exact timestamps
4. Analyzes transcript, identifies top segments
5. **For each clip:**
   - Generates "Why" justification first
   - Extracts transcript for exact timestamp range
   - Downloads video using those exact timestamps
6. Returns summary with folder location

**User**: Get 3 clips about "startup funding" from https://youtube.com/watch?v=xyz789

**Claude**:
1. Same setup
2. Filters transcript for "startup", "funding", "invest", "raise" keywords
3. Scores segments with topic_match weighted higher
4. For each of 3 clips: Why → Transcript → Video
5. Returns summary
