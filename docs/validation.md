# 验证方法与已知边界

工作流 V1.0，分发包 1.0.0。工程校验与真实项目效果分别记录。

## 可重复的检查

```bash
python -m unittest discover -s tests -v
python examples/try_delivery.py
```

测试不访问网络、真实账户或业务系统，使用临时项目与虚构批准。

| 检查面 | 代表性边界 |
| --- | --- |
| 接入 | 有限只读扫描、幂等安装、既有规则 / 配置保护、本地修改冲突、路径越界与链接拒绝 |
| 审批与任务 | 草稿不执行、计划 / Graph 变化使审批过期、进度更新不使其过期、批次与路径、依赖环和缺失依赖 |
| 验收与证据 | 无证据不能 DONE、源码 / 报告变化、方法替换、版本绑定、旧证据保留、最新失败覆盖旧 PASS |
| 完成与恢复 | 任务与整体验收分开、空必需项不执行、后续专项独立、累计修复和时间限制、异常恢复入口 |
| 知识与分发 | 待同步稿可交接、必要文档、包元数据、本地链接、分发无敏感凭证和不需要的文档附件 |
| 端到端工具 | 从 inspect / init / check / new 到审批、实际本地检查、交接和源码变更后的证据失效 |

CI 在 Ubuntu / Windows / macOS × Python 3.10 / 3.13 共六种组合执行相同测试，实际结果见 [GitHub Actions](https://github.com/longzhang2026-sudo/delivery/actions/workflows/ci.yml)。宿主不允许创建目录符号链接时，仅该用例会按条件跳过，其他路径拒绝测试仍执行。

## Agent 行为试用

自动化工具测试不等于 Agent 已遵守完整工作流。2026-10-22 已完成一轮独立 Agent 隔离试用：给予小型 Python 项目原始文件和“先接入、调查与规划，交我审批”的请求，不提供预期答案。

实际结果：inspect / init / check 成功，重复接入 written=0；既有 AGENTS、业务源码和 README 字节保持原样。评估者识别出 unittest 虽退出 0 但运行 0 个测试，未把它当作业务验证通过；另做已有行为探测，形成最小修改方案、任务、验收与后续事项，未实施业务改动。最终审批保持 PENDING、限制为 null，Guard 返回 record_valid=true、execution_ready=false、delivery_ready=false、issues=[]。

这只覆盖接入与审批前规划路径，不代表已验证批准后执行或真实业务交付。

进一步应覆盖批准单步后的范围控制、修复无进展退出、审批后重大范围变更、真实环境待验及中断后恢复。没有执行的场景不能写成通过。

## 不作出的保证

- 安装 CONFIGURED、record_valid、execution_ready、delivery_ready 分别限定含义，不等于全部业务正确。
- 校验器不自动执行业务命令、认证审批身份、自动计时 / 计费、判断所有影响面或提供系统权限隔离。
- 证据摘要只检查被引用文件；远端实例身份和实际业务结果仍需对应证据。
- 当前工程检查不证明真实项目提效、跨项目稳定性、生产质量或客户接收；仍需真实试点。

设计原则见 [design.md](design.md)，用户操作见 [usage.md](usage.md)，内部字段见 [record.md](../skills/delivery/references/record.md)。
