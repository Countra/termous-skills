---
name: termous-desktop-workflows
description: 使用 Termous MCP 创建、编辑和运行 RDP／VNC 可视化桌面脚本，提取并确认图像模板，读取回归测试报告。适用于可重复的桌面流程、图像定位和 UI 回归；即时鼠标键盘操作使用 termous-remote-desktop，本机应用发现使用 termous-desktop。
---

# Termous 桌面脚本

使用已配置的 `termous.desktop_workflows.*` 工具。保持 Termous 运行。缺少工具意味着权限或版本不支持，不能绕过授权调用协议、查找凭据或执行其他命令。

## 创建与编辑

1. 先调用 `termous.desktop_workflows.schema` 读取当前步骤合同和限制，再用 `termous.desktop_workflows.list` 搜索现有脚本。脚本库为本机共享库，编辑前确认用户指的是哪一个脚本。
2. `termous.desktop_workflows.get` 返回指定版本正文；`termous.desktop_workflows.versions` 分页返回作者和版本摘要。
3. `termous.desktop_workflows.create` 可创建空草稿或完整定义。`termous.desktop_workflows.update` 必须携带 `expected_revision`，使用完整 `definition` 或稳定步骤 ID 的 `changes`，两种方式互斥。批量编辑最多 64 项，失败不部分保存；移动的 index 指移除原项后的索引。
4. `termous.desktop_workflows.duplicate` 指定源版本和新名称；`termous.desktop_workflows.restore` 指定历史版本与当前预期修订号，产生新版本。修改者不会覆盖原创建者。
5. `termous.desktop_workflows.validate` 检查完整定义。参数类型为 string、number、boolean；敏感文本只在启动时提供，不写入默认值、步骤文字或说明。
6. `termous.desktop_workflows.delete` 需要对应权限，并遵循 Termous 当前审批策略。删除保留已有报告；冲突时读取新版本，不自动覆盖。

编辑与确认模板免人工审批，不等于授权执行远端输入。每个变更使用新的 `client_request_id`；传输不确定时重复同一标识和同一参数，不能换标识重放。

## 获取与确认图像模板

1. 通过现有远程桌面工具选择精确会话／保存配置，建立自己的观察附着并等待 ready。不得自行猜测会话 ID、代次或资产 ID。
2. `termous.desktop_workflows.captures.create` 使用 attachment_id，获得固定原帧的 snapshot_id 和预览。默认图片最多 1600×1000；其元数据说明原始区域及缩放关系。
3. 观察实际图片，再调用 `termous.desktop_workflows.templates.preview`，提交 snapshot_id、region（x、y、width、height）。默认 image 坐标基于返回预览；desktop 坐标须明确指定。
4. 查看图片 1 的原像素模板和图片 2 的选区上下文。确认没有截错、截断目标或包含不稳定内容；需要调整时创建新预览，不能假装已查看。可用 `termous.desktop_workflows.templates.get` 重新查看。
5. 推荐调用 `termous.desktop_workflows.templates.match`：preview_id 和 target.asset_id 二选一。它在当前桌面只读搜索，返回候选框和分数，不点击。多个候选不代表唯一可点击，缩小区域或改选模板。
6. 观察正确后显式调用 `termous.desktop_workflows.templates.confirm` 保存同一 preview_id，返回 asset_id。当前目标不在画面上也可以保存有效模板；不要把匹配唯一作为保存的强制条件。
7. `termous.desktop_workflows.templates.discard` 丢弃未确认预览；`termous.desktop_workflows.captures.release` 释放快照。临时资源 5 分钟过期，过期后重新获取，禁止把新截图当作旧原帧。

图片正文仅使用工具图片块；定义只引用 asset_id，不粘贴 Base64。模板原图不缩小保存。没有图片能力的模型可以管理已有脚本，但不能自动完成视觉选区与确认。

例如找到软件图标后双击：步骤 kind 为 pointer.click，action 为 {"button":"left","count":2}，target 为 {"kind":"image","image":{"asset_id":"工具返回的资产标识","threshold":0.95,"offset":{"x":0,"y":0}}}。运行器会重新定位，不需要先用测试定位工具发点击；建议再加 image.wait 或 image.assert 检查窗口是否打开。

## 固定版本运行与结束

- `termous.desktop_workflows.runs.start` 指定明确 version；session_id＋connection_generation 与 profile_id 二选一。默认不抢占，takeover=true 必须符合用户授权目标和范围。
- 开始返回 run_id，Core 继续准备并发起全局审批。waiting_user_action 由可信界面处理证书、主机密钥或缺失凭据；不要自行信任或代填密码。
- 运行有自己的控制授权，不能把已有直接输入授权借给脚本。最长 30 分钟，15 分钟无有效运行截图／输入释放。报告轮询和模板预览不续授权。
- 使用 `termous.desktop_workflows.runs.get` 的 after_revision 与 wait_ms（最多 10000）等待变化。超时只是当前快照。**必须等待终态后再结束本轮 Agent Run 或关闭 MCP 会话**；调用方结束会取消运行，不能承诺它脱离本轮继续后台执行。
- `termous.desktop_workflows.runs.list` 分页查摘要。`termous.desktop_workflows.runs.control` 只能管理自己的运行，action 为 pause、resume、step 或 cancel；人工界面可随时干预，不能自动抢回控制。
- 页面关闭不取消运行。自己创建的连接默认在仍独占时关闭；keep_connection=true 保留。已有连接始终保留。
- 先读报告，再按需用 `termous.desktop_workflows.assets.get` 读取证据。提供 run_id，或 script_id＋version 证明图片关系；本调用方刚确认的待保存模板可直接读取。
- 动作 accepted 只表示协议接受；没有断言的 completed 是“执行完成”。uncertain、清理失败或已派发后断线不能自动重试，重新观察并向用户说明已知范围。

## 权限

所有工具均要求 desktop_workflows:read。编辑需要 write；删除需要 delete；启动／控制需要 run。图像工具还需 desktops:capture。启动另需 desktops:read、capture、control；创建连接需 connect，自动关闭新连接还需 close。已有客户端不会自动增加这些权限。

仅使用声明式步骤，不执行任意代码、OCR、定时调度或跨桌面脚本。不扩大用户的真实远端测试授权。
