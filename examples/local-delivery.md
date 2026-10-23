# 本地交付示例

```bash
python examples/try_delivery.py
```

演示在临时目录中创建小型 Python 命令行程序，依次运行公开 CLI 的 inspect、init、check、new 和 guard。示例中的审批与接收均标为 SYNTHETIC，属于测试夹具；其中的三次修复 / 十分钟仅用于隔离演示，不是项目默认值。

## 需求与任务

本期：接收输入、去除首尾空白、统一小写；检查空白输入与命令行调用，交付运行说明。正式托管联调由 F01 表示，已在夹具方案中明确不属于当前范围。

| 检查 | 实际动作 |
| --- | --- |
| C1 任务验收 | 启动本地 Python 进程，断言混合大小写和空白输入的结果 |
| C2 整体场景 | 启动命令行程序，核对输入和 stdout，保存实际报告 |
| 后续 F01 | 保留 NOT_VERIFIED 和接手入口，不访问远端服务 |

## 预期输出

```json
{
  "installation": "CONFIGURED",
  "draft_execution_ready": false,
  "approved_execution_ready": true,
  "current_scope_delivery_ready": true,
  "external_followups_pending": ["F01"],
  "after_source_change_delivery_ready": false,
  "actual_local_processes": 2
}
```

源文件与原始报告均计算摘要并绑定当前计划 / Graph。演示最后有意移除大小写转换，旧证据随即不能支持当前完成。临时目录自动清理，不修改业务项目、访问网络或运行后台服务。

这是端到端工具演示，不能证明真实客户项目、人工审批身份、运行环境或提效幅度。如何在真实项目使用见 [使用手册](../docs/usage.md)。
