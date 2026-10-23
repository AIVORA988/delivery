<p align="center"><img src="docs/banner.svg" alt="delivery" width="100%"></p>

# delivery

**Plan with intent. Execute with approval. Deliver with evidence.**

[中文](README.md) · [MIT](LICENSE) · [CI](https://github.com/AIVORA988/delivery/actions/workflows/ci.yml)

A project-local Agent Skill for incremental work and the first usable slice of a new project. Workflow V1.0, package 1.0.0, Python 3.10+, standard library only.

## Workflow architecture

[![delivery V1.0 workflow architecture](docs/architecture.png)](docs/architecture.png)

[View the full-resolution diagram (Chinese)](docs/architecture.png)

## Quick start

Use an agent that supports Skills in your target project and send these three prompts in order:

### 1. Install

```text
Install the delivery Skill from https://github.com/AIVORA988/delivery
into the current project and initialize it. Preserve existing rules and local changes.
```

### 2. Describe the requirement

```text
Use the delivery Skill to build a shopping WeChat Mini Program with product browsing,
a cart, checkout with WeChat Pay, and order lookup. First present the requirements,
design, task breakdown and acceptance methods. Wait for my approval before implementation.
```

### 3. Approve and execute

Send this after reviewing and approving the plan:

```text
I approve the current plan and task scope. Use the delivery Skill to implement it, verify the result,
perform overall acceptance and update the usage instructions. Keep any live-payment
checks pending when their prerequisites are unavailable.
```

See [START.md](START.md) for manual installation and conflict handling.

## Run a local demonstration

```bash
python examples/try_delivery.py
python -m unittest discover -s tests -v
```

The isolated fixture runs real local checks, demonstrates a blocked unapproved draft, current-scope completion with an unverified external followup, then invalidates evidence after source changes. Fixture approvals are synthetic, not real project acceptance.

## What it checks

- Plan and task-definition hashes bound to the recorded approval.
- Acyclic dependencies, approved batches and path boundaries.
- Recorded repair/time limits that survive recovery.
- Current source/artifact and raw-report fingerprints.
- Separate task and overall acceptance, receipt and handoff.
- Explicit external followups and timely documentation updates.

The read-only guard checks record consistency. It does not execute project commands, authenticate the reviewer, verify evidence honesty, or enforce an OS sandbox. Installation success means CONFIGURED, not application correctness. Real project effectiveness remains unpiloted.

Current-scope acceptance may use approved local, mock, test or review methods. A live-environment check blocks current completion only when explicitly required in that scope. Required checks cannot be silently deferred. Documentation and knowledge evolve with actual decisions, implementation and executed checks.

[Workflow](skills/delivery/SKILL.md) · [Usage](docs/usage.md) · [Record contract](skills/delivery/references/record.md) · [Validation](docs/validation.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
