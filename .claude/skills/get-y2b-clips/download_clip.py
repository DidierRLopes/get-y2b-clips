#!/usr/bin/env python3
"""Download a video clip from YouTube with retry logic and progress reporting.

Usage:
    python download_clip.py --url URL --start HH:MM:SS --end HH:MM:SS --output PATH [options]

Example:
    python download_clip.py \
        --url "https://www.youtube.com/watch?v=abc123" \
        --start 00:08:56 \
        --end 00:10:31 \
        --output "clips/01_my_clip/My Clip Video.mp4"
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


# ANSI colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_stage(stage: str, message: str):
    """Print a stage indicator."""
    print(f"{Colors.CYAN}{Colors.BOLD}[{stage}]{Colors.RESET} {message}")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.GREEN}  ✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}  ✗ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}  ⚠ {message}{Colors.RESET}")


def print_info(message: str):
    """Print an info message."""
    print(f"{Colors.DIM}    {message}{Colors.RESET}")


def download_clip(
    url: str,
    start: str,
    end: str,
    output: str,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    quiet: bool = False
) -> bool:
    """Download a video clip with retry logic.

    Args:
        url: YouTube URL
        start: Start timestamp (HH:MM:SS)
        end: End timestamp (HH:MM:SS)
        output: Output file path
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        quiet: Suppress yt-dlp output

    Returns:
        True if successful, False otherwise
    """
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        'yt-dlp',
        '-f', 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        '--download-sections', f'*{start}-{end}',
        '--force-keyframes-at-cuts',
        '--merge-output-format', 'mp4',
        '-o', str(output_path),
        url
    ]

    if quiet:
        cmd.extend(['--quiet', '--no-warnings'])

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print_warning(f"Retry attempt {attempt}/{max_retries}...")
                time.sleep(retry_delay)

            result = subprocess.run(
                cmd,
                capture_output=quiet,
                text=True
            )

            if result.returncode == 0:
                # Verify file was created
                if output_path.exists():
                    size_mb = output_path.stat().st_size / (1024 * 1024)
                    print_success(f"Downloaded: {output_path.name} ({size_mb:.1f} MB)")
                    return True
                else:
                    print_error("Download completed but file not found")

            else:
                if quiet and result.stderr:
                    # Check for specific errors
                    if '403' in result.stderr or 'Forbidden' in result.stderr:
                        print_warning("YouTube returned 403 - will retry...")
                        continue
                    print_error(f"yt-dlp error: {result.stderr[:200]}")

        except Exception as e:
            print_error(f"Exception: {e}")

    print_error(f"Failed after {max_retries} attempts")
    return False


def main():
    parser = argparse.ArgumentParser(
        description='Download a video clip from YouTube with retry logic'
    )
    parser.add_argument('--url', '-u', required=True, help='YouTube URL')
    parser.add_argument('--start', '-s', required=True, help='Start timestamp (HH:MM:SS)')
    parser.add_argument('--end', '-e', required=True, help='End timestamp (HH:MM:SS)')
    parser.add_argument('--output', '-o', required=True, help='Output file path')
    parser.add_argument('--retries', '-r', type=int, default=3, help='Max retries (default: 3)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress yt-dlp output')

    args = parser.parse_args()

    print_stage("DOWNLOAD", f"Fetching clip {args.start} - {args.end}")

    success = download_clip(
        url=args.url,
        start=args.start,
        end=args.end,
        output=args.output,
        max_retries=args.retries,
        quiet=args.quiet
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
