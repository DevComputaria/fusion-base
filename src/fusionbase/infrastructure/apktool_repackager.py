"""Repackager usando apktool"""
import subprocess
from pathlib import Path


class ApktoolRepackager:
    def repackage(self, unpacked_dir: Path, output_apk: Path) -> None:
        result = subprocess.run(
            ["apktool", "b", str(unpacked_dir), "-o", str(output_apk)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"apktool build falhou:\n{result.stderr}")
