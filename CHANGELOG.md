# Changelog

All notable changes to this project are documented here. Format mirrors [Keep a Changelog](https://keepachangelog.com).

## [Unreleased]

- feat: memory-spine tooling — append-only JSONL event stream at `.biltiq/memory-stream.jsonl` (per-machine, gitignored), curator that projects events into `MEMORY.md` between `auto:<name>:start/end` markers with fail-closed semantics, and an opt-in `post-commit` hook + installer that runs the curator in the background without aborting commits on failure (BILTIQ-003)

## [0.1.0] - YYYY-MM-DD

- feat: initial repo bootstrap (BILTIQ-000)
