from pathlib import Path
import unittest


class LauncherPathTests(unittest.TestCase):
    def test_launcher_uses_physical_path_without_subst_drive(self):
        launcher = Path(__file__).resolve().parents[1] / "launch-canvas.ps1"
        source = launcher.read_text(encoding="utf-8")

        self.assertNotIn("subst.exe", source)
        self.assertNotIn('Get-DosDeviceTarget -DriveName "R:"', source)
        self.assertIn('$AppDir = $PhysicalAppDir', source)
        self.assertIn('"--app-dir", "`"$AppDir`""', source)


if __name__ == "__main__":
    unittest.main()
