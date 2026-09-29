"""使用隔离系统接口验证 Skill 中实际提供的 PowerShell 工作流。"""

import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows 安装发现合同仅适用于 Windows")
class DesktopWorkflowTests(unittest.TestCase):
    def test_powershell_workflow_with_isolated_system_interfaces(self):
        fixture = ROOT / "tests" / "desktop-workflow.fixture.ps1"
        reference = ROOT / "skills" / "termous-desktop" / "references" / "windows.md"
        interpreters = list(dict.fromkeys(
            path for name in ("powershell.exe", "pwsh.exe") if (path := shutil.which(name))
        ))
        self.assertTrue(interpreters, "Windows 回归需要已有 PowerShell")
        # 从 UTF-8 读取夹具，避免 Windows PowerShell 按本机代码页解码中文。
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
            f"& ([scriptblock]::Create([IO.File]::ReadAllText({quote(fixture)}))) "
            f"-ReferencePath {quote(reference)}"
        )
        for interpreter in interpreters:
            with self.subTest(interpreter=interpreter):
                result = subprocess.run(
                    [interpreter, "-NoProfile", "-NonInteractive", "-Command", command],
                    capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("DESKTOP_WORKFLOW_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
