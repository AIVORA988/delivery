# 从这里接入 delivery

## 交给 Agent

在业务项目中发送：

```text
工作流仓库：<已克隆或下载的 delivery 目录>
目标项目：<要接入的项目目录>

按仓库中的项目接入规则完成 inspect → init → check。
保留目标项目 AGENTS、已有配置、本地修改与任务记录，仅安装项目内 Skill。
识别真实构建、测试和运行入口，未执行的基线保持 NOT_VERIFIED。
输出已准备内容、检查结果、缺失条件与下一步；先规划首个需求，等审批后实施。
```

Agent 读取 [接入规则](skills/delivery/references/setup.md)，具体项目规则优先。已有接入直接复用，不重复安装或清零累计值。

## 手工安装

需要 Python 3.10+，无 pip 依赖。目标项目目录须已存在；下面命令在 delivery 仓库根目录执行，替换实际项目位置。

```bash
git clone https://github.com/longzhang2026-sudo/delivery.git
cd delivery
python skills/delivery/scripts/delivery.py inspect --project ../your-project
python skills/delivery/scripts/delivery.py init --project ../your-project
python skills/delivery/scripts/delivery.py check --project ../your-project
```

macOS / Linux 可使用 python3，Windows 可使用 py -3。也可下载 GitHub ZIP，无需为了安装引入 Git。检查成功只表示 CONFIGURED，不代表业务项目构建或验收通过。

## 第一个需求

```text
$delivery 为当前需求准备目标与边界、现状依据、方案、任务依赖和验收约定。
本期采用哪些本地 / Mock / 测试检查先说明；真实环境专项需要时另列。
先交我审批，暂不修改业务代码。
```

批准时确认具体方案版本、批次、允许操作和有限修复 / 时间规则。已有会话批准可以直接引用，不重复签模板。Agent 维护内部记录并在批准范围内执行。

## 安装冲突

出现本地修改或不兼容文件时先比较，不覆盖。脚本安装不会改 AGENTS、全局设置、业务代码或运行项目命令。卸载或迁移前保留需求记录；完整说明见 [接入与维护](skills/delivery/references/setup.md)。

其他支持 Agent Skills 的工具可读取 [SKILL.md](skills/delivery/SKILL.md)，自动发现与调用语法按宿主支持情况。项目路径说明参考 [OpenAI 官方文档](https://learn.chatgpt.com/docs/build-skills)。
