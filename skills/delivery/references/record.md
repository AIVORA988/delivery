# Run Record v1：内部记录契约

仅在维护 `record.json`、运行 Guard 或诊断恢复时阅读。用户看到业务目标、审批材料与接收结果；以下字段由 Agent 维护。初始结构见 [run.json](../assets/run.json)。

## 一份需求，两个入口

`plan.md` 保存 Mission、Explore、Contract、Graph 的可读审批视图。`record.json` 保存唯一任务状态、内部验收定义、审批依据、证据、后续专项及交接。日志 / 截图保留引用，公共事实不在每任务重复填写。

批准后，计划只因实质设计变更修改；进度、检查、累计消耗和交接更新写入 record。Guard 对计划字节与 Graph 定义分别计算 SHA-256。任务状态、用量、证据和后续专项进度不改变 Graph 摘要，改任务范围、依赖或验收定义会使原审批过期。

## 结构

| 字段 | 最低内容 |
| --- | --- |
| schema_version / id / title / scope | 固定整数 1；需求 ID、标题、本期目标和边界 |
| tasks | id、title、paths、depends_on、state、repairs、used_minutes、checks；异常任务补 note |
| checks | 全局唯一 id，kind，method，expected；条件项补 trigger / reason |
| approval | decision、reviewer、at、source、plan_sha256、graph_sha256、tasks、paths、operations、limits |
| approval_history（可选） | 按批准顺序保留的历史 APPROVED 完整快照，字段与 approval 一致；省略等同空数组 |
| evidence | 唯一 id、check、baseline、method、actual、result、at、producer、report、subjects |
| overall | 独立 checks、accepted_by、accepted_at、source |
| followups | id、goal、method、reason、required_for_scope=false、resume、status |
| handoff | artifacts、docs、knowledge、resume |

路径使用项目相对路径和 `/`，不允许越界、绝对路径、符号链接或 Windows reparse point。批准路径可用 `.` 表示当前项目；限制应与实际需求相称。Guard 不捕获操作系统级写入，Agent 仍须在每次行动前遵守授权。

### 任务与验收

`state`：PENDING、READY、RUNNING、VERIFYING、REPAIRING、DONE、BLOCKED、NEED_DECISION、STOPPED。依赖必须存在且无环；READY / 活动 / DONE 不能越过未完成依赖。BLOCKED / NEED_DECISION / STOPPED 需要 note 和 handoff.resume。

`checks` 的 kind 为 REQUIRED / CONDITIONAL / OPTIONAL。条件项 trigger 为 TRIGGERED / NOT_TRIGGERED / UNKNOWN；不触发需要 reason，UNKNOWN 不能完成。每项任务和整体验收至少有一个适用必需项；不能靠空数组声称完成。OPTIONAL 可约定 `failure_blocks: true`，纳入批准定义。

任务示例：

```json
{
  "id": "T01", "title": "实现已确认的输入规范化",
  "paths": ["app.py", "tests"], "depends_on": [],
  "state": "PENDING", "repairs": 0, "used_minutes": 0,
  "checks": [{"id": "A01", "kind": "REQUIRED",
    "method": "本地单元测试", "expected": "正常、空白与异常输入符合约定"}]
}
```

### 审批与用量

decision 为 PENDING / APPROVED / CHANGES_REQUESTED / REJECTED。只有真实批准后才填审批人、时间和来源。Agent 从 Guard 输出取得当前 baseline 摘要，关联实际批准的计划、Graph、任务批次、路径和操作。

切换批次覆盖 `approval` 前，将原有实际 APPROVED 记录完整保留到 `approval_history`；保留原审批人、时间、可追溯的真实确认来源、摘要、任务、路径、操作与限制，不改写为当前批次。Guard 只读校验，不自动保存或补造审批，也不会从 DONE、PASS 或上次总结推断历史授权。历史记录缺失时恢复可核验的原批准记录，或请有权限的审批人重新确认；不得由 Agent 自行补批。

DONE 必须由有效的当前审批或历史快照覆盖。历史快照须与当前 plan / Graph 摘要一致，具有完整来源、任务范围、路径、允许操作及有效有限规则；累计修复不得超过该快照上限。旧基线快照仅保留历史，不证明当前授权。历史快照不授权 RUNNING / VERIFYING / REPAIRING 或下一任务；这些仍以当前 `approval` 为准。添加历史快照不改变 Graph 摘要，方案或 Graph 实质变更仍需复核批准与证据。

审批来源的真实性仍须由执行方按实际授权核实；记录中的姓名、时间与 source 字段不构成身份认证或防伪证明。

`limits.max_repairs` 为非负整数或 null，`max_minutes` 为正整数或 null；连续执行至少应有一个已确认的有限限制。null 是待配置，不等于无限。累计 repairs / used_minutes 不随恢复清零；次数约束下一次修复启动，最后一轮允许完成重验。Guard 只核对记录，Agent / 宿主负责实际计数和停止。

### 证据与版本

每条执行证据保存当前 `baseline`（plan_sha256、graph_sha256），以及实际 method、actual、result、at 和 producer。result 为 PASS / FAIL / NOT_VERIFIED / NOT_RUN。实际执行的 PASS / FAIL 必须有非空 subjects 和 report；均为 `{ "path": "项目相对文件", "sha256": "文件摘要" }`。

subjects 绑定本次检查的源码、配置或产物；报告记录实际命令 / 操作、输入、预期、输出、环境与限制。远端运行还需在报告中记录被测实例 / 构建身份，不能用本地文件摘要代替实际部署身份核对。

同一基线、同一检查以追加顺序的最新证据作为当前结果；旧失败和旧版本证据保留。原始报告按尝试另存，避免重验覆盖旧报告。当前对象或报告摘要不符时按 NOT_VERIFIED 处理。方法不同于批准定义时需要复核，不能把本地或 Mock 结果冒充指定真实检查。

摘要只能发现所引用文件发生变化，无法证明记录未被伪造或覆盖所有相关行为。变更影响分析仍须核对调用方、数据、外部依赖和回归范围。

### 本期完成与后续

DONE 表示该任务有可追溯的有效执行授权，当前适用必需检查通过且证据有效。未经授权的 DONE 产生 DONE_AUTHORIZATION 问题并阻止交付。全部任务 DONE 后仍要检查 overall.checks 与实际接收来源。artifacts / docs 为存在的交付文件列表，必要材料不能为空。

knowledge.status 为 PENDING / UPDATED / NO_INCREMENT / DRAFT_READY；UPDATED / DRAFT_READY 要有实际稿件引用，NO_INCREMENT 要有理由。知识库不可写时允许交接更新稿，后续同步不默认阻断本期。

后续专项必须显式 `required_for_scope: false`，记录条件与恢复入口；其 NOT_VERIFIED / FAIL 不自动改变本期完成。已约定本期必需的项目不能直接挪到 followups：先复核范围和验收，更新批准基线，再评估受影响证据。
