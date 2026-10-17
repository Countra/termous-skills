"""能力契约需要完整覆盖，并拒绝不存在的工具或失效文档。"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("capabilities", ROOT / "scripts/sync_capabilities.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CapabilityTests(unittest.TestCase):
    def test_complete_catalog(self):
        catalog = MODULE.validate_catalog()
        self.assertEqual(len(catalog["capabilities"]), 29)

    def test_generated_copies_are_checked_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            MODULE.synchronize(web_root=directory)
            MODULE.synchronize(check=True, web_root=directory)
            target = Path(directory) / "electron/agent/contracts/capabilities.generated.json"
            target.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "过期"):
                MODULE.synchronize(check=True, web_root=directory)
            self.assertEqual(target.read_text(encoding="utf-8"), "{}")

    def test_missing_or_duplicate_tools_and_missing_resources_are_rejected(self):
        source = json.loads((ROOT / "contracts/agent-capabilities.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "contracts").mkdir()
            (root / "contracts/mcp-tools.json").write_bytes((ROOT / "contracts/mcp-tools.json").read_bytes())
            uris = [family["skill"] for family in source["capabilities"]] + list(source["skillEntries"])
            for uri in uris:
                path = root / "skills" / uri.removeprefix("skill://")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("流程说明", encoding="utf-8")
            for change in ("missing", "duplicate", "reference", "resource", "operation_missing", "operation_unknown", "settled_without_states", "settled_invalid", "approval_path", "approval_type", "recovery_error", "recovery_target", "unreachable_target", "empty_error", "entry_overflow", "progress_path", "progress_collection", "progress_target", "preparation_type", "preparation_empty", "preparation_length"):
                catalog = json.loads(json.dumps(source))
                family = catalog["capabilities"][0]
                if change == "missing":
                    family["steps"][0]["tools"].pop()
                elif change == "duplicate":
                    family["steps"].append(family["steps"][0])
                elif change == "reference":
                    family["recovery"] = ["invented"]
                elif change == "resource":
                    family["skill"] = "skill://termous-remote-ops/references/missing.md"
                elif change == "operation_missing":
                    del family["operations"]["list"]
                elif change == "settled_without_states":
                    family["evidence"] = {"settled": ["running"]}
                elif change == "settled_invalid":
                    family["evidence"] = {"states": ["instance.status"], "settled": [None]}
                elif change.startswith("approval_"):
                    family["evidence"] = {"approvals": ["control[0].approval"] if change == "approval_path" else "control.approval"}
                elif change == "recovery_error":
                    family["cases"] = [{"tools": ["list"], "errors": ["invented"], "next": [], "guidance": "说明"}]
                elif change == "recovery_target":
                    family["cases"] = [{"tools": ["list"], "errors": ["missing"], "targets": ["session"], "next": [], "guidance": "说明"}]
                elif change == "unreachable_target":
                    family["bindings"] = {"profile": "file_profile"}
                    family["cases"] = [{"tools": ["list"], "errors": ["missing"], "targets": ["session"], "next": [], "guidance": "说明"}]
                elif change == "empty_error":
                    family["cases"] = [{"tools": ["list"], "path": "items", "errors": ["missing"], "empty": True, "omittedIsEmpty": True, "next": [], "guidance": "说明"}]
                elif change == "entry_overflow":
                    catalog["skillEntries"][next(iter(catalog["skillEntries"]))] = ["termous.hosts.list"] * 9
                elif change.startswith("preparation_"):
                    family["steps"][0]["preparation"] = {"preparation_type": [], "preparation_empty": " ", "preparation_length": "前" * 1201}[change]
                elif change.startswith("progress_"):
                    family["steps"][0]["progresses"] = {"tools": ["access_profiles.list"], "path": "catalog.id"}
                    progresses = family["steps"][0]["progresses"]
                    if change == "progress_path":
                        progresses["path"] = ""
                    else:
                        progresses["collection"] = "true" if change == "progress_collection" else True
                else:
                    family["operations"]["list"] = ["invented_action"]
                (root / "contracts/agent-capabilities.json").write_text(json.dumps(catalog), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(ValueError):
                    MODULE.validate_catalog(root)
