# AI Context Index

## Purpose

This directory is the repository's persistent, agent-independent project knowledge. It explains the codebase; it does not replace the code.

## Quick start

1. Read `AGENTS.md`.
2. Read this file.
3. Read `PROJECT.md`, `CURRENT_STATE.md`, `TASKS.md`, and `HANDOFF.md`.
4. Route the task to the relevant context below.
5. Verify context against the actual source code before changing anything.
6. Make the smallest safe change, test it, and update context plus handoff.

## Project identity

| Field | Value |
|---|---|
| Project | Backup Control Center (BCC) |
| Domain | Desktop support and monitoring for autonomous remote backups |
| Runtime | Python 3 / Windows primary |
| UI | CustomTkinter |
| Persistence | SQLite in Windows AppData |
| Remote access | Paramiko SSH/SFTP, often over Tailscale |
| Current status | Functional desktop application; live SSH checks require operator network |

## Context map

| Context | File | Read when |
|---|---|---|
| Project overview | `PROJECT.md` | Every task |
| Current state | `CURRENT_STATE.md` | Every task |
| Handoff | `HANDOFF.md` | Every task |
| Architecture | `ARCHITECTURE.md` | Service, UI, deployment, or integration work |
| Modules | `MODULES.md` | Locating implementation |
| Database | `DATABASE.md` | Schema, repository, or migration work |
| Conventions | `CONVENTIONS.md` | Every code change |
| Decisions | `DECISIONS.md` | Architectural or behavior changes |
| Roadmap | `ROADMAP.md` | Planning or prioritization |
| Tasks | `TASKS.md` | Selecting and closing work |
| Changelog | `CHANGELOG.md` | Significant completed changes |

## Task routing

| Task area | Start with |
|---|---|
| UI/view | `CONVENTIONS.md`, `MODULES.md`, `architecture/frontend.md` |
| SSH/deploy/backup/monitor | `ARCHITECTURE.md`, `MODULES.md`, `architecture/infrastructure.md` |
| Database/repository | `DATABASE.md`, `database/tables.md`, `database/migrations.md` |
| Security/secrets | `CONVENTIONS.md`, `architecture/security.md`, `DECISIONS.md` |
| Packaging/operations | `PROJECT.md`, `CURRENT_STATE.md`, `architecture/infrastructure.md` |

The detailed routing documents are intentionally short and may point directly to source files.

## Source-of-truth hierarchy

1. Running behavior
2. Actual source code
3. Schema and migrations
4. Tests and smoke checks
5. This context
6. General documentation
7. Agent assumptions

For accepted architecture decisions, `DECISIONS.md` is the official record; changes require a new ADR.

## Context health

Last audit: 2026-08-17. The top-level context files match the current repository shape. Live remote behavior and AppData inventory remain unverified from this workspace.

## Agent protocol

See `agents/onboarding.md`, `agents/workflow.md`, and `agents/handoff.md`.
