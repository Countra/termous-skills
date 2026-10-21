"""校验统一能力契约，并同步 Core 与 Worker 使用的只读生成副本。"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"list", "inspect", "observe", "preview", "submit", "poll", "result", "mutate", "input", "cancel", "close"}
FAILURES = {"blocked", "uncertain", "stale", "pending", "missing", "invalid", "unavailable", "unknown"}
BINDINGS = {"ssh_session", "ssh_profile", "desktop_session", "desktop_profile", "file_profile"}


def full_name(capability, name):
    return name if name.startswith("termous.") or name == "wait_workflow_run" else capability["prefix"] + name


def validate_catalog(root=ROOT):
    catalog = json.loads((root / "contracts/agent-capabilities.json").read_text(encoding="utf-8"))
    contract = json.loads((root / "contracts/mcp-tools.json").read_text(encoding="utf-8"))
    expected = {tool["name"] for tool in contract["tools"]} | {"wait_workflow_run"}
    if catalog["version"] != 1:
        raise ValueError("不支持的能力契约版本")
    operations = catalog.get("operations", {})
    if not operations or not all(isinstance(key, str) and key.isascii() and key.isidentifier() and isinstance(words, str) and words for key, words in operations.items()):
        raise ValueError("检索动作词表不合法")
    names, ids = set(), set()
    references = []
    for capability in catalog["capabilities"]:
        if capability["id"] in ids or not all(capability.get(key) for key in ("id", "group", "prefix", "keywords", "purpose", "skill", "entry", "recovery", "steps")):
            raise ValueError("能力定义重复或缺少职责、入口和恢复说明")
        ids.add(capability["id"])
        evidence = capability.get("evidence", {})
        if "approvals" in evidence and (not isinstance(evidence["approvals"], list) or not evidence["approvals"]
                                        or any(not isinstance(path, str) or not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", path)
                                               for path in evidence["approvals"])):
            raise ValueError("审批证据必须使用非空字段路径列表")
        if "settled" in evidence and (not evidence.get("states") or not isinstance(evidence["settled"], list)
                                      or not evidence["settled"] or any(not isinstance(state, str) or not state for state in evidence["settled"])):
            raise ValueError("资源就绪态必须引用状态字段并声明非空状态枚举")
        validate_uri(root, capability["skill"])
        references.extend(full_name(capability, name) for name in capability["entry"] + capability["recovery"] + capability.get("missing", []))
        if any(key not in {"session", "profile"} or value not in BINDINGS for key, value in capability.get("bindings", {}).items()):
            raise ValueError("能力契约引用未知的目标绑定")
        declared = capability.get("operations", {})
        if set(declared) != {name for step in capability["steps"] for name in step["tools"]}:
            raise ValueError("每个工具必须有且仅有一份检索动作声明")
        if any(not isinstance(values, list) or not values or any(value not in operations for value in values) for values in declared.values()):
            raise ValueError("工具引用未知或空检索动作")
        for step in capability["steps"]:
            if step["role"] not in ROLES or not step["tools"]:
                raise ValueError("能力阶段不合法")
            if "preparation" in step and (not isinstance(step["preparation"], str) or not step["preparation"].strip() or len(step["preparation"]) > 1200):
                raise ValueError("调用前说明必须为非空且不超过 1200 字符的文本")
            if "recovery" in step and (not isinstance(step["recovery"], list) or any(not isinstance(name, str) or not name for name in step["recovery"])):
                raise ValueError("阶段恢复入口必须为工具名称列表")
            for short_name in step["tools"]:
                name = full_name(capability, short_name)
                if name in names:
                    raise ValueError(f"工具有多个职责定义: {name}")
                names.add(name)
            references.extend(full_name(capability, name) for name in step.get("next", []) + step.get("cleanup", []) + step.get("recovery", []))
            if "completion" in step:
                references.append(full_name(capability, step["completion"]["next"]))
            if "progresses" in step:
                progresses = step["progresses"]
                references.extend(full_name(capability, name) for name in progresses["tools"])
                if not isinstance(progresses.get("path"), str) or not progresses["path"]:
                    raise ValueError("进展规则必须引用非空回执字段")
                if "collection" in progresses and not isinstance(progresses["collection"], bool):
                    raise ValueError("空集合进展标记必须为布尔值")
                if progresses.get("collection"):
                    empty_lists = {name for case in capability.get("cases", []) if case.get("empty") is True for name in case["tools"]}
                    lists = {name for previous in capability["steps"] if previous["role"] == "list" for name in previous["tools"]}
                    if not progresses["tools"] or set(progresses["tools"]) - (empty_lists & lists):
                        raise ValueError("空集合进展只能引用同能力中声明了空结果的列表")
        for case in capability.get("cases", []):
            references.extend(full_name(capability, name) for name in case["tools"] + case["next"])
            if not case.get("tools") or not case.get("guidance") or not (case.get("path") or case.get("errors")):
                raise ValueError("恢复规则缺少工具、条件或说明")
            if any(value not in FAILURES for value in case.get("errors", [])):
                raise ValueError("恢复规则引用未知错误类别")
            if any(value not in {"session", "profile", "unbound"} for value in case.get("targets", [])):
                raise ValueError("恢复规则引用未知目标类别")
            if any(target != "unbound" and target not in capability.get("bindings", {}) for target in case.get("targets", [])):
                raise ValueError("目标恢复规则必须声明绑定来源")
            if case.get("codes") and not case.get("errors"):
                raise ValueError("错误码规则必须声明错误类别")
            if case.get("omittedIsEmpty") and (case.get("empty") is not True or not case.get("path") or case.get("errors")):
                raise ValueError("旧版空集合兼容只能用于明确的成功列表结果")
    if names != expected:
        raise ValueError(f"工具职责覆盖不完整: missing={sorted(expected - names)}, extra={sorted(names - expected)}")
    for uri, entries in catalog.get("skillEntries", {}).items():
        validate_uri(root, uri)
        if len(entries) > 8 or len(entries) != len(set(entries)):
            raise ValueError("Skill 入口超出加载上限或存在重复工具")
        references.extend(entries)
    if set(references) - names:
        raise ValueError(f"导航引用不存在的工具: {sorted(set(references) - names)}")
    return catalog


def validate_uri(root, uri):
    if not uri.startswith("skill://") or ".." in uri or "\\" in uri:
        raise ValueError(f"非法 Skill URI: {uri}")
    if not (root / "skills" / uri.removeprefix("skill://")).is_file():
        raise ValueError(f"Skill 子资源不存在: {uri}")


def synchronize(check=False, web_root=None, backend_root=None):
    catalog = validate_catalog()
    content = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n"
    targets = []
    for directory, relative in [
        (web_root, "electron/agent/contracts/capabilities.generated.json"),
        (backend_root, "internal/api/mcp/toolkit/capabilities.generated.json"),
    ]:
        if directory is not None:
            targets.append(Path(directory) / relative)
    for target in targets:
        if check:
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                raise ValueError(f"能力契约生成副本过期，请运行 sync_capabilities.py: {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
    return len(catalog["capabilities"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--web-root", type=Path)
    parser.add_argument("--backend-root", type=Path)
    args = parser.parse_args()
    try:
        count = synchronize(args.check, args.web_root, args.backend_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"能力契约校验失败: {error}\n")
    print(f"能力契约通过: {count} 个能力，134 个 MCP 工具和 1 个本地等待工具")
