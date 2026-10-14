# 固定版本运行与结束

- `termous.desktop_workflows.runs.start` 指定明确 version；session_id＋connection_generation 与 profile_id 二选一。默认不抢占，takeover=true 必须符合用户授权目标和范围。
- 开始返回 run_id，Core 继续准备并发起全局审批。waiting_user_action 由可信界面处理证书、主机密钥或缺失凭据；不要自行信任或代填密码。
- 运行有自己的控制授权，不能把已有直接输入授权借给脚本；从直接控制切换为脚本运行前，先归还自己取得的直接控制。最长 30 分钟，15 分钟无有效运行截图／输入释放。报告轮询和模板预览不续授权。
- 内置 Agent 启动工具会持续等待准备和人工确认完成；用户尚未决定时，不重复启动，也不结束本轮。后续优先用 `wait_workflow_run`：普通执行一次等待最多 60 秒，人工确认期间持续等待 Core 的批准、拒绝或到期结果，不需要模型反复查询。外部客户端使用 `termous.desktop_workflows.runs.get` 的 after_revision 与 wait_ms（最多 10000）等待变化。普通等待超时只是当前快照。**必须等待终态后再结束本轮 Agent Run 或关闭 MCP 会话**；调用方结束会取消运行，不能承诺它脱离本轮继续后台执行。
- 本文档读过后直接使用运行、查询或等待工具。读取文档、refresh 重读及重新发现同一工具都不等于继续运行。新一轮用户说“继续”时，先查询既有 run_id 的实际终态；已取消或中断的运行不能直接续跑，也不能恢复旧输入授权。
- `termous.desktop_workflows.runs.list` 分页查摘要。`termous.desktop_workflows.runs.control` 只能管理自己的运行，action 为 pause、resume、step 或 cancel；人工界面可随时干预，不能自动抢回控制。
- 页面关闭不取消运行。自己创建的连接默认在仍独占时关闭；keep_connection=true 保留。已有连接始终保留。
- 先读报告，再按需用 `termous.desktop_workflows.assets.get` 读取证据。提供 run_id，或 script_id＋version 证明图片关系；本调用方刚确认的待保存模板可直接读取。
- 报告 `steps[].asset_id` 是本次运行的截图证据，每次失败可以不同；不是步骤引用的模板。`desktop_workflow_image_missing` 表示画面未匹配或出现／消失条件等待超时，不表示模板丢失。先查看失败证据，再读取报告指定版本核对步骤顺序和模板；不要凭此错误推断版本绑定异常或重建全部模板。
- 动作 accepted 只表示协议接受；没有断言的 completed 是“执行完成”。uncertain、清理失败或已派发后断线不能自动重试，重新观察并向用户说明已知范围。
- 区分报告的 error_code、cleanup_error 和各步骤状态。仅 cleanup_error 非空不能说新的文本或点击已经派发；可以只读核查并正常说明哪些步骤已接受、哪里中断以及清理未确认。输入或步骤本身 uncertain 时停止后续自动操作。desktop_control_stale 不能证明是谁收回控制，不能根据猜测重新接管并从头重跑。
