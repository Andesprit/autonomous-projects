# autonomous-projects

**Point it at a codebase and it comes back with ideas — each with a spec and a
plan — plus code reviews. You approve the good ones, and it implements them,
with a second AI checking the work (re-running your tests) before it reaches
you.**

A [flow-atelier](https://github.com/LGuillermoAngaritaG/flow-atelier) package
that turns a repo into a steady stream of small, reviewed
improvements — without handing over the keys. You drop a `.atelier/project/`
folder into the repo and point the conduit at it; each tick generates
**10 straightforward ideas, 3 divergent ones, and 5 code reviews** by default
(every count is overridable) — it studies the project, proposes ideas and code
reviews, drains any raw tasks you dropped, advances approved work, and waits.
You skim the proposals and
drag the good ones into the work queue. Next tick it implements them in priority
order, a *second* AI independently checks the work, and the finished change
lands awaiting your final yes.

Why people keep it running:

- **You stay in control.** The bot proposes and implements; *you* decide what's
  worth doing and what's actually done. It never marks its own work complete.
- **Two kinds of ideas.** Straightforward ideas come from a survey of the real
  code. Divergent ones come from
  [`adhd`](https://github.com/UditAkhourii/adhd): five isolated agents ideate
  under different cognitive frames (regulator, biology, speedrunner, $0
  budget…), then a critic scores, clusters, and prunes traps — so the backlog
  gets the non-obvious pick, not just the answer everyone would give first.
- **You set the pace.** A tick proposes by default (10 ideas, 3 divergent, 5
  reviews) and touches your work queue only when you ask (`n_improve` /
  `n_todo` default to `0`). Every count is a `--input` away from whatever you
  want, including `0`.
- **Two-agent quality gate.** Every task is built by one agent and verified by
  another — which *re-runs the test suite itself* — before it reaches you,
  looped until the reviewer signs off.
- **It works while you don't.** Schedule it overnight and wake up to a triaged
  backlog and reviewed diffs instead of a blank page.
- **Just markdown and folders.** Your whole workflow is files you can read,
  edit, and move by hand. No database, no dashboard to learn.
- **Cost-aware.** It reads the harness's live 5-hour usage before each activity
  **and again before every iteration**, so a long branch stops at the first
  iteration that is at/over your `max_usage` ceiling instead of discovering it
  an hour later.
- **Degrades before it fails.** An empty queue, a missing optional skill, a
  generation step that returns nothing usable: each stops just its own branch,
  loudly, and leaves the others running. Only a genuinely missing hard
  dependency (`python3`, `npx`, `claude`) stops the tick — up front, in
  `dep_guard`, with a named message.

```
bot:  00_backlog/  ──▶  02_in-progress/  ──▶  03_to-review/
you:        └────▶ 01_to-do/                        └─▶ 04_done/
you drop raw tasks ▶ 00_tasks/ ──(bot improves)──▶ 00_backlog/
stalled task ▶ 05_blocked/ (bot parks a task it couldn't finish, with a note)
```

## Quickstart

**1. Install flow-atelier, the agent skills, and this package.**

```bash
uv tool install flow-atelier
atelier add LGuillermoAngaritaG/autonomous-projects
atelier list conduits        # confirm autonomous-projects appears
```

Then install the two skill sets the conduits drive — inside Claude Code:

```
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```

…and from a shell:

```bash
npx skills add UditAkhourii/adhd
```

**2. Scaffold a project inside your repo.**

```bash
# one command — the scaffold-project conduit wraps the scaffolder:
atelier run scaffold-project --input project_root=/abs/path/to/your/repo

# or call the script directly (it ships inside the package, under
# .atelier/conduits/autonomous-projects/scripts/):
python3 <package>/.atelier/conduits/autonomous-projects/scripts/new_project.py \
  --repo /abs/path/to/your/repo
```

`new_project.py` creates `<repo>/.atelier/project/` with a ready `project.md`
and all seven stage folders. It refuses if `.atelier/project/` already exists or
if the repo isn't an existing writable directory — and builds atomically, so a
failure leaves nothing half-made. Then open
`<repo>/.atelier/project/project.md` and fill in `# Goal` / `# Constraints`.
(Prefer to do it by hand? The layout is just folders — see
[Scaffold a project](#scaffold-a-project).)

**3. Run one tick.**

```bash
# the defaults: 10 straightforward ideas, 3 divergent ones, 5 reviews
atelier run autonomous-projects --input project_root=/abs/path/to/your/repo

# or say exactly how much to do:
atelier run autonomous-projects --input project_root=/abs/path/to/your/repo \
  --input n_ideas=2 --input n_adhd=0 --input n_reviews=1
```

A bare run generates `n_ideas=10`, `n_adhd=3` and `n_reviews=5` — that is
**18 AI activities**, and the divergent ones cost roughly 10 agent calls each,
so expect a long, quota-hungry tick (the `max_usage` gate still stops each
activity at your ceiling). Set any count to `0` to skip it. `n_improve` and
`n_todo` still default to `0`: the tick never touches your work queue unless
you ask. Nothing reaches `04_done/` — that is your move.

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

**2. Install the agent skills** (one time). The conduits drive
`/agent-skills:spec`, `/agent-skills:plan`, `/agent-skills:review` and
`/agent-skills:build` from
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills). They are
**not** shipped by this package — `atelier add` installs conduits only.

Install it as a Claude Code plugin (this is what registers the namespaced
commands; run both lines inside Claude Code):

```
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```

Verify the commands exist before running a tick — type `/agent-skills:` in
Claude Code and confirm `spec`, `plan`, `review` and `build` are listed. The
plugin install is required: `npx skills add addyosmani/agent-skills` installs
the *skills* but not the slash commands, so the conduits' `/agent-skills:*`
lines would not resolve.

(There is no `/idea` upstream: the straightforward-idea instructions live
inline in the `generate-idea` conduit, so nothing extra is needed for it.)

**3. Install the `adhd` skill** (one time), which drives the divergent-ideation
branch (`n_adhd`):

```bash
npx skills add UditAkhourii/adhd
```

This one is a *skill*, not a plugin command — the conduit names it in prose
(``Use the `adhd` skill``), so either the `npx skills add` install above
(`~/.claude/skills/adhd/`) or a project-level `.claude/skills/adhd/` works.
Without it the branch degrades to an ordinary single-shot idea instead of the
divergent loop; run with `--input n_adhd=0` if you'd rather not install it.
Details: [UditAkhourii/adhd](https://github.com/UditAkhourii/adhd).

**4. Install this package** with `atelier add` (git URL, `owner/repo`, or a
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

**Requirements.** The first task in every tick (`dep_guard`) checks these, so a
problem surfaces up front instead of mid-run:

| | Needed for | Missing it |
|---|---|---|
| `python3` | every helper script (counters, usage gate, pickers) — all plain stdlib | **tick fails** |
| `npx` (Node) | `harness:claude-code` launches `@agentclientprotocol/claude-agent-acp` through it | **tick fails** |
| `claude` | the ACP agent drives the Claude Code CLI | **tick fails** |
| Node 22+ | `scripts/usage.mjs` reads the 5h usage cache (`node:sqlite`) | warns; `max_usage` stops throttling (fails open) |
| [agent-skills](https://github.com/addyosmani/agent-skills) plugin | `/agent-skills:spec\|plan\|review\|build` (step 2) | warns; those steps run unguided |
| [`adhd`](https://github.com/UditAkhourii/adhd) skill | the `n_adhd` branch (step 3) | warns; that branch degrades to a single-shot idea |

`uv` is **not** required — no conduit runs it. It appears only if your own
project's `test_command` uses it (e.g. `uv run pytest`), and to run this
package's script tests.

**Upgrading.** `atelier add` skips conduits that already exist, so re-running it
after a new release changes nothing. Use `atelier update autonomous-projects`
(re-fetches from the recorded source), or `atelier add … --force` to overwrite.

---

## Run

Point the conduit at the repo holding `.atelier/project/`, and say how much of
each activity to run this tick:

```bash
atelier run autonomous-projects --input project_root=/abs/path/to/your/repo \
  --input n_todo=3
```

Naming a count overrides its default; the ones you don't name keep theirs
(`n_ideas=10`, `n_adhd=3`, `n_reviews=5`, `n_improve=0`, `n_todo=0`). Set a
count to `0` to skip that activity — e.g. add `--input n_ideas=0 --input
n_adhd=0 --input n_reviews=0` to the run above to advance to-do tasks and
nothing else.
One repo per `project_root`; to drive several repos, run (or schedule) the
conduit once per repo. There is no central registry and no picker — the conduit
advances the single project it's pointed at.

---

## Scaffold a project

A project lives in `<repo>/.atelier/project/` — a `project.md` plus a set of
numbered stage folders, dropped into the repo the bot will edit. The one-command
way:

```bash
python3 .atelier/conduits/autonomous-projects/scripts/new_project.py --repo /abs/path/to/repo
```

…or create it by hand:

```
<repo>/                 ← the codebase the bot edits (project_root)
  .atelier/project/
    project.md          ← you write this (goal, constraints)
    00_backlog/         ← bot writes idea_*.md / adhd_*.md / review_*.md / task_*.md proposals
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

- **Bot proposes** → `00_backlog/`. Each tick it can add straightforward ideas
  (`idea_*.md`), divergent ones (`adhd_*.md`), code reviews (`review_*.md`),
  and spec'd tasks (`task_*.md`, from your raw inbox — see below). The `adhd_`
  prefix is the only difference between the two kinds of idea — same template,
  same `priority: 3`, same triage — so you can tell at a glance which came out
  of the expensive divergent pass.
- **You feed raw tasks** → `00_tasks/`. Drop a rough one-line task; the bot runs
  `/agent-skills:spec` + `/agent-skills:plan` on it and writes a polished
  `task_*.md` into `00_backlog`
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
dep_guard ─┬─▶ counts ───────────────┐
           ├─▶ usage_ideas           ├─▶ generate_ideas      (n_ideas>0   ∧ usage_ideas ok)
           ├─▶ usage_adhd            ├─▶ generate_adhd_ideas (n_adhd>0    ∧ usage_adhd ok)
           ├─▶ usage_reviews         ├─▶ generate_reviews    (n_reviews>0 ∧ usage_reviews ok)
           ├─▶ usage_improve         ├─▶ improve_tasks       (n_improve>0 ∧ usage_improve ok)
           └─▶ usage_todo            └─▶ do_tasks            (n_todo>0    ∧ usage_todo ok)
```

### 0. `dep_guard`
The DAG root. Fails fast, with a named message, when a **hard** dependency is
missing from `PATH` — `python3`, `npx`, `claude` — so it stops the tick cleanly
instead of crashing a branch deep in the run. Everything else only **warns**:
missing `node` (the usage gate stops throttling), a missing agent-skills plugin
or `adhd` skill (those steps degrade). See the table under
[Requirements](#install).

### 1. `counts` — what to run this tick
You tell each tick how much of each activity to do with `--input n_ideas=…`,
`n_adhd`, `n_reviews`, `n_improve`, `n_todo`. The `counts` task simply
echoes them so each branch can gate on its own count being non-zero (a
`depends_on` can't read a run input directly, but it can match a task's output):

```
n_ideas: 2
n_adhd: 0
n_reviews: 0
n_improve: 0
n_todo: 3
```

A branch whose `n_*` is `0` is skipped. The proposal counts default to
`10`/`3`/`5` (ideas/adhd/reviews) and the queue counts (`n_improve`, `n_todo`)
to `0`, so a bare run tops up the backlog and touches nothing you've approved.

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

That check runs **once**, before the branch starts. On its own that's not enough
at these defaults: `n_ideas=10` is one branch that can run for an hour, starting
under the ceiling and spending well past it. So the ceiling is re-read inside
each branch too — the same `count` step that stops the loop at `n_*` also calls
the usage gate, and emits

```
made: 4
remaining: 0
stopped: usage ceiling reached
```

at the first iteration that is at/over `max_usage`. The branch ends there with
its finished work kept, the other branches carry on, and the re-check is
fail-open exactly like the one before it (`loop_count.py`, `usage_ok`).

### 3. The five work branches
Each branch runs only when **both** its conditions pass — its count is non-zero
**and** its usage check is `ok`. The tick's `max_concurrency: 3` means the
three proposal branches — `generate_ideas`, `generate_adhd_ideas` and
`generate_reviews` — run **at the same time**, so a tick costs about as long as
its slowest branch instead of the sum of all three. Within a branch, iterations
stay sequential, so each new idea still sees the ones before it. Across
branches they don't: an idea and an adhd idea produced in the same tick can't
read each other, so occasionally two of them land on the same theme — triage
catches it. `improve_tasks` and `do_tasks` are declared last and take slots as
the proposal branches finish:

| Branch | Runs when | Calls | Writes to |
|---|---|---|---|
| `generate_ideas`   | `n_ideas > 0` ∧ `usage_ideas` ok | `generate-idea` conduit | `idea_*.md` → `00_backlog/` |
| `generate_adhd_ideas` | `n_adhd > 0` ∧ `usage_adhd` ok | `generate-adhd-idea` conduit | `adhd_*.md` → `00_backlog/` |
| `generate_reviews` | `n_reviews > 0` ∧ `usage_reviews` ok | `generate-review` conduit | `review_*.md` → `00_backlog/` |
| `improve_tasks`    | `n_improve > 0` ∧ `usage_improve` ok | `improve-task` conduit | `task_*.md` → `00_backlog/` (drains `00_tasks/`) |
| `do_tasks`         | `n_todo > 0` ∧ `usage_todo` ok | `work-one-todo` conduit | advances `01_to-do/` → `03_to-review/` (or `05_blocked/`) |

`generate_adhd_ideas` is the expensive one. Each iteration hands the problem
("what is the highest-leverage improvement to make to this codebase right now —
the one a careful maintainer would not have reached for first?") to the
[`adhd`](https://github.com/UditAkhourii/adhd) skill, which spawns **5 parallel
isolated agents** under different cognitive frames, then runs a critic pass that
scores each idea on novelty/viability/fit, clusters them by underlying angle,
flags traps, and deepens the top survivors. The conduit then carries forward
exactly one idea — the shortlist's non-obvious-but-viable ★ pick, never a
flagged trap — and runs it through the same `/agent-skills:plan` + store steps
as an ordinary idea. Budget roughly **10 agent calls per `adhd_*.md`**, so
`n_adhd=3` is about 30. The project's `# Constraints` are binding inside the
loop: an idea that violates one is treated as a trap and cannot win.

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
| `n_ideas`   | `10` | Straightforward ideas to generate into `00_backlog/` this tick. |
| `n_adhd`    | `3` | Divergent (`adhd` skill) ideas into `00_backlog/` this tick. ~10 agent calls each — set `0` to skip. |
| `n_reviews` | `5` | Reviews to generate into `00_backlog/` this tick. |
| `n_improve` | `0` | Raw tasks from `00_tasks/` to spec into `00_backlog/` this tick (stops early when the inbox drains). |
| `n_todo`    | `0` | To-do tasks to advance from `01_to-do/` this tick (stops early when the queue drains). |
| `max_usage` | `80` | Usage ceiling (%). An activity is skipped when its harness's live 5h usage is at/over this. |

```bash
# the defaults: 10 ideas + 3 divergent ideas + 5 reviews:
atelier run autonomous-projects --input project_root=/abs/path/to/repo

# advance up to 3 approved to-do tasks, nothing else:
atelier run autonomous-projects --input project_root=/abs/path/to/repo \
  --input n_todo=3 --input n_ideas=0 --input n_adhd=0 --input n_reviews=0

# top up the backlog cheaply: 2 ideas + 1 review, no divergent pass,
# and only if Claude Code is under 60%:
atelier run autonomous-projects --input project_root=/abs/path/to/repo \
  --input n_ideas=2 --input n_adhd=0 --input n_reviews=1 --input max_usage=60
```

---

## Architecture / files

Everything lives under `.atelier/conduits/`:

```
autonomous-projects/
  conduit.yaml          the tick DAG (dep_guard → counts/usage_* → 5 branches)
  scripts/
    usage_check.py       single usage gate → ok: true|false (reads the activity's harness, fail-open)
    usage.mjs            reads Claude Code's local 5h-usage data (also Codex/OpenCode)
    loop_count.py        per-tick counter (made:/remaining: via {{loop.previous}}) + the per-iteration usage re-check
    require_markers.py   non-fatal gate: did a generation step emit its ===MARKER=== block? stops one branch, not the tick
    new_project.py       one-command scaffolder (--repo, atomic)
    tick_lock.py         single-flight OS lock wrapper
    tests/               loop_count, usage_check, require_markers, new_project, tick_lock, count_tasks, block_stranded, pick_next_task
  references/
    project_template.md  the project.md starter
    task_template.md     the task_*.md starter
generate-idea/           sub-conduit: inline idea prompt → :plan → store idea_*.md (priority 3); counts to n_ideas
generate-adhd-idea/      sub-conduit: adhd skill (5 frames + critic) → :plan → store adhd_*.md (priority 3); counts to n_adhd
generate-review/         sub-conduit: :review → :plan → store review_*.md (priority 2); counts to n_reviews
improve-task/            sub-conduit: pick raw task → :spec + :plan → task_*.md (priority 1); counts to n_improve / inbox drain
improve-all-tasks/       loops improve-task until the inbox drains (standalone; the tick calls improve-task directly)
work-one-todo/           pick-by-priority → advance (build+review to DONE) → park stranded → count to n_todo / queue drain
task-with-review/        one builder + one reviewer (each re-runs tests), returns a VERDICT
scaffold-project/        standalone: scaffold .atelier/project/ into a target repo (wraps new_project.py; project_root, defaults to .)
```

Above, `:spec` / `:plan` / `:review` / `:build` are the `/agent-skills:*`
commands from [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills),
and the `adhd` skill is [UditAkhourii/adhd](https://github.com/UditAkhourii/adhd)
(both installed separately — see [Install](#install)). The straightforward idea
step needs neither; its instructions are inline in `generate-idea/conduit.yaml`.

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
run_path: /abs/path/to/your/repo   # required: the working dir the tick runs in
inputs:
  project_root: /abs/path/to/your/repo
  n_ideas: "2"
  n_adhd: "1"
  n_reviews: "1"
  n_todo: "5"
  max_usage: "80"
schedule:
  mode: interval
  name: autonomous-projects-30min
  every_minutes: 30
  timezone: America/Bogota
```

Four ready-to-edit examples ship in `.atelier/schedules/` — a morning,
afternoon, evening and night profile with different counts and ceilings (the
night one runs the full default load; the evening one skips the divergent
pass). They are **examples, not installed state**: `atelier add` copies conduits
only, so nothing schedules itself. Set `project_root` and `run_path` in one and
add it:

```bash
atelier schedule add path/to/schedule.yaml
atelier scheduler start      # foreground daemon; Ctrl+C to stop
```

To drive several repos, add one schedule per repo, each with its own
`project_root`. Overnight, each tick advances its repo's project: tops up the
backlog with the ideas and reviews you asked for, improves any raw tasks you
dropped, and advances up to `n_todo` approved to-do tasks through the two-agent
DONE loop — skipping any activity whose harness is over your usage ceiling. You
wake up to a triaged backlog and reviewed diffs waiting for your yes.

**Single-flight (cron / custom timers).** A tick may run up to 2h, so on a
30-min interval a slow tick can still be working when the next fires — two runs
then race over the same project files. Wrap the invocation in `tick_lock.py` so
the second run prints a skip note and exits instead:

```bash
python3 .atelier/conduits/autonomous-projects/scripts/tick_lock.py \
  atelier run autonomous-projects --input project_root=/abs/path/to/your/repo
```

It takes an OS advisory lock for the whole run; the kernel releases it if the
run crashes or is killed, so a dead run never jams the loop.
