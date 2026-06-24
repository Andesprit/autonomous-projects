# autonomous-projects

**Point it at a codebase and tell it how much to do. It comes back with ideas —
each with a spec and a plan — plus code reviews. You approve the good ones, and
it implements them, with a second AI checking the work (re-running your tests)
before it reaches you.**

A [flow-atelier](https://github.com/LGuillermoAngaritaG/flow-atelier) package
that turns a repo into a steady stream of small, reviewed
improvements — without handing over the keys. You drop a `.atelier/project/`
folder into the repo and point the conduit at it; each tick you say how many
ideas, reviews, task write-ups, and to-do tasks to run, and it does exactly
that — studies the project, proposes ideas and code reviews, drains any raw
tasks you dropped, advances approved work, and waits. You skim the proposals and
drag the good ones into the work queue. Next tick it implements them in priority
order, a *second* AI independently checks the work, and the finished change
lands awaiting your final yes.

Why people keep it running:

- **You stay in control.** The bot proposes and implements; *you* decide what's
  worth doing and what's actually done. It never marks its own work complete.
- **You set the pace.** Each tick you say how many of each activity to run
  (`n_ideas` / `n_reviews` / `n_improve` / `n_todo`). Nothing you didn't ask for
  happens.
- **Two-agent quality gate.** Every task is built by one agent and verified by
  another — which *re-runs the test suite itself* — before it reaches you,
  looped until the reviewer signs off.
- **It works while you don't.** Schedule it overnight and wake up to a triaged
  backlog and reviewed diffs instead of a blank page.
- **Just markdown and folders.** Your whole workflow is files you can read,
  edit, and move by hand. No database, no dashboard to learn.
- **Cost-aware.** Before each activity it checks the harness's live 5-hour usage
  and skips that activity when it's at/over your `max_usage` ceiling, so a run
  won't blow past your quota.
- **Hard to derail.** A missing tool, an empty queue, or a crashed sub-step
  degrades gracefully (skip + warn) — it doesn't take the tick down with it.

```
bot:  00_backlog/  ──▶  02_in-progress/  ──▶  03_to-review/
you:        └────▶ 01_to-do/                        └─▶ 04_done/
you drop raw tasks ▶ 00_tasks/ ──(bot improves)──▶ 00_backlog/
stalled task ▶ 05_blocked/ (bot parks a task it couldn't finish, with a note)
```

## Quickstart

**1. Install flow-atelier and this package.**

```bash
uv tool install flow-atelier
atelier add LGuillermoAngaritaG/autonomous-projects
atelier list conduits        # confirm autonomous-projects appears
```

**2. Scaffold a project inside your repo.**

```bash
# one command — the scaffold-project conduit wraps the scaffolder:
atelier run scaffold-project --input project_root=/abs/path/to/your/repo

# or call the script directly (it ships inside the package, under
# .atelier/conduits/autonomous-projects/scripts/):
uv run python <package>/.atelier/conduits/autonomous-projects/scripts/new_project.py \
  --repo /abs/path/to/your/repo
```

`new_project.py` creates `<repo>/.atelier/project/` with a ready `project.md`
and all seven stage folders. It refuses if `.atelier/project/` already exists or
if the repo isn't an existing writable directory — and builds atomically, so a
failure leaves nothing half-made. Then open
`<repo>/.atelier/project/project.md` and fill in `# Goal` / `# Constraints`.
(Prefer to do it by hand? The layout is just folders — see
[Scaffold a project](#scaffold-a-project).)

**3. Run one tick — and say how much to do.**

```bash
# top up the backlog with 2 ideas and 1 review:
atelier run autonomous-projects --input project_root=/abs/path/to/your/repo \
  --input n_ideas=2 --input n_reviews=1
```

Every `n_*` defaults to `0`, so a bare run does nothing — you ask for work
explicitly. The tick generates exactly what you asked for and exits. Nothing
reaches `04_done/` — that is your move.

**4. See the output and triage.**

Proposals land in `<repo>/.atelier/project/00_backlog/`. Move the good ones to
`<repo>/.atelier/project/01_to-do/`, then advance them next tick with
`--input n_todo=N`.

For front-matter fields, board mechanics, tick internals, and tuning, see the
sections below.

---

## Install

**1. Install [flow-atelier](https://github.com/LGuillermoAngaritaG/flow-atelier)** (one time):

```bash
uv tool install flow-atelier
atelier --version
```

**2. Install this package** with `atelier add` (git URL, `owner/repo`, or a
local path):

```bash
atelier add LGuillermoAngaritaG/autonomous-projects
# or from a local checkout:
atelier add ./atelier-examples/autonomous-projects
```

This installs the conduits globally, so you can run them from **any folder**.
Confirm with:

```bash
atelier list conduits        # autonomous-projects should appear
```

**Requirements:** the helper scripts run under
[`uv`](https://docs.astral.sh/uv/) (the counter and usage check are plain
stdlib `python3`); `usage.mjs` needs Node 22+ (`node:sqlite`). The
work/review/idea steps drive **Claude Code**. The first task in every tick
(`dep_guard`) fails fast with a clear message if `uv`, the `claude` CLI,
`python3`, or `node` is missing from `PATH`, so a missing tool surfaces
immediately instead of mid-run. The next task (`project_guard`) likewise fails
fast if `project_root` isn't a scaffolded project (no `.atelier/project/project.md`),
so a wrong path or a forgotten scaffold step stops the tick cleanly instead of
crashing deep in a sub-conduit.

---

## Run

Point the conduit at the repo holding `.atelier/project/`, and say how much of
each activity to run this tick:

```bash
atelier run autonomous-projects --input project_root=/abs/path/to/your/repo \
  --input n_todo=3
```

Every `n_*` count defaults to `0` (skip), so name only the activities you want.
One repo per `project_root`; to drive several repos, run (or schedule) the
conduit once per repo. There is no central registry and no picker — the conduit
advances the single project it's pointed at.

---

## Scaffold a project

A project lives in `<repo>/.atelier/project/` — a `project.md` plus a set of
numbered stage folders, dropped into the repo the bot will edit. The one-command
way:

```bash
uv run python .atelier/conduits/autonomous-projects/scripts/new_project.py --repo /abs/path/to/repo
```

…or create it by hand:

```
<repo>/                 ← the codebase the bot edits (project_root)
  .atelier/project/
    project.md          ← you write this (goal, constraints)
    00_backlog/         ← bot writes idea_*.md / review_*.md / task_*.md proposals
    00_tasks/           ← you drop RAW task files here; the bot turns them into specs
    00_abandoned/       ← you drop rejected proposals here (+ a note saying why)
    01_to-do/           ← you move approved proposals here = the work queue
    02_in-progress/     ← bot moves a task here while working it
    03_to-review/       ← bot moves it here when done; awaiting your review
    04_done/            ← only you move tasks here
    05_blocked/         ← bot parks a task it started but couldn't finish (created on demand)
```

`project.md` uses YAML front-matter (the template ships at
`references/project_template.md`):

```markdown
---
test_command: "uv run pytest"          # optional; how the builder + reviewer run your tests
---
# Goal
What you want done.
# Description
Short context.
# Constraints
Anything the bot must respect — these are binding; it won't work around them.
```

The bot edits the repo holding `.atelier/project/` — there is no separate
`location:` field; the codebase is implicit. The `project.md` file is **yours**
— the bot treats it as read-only and never edits it. Only `test_command` and
the `# Goal` / `# Description` / `# Constraints` body are read. Whether the bot
commits its work is decided by the repo itself: if `project_root` is a git
repository it commits each task; if not, it just edits files.

---

## The task board — what to move, and what to expect

The flow is half bot, half you:

- **Bot proposes** → `00_backlog/`. Each tick it can add ideas (`idea_*.md`),
  code reviews (`review_*.md`), and spec'd tasks (`task_*.md`, from your raw
  inbox — see below).
- **You feed raw tasks** → `00_tasks/`. Drop a rough one-line task; the bot runs
  `/spec` + `/plan` on it and writes a polished `task_*.md` into `00_backlog`
  (carrying your original wording verbatim into `# Description`), then deletes
  the raw file.
- **You triage** `00_backlog/`: move good proposals to `01_to-do/`, bad ones to
  `00_abandoned/`. Leave your reasoning in the abandoned file — it steers future
  proposals away from that kind.
- **Bot executes** `01_to-do/`: picks the **highest-priority** task, moves it to
  `02_in-progress/`, does the work (commits if the repo uses git), then a **second
  agent independently re-runs your tests and judges DONE/NOT_DONE**, retrying up
  to 10 times until DONE, then moves it to `03_to-review/`.
- **You approve.** Move finished tasks from `03_to-review/` to `04_done/`. **The
  bot never moves anything to `04_done/`** — that judgment is yours.
- **Stalled work is parked, not lost.** If the bot starts a task but can't carry
  it to DONE within the retry budget, it moves it to `05_blocked/` with a
  `# Blocked` note instead of silently retrying it forever — so the queue keeps
  flowing and you can see what got stuck.

Nothing happens to a project until you move proposals into `01_to-do/`. The bot
only ever touches `00_backlog/ → 02_in-progress/ → 03_to-review/` (and parks to
`05_blocked/`, and drains `00_tasks/`); everything else is your move.

---

## How a tick works — under the hood

Each `atelier run autonomous-projects` is one **tick**. A tick is a small DAG of
tasks (see `.atelier/conduits/autonomous-projects/conduit.yaml`):

```
dep_guard ─▶ project_guard ─┬─▶ counts ───────────────┐
                            ├─▶ usage_ideas           │
                            ├─▶ usage_reviews         ├─▶ generate_ideas   (n_ideas>0   ∧ usage_ideas ok)
                            ├─▶ usage_improve         ├─▶ generate_reviews (n_reviews>0 ∧ usage_reviews ok)
                            └─▶ usage_todo            ├─▶ improve_tasks    (n_improve>0 ∧ usage_improve ok)
                                                      └─▶ do_tasks         (n_todo>0    ∧ usage_todo ok)
```

### 0. `dep_guard`
The DAG root. Fails fast (with a named, actionable message) if `uv`, the
`claude` CLI, `python3`, or `node` is missing from `PATH` — every activity runs
on Claude Code, and `node` is what makes the `max_usage` gate real (`usage.mjs`
runs under it; without `node` the usage read silently fails open and the ceiling
is never enforced) — so a missing tool stops the tick cleanly instead of
crashing a branch deep in the run.

### 0.5 `project_guard`
Runs right after `dep_guard`, before any work. Fails fast if `project_root`
isn't a scaffolded project — i.e. there's no `.atelier/project/project.md` where
one should be. This catches the common mistakes of forgetting to scaffold,
mistyping `project_root`, or aiming at the wrong repo, instead of letting the
tick sail past and die deep in a sub-conduit. The message names both failure
modes and prints the exact scaffold command:

```
not a project: no project.md at <path>/.atelier/project/project.md
If the path is wrong, fix --input project_root.
Otherwise scaffold it first:
  atelier run new-project --input project_root=<path>
```

### 1. `counts` — what to run this tick
You tell each tick how much of each activity to do with `--input n_ideas=…`,
`n_reviews`, `n_improve`, `n_todo` (all default `0`). The `counts` task simply
echoes them so each branch can gate on its own count being non-zero (a
`depends_on` can't read a run input directly, but it can match a task's output):

```
n_ideas: 2
n_reviews: 0
n_improve: 0
n_todo: 3
```

A branch whose `n_*` is `0` is skipped. With every count at its `0` default the
tick is a no-op — nothing runs until you ask for it.

### 2. `usage_*` — the one gate
The only gate is a usage ceiling. For each activity, a `usage_*` task resolves
the harness declared in that activity's sub-conduit (all `claude-code` today,
following `work-one-todo` → `task-with-review`), reads its live **5-hour
usage %** via `scripts/usage.mjs` (Claude Code's own local rate-limit cache —
no network), and prints `ok: true` while it's **under** `--input max_usage`
(default `80`), else `ok: false`:

```
ok: true
```

Usage that can't be read, an unknown harness, or an unparseable ceiling all
**fail open** (`ok: true`), and the check always exits `0` — so a broken reading
never blocks the tick. (`scripts/usage_check.py`.)

### 3. The four work branches
Each branch runs only when **both** its conditions pass — its count is non-zero
**and** its usage check is `ok`:

| Branch | Runs when | Calls | Writes to |
|---|---|---|---|
| `generate_ideas`   | `n_ideas > 0` ∧ `usage_ideas` ok | `generate-idea` conduit | `idea_*.md` → `00_backlog/` |
| `generate_reviews` | `n_reviews > 0` ∧ `usage_reviews` ok | `generate-review` conduit | `review_*.md` → `00_backlog/` |
| `improve_tasks`    | `n_improve > 0` ∧ `usage_improve` ok | `improve-task` conduit | `task_*.md` → `00_backlog/` (drains `00_tasks/`) |
| `do_tasks`         | `n_todo > 0` ∧ `usage_todo` ok | `work-one-todo` conduit | advances `01_to-do/` → `03_to-review/` (or `05_blocked/`) |

### 4. Per-tick counts — how a loop stops at N
The atelier engine requires `repeat:` to be a **literal integer** and `until:` a
**fixed regex** — neither can read a runtime `--input`. So each branch loops to a
high literal `repeat:` safety ceiling (`50`) and a small counter inside the
sub-conduit stops it at your `n_*`:

- A leading `count` step reads the running tally carried in `{{loop.previous}}`
  (the previous iteration's output) and, once `n_*` activities have run, emits
  `remaining: 0` — which trips the branch's `until: output.match(remaining: 0)`
  and gates the activity off.
- After the activity runs, a trailing `advance` step bumps the tally (`made: K`)
  and recomputes `remaining`, so the next iteration sees the new count.

`improve_tasks` and `do_tasks` also stop when their **queue drains** —
`improve-task` emits `task_counter: 0` when the inbox is empty, `work-one-todo`
when `01_to-do/` is empty — so each runs `min(n_*, work available)` (their
`until` matches `remaining: 0 | task_counter: 0`).

The counter is `scripts/loop_count.py` (pure, unit-tested);
`tests/test_loop_count.py` proves a loop stops exactly at its target across
iterations.

### 5. The two-agent execution loop (`work-one-todo`)
For each to-do task, `work-one-todo`:

1. **Picks by priority** (`pick_next_task.py`) — sorts `01_to-do/*.md` by
   (`priority` ascending, then filename) so the lowest `priority` number is
   worked first; a missing/blank priority sorts last.
2. **Builds + reviews in a loop** — loops `task-with-review` up to **10** times
   `until` the reviewer returns `VERDICT: DONE`. The **builder** reads the task,
   resumes any task already in `02_in-progress/`, cds into the repo
   (`project_root`), does the work, and runs the **full** test suite — using the
   project's `test_command` if set, else auto-detecting a conventional one
   (`pytest`, `npm test`, `cargo test`, `make test`, …). It records exact
   pass/fail counts in `# How was done and tested`, never moves a task with red
   tests, and if there are no tests it says so plainly rather than faking a pass.
   The **reviewer** then *independently re-runs the suite itself* and checks two
   things — Completion (was it actually done?) and Alignment (does it serve the
   goal and respect every constraint?) — returning `NOT_DONE` (with a reason that
   becomes the next iteration's priority) unless both hold and the tests are
   green under its own run. The reviewer is skipped entirely when the builder
   reports `NOTHING TO DO`. Both builder and reviewer run on Claude Code.
3. **Parks stranded work** (`block_stranded.py`) — if a task is still sitting in
   `02_in-progress/` after the loop gives up, it's moved to `05_blocked/` with a
   `# Blocked` note (de-duped filename) so it stops being silently retried every
   tick.
4. **Counts** — `bump` advances the per-tick counter (`made: N`) so the outer
   loop stops at `n_todo`, and `count_todo` emits `task_counter: N` so it also
   stops when `01_to-do/` drains — whichever cap is smaller wins.

Each sub-conduit declares `tool: harness:claude-code` directly on its build /
review / generate steps; there are no harness-router wrapper conduits.

---

## Tuning — parameters you control

### Per project (front-matter in `project.md`)

| Field          | What it controls |
|----------------|------------------|
| `test_command` | *(optional)* Exact command both the builder and reviewer use to run your tests. Omit to let them auto-detect a conventional suite. |

(Whether the bot commits is no longer a field — it's auto-detected: if the
target repo is a git repository the bot commits each task, otherwise it just
edits files.)

### Per run (`--input`)

| Input | Default | What it controls |
|-------|---------|------------------|
| `project_root` | *(required)* | Absolute path to the repo holding `.atelier/project/`; the codebase the bot edits. |
| `n_ideas`   | `0` | Ideas to generate into `00_backlog/` this tick. |
| `n_reviews` | `0` | Reviews to generate into `00_backlog/` this tick. |
| `n_improve` | `0` | Raw tasks from `00_tasks/` to spec into `00_backlog/` this tick (stops early when the inbox drains). |
| `n_todo`    | `0` | To-do tasks to advance from `01_to-do/` this tick (stops early when the queue drains). |
| `max_usage` | `80` | Usage ceiling (%). An activity is skipped when its harness's live 5h usage is at/over this. |

```bash
# advance up to 3 approved to-do tasks, nothing else:
atelier run autonomous-projects --input project_root=/abs/path/to/repo --input n_todo=3

# top up the backlog: 2 ideas + 1 review, but only if Claude Code is under 60%:
atelier run autonomous-projects --input project_root=/abs/path/to/repo \
  --input n_ideas=2 --input n_reviews=1 --input max_usage=60
```

---

## Architecture / files

Everything lives under `.atelier/conduits/`:

```
autonomous-projects/
  conduit.yaml          the tick DAG (dep_guard → counts/usage_* → 4 branches)
  scripts/
    usage_check.py       single usage gate → ok: true|false (reads the activity's harness, fail-open)
    usage.mjs            reads Claude Code's local 5h-usage data (also Codex/OpenCode)
    loop_count.py        per-tick counter: made:/remaining: carried via {{loop.previous}}
    new_project.py       one-command scaffolder (--repo, atomic)
    tick_lock.py         single-flight OS lock wrapper
    tests/               loop_count, usage_check, new_project, tick_lock, count_tasks, block_stranded, pick_next_task
  references/
    project_template.md  the project.md starter
    task_template.md     the task_*.md starter
generate-idea/           sub-conduit: /idea → /plan → store idea_*.md (priority 3); counts to n_ideas
generate-review/         sub-conduit: /review → /plan → store review_*.md (priority 2); counts to n_reviews
improve-task/            sub-conduit: pick raw task → /spec + /plan → task_*.md (priority 1); counts to n_improve / inbox drain
improve-all-tasks/       loops improve-task until the inbox drains (standalone; the tick calls improve-task directly)
work-one-todo/           pick-by-priority → advance (build+review to DONE) → park stranded → count to n_todo / queue drain
task-with-review/        one builder + one reviewer (each re-runs tests), returns a VERDICT
scaffold-project/        standalone: scaffold .atelier/project/ into a target repo (wraps new_project.py; project_root, defaults to .)
```

Every activity runs on Claude Code (`tool: harness:claude-code`, declared
directly in each sub-conduit). The usage shim, counter, and helper scripts are
pure and unit-tested; the generation/execution steps drive the AI harness.
Sub-conduits receive their folder paths and per-tick `target`/`prior` from the
parent, so the layout is defined in one place (`conduit.yaml`).

---

## Schedule it

Run on a timer with a schedule file (one schedule per repo; set `project_root`
to the repo holding `.atelier/project/`, and the per-tick counts you want each
run to do):

```yaml
conduit_name: autonomous-projects
inputs:
  project_root: /abs/path/to/your/repo
  n_ideas: "2"
  n_reviews: "1"
  n_todo: "5"
schedule:
  mode: interval
  name: autonomous-projects-30min
  every_minutes: 30
  timezone: America/Bogota
```

```bash
atelier schedule add path/to/schedule.yaml
atelier scheduler start      # foreground daemon; Ctrl+C to stop
```

To drive several repos, add one schedule per repo, each with its own
`project_root` (and, if you wrap ticks in `tick_lock.py`, its own
`--lock-file` — see Single-flight below). Overnight, each tick advances its
repo's project: tops up the backlog with the ideas and reviews you asked for,
improves any raw tasks you dropped, and advances up to `n_todo` approved to-do
tasks through the two-agent DONE loop — skipping any activity whose harness is
over your usage ceiling. You wake up to a triaged backlog and reviewed diffs
waiting for your yes.

**Single-flight (cron / custom timers).** A tick may run up to 2h, so on a
30-min interval a slow tick can still be working when the next fires — two runs
then race over the same project files. Wrap the invocation in `tick_lock.py` so
the second run prints a skip note and exits instead:

```bash
# one lock per repo: co-locate it with the repo it guards
python3 .atelier/conduits/autonomous-projects/scripts/tick_lock.py \
  --lock-file /abs/path/to/your/repo/.autonomous-projects.lock \
  atelier run autonomous-projects --input project_root=/abs/path/to/your/repo
```

Use a distinct `--lock-file` per repo. Without it the lock defaults to
`<cwd>/.autonomous-projects.lock`, so several repos launched from the same
directory share one lock — the first grabs it and the rest print "a tick is
already running, skipping this one" and exit without working. They don't fail
or warn, so the only symptom is repos that sat still all night.

It takes an OS advisory lock for the whole run; the kernel releases it if the
run crashes or is killed, so a dead run never jams the loop.
