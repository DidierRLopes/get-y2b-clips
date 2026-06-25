#!/usr/bin/env python3
"""Render extracted insights to a .txt file AND pretty-print them in the terminal.

Reads an insights JSON file (produced after analyzing a YouTube transcript) and:
  1. Writes a clean, human-readable .txt report
  2. Prints the same content to the terminal with color highlighting

Usage:
    python render_insights.py --insights insights.json --output insights.txt

Expected insights.json schema:
{
  "source": {
    "url": "https://www.youtube.com/watch?v=...",
    "title": "Video Title",
    "channel": "Channel Name",
    "duration_minutes": 92
  },
  "insights": [
    {
      "title": "Short headline for the idea",
      "claim": "1-3 sentence statement of the insight as the speaker frames it.",
      "timestamp": "00:14:05",
      "type": "controversial" | "novel" | "both",
      "controversy_score": 0-10,
      "novelty_score": 0-10,
      "why": "Why this is controversial and/or appears to be a genuinely new idea.",
      "web_contrast": "What the conventional / commonly-found-online view is, and how this differs.",
      "quote": "Optional short verbatim quote from the transcript."
    }
  ]
}
"""

import argparse
import json
import sys
from pathlib import Path


class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def type_label(t: str) -> str:
    return {
        'controversial': 'CONTROVERSIAL',
        'novel': 'NOVEL IDEA',
        'both': 'CONTROVERSIAL + NOVEL',
    }.get((t or '').lower(), (t or 'INSIGHT').upper())


def build_lines(data: dict, color: bool) -> list[str]:
    """Build the report lines. If color=True, include ANSI codes (terminal)."""
    def c(code: str, text: str) -> str:
        return f"{code}{text}{C.RESET}" if color else text

    src = data.get('source', {})
    insights = data.get('insights', [])
    lines: list[str] = []

    lines.append(c(C.BOLD + C.CYAN, "=" * 70))
    lines.append(c(C.BOLD + C.CYAN, "  KEY INSIGHTS — controversial & seemingly-novel ideas"))
    lines.append(c(C.BOLD + C.CYAN, "=" * 70))
    if src.get('title'):
        lines.append(c(C.BOLD, f"Video:    {src['title']}"))
    if src.get('channel'):
        lines.append(f"Channel:  {src['channel']}")
    if src.get('url'):
        lines.append(c(C.DIM, f"URL:      {src['url']}"))
    if src.get('duration_minutes'):
        lines.append(c(C.DIM, f"Duration: {src['duration_minutes']} min"))
    lines.append(f"Insights: {len(insights)}")
    lines.append("")

    if not insights:
        lines.append(c(C.YELLOW, "No qualifying insights found."))
        return lines

    for i, ins in enumerate(insights, 1):
        ctype = type_label(ins.get('type', ''))
        cscore = ins.get('controversy_score')
        nscore = ins.get('novelty_score')
        ts = ins.get('timestamp', '')

        header = f"[{i}] {ins.get('title', 'Untitled')}"
        lines.append(c(C.BOLD + C.MAGENTA, header))

        meta_bits = [ctype]
        if cscore is not None:
            meta_bits.append(f"controversy {cscore}/10")
        if nscore is not None:
            meta_bits.append(f"novelty {nscore}/10")
        if ts:
            meta_bits.append(f"@ {ts}")
        lines.append(c(C.YELLOW, "    " + "  |  ".join(meta_bits)))
        lines.append("")

        if ins.get('claim'):
            lines.append(c(C.GREEN, "    CLAIM:"))
            for wl in _wrap(ins['claim']):
                lines.append("    " + wl)
            lines.append("")

        if ins.get('why'):
            lines.append(c(C.GREEN, "    WHY IT STANDS OUT:"))
            for wl in _wrap(ins['why']):
                lines.append("    " + wl)
            lines.append("")

        if ins.get('web_contrast'):
            lines.append(c(C.GREEN, "    VS. THE COMMON ONLINE VIEW:"))
            for wl in _wrap(ins['web_contrast']):
                lines.append("    " + wl)
            lines.append("")

        if ins.get('quote'):
            lines.append(c(C.DIM, '    "' + ins['quote'].strip().strip('"') + '"'))
            lines.append("")

        lines.append(c(C.DIM, "    " + "-" * 60))
        lines.append("")

    return lines


def _wrap(text: str, width: int = 76) -> list[str]:
    words = str(text).split()
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out or [""]


def main():
    ap = argparse.ArgumentParser(description="Render insights to .txt and terminal")
    ap.add_argument('--insights', '-i', required=True, help='Path to insights.json')
    ap.add_argument('--output', '-o', required=True, help='Path to output .txt')
    ap.add_argument('--no-print', action='store_true',
                    help='Only write the file, do not print to terminal')
    args = ap.parse_args()

    ins_path = Path(args.insights)
    if not ins_path.exists():
        print(f"Error: insights file not found: {ins_path}", file=sys.stderr)
        sys.exit(1)

    with open(ins_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Plain text -> file
    plain = build_lines(data, color=False)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(plain) + "\n")

    # Colorized -> terminal
    if not args.no_print:
        print("\n".join(build_lines(data, color=True)))

    print(f"\n{C.GREEN}  ✓ Saved insights to {out_path}{C.RESET}")


if __name__ == '__main__':
    main()
