"""校验同一 MCP 模块拆分注册文件后仍检查全部工具和授权入口。"""

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_skills.py"
SPEC = importlib.util.spec_from_file_location("validate_skills", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class BackendRegistryTests(unittest.TestCase):
    def test_split_registry_preserves_scope_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = root / "internal/api/mcp"
            (registry / "files").mkdir(parents=True)
            model = root / "internal/model/mcpaccess"
            model.mkdir(parents=True)
            (model / "types.go").write_text(
                'ScopeFilesDelete Scope = "files:delete"\nProtocolVersion = "2025-11-25"\n', encoding="utf-8"
            )
            (registry / "handler.go").write_text("package mcpapi\n", encoding="utf-8")
            (registry / "registry.go").write_text(
                'import (\n\tfilesapi "termous/backend/internal/api/mcp/files"\n)\n'
                'func registerTools() {\n\tfilesapi.RegisterDelete()\n}\n', encoding="utf-8"
            )
            split = registry / "files/delete_registry.go"
            source = (
                'func RegisterDelete() {\n\tif principal.HasScope(mcpaccessmodel.ScopeFilesDelete) {\n'
                '\t\tName: "termous.files.delete.preview"\n\t}\n}\n'
            )
            split.write_text(source, encoding="utf-8")
            tool = "termous.files.delete.preview"
            contract = {"scopes": ["files:delete"], "tools": [{"name": tool, "scope": "files:delete"}],
                        "mcp_protocol_version": "2025-11-25"}
            errors = []
            validator.validate_backend(root, contract, {tool}, errors)
            self.assertEqual(errors, [])

            (registry / "files/duplicate_registry.go").write_text(source, encoding="utf-8")
            errors = []
            validator.validate_backend(root, contract, {tool}, errors)
            self.assertTrue(any("defined more than once" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
