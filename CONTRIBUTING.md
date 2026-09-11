# Contributing

Thanks for helping. [AGENTS.md](AGENTS.md) holds the rules that apply to every change;
this page is the workflow around them.

## Setup

```sh
git clone https://github.com/mdelgert/omarchy-mise.git
cd omarchy-mise
mise install
mise run omarchy:check
```

`mise run omarchy:doctor` reports anything missing. Development needs Python 3.11+ and
mise; changing QML or running the desktop checks also needs an Omarchy install.

## Making a change

1. Branch from `main`.
2. Make the smallest coherent change. Read the file you are changing first.
3. Add a test in `tests/` for any behaviour change.
4. Update the documentation the change affects — a new setting means
   `config.example.toml`, [docs/CONFIGURATION.md](docs/CONFIGURATION.md), and the
   schema in `config.py`, all together.
5. `mise run omarchy:fmt` to format, `mise run omarchy:check` to verify.
6. On a desktop, `mise run omarchy:check-desktop`, and see any QML change running.
7. Add a `CHANGELOG.md` entry under Unreleased.

## What gets reviewed

- Does it respect the boundaries in [AGENTS.md](AGENTS.md)?
- Is there exactly one implementation of the behaviour?
- Does it fail usefully — a message naming what to fix, not a stack trace?
- Are new settings documented, defaulted, and validated?
- Was a QML change actually seen running?

## Commits

Write a short imperative subject and explain *why* in the body when it is not obvious.
Keep unrelated formatting out of the diff; `git diff --check` should be clean.

## Where to start

[docs/ROADMAP.md](docs/ROADMAP.md) lists the remaining v1 work in order, each item
scoped with the files it touches and how to know it is finished. R1 is the smallest.

Working with more than one person or agent at a time? Read *Working in parallel* at
the top of the roadmap first: the items form a dependency chain, so the split that
works is by file ownership, one git worktree per lane.
