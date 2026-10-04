# spawn-angle.py - reference script, NOT an installed Python skill.
#
# How to use: open this file, copy everything below this header, and paste it
# into the Python REPL (ipython tool) once per session. Then, in one REPL cell:
#
#     handles = [
#         await spawn_angle("a1-invert", "Assume the fix exists; test what must be true.",
#                           evidence_for="...", evidence_against="..."),
#         await spawn_angle("a2-minimal", "Build the smallest failing case.", budget=30,
#                           model="<exact selector from rlm.find_models>", thinking="high"),
#     ]
#
# and end your turn. Do not poll. While children run, the goal continuation is
# held and is delivered when the last child settles; replies and
# `[child-exited ...]` notices also wake you. Then read attempts/<angle-id>/REPORT.md.
#
# `rlm` is already in the REPL namespace. `model` must be an exact selector
# returned by `await rlm.find_models(...)`; `thinking` is a level the child model
# supports (off, minimal, low, medium, high, xhigh, max) or None to inherit.
# After a kernel restart or compaction, paste this again (or exec the file).
#
# Children see NOTHING of your context: not this skill, not the harness facts,
# not your reasoning. The prompt below is their whole world. Keep it complete.

import os, textwrap


async def spawn_angle(
    angle_id: str,
    angle_brief: str,
    *,
    evidence_for: str = "state what observation would support this angle",
    evidence_against: str = "state what observation would refute this angle",
    budget: int = 40,
    model: str | None = None,
    thinking: str | None = None,
    can_spawn_helpers: bool = False,
    extra: str = "",
):
    workdir = f"./.deep-solve/attempts/{angle_id}"
    os.makedirs(workdir, exist_ok=True)
    helpers = (
        "You may spawn at most 2 helper subagents of your own with `await rlm.spawn(prompt, name=...)` "
        "if a sub-question is independent and context-heavy; give them the same message rules you have."
        if can_spawn_helpers
        else "You cannot spawn subagents in this session (recursion depth limit). Do all work yourself."
    )
    prompt = textwrap.dedent(f"""
    You are one of several workers attacking the same hard problem from different angles.
    Your angle id: {angle_id}. Work only on this angle. Do not re-derive the whole problem.

    First read, in this order:
    1. ./.deep-solve/PROBLEM.md  (the problem, success criteria, constraints, known facts)
    2. ./.deep-solve/HYPOTHESES.md  (what other angles exist and which are already refuted; do not repeat a refuted one)
    3. ./.deep-solve/LOG.md  (the last two entries only: what was learned so far)

    Your angle: {angle_brief}

    Evidence rules, decided before you start:
    - This angle is SUPPORTED if you observe: {evidence_for}
    - This angle is REFUTED if you observe: {evidence_against}
    - Anything else is INCONCLUSIVE. Say so. Do not stretch weak evidence into a verdict.

    Method:
    - Reproduce or measure before you change anything. Record the baseline.
    - Prefer the cheapest experiment that can distinguish supported from refuted.
    - Check the givens: if a stated fact in PROBLEM.md looks false, test it and report that first.
    - Keep raw outputs, scripts, and data in {workdir}/. Summaries lie; keep the raw evidence.
    - {helpers}

    Report contract (write {workdir}/REPORT.md AS YOU GO, not at the end; a run can be cut off):
      # {angle_id}
      ## Verdict: supported | refuted | inconclusive   (confidence: low | medium | high)
      ## Method (what you did, in order)
      ## Commands run (exact)
      ## Raw observations (paste outputs or point to files in this directory)
      ## What this rules in or out
      ## Single best next step
      ## Open questions / assumptions I made
    The report must be readable by someone with none of your context.

    Message rules (mandatory):
    - Every assistant message must include a tool call until you send your final reply via
      `await agent_message.send(<message>, receiver_role="parent")`. A text-only message ends your
      session and I receive nothing.
    - Use at most {budget} tool calls. If you run out, stop, finish the report, and reply with what you have.
    - Reply even if partial. A partial reply beats no reply.
    - Post short status with `await rlm.progress_note("...")` at milestones (baseline done, experiment N done, report written).
    - Final reply, 10 lines max: verdict + confidence, the two strongest pieces of evidence, path to REPORT.md, recommended next step.
    {extra}
    """).strip()
    kwargs: dict = {"name": angle_id}
    if model:
        kwargs["model"] = model
    if thinking:
        kwargs["thinking"] = thinking
    return await rlm.spawn(prompt, **kwargs)


async def spawn_red_team(solution_summary: str, budget: int = 40, model: str | None = None, thinking: str | None = None):
    """Independent adversary. Has not seen your reasoning; gets only the solution and the criteria."""
    workdir = "./.deep-solve/attempts/red-team"
    os.makedirs(workdir, exist_ok=True)
    prompt = textwrap.dedent(f"""
    You are an adversarial reviewer. Your job is to BREAK a proposed solution, not to confirm it.

    Read ./.deep-solve/PROBLEM.md (success criteria and constraints) and ./.deep-solve/SOLUTION.md if present.
    Proposed solution, as the author states it: {solution_summary}

    Attack it:
    - Run ./.deep-solve/verify.sh yourself and read what it actually checks. List criteria it does NOT check.
    - Find inputs, edge cases, environments, or assumptions under which the solution fails or the criteria are not met.
    - For every failure you find, write a reproduction (script or exact steps) into {workdir}/ and reference it.
    - If you cannot break it after a real attempt, say exactly what you tried and why each attempt failed to break it.

    Write {workdir}/REPORT.md as you go:
      # red-team
      ## Verdict: broken | holds (so far) | cannot evaluate
      ## Failures found (each with a reproduction path)
      ## Criteria not covered by verify.sh
      ## Attacks tried that did not break it
      ## Residual risks

    Message rules (mandatory):
    - Every assistant message must include a tool call until you send your final reply via
      `await agent_message.send(<message>, receiver_role="parent")`. A text-only message ends your session and I receive nothing.
    - Use at most {budget} tool calls. Reply even if partial. A partial reply beats no reply.
    - Final reply, 10 lines max: verdict, the worst failure (if any) with its reproduction path, path to REPORT.md.
    """).strip()
    kwargs: dict = {"name": "red-team"}
    if model:
        kwargs["model"] = model
    if thinking:
        kwargs["thinking"] = thinking
    return await rlm.spawn(prompt, **kwargs)
