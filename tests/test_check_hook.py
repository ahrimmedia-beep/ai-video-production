import json
import subprocess
from pathlib import Path

import pytest

from tools import check_hook
from tools.check_hook import (
    find_problems,
    format_report,
    joined_text,
    main,
    parse_lead_silence,
    words_from_whisper,
)


def w(word: str, start: float, end: float) -> dict:
    return {"word": word, "start": start, "end": end}


GOOD_WORDS = [w(" Every", 0.10, 0.40), w(" evening", 0.42, 0.80), w(" calls", 0.85, 1.20),
              w(" go", 1.25, 1.40), w(" nowhere.", 1.45, 2.00)]

SILENCE_AT_START = """\
[silencedetect @ 0x6000] silence_start: -0.0213
[silencedetect @ 0x6000] silence_end: 0.412 | silence_duration: 0.433
[silencedetect @ 0x6000] silence_start: 3.1
[silencedetect @ 0x6000] silence_end: 3.4 | silence_duration: 0.3
"""


# ---------- parse_lead_silence ----------


def test_lead_silence_is_the_first_silence_end():
    assert parse_lead_silence(SILENCE_AT_START) == pytest.approx(0.412)


def test_no_lead_silence_when_first_silence_starts_later():
    log = "silence_start: 1.25\nsilence_end: 1.6 | silence_duration: 0.35\n"
    assert parse_lead_silence(log) == 0.0


def test_silence_that_never_ends_fills_the_window():
    assert parse_lead_silence("silence_start: 0\n") == check_hook.WINDOW
    assert parse_lead_silence("silence_start: 0\n", window=3.0) == 3.0


def test_no_silence_at_all():
    assert parse_lead_silence("size=N/A time=00:00:05.00 bitrate=N/A\n") == 0.0


# ---------- words ----------


def test_words_from_whisper_flattens_segments():
    data = {"segments": [{"words": GOOD_WORDS[:2]}, {"words": GOOD_WORDS[2:]}, {"text": "no words key"}]}
    assert words_from_whisper(data) == GOOD_WORDS
    assert words_from_whisper({}) == []


def test_joined_text():
    assert joined_text(GOOD_WORDS) == "Every evening calls go nowhere."


# ---------- find_problems ----------


def test_good_opening_passes():
    assert find_problems(0.1, GOOD_WORDS) == []


def test_long_silence_at_start():
    errs = find_problems(0.45, GOOD_WORDS)
    assert errs == ["silence at the start 0.45 s (limit 0.3)"]


def test_no_voice():
    assert find_problems(5.0, []) == [
        "silence at the start 5.00 s (limit 0.3)",
        "no voice in the first 5 s",
    ]


def test_first_word_too_late():
    words = [w(" Late", 0.95, 1.2), *GOOD_WORDS[1:]]
    errs = find_problems(0.0, words)
    assert errs == ["first word at 0.95 s (limit 0.8)"]


def test_gap_inside_the_window():
    words = [*GOOD_WORDS[:3], w(" after", 2.6, 2.9), w(" pause.", 2.9, 3.2)]
    errs = find_problems(0.0, words)
    assert errs == ["gap without voice 1.2-2.6 s"]


def test_too_few_words():
    errs = find_problems(0.0, GOOD_WORDS[:3])
    assert errs == ["no real speech in the first 5 s (too few words or a Whisper hallucination)"]


@pytest.mark.parametrize("phrase", [" Thank you.", " Thanks for watching!", " Subtitles by the community"])
def test_whisper_hallucination(phrase):
    words = [*GOOD_WORDS[:4], w(phrase, 1.5, 2.0)]
    assert any("Whisper hallucination" in e for e in find_problems(0.0, words))


def test_format_report():
    ok = format_report("v.mp4", GOOD_WORDS, [])
    assert ok.splitlines() == ["✅ ok  v.mp4", '   voice 0-5 s: "Every evening calls go nowhere."']
    bad = format_report("v.mp4", [], ["no voice in the first 5 s"])
    assert bad.splitlines() == ["❌ REJECT  v.mp4", '   voice 0-5 s: "-"', "   ❌ no voice in the first 5 s"]


# ---------- I/O wrappers with a fake ffmpeg / whisper ----------


def fake_run(stderr: str = "", whisper: dict | None = None, ffmpeg_ok: bool = True):
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[0] == "mlx_whisper" and whisper is not None:
            out = Path(cmd[cmd.index("--output-dir") + 1])
            (out / "head.json").write_text(json.dumps(whisper))
        if cmd[0] == "ffmpeg" and "-vn" in cmd and ffmpeg_ok:
            Path(cmd[-1]).write_bytes(b"RIFF")
        return subprocess.CompletedProcess(cmd, 0 if ffmpeg_ok else 1, stdout="", stderr=stderr)

    run.calls = calls
    return run


def test_extract_head_builds_ffmpeg_command(monkeypatch, tmp_path):
    run = fake_run()
    monkeypatch.setattr(check_hook, "run", run)
    wav = tmp_path / "head.wav"
    assert check_hook.extract_head(Path("in.mp4"), wav)
    cmd = run.calls[0]
    assert cmd[:6] == ["ffmpeg", "-hide_banner", "-y", "-t", "5.0", "-i"]
    assert cmd[-5:] == ["-ac", "1", "-ar", "16000", str(wav)]


def test_extract_head_without_audio(monkeypatch, tmp_path):
    monkeypatch.setattr(check_hook, "run", fake_run(ffmpeg_ok=False))
    assert not check_hook.extract_head(Path("in.mp4"), tmp_path / "head.wav")


def test_lead_silence_reads_ffmpeg_stderr(monkeypatch):
    run = fake_run(stderr=SILENCE_AT_START)
    monkeypatch.setattr(check_hook, "run", run)
    assert check_hook.lead_silence(Path("head.wav")) == pytest.approx(0.412)
    assert "silencedetect=n=-40dB:d=0.2" in run.calls[0]


def test_transcribe_reads_whisper_json(monkeypatch):
    monkeypatch.setattr(check_hook, "run", fake_run(whisper={"segments": [{"words": GOOD_WORDS}]}))
    assert check_hook.transcribe(Path("head.wav")) == GOOD_WORDS


def test_transcribe_without_output(monkeypatch):
    monkeypatch.setattr(check_hook, "run", fake_run(whisper=None))
    assert check_hook.transcribe(Path("head.wav")) == []


# ---------- check() and main() ----------


@pytest.fixture
def fake_media(monkeypatch):
    """Replace ffmpeg and Whisper with canned results, per video file name."""
    results = {
        "good.mp4": (0.05, GOOD_WORDS),
        "silent.mp4": (1.2, [w(" Late", 1.3, 1.6)]),
    }

    def extract_head(video, wav):
        if video.name == "no-audio.mp4":
            return False
        wav.write_text(video.name)
        return True

    monkeypatch.setattr(check_hook, "extract_head", extract_head)
    monkeypatch.setattr(check_hook, "lead_silence", lambda wav: results[wav.read_text()][0])
    monkeypatch.setattr(check_hook, "transcribe", lambda wav: results[wav.read_text()][1])


def test_check_good_video(fake_media, capsys):
    assert check_hook.check(Path("good.mp4"))
    assert capsys.readouterr().out.startswith("✅ ok  good.mp4")


def test_check_rejects_silent_start(fake_media, capsys):
    assert not check_hook.check(Path("silent.mp4"))
    out = capsys.readouterr().out
    assert "❌ REJECT  silent.mp4" in out
    assert "silence at the start 1.20 s" in out
    assert "first word at 1.30 s" in out


def test_check_without_audio_track(fake_media, capsys):
    assert not check_hook.check(Path("no-audio.mp4"))
    assert "no-audio.mp4: no audio track" in capsys.readouterr().out


def test_main_checks_every_file(fake_media, capsys):
    assert main(["silent.mp4", "good.mp4"]) == 1
    out = capsys.readouterr().out
    assert "silent.mp4" in out and "good.mp4" in out
    assert main(["good.mp4"]) == 0


def test_main_without_arguments_prints_usage():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert "Usage" in str(exc.value.code)
