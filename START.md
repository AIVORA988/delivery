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

## 安装冲突

检测到本地修改或不兼容文件时，先审查差异，不直接覆盖。安装脚本不修改 AGENTS、全局设置或业务代码，不执行项目命令。卸载或迁移前保留需求记录；完整说明见 [接入与维护](skills/delivery/references/setup.md)。

支持 Agent Skills 的工具可读取 [SKILL.md](skills/delivery/SKILL.md)，自动发现与调用方式按所用工具的支持情况处理；也可让 Agent 直接读取该文件并按规则工作。
