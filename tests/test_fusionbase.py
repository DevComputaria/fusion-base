"""Testes unitários e de integração do Fusion Base"""
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from defusedxml.common import DefusedXmlException

from fusionbase.domain import (
    AppType,
    BuildRequest,
    InjectionMapping,
    InjectionPoint,
    InjectionType,
)
from fusionbase.application.use_cases import ProtectAppUseCase
from fusionbase.infrastructure.manifest_mapper import ManifestInjectionMapper
from fusionbase.infrastructure.smali_injector import SmaliInjector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_path():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_mapping():
    return InjectionMapping(
        package="com.example.app",
        app_type=AppType.FLUTTER,
        primary=InjectionPoint(
            type=InjectionType.APPLICATION_ONCREATE,
            class_name="com.example.app.MainApplication",
        ),
        fallback=InjectionPoint(
            type=InjectionType.CONTENT_PROVIDER,
            class_name="com.fusionbase.TelemetryProvider",
        ),
        confidence="high",
        application_class="com.example.app.MainApplication",
    )


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

class TestDomain:
    def test_injection_mapping_to_dict(self, sample_mapping):
        d = sample_mapping.to_dict()
        assert d["package"] == "com.example.app"
        assert d["app_type"] == "flutter"
        assert d["injection"]["primary"]["type"] == "application_oncreate"
        assert d["confidence"] == "high"

    def test_build_request_creation(self):
        req = BuildRequest(
            input_path="app.aab",
            output_path="out.aab",
            elastic_url="https://elastic.example.com",
            keystore_path="key.jks",
            keystore_password="secret",
        )
        assert req.input_path == "app.aab"
        assert req.keep_workdir is False


# ---------------------------------------------------------------------------
# Application - Use Case (com mocks)
# ---------------------------------------------------------------------------

class TestProtectAppUseCase:
    def test_success_flow(self, tmp_path, sample_mapping):
        # Mocks
        unpacker = MagicMock()
        mapper = MagicMock()
        mapper.map.return_value = sample_mapping
        injector = MagicMock()
        repackager = MagicMock()
        signer = MagicMock()

        use_case = ProtectAppUseCase(unpacker, mapper, injector, repackager, signer)

        input_file = tmp_path / "app.apk"
        input_file.write_text("fake")
        output_file = tmp_path / "out.apk"

        request = BuildRequest(
            input_path=str(input_file),
            output_path=str(output_file),
            elastic_url="https://elastic.example.com",
            keystore_path="key.jks",
            keystore_password="secret",
        )

        result = use_case.execute(request)

        assert result.success is True
        assert result.mapping == sample_mapping
        unpacker.unpack.assert_called_once()
        mapper.map.assert_called_once()
        injector.inject.assert_called_once()
        repackager.repackage.assert_called_once()
        signer.sign.assert_called_once()

    def test_missing_input_file(self, tmp_path):
        use_case = ProtectAppUseCase(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )
        request = BuildRequest(
            input_path=str(tmp_path / "nao_existe.apk"),
            output_path=str(tmp_path / "out.apk"),
            elastic_url="https://elastic.example.com",
            keystore_path="key.jks",
            keystore_password="secret",
        )
        result = use_case.execute(request)
        assert result.success is False
        assert "não encontrado" in result.message.lower()


# ---------------------------------------------------------------------------
# Infrastructure - ManifestInjectionMapper
# ---------------------------------------------------------------------------

class TestManifestInjectionMapper:
    def test_rejects_xml_entities(self, tmp_path):
        manifest = tmp_path / "AndroidManifest.xml"
        manifest.write_text('''<?xml version="1.0"?>
<!DOCTYPE manifest [
    <!ENTITY payload SYSTEM "file:///etc/passwd">
]>
<manifest package="&payload;"/>
''')

        mapper = ManifestInjectionMapper()

        with pytest.raises(DefusedXmlException):
            mapper.map(tmp_path)

    def test_maps_application_oncreate(self, tmp_path):
        manifest = tmp_path / "AndroidManifest.xml"
        manifest.write_text('''<?xml version="1.0" encoding="utf-8"?>
<manifest package="com.example.app" xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:name="com.example.app.MainApplication">
        <activity android:name="com.example.app.MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>''')

        mapper = ManifestInjectionMapper()
        mapping = mapper.map(tmp_path)

        assert mapping.package == "com.example.app"
        assert mapping.primary.type == InjectionType.APPLICATION_ONCREATE
        assert mapping.primary.class_name == "com.example.app.MainApplication"
        assert mapping.confidence == "high"
        assert mapping.app_type == AppType.NATIVE

    def test_detects_flutter(self, tmp_path):
        # Cria estrutura mínima de Flutter
        lib_dir = tmp_path / "lib" / "arm64-v8a"
        lib_dir.mkdir(parents=True)
        (lib_dir / "libflutter.so").write_text("fake")

        manifest = tmp_path / "AndroidManifest.xml"
        manifest.write_text('''<?xml version="1.0" encoding="utf-8"?>
<manifest package="com.flutter.app" xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:name="io.flutter.app.FlutterApplication"/>
</manifest>''')

        mapper = ManifestInjectionMapper()
        mapping = mapper.map(tmp_path)

        assert mapping.app_type == AppType.FLUTTER
        assert "Flutter detectado" in mapping.notes


# ---------------------------------------------------------------------------
# Infrastructure - SmaliInjector
# ---------------------------------------------------------------------------

class TestSmaliInjector:
    def test_writes_telemetry_class(self, tmp_path, sample_mapping):
        injector = SmaliInjector()
        injector.inject(tmp_path, sample_mapping, "https://elastic.example.com")

        telemetry = tmp_path / "smali" / "com" / "fusionbase" / "Telemetry.smali"
        assert telemetry.exists()
        content = telemetry.read_text()
        assert "Lcom/fusionbase/Telemetry;" in content
        assert "elastic.example.com" in content

    def test_injects_into_oncreate(self, tmp_path, sample_mapping):
        # Cria smali falso da Application
        smali_dir = tmp_path / "smali" / "com" / "example" / "app"
        smali_dir.mkdir(parents=True)
        app_smali = smali_dir / "MainApplication.smali"
        app_smali.write_text('''.class public Lcom/example/app/MainApplication;
.super Landroid/app/Application;

.method public onCreate()V
    .locals 0
    return-void
.end method
''')

        injector = SmaliInjector()
        injector.inject(tmp_path, sample_mapping, "https://elastic.example.com")

        content = app_smali.read_text()
        assert "FusionBaseTelemetry" in content
        assert "Lcom/fusionbase/Telemetry;->start()V" in content


# ---------------------------------------------------------------------------
# Integração (marcados, exigem ferramentas externas)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIntegration:
    @pytest.mark.skip(reason="Requer apktool + apksigner + APK de teste real")
    def test_full_pipeline_with_real_apk(self, tmp_path):
        """
        Teste de integração completo.
        Para habilitar:
        1. Tenha um APK de teste pequeno
        2. Remova o skip
        3. Configure keystore de teste
        """
        pass
