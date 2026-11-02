<p align="center"><img src="docs/banner.svg" alt="delivery" width="100%"></p>

# delivery

**A lightweight, agent-agnostic workflow for approval-gated, evidence-based software delivery.**

[中文](README.md) · [MIT](LICENSE) · [CI](https://github.com/AIVORA988/delivery/actions/workflows/ci.yml)

delivery supports incremental development in existing systems and new projects. It establishes requirements and design baselines before implementation, coordinates work through human approval and task dependencies, and records verification evidence for acceptance and knowledge capture. It does not depend on a specific agent, model, toolchain, MCP server or cloud service.

Agents advance the workflow and perform development work. The Agent Skill defines behavioral rules; the Python Guard performs deterministic validation of records and referenced files. Users define goals, approve scope, make key decisions and accept deliverables.

Workflow V1.0, package 1.0.0, Python 3.10+, standard library only.

## Workflow architecture

[![delivery V1.0 workflow architecture](docs/architecture.png)](docs/architecture.png)

[View the full-resolution diagram (Chinese)](docs/architecture.png)

## Quick start

Use a tool that supports Agent Skills in your target project. This example requires detailed design and approval. After installation, independent low-risk fixes can be requested directly; the agent selects the appropriate path.

### 1. Install

```text
Install delivery from https://github.com/AIVORA988/delivery into the current project,
including both Skills and the knowledge entry. Preserve existing rules and local changes.
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
perform overall acceptance and update the usage instructions. Keep live-payment checks
pending only when they have explicitly been approved as follow-up validation.
```

See [START.md](START.md) for manual installation and conflict handling.

## Two Skill entry points

| Skill | Purpose |
| --- | --- |
| `$delivery` | Daily development, including targeted knowledge retrieval, approval, execution, acceptance and incremental updates |
| `$delivery-bootstrap` | Explicit, scoped knowledge construction for an existing project, with source references and resumable coverage |

Daily work only needs `$delivery`. When an existing project needs a dedicated knowledge pass:

```text
$delivery-bootstrap Document the order and payment modules. Preserve existing documentation,
cite sources, distinguish unverified behavior and record where to continue.
```

Bootstrap does not run during installation, modify application code, or add a development stage. Both Skills ship together; discovery and invocation syntax depend on the host.

## Small fixes, detailed design and module batches

Use `$delivery` for daily work. The agent selects a path based on risk:

- **Independent, low-risk fixes and internal API adjustments:** investigate, implement and run focused checks plus relevant regression tests under the user's actual fix authorization. Separate plans, run records and knowledge articles are not mandatory.
- **Complex or high-risk requirements:** complete the applicable business, interface, data, failure, concurrency, consistency, compatibility and acceptance design before approval and implementation.
- **Cross-module work:** use one design and Graph across calls, with producer/consumer contracts, dependencies, retained approval batches and a final integration task.

The lightweight path compresses the seven responsibilities and reuses explicit authorization; it does not bypass project rules or an existing standard run. Payment, authorization, migrations, public contract changes and shared business rules require risk review regardless of patch size. Requests limited to planning or one module remain binding.

After installation, send the prompt that matches your task, for example:

- **Small fix:** `$delivery Fix pagination not resetting when a filter changes. Preserve ordinary paging and run the relevant regression checks.`
- **Detailed design:** `$delivery Add multi-warehouse stock reservations and cancellation releases to this store. First prepare an implementable design, task plan and acceptance criteria. Wait for approval before implementation.`
- **Module batch:** `$delivery Continue the existing stock reservation run. Implement only the approved inventory module, reuse the design, contracts and records, verify it and hand it off. Do not proceed to the order module.`

Optional `record.contracts` binds stable external design or API files to the existing baseline. Content changes invalidate approval and evidence. Guard's `--task` checks a specific task; `batch_complete` describes the current approved batch, while `delivery_ready` still requires overall acceptance. These are record checks, not runtime interception. See [Usage](docs/usage.md) for short prompts (Chinese).

## Workflow and example

The seven stages are **Mission → Explore → Contract → Graph → Loop → Acceptance → Knowledge**. A separate **Approval Gate** sits between Graph and Loop.

| Term | Responsibility |
| --- | --- |
| Mission | Requirements understanding |
| Explore | Current-state investigation |
| Contract | Design finalization |
| Graph | Task planning |
| Approval Gate | Human approval of the baseline, scope and permitted operations |
| Loop | Execution and verification, failure classification, repair, reverification and recovery |
| Acceptance | Overall acceptance and delivery |
| Knowledge | Documentation and knowledge capture |

The approved baseline includes requirements, design, tasks and acceptance methods. Agents continue within the approved batch while respecting dependencies, scope and recorded limits. Material changes require review of the affected parts. Harness capabilities provide cross-cutting support for project rules, tools, environments, permissions, quality checks, evidence and recovery.

```bash
python examples/try_delivery.py
python -m unittest discover -s tests -v
```

The isolated fixture runs real local checks, demonstrates a blocked unapproved draft, current-scope completion with an unverified external followup, then invalidates evidence after source changes. Fixture approvals are synthetic, not real project acceptance.

## Workflow details

Click a diagram to view the full-resolution original (Chinese). See [Usage](docs/usage.md) for the corresponding steps.

### 01 · Approval and authorization gate

[![01 · Approval and authorization gate](docs/diagrams/01-approval-gate.png)](docs/diagrams/01-approval-gate.png)

### 02 · Execution and repair loop

[![02 · Execution and repair loop](docs/diagrams/02-execution-loop.png)](docs/diagrams/02-execution-loop.png)

### 03 · Acceptance and evidence loop

[![03 · Acceptance and evidence loop](docs/diagrams/03-acceptance-evidence.png)](docs/diagrams/03-acceptance-evidence.png)

## Core validation mechanisms

- **Approval baseline consistency**: approval is bound to plan and task-definition hashes. Material changes invalidate the baseline; routine progress updates do not.
- **Task dependencies and authorization scope**: check acyclic dependencies, approved batches and path boundaries. DONE tasks require valid current or historical approval coverage.
- **Evidence validity**: source, artifact and raw-report fingerprints must match. Changed files invalidate the current result; historical evidence is retained.
- **Bounded repair and recovery**: validate recorded repair counts and elapsed time against limits, retaining cumulative usage and recovery details across interruptions. Unconfigured limits do not imply unlimited execution.
- **Separate task and overall acceptance**: task completion does not replace overall acceptance, a recorded receipt or required handoff materials.
- **Current delivery scope and follow-up validation**: explicitly approved follow-ups remain separate, while documentation and knowledge are updated as work progresses.

The read-only Guard is a deterministic validator of record consistency and referenced files. It does not execute project commands, authenticate reviewers, establish report authenticity, or enforce an operating-system sandbox. Agents and the agreed recipients remain responsible for execution, impact analysis and business acceptance under project rules. Installation success means CONFIGURED, not application correctness.

## Acceptance scope and evidence validity

Current-scope acceptance may use approved local, Mock, test-environment, source-review or demonstration methods. Conclusions apply only to the coverage actually verified; tasks need not pass through every environment tier. Required live-environment checks must pass within the current scope and cannot be silently deferred.

When all required task checks, overall acceptance, handoff materials and the agreed receipt are complete, the current delivery scope may be declared complete. Approved follow-up validation retains its own NOT_VERIFIED status and recovery entry. Documentation and knowledge evolve with actual decisions, implementation and executed checks; subsequent live results supplement those records.

## Project integration and implementation boundaries

The default files are `plan.md` for the reviewable plan and `record.json` for task state, approvals, evidence and handoff records. Agents maintain the internal records. Existing project rules and local changes are preserved; existing plans and records may be reused without mandatory migration. Isolated investigations and minor fixes follow the project's lightweight process.

## Knowledge capture and reuse

**Initialize → Read → Reference → Update → Review → Reuse.**

Installation deploys both Skills and creates only `docs/knowledge/README.md`, registering the path in `knowledge_paths`. Other files are created when useful:

```text
docs/knowledge/
├── README.md       Topic index, coverage and continuation points
├── project.md      Project overview and constraints
├── modules/        Module rules, interfaces and data relationships
├── decisions/      Significant decisions and applicability
├── guides/         Development, operation and verification procedures
├── lessons/        Reusable diagnoses, fixes and prevention
└── deliveries/     Delivery summaries with lasting reference value
```

Existing architecture, API and operations documents remain in place and are linked rather than duplicated. A confirmed empty knowledge base is skipped. Otherwise, agents retrieve relevant material, verify it against current sources, and explain what the plan adopts, updates or rejects. An outdated index or incomplete scan does not establish emptiness.

Required documentation changes belong to the approved task scope. Implementation updates affected topics; acceptance checks consistency, sources, limitations and relevant links. Capture scope, conclusions or steps, provenance, verification limits and the actual update date. No increment requires a reason, not a redundant document. Future requests retrieve and revalidate the knowledge; interrupted construction resumes from recorded coverage.

New projects still require a runnable first slice and applicable verification. Existing projects still require compatibility, invariants and regression checks. Knowledge supports these checks; it does not replace approval, evidence or overall acceptance. See the shared [knowledge rules](skills/delivery/references/knowledge.md) (Chinese).

The package supports direct Skill installation and a project-local setup script, with optional plugin manifests. It includes no independent background scheduler, complete programmatic workflow engine, operating-system permission sandbox, approval identity authentication or automatic production release capability.

[Workflow](skills/delivery/SKILL.md) · [Usage](docs/usage.md) · [Record contract](skills/delivery/references/record.md) · [Validation](docs/validation.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
