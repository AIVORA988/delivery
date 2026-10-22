# 项目接入与维护

脚本只使用 Python 3.10+ 标准库。没有 Python 时可按 Skill 规则和项目既有 Markdown 工作；说明工具检查尚未执行，不宣称 CONFIGURED。不要自动安装全局运行时、改全局 Codex 配置或扩大项目权限。

## 初次接入

先读取目标项目及上级适用规则、已有计划和构建测试说明。确认目标项目存在且可写；工作流源码仓库与业务项目是两个位置。

在仓库根目录调用：

```bash
python skills/delivery/scripts/delivery.py inspect --project ../your-project
python skills/delivery/scripts/delivery.py init --project ../your-project
python skills/delivery/scripts/delivery.py check --project ../your-project
```

替换实际目标；Windows 也支持 `py -3`，macOS / Linux 可用 `python3`。已安装到项目时，脚本入口改为 `.agents/skills/delivery/scripts/delivery.py`。

`inspect` 只扫描最多两层子模块、最多 1000 个目录项的文件名线索，不读取密钥、不跟随链接、不执行命令。`init` 安装 Skill 和 `.delivery/project.json`、`install.json`，保留 AGENTS 及用户配置。`check` 核对配置和安装文件摘要；成功只表示静态 CONFIGURED，`runtime_verified` 仍为 false。

发现现有 Skill 的本地修改、符号链接、Windows reparse point 或不兼容记录时停止，报告冲突，不用 force 覆盖。重复接入相同内容不产生改动；升级仅替换与上次安装摘要一致的文件。源包移除文件时要求先人工审查，不自动删除未知文件。

## 项目基线

Agent 根据真实 README / 构建配置补充 `.delivery/project.json` 的 commands、knowledge_paths、policy 和 baseline。命令记录实际入口与候选 / 已执行状态；不要凭技术栈猜测后直接标记验证通过。

初始修复与时间限制为 null，表示待确认。首次规划中集中提出有限规则，项目已明确的约定优先；每任务三次修复只能作为建议。审批记录写入最终采用值，不替用户预填预算。Guard 校验登记值，不自动计时、不测量费用、不提供操作系统权限隔离。

在授权范围内执行项目必要基线检查，保留命令、环境、退出码、报告和限制。安装依赖可能执行第三方脚本，依项目约定处理；接入本身不授权写生产数据、部署或支付。

## 建立与维护需求记录

```bash
python .agents/skills/delivery/scripts/delivery.py new --project . --id first-slice --title "首个业务闭环"
```

生成 `.delivery/runs/first-slice/plan.md` 和 `record.json`，均为草稿。重复 ID 会拒绝覆盖。前者供审批阅读，后者由 Agent 维护任务、审批、证据及交接。已有需求继续使用同一记录，不因换会话重新初始化。

进入 Loop、重要重验、恢复与交付前，Agent 读取 [record.md](record.md) 并执行：

```bash
python .agents/skills/delivery/scripts/delivery.py guard --project . --id first-slice
```

`record_valid` 只表示记录自洽；`execution_ready` 表示存在满足已登记审批及依赖的活动任务；`delivery_ready` 表示本期记录门槛齐备。三者都不验证业务语义、审批身份或报告真实性。用户无需手工运行此命令或编辑内部字段。

## 退出与冲突

脚本退出码：0 表示检查/操作正常，包括合法草稿尚未就绪；1 表示 Guard 或安装检查发现矛盾；2 表示输入、路径、解析或 I/O 错误。全部输出 JSON，供宿主读取。不要只凭退出码 0 宣称验收通过。

本地安装修改会使 check 返回 CONFLICT；先比较用户变更与上次安装摘要，再决定合并。不要删除用户记录或重置累计消耗。卸载时先备份 `.delivery` 需求记录，只移除确认归该安装管理的文件；脚本不提供递归自动删除。
