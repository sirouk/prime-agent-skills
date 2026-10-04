# spawn-angle.py - reference script, NOT an installed Python skill.
#
# How to use: open this file, copy everything below this header, and paste it
# into the Python REPL (ipython tool) once per session. Then, in one REPL cell:
#
#     handles = [
#         await spawn_angle("a1-invert", "Assume the fix exists; test what must be true."),
#         await spawn_angle("a2-minimal", "Build the smallest failing case.", budget=30),
#     ]
#
# and end your turn. Replies arrive as messages. Read attempts/<angle-id>/REPORT.md.
# `rlm` is already in the REPL namespace. The `model` argument must be an exact
# selector returned by `await rlm.find_models(...)`.
# After a kernel restart, paste it again (or re-read it from disk).

import os, textwrap


async def spawn_angle(angle_id: str, angle_brief: str, budget: int = 40, model: str | None = None):
    workdir = f"./.deep-solve/attempts/{angle_id}"
    os.makedirs(workdir, exist_ok=True)
    prompt = textwrap.dedent(f"""
    You are one of several workers attacking the same hard problem from different angles.
    Read ./.deep-solve/PROBLEM.md first. Your angle: {angle_id}.

    Brief: {angle_brief}

    Rules:
    - Work only on your angle. Do not re-derive the whole problem.
    - Write everything that matters to {workdir}/REPORT.md as you go: method, commands run, raw observations,
      result (supported / refuted / inconclusive), confidence, and the single most useful next step.
      Put raw outputs and scripts in {workdir}/. The report must be readable without your context.
    - Use at most {budget} tool calls. If you run out, stop and report what you have.
    - Every assistant message must include a tool call until you send your final reply via
      `await agent_message.send(<message>, receiver_role="parent")`. A text-only message ends your
      session and I receive nothing. Reply even if partial. A partial reply beats no reply.
    - Post short status with `await rlm.progress_note(...)` at milestones.
    - Final reply: 10 lines max: verdict, key evidence, path to REPORT.md, recommended next step.
    """).strip()
    kwargs = {"name": angle_id}
    if model:
        kwargs["model"] = model
    return await rlm.spawn(prompt, **kwargs)
