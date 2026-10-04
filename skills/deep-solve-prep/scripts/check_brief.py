#!/usr/bin/env python3
"""Mechanical readiness check for /deep-solve briefs in a BRIEFS.md file.

Usage:
    python3 check_brief.py ./.deep-solve-prep/BRIEFS.md [--id DS-1] [--json]

Exit 0: no mechanical defects in the selected brief(s).
Exit 1: defects found (listed, one per line, as `<id>: <defect>`).
Exit 2: the file or the brief id could not be read.

A brief is the text from one line starting with `/deep-solve ` up to the next
such line or the end of the file. Its id is taken from the Context line
("This brief is <id> of <n>"), else from a preceding markdown heading, else
its 1-based position.

This check is necessary, not sufficient. It cannot know whether the inputs are
really on the machine or whether the user said "yes"; the skill records those
in NOTES.md. Python 3.9+, stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "Context:",
    "Question:",
    "Success criteria",
    "Inputs",
    "Constraints:",
    "Out of scope:",
    "Budget:",
    "Human gates",
]

# Adjectives that mean nothing to verify.sh unless a number sits next to them.
VAGUE_WORDS = [
    "durable", "robust", "reliable", "scalable", "performant", "efficient", "fast",
    "good", "better", "best", "optimal", "optimized", "high quality", "high-quality",
    "clean", "simple", "elegant", "sustainable", "stable", "secure", "accurate",
    "correct", "intelligent", "smart", "adaptive", "self-aware", "fruitful",
]

# Words that belong in CHARTER.md, never in a brief.
PURPOSE_WORDS = [
    "bless", "blessing", "history", "legacy", "soul", "vision", "mission", "passion",
    "dream", "destiny", "god", "love", "kids", "children", "world-class", "revolutionary",
]

# prime-agent's own vocabulary; a brief that uses these for the user's concepts confuses the agent.
TOOL_WORDS = {
    "kernel": "prime-agent's Python REPL kernel",
    "skill": "an installed prime-agent skill",
    "harness": "the prime-agent continual harness",
    "subagent": "a prime-agent child session",
    "memory": "a prime-agent harness memory",
}

# Authorizations that must be human gates, never standing permissions.
FORBIDDEN_AUTH = [
    r"\bdeploy(?:ment)? to prod", r"\bput capital", r"\blive (?:capital|trading|money)",
    r"\breal money", r"\bplace (?:an )?orders?\b", r"\bexecute trades?\b",
    r"\bdelete the old\b", r"\brm -rf\b", r"\bdrop (?:table|database)\b",
    r"\bemail\b", r"\bnotify the team\b", r"\bpush to (?:main|master|production)\b",
]

# "Ask me", "when I say go": conversation gates that do not belong in a one-shot brief.
CONVERSATION_GATES = [r"\bask me\b", r"\bwhen I say go\b", r"\bwait for my\b", r"\bcheck with me first\b"]

PLACEHOLDER = re.compile(r"<[^<>\n]{1,80}>")
ACTION_VERBS = (
    "deploy|build|ship|put|make|design|redesign|implement|migrate|purge|delete|remove|"
    "write|create|launch|monitor|trade|optimi[sz]e|refactor|rewrite|test|measure|evaluate|"
    "compare|find|decide|choose|select|validate|prove|fix|clean|document"
)
NUMBER = re.compile(r"\d")


def split_briefs(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.lstrip().startswith("/deep-solve ")]
    briefs: list[tuple[str, str]] = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end])
        # stop at a closing code fence so the fence and prose after it are not part of the brief
        fence = body.find("\n```")
        if fence != -1:
            body = body[:fence]
        match = re.search(r"This brief is\s+([A-Za-z0-9][A-Za-z0-9._-]*)\s+of\b", body)
        if match:
            brief_id = match.group(1)
        else:
            heading = next(
                (lines[j] for j in range(start - 1, -1, -1) if lines[j].startswith("#")), None
            )
            brief_id = heading.lstrip("# ").strip() if heading else str(n + 1)
        briefs.append((brief_id, body))
    return briefs


def section(body: str, name: str) -> str:
    """Text from the line containing `name` up to the next required-section header."""
    start = body.find(name)
    if start == -1:
        return ""
    rest = body[start + len(name):]
    ends = [rest.find(other) for other in REQUIRED_SECTIONS if other != name and rest.find(other) != -1]
    return rest[: min(ends)] if ends else rest


def check_brief(brief_id: str, body: str) -> list[str]:
    defects: list[str] = []
    title = body.splitlines()[0].strip()
    title_words = title[len("/deep-solve "):].split()
    if len(title_words) < 8:
        defects.append(f"title has {len(title_words)} words; under 8 means it carries too little domain vocabulary")

    for name in REQUIRED_SECTIONS:
        if name not in body:
            defects.append(f"missing section '{name.rstrip(':')}'")

    for match in PLACEHOLDER.finditer(body):
        token = match.group(0)
        if token.lower() in {"<none>"}:
            continue
        defects.append(f"placeholder still present: {token}")

    question = section(body, "Question:")
    if question:
        q = question.strip()
        # 'and' joining two actions is two questions; 'and' inside a list of techniques is one.
        if re.search(r"\band (?:then|also|afterwards)\b", q, re.IGNORECASE) or re.search(
            rf",?\s+and\s+(?:{ACTION_VERBS})\b", q, re.IGNORECASE
        ):
            defects.append("Question joins two actions with 'and': split into two briefs or rephrase as one question")
        if q.count("?") > 1:
            defects.append("Question asks more than one thing (multiple '?')")
        if len(q.split(". ")) > 2 and len(q) > 400:
            defects.append("Question is longer than two sentences")

    criteria = section(body, "Success criteria")
    # Check each field on its own, with list markers removed, so '1.' never counts as a number.
    for label, field in (("Question", question), ("Success criteria", criteria)):
        stripped = re.sub(r"^\s*\d+[.)]\s*", "", field, flags=re.MULTILINE)
        for word in VAGUE_WORDS:
            for match in re.finditer(rf"\b{re.escape(word)}\b", stripped, re.IGNORECASE):
                window = stripped[max(0, match.start() - 80): match.end() + 80]
                if not NUMBER.search(window):
                    defects.append(f"'{word}' in {label} with no number within 80 characters")
                    break

    if criteria:
        numbered = re.findall(r"^\s*\d+\.", criteria, re.MULTILINE)
        if len(numbered) < 3:
            defects.append(f"Success criteria has {len(numbered)} numbered items; need at least 3 (known-bad rejection, known-good acceptance, a threshold)")
        low = criteria.lower()
        if not re.search(r"\breject", low):
            defects.append("Success criteria has no known-bad rejection check (a verifier that never rejects proves nothing)")
        if not re.search(r"\baccept", low):
            defects.append("Success criteria has no known-good acceptance check")

    lowered = body.lower()
    for word in PURPOSE_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            defects.append(f"purpose word '{word}' belongs in CHARTER.md, not in the brief")

    for word, meaning in TOOL_WORDS.items():
        # allow the skill's own references like 'deep-solve skill' and 'harness memories' in the Context line
        hits = [m for m in re.finditer(rf"\b{word}s?\b", lowered)]
        for m in hits:
            context = lowered[max(0, m.start() - 30): m.end() + 30]
            if "deep-solve" in context or "prime-agent" in context or "rlm" in context:
                continue
            defects.append(f"'{word}' collides with {meaning}; rename the user's concept (e.g. 'core', 'engine') and note it in CHARTER.md")
            break

    for pattern in FORBIDDEN_AUTH:
        m = re.search(pattern, lowered)
        if m:
            gates = section(body, "Human gates").lower()
            if m.group(0) not in gates:
                defects.append(f"'{m.group(0)}' appears outside Human gates; money, production, deletion, and third-party actions are human gates")

    for pattern in CONVERSATION_GATES:
        if re.search(pattern, lowered):
            defects.append(f"conversation gate '{pattern.strip(chr(92) + 'b')}' in a brief; prep is the conversation, the brief is fired after it")

    inputs = section(body, "Inputs")
    if inputs and not re.search(r"\(proved by:", inputs):
        defects.append("Inputs have no '(proved by: <command>)' note; every path must be proven in this session")
    if inputs and re.search(r"\b(?:old machine|other machine|will bring|can get|not yet|somewhere)\b", inputs.lower()):
        defects.append("Inputs mention data that is not on this machine; that is a prerequisite, and the brief is BLOCKED")

    budget = section(body, "Budget:")
    if budget and not NUMBER.search(budget):
        defects.append("Budget has no number (rounds, hours, or tokens)")
    if budget and "goal.complete()" not in budget:
        defects.append("Budget does not state the cap behavior ('do not call goal.complete() unless every criterion passes')")

    return defects


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--id", dest="brief_id", default=None, help="check only this brief id")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    briefs = split_briefs(text)
    if not briefs:
        print(f"ERROR: no '/deep-solve ' lines found in {args.path}", file=sys.stderr)
        return 2
    if args.brief_id is not None:
        briefs = [(i, b) for i, b in briefs if i == args.brief_id]
        if not briefs:
            print(f"ERROR: no brief with id {args.brief_id!r}", file=sys.stderr)
            return 2

    report = {brief_id: check_brief(brief_id, body) for brief_id, body in briefs}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for brief_id, defects in report.items():
            if defects:
                for defect in defects:
                    print(f"{brief_id}: {defect}")
            else:
                print(f"{brief_id}: OK (no mechanical defects; still needs proven inputs and the user's yes)")
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
