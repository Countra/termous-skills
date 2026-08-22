#!/usr/bin/env python3
"""校验 Termous Skill 结构以及同步维护的 MCP 能力合同。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
CONTRACT_PATH = ROOT / "contracts" / "mcp-tools.json"
ROUTING_CASES_PATH = ROOT / "tests" / "routing-cases.json"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
TOOL_NAME_PATTERN = re.compile(r'^\s*Name:\s*"(termous\.[^"]+)"', re.MULTILINE)
TOOL_SCOPE_PATTERN = re.compile(r"^\s*if\s+principal\.HasScope\(mcpaccessmodel\.(Scope\w+)\)")
SCOPE_PATTERN = re.compile(r'(Scope\w+)\s+Scope\s*=\s*"([^"]+)"')
PROTOCOL_PATTERN = re.compile(r'ProtocolVersion\s*=\s*"([^"]+)"')
PROTOCOL_VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MODULE_IMPORT_PATTERN = re.compile(
    r'^\s*(?:(\w+)\s+)?"termous/backend/internal/api/mcp/([^"]+)"\s*$', re.MULTILINE
)
REGISTER_CALL_PATTERN = re.compile(r"^\s*(\w+)\.(Register\w*)\(", re.MULTILINE)
TOP_LEVEL_FUNCTION_PATTERN = re.compile(
    r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(", re.MULTILINE
)
ALLOWED_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}
ALLOWED_APPROVALS = {"none", "per-call"}
ROUTING_KINDS = {"direct", "cross-domain", "ambiguous", "negative"}
EXPECTED_CONTRACT_VERSION = 1
EXPECTED_SKILL_COUNT = 6
EXPECTED_TOOL_COUNT = 73
EXPECTED_SCOPE_COUNT = 28


def read_json(path: Path, errors: list[str]) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return {}


def parse_frontmatter(path: Path, errors: list[str]) -> tuple[dict[str, object], str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
        return {}, ""

    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
    if match is None:
        errors.append(f"{path.relative_to(ROOT)}: missing or invalid YAML frontmatter")
        return {}, content
    try:
        value = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid YAML frontmatter: {exc}")
        return {}, content[match.end() :]
    if not isinstance(value, dict):
        errors.append(f"{path.relative_to(ROOT)}: frontmatter must be an object")
        return {}, content[match.end() :]
    return value, content[match.end() :]


def validate_contract(errors: list[str]) -> tuple[dict[str, object], set[str], set[str]]:
    raw = read_json(CONTRACT_PATH, errors)
    if not isinstance(raw, dict):
        return {}, set(), set()

    scopes = raw.get("scopes")
    tools = raw.get("tools")
    if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
        errors.append("contracts/mcp-tools.json: scopes must be an array of strings")
        scopes = []
    if not isinstance(tools, list) or not all(isinstance(item, dict) for item in tools):
        errors.append("contracts/mcp-tools.json: tools must be an array of objects")
        tools = []

    contract = dict(raw)
    contract["scopes"] = scopes
    contract["tools"] = tools

    if raw.get("contract_version") != EXPECTED_CONTRACT_VERSION:
        errors.append(
            f"contracts/mcp-tools.json: contract_version must be {EXPECTED_CONTRACT_VERSION}"
        )
    protocol_version = raw.get("mcp_protocol_version")
    if not isinstance(protocol_version, str) or not PROTOCOL_VERSION_PATTERN.fullmatch(protocol_version):
        errors.append("contracts/mcp-tools.json: invalid mcp_protocol_version")

    scope_set = set(scopes)
    if len(scope_set) != len(scopes):
        errors.append("contracts/mcp-tools.json: duplicate scopes")
    if raw.get("scope_count") != len(scopes):
        errors.append("contracts/mcp-tools.json: scope_count does not match scopes")
    if raw.get("tool_count") != len(tools):
        errors.append("contracts/mcp-tools.json: tool_count does not match tools")
    if len(scopes) != EXPECTED_SCOPE_COUNT:
        errors.append(f"contracts/mcp-tools.json: expected {EXPECTED_SCOPE_COUNT} Scopes, found {len(scopes)}")
    if len(tools) != EXPECTED_TOOL_COUNT:
        errors.append(f"contracts/mcp-tools.json: expected {EXPECTED_TOOL_COUNT} Tools, found {len(tools)}")

    names: list[str] = []
    owners: set[str] = set()
    used_scopes: set[str] = set()
    for index, tool in enumerate(tools):
        prefix = f"contracts/mcp-tools.json: tools[{index}]"
        name = tool.get("name")
        owner = tool.get("skill")
        scope = tool.get("scope")
        approval = tool.get("approval")
        if not isinstance(name, str) or not name.startswith("termous."):
            errors.append(f"{prefix}: invalid Tool name")
        else:
            names.append(name)
        if not isinstance(owner, str) or not SKILL_NAME_PATTERN.fullmatch(owner):
            errors.append(f"{prefix}: invalid owner Skill")
        else:
            owners.add(owner)
        if not isinstance(scope, str) or scope not in scope_set:
            errors.append(f"{prefix}: unknown Scope {scope!r}")
        else:
            used_scopes.add(scope)
        if not isinstance(approval, str) or approval not in ALLOWED_APPROVALS:
            errors.append(f"{prefix}: invalid approval {approval!r}")

    duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
    if duplicates:
        errors.append(f"contracts/mcp-tools.json: duplicate Tools: {', '.join(duplicates)}")
    unused_scopes = sorted(scope_set - used_scopes)
    if unused_scopes:
        errors.append(f"contracts/mcp-tools.json: unused Scopes: {', '.join(unused_scopes)}")
    return contract, set(names), owners


def validate_links(skill_dir: Path, errors: list[str]) -> None:
    for markdown in skill_dir.rglob("*.md"):
        content = markdown.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_PATTERN.findall(content):
            target = raw_target.strip().split("#", 1)[0]
            if not target or re.match(r"^[a-z]+://", target, re.IGNORECASE):
                continue
            resolved = (markdown.parent / target).resolve()
            try:
                resolved.relative_to(skill_dir.resolve())
            except ValueError:
                errors.append(f"{markdown.relative_to(ROOT)}: link escapes the Skill: {raw_target}")
                continue
            if not resolved.exists():
                errors.append(f"{markdown.relative_to(ROOT)}: missing link target {raw_target}")


def validate_skill(skill_dir: Path, errors: list[str]) -> str | None:
    skill_file = skill_dir / "SKILL.md"
    frontmatter, body = parse_frontmatter(skill_file, errors)
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    unexpected = sorted(set(frontmatter) - ALLOWED_FRONTMATTER)
    if unexpected:
        errors.append(f"{skill_file.relative_to(ROOT)}: unsupported frontmatter: {', '.join(unexpected)}")
    if name != skill_dir.name:
        errors.append(f"{skill_file.relative_to(ROOT)}: name must match directory {skill_dir.name}")
    if not isinstance(name, str) or not SKILL_NAME_PATTERN.fullmatch(name) or len(name) > 64:
        errors.append(f"{skill_file.relative_to(ROOT)}: invalid Skill name")
        return None
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append(f"{skill_file.relative_to(ROOT)}: invalid description")
    elif "<" in description or ">" in description:
        errors.append(f"{skill_file.relative_to(ROOT)}: description cannot contain angle brackets")
    if re.search(r"^\s*\[TODO:[^\]]*\]\s*$", body, re.MULTILINE):
        errors.append(f"{skill_file.relative_to(ROOT)}: unfinished TODO placeholder")

    metadata_path = skill_dir / "agents" / "openai.yaml"
    try:
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{metadata_path.relative_to(ROOT)}: invalid metadata: {exc}")
        metadata = {}
    interface = metadata.get("interface") if isinstance(metadata, dict) else None
    if not isinstance(interface, dict):
        errors.append(f"{metadata_path.relative_to(ROOT)}: interface is required")
    else:
        for field in ("display_name", "short_description", "default_prompt"):
            if not isinstance(interface.get(field), str) or not interface[field].strip():
                errors.append(f"{metadata_path.relative_to(ROOT)}: interface.{field} is required")
        short_description = interface.get("short_description", "")
        if isinstance(short_description, str) and not 25 <= len(short_description) <= 64:
            errors.append(f"{metadata_path.relative_to(ROOT)}: short_description must be 25-64 characters")
        default_prompt = interface.get("default_prompt", "")
        if isinstance(default_prompt, str) and f"${name}" not in default_prompt:
            errors.append(f"{metadata_path.relative_to(ROOT)}: default_prompt must mention ${name}")
    if isinstance(metadata, dict) and metadata.get("dependencies"):
        errors.append(f"{metadata_path.relative_to(ROOT)}: fixed MCP dependencies are not allowed")
    policy = metadata.get("policy") if isinstance(metadata, dict) else None
    if isinstance(policy, dict) and policy.get("allow_implicit_invocation") is False:
        errors.append(f"{metadata_path.relative_to(ROOT)}: implicit invocation must remain enabled")

    validate_links(skill_dir, errors)
    return name


def validate_routing_cases(skill_names: set[str], errors: list[str]) -> None:
    raw = read_json(ROUTING_CASES_PATH, errors)
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list):
        errors.append("tests/routing-cases.json: cases must be an array")
        return
    prompts: set[str] = set()
    covered: set[str] = set()
    kinds: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"tests/routing-cases.json: cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: case must be an object")
            continue
        prompt = case.get("prompt")
        expected = case.get("expected_skills")
        kind = case.get("kind")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{prefix}: prompt is required")
        elif prompt in prompts:
            errors.append(f"{prefix}: duplicate prompt")
        else:
            prompts.add(prompt)
        if kind not in ROUTING_KINDS:
            errors.append(f"{prefix}: invalid kind {kind!r}")
        else:
            kinds.add(kind)
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            errors.append(f"{prefix}: expected_skills must be an array of strings")
            continue
        unknown = sorted(set(expected) - skill_names)
        if unknown:
            errors.append(f"{prefix}: unknown Skills: {', '.join(unknown)}")
        covered.update(expected)
        if kind == "negative" and expected:
            errors.append(f"{prefix}: negative case cannot expect a Skill")
    missing = sorted(skill_names - covered)
    if missing:
        errors.append(f"tests/routing-cases.json: no positive case for: {', '.join(missing)}")
    missing_kinds = sorted(ROUTING_KINDS - kinds)
    if missing_kinds:
        errors.append(f"tests/routing-cases.json: missing case kinds: {', '.join(missing_kinds)}")


def go_function_sections(source: str) -> dict[str, str]:
    matches = list(TOP_LEVEL_FUNCTION_PATTERN.finditer(source))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        sections[match.group(1)] = source[match.start() : end]
    return sections


def validate_backend(backend_root: Path, contract: dict[str, object], tool_names: set[str], errors: list[str]) -> None:
    registry_root = backend_root / "internal" / "api" / "mcp"
    root_registry = registry_root / "registry.go"
    model_file = backend_root / "internal" / "model" / "mcpaccess" / "types.go"
    handler_file = backend_root / "internal" / "api" / "mcp" / "handler.go"
    if (
        not registry_root.is_dir()
        or not root_registry.is_file()
        or not model_file.is_file()
        or not handler_file.is_file()
    ):
        errors.append(f"backend root is not a compatible Termous Backend: {backend_root}")
        return

    scope_declarations = dict(SCOPE_PATTERN.findall(model_file.read_text(encoding="utf-8")))
    backend_scopes = set(scope_declarations.values())
    contract_scopes = set(contract.get("scopes", []))
    if backend_scopes != contract_scopes:
        missing = sorted(backend_scopes - contract_scopes)
        stale = sorted(contract_scopes - backend_scopes)
        if missing:
            errors.append(f"contract misses Backend Scopes: {', '.join(missing)}")
        if stale:
            errors.append(f"contract contains stale Scopes: {', '.join(stale)}")

    root_registry_source = root_registry.read_text(encoding="utf-8")
    imported_modules = {
        alias or module_path.rsplit("/", 1)[-1]: module_path
        for alias, module_path in MODULE_IMPORT_PATTERN.findall(root_registry_source)
    }
    register_calls = REGISTER_CALL_PATTERN.findall(root_registry_source)
    registered_entrypoint_counts = Counter(register_calls)
    for (alias, function_name), count in sorted(registered_entrypoint_counts.items()):
        if count > 1:
            errors.append(
                f"Backend MCP entrypoint is registered more than once: {alias}.{function_name}"
            )
    module_registries = {
        registry.parent.relative_to(registry_root).as_posix(): registry
        for registry in registry_root.rglob("registry.go")
        if registry != root_registry and TOOL_NAME_PATTERN.search(registry.read_text(encoding="utf-8"))
    }

    available_entrypoints: dict[tuple[str, str], str] = {}
    for module_path, registry in module_registries.items():
        source = registry.read_text(encoding="utf-8")
        for function_name, section in go_function_sections(source).items():
            if function_name.startswith("Register") and TOOL_NAME_PATTERN.search(section):
                available_entrypoints[(module_path, function_name)] = section

    registered_entrypoints: list[tuple[str, str]] = []
    for alias, function_name in register_calls:
        module_path = imported_modules.get(alias)
        if module_path is None:
            continue
        entrypoint = (module_path, function_name)
        registered_entrypoints.append(entrypoint)
        if entrypoint not in available_entrypoints:
            errors.append(
                f"Backend registered MCP entrypoint has no Tool registry: "
                f"{module_path}.{function_name}"
            )
    for module_path, function_name in sorted(set(available_entrypoints) - set(registered_entrypoints)):
        errors.append(f"Backend MCP Tool entrypoint is not registered: {module_path}.{function_name}")

    backend_tool_scopes: dict[str, str] = {}
    for entrypoint in registered_entrypoints:
        source = available_entrypoints.get(entrypoint)
        if source is None:
            continue
        current_scope = ""
        scope_indent = -1
        for line in source.splitlines():
            indent = len(line) - len(line.lstrip())
            if scope_match := TOOL_SCOPE_PATTERN.search(line):
                current_scope = scope_declarations.get(scope_match.group(1), "")
                scope_indent = indent
            # Registry 由 gofmt 格式化；回到 HasScope 同级缩进即离开授权块。
            elif current_scope and line.strip() and indent <= scope_indent:
                current_scope = ""
                scope_indent = -1
            for tool_name in TOOL_NAME_PATTERN.findall(line):
                if not current_scope:
                    errors.append(f"Backend Tool has no recognized Scope: {tool_name}")
                    continue
                previous_scope = backend_tool_scopes.get(tool_name)
                if previous_scope is not None:
                    if previous_scope == current_scope:
                        errors.append(f"Backend Tool is registered more than once: {tool_name}")
                    else:
                        errors.append(
                            f"Backend Tool is registered under multiple Scopes: "
                            f"{tool_name} ({previous_scope}, {current_scope})"
                        )
                    continue
                backend_tool_scopes[tool_name] = current_scope

    backend_tools = set(backend_tool_scopes)
    if backend_tools != tool_names:
        missing = sorted(backend_tools - tool_names)
        stale = sorted(tool_names - backend_tools)
        if missing:
            errors.append(f"contract misses Backend Tools: {', '.join(missing)}")
        if stale:
            errors.append(f"contract contains stale Tools: {', '.join(stale)}")

    contract_tool_scopes = {
        tool["name"]: tool["scope"]
        for tool in contract.get("tools", [])
        if isinstance(tool, dict) and isinstance(tool.get("name"), str) and isinstance(tool.get("scope"), str)
    }
    for tool_name in sorted(backend_tools & tool_names):
        expected_scope = contract_tool_scopes.get(tool_name)
        backend_scope = backend_tool_scopes[tool_name]
        if expected_scope != backend_scope:
            errors.append(
                f"contract Scope differs from Backend for {tool_name}: {expected_scope!r} != {backend_scope!r}"
            )

    match = PROTOCOL_PATTERN.search(handler_file.read_text(encoding="utf-8"))
    if match is None or match.group(1) != contract.get("mcp_protocol_version"):
        errors.append("contract MCP protocol version differs from Backend")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-root", type=Path, help="Optional adjacent Termous Backend root")
    args = parser.parse_args()
    errors: list[str] = []

    contract, tool_names, contract_owners = validate_contract(errors)
    skill_dirs = sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir())
    skill_names = {name for path in skill_dirs if (name := validate_skill(path, errors)) is not None}
    if len(skill_names) != EXPECTED_SKILL_COUNT:
        errors.append(f"expected {EXPECTED_SKILL_COUNT} Skill directories, found {len(skill_names)}")
    if skill_names != contract_owners:
        missing = sorted(contract_owners - skill_names)
        extra = sorted(skill_names - contract_owners)
        if missing:
            errors.append(f"missing Skill directories: {', '.join(missing)}")
        if extra:
            errors.append(f"Skills without Tool ownership: {', '.join(extra)}")

    documents: dict[str, str] = {}
    for skill_dir in skill_dirs:
        documents[skill_dir.name] = "\n".join(
            path.read_text(encoding="utf-8") for path in skill_dir.rglob("*.md")
        )
    for tool in contract.get("tools", []):
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        owner = tool.get("skill")
        if isinstance(name, str) and isinstance(owner, str) and name not in documents.get(owner, ""):
            errors.append(f"{owner}: owned Tool is not documented: {name}")

    validate_routing_cases(skill_names, errors)
    if args.backend_root is not None:
        validate_backend(args.backend_root.resolve(), contract, tool_names, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    backend_note = " with Backend contract comparison" if args.backend_root is not None else ""
    print(f"Validated {len(skill_names)} Skills, {len(tool_names)} Tools, and {len(contract.get('scopes', []))} Scopes{backend_note}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
