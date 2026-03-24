#!/usr/bin/env python3
"""
save_transcript.py — Extract the latest macOS Voice Memo transcript and commit it.

Usage:
    python3 save_transcript.py          # normal run
    python3 save_transcript.py --dry-run  # preview without writing/committing

Requirements: Python 3.6+, git (configured with push access to this repo).
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECORDINGS_DIR = Path.home() / "Library" / "Group Containers" / \
    "group.com.apple.VoiceMemos.shared" / "Recordings"

REPO_ROOT = Path(__file__).resolve().parent
TRANSCRIPTS_DIR = REPO_ROOT / "transcripts"


def find_latest_m4a(recordings_dir: Path) -> Path:
    """Return the most recently modified .m4a file under recordings_dir."""
    m4a_files = list(recordings_dir.rglob("*.m4a"))
    if not m4a_files:
        sys.exit(
            f"ERROR: No .m4a files found under:\n  {recordings_dir}\n"
            "Make sure you have at least one Voice Memo recording on this Mac."
        )
    return max(m4a_files, key=lambda p: p.stat().st_mtime)


def find_sidecar_json(m4a_path: Path):
    """Return the .json sidecar that lives in the same directory as m4a_path, or None."""
    parent = m4a_path.parent
    json_files = list(parent.glob("*.json"))
    if not json_files:
        return None
    # If multiple JSON files exist pick the one with the most recent mtime.
    return max(json_files, key=lambda p: p.stat().st_mtime)


def extract_transcript_from_m4a(m4a_path: Path) -> str:
    """Extract transcript from the tsrp atom embedded in the .m4a file.

    Apple encodes transcripts as a JSON blob prefixed with 'tsrp' inside the
    MPEG-4 container. The JSON structure is:
      {"attributedString": {"runs": ["word", <index>, ...], "attributeTable": [...]}}
    Words occupy even indices of the runs array.
    """
    data = m4a_path.read_bytes()
    marker = b'tsrp'
    idx = data.find(marker)
    if idx == -1:
        return ""
    json_bytes = data[idx + len(marker):]
    brace_start = json_bytes.find(b'{')
    if brace_start == -1:
        return ""
    depth = 0
    for i, b in enumerate(json_bytes[brace_start:], brace_start):
        if b == ord('{'):
            depth += 1
        elif b == ord('}'):
            depth -= 1
            if depth == 0:
                raw = json_bytes[brace_start:i + 1].decode('utf-8', errors='replace')
                try:
                    obj = json.loads(raw)
                    attr = obj["attributedString"]
                    if isinstance(attr, list):
                        runs = attr
                    elif isinstance(attr, dict):
                        runs = attr.get("runs", [])
                    else:
                        return ""
                    words = [r for r in runs if isinstance(r, str)]
                    return " ".join(w.strip() for w in words if w.strip())
                except (json.JSONDecodeError, KeyError, TypeError):
                    return ""
    return ""


def extract_transcript(json_path: Path) -> str:
    """Parse the JSON sidecar and return the full transcript text."""
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    try:
        chunks = data["SpeechRecognitionResult"]["STChunks"]
    except (KeyError, TypeError):
        sys.exit(
            f"ERROR: Unexpected JSON structure in:\n  {json_path}\n"
            "Expected keys: SpeechRecognitionResult → STChunks"
        )

    if not chunks:
        sys.exit(
            f"ERROR: STChunks is empty in:\n  {json_path}\n"
            "The transcript may still be processing."
        )

    parts = [chunk.get("STString", "").strip() for chunk in chunks]
    return " ".join(p for p in parts if p)


def recording_timestamp(m4a_path: Path) -> str:
    """Return 'YYYY-MM-DD_HHMMSS' derived from the .m4a modification time (local time)."""
    mtime = m4a_path.stat().st_mtime
    dt = datetime.fromtimestamp(mtime)
    return dt.strftime("%Y-%m-%d_%H%M%S")


def transcript_already_committed(relative_path: str) -> bool:
    """Return True if the transcript file is already tracked by git (idempotency guard)."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative_path],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def git_run(*args):
    """Run a git command inside REPO_ROOT, raise on failure."""
    cmd = ["git", *args]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(
            f"ERROR: git command failed: {' '.join(cmd)}\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without writing or committing anything.")
    args = parser.parse_args()

    if not RECORDINGS_DIR.is_dir():
        sys.exit(
            f"ERROR: Recordings directory not found:\n  {RECORDINGS_DIR}\n"
            "This script must be run on macOS with the Voice Memos app installed."
        )

    # 1. Find the latest recording
    m4a_path = find_latest_m4a(RECORDINGS_DIR)
    timestamp = recording_timestamp(m4a_path)
    print(f"Latest recording : {m4a_path}")
    print(f"Timestamp        : {timestamp}")

    # 2. Extract transcript — try JSON sidecar first, fall back to tsrp atom
    json_path = find_sidecar_json(m4a_path)
    if json_path:
        print(f"Sidecar JSON     : {json_path}")
        transcript = extract_transcript(json_path)
    else:
        print("Sidecar JSON     : not found, trying tsrp atom in .m4a")
        transcript = extract_transcript_from_m4a(m4a_path)
        if not transcript:
            sys.exit(
                f"ERROR: No transcript found for:\n  {m4a_path}\n"
                "No JSON sidecar exists and no tsrp atom was found in the .m4a file.\n"
                "Try opening the Voice Memos app and waiting for transcription to finish."
            )
    print(f"Transcript length: {len(transcript)} characters")

    # 3. Determine output path
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    out_filename = f"{timestamp}.txt"
    out_path = TRANSCRIPTS_DIR / out_filename
    relative_out = str(out_path.relative_to(REPO_ROOT))

    if args.dry_run:
        print(f"\n[dry-run] Would write  : {relative_out}")
        print(f"[dry-run] Would commit : 'Add transcript {out_filename}'")
        print("\n--- Transcript preview (first 500 chars) ---")
        print(transcript[:500])
        return

    # 4. Idempotency: skip if already committed
    if out_path.exists() and transcript_already_committed(relative_out):
        print(f"\nTranscript already committed ({relative_out}). Nothing to do.")
        return

    # Write the transcript file
    out_path.write_text(transcript, encoding="utf-8")
    print(f"\nWrote transcript : {relative_out}")

    # 5. Commit and push
    git_run("add", relative_out)
    git_run("commit", "-m", f"Add transcript {out_filename}")
    git_run("push", "origin", "main")
    print(f"Committed and pushed: {relative_out}")


if __name__ == "__main__":
    main()
