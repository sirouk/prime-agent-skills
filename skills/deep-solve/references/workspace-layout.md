# Workspace layout: `./.deep-solve/`

The problem state lives on disk. Context is compacted, REPL variables over 16 MiB are dropped at compaction, and children cannot see the parent's context. Use this directory (or the one the user names).

```
.deep-solve/
  PROBLEM.md
  HYPOTHESES.md
  LOG.md
  attempts/<angle-id>/REPORT.md
  evidence/
  verify.sh
  SOLUTION.md
```

| Path | Purpose |
|---|---|
| `PROBLEM.md` | The problem in your own words, success criteria, constraints, unknowns, assumptions, and what "done" means in checkable terms. |
| `HYPOTHESES.md` | Table: id, angle/approach, prediction, cost estimate, status (open / running / refuted / supported / parked), evidence file. |
| `LOG.md` | Append-only. One dated entry per round: what was tried, what was observed, what changed in your beliefs, what is next. Written for a reader with no context. |
| `attempts/<angle-id>/REPORT.md` | One directory per attempt. Holds the child's `REPORT.md`, scripts, data, and outputs. |
| `evidence/` | Raw outputs, measurements, failing cases, reproductions, and prior-art sources. Keep raw evidence; summaries lie. |
| `verify.sh` | Executable that exits 0 only when the success criteria are met. Single source of truth for completion. Write it early and tighten it. |
| `SOLUTION.md` | Written last: answer, how it was verified, what was tried and failed and why, remaining risks, how to reproduce. Each success criterion has its evidence path. |

## Minimal `verify.sh`

Start with whatever part of the criteria you can check. Add checks as "solved" gets sharper. Each failed check must print why and make the script exit non-zero.

```bash
#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."   # project root

fail=0
check() {  # check "<criterion>" <command...>
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "PASS: $name"; else echo "FAIL: $name"; fail=1; fi
}

check "tests pass"            make test
check "reproduction is fixed" ./.deep-solve/evidence/repro.sh

exit "$fail"
```

Make it executable: `chmod +x .deep-solve/verify.sh`.

The `.deep-solve/` directory is in this package's `.gitignore`. In your own project, decide whether to commit it or ignore it.
