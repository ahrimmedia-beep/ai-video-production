#!/usr/bin/env python3
"""Automatic check of a video script before it goes to review.

It catches, mechanically, the things a reviewer has already rejected before:
filler phrases, slogans, rhetorical questions, claims the brief does not allow,
vague pronouns. Whether the hook actually works is still checked by a person.

The script file holds one section per video, each starting with a
"## video-NN.wav" heading. Lines starting with "#", "**", "*(" or ">" are notes
and are skipped. A "---" line ends the section.

Usage:
  python3 tools/check_script.py SCRIPTS.md [video-NN ...]
Without names, every "## video-NN.wav" section is checked.
Exit code 1 if there are errors.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Errors: phrases a reviewer has already rejected as filler or slogans.
SLOP = (
    "not just", "it's not about", "the problem isn't", "not only", "the most expensive",
    "money on the table", "leaving money", "gold mine", "the new oil", "game changer",
    "let's break it down", "today i'll tell you", "imagine", "pay attention", "here's the thing",
    "spoiler", "the truth is", "sound familiar", "recognize yourself", "it's important to note",
    "it's worth noting", "in today's world", "in the era of", "transform", "ecosystem", "synerg",
    "magic", "level up", "next level", "unique", "innovati", "revolution", "unprecedented",
    "hurry", "spots are running out", "today only", "i guarantee",
    "neighbo",  # say "competitors" instead
)
# Errors: numbers and claims the product brief does not allow. Set per project.
BANNED_CLAIMS = ("9 out of 10", "nine out of ten")
# The hook must not open with a number or a statistic. "one" is left out on purpose:
# in English it is too often a pronoun ("no one", "the one").
NUMBER_WORDS = (r"\d|\b(zero|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|"
                r"forty|fifty|hundred|thousands?|millions?|percent|dollars?)\b")
# Warnings: worth a second look, say it simpler or more concretely.
WEAK = ("allows", "ensures", "serves as", "carries out", "plays a role", "always", "never", "all businesses")


@dataclass(frozen=True)
class TermRule:
    """A word the brand voice does not use. `unless` is a phrase where it is allowed."""

    pattern: str
    message: str
    unless: str | None = None


TERMS = (
    TermRule(r"\bbots?\b", '"bot": say "AI assistant"'),
    TermRule(r"\bsystems?\b", '"system": only in "the system does the routine work", otherwise "AI assistant"',
             unless=r"the (ai )?system does the routine"),
)


@dataclass(frozen=True)
class Rules:
    slop: tuple[str, ...] = SLOP
    banned_claims: tuple[str, ...] = BANNED_CLAIMS
    weak: tuple[str, ...] = WEAK
    terms: tuple[TermRule, ...] = TERMS
    number_words: str = NUMBER_WORDS
    # sentences that may start with "this": the product introduction
    intro_starts: tuple[str, ...] = ("this is an ai",)
    words_per_sec: float = 2.8  # speaker's pace, measured on a real take: 172 words in about 62 s of speech
    max_hook_words: int = 22
    max_seconds: float = 55  # target is 35-50 s of voice
    min_seconds: float = 25


DEFAULT_RULES = Rules()


@dataclass
class Report:
    name: str
    hook: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    n_words: int = 0
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------- parsing ----------


def sections(text: str) -> dict[str, list[str]]:
    """Map "video-NN" to the spoken lines of its section."""
    out: dict[str, list[str]] = {}
    name = None
    for line in text.splitlines():
        m = re.match(r"##\s+(video-\d+)", line)
        if m:
            name = m.group(1)
            out[name] = []
            continue
        if line.startswith("## "):
            name = None
        if name is None:
            continue
        s = line.strip()
        if s == "---":
            name = None
            continue
        if not s or s.startswith(("#", "**", "*(", ">")):
            continue
        out[name].append(s)
    return out


def split_sentences(lines: list[str]) -> list[str]:
    text = " ".join(lines)
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"“«])", text)
    return [p.strip() for p in parts if p.strip()]


QUOTED = re.compile(r"«[^»]*»|“[^”]*”|\"[^\"]*\"")


def unquoted(s: str) -> str:
    """The sentence with quoted speech emptied, so a question inside a quote is allowed."""
    return QUOTED.sub('""', s)


# ---------- the check ----------


def check(name: str, lines: list[str], rules: Rules = DEFAULT_RULES) -> Report:
    sents = split_sentences(lines)
    report = Report(name)
    errors, warns = report.errors, report.warnings

    if not sents:
        errors.append("no text")
        return report

    hook = report.hook = lines[0]
    if re.search(rules.number_words, hook.lower()):
        errors.append(f'hook starts with a number or a fact: "{hook}". Move numbers to the middle of the video')
    if len(hook.split()) > rules.max_hook_words:
        warns.append(f'long hook ({len(hook.split())} words): "{hook}"')

    for s in sents:
        low = s.lower().replace("’", "'")
        q = unquoted(s)
        if "?" in q:
            errors.append(f'rhetorical question (a question is allowed only inside a quote): "{s}"')
        for p in rules.slop:
            if p in low:
                errors.append(f'"{p}" is filler or a slogan: "{s}"')
        for p in rules.banned_claims:
            if p in low:
                errors.append(f'banned claim "{p}" (product brief): "{s}"')
        for t in rules.terms:
            if re.search(t.pattern, low) and not (t.unless and re.search(t.unless, low)):
                errors.append(f'{t.message}: "{s}"')
        if re.search(r"\bif (you have|you)\b[^.!?]*—\s*(there|this|that|they|them)\b", low):
            errors.append(f'the condition leads nowhere or the pronoun has no referent: "{s}"')
        if re.match(r"(there|this|that|they|them|it)\b", low) and not low.startswith(rules.intro_starts):
            warns.append(f'sentence starts with "{low.split()[0]}". Is it clear what it points to? "{s}"')
        if re.search(r"\bnot\s+\w+,\s+but\s", low):
            warns.append(f'"not X, but Y" construction. Is it needed? "{s}"')
        for p in rules.weak:
            if p in low:
                warns.append(f'"{p}": say it simpler or more concretely? "{s}"')

    short_run = 0
    for s in sents:
        short_run = short_run + 1 if len(s.split()) <= 3 else 0
        if short_run == 3:
            warns.append(f'three short telegraphic sentences in a row, the last one: "{s}"')
    starts = [s.split()[0].lower().strip("\"“«—,") for s in sents]
    for i in range(len(starts) - 2):
        if starts[i] == starts[i + 1] == starts[i + 2]:
            warns.append(f'three sentences in a row start with "{starts[i]}"')

    low_all = " ".join(sents).lower()
    report.n_words = len(re.findall(r"[\w'’-]+", low_all))
    report.seconds = report.n_words / rules.words_per_sec
    if report.seconds > rules.max_seconds:
        warns.append(f"too long: {report.n_words} words, about {report.seconds:.0f} s of voice (target 35-50 s)")
    if report.seconds < rules.min_seconds:
        warns.append(f"too short: {report.n_words} words, about {report.seconds:.0f} s of voice")
    return report


def format_report(r: Report) -> str:
    mark = "✅" if r.ok else "❌"
    lines = [f'{mark} {r.name}: {len(r.errors)} errors, {len(r.warnings)} warnings, '
             f'{r.n_words} words, about {r.seconds:.0f} s · hook: "{r.hook}"']
    lines += [f"   ❌ {e}" for e in r.errors]
    lines += [f"   ⚠️ {w}" for w in r.warnings]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        sys.exit(__doc__)
    secs = sections(Path(args[0]).read_text(encoding="utf-8"))
    names = args[1:] or list(secs)
    ok = True
    for n in names:
        if n not in secs:
            print(f'❌ {n}: no "## {n}.wav" section in the file')
            ok = False
            continue
        report = check(n, secs[n])
        print(format_report(report))
        ok = report.ok and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
