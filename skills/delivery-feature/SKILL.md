---
name: delivery-feature
description: 基于用户提供的详细设计（支持附件）规划全新中大型系统，定义 Feature 边界、接口契约、依赖和每 Feature 最多 30 个任务，提交整体方案人工审批。批准后路由到 delivery-feature-run，不在规划阶段实施业务代码。
metadata:
  version: "V1.0"
---

# delivery-feature

这是 Feature 规划入口，不是执行入口。复用七阶段，负责 Mission → Explore → Contract → Graph 与原人工审批关口；不增加第二套审批、计划或任务库。

读取项目规则、用户提供的详细设计、原计划和工作区。一份详细设计即可，支持直接上传附件或引用已有文件；不要求同时提供独立架构文档，也不要求用户放入 docs/design 或其他固定目录。按 [setup.md](../delivery/references/setup.md) 接入，按 [knowledge.md](../delivery/references/knowledge.md) 判断空库或按需复用。按内容复核必要设计，关键缺口列出并停在规划；不因文档数量或位置阻塞，也不自行把猜测或未确认架构当成批准输入。

附件由 Agent 读取并保存为项目内可追溯的稳定副本，优先沿用项目已有资料目录，否则使用本需求的 .delivery/runs/<需求ID>/inputs/；不要求用户自行搬放或另写文档。保留附件来源和原意；无法读取时明确说明并请求可读材料，不补造内容。已有项目内文件原位引用，避免重复副本。

按共享 [planning.md](../delivery/references/planning.md) 复核业务、架构、接口、数据、异常、并发、一致性、兼容、回退与验收。新建记录使用 [共享脚本](../delivery/scripts/delivery.py) 的 `new --project <项目> --id <需求ID> --title <标题> --scenario feature`。将实际引用的详细设计文件或附件稳定副本登记到 contracts，纳入审批摘要，单个文件即可；用户另有架构或接口资料时按实际引用补充，不强制补齐第二份文档。记录结构见 [record.md](../delivery/references/record.md)。

先固定本期完整 Feature 和任务定义，再分批实施；超过边界重新拆分合理需求或 Feature，不隐藏独立任务。每个 Feature 有稳定 ID、业务目标、接口提供方 / 消费方、必要依赖和模块验收 checks；每项任务唯一归属一个 Feature，每个 Feature 1-30 项任务，DONE 也计数。任务跨 Feature 依赖必须与 Feature 依赖一致，两层依赖均无环。保留整体业务链路与最终集成验收；Feature 不是按文件夹机械切分。

输出一份可审批 plan 与完整 Graph，明确 Feature 与子任务、设计来源、验证方法、允许操作及有限执行规则，停在实施边界等待真实审批。需调整则修订并重交。首次提需求、执行 Skill 名称或沉默都不等于批准；Agent 不补造审批。

用户批准整体方案和任务范围并授权开始后，使用 [delivery-feature-run](../delivery-feature-run/SKILL.md) 确定本轮一个或多个 Feature；本轮已明确指定时直接校验，不重复选择，不因选择范围重复审批。用户只批准或明确暂不实施时保存批准并停止。Feature 分批授权以完整模块为单位，所选模块的全部未完成任务须获当前授权；完整授权后，本轮仍可只执行指定子任务。只批准部分子任务时说明模块所缺授权，不擅自补批；选择只能缩小有效授权，不能扩大。

批准后不把进度追加到冻结 plan，状态、证据与交接只写同一 record。新增 Feature / Task、改归属或依赖、设计 / 契约实质变化使整体基线失效，分析受影响模块后复核原关口与相关证据，不自动迁移历史 DONE / PASS。
