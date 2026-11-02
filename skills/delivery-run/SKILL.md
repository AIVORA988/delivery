---
name: delivery-run
description: 执行或恢复已获人工审批的普通或存量需求方案，按任务依赖进行实施、验证、修复和重验，完成整体验收与知识更新。不能代替方案审批；Feature 型计划使用 delivery-feature-run。
metadata:
  version: "V1.0"
---

# delivery-run

执行入口，不重新规划，不将本 Skill 的调用当作审批。读取项目规则与原 run；未指定 run 且候选不唯一时才请用户选择。核对实际审批来源、当前基线、范围、依赖、工作区及累计用量；没有有效审批则回到 [delivery](../delivery/SKILL.md) 的关口，保留已有成果，不伪造批准。

初次接入或升级用共享 [setup.md](../delivery/references/setup.md)，记录规则用 [record.md](../delivery/references/record.md)。scenario=feature 时转 [delivery-feature-run](../delivery-feature-run/SKILL.md) 选择范围，不能在此直接执行全部 Feature。旧版无 scenario 的已批准记录可按原语义恢复，不擅自改写基线。

读取唯一 [execution.md](../delivery/references/execution.md)，按已批准任务依赖运行 Task Loop。每个任务开始 / 恢复前用配套脚本 `guard --project <项目> --id <原需求ID> --task <TaskID>`，须退出 0 且 execution_ready=true；检查当前实际操作仍在授权范围。PENDING 只有在实际依赖满足后才转 READY。

每项实施后验证；失败先分类，在限额内诊断、修复、重验；通过且证据有效才 DONE 并推进下一任务。不逐任务重复审批。用户指定单步或子集时只执行该范围；实质方案 / 契约变化回到原审批关口，保留历史和累计用量。

本批次结束保存实际结果与恢复入口；当前范围全部任务完成后做独立整体验收和约定接收，不能用 batch_complete 替代 delivery_ready。按共享 [knowledge.md](../delivery/references/knowledge.md) 持续更新文档与知识，不等待已批准后续专项，不将 Mock 结果当作真实环境通过。
