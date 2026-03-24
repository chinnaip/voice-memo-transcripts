# voice-memo-transcripts

Auto-saved transcripts from macOS Voice Memos app.

---

## Overview

`save_transcript.py` finds your most recently modified Voice Memo, extracts the
auto-generated speech-to-text transcript, writes it to `transcripts/`, and
commits and pushes the file to `main` — all with a single command.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| macOS | Script reads from `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/` |
| Python 3.6+ | Ships with macOS; verify with `python3 --version` |
| git | Must be configured with push access to this repo (SSH key or HTTPS token) |
| Voice Memos | At least one recording with a completed transcript |

---

## Setup

### 1 — Clone the repo (first time only)

```bash
git clone git@github.com:chinnaip/voice-memo-transcripts.git
cd voice-memo-transcripts
```

### 2 — Verify git push access

```bash
git push --dry-run origin main
```

If this fails, configure your credentials:

- **SSH**: add your public key to GitHub → Settings → SSH keys.
- **HTTPS**: create a Personal Access Token (PAT) with `repo` scope at
  GitHub → Settings → Developer settings → Personal access tokens, then run:
  ```bash
  git remote set-url origin https://<YOUR_TOKEN>@github.com/chinnaip/voice-memo-transcripts.git
  ```

### 3 — Allow Voice Memos transcription (macOS)

Open the **Voice Memos** app, record something, and wait for the transcription
indicator to disappear. The JSON sidecar is written automatically by the app
after transcription completes — the script needs this file to exist.

---

## Usage

```bash
# Normal run: extract, write, commit, and push
python3 save_transcript.py

# Preview mode (no files written, no git commands run)
python3 save_transcript.py --dry-run
```

### Example output

```
Latest recording : /Users/alice/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/A1B2C3D4-.../Recording.m4a
Timestamp        : 2026-03-24_143500
Sidecar JSON     : /Users/alice/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/A1B2C3D4-.../Recording.json
Transcript length: 312 characters

Wrote transcript : transcripts/2026-03-24_143500.txt
Committed and pushed: transcripts/2026-03-24_143500.txt
```

The resulting file `transcripts/2026-03-24_143500.txt` will contain the full
transcript as a single block of text, e.g.:

```
So today I wanted to talk about the new feature we shipped last week...
```

---

## Idempotency

Re-running the script for the same recording is safe. If
`transcripts/<timestamp>.txt` is already committed, the script prints
`Nothing to do.` and exits without creating a duplicate commit.

---

## Troubleshooting

| Error message | Likely cause | Fix |
|---|---|---|
| `Recordings directory not found` | Running on non-macOS or the app was never opened | Must run on macOS with Voice Memos installed |
| `No .m4a files found` | No recordings exist yet | Record at least one memo in the Voice Memos app |
| `No JSON sidecar found` | Transcription not finished | Open Voice Memos, wait for transcription to complete, then re-run |
| `Unexpected JSON structure` | Apple changed the JSON schema | Open an issue in this repo with the contents of the `.json` file |
| `STChunks is empty` | Transcription still in progress | Wait a few seconds and re-run |
| `git command failed` on push | No push credentials | Follow the **Setup → Verify git push access** steps above |

---

## Repository layout

```
voice-memo-transcripts/
├── save_transcript.py   ← the script
├── transcripts/         ← generated transcript files (committed by the script)
└── README.md
```
