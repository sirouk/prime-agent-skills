---
description: Kick off a long, multi-angle attack on one hard problem using goal mode, parallel subagents, on-disk evidence, and the continual harness.
argument-hint: <one-line problem statement, or leave empty and paste the full problem next>
---
PROBLEM: $ARGUMENTS

If the line above is empty or clearly incomplete, the full problem statement is in the next user message or in `./.deep-solve/PROBLEM.md`. Read it first.

Load the `deep-solve` skill now: read its `SKILL.md` from the skills inventory (or run `/skill:deep-solve`) and follow it exactly, including its Freshness step. The skill is the single source of truth for the method.

Standing authorizations for this run, so you do not need to stop and ask:
- I am asking for a persistent goal. Create it with `await goal.create(objective)` as the skill describes. If a stale goal blocks it, tell me in one line and wait.
- Create and write under `./.deep-solve/` freely.
- Spawn subagents freely, within the harness depth limit, and pick different models or thinking levels for them when that helps.
- Trigger compaction and refinement yourself at round boundaries.
- Use web search.

Default budget: up to 6 exploration rounds unless I say otherwise. At the cap, stop, write `SOLUTION.md`, and report the best supported result and what was ruled out. Do not call `goal.complete()` unless the success criteria are actually met.

Do not ask me clarifying questions up front. Make the smallest reasonable assumption, write it in `PROBLEM.md` under "Assumptions", and start. Ask me only if a decision is both blocking and irreversible.

Begin at step 1 of the skill.
