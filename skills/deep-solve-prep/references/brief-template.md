# Brief template

One brief per question. Copy the block, fill every `<...>`, and delete the guidance lines in parentheses. A brief with any `<...>` left is not ready.

````
/deep-solve <One-line title: what is being built or decided, with the domain's exact names in it>

Context: read ./.deep-solve-prep/CHARTER.md and ./.deep-solve-prep/NOTES.md first. This brief is <id> of <n>; it depends on <ids or "nothing">.

Question: <Two sentences at most. Answerable as supported / refuted / inconclusive. No "and".>

Success criteria (these become verify.sh):
1. <Known-bad rejection: the verifier rejects <named deliberately-wrong input> because <measurable reason>.>
2. <Known-good acceptance: the verifier accepts <named trusted input> on <named held-out data>.>
3. <Threshold: <metric> <comparator> <number> on <data> over <window>.>
4. <Self-test: every check has a unit test with a synthetic known-answer case.>
5. <Runtime bound: the whole verify.sh completes in under <N> <unit> on this machine.>

Inputs (all present on this machine now):
- <path>: <what it is, format, size, date range>  (proved by: <command the user ran>)
- <repo path @ branch/commit>: <what is trusted in it and must be reused>

Constraints:
- Do not modify <paths or components>.
- Read-only access to <data>.
- No <exchange / network / production / external side effect>.
- <Anything the measurement must hold fixed so the agent cannot pass by changing the ruler.>

Out of scope: <list; the tempting adjacent work that belongs to another brief>.

Known candidate hypotheses (start here, do not stop here): <the user's and your hunches, one line each>.

Budget: <N> rounds. At the cap: write SOLUTION.md with the best supported result and what was ruled out; report; do not call goal.complete() unless every criterion passes.

Human gates (stop and ask, do not assume): <irreversible decisions, if any; else "none">.
````

## Readiness states

Every brief is in exactly one state: `DRAFT` (placeholders remain), `BLOCKED` (an input is not on this machine, or a dependency is unfinished), `NEEDS-YES` (complete and proven, waiting for the user's "yes, if verify.sh passed I would believe it"), `READY`. Only `READY` produces a `/deep-solve` paste block.

`READY` requires all of: `check_brief.py` exits 0 for this brief; every Inputs path was proven in this session by a command whose first output line is recorded next to it; every dependency is `READY` or has a `SOLUTION.md`; the user's "yes" is quoted in `NOTES.md` under "Yes record"; human gates are written and nothing authorizes money, production writes, deletion, or third-party messages.

The mechanical half is a script: `python3 <skill-directory>/scripts/check_brief.py ./.deep-solve-prep/BRIEFS.md --id <id>`. It checks the required sections (`Context:`, `Question:`, `Success criteria`, `Inputs`, `Constraints:`, `Out of scope:`, `Budget:`, `Human gates`), placeholders, two-action "and" in the question, vague adjectives without a number, purpose words, prime-agent vocabulary collisions, forbidden standing authorizations, conversation gates, unproven inputs, and an unnumbered budget. A fully worked `READY` brief is in [brief-example-ready.md](brief-example-ready.md); it passes the checker.

## Readiness checklist

The human half. Check every line with the user. Mark each `[x]` only when it is true on this machine today.

- [ ] One question, no "and", answerable supported / refuted / inconclusive.
- [ ] Every criterion has a number, a named input, or a named command. No "robust", "durable", "intelligent", "sustainable" without a definition in numbers.
- [ ] A known-bad input the verifier must reject, and a known-good input it must accept, are both named.
- [ ] Every input path exists here now (the user ran a command that proved it), or the brief is marked "blocked by prerequisite <x>" and is not fired.
- [ ] The measurement is pinned: the agent cannot pass by changing how the metric is computed.
- [ ] "Do not modify" and "out of scope" are written.
- [ ] Dependencies on other briefs are written and respected in run order.
- [ ] Round cap and cap behavior are written.
- [ ] Human gates are written; nothing touching money, production, deletion, or third parties is auto-authorized.
- [ ] No purpose language in question or criteria; it lives in CHARTER.md.
- [ ] No collisions with tool vocabulary (prime-agent: kernel, skill, goal, harness, memory). Renamed and noted.
- [ ] The user has said: "if verify.sh passed, I would believe it."

## Vocabulary note

The deep-solve agent writes the goal objective from the brief. The harness ranks memories by term overlap with that objective (goal terms weigh 3.0; terms must be at least 4 characters). The brief's title and question should therefore carry the real names: tool names (`vectorbtpro`, `numba`), method names (`CPCV`, `walk-forward`, `PBO`), identifiers (strategy names, dataset names, metric names). A brief whose title is "make the system durable" ranks nothing.
