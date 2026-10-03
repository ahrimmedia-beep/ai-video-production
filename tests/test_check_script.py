from pathlib import Path

import pytest

from tools.check_script import (
    DEFAULT_RULES,
    Report,
    Rules,
    TermRule,
    check,
    format_report,
    main,
    sections,
    split_sentences,
    unquoted,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_script.md"

# 84 plain words, about 30 s of voice: inside the 25-55 s window, so no length warning
FILLER = [
    "Our team answers every order on the same day and writes the details into a shared table.",
    "Each morning the owner reads a short summary of the night and plans the work for the day.",
    "Clients get a reply within minutes, even late in the evening, and the order stays on record.",
    "Most questions are about price, delivery time and pickup, so the answers are short and clear.",
    "Weekends work the same way, with no extra staff and no missed messages in the inbox.",
]


def body(*lines: str) -> list[str]:
    return [*lines, *FILLER]


def errors_for(*lines: str, rules: Rules = DEFAULT_RULES) -> list[str]:
    return check("video-01", body(*lines), rules).errors


def warnings_for(*lines: str, rules: Rules = DEFAULT_RULES) -> list[str]:
    return check("video-01", body(*lines), rules).warnings


# ---------- parsing ----------


def test_sections_keeps_only_spoken_lines():
    text = "\n".join([
        "# Title",
        "intro outside any section",
        "## video-01.wav",
        "**Voice**",
        "> a note",
        "*(pause)*",
        "# comment",
        "",
        "First line.",
        "Second line.",
        "---",
        "after the separator",
        "## video-02.wav",
        "Other video.",
        "## Notes",
        "not a video",
    ])
    assert sections(text) == {
        "video-01": ["First line.", "Second line."],
        "video-02": ["Other video."],
    }


def test_sections_on_fixture_file():
    secs = sections(FIXTURE.read_text(encoding="utf-8"))
    assert list(secs) == ["video-01", "video-02"]
    assert secs["video-01"][0].startswith("Most orders")
    assert secs["video-02"][0] == "9 out of 10 calls go unanswered."


def test_split_sentences_on_end_marks_and_capitals():
    lines = ["One thing. Two things!", "Three? four stays. “Quoted” starts here… Done."]
    assert split_sentences(lines) == [
        "One thing.",
        "Two things!",
        "Three? four stays.",
        "“Quoted” starts here…",
        "Done.",
    ]


def test_split_sentences_keeps_question_inside_quote():
    assert split_sentences(["A client asks “Can I come at eight?” and gets an answer."]) == [
        "A client asks “Can I come at eight?” and gets an answer."
    ]


@pytest.mark.parametrize("text", ['He said "why?" twice', "He said “why?” twice", "He said «why?» twice"])
def test_unquoted_empties_all_quote_styles(text):
    assert "?" not in unquoted(text)
    assert unquoted(text).startswith("He said ") and unquoted(text).endswith(" twice")


# ---------- errors ----------


def test_clean_text_passes():
    r = check("video-01", body("Most orders come in the evening."))
    assert r.ok
    assert r.warnings == []
    assert r.hook == "Most orders come in the evening."


def test_empty_section_is_an_error():
    r = check("video-03", [])
    assert not r.ok
    assert r.errors == ["no text"]


@pytest.mark.parametrize("hook", ["40% of calls are missed.", "Twenty calls a day go nowhere."])
def test_hook_must_not_open_with_a_number(hook):
    assert any("hook starts with a number" in e for e in errors_for(hook))


def test_number_in_the_middle_is_fine():
    r = check("video-01", body("Calls come in the evening.", "We answered 40 of them."))
    assert r.ok


def test_rhetorical_question_is_an_error_but_quoted_question_is_not():
    assert any("rhetorical question" in e for e in errors_for("Calls come in.", "Who answers them?"))
    assert errors_for("Calls come in.", "A client asks “Who answers?” and waits.") == []


def test_slop_phrase_is_an_error():
    errs = errors_for("Calls come in.", "Let's break it down in today's world.")
    assert any('"let\'s break it down"' in e for e in errs)
    assert any('"in today\'s world"' in e for e in errs)


def test_curly_apostrophe_is_matched_too():
    assert any("filler" in e for e in errors_for("Calls come in.", "It’s not about price."))


def test_banned_claim_is_an_error():
    assert any("banned claim" in e for e in errors_for("Calls come in.", "Nine out of ten clients agree."))


def test_banned_claims_are_configurable():
    rules = Rules(banned_claims=("pays off in a month",))
    assert any("banned claim" in e for e in errors_for("Calls come in.", "It pays off in a month.", rules=rules))
    assert not any("banned claim" in e for e in errors_for("Calls come in.", "Nine out of ten agree.", rules=rules))


def test_term_rule_and_its_exception():
    assert any('"bot"' in e for e in errors_for("Calls come in.", "Our bot answers."))
    assert any('"system"' in e for e in errors_for("Calls come in.", "Our system answers."))
    assert errors_for("Calls come in.", "The system does the routine work for you.") == []


def test_custom_term_rule():
    rules = Rules(terms=(TermRule(r"\bcheap\b", '"cheap": say "affordable"'),))
    assert any('"cheap"' in e for e in errors_for("Calls come in.", "A cheap option.", rules=rules))
    # the default "bot" rule is replaced, not merged
    assert errors_for("Calls come in.", "Our bot answers.", rules=rules) == []


def test_condition_that_leads_nowhere():
    errs = errors_for("Calls come in.", "If you run a shop — this is for you.")
    assert any("condition leads nowhere" in e for e in errs)


# ---------- warnings ----------


def test_long_hook_is_a_warning():
    hook = " ".join(["word"] * 23) + "."
    assert any("long hook (23 words)" in w for w in warnings_for(hook))


def test_vague_pronoun_start_is_a_warning_except_product_intro():
    assert any('starts with "they"' in w for w in warnings_for("Calls come in.", "They wait for an answer."))
    assert warnings_for("Calls come in.", "This is an AI assistant for small shops.") == []


def test_not_x_but_y_is_a_warning():
    ws = warnings_for("Calls come in.", "We sell time, but not hours.", "Not price, but speed.")
    assert sum("not X, but Y" in w for w in ws) == 1


def test_weak_word_is_a_warning():
    assert any('"allows"' in w for w in warnings_for("Calls come in.", "The tool allows faster answers."))


def test_three_short_sentences_in_a_row():
    ws = warnings_for("Calls come in.", "Nobody answers.", "Clients leave.", "Money goes.")
    assert any("three short telegraphic sentences" in w for w in ws)


def test_three_sentences_with_the_same_start():
    ws = warnings_for("We call back fast.", "We write the order down.", "We send a summary.")
    assert any('three sentences in a row start with "we"' in w for w in ws)


def test_length_estimate_and_limits():
    r = check("video-01", ["Short text here."])
    assert r.n_words == 3
    assert r.seconds == pytest.approx(3 / 2.8)
    assert any("too short" in w for w in r.warnings)

    long = check("video-01", FILLER * 3)
    assert long.n_words == 3 * check("video-01", FILLER).n_words
    assert any("too long" in w for w in long.warnings)


def test_words_per_second_is_configurable():
    r = check("video-01", body("Calls come in."), Rules(words_per_sec=1.0))
    assert r.seconds == r.n_words
    assert any("too long" in w for w in r.warnings)


# ---------- output and CLI ----------


def test_format_report_lists_errors_and_warnings():
    r = Report("video-07", hook="Hi.", errors=["bad"], warnings=["hmm"], n_words=10, seconds=3.6)
    out = format_report(r)
    assert out.splitlines()[0].startswith("❌ video-07: 1 errors, 1 warnings, 10 words, about 4 s")
    assert "   ❌ bad" in out
    assert "   ⚠️ hmm" in out


def test_main_on_fixture(capsys):
    assert main([str(FIXTURE)]) == 1
    out = capsys.readouterr().out
    assert "✅ video-01: 0 errors, 0 warnings" in out
    assert "❌ video-02: 7 errors" in out


def test_main_single_clean_section(capsys):
    assert main([str(FIXTURE), "video-01"]) == 0
    assert "video-02" not in capsys.readouterr().out


def test_main_unknown_section(capsys):
    assert main([str(FIXTURE), "video-09"]) == 1
    assert 'no "## video-09.wav" section' in capsys.readouterr().out


def test_main_without_arguments_prints_usage():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert "Usage" in str(exc.value.code)
