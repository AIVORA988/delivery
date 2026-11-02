# delivery 安装与维护

使用入口见 README 的 [安装 → 提需求 → 审批执行](README.md#快速开始) 三段 prompt。本页说明手工安装与冲突处理。

## 手工安装

需要 Python 3.10+，仅使用标准库，无需通过 pip 安装依赖。目标项目目录须已存在；以下命令在 delivery 仓库根目录执行，项目路径替换为实际位置。

```bash
git clone https://github.com/AIVORA988/delivery.git
cd delivery
python skills/delivery/scripts/delivery.py inspect --project ../your-project
python skills/delivery/scripts/delivery.py init --project ../your-project
python skills/delivery/scripts/delivery.py check --project ../your-project
```

macOS / Linux 可使用 python3，Windows 可使用 py -3。也可下载 GitHub ZIP，无需安装 Git。检查成功只表示 CONFIGURED，不代表业务项目构建或验收通过。

使用完整仓库或 ZIP，保留 `skills/delivery` 与 `skills/delivery-bootstrap`。init 一次安装两个入口并创建 `docs/knowledge/README.md`，保留已有知识与配置，不运行深度分析。复制 Skill 文件或安装插件本身不保证 Python 已执行；首次调用时由 Agent 核对并补齐项目接入。旧安装从完整分发重新 init 即可升级，原审批和需求记录保持原样。

## 两个使用入口

- `$delivery`：日常研发，按需读取、核对和更新知识；新项目空库正常跳过。
- `$delivery-bootstrap`：用户明确要求时集中分析存量项目，可指定模块并按索引恢复；不修改业务代码。

知识目录与读写约定见 [知识规则](skills/delivery/references/knowledge.md)，用户示例见 [使用手册](docs/usage.md)。调用语法和自动发现以宿主支持为准。

## 安装冲突

检测到本地修改或不兼容文件时，先审查差异，不直接覆盖。安装脚本不修改 AGENTS、全局设置或业务代码，不执行项目命令。卸载或迁移前保留需求记录；完整说明见 [接入与维护](skills/delivery/references/setup.md)。

支持 Agent Skills 的工具可读取 [SKILL.md](skills/delivery/SKILL.md)，自动发现与调用方式按所用工具的支持情况处理；也可让 Agent 直接读取该文件并按规则工作。
