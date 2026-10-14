# 获取与确认图像模板

1. 通过现有远程桌面工具选择精确会话／保存配置，建立自己的观察附着并等待 ready。不得自行猜测会话 ID、代次或资产 ID。
2. `termous.desktop_workflows.captures.create` 使用 attachment_id，获得固定原帧的 snapshot_id 和预览。默认图片最多 1600×1000；其元数据说明原始区域及缩放关系。
3. 目标很小或文字不清时，先调用 `termous.desktop_workflows.captures.view`，从同一 snapshot_id 的固定帧生成局部视图；返回 image_view.width／height 是实际展示尺寸，source 是原帧元数据。使用 view_id 再选区，不自行换算缩放。视图继承快照到期时间，每所有者最多 8 个。
4. 观察实际图片，再调用 `termous.desktop_workflows.templates.preview`，提交 snapshot_id、region（x、y、width、height）。传入可选 view_id 后，region 一律采用该视图展示像素。默认 image 基于返回图片；desktop 仅用于明确的原图坐标；original 非法。compact=true 只返回模板与附近上下文，节省图片用量。

模板每边必须为 **8～512 个原始像素**，放大视图不能改变此限制。纯色、透明或缺少特征的模板会被拒绝。960 像素宽的整行文字应改为 captures.view 查看，再选择更紧凑的稳定特征。
5. 查看图片 1 的原像素模板和图片 2 的选区上下文。确认没有截错、截断目标或包含不稳定内容；需要调整时创建新预览，不能假装已查看。可用 `termous.desktop_workflows.templates.get` 重新查看。
6. 推荐调用 `termous.desktop_workflows.templates.match`：preview_id 和 target.asset_id 二选一。它在当前桌面只读搜索，返回候选框和分数，不点击。多个候选不代表唯一可点击，缩小区域或改选模板。
7. 观察正确后显式调用 `termous.desktop_workflows.templates.confirm` 保存同一 preview_id，返回 asset_id。当前目标不在画面上也可以保存有效模板；不要把匹配唯一作为保存的强制条件。
8. `termous.desktop_workflows.captures.release` 释放快照；`termous.desktop_workflows.templates.discard` 丢弃未确认预览。临时资源 5 分钟过期，过期后重新获取，禁止把新截图当作旧原帧。

创建和释放是不同操作。缺少准确工具时先 `discover_tools` 搜索 `termous.desktop_workflows.captures.create`，不能拿 release 代替；释放返回 completed 后不再对同一 snapshot_id 调用 release。需要新画面时用有效 attachment_id 创建新快照。

图片正文仅使用工具图片块；定义只引用 asset_id，不粘贴 Base64。模板原图不缩小保存。没有图片能力的模型可以管理已有脚本，但不能自动完成视觉选区与确认。

例如找到软件图标后双击：步骤 kind 为 pointer.click，action 为 {"button":"left","count":2}，target 为 {"kind":"image","image":{"asset_id":"工具返回的资产标识","threshold":0.95,"offset":{"x":0,"y":0}}}。运行器会重新定位，不需要先用测试定位工具发点击；建议再加 image.wait 或 image.assert 检查窗口是否打开。
