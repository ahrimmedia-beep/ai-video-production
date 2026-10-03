#!/usr/bin/env python3
"""Hook gate: the first seconds of a video must start with the voice.

Rule: the speaker's voice is heard from 0.0 s and the first line is the hook.
The wording of the hook changes from video to video for A/B tests.
Silence at the start means the video is rejected.

Checks on the first 5 seconds:
  1. silence at the very start longer than 0.3 s                -> reject
  2. first word (Whisper) later than 0.8 s                      -> reject
  3. a gap without voice longer than 1.0 s inside 0-5 s         -> reject
  4. fewer than 4 words, or Whisper hallucinations on silence
     ("Thank you", "Subtitles by ...")                          -> reject

Usage: python3 tools/check_hook.py video.mp4 [more.mp4 ...]
Exit code 1 if at least one video is rejected.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WINDOW = 5.0
MAX_LEAD_SILENCE = 0.3
MAX_FIRST_WORD = 0.8
MAX_GAP = 1.0
MIN_WORDS = 4
MODEL = "mlx-community/whisper-large-v3-turbo"

# Phrases Whisper tends to invent on silence or music instead of real speech.
HALLUCINATIONS = re.compile(r"thank you|thanks for watching|subtitles by|to be continued", re.I)


# ---------- pure functions (no I/O) ----------


def parse_lead_silence(ffmpeg_log: str, window: float = WINDOW) -> float:
    """Length of the silence at the very start, read from ffmpeg `silencedetect` output.

    Returns 0.0 when the audio does not start with silence, and `window`
    when the silence starts at 0 and never ends inside the analysed window.
    """
    starts = [float(x) for x in re.findall(r"silence_start: ([-\d.e]+)", ffmpeg_log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", ffmpeg_log)]
    if starts and starts[0] <= 0.05:
        return ends[0] if ends else window
    return 0.0


def words_from_whisper(data: dict) -> list[dict]:
    """Flat list of word dicts ({"word", "start", "end"}) from Whisper JSON output."""
    return [w for s in data.get("segments", []) for w in s.get("words", [])]


def joined_text(words: list[dict]) -> str:
    return "".join(w["word"] for w in words).strip()


def find_problems(lead_silence: float, words: list[dict]) -> list[str]:
    """All reasons to reject the opening of a video. An empty list means it passes."""
    errors = []
    if lead_silence > MAX_LEAD_SILENCE:
        errors.append(f"silence at the start {lead_silence:.2f} s (limit {MAX_LEAD_SILENCE})")
    if not words:
        errors.append(f"no voice in the first {WINDOW:.0f} s")
    else:
        if words[0]["start"] > MAX_FIRST_WORD:
            errors.append(f"first word at {words[0]['start']:.2f} s (limit {MAX_FIRST_WORD})")
        for a, b in zip(words, words[1:], strict=False):
            if b["start"] - a["end"] > MAX_GAP:
                errors.append(f"gap without voice {a['end']:.1f}-{b['start']:.1f} s")
        text = joined_text(words)
        if len(words) < MIN_WORDS or HALLUCINATIONS.search(text):
            errors.append("no real speech in the first 5 s (too few words or a Whisper hallucination)")
    return errors


def format_report(name: str, words: list[dict], errors: list[str]) -> str:
    head = joined_text(words)[:90] if words else "-"
    mark = "❌ REJECT" if errors else "✅ ok"
    lines = [f"{mark}  {name}", f'   voice 0-5 s: "{head}"']
    lines += [f"   ❌ {e}" for e in errors]
    return "\n".join(lines)


# ---------- I/O: ffmpeg and Whisper ----------


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def extract_head(video: Path, wav: Path) -> bool:
    """Cut the first WINDOW seconds of audio to a 16 kHz mono WAV. False if there is no audio."""
    r = run(["ffmpeg", "-hide_banner", "-y", "-t", str(WINDOW), "-i", str(video),
             "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    return r.returncode == 0 and wav.exists()


def lead_silence(wav: Path) -> float:
    log = run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af",
               "silencedetect=n=-40dB:d=0.2", "-f", "null", "-"]).stderr
    return parse_lead_silence(log)


def transcribe(wav: Path) -> list[dict]:
    """Word timings from mlx-whisper. An empty list if Whisper wrote nothing."""
    with tempfile.TemporaryDirectory() as d:
        run(["mlx_whisper", str(wav), "--model", MODEL, "--word-timestamps", "True",
             "--output-format", "json", "--output-dir", d, "--verbose", "False"])
        js = next(Path(d).glob("*.json"), None)
        if not js:
            return []
        data = json.loads(js.read_text())
    return words_from_whisper(data)


def check(video: Path) -> bool:
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "head.wav"
        if not extract_head(video, wav):
            print(f"❌ {video.name}: no audio track")
            return False
        sil = lead_silence(wav)
        ws = transcribe(wav)

    errors = find_problems(sil, ws)
    print(format_report(video.name, ws, errors))
    return not errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        sys.exit(__doc__)
    # a list, not a generator: every file is checked even after the first failure
    ok = all([check(Path(p)) for p in args])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
