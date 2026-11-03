<p align="center"><img src="docs/banner.svg" alt="delivery — Plan. Approve. Deliver." width="100%"></p>

<p align="center">
  <a href="https://github.com/AIVORA988/delivery/actions/workflows/ci.yml"><img src="https://github.com/AIVORA988/delivery/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-33bda7" alt="MIT"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/workflow-V1.0-2563eb" alt="Workflow V1.0"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab" alt="Python 3.10+">
  <a href="README.en.md">English</a>
</p>

# delivery

**面向 AI Agent 的轻量级研发交付工作流**

将需求与方案、人工审批、任务执行、验证证据和知识复用连接为一个交付闭环。支持存量系统增量开发与全新项目，不绑定特定 Agent、模型、工具链或 MCP。

用户确定目标、审批方案并接收成果；Agent 负责调查、设计和实施；Skill 定义行为规范，Python Guard 校验记录、文件版本与授权范围。

[七阶段工作流](#七阶段工作流) · [快速开始](#快速开始) · [日常研发双路径](#日常研发双路径) · [知识复用](#知识沉淀与复用) · [文档与验证](#文档与验证)

## 七阶段工作流

[![七阶段工作流：独立人工审批、任务执行验证修复闭环，以及贯穿全流程的 Harness 横向支撑](docs/diagrams/seven-stage-workflow.svg)](docs/diagrams/seven-stage-workflow.svg)

**人工审批是独立关口，位于 Graph 与 Loop 之间。** 批准后在授权范围内执行；任务完成后仍须整体验收，知识随实施持续更新。

**Loop** 按任务依赖推进实施、验证、失败归因、授权内修复与重验。**Harness** 为七阶段提供规则、工具、环境、权限、质量检查、证据与恢复支撑；Agent 执行研发操作，Guard 只读校验记录。[职责与实现边界](docs/design.md#职责分离与工具解耦)

## 快速开始

在目标项目中使用支持 Agent Skills 的工具。Python 工具需要 **Python 3.10+**，仅使用标准库；Skill 发现和调用语法以宿主支持为准。

### 1. 安装

```text
请从 https://github.com/AIVORA988/delivery 安装完整五个 Skill 到当前项目，
初始化知识库，保留已有规则、本地修改与需求记录。
```

Agent 按 `inspect → init → check` 接入，将五个 Skill 安装到 `.agents/skills/`，创建缺失的 `docs/knowledge/README.md` 并登记路径。安装不运行知识深度分析或业务测试；`CONFIGURED` 仅表示接入检查通过。[手工安装、ZIP 安装与升级](START.md)

### 2. 提需求

| 场景 | 使用示例 | 任务上限 |
| --- | --- | --- |
| 简单 Bug / 低风险功能调整或新增 | `$delivery 修复订单状态筛选异常。` | 整个需求 ≤3 |
| 存量系统复杂需求 | `$delivery 为现有商城新增拆单发货功能。` | 整个需求 ≤15 |
| 全新中大型项目 | `$delivery-feature 根据 docs/design 下的架构与详细设计，规划商城系统，按 Feature 拆分任务。` | 每 Feature ≤30 |

普通入口自动判断设计深度；支付、权限、迁移、公共契约或共享一致性变更按风险充分设计，不因改动小而简化。新中大型项目须提供架构与详细设计。任务上限包含已完成任务，不按审批批次重算；超限时重新划分合理边界，不强行合并任务。

### 3. 审批执行

Agent 先提交方案、任务依赖、验收标准、操作范围和有限执行规则。阅读并同意后回复：

```text
批准当前方案和任务清单，按约定范围与执行限制开始执行。
```

需调整则修订方案并重新呈交；明确批准且授权开始后，Agent 使用对应执行入口，在有效授权内连续执行，不逐任务重复审批。指定“只给方案”“暂不执行”或“只执行本模块”时遵守该限制；调用执行 Skill 本身不构成批准。

## 日常研发双路径

[![日常研发双路径：普通需求与 Feature 项目共用人工审批、验收和知识复用](docs/diagrams/daily-dual-path.svg)](docs/diagrams/daily-dual-path.svg)

| Skill | 职责 |
| --- | --- |
| [`$delivery`](skills/delivery/SKILL.md) | 普通 / 存量需求规划，形成方案、任务与审批材料 |
| [`$delivery-run`](skills/delivery-run/SKILL.md) | 执行或恢复已批准的普通方案，按依赖运行 Task Loop |
| [`$delivery-feature`](skills/delivery-feature/SKILL.md) | 基于架构与详细设计规划新中大型项目，明确 Feature、接口契约和两层依赖 |
| [`$delivery-feature-run`](skills/delivery-feature-run/SKILL.md) | 确认本轮一个或多个已批准 Feature，逐模块执行子任务与模块验收 |
| [`$delivery-bootstrap`](skills/delivery-bootstrap/SKILL.md) | 用户明确要求时集中构建存量知识；不修改业务代码，不是研发前置步骤 |

两条路径共用上述七阶段及同一方案与记录。方案、任务或稳定设计 / 接口契约实质变化时，回到原人工审批关口复核。

完整架构与细节：[架构主图](docs/architecture.png) · [审批授权](docs/diagrams/01-approval-gate.png) · [执行修复](docs/diagrams/02-execution-loop.png) · [验收证据](docs/diagrams/03-acceptance-evidence.png) · [设计原则与 Harness 边界](docs/design.md)

## 执行闭环与分批恢复

普通需求按任务依赖执行 **实施 → 验证 → 失败分类 → 授权内修复 → 重验**。必要证据有效才标记 `DONE` 并推进依赖任务；缺少必需条件、需要决策、到限或外部结果不明时保存原因与恢复入口，不盲目重试。

Feature 项目先选择本轮一个或多个已批准模块。未完成前置须显式同选，或已通过模块验收；不擅自补选。默认按依赖串行，先完成当前 Feature 的子任务与模块验收，再推进下一个。无原生多选控件时使用对话编号列表；取消或未回答不执行。

[![Feature 分批交付闭环：子任务、模块验收、本轮交接与系统整体验收](docs/diagrams/feature-task-loop.svg)](docs/diagrams/feature-task-loop.svg)

中断或下次分批实施时调用原执行入口：

```text
$delivery-run 继续当前已批准方案，先核对实际工作区、证据与累计用量。
```

Feature 项目调用 `$delivery-feature-run` 后重新选择本轮范围。均复用原 `plan.md` / `record.json` 与有效授权，保留历史批次和累计限额，跳过仍有效的 DONE。**本轮所选完成、批准批次完成与系统整体交付是不同判定。** [完整交互与恢复规则](docs/usage.md)

## 验收与 Guard 边界

| 检查面 | 当前实现 |
| --- | --- |
| 审批与依赖 | 校验 plan / Graph 基线、任务 / Feature 依赖、批准任务及路径、记录中的累计修复与时间限制；合法历史 DONE 保留其授权依据 |
| 实际范围 | 新 Git 需求保存起始工作区，核对暂存、未暂存、未跟踪及已提交的累计差异；执行方保留操作前检查点，用 `--changes-since` 核对本轮变化是否属于当前任务，保留此前批次未变的合法成果。旧记录 / 非 Git 项目须人工核对 |
| 验证证据 | 核对当前基线、方法、源码 / 产物和原始报告版本；文件变化使相关旧 PASS 失效，保留历史证据 |
| 最终接收 | 全部任务合法 DONE、任务 / 模块 / 整体必需检查与文档知识交接就绪后才生成摘要，绑定证据、交付文件及 Git 可见成果差异；实际接收须覆盖当前版本，不自动沿用旧接收 |

已完成依赖链返修时，先复核并回退受影响后继、使相关检查待重验，再按原授权和累计限额恢复执行。升级后，有 Git 起点的旧接收可能因增强成果绑定而失效；任务与审批保留，接收须按当前版本核实。[执行与兼容规则](skills/delivery/references/execution.md)

本期验收可采用获批的源码审查、构建、测试、本地、Mock 或真实环境方法，结论限定在实际覆盖范围。已批准的后续验证专项独立保留 `NOT_VERIFIED`；本期必需检查不能自行后移。任务或模块分别通过不替代完整业务链路、异常与回归验收。

Guard 是只读确定性校验器，不运行项目测试、自动计时、实时拦截命令或认证审批 / 接收身份。Git 核对不能归因多方改动，也不覆盖已撤销的瞬时写入、被忽略的未跟踪文件或项目外操作；plan / record 语义一致性、报告真实性及业务影响仍需复核。当前没有后台调度器、完整流程执行引擎或权限沙箱。安装与结构校验不代表业务验收通过。[记录契约](skills/delivery/references/record.md) · [安全说明](SECURITY.md)

## 知识沉淀与复用

**初始化入口 → 按需检索并核对源码 → 方案采用 → 实施更新 → 验收整理 → 下一需求复用。**

[![目标项目文档结构：.agents/skills 安装五个 Skill；.delivery 保存接入配置与需求的 plan.md、record.json；docs/knowledge 保存索引与按需生成的项目、模块、决策、指南、经验和交付知识](docs/diagrams/document-structure.svg)](docs/diagrams/document-structure.svg)

图示为**目标项目接入后的默认目录**。`.delivery/runs/<需求ID>/plan.md` 保存可读审批方案，`record.json` 保存任务、审批、证据引用、用量与恢复入口；长期知识以 `docs/knowledge/README.md` 为索引。除知识入口外，正文和目录按需生成。确认空库时跳过空文档；有内容时定向检索，核对当前源码和适用版本，不全量加载。已有文档原位维护并建立索引；必要更新纳入批准任务，随实施持续沉淀，不等待已批准的后续真实环境验证。保留来源、验证边界与未知项；无增量说明理由，不机械新增文档。内部记录由 Agent 维护，用户无需填写 JSON 或摘要。

需要集中梳理存量项目时单独调用：

```text
$delivery-bootstrap 梳理订单与支付模块，保留已有文档，记录源码依据、未验证范围和继续入口。
```

新项目仍需验证首个可运行闭环，存量项目仍需兼容与受影响路径回归；知识不替代审批或验证。[知识目录与复用规则](skills/delivery/references/knowledge.md)

## 文档与验证

| 文档 | 内容 |
| --- | --- |
| [安装与维护](START.md) · [使用手册](docs/usage.md) | 手工接入、升级、规划、审批、执行和恢复 |
| [设计原则](docs/design.md) · [共享记录契约](skills/delivery/references/record.md) | 职责边界、审批基线、Guard 与历史兼容 |
| [本地交付示例](examples/local-delivery.md) · [验证说明](docs/validation.md) | 可运行演示、自动测试、CI 与未覆盖范围 |

在本仓库根目录运行：

```bash
python examples/try_delivery.py
python -m unittest discover -s tests -v
```

演示在临时目录实际执行两个本地检查进程，展示未批准阻止执行、当前范围完成和源码变化后的证据失效；审批与接收均为合成夹具，不访问外部业务系统。

工作流 **V1.0** · 分发包 **1.0.0** · [MIT](LICENSE) · [贡献指南](CONTRIBUTING.md) · [版本记录](CHANGELOG.md)
