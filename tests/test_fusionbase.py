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
    InjectionResult,
    InjectionStatus,
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
        injector.inject.return_value = InjectionResult(
            status=InjectionStatus.APPLIED,
        )
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

    def test_injection_failure_stops_pipeline(self, tmp_path, sample_mapping):
        unpacker = MagicMock()
        mapper = MagicMock()
        mapper.map.return_value = sample_mapping
        injector = MagicMock()
        injector.inject.return_value = InjectionResult(
            status=InjectionStatus.CLASS_NOT_FOUND,
            class_name="com.example.app.MainApplication",
            method="onCreate",
            message="Classe Smali não encontrada",
        )
        repackager = MagicMock()
        signer = MagicMock()
        use_case = ProtectAppUseCase(
            unpacker,
            mapper,
            injector,
            repackager,
            signer,
        )
        input_file = tmp_path / "app.apk"
        input_file.write_text("fake")

        result = use_case.execute(
            BuildRequest(
                input_path=str(input_file),
                output_path=str(tmp_path / "out.apk"),
                elastic_url="https://elastic.example.com",
                keystore_path="key.jks",
                keystore_password="secret",
            )
        )

        assert result.success is False
        assert "Injeção obrigatória falhou" in result.message
        repackager.repackage.assert_not_called()
        signer.sign.assert_not_called()

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
    @staticmethod
    def _write_application(
        root,
        smali_dir="smali",
        body="    .locals 0\n    return-void\n",
    ):
        app_dir = root / smali_dir / "com" / "example" / "app"
        app_dir.mkdir(parents=True)
        app_smali = app_dir / "MainApplication.smali"
        app_smali.write_text(
            ".class public Lcom/example/app/MainApplication;\n"
            ".super Landroid/app/Application;\n\n"
            ".method public onCreate()V\n"
            f"{body}"
            ".end method\n"
        )
        return app_smali

    def test_writes_telemetry_class(self, tmp_path, sample_mapping):
        self._write_application(tmp_path)
        injector = SmaliInjector()
        result = injector.inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        telemetry = tmp_path / "smali" / "com" / "fusionbase" / "Telemetry.smali"
        assert result.status == InjectionStatus.APPLIED
        assert telemetry.exists()
        content = telemetry.read_text()
        assert "Lcom/fusionbase/Telemetry;" in content
        assert "elastic.example.com" in content

    def test_injects_into_oncreate(self, tmp_path, sample_mapping):
        app_smali = self._write_application(tmp_path)

        injector = SmaliInjector()
        result = injector.inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        content = app_smali.read_text()
        assert result.status == InjectionStatus.APPLIED
        assert "FusionBaseTelemetry" in content
        assert "Lcom/fusionbase/Telemetry;->start()V" in content
        assert content.index(".locals 0") < content.index("FusionBaseTelemetry")

    def test_injects_after_registers_directive(self, tmp_path, sample_mapping):
        app_smali = self._write_application(
            tmp_path,
            body="    .registers 1\n    return-void\n",
        )

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        content = app_smali.read_text()
        assert result.status == InjectionStatus.APPLIED
        assert content.index(".registers 1") < content.index("FusionBaseTelemetry")

    def test_resolves_application_in_secondary_dex(self, tmp_path, sample_mapping):
        app_smali = self._write_application(tmp_path, smali_dir="smali_classes3")

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert result.status == InjectionStatus.APPLIED
        assert result.target_path == (
            "smali_classes3/com/example/app/MainApplication.smali"
        )
        assert "FusionBaseTelemetry" in app_smali.read_text()
        assert (
            tmp_path
            / "smali_classes3"
            / "com"
            / "fusionbase"
            / "Telemetry.smali"
        ).exists()

    def test_missing_class_returns_explicit_failure(self, tmp_path, sample_mapping):
        (tmp_path / "smali").mkdir()

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert result.status == InjectionStatus.CLASS_NOT_FOUND
        assert result.successful is False
        assert not (tmp_path / "smali" / "com" / "fusionbase").exists()

    def test_missing_method_returns_explicit_failure(self, tmp_path, sample_mapping):
        app_smali = self._write_application(tmp_path)
        app_smali.write_text(
            ".class public Lcom/example/app/MainApplication;\n"
            ".super Landroid/app/Application;\n"
        )

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert result.status == InjectionStatus.METHOD_NOT_FOUND
        assert result.successful is False

    def test_method_without_register_directive_returns_failure(
        self,
        tmp_path,
        sample_mapping,
    ):
        self._write_application(tmp_path, body="    return-void\n")

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert result.status == InjectionStatus.INVALID_METHOD
        assert result.successful is False

    def test_unterminated_method_returns_failure(self, tmp_path, sample_mapping):
        app_smali = self._write_application(tmp_path)
        app_smali.write_text(app_smali.read_text().replace(".end method\n", ""))

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert result.status == InjectionStatus.INVALID_METHOD
        assert result.successful is False

    def test_unsupported_injection_point_returns_failure(
        self,
        tmp_path,
        sample_mapping,
    ):
        sample_mapping.primary = InjectionPoint(
            type=InjectionType.CONTENT_PROVIDER,
            class_name="com.fusionbase.TelemetryProvider",
        )

        result = SmaliInjector().inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert result.status == InjectionStatus.UNSUPPORTED_MAPPING
        assert result.successful is False

    def test_injection_is_idempotent(self, tmp_path, sample_mapping):
        app_smali = self._write_application(tmp_path)
        injector = SmaliInjector()

        first = injector.inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )
        second = injector.inject(
            tmp_path,
            sample_mapping,
            "https://elastic.example.com",
        )

        assert first.status == InjectionStatus.APPLIED
        assert second.status == InjectionStatus.ALREADY_APPLIED
        assert second.successful is True
        assert app_smali.read_text().count("FusionBaseTelemetry") == 1


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
