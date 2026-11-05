---
name: delivery-feature-run
description: 在整体方案有效获批后，执行本轮指定的一个或多个 Feature，未指定或有歧义时收集选择；按依赖逐模块运行子任务执行、验证与修复闭环，支持恢复、模块验收及最终集成验收。
metadata:
  version: "V1.0"
---

# delivery-feature-run

读取原 Feature run、项目规则、实际工作区和真实批准依据；未审批、基线过期或材料缺失时回到 [delivery-feature](../delivery-feature/SKILL.md) 的原关口，不把执行请求或 Feature 选择当作批准。普通计划交由 [delivery-run](../delivery-run/SKILL.md)。升级与记录共用 [setup.md](../delivery/references/setup.md) / [record.md](../delivery/references/record.md)，不新建 Feature 状态库。

## 本轮选择

1. 先运行只读 Guard，记录有 issues 时先处理，不提供可执行选择。展示 Feature ID、名称、已完成 / 总任务数、模块验收、有效授权、未完成依赖和恢复位置。Feature 的全部未完成任务须获当前批次授权；只批准部分子任务不能选入整个模块，说明所缺授权，不自动扩大批准。完整模块授权后，本轮可只执行用户指定子任务，验证交接后停止。依赖未完成时说明可一并选择其已批准前置。
2. 本轮指令已明确一个或多个 Feature ID，或名称能唯一定位时，直接采用并校验执行，不重复选择或确认。未指定或存在歧义时，先收集本轮完整选择：
   - 优先使用支持勾选多项并统一确认 / 提交的宿主原生多选控件。勾选首项或中间变更不算提交，不得据此启动执行。
   - 无此能力、仅支持单选或能力不明确时，展示 Feature ID 列表，请用户在一条回复中一次性输入全部 ID，例如 `F01 F02 F03`（也可只填一个）。该回复即完成选择，不再单独确认；不用单选选项代替，不逐项询问，不安装 GUI。
   - 完整选择提交后才进入下方校验与执行；未提交、取消或未回答时停在选择处，不把首项、默认项或临时结果当作最终范围。不在每个子任务重新询问，不默默沿用上次选择。
3. 选中范围的未完成前置须同时被选择，或已经通过模块验收。遗漏时提示补选或调整，不擅自追加。选择只缩小原授权，不改变 approval 或 Graph；多选默认按依赖串行，不自动开启并行。
4. 运行 `guard --project <项目> --id <原需求ID> --features <F01> <F02>`，要求退出 0 且 selection_ready=true。按照返回 feature_order 推进；未完成前置或未授权选择不能启动。选择结果及下一入口可记入原 handoff.resume，不写批准 plan。

## Feature → Task Loop

读取唯一 [execution.md](../delivery/references/execution.md)。在选定范围内，先完成当前 Feature，再推进下一个；每个 Feature 包含多个子任务（允许单任务的合理小 Feature）。每个任务实际满足依赖后转 READY，开始 / 恢复前执行 `guard --project <项目> --id <原需求ID> --features <本轮全部ID> --task <TaskID>`，要求退出 0 且 execution_ready=true。

每项任务实施 → 验证 → 失败分类 → 授权内修复 → 重验，当前必需证据有效才 DONE。修复到限、结果不明或必需条件缺失按共享规则保存原因与进度；未解决时不推进依赖该结果的任务或 Feature，不重置累计用量。

按共享执行规则保留操作前 scope_checkpoint，并用 --changes-since 核对本轮实际变化；整体授权不代替本轮选择，跨批次旧改动与本轮新增修改分别判断。已完成模块返修先处理受影响后继和证据，再恢复子任务，不跳过依赖检查。

当前 Feature 全部任务 DONE 后，执行其获批 checks，按原证据结构保存实际模块验收结果；只有 Guard 的 features.complete=true 才推进依赖它的 Feature。任务全 DONE 但模块证据缺失时进行模块验收，不借用另一个任务的就绪结果。所选范围无可启动任务时读取阻塞原因，不忙等或自行更改设计。

本轮 selection_complete=true 只表示所选 Feature 完成；保存批次成果、未完成范围和恢复入口，按共享 [knowledge.md](../delivery/references/knowledge.md) 更新相关正文与索引。下次调用按本轮指令确定范围，明确指定时不重复选择；核实实际进度，跳过仍有效的 DONE。全部本期 Feature 完成后执行独立 overall 验收与约定接收；完整业务链路、异常和回归通过且交接齐备才判断 delivery_ready，不把模块分别通过当作系统已联通。
