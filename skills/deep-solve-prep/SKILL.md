---
name: deep-solve-prep
description: Runs a structured conversation that turns a vision, charter, or messy problem description into one or more sharp /deep-solve briefs, each with a single question, machine-checkable success criteria, data and constraints, and a verify.sh sketch. Use when the user says "help me prepare a deep-solve", "turn this into a deep-solve prompt", "is this ready for /deep-solve", "scope this problem", "write the brief", or pastes a long vision, mandate, or operating document and wants to attack it. Use before /deep-solve whenever the problem has more than one question, no checkable finish line, or unknown data and constraints.
---

# Deep-solve prep

`/deep-solve` is a one-shot engine for one problem with a checkable finish line. It punishes vague input: no `verify.sh` can exist for a vision, and a goal objective full of purpose words crowds out the domain vocabulary the harness ranks memories by. This skill is the conversation that turns what the user has (a vision, a charter, a frustration, a pile of history) into what `/deep-solve` needs. The product is a file, `./.deep-solve-prep/BRIEFS.md`, holding one or more briefs the user can fire with `/deep-solve` as they are.

This is a conversation, not a one-shot. Ask. Wait. Do not create a goal. Do not spawn angle children. Do not start solving the problem; the moment you catch yourself proposing a solution, write it down as a candidate hypothesis in the brief and return to the questions.

## Freshness

Resolve the directory containing this `SKILL.md`, then run its updater exactly once at the start of the invocation. In prime-agent, run it through the Python REPL as `await bash("python3 <skill-directory>/scripts/update_check.py --apply")`. The shell form is:

```bash
python3 <skill-directory>/scripts/update_check.py --apply
```

Resolve that path relative to this `SKILL.md`, not the working repository.

- `UP_TO_DATE`: continue.
- `UPDATED`: reread the updated `SKILL.md` and references from disk completely, then continue without restarting or asking.
- `LOCAL_DIRTY`: preserve the local skill, do not force an overwrite, state the skipped update briefly, and continue with the installed skill.
- `UNMANAGED`: continue; this copy is not self-updated.
- `ERROR`: state that freshness could not be verified and continue with the installed skill.

Never use `--force` unless the user explicitly authorizes overwriting local skill changes.

Reference files:
- [references/brief-template.md](references/brief-template.md): the exact shape of one brief and the readiness checklist.
- [references/question-bank.md](references/question-bank.md): the questions, by phase, with why each one matters.
- [references/example-vortex.md](references/example-vortex.md): a worked example: a seven-purpose trading-system charter decomposed into a phased plan and four briefs.

## The shape of a deep-solve-able problem

A brief is ready when all of these hold. Check them with the user, not by assumption.

1. **One question.** It can be stated in two sentences and answered supported / refuted / inconclusive.
2. **Machine-checkable criteria.** Someone could write `verify.sh` from them today. Numbers, thresholds, named inputs, named commands.
3. **Known inputs.** The data, code, or environment the work needs exists, is reachable from this machine, and its path and format are written down. If it is not here yet, bringing it here is a prerequisite task, not a brief.
4. **Explicit constraints.** What must not change. What is out of scope. What is forbidden (live capital, production writes, external side effects).
5. **A known-answer check.** At least one case where the right result is already known, so the verifier can be validated before it is trusted (a deliberately broken input it must reject; a trusted input it must accept).
6. **Ordering.** If this brief depends on another brief's output, that is written down and the other runs first.
7. **Bounded.** Round cap, time or token budget if the user has one, and what to do at the cap.
8. **Safe defaults.** Nothing in the brief needs a human decision mid-run except the irreversible ones, and those are named with "stop and ask".

Anything else the user cares about (vision, purpose, voice, long-term program) goes in a charter file, not in the brief. The brief cites the charter in one line.

## The conversation, in five phases

Keep one working file from the first turn: `./.deep-solve-prep/NOTES.md` (what you learned, in the user's words where possible) and, from phase 3 on, `./.deep-solve-prep/BRIEFS.md`. Context will be compacted; the files are the memory. Use the REPL to write them; do not keep them in your head.

Ask at most 5 questions per turn. Number them. Prefer questions whose answer changes what you would write. Skip anything you can find yourself (read the repo, list the data directory, run the existing tests) and say that you did.

### Phase 1. Saturate

Goal: understand what the user has, where it came from, and what hurts. Read before you ask.

- If a repo, directory, or document is mentioned, read it now: git history summary, directory layout, README, test inventory, the main entry points. Write what you found to `NOTES.md` under "What exists".
- Ask for the story in the user's words if they have not told it: origin, what changed over time, what works, what hurts, what was tried and abandoned.
- Separate the material into four lists in `NOTES.md`: **facts** (verifiable), **beliefs** (the user's judgments and hunches), **wants** (goals and purposes), **constraints** (hard limits). Read the lists back to the user in one short block and ask what is wrong.
- Spot vocabulary. Collect the distinctive domain terms (tool names, method names, identifiers, metrics). These go into every goal objective and memory title later, because the harness ranks by them.

### Phase 2. Decompose

Goal: find the separable questions inside the vision.

- List every distinct thing the user wants done. For each, classify it: **research question** (unknown answer, testable), **engineering task** (known how, needs doing), **prerequisite** (data, access, environment), **decision** (only the user can make it), **operations** (deploy, monitor, run). Only research questions become `/deep-solve` briefs. Say which items are which and why.
- Find the dependency order. Which question's answer do the others need? Usually a validation or measurement method comes first: without a trusted way to tell good from bad, every later brief's `verify.sh` is unfounded.
- For each candidate brief, propose the one-sentence question and ask the user to accept, sharpen, or split it. Split anything with "and" in the question.
- Flag anything that must never be automated without a human step (money, production data, irreversible deletes, messages to third parties). Write it under "Human gates" in `NOTES.md`.

### Phase 3. Sharpen each brief

Goal: make each brief pass the readiness checklist. Work on one brief at a time, in dependency order. Write it into `BRIEFS.md` using [references/brief-template.md](references/brief-template.md), then ask only about the blanks.

Questions that matter most here, roughly in order:
1. What is the known-good reference and the known-bad reference? (The verifier must accept one and reject the other.)
2. What are the numbers? Thresholds, windows, sizes, counts, time limits. "Durable" and "robust" are not numbers; ask what number would make the user say "yes, that is durable".
3. Where exactly are the inputs, and can this machine read them now? Ask for a path and a command that proves it (`ls`, `du -sh`, `head`). If the data is elsewhere, write "Prerequisite: bring <data> to <path>" and do not pretend the brief is ready.
4. What must not change during the run?
5. What is out of scope, even though it is tempting?
6. What is the budget: rounds, hours, tokens? What should happen at the cap?
7. Which existing code is trusted and must be reused, and which may be replaced?

Draft a `verify.sh` sketch for each brief: the checks it would run and what each check proves. Ask the user whether passing that script would convince them. If the answer is no, the criteria are not done.

### Phase 4. Review

Goal: catch the mistakes that kill a one-shot before it starts.

Read each brief against the checklist and against [references/question-bank.md](references/question-bank.md) "Red flags". Common ones:
- Purpose language in the question or criteria ("sustainable", "intelligent", "fruitful", "bless"). Move it to the charter.
- A criterion the agent could satisfy by changing the measurement instead of the system. Pin the measurement.
- A brief that needs data not yet on this machine.
- Two briefs that will modify the same code at the same time. Serialize them.
- An authorization in the brief that should be a human gate (anything touching capital, production, or deletion).
- Words that collide with the tool's own vocabulary. In prime-agent, "kernel" means the Python REPL kernel; "skill" means an installed skill; "goal" means the harness goal. Rename the user's concept in the brief ("Vortex core", not "kernel") and say why.

State the review findings as a short list and fix them in `BRIEFS.md`.

### Phase 5. Hand off

Produce, in `./.deep-solve-prep/`:
- `CHARTER.md`: the vision, purpose, constraints, and human gates, in the user's voice. One page. Each brief cites it in one line.
- `BRIEFS.md`: the briefs in run order, each pasteable as `/deep-solve <brief>`. Each brief's "Context" section tells the deep-solve agent to read `CHARTER.md` and `NOTES.md` first.
- `PLAN.md`: the phased sequence: prerequisites and engineering tasks that are not briefs, the briefs in order, the human gates, and what happens after the briefs (build sprints, deployment) so the user sees the whole road, not just the research.

Then tell the user, in this order: which brief to fire first and why; what they must do before firing it (prerequisites); the exact `/deep-solve` line to paste; and the one recommended launch (`prime-agent --thinking max`, optional `/rlm-max-depth 3` if the briefs want helpers). Offer to persist durable facts from `NOTES.md` as local harness memories so the deep-solve run starts with them in its digest; do it only if the user says yes. The `deep-solve` skill reads `./.deep-solve-prep/BRIEFS.md` and `CHARTER.md` when they exist, so leave them in place.

## Rules

- Never create a goal in this skill. Prep has no finish line that a goal should enforce; the user ends it.
- Never spawn children to "start exploring" during prep. One exception: a read-only repo or data survey that is large and independent may go to one child with the standard message contract ("every assistant message must include a tool call until you send your final reply via `await agent_message.send(<message>, receiver_role=\"parent\")`; a text-only message ends your session and I receive nothing; use at most N tool calls; reply even if partial").
- Keep the user's words. When you restate, quote. When you rename, say so and why.
- One brief per question. If the user insists on a combined brief, write it, then write the split version beneath it and recommend the split.
- Write to disk every turn. The conversation may outlive the context window.
- End every turn with the numbered questions still open, or with "ready to fire" and the exact line.
