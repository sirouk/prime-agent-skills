# Harness mechanics (prime-agent 0.9.8)

Verified facts that the deep-solve method relies on. Paths are relative to the prime-agent repository root. Do not extend this table with unverified claims.

| ID | Fact | Why it matters for deep-solve | Source file |
|---|---|---|---|
| H1 | The goal re-prompts the agent at each natural turn end until `goal.complete()` is called. | It is the engine of a long run. End turns while children work; the goal brings you back. | `crates/pa-core/src/session_engine/goal_driver.rs`, `crates/pa-daemon/src/goal_continuation.rs` |
| H2 | 3 consecutive no-output turns (no text, no tool call) end the goal (`CONTINUATION_NO_PROGRESS_CAP = 3`, retry backoff 10s, 20s, 40s). | Every turn must do something observable, or the run dies. | `crates/pa-core/src/session_engine/goal_driver/progress.rs` |
| H3 | Default RLM max depth is 2 (`DEFAULT_RLM_MAX_DEPTH = 2`). Raise with `/rlm-max-depth`. | Children can spawn helpers; grandchildren cannot. Plan angle trees to fit. | `crates/pa-daemon/src/rlm_children.rs` |
| H4 | The harness digest shows the top 3 entries per kind, each truncated to 140 characters. Entries are ranked by term overlap: goal objective terms at weight 3.0, then the last 4 user/assistant messages (newest first, weights 2.0 down to 1.0). | Put the problem's exact vocabulary in the goal objective and in memory titles so the right memories surface. | `crates/pa-core/src/session_engine/harness_digest.rs` (`digest_query_terms`), `crates/pa-core/src/refinement/ranking.rs`, `crates/pa-core/src/refinement/mod.rs` (`DEFAULT_OVERVIEW_CONTENT_LIMIT = 140`) |
| H5 | Auto-refine runs about every 25 turns (`turn_interval: 25`) and at compaction, with a 20 minute cooldown (`cooldown_ms = 20 * 60 * 1000`), at depth 0 only. | Do not wait for it. Call `refine.run(...)` yourself at useful moments. Children do not get auto-refine. | `crates/pa-core/src/session_engine/refine.rs`, `crates/pa-core/src/session_engine/auto_refine_trigger.rs` |
| H6 | A child whose assistant message ends with text and no tool call terminates its own session; the parent receives nothing. | Every spawn prompt must carry the tool-call-until-final-reply rule, a tool-call budget, and "reply even if partial". | Runtime behavior of RLM children (see the child contract in SKILL.md) |
| H7 | Compaction drops REPL variables whose serialized size is over 16 MiB (`DEFAULT_SNAPSHOT_MAX_VARIABLE_BYTES = 16 * 1024 * 1024`). | Keep large data on disk under `./.deep-solve/`; reload after compaction. | `crates/pa-core/src/kernel/state_snapshot.rs` |
| H8 | A package repo is auto-discovered through top-level `skills/` and `prompts/` convention directories; no manifest is needed. | This repo installs as a package with `prime-agent package install`. | `crates/pa-core/src/packages/resolve/collect.rs`, `crates/pa-core/src/packages/resolve/discovery.rs` |
| H9 | Prompt templates: name is the file stem; frontmatter has `description` and `argument-hint`; `$ARGUMENTS` is substituted with the command arguments. | `prompts/deep-solve.md` becomes `/deep-solve <problem>`. | `crates/pa-core/src/skills/prompt_templates.rs` |

Note on H6: this fact comes from the RLM runtime contract stated in the prime-agent base prompt and the source template; it is not a single constant in the repo.
