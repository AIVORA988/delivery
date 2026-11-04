# 项目接入与维护

脚本只使用 Python 3.10+ 标准库；Git 可用时通过只读查询核对实际修改范围，不添加 Python 运行依赖。缺少可用 Python 3.10+ 时可继续只读调查、Markdown 方案草稿及已获授权的知识整理，说明工具检查未执行，不宣称 CONFIGURED；不能进入依赖 Guard 的自动实施、返修或正式完成判定。保存原记录、缺失条件与恢复入口，运行时可用后重新校验再继续；不伪造过去的工作区起点或证据。不要自动安装全局运行时、改全局 Agent 配置或扩大项目权限。

## 初次接入

先读取目标项目及上级适用规则、已有计划和构建测试说明。确认目标项目存在且可写；工作流源码仓库与业务项目是两个位置。

在仓库根目录调用：

```bash
python skills/delivery/scripts/delivery.py inspect --project ../your-project
python skills/delivery/scripts/delivery.py init --project ../your-project
python skills/delivery/scripts/delivery.py check --project ../your-project
```

替换实际目标；Windows 也支持 `py -3`，macOS / Linux 可用 `python3`。已安装到项目时，脚本入口改为 `.agents/skills/delivery/scripts/delivery.py`。

Windows 调用建议在 Python 后加 `-X utf8`，并按 UTF-8 解码子进程 JSON 输出，避免 Feature 中文名称乱码；只设置当前进程，不修改全局编码。

`inspect` 只扫描最多两层子模块、最多 1000 个目录项的文件名线索，不读取密钥、不跟随链接、不执行命令。`init` 同包安装 delivery、delivery-feature、delivery-run、delivery-feature-run、delivery-bootstrap，维护 `.delivery/project.json`、`install.json`，创建缺失的 `docs/knowledge/README.md` 并补充 knowledge_paths；保留 AGENTS、用户配置及已有知识，不运行 Bootstrap 或业务分析。

从完整仓库或 ZIP 接入，保留全部五个相邻 Skill 目录，仅下载 delivery 子目录不构成完整分发。已安装的完整包也可用上述脚本接入其他项目，不依赖原源码仓库位置。插件安装及 `$skill-name` 发现由宿主支持决定；复制文件不自动执行 Python，官方接入流程或首次调用的 Agent 执行初始化。

`check` 核对配置、五个 Skill 的安装摘要及知识入口；knowledge 返回有界候选发现结果，不读取业务正文。最多调查 1000 个目录项、六层知识子目录，最多返回 20 个候选文件；除识别默认空入口外不读正文。empty 为 true 表示确认空库，false 表示发现候选，null 表示未知；扫描截断、不可读或链接路径不能当作空库。成功只表示静态 CONFIGURED，`runtime_verified` 仍为 false。文档语义和相关索引链接由 Agent 按 [knowledge.md](knowledge.md) 核对。

发现现有 Skill 的本地修改、符号链接、Windows reparse point 或不兼容记录时停止，报告冲突，不用 force 覆盖。重复接入相同内容不产生改动；升级仅替换与上次安装摘要一致的文件。源包移除文件时要求先人工审查，不自动删除未知文件。

旧版单 / 双 Skill 安装可从完整分发重新 init 补齐；原 install.json 的 files 继续保存 delivery 摘要，companions 保存其余四个 Skill 摘要，schema_version 仍为 1。新版 check 会提示旧包缺少入口，init 完整预检后补齐；本地修改冲突则全程不写。知识正文不写入安装回执，不因编辑正文产生安装冲突。升级不改已有 plan / record、审批和证据。

Git 范围核对将当前完整安装回执与实际摘要吻合的精确受管文件列为 maintenance，区分安装维护与业务修改；不整体忽略 .agents / .delivery，不重置原始工作区。未登记文件、本地修改、异常回执、可执行位或不同暂存内容不享受该处理。仅安装维护不使业务接收过期；若 Skill 本身是被检查成果，其 subjects / 交付文件版本仍照常绑定。回执是本地一致性依据，不是安装操作授权或签名证明。

## 项目基线

Agent 根据真实 README / 构建配置补充 `.delivery/project.json` 的 commands、knowledge_paths、policy 和 baseline。knowledge_paths 保留既有项目相对路径并登记默认入口；用于定位，不自动授予写权限。已有文档优先索引引用，正文按 [knowledge.md](knowledge.md) 读取和维护。命令记录实际入口与候选 / 已执行状态；不要凭技术栈猜测后直接标记验证通过。

commands 可用 `{"test": {"command": "python -m unittest discover -s tests -v", "status": "NOT_VERIFIED"}}` 记录已找到但未执行的真实入口，项目已有形式优先。Guard 不解析命令语义或据此执行；通过状态须有实际报告支持。

初始修复与时间限制为 null，表示待确认。首次规划中集中提出有限规则，项目已明确的约定优先；每任务三次修复只能作为建议。审批记录写入最终采用值，不替用户预填预算。Guard 校验登记值，不自动计时、不测量费用、不提供操作系统权限隔离。

在授权范围内执行项目必要基线检查，保留命令、环境、退出码、报告和限制。安装依赖可能执行第三方脚本，依项目约定处理；接入本身不授权写生产数据、部署或支付。

## 建立与维护需求记录

```bash
python .agents/skills/delivery/scripts/delivery.py new --project . --id first-slice --title "首个业务闭环" --scenario simple
```

新需求生成 `.delivery/runs/first-slice/plan.md` 和 `record.json`，均为未审批草稿。--scenario 可选 simple / standard / feature，默认 standard；分别限制整个需求最多 3 / 15，或每 Feature 最多 30 个任务。前者供审批阅读，后者由 Agent 维护任务、审批、证据及交接。重复 ID 拒绝覆盖，跨会话 / 分批沿用原记录。简单任务也先规划审批，历史无 scenario 记录保持原语义而不静默迁移。

可捕获的 record 写入失败仅清理本次创建且未被改动、没有其他资料的 plan，允许重试；不确定归属时保留文件。进程中断留下单文件时，new 明确报告 Incomplete run；先备份和审查已有文件，再恢复未批准草稿，不覆盖人工方案。若原工作区起点已经丢失，重新调查现存修改并确认当前起点，不补造过去的 snapshot、审批或执行记录。

在实施前建立 run：new 会读取原始 Git HEAD 和已有改动指纹到 workspace，Guard 据此核对后续实际范围；不自动暂存或提交。Git 不可用或旧记录无起点时明确返回 change_scope=NOT_CONFIGURED，由 Agent 人工核对，不补造历史起点。已有 Git 起点但查询失败时不降级放行，详见 [记录契约](record.md)。

进入 Loop、重要重验、恢复与交付前，Agent 读取 [record.md](record.md) 并执行：

```bash
python .agents/skills/delivery/scripts/delivery.py guard --project . --id first-slice
python .agents/skills/delivery/scripts/delivery.py guard --project . --id first-slice --task T01
```

Feature 型 run 按本轮指令确定一个或多个模块，已明确指定时不重复询问；未指定或有歧义时收集选择，再逐项检查任务，例如 `guard --project . --id store --features F01 F02 --task T01`。模块须获得完整授权，授权后本轮可只执行指定任务。不指定 Feature 时仅查询状态，不能启动 Feature 子任务。取消或未回答不执行；宿主不支持多选弹框时使用编号列表。Python 不显示 GUI，详见 [记录契约](record.md)。

不带 --task 用于审批材料和整体验收；带 --task 用于具体任务开始 / 恢复前校验。`record_valid` 只表示记录自洽；`execution_ready` 在指定任务时仅表示该任务就绪，否则表示存在可执行任务；`batch_complete` 表示当前批准批次完成；`delivery_ready` 表示本期整体记录门槛齐备。它们都不验证业务语义、审批身份或报告真实性。用户无需手工运行命令或编辑内部字段。

## 退出与冲突

脚本退出码：0 表示检查/操作正常，包括不指定任务或选择时合法草稿尚未就绪；1 表示检查发现矛盾、--task 所查任务未就绪或 --features 选择未获准；2 表示输入、路径、解析或 I/O 错误。全部输出 JSON，供宿主读取。不要只凭退出码 0 宣称验收通过。

本地安装修改会使 check 返回 CONFLICT；先比较用户变更与上次安装摘要，再决定合并。不要删除用户记录或重置累计消耗。卸载时先备份 `.delivery` 需求记录，只移除确认归该安装管理的 Skill 文件，保留项目知识正文；脚本不提供递归自动删除。
