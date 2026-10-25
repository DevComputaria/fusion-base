"""Unpacker usando apktool + bundletool"""
import subprocess
import zipfile
from pathlib import Path


class ApktoolUnpacker:
    def unpack(self, input_path: Path, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

        if input_path.suffix.lower() == ".aab":
            apk = self._aab_to_universal_apk(input_path, dest.parent)
        else:
            apk = input_path

        self._run(["apktool", "d", "-f", "-o", str(dest), str(apk)])

    def _aab_to_universal_apk(self, aab: Path, workdir: Path) -> Path:
        apks = workdir / "universal.apks"
        self._run([
            "bundletool", "build-apks",
            f"--bundle={aab}",
            f"--output={apks}",
            "--mode=universal",
        ])
        with zipfile.ZipFile(apks) as z:
            z.extract("universal.apk", workdir)
        return workdir / "universal.apk"

    def _run(self, cmd: list[str]) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Comando falhou: {' '.join(cmd)}\n{result.stderr}")
