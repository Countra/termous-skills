# 创建与编辑

1. 先调用 `termous.desktop_workflows.schema` 读取当前步骤合同和限制，再用 `termous.desktop_workflows.list` 搜索现有脚本。脚本库为本机共享库，编辑前确认用户指的是哪一个脚本。
2. `termous.desktop_workflows.get` 返回指定版本正文；`termous.desktop_workflows.versions` 分页返回作者和版本摘要。
3. `termous.desktop_workflows.create` 可创建空草稿或完整定义。`termous.desktop_workflows.update` 必须携带 `expected_revision`，使用完整 `definition` 或稳定步骤 ID 的 `changes`，两种方式互斥。批量编辑最多 64 项，失败不部分保存；移动的 index 指移除原项后的索引。
4. `termous.desktop_workflows.duplicate` 指定源版本和新名称；`termous.desktop_workflows.restore` 指定历史版本与当前预期修订号，产生新版本。修改者不会覆盖原创建者。
5. `termous.desktop_workflows.validate` 检查完整定义。参数类型为 string、number、boolean；敏感文本只在启动时提供，不写入默认值、步骤文字或说明。
6. `termous.desktop_workflows.delete` 需要对应权限，并遵循 Termous 当前审批策略。删除保留已有报告；冲突时读取新版本，不自动覆盖。

编辑与确认模板免人工审批，不等于授权执行远端输入。每个变更使用新的 `client_request_id`；传输不确定时重复同一标识和同一参数，不能换标识重放。
