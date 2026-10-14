---
name: termous-desktop-workflows
description: 使用 Termous MCP 创建、编辑和运行 RDP／VNC 可视化桌面脚本，提取并确认图像模板，读取回归测试报告。适用于可重复的桌面流程、图像定位和 UI 回归；即时鼠标键盘操作使用 termous-remote-desktop，本机应用发现使用 termous-desktop。
---

# Termous 桌面脚本

通过已授权的 `termous.desktop_workflows.*` 创建、编辑和运行可重复的 RDP／VNC 流程。内置 Agent 先用 discover_tools 按意图加载所需工具；外部 MCP 客户端使用自身工具发现机制。缺少工具不能绕过权限或读取凭据。

按当前任务读取对应小节，无需每次加载全部内容：

- [脚本创建、局部编辑与版本](references/editing.md)
- [固定截图、局部查看与模板确认](references/templates.md)
- [固定版本运行、报告与失败处理](references/runs.md)
- 连接与即时输入参见 `termous-remote-desktop`。

## 必须保留的规则

- 坐标基于返回 image_view 的展示像素。小目标先 captures.view 放大观察，再 templates.preview；Core 换算原始像素，不手算比例，不猜 original 坐标模式。
- 模板每边为 8～512 原始像素，选择紧凑稳定特征；检查预览后显式确认，再引用 asset_id。建议先测试定位；测试不点击，当前未匹配也不妨碍保存有效模板。
- 遵守当前 Run 明确给出的执行预算；启用时，同一桌面选区流程不会因重新截图或更换 request_id 重置。预算默认关闭，不自行附加固定次数上限；重复失败时应根据诊断调整方案，缺少能力或必要信息时向用户说明。
- 图像正文仅使用图片内容块，定义只保存资产引用。无视觉能力时不能自动确认选区。
- 打开应用与已知 URL 优先快捷键、文本输入和后续验证，不为每次按键创建模板。
- “今天的日报”不能用今天标题的固定截图保证长期正确。区分固定期号、列表最新一期与按当天日期判断；当前纯像素能力不足时说明边界，不默认第一条就是今天。
- 运行固定版本；必须等终态或明确取消后结束本轮。结果不确定的输入不能自动重放。
- 全部操作仍由 Core 校验权限、审批、身份与归属；页面关闭不影响运行，Agent Run／MCP 会话结束会清理所属运行。
