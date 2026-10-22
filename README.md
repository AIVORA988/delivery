# delivery V1.0

面向存量系统增量开发与全新项目开发的 AI 研发交付 Skill。重需求、重方案、重任务拆分；审批后连续执行，按本期约定整体验收，文档与知识及时更新。

![delivery V1.0 架构流程图](docs/architecture.png)

## 安装到项目

在目标项目中让支持 Skill 的 Agent 执行：

```text
请将 https://github.com/longzhang2026-sudo/delivery 中的 skills/delivery
安装到当前项目的 .agents/skills/delivery，仅作用于当前项目。
保留已有规则；已有同名 Skill 时先比较差异，不直接覆盖。
```

私有仓库需使用已有 GitHub 访问权限。也可检出仓库，将 `skills/delivery` 完整复制到目标项目的 `.agents/skills/delivery`，包含全部引用文件和模板。Codex 项目级发现规则见 [OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)。若安装后未出现，重新打开会话或重启客户端。

其他 Agent 可读取 `skills/delivery/SKILL.md` 并按需读取相对引用；是否自动发现或支持 `$delivery` 取决于宿主能力。Skill 无额外运行依赖，构建和验证复用目标项目工具。

## 最简单的用法

**先出方案：**

```text
$delivery 我要实现【需求】。先调查现状，形成需求、方案、任务拆分和
本期验收约定，提交我审批；暂不修改业务代码。
```

**方案通过后执行：**

```text
$delivery 我批准这份方案和任务清单，按其中的执行范围与限制实施本批次。
在范围内连续执行、验证和修复，最后做整体验收并更新交付文档。
```

**中断后继续：**

```text
$delivery 继续当前已批准批次。先核对实际工作区、任务、证据和累计限额，
从上次入口恢复，不重复已完成且仍有效的检查。
```

也可指定“只执行 T02”“只做本期验收”“补充后续真实环境专项结果”。已有审批在适用范围内继续有效。

## 工作方式

`Mission → Explore → Contract → Graph → 审批关口 → Loop → Acceptance → Knowledge`

- 前四阶段准备目标、事实、方案、任务依赖和验收方法，集中审批。
- Loop 在已批准范围内执行、检查、诊断、修复与重验；缺少必需条件、待决策、到限或无进展时保存入口。
- 整体验收检查需求及任务组合，采用已批准的方法。真实环境并非所有任务的统一前置条件；已列后续的专项保持未验证，本期可按约完成。
- 文档和知识随决策、实现、检查更新，后续实测再补充。用户负责目标、审批和接收，Agent 维护编号、状态与证据。

## 文件入口

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](skills/delivery/SKILL.md) | 主入口与七阶段职责 |
| [planning.md](skills/delivery/references/planning.md) | 前期设计、任务和审批 |
| [execution.md](skills/delivery/references/execution.md) | Loop、证据、验收、知识与恢复 |
| [delivery-plan.md](skills/delivery/assets/delivery-plan.md) | 可裁剪的单篇主清单模板 |
| [详细设计 PDF](docs/delivery-v1.0.pdf) | 完整设计说明 |
| [检查记录](docs/validation.md) | 封装检查及验证边界 |

这是供 Agent 读取的流程与模板包，实际执行依赖宿主工具、项目能力和有效授权。Skill 不自行启动后台任务，不自动授予发布、外部写入或无限重试权限。工作流实际效果仍需项目试点验证。
