<p align="center"><img src="docs/banner.svg" alt="delivery" width="100%"></p>

# delivery

**Plan with intent. Execute with approval. Deliver with evidence.**

[中文](README.md) · [MIT](LICENSE) · [CI](https://github.com/longzhang2026-sudo/delivery/actions/workflows/ci.yml)

A project-local Agent Skill for incremental work and the first usable slice of a new project. Workflow V1.0, package 1.0.0, Python 3.10+, standard library only.

## Start

Ask your agent to install `skills/delivery` from this repository into the target project's `.agents/skills/delivery`, preserve existing rules, then run inspect → init → check. See [START.md](START.md) for paths and conflict handling.

```text
$delivery Investigate this requirement and prepare the scope, design, task graph,
acceptance methods and execution boundaries. Present it for approval before implementation.
```

After actual approval, continue within the approved batch. Existing valid approval carries across sessions. A request to execute only one task remains binding.

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
