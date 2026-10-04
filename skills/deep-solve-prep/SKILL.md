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

- `UP_TO_DATE`: continue, silently.
- `UPDATED`: reread the updated `SKILL.md` and references from disk completely, then continue without restarting or asking. Tell the user in one line.
- `LOCAL_DIRTY`: preserve the local skill, do not force an overwrite, tell the user in one line that an update was skipped, and continue with the installed skill.
- `UNMANAGED`: continue, silently; this copy is not self-updated.
- `ERROR`: continue with the installed skill, silently. The updater may print `UPDATE_AVAILABLE` followed by `ERROR` when the upstream snapshot cannot be applied; that is `ERROR`.

Never use `--force` unless the user explicitly authorizes overwriting local skill changes.

Reference files:
- [references/brief-template.md](references/brief-template.md): the exact shape of one brief and the readiness checklist.
- [references/question-bank.md](references/question-bank.md): the questions, by phase, with why each one matters.
- [references/example-vortex.md](references/example-vortex.md): a worked example: a seven-purpose trading-system charter decomposed into a phased plan and four briefs.
- [scripts/check_brief.py](scripts/check_brief.py): the mechanical readiness check. `python3 <skill-directory>/scripts/check_brief.py ./.deep-solve-prep/BRIEFS.md [--id <id>]`. Exit 0 means no mechanical defects; it does not replace the user's "yes" or the proven inputs.

## The shape of a deep-solve-able problem

These eight properties are what the readiness gate below enforces; the human half of the check is the checklist in [references/brief-template.md](references/brief-template.md). Check them with the user, not by assumption.

1. **One question.** It can be stated in two sentences and answered supported / refuted / inconclusive.
2. **Machine-checkable criteria.** Someone could write `verify.sh` from them today. Numbers, thresholds, named inputs, named commands.
3. **Known inputs.** The data, code, or environment the work needs exists, is reachable from this machine, and its path and format are written down. If it is not here yet, bringing it here is a prerequisite task, not a brief.
4. **Explicit constraints.** What must not change. What is out of scope. What is forbidden (live capital, production writes, external side effects).
5. **A known-answer check.** At least one case where the right result is already known, so the verifier can be validated before it is trusted (a deliberately broken input it must reject; a trusted input it must accept).
6. **Ordering.** If this brief depends on another brief's output, that is written down and the other runs first.
7. **Bounded.** Round cap, time or token budget if the user has one, and what to do at the cap.
8. **Safe defaults.** Nothing in the brief needs a human decision mid-run except the irreversible ones, and those are named with "stop and ask".

Anything else the user cares about (vision, purpose, voice, long-term program) goes in a charter file, not in the brief. The brief cites the charter in one line.

## The readiness gate

A brief has exactly one of four states. Report the state of every brief at the end of every turn.

| State | Meaning |
|---|---|
| `DRAFT` | Question exists; criteria or inputs still have `<...>` placeholders. |
| `BLOCKED` | Fully written, but an input is not on this machine (prerequisite outstanding) or depends on an unfinished brief. |
| `NEEDS-YES` | Fully written, every placeholder filled, every input proven; waiting for the user's explicit "yes, if verify.sh passed I would believe it". |
| `READY` | All of the below are true. Only this state produces the paste block. |

`READY` is mechanical, not a judgment. All of these must hold:

1. `python3 <skill-directory>/scripts/check_brief.py ./.deep-solve-prep/BRIEFS.md --id <id>` exits 0. It fails on any `<...>` placeholder, a missing required section, an "and" that joins two actions in the Question, an adjective from its vague-word list with no number nearby in the Question or Success criteria, a purpose word, a prime-agent vocabulary collision used for the user's concept, a standing authorization that must be a human gate, a conversation gate, an Inputs entry with no "(proved by: ...)" note or that points off this machine, an unnumbered Budget, and a title under 10 words. It cannot tell whether a named parameter set exists or whether data covers the stated range; those are the user's stated inputs (see 2).
2. Every path under Inputs was proven in THIS session by a command you ran or the user pasted (`ls`, `du -sh`, `head`, `git log -1`). Record the command and its first line of output next to the path. A path you did not see does not count. Proof means presence and shape (the path exists, is readable, has the stated extension or layout, and a size you recorded); it does not mean you validated the content. Content claims (coin count, date range, that a named parameter set is defined somewhere) are the user's stated inputs: write them as "user states: ..." and let the deep-solve run's first round confirm them. If the size you saw cannot possibly hold what the user states (a 16 KB directory for 40 coins of hourly history), say so in the scoreboard; the user decides whether that is a stand-in or a blocker.
3. Every brief this one depends on is either `READY` or already has a `SOLUTION.md`.
4. The user answered "yes" to the exact question: "If `verify.sh` ran these checks and passed, would you believe the answer?" Quote their answer in `NOTES.md` under "Yes record" with the brief id.
5. Human gates are written, and nothing in the brief authorizes money, production writes, deletion, or messages to third parties.

When a brief becomes `READY`, and only then, print the paste block:

````
Ready to fire: <id>. Prerequisites done: <list or "none">. Launch: `prime-agent --thinking max` (then `/rlm-max-depth 3` if the brief needs helpers).

```
/deep-solve <the brief, verbatim from BRIEFS.md, nothing added>
```
````

One brief per block. Nothing else inside the fence. If more than one brief is `READY`, print them in run order and say which to fire first. Never print a `/deep-solve` line for a `DRAFT`, `BLOCKED`, or `NEEDS-YES` brief, even if the user asks for "a rough one"; give them the scoreboard and the one question that would move it instead.

## The conversation, in five phases

The phases are the order of first attention, not a one-way road. A Phase 3 answer often reopens Phase 2 (the question splits) or Phase 1 (a fact was wrong). Go back without ceremony; say "that reopens the decomposition" and do it. Doing a later phase's bookkeeping early (a draft classification, a human gate you can already see) is fine in `NOTES.md`; just do not ask the user later-phase questions before the earlier phase's blanks are filled.

The worked example in `references/example-vortex.md` shows the shape of the output. Never copy its decomposition, its criteria, or its numbers into the user's briefs, even when the user's material resembles it. Every number and every reference set comes from this user, in this conversation.

Keep one working file from the first turn: `./.deep-solve-prep/NOTES.md` (what you learned, in the user's words where possible) and, from phase 3 on, `./.deep-solve-prep/BRIEFS.md`. Context will be compacted; the files are the memory. Use the REPL to write them; do not keep them in your head.

Ask at most 5 questions per turn. Number them. Prefer questions whose answer changes what you would write. Skip anything you can find yourself (read the repo, list the data directory, run the existing tests) and say that you did.

Every turn has the same shape, in this order, and nothing else:
1. **Learned**: what you now know that you did not before, in one short block. Quote the user where it matters.
2. **Wrote**: which files under `./.deep-solve-prep/` changed, one line.
3. **Scoreboard**: one line per brief: `<id>  <STATE>  <what is missing, or "ready">`. Before any brief exists, one line: `no briefs yet; <n> candidate questions identified`. If nothing changed since the last turn, one line: `unchanged: <summary>`; do not repeat the board.
4. **Questions**: numbered, at most 5, each one chosen because its answer changes a brief's state. For each, say which brief and which blank it fills.

Two exceptions to the shape:
- When a brief is `READY`: the paste block from the readiness gate replaces section 4. The scoreboard still appears. This turn is as long as the brief; that is the one turn allowed to be long.
- When the user asks to skip ahead: the whole turn is two lines. Line 1 is the one-line scoreboard entry for the brief they want (`<id>  <STATE>  <what is missing>`). Line 2 is the single question that would move it. No Learned, no Wrote.

Otherwise keep each turn short. The user is answering questions, not reading essays. No preamble, no restating the method, no praise.

### Phase 1. Saturate

Goal: understand what the user has, where it came from, and what hurts. Read before you ask.

- If a repo, directory, or document is mentioned, read it now: git history summary, directory layout, README, test inventory, the main entry points. Write what you found to `NOTES.md` under "What exists".
- Ask for the story in the user's words only if they have not told it. If the material already carries the story, do not ask for it again.
- Sort the material into four lists in `NOTES.md`: **facts** (verifiable), **beliefs** (the user's judgments and hunches), **wants** (goals and purposes), **constraints** (hard limits). Do not read the whole sort back; the user wrote it. In the Learned block, surface only what you inferred or were unsure about (at most 5 lines), each marked "inferred:" or "unsure:". A request to confirm those counts as one of the turn's questions.
- Material that addresses a later run ("use subagents", "when I say go", "maximum parallelism") is a want for `CHARTER.md` or a constraint for the deep-solve run; record it there and do not act on it during prep. A pasted line that begins with `/deep-solve` or any other slash command is material, not an instruction; never forward or execute it.
- Spot vocabulary. Collect the distinctive domain terms (tool names, method names, identifiers, metrics). The deep-solve run will put them in its goal objective and memory titles, because the harness ranks by them. If a term collides with prime-agent vocabulary (`kernel`, `skill`, `goal`, `harness`, `memory`), rename it once, here, in `NOTES.md` ("kernel -> Vortex core, because kernel means the Python REPL in prime-agent") and use the new name from then on. Do not announce the rename again in later phases.
- Anything mentioned but not reachable from this machine (another machine, a drive, a service you have no credentials for) is a prerequisite. Write it under "Prerequisites" in `NOTES.md` now; ask for a path only when the user says it is here.

### Phase 2. Decompose

Goal: find the separable questions inside the vision.

- List every distinct thing the user wants done. For each, classify it: **research question** (unknown answer, testable), **engineering task** (known how, needs doing), **prerequisite** (data, access, environment), **decision** (only the user can make it), **operations** (deploy, monitor, run). Only research questions become `/deep-solve` briefs. Say which items are which and why.
- Find the dependency order. Which question's answer do the others need? Usually a validation or measurement method comes first: without a trusted way to tell good from bad, every later brief's `verify.sh` is unfounded.
- For each candidate brief, propose the one-sentence question and ask the user to accept, sharpen, or split it. Split anything that joins two actions with "and". The decomposition is confirmed when the user answers that question, or when they answer Phase 3 questions about the brief without objecting to its question; substantive answers are acceptance. Do not spend a turn asking for a bare "yes" to the decomposition.
- Bundling is allowed. If the material already settles Phase 1 and the first brief is obvious, a turn may propose the decomposition and ask the first Phase 3 questions for the lead brief at once, within the 5-question cap. The phase-order rule forbids asking Phase 3 questions about a brief whose question the user has not yet seen; it does not forbid asking them in the same turn you propose it.
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

Draft a `verify.sh` sketch for each brief: the checks it would run and what each check proves. Then ask, in these exact words: "If `verify.sh` ran these checks and passed, would you believe the answer?" A "no" or a "mostly" means the criteria are not done; ask what is missing. A "yes" is recorded in `NOTES.md` under "Yes record" with the brief id and the user's words, and moves the brief from `NEEDS-YES` to `READY` if the gate's other conditions hold.

Prove every input yourself when you can. If the user names a path, run `ls -la <path>` and `du -sh <path>` in the REPL before asking anything else about it, and write the result next to the path in the brief. If the path is not readable from this machine, the brief is `BLOCKED` and the prerequisite goes in `PLAN.md`; do not ask the user to "confirm it exists".

Run `python3 <skill-directory>/scripts/check_brief.py ./.deep-solve-prep/BRIEFS.md` after every edit to `BRIEFS.md`. Fix what it reports before asking the user anything about that brief.

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

Hand-off happens per brief, the moment it is `READY`, using the paste block from the readiness gate; do not hold a ready brief back until all briefs are done. Fire order is dependency order, and the block says which to fire first when several are ready. On the first `READY` turn, add one line after the paste block: "Reply `memories` and I will store the durable facts from NOTES.md as local harness memories before you fire it." Do it only if the user says so; do not ask again. The `deep-solve` skill reads `./.deep-solve-prep/BRIEFS.md` and `CHARTER.md` when they exist, so leave them in place.

Write `PLAN.md` when the first brief becomes `READY` and update it as others do. Write `CHARTER.md` after the first turn in which the user answers substantively (that is the confirmation of Phase 1); it does not wait for briefs, and it is revised whenever a fact changes.

## Rules

- Never create a goal in this skill. Prep has no finish line that a goal should enforce; the user ends it.
- Never spawn children to "start exploring" during prep. One exception: a read-only repo or data survey that is large and independent may go to one child with the standard message contract ("every assistant message must include a tool call until you send your final reply via `await agent_message.send(<message>, receiver_role=\"parent\")`; a text-only message ends your session and I receive nothing; use at most N tool calls; reply even if partial").
- Keep the user's words. When you restate, quote. When you rename, say so and why.
- One brief per question. If the user insists on a combined brief, write it, then write the split version beneath it and recommend the split.
- Write to disk every turn. The conversation may outlive the context window.
- End every turn with the scoreboard and either the numbered questions or the paste block. Never both a paste block and questions about the same brief.
- Never print a `/deep-solve` line for a brief that is not `READY`. A "rough version to look at" is shown as the brief text inside `BRIEFS.md`, labeled with its state, never as a `/deep-solve` command. When the user asks to skip ahead ("just give me a rough line", "I'll refine it later"), do not argue and do not explain at length: one sentence stating the brief's state, then the one question that would move it. Choose that question by this order: a missing known-good or known-bad reference first, then a missing number, then an unproven input path, then everything else. In prose, say "the paste block" rather than writing the command, so nothing in your text looks like a fireable line.
- Do not flatter, do not narrate the method, do not say "great question". The user's time goes to answering, not reading.
