# 删除工作流

删除通过 `termous.sftp.files.delete.*` 工具进行，删除预览、启动、状态和结果需要独立的 `sftp:delete` 权限，取消需要 `sftp:cancel`。已有 `sftp:write` 不包含删除权限；缺少工具时提示在 Termous 中授权，不能改用 Shell 命令绕过。

## 预览与启动

1. 按普通 SFTP 流程确认当前客户端拥有的、已连接的文件会话，使用最新 `file_session_id` 和 `expected_connection_generation`。交互终端的 SSH 会话 ID 不能代替文件会话 ID。
2. 将用户要求转换为明确的绝对 POSIX `paths`，保留原路径语义。路径不展开通配符或环境变量；禁止根目录、重复路径、父子重叠路径，不擅自加入相邻文件。
3. 调用 `termous.sftp.files.delete.preview`，传入 `paths`、`recursive`、会话和连接代次。只有需要删除非空目录时才使用 `recursive=true`。
4. 预览会扫描完整范围，再分页返回明细。按 `next_offset` 读取其余页面，确保各页 `plan_hash` 一致，不能把首页当作完整范围。扫描失败、超限或计划发生变化时停止，不提交删除。
5. 向用户说明主机、顶层路径、递归选项、实际文件／目录／链接数量，以及直接删除无法撤销。符号链接只删除链接本身；父路径经过目录链接时，应让用户明确选择真实路径，不自行扩大范围。
6. 使用同一份参数，将预览返回的 `plan_hash` 作为 `expected_plan_hash`，并使用一个稳定的 `client_request_id` 调用 `termous.sftp.files.delete.start`。默认由 Termous 原生审批；显式开启无需审批时仍执行权限与计划复核，不推断或改变该设置。
7. 记录返回的任务 ID。审批通过或任务创建仅表示可以开始，不能报告已经删除完成。

预览上限为 500 个顶层路径、10,000 个清单节点、256 层和 4 MiB 计划载荷；预览与执行前复核分别限时 30 秒。超限时明确报告并让用户缩小范围，不自动拆分成多次写操作规避限制。

## 查询结果与取消

- 通过 `termous.sftp.files.delete.get` 查询自有任务，直到 `completed`、`failed` 或 `cancelled`。
- 通过 `termous.sftp.files.delete.result` 分页读取终态结果，报告 `deleted`、`failed`、`not_executed`、`uncertain` 数量及必要路径。`partial` 或 `uncertain` 不能省略。
- 调用 `termous.sftp.files.delete.cancel` 只请求停止后续步骤；`cancel_requested=true` 不代表任务已结束或内容已经恢复。继续查询终态后报告实际结果。
- 若当前客户端只有 `sftp:cancel` 而没有 `sftp:delete`，取消后无法调用状态或结果工具；仅报告已请求取消，并说明查看最终结果需要 `sftp:delete`，不推断实际删除范围。
- AI 助手主动停止会取消该 Run/generation 发起的删除，已经完成的内容不会恢复。正常回答结束与主动停止不同，不要依赖结束回答来取消任务。
- 删除途中新增的目录内容不会自动加入范围。遇到目录非空或来源变化，应报告冲突，不追加一轮递归删除。

## 失败与重试边界

- 拒绝、过期或取消的待审批请求不授权执行；不要自动重新申请。
- 立即丢失启动响应时，只能用原请求 ID 和完全相同参数恢复既有请求，不能通过更换 ID 自动重试。
- 计划变化需要重新预览和确认；不允许把新计划放入旧请求 ID。
- 网络中断可能发生在远端已删除、响应尚未返回之间。遇到 `uncertain`，停止自动写入并检查相关路径，不能宣称没有执行。
- 请求幂等和任务历史是有界内存记录，Core 重启后不自动重放。需要重新读取文件状态、预览范围，并取得新的操作授权。
- SFTP 多路径操作不是原子事务，取消和失败都不提供回滚保证。
