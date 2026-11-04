# Run Record v1：内部记录契约

仅在维护 `record.json`、运行 Guard 或诊断恢复时阅读。用户看到业务目标、审批材料与接收结果；以下字段由 Agent 维护。初始结构见 [run.json](../assets/run.json)。

## 一份需求，一组共享记录

`plan.md` 保存 Mission、Explore、Contract、Graph 的可读审批视图。`record.json` 保存唯一任务状态、内部验收定义、审批依据、证据、后续专项及交接。日志 / 截图保留引用，公共事实不在每任务重复填写。

批准后，计划只因实质设计变更修改；进度、检查、累计消耗和交接更新写入 record。Guard 对计划字节与 Graph 定义分别计算 SHA-256。任务状态、用量、证据和后续专项进度不改变 Graph 摘要，改任务范围、依赖或验收定义会使原审批过期。

所有新开发需求使用本记录，简单任务精简方案深度，不省略审批或必要验证。规划与执行入口复用原记录；纯只读排查不授权实施。

## Git 实际修改范围

`new` 在 Git 可用且项目位于仓库内时自动保存 `workspace`，在创建本需求文件前读取，不暂存、不提交、不修改业务文件。结构为 `{ "head": "起始提交 SHA 或 null", "dirty": { "项目相对路径": { "worktree": "file:SHA256 / link:SHA256 / null", "index": "mode:blob-id / null" } } }`；null HEAD 表示尚无首次提交。工作区指纹覆盖文件内容及可执行位，链接只读取目标文本；它与 Evidence 的文件内容摘要用途不同。非空 workspace 纳入原 Graph 摘要，改写起点使原审批失效，不允许事后用当前状态补造起点。

有效审批下，Guard 通过只读 Git 查询与实际文件指纹核对起点以来的累计差异，覆盖暂存、未暂存、未跟踪、删除、重命名及执行期间已提交的修改。起点已有且未变的改动不归入本次；其内容、暂存状态或存在性变化仍须复核。授权范围为当前批准任务的 paths，加同基线有效历史授权覆盖的 DONE 任务路径，以及已绑定内容的 contracts；仅写在未授权任务或宽泛 approval.paths 中的路径不构成任务执行范围。本需求 `.delivery/runs/<id>/` 是记录与报告目录，不作为业务修改核对对象；其他目录不自动豁免，必要文档与知识路径须纳入任务。

输出 `change_scope`：PASS 表示此次范围核对通过；FAIL 的 outside 列出越界路径；NOT_VERIFIED 表示原 Git 工作区不可读、冲突或不支持的变更，后二者均阻止执行就绪和最终交付。WAITING_APPROVAL 表示尚无有效审批；其他记录错误应同时查看 issues。旧记录或非 Git 环境无原始 workspace 时输出 NOT_CONFIGURED，保留原审批与任务语义，Agent 必须人工核对实际差异，不能声称自动范围检查通过。Guard 不自动迁移旧记录。

此核对限定项目目录与检查时的累计差异，不能归因多个操作者、检测已撤销的瞬时写入、Git 忽略的未跟踪产物或项目外操作；变更子模块内容须另行人工处理。它不是实时拦截、逐操作授权或权限沙箱。Git 配置和工作区须可信，报告真实性与业务影响仍由 Agent 和接收方核实。

## 结构

| 字段 | 最低内容 |
| --- | --- |
| schema_version / id / title / scope | 固定整数 1；需求 ID、标题、本期目标和边界 |
| scenario | 新需求为 simple / standard / feature；整个 Graph 分别≤3 / ≤15，或每 Feature≤30 个任务 |
| features（Feature 场景） | id、title、depends_on、checks；每 Feature 至少一个任务，模块完成状态由任务及证据推导 |
| contracts | 参与审批的稳定设计 / 接口文件的项目相对路径数组；Feature 场景须非空，普通场景可选 |
| workspace（可选） | new 读取的原始 Git HEAD 与已有改动指纹；缺失 / null 表示没有自动范围核对起点 |
| tasks | id、title、paths、depends_on、state、repairs、used_minutes、checks；异常任务补 note |
| checks | 全局唯一 id，kind，method，expected；条件项补 trigger / reason |
| approval | decision、reviewer、at、source、plan_sha256、graph_sha256、tasks、paths、operations、limits |
| approval_history（可选） | 按批准顺序保留的历史 APPROVED 完整快照，字段与 approval 一致；省略等同空数组 |
| evidence | 唯一 id、check、baseline、method、actual、result、at、producer、report、subjects |
| overall | 独立 checks、accepted_by、accepted_at、source、accepted_sha256 |
| followups | id、goal、method、reason、required_for_scope=false、resume、status |
| handoff | artifacts、docs、knowledge、resume |

路径使用项目相对路径和 `/`，不允许越界、绝对路径、符号链接或 Windows reparse point。批准路径可用 `.` 表示当前项目；限制应与实际需求相称。Guard 不捕获操作系统级写入，Agent 仍须在每次行动前遵守授权。

### 场景与 Feature 定义

new 默认创建 standard，可传 --scenario simple / feature。simple 为无高风险局部需求，standard 为存量复杂或高风险需求；风险、设计深度和任务拆分由 Agent 判断，Guard 校验声明的结构与数量。上限包含整个原 Graph 的 DONE 和未批准任务，不能换批次绕过。超过上限重新划分合理需求或 Feature，不隐藏独立交付任务。

Feature 场景每项 task 必须有唯一 feature 字段，指向定义的 Feature。Feature ID 唯一、依赖存在且无环；任务跨 Feature 的提供方须处于该 Feature 的依赖链中。Feature 的 checks 与任务 / overall checks 共用全局唯一检查 ID 和同一证据结构。每个 Feature 至少有一个适用必需检查，全部子任务 DONE 且证据有效、模块 checks 通过才 complete；依赖 Feature 未 complete 时不能推进当前 Feature 的任务。

```json
{
  "scenario": "feature",
  "contracts": [".delivery/runs/store/inputs/商城详细设计.md"],
  "features": [
    {"id": "F01", "title": "商品中心", "depends_on": [],
     "checks": [{"id": "FC01", "kind": "REQUIRED", "method": "本地模块集成测试", "expected": "商品链路符合约定"}]}
  ]
}
```

这是字段片段，须配合真实任务和完整 run 使用。scenario、Feature 定义、任务归属和模块验收均纳入 Graph 摘要，进度仍不改变基线。无 scenario 的旧记录保持原摘要与数量规则，不强制迁移；统一缺陷校验也适用于旧记录，不保留越限或不一致记录的错误放行。新记录始终声明场景，不得删字段规避限制。若主动转换旧运行，须按实质基线变更复核批准和证据，不能偷偷重写历史。

### 外部设计与接口契约

公共约定可直接写 plan，不强制另建契约文件。引用现有文件作为审批依据时登记 `contracts`，例如 `["docs/api/orders.md"]`；路径必须唯一、存在且是文件，不能引用本需求的可变 record.json。Guard 读取实际文件内容计算摘要并纳入 Graph，不能以手填哈希声明其未变更。契约路径或内容改变，当前 / 历史审批和旧证据均不能证明新基线成立。

数组顺序不影响摘要；不登记契约且无 scenario 的历史记录及空 contracts 保持旧摘要不变。Feature 执行必须登记实际详细设计文件或附件的项目内稳定副本，单个文件即可，不要求独立架构文档或固定目录，空 contracts 不放行；上述路径仅为示例，文件是否充分仍由 Agent 和审批人按内容判断。任务进度和普通知识更新仍不改变 Graph。只登记稳定规范输入，不登记待生成产物或持续更新的说明，执行对象由 evidence.subjects 绑定。Guard 不自动发现传递引用或判断语义兼容，登记范围与变更影响仍由 Agent 分析。

### 任务与验收

`state`：PENDING、READY、RUNNING、VERIFYING、REPAIRING、DONE、BLOCKED、NEED_DECISION、STOPPED。依赖必须存在且无环；READY / 活动 / DONE 不能越过未完成依赖。BLOCKED / NEED_DECISION / STOPPED 需要 note 和 handoff.resume。

`checks` 的 kind 为 REQUIRED / CONDITIONAL / OPTIONAL。条件项 trigger 为 TRIGGERED / NOT_TRIGGERED / UNKNOWN；不触发需要 reason，UNKNOWN 不能完成。每项任务和整体验收至少有一个适用必需项；不能靠空数组声称完成。OPTIONAL 可约定 `failure_blocks: true`，纳入批准定义。

仅有 NOT_TRIGGERED / UNKNOWN 条件项而没有适用必需项时，不授权开始执行；有其他适用必需项的 UNKNOWN 仍阻止最终完成。trigger / reason 同属 Graph 定义，改变适用性须复核原审批，不能只刷新摘要绕过确认。定义数组顺序参与原摘要；调整独立任务的实际执行顺序无需重排数组。外部 contracts 数组仍按路径排序，保留原行为。

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

DONE 必须由有效的当前审批或历史快照覆盖。历史快照须与当前 plan / Graph 摘要一致，具有完整来源、任务范围、路径、允许操作及有效有限规则；该任务累计修复和时间均不得超过对应快照上限。当前批次收紧限制不追溯否定原审批内合法完成的 DONE；重新进入活动状态仍按当前审批和累计用量校验。旧基线快照仅保留历史，不证明当前授权。历史快照不授权 RUNNING / VERIFYING / REPAIRING 或下一任务；这些仍以当前 `approval` 为准。添加历史快照不改变 Graph 摘要，方案或 Graph 实质变更仍需复核批准与证据。

审批来源的真实性仍须由执行方按实际授权核实；记录中的姓名、时间与 source 字段不构成身份认证或防伪证明。

`limits.max_repairs` 为非负整数或 null，`max_minutes` 为正整数或 null；连续执行至少应有一个已确认的有限限制。null 是待配置，不等于无限。累计 repairs / used_minutes 不随恢复清零；次数约束下一次修复启动，最后一轮允许完成重验。Guard 只核对记录，Agent / 宿主负责实际计数和停止。

限额由每个任务继承，非批次总预算；used_minutes 是该任务累计实际执行分钟，不是自动采集的墙钟时间。进入 REPAIRING 前先增加 repairs，0 次不能处于 REPAIRING；达到最大次数的已登记一轮可在剩余时间内重验，下一轮不得启动。used_minutes 达到上限时不再放行执行；若检查已在限额内完成，恰好到限的 DONE 可验收，超过上限的 DONE 不能凭 PASS 交付。operations 校验记录形状和非空范围，不自动将自然语言操作映射到命令权限；每次实际操作仍由 Agent / 宿主核对。

### 证据与版本

每条执行证据保存当前 `baseline`（plan_sha256、graph_sha256），以及实际 method、actual、result、at 和 producer。result 为 PASS / FAIL / NOT_VERIFIED / NOT_RUN。实际执行的 PASS / FAIL 必须有非空 subjects 和 report；均为 `{ "path": "项目相对文件", "sha256": "文件摘要" }`。

subjects 绑定本次检查的源码、配置或产物；报告记录实际命令 / 操作、输入、预期、输出、环境与限制。远端运行还需在报告中记录被测实例 / 构建身份，不能用本地文件摘要代替实际部署身份核对。

同一基线、同一检查以追加顺序的最新证据作为当前结果；旧失败和旧版本证据保留。原始报告按尝试另存，避免重验覆盖旧报告。当前对象或报告摘要不符时按 NOT_VERIFIED 处理。方法不同于批准定义时需要复核，不能把本地或 Mock 结果冒充指定真实检查。

约定 failure_blocks 的检查一旦在当前基线失败，源码 / 报告变化或追加 NOT_RUN / NOT_VERIFIED 不解除阻塞；须追加当前对象与报告均有效的 PASS。普通 OPTIONAL 未执行仍不自动阻塞。此规则不改变检查定义或原 Graph 摘要。

摘要只能发现所引用文件发生变化，无法证明记录未被伪造或覆盖所有相关行为。变更影响分析仍须核对调用方、数据、外部依赖和回归范围。

### 本期完成与后续

`guard --project <项目> --id <原需求ID> --task T02` 只读检查指定任务的执行前提。`next_tasks` 仍列出所有候选，`selected_task` 标明所查任务，`execution_ready` 仅当该任务在候选中且无问题时为 true；未授权、依赖未满足、到限、PENDING、DONE 或阻塞任务均不能放行。退出 0 表示该任务可执行，1 表示未就绪或记录有问题，未知 ID 为输入错误（退出 2）。正常但未获授权的任务无需被标记为记录错误。

无 --task 时保持原语义：execution_ready 表示至少有一项可执行，合法草稿可退出 0。不能将全局结果用于任意 Task ID，也不能将退出 0 等同于审批通过。

Feature 型计划不传 --features 时只做状态审查，next_tasks 为空、execution_ready=false，即便 --task 指向已批准任务也不能借此绕过选择。开发者确认单选或多选后，执行方传 `guard --project <项目> --id <原需求ID> --features F01 F02`；每任务再加 `--task T01`。所选 ID 唯一且存在，必须由有效当前授权覆盖未完成子任务；未完成前置须同选或已 complete，不自动扩大选择。选择不改审批、Graph 或任何文件。

输出 selected_features、按依赖排列的 feature_order、selection_ready、selection_complete 和 features 进度。next_tasks 仅来自排序后首个未完成 Feature，避免多选变成隐式并行；具体 --task 仍须处于候选中。模块验收待执行时可能 selection_ready=true 而 execution_ready=false，因为没有新的子任务可启动，执行方应按获批方法补模块检查。全选范围已完成时不重跑任务，selection_complete=true 仍不代表系统完成。

Git 起点可用且具体任务可执行时，输出 scope_checkpoint，包含 run、baseline、features、task、workspace。执行方在操作前把完整 Guard JSON 临时保存在当前 run，操作后用原选择 / 任务加 `--changes-since <项目相对JSON路径>`；程序读取其中的 scope_checkpoint，核对运行、基线、选择、任务和原 HEAD，再比较暂存 / 工作区指纹。invocation_scope 为 PASS / FAIL / NOT_VERIFIED；未传入为 NOT_CHECKED，不等于本轮范围通过。范围限于该任务 paths，累计 change_scope 的批准批次与历史 DONE 语义不变。无效 / 过期检查点产生 SCOPE_CHECKPOINT，越界产生 INVOCATION_SCOPE，均阻止执行和交付；缺文件或缺检查点为输入错误。它是临时只读校验输入，不写 record、不改变 Graph，也不自动执行或认证检查点来源；丢失后先人工核实，不以当前状态补造过去。具体操作与恢复次序见 [execution.md](execution.md)。

features 返回 id、title、tasks、done（已标记 DONE 数）、tasks_done、complete、authorized 和 blocked_by；任务数量不代表证据已通过，完整判定读取 complete 和 issues。取消选择不调用执行；未知 / 重复 / 空选择是输入错误（退出 2），--features 范围未获批或依赖不闭合为未就绪（退出 1）。合法选择可退出 0，实际任务是否可启动仍读取 execution_ready；带 --task 时该任务未就绪退出 1。

`batch_complete` 是派生结果：当前审批及有限规则有效、批准任务非空、该批次全部 DONE 且必需证据通过、无记录问题；不要求其余模块或 overall 已完成。`remaining_tasks` 列出原 Graph 中尚未 DONE 的任务。分批切换沿用同一 run 和基线，历史快照规则不变；本批次完成时保存 handoff.resume，最终集成与整体验收仍决定 delivery_ready。

DONE 表示该任务有可追溯的有效执行授权，当前适用必需检查通过且证据有效。未经授权的 DONE 产生 DONE_AUTHORIZATION 问题并阻止交付。Feature 场景还须全部模块 complete；全部任务 DONE 后仍要检查 overall.checks 与实际接收来源。artifacts / docs 为存在的交付文件列表，必要材料不能为空。

Guard 输出的 `acceptance_sha256` 是接收版本摘要，不是批准或接收证明。仅在全部任务合法 DONE、任务 / Feature / 整体必需检查通过、审批及限额有效、无校验错误、必要交付文件和知识交接就绪时生成；实际接收本身在摘要生成后记录，其他前提未满足时为 null。它绑定当前 plan / Graph 基线、任务 / Feature / overall 的适用必需检查及 failure_blocks 检查的最新证据，以及 handoff.artifacts / docs 中各文件的路径和实际内容。交付文件应为稳定产物或说明；handoff.artifacts / docs 及当前有效证据的 subjects / report 引用本 run 可变 record.json 时产生 SELF_REFERENCE，摘要为 null，不能通过改大小写或同文件别名规避。普通稳定 JSON / 报告仍允许。

有原 Git 起点时，接收摘要还绑定起点以来实际成果差异及最终内容，包括新增 / 修改 / 删除 / 重命名；保持未变的原有脏文件不纳入，单纯暂存 / 取消暂存不改变成果摘要，本 run 记录目录仍不作累计业务修改核对。未被 subjects 引用的可见 Git 成果变化也使旧接收失效，但不自动证明检查覆盖充分；须真实重验受影响项及完成约定接收，不能自动更新 accepted_sha256。原 Git 起点不可读时不生成摘要，不降级成人工通过。

先完成必要检查和交付材料，取得非空 acceptance_sha256，按该版本进行约定接收。仅在真实接收来源确实覆盖当前基线与成果后，将该摘要写入 `overall.accepted_sha256`，同时记录实际 accepted_by / accepted_at / source，再运行 Guard 核对。Guard 不回填字段；不得随重验自动覆盖摘要来沿用旧接收。基线、受约束证据或交付文件变化后摘要不匹配，delivery_ready=false；任务执行授权、batch_complete 和有效历史 DONE 仍按原规则判定。

该字段不加入 Graph 摘要，不改审批或证据基线。批次切换、状态 / 用量、恢复入口、后续专项状态和仅修改知识引用不影响接收摘要；Git 范围内知识正文实际变化照常纳入成果差异。旧记录仍可读取、恢复任务和保留有效审批；有 Git 起点的旧接收可能因增强成果绑定而失效，不能自动换算摘要，须核实实际接收覆盖当前成果，无法证明时重新接收。无原起点仍保留人工范围核对，不补造历史。摘要不提供身份认证、防篡改、业务覆盖分析或 Git 忽略文件 / 项目外操作检测。

knowledge.status 为 PENDING / UPDATED / NO_INCREMENT / DRAFT_READY；UPDATED / DRAFT_READY 要有实际稿件引用，NO_INCREMENT 要有理由。知识库不可写时允许交接更新稿，后续同步不默认阻断本期。

目录及读写约定见 [knowledge.md](knowledge.md)。初始化空索引不算业务知识增量；记录引用不能证明 Agent 已正确理解正文。知识进度写 record，不向已批准 plan 追加；文档被 subjects 引用时仍受原有摘要失效规则约束，不因知识维护豁免。

后续专项必须显式 `required_for_scope: false`，记录条件与恢复入口；其 NOT_VERIFIED / FAIL 不自动改变本期完成。已约定本期必需的项目不能直接挪到 followups：先复核范围和验收，更新批准基线，再评估受影响证据。
