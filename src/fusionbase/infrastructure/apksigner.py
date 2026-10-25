"""Signer usando apksigner"""
import os
import subprocess
from pathlib import Path


class ApkSigner:
    def sign(
        self,
        unsigned_apk: Path,
        output_path: Path,
        keystore: str,
        password: str,
        alias: str | None,
    ) -> None:
        if password.startswith("env:"):
            password = os.environ.get(password[4:], "")

        cmd = [
            "apksigner", "sign",
            "--ks", keystore,
            "--ks-pass", f"pass:{password}",
            "--key-pass", f"pass:{password}",
            "--out", str(output_path),
            str(unsigned_apk),
        ]
        if alias:
            cmd.extend(["--ks-key-alias", alias])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"apksigner falhou:\n{result.stderr}")
