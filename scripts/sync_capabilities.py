"""校验统一能力契约，并同步 Core 与 Worker 使用的只读生成副本。"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"list", "inspect", "observe", "preview", "submit", "poll", "result", "mutate", "input", "cancel", "close"}


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
        if "settled" in evidence and (not evidence.get("states") or not isinstance(evidence["settled"], list)
                                      or not evidence["settled"] or any(not isinstance(state, str) or not state for state in evidence["settled"])):
            raise ValueError("资源就绪态必须引用状态字段并声明非空状态枚举")
        validate_uri(root, capability["skill"])
        references.extend(full_name(capability, name) for name in capability["entry"] + capability["recovery"])
        declared = capability.get("operations", {})
        if set(declared) != {name for step in capability["steps"] for name in step["tools"]}:
            raise ValueError("每个工具必须有且仅有一份检索动作声明")
        if any(not isinstance(values, list) or not values or any(value not in operations for value in values) for values in declared.values()):
            raise ValueError("工具引用未知或空检索动作")
        for step in capability["steps"]:
            if step["role"] not in ROLES or not step["tools"]:
                raise ValueError("能力阶段不合法")
            for short_name in step["tools"]:
                name = full_name(capability, short_name)
                if name in names:
                    raise ValueError(f"工具有多个职责定义: {name}")
                names.add(name)
            references.extend(full_name(capability, name) for name in step.get("next", []) + step.get("cleanup", []))
            if "completion" in step:
                references.append(full_name(capability, step["completion"]["next"]))
            if "progresses" in step:
                references.extend(full_name(capability, name) for name in step["progresses"]["tools"])
        for case in capability.get("cases", []):
            references.extend(full_name(capability, name) for name in case["tools"] + case["next"])
    if names != expected:
        raise ValueError(f"工具职责覆盖不完整: missing={sorted(expected - names)}, extra={sorted(names - expected)}")
    for uri, entries in catalog.get("skillEntries", {}).items():
        validate_uri(root, uri)
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
            target.write_text(content, encoding="utf-8")
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
