"""文件能力改名必须保留 v1 的授权、审批及其余工具合同。"""

import copy
import json
import unittest
from unittest.mock import patch

from test_backend_registry import validator


class FileContractRenameTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(validator.CONTRACT_PATH.read_text(encoding="utf-8"))

    def validate(self):
        errors = []
        with patch.object(validator, "read_json", return_value=copy.deepcopy(self.contract)):
            validator.validate_contract(errors)
        return errors

    def test_complete_rename_preserves_frozen_v1_contract(self):
        self.assertEqual(self.validate(), [])
        renamed = [tool for tool in self.contract["tools"] if tool["skill"] == "termous-files"]
        self.assertEqual(len(renamed), 31)
        self.assertEqual(len(self.contract["tools"]) - len(renamed), 61)
        self.assertEqual(len(set(validator.FILE_TOOL_RENAMES.values())), 31)
        self.assertEqual(len(set(validator.FILE_SCOPE_RENAMES.values())), 9)

    def test_unrelated_tool_approval_and_file_scope_cannot_drift(self):
        changes = [
            ("termous.commands.dispatch", "approval", "none"),
            ("termous.files.delete.start", "scope", "files:write"),
            ("termous.files.delete.start", "approval", "none"),
            ("termous.files.read_text", "skill", "termous-sftp"),
        ]
        for name, field, value in changes:
            with self.subTest(name=name, field=field):
                original = copy.deepcopy(self.contract)
                next(tool for tool in self.contract["tools"] if tool["name"] == name)[field] = value
                self.assertTrue(self.validate())
                self.contract = original

    def test_old_external_names_and_guessed_rename_are_rejected(self):
        for name in ("termous.sftp.files.read_text", "termous.files.files.read_text", "termous.files.local_browse"):
            with self.subTest(name=name):
                original = copy.deepcopy(self.contract)
                next(tool for tool in self.contract["tools"] if tool["name"] == "termous.files.read_text")["name"] = name
                self.assertTrue(self.validate())
                self.contract = original

    def test_shared_capability_does_not_accept_manage_scope(self):
        original = copy.deepcopy(self.contract)
        capability = next(tool for tool in self.contract["tools"] if tool["name"] == "termous.remoteops.docker.capability")
        capability["alternative_scopes"].append("docker:images:manage")
        self.assertTrue(self.validate())
        self.contract = original

    def test_old_search_scope_and_reordered_tools_are_rejected(self):
        original = copy.deepcopy(self.contract)
        self.contract["scopes"] = ["sftp:file_search" if scope == "files:search" else scope for scope in self.contract["scopes"]]
        self.assertTrue(self.validate())
        self.contract = original
        self.contract["tools"][0], self.contract["tools"][1] = self.contract["tools"][1], self.contract["tools"][0]
        self.assertTrue(self.validate())


if __name__ == "__main__":
    unittest.main()
