"""Integração do injetor com montagem real via Apktool."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from fusionbase.domain import (
    AppType,
    InjectionMapping,
    InjectionPoint,
    InjectionStatus,
    InjectionType,
)
from fusionbase.infrastructure.smali_injector import SmaliInjector


def _mapping() -> InjectionMapping:
    return InjectionMapping(
        package="com.example.app",
        app_type=AppType.NATIVE,
        primary=InjectionPoint(
            type=InjectionType.APPLICATION_ONCREATE,
            class_name="com.example.app.MainApplication",
        ),
        fallback=InjectionPoint(type=InjectionType.CONTENT_PROVIDER),
        confidence="high",
        application_class="com.example.app.MainApplication",
    )


def _write_decoded_apk(root: Path, include_oncreate: bool = True) -> Path:
    root.mkdir()
    (root / "apktool.yml").write_text(
        """version: 3.0.3
apkFileName: fixture.apk
isFrameworkApk: false
usesFramework:
  ids:
  - 1
sdkInfo:
  minSdkVersion: 21
  targetSdkVersion: 35
packageInfo:
  forcedPackageId: 127
versionInfo:
  versionCode: 1
  versionName: '1.0'
resourcesAreCompressed: false
sharedLibrary: false
sparseResources: false
unknownFiles: {}
doNotCompress: []
"""
    )
    (root / "AndroidManifest.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.app"
    android:versionCode="1"
    android:versionName="1.0">
    <uses-sdk android:minSdkVersion="21" android:targetSdkVersion="35" />
    <application android:name="com.example.app.MainApplication" />
</manifest>
"""
    )
    app_dir = root / "smali_classes2" / "com" / "example" / "app"
    app_dir.mkdir(parents=True)
    app = app_dir / "MainApplication.smali"
    oncreate = ""
    if include_oncreate:
        oncreate = """
.method public onCreate()V
    .locals 0
    invoke-super {p0}, Landroid/app/Application;->onCreate()V
    return-void
.end method
"""
    app.write_text(
        """.class public Lcom/example/app/MainApplication;
.super Landroid/app/Application;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Application;-><init>()V
    return-void
.end method
"""
        + oncreate
    )
    primary_dir = root / "smali" / "com" / "example" / "app"
    primary_dir.mkdir(parents=True)
    (primary_dir / "Primary.smali").write_text(
        """.class public Lcom/example/app/Primary;
.super Ljava/lang/Object;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method
"""
    )
    return app


def _apktool_command() -> list[str] | None:
    jar = os.environ.get("APKTOOL_JAR")
    if jar:
        return ["java", "-jar", jar]
    executable = shutil.which("apktool")
    return [executable] if executable else None


@pytest.mark.integration
def test_injected_multidex_smali_rebuilds_with_apktool(tmp_path):
    apktool = _apktool_command()
    if apktool is None:
        pytest.skip("Apktool não está instalado")

    decoded = tmp_path / "decoded"
    app = _write_decoded_apk(decoded)
    result = SmaliInjector().inject(
        decoded,
        _mapping(),
        "https://elastic.example.com",
    )
    output = tmp_path / "rebuilt.apk"
    framework = tmp_path / "framework"
    framework.mkdir()

    completed = subprocess.run(
        [
            *apktool,
            "b",
            "--frame-path",
            str(framework),
            str(decoded),
            "-o",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.status == InjectionStatus.APPLIED
    assert app.read_text().index(".locals 0") < app.read_text().index(
        "FusionBaseTelemetry"
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert output.is_file()
    assert output.stat().st_size > 0

    verified = tmp_path / "verified"
    verification = subprocess.run(
        [
            *apktool,
            "decode",
            "--force",
            "--frame-path",
            str(framework),
            str(output),
            "--output",
            str(verified),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verification.returncode == 0, verification.stdout + verification.stderr
    rebuilt_application = (
        verified
        / "smali_classes2"
        / "com"
        / "example"
        / "app"
        / "MainApplication.smali"
    ).read_text()
    assert "Lcom/fusionbase/Telemetry;->start()V" in rebuilt_application
    assert (
        verified
        / "smali_classes2"
        / "com"
        / "fusionbase"
        / "Telemetry.smali"
    ).is_file()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("class", InjectionStatus.CLASS_NOT_FOUND),
        ("method", InjectionStatus.METHOD_NOT_FOUND),
    ],
)
def test_missing_required_target_returns_failure(tmp_path, target, expected):
    decoded = tmp_path / "decoded"
    if target == "class":
        decoded.mkdir()
        (decoded / "smali").mkdir()
    else:
        _write_decoded_apk(decoded, include_oncreate=False)

    result = SmaliInjector().inject(
        decoded,
        _mapping(),
        "https://elastic.example.com",
    )

    assert result.status == expected
    assert result.successful is False
    assert not (tmp_path / "rebuilt.apk").exists()
