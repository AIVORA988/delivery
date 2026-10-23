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

需求与方案前置 · 人工审批授权 · 受控迭代执行 · 基于证据验收 · 持续知识沉淀

delivery 覆盖需求理解、现状调查、方案定版、任务规划、执行与验证闭环、整体验收与交付、文档与知识沉淀七个阶段，在任务规划与执行之间设置独立的人工审批关口。

通过明确的需求与方案基线、人工审批授权、任务依赖约束和可追溯的验证证据，规范 Agent 在授权范围内的研发执行过程。适用于存量系统增量开发与全新项目开发，不绑定特定 Agent、模型或工具链，不依赖特定 MCP 或云服务。

**[架构流程图](#架构流程图) · [快速开始](#快速开始) · [流程辅图](#关键流程辅图) · [运行机制与示例](#运行机制与示例) · [使用手册](docs/usage.md) · [工作流规范](skills/delivery/SKILL.md)**

## 架构流程图

[![delivery V1.0 架构流程图](docs/architecture.png)](docs/architecture.png)

[查看高清原图](docs/architecture.png)

## 快速开始

在目标项目中使用支持 Agent Skill 的工具，依次发送以下三段 prompt：

### 1. 安装

```text
请从 https://github.com/AIVORA988/delivery 安装 delivery Skill 到当前项目，完成初始化，保留已有规则与本地修改。
```

### 2. 提需求

```text
使用 delivery Skill 开发一个支持微信支付的商城小程序，包含商品展示、购物车、下单支付和订单查询。先提交需求方案、任务拆分和验收方式，等我审批后再开发。
```

### 3. 审批执行

阅读方案并同意后发送：

```text
我批准当前方案和任务范围，请使用 delivery Skill 开始开发，完成后验证、整体验收并更新使用说明。真实支付条件不足的部分保留待验。
```

手工安装与冲突处理见 [START.md](START.md)。

## 运行机制与示例

Agent 负责流程推进和实际研发执行，Skill 定义行为规范，Python Guard 作为确定性校验器核对记录与所引用文件。使用者负责目标、人工审批、关键决策与交付接收。

Harness 提供横向支撑能力，涵盖项目规则、工具、环境、权限、质量门禁、验证证据与恢复。

```bash
python examples/try_delivery.py
```

本地隔离示例实际执行检查，依次展示以下结果：

1. 草稿尚未批准，不能进入执行。
2. 测试夹具批准后，范围内任务可以执行。
3. 本期任务、整体验收与交接条件满足，已批准的后续真实环境专项仍独立保留未验证状态。
4. 修改已检查源码后，Guard 判定原 PASS 证据失效。

演示使用临时目录和虚构审批，不访问外部业务系统，不代表真实项目已经通过。逐步解释见 [本地交付示例](examples/local-delivery.md)。

## 方案基线、审批授权与受控执行

七阶段主流程：**Mission → Explore → Contract → Graph → Loop → Acceptance → Knowledge**。人工审批关口位于 Graph 与 Loop 之间。

| 环节 | 重点产物 | 进入下一步的依据 |
| --- | --- | --- |
| Mission：需求理解 | 目标、范围、业务不变量与成功标准 | 需求、假设与未知项明确 |
| Explore：现状调查 | 现有能力、事实来源与差异分析 | 复用依据、必要变更与关键依赖明确 |
| Contract：方案定版 | 业务与技术方案、本期验收、阶段授权 | 设计决策与实施边界明确 |
| Graph：任务规划 | 唯一任务清单、任务依赖与验收定义 | 任务可执行、可验证、可交接 |
| Approval Gate：人工审批关口 | 实际确认来源、审批基线、任务批次与允许操作 | 方案、任务与验收方式获得明确批准 |
| Loop：执行与验证闭环 | 执行、验证、失败分类、修复、重验与恢复 | 当前任务满足本期必需验收，累计限制保留 |
| Acceptance：整体验收与交付 | 需求覆盖、任务集成、异常回归与实际接收 | 本期必需检查和必要交付材料齐备 |
| Knowledge：文档与知识沉淀 | 决策、实现、运行说明、验证证据与后续入口 | 按当前事实持续更新，后续实测补充 |

## 关键流程辅图

点击图片查看高清原图，操作说明见 [使用手册](docs/usage.md)。

### 01 · 审批与授权关口

[![01 · 审批与授权关口](docs/diagrams/01-approval-gate.png)](docs/diagrams/01-approval-gate.png)

### 02 · Loop 执行与修复闭环

[![02 · Loop 执行与修复闭环](docs/diagrams/02-execution-loop.png)](docs/diagrams/02-execution-loop.png)

### 03 · 验收与证据闭环

[![03 · 验收与证据闭环](docs/diagrams/03-acceptance-evidence.png)](docs/diagrams/03-acceptance-evidence.png)

## 核心校验机制

- **审批基线一致性**：审批绑定方案与 Graph 定义的摘要；验收、范围或依赖发生实质变更时原审批失效，常规进度更新不影响审批基线。
- **任务依赖与授权范围**：检测依赖环、缺失任务、依赖未满足及超出当前批准批次的活动；DONE 任务须有有效的当前或历史审批覆盖。
- **验证证据有效性**：源码 / 产物与原始报告摘要变化时，相关当前结果按未验证处理，保留历史证据。
- **有界修复与中断恢复**：核对记录中的累计修复次数与时间，未配置限制不视为无限执行；中断时保留原因与恢复入口。
- **任务完成与整体验收独立判定**：全部任务 DONE 后，仍须检查整体需求、集成结果、接收记录和必要交接材料。
- **本期验收与后续验证专项分别管理**：已批准的后续真实环境专项独立记录；文档与知识依据设计、实现和已执行检查持续更新。

Guard 只校验记录和所引用文件，不运行项目测试、不认证审批身份，也不证明报告真实性。实际执行、影响分析与业务验收仍由 Agent 和约定接收方按项目规则完成。

## 分层验收与证据有效性

本地、Mock、测试服务、源码审查或演示均可按批准的验收约定支持本期验收，结论限定在实际覆盖范围。不要求每个任务依次通过所有环境层级。本期明确要求的真实环境检查属于本期必需项，未满足时不能自行转为后续验证专项。

例如，本期约定交付页面与接口契约，使用本地和 Mock 验证业务路径；正式账号或部署联调已批准为后续验证专项。本期约定的验收与交接条件满足时，可以确认**本期研发交付完成**，同时保留正式联调的 **NOT_VERIFIED** 状态。文档与知识依据当前事实更新，后续实测补充验证证据。

## 轻量级集成与现有工程兼容

```text
your-project/
├── AGENTS.md                         原有规则保持原样
├── .agents/skills/delivery/           项目内 Skill、脚本和参考规则
└── .delivery/
    ├── project.json                  公共命令、规则与知识位置
    ├── install.json                  安装摘要与冲突检查
    └── runs/first-slice/
        ├── plan.md                   供审批阅读的方案
        └── record.json               Agent 维护任务、证据与交接
```

方案与运行记录默认使用 `plan.md` 和 `record.json`。已有可靠的计划与记录时可直接遵循 Skill 规则，不强制迁移；孤立排查和微小修复沿用项目轻量流程。内部记录由 Agent 维护，使用者无需填写 JSON、内部编号或摘要。

## 文档与示例

| 入口 | 内容与适用场景 |
| --- | --- |
| [START.md](START.md) | 第一次安装和接入项目 |
| [使用手册](docs/usage.md) | 规划、批准、执行、验收与恢复 |
| [Skill 主入口](skills/delivery/SKILL.md) | Agent 的七阶段职责和按需路由 |
| [项目接入](skills/delivery/references/setup.md) | 安装、升级、配置和故障处理 |
| [记录契约](skills/delivery/references/record.md) | 内部状态、审批摘要与证据校验 |
| [本地交付示例](examples/local-delivery.md) | 可运行场景与输出解释 |
| [验证说明](docs/validation.md) | 自动测试、CI 与校验范围 |
| [设计原则](docs/design.md) | Agent 无关、轻量记录与适用边界 |

## 开源信息

工作流 **V1.0**，分发包 **1.0.0**，Python **3.10+**，仅标准库。支持直接复制 Skill 或使用项目接入脚本，另附可选插件清单。

安装、审批、验证证据、验收与恢复的工程检查可重复执行。当前实现不包含独立后台调度器、完整的程序化流程执行引擎、操作系统权限沙箱、审批身份认证或自动生产发布能力。

[MIT License](LICENSE) · [贡献指南](CONTRIBUTING.md) · [安全说明](SECURITY.md) · [版本记录](CHANGELOG.md)

