# delivery 安装与维护

使用入口见 README 的 [安装 → 提需求 → 审批执行](README.md#快速开始) 三段 prompt。本页说明手工安装与冲突处理。

## 手工安装

需要 Python 3.10+，仅使用标准库，无需通过 pip 安装依赖。先获取源码；已克隆仓库的用户直接进入现有仓库根目录，跳过以下两条命令。

```bash
git clone https://github.com/AIVORA988/delivery.git
cd delivery
```

也可下载 GitHub ZIP，无需安装 Git；解压后进入含 skills 目录的源码根目录，直接执行下面的接入段，不再 clone 或 cd delivery。

在源码根目录接入目标项目。目标项目目录须已存在，与源码目录分别定位；将以下路径替换为实际位置，含空格时保留引号。示例目标项目与 delivery 源码目录是同级目录。

```bash
python -X utf8 skills/delivery/scripts/delivery.py inspect --project "../your project"
python -X utf8 skills/delivery/scripts/delivery.py init --project "../your project"
python -X utf8 skills/delivery/scripts/delivery.py check --project "../your project"
```

macOS / Linux 可使用 python3，Windows 可使用 py -3。检查成功只表示 CONFIGURED，不代表业务项目构建或验收通过。缺少 Python 3.10+ 时，可继续调查、方案草稿和获授权的知识整理；依赖 Guard 的自动实施、返修及正式完成判定等待运行时恢复，不自动安装全局运行时。

使用完整仓库或 ZIP，保留 skills 下全部五个相邻 Skill 目录。init 一次安装四个研发入口和 Bootstrap，并创建 `docs/knowledge/README.md`，保留已有知识与配置，不运行深度分析。复制 Skill 文件或安装插件本身不保证 Python 已执行；首次调用时由 Agent 核对并补齐项目接入。旧安装从完整分发重新 init 即可升级，原审批和需求记录保持原样。

## 使用入口

- `$delivery`：普通 / 存量需求规划，自动判断简短或完整方案，等待审批；任务上限 3 / 15。
- `$delivery-feature`：全新中大型项目规划，提供一份详细设计即可，支持直接上传附件，不要求独立架构文档或固定目录，每 Feature 最多 30 个子任务。
- `$delivery-run`：执行或恢复已批准的普通方案，按任务依赖 Loop。
- `$delivery-feature-run`：确认本轮单个或多个 Feature，按依赖逐模块执行各自 Task Loop。
- `$delivery-bootstrap`：用户明确要求时集中分析存量项目，可指定模块并按索引恢复；不修改业务代码。

批准且授权开始后由 Agent 使用对应执行入口；执行命令本身不构成审批，Feature 选择不扩大原授权。Feature 按完整模块授权，授权后本轮可只执行指定子任务；已明确指定模块时不重复选择，未指定或有歧义时再询问。旧单 / 双 Skill 安装重新 init 补齐，新 check 要求完整包，但升级不改原需求与审批。知识目录见 [知识规则](skills/delivery/references/knowledge.md)，完整示例见 [使用手册](docs/usage.md)。入口发现和原生多选控件以宿主支持为准，无多选弹框时使用编号列表，不安装 GUI。

## 安装冲突

检测到本地修改或不兼容文件时，先审查差异，不直接覆盖。安装脚本不修改 AGENTS、全局设置或业务代码，不执行项目命令。卸载或迁移前保留需求记录；完整说明见 [接入与维护](skills/delivery/references/setup.md)。

支持 Agent Skills 的工具可读取 [SKILL.md](skills/delivery/SKILL.md)，自动发现与调用方式按所用工具的支持情况处理；也可让 Agent 直接读取该文件并按规则工作。
