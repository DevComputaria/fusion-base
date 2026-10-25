"""Testes de propriedade (Hypothesis)"""
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from fusionbase.domain import (
    AppType,
    InjectionMapping,
    InjectionPoint,
    InjectionType,
)
from fusionbase.infrastructure.manifest_mapper import ManifestInjectionMapper


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

class_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.",
    min_size=3,
    max_size=60,
).filter(lambda s: s[0].isalpha() and ".." not in s and not s.endswith("."))

injection_types = st.sampled_from(list(InjectionType))
app_types = st.sampled_from(list(AppType))
confidences = st.sampled_from(["high", "medium", "low"])


@st.composite
def injection_points(draw):
    return InjectionPoint(
        type=draw(injection_types),
        class_name=draw(st.one_of(st.none(), class_names)),
        method=draw(st.sampled_from(["onCreate", "onStart", "init"])),
    )


@st.composite
def mappings(draw):
    return InjectionMapping(
        package=draw(class_names),
        app_type=draw(app_types),
        primary=draw(injection_points()),
        fallback=draw(injection_points()),
        confidence=draw(confidences),
        application_class=draw(st.one_of(st.none(), class_names)),
        launcher_activity=draw(st.one_of(st.none(), class_names)),
        notes=draw(st.lists(st.text(min_size=0, max_size=40), max_size=5)),
    )


# ---------------------------------------------------------------------------
# Propriedades do domínio
# ---------------------------------------------------------------------------

class TestMappingProperties:
    @given(mappings())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_to_dict_roundtrip_keys(self, mapping: InjectionMapping):
        """to_dict sempre produz as chaves esperadas e valores coerentes."""
        d = mapping.to_dict()

        assert d["package"] == mapping.package
        assert d["app_type"] == mapping.app_type.value
        assert d["confidence"] == mapping.confidence
        assert d["injection"]["primary"]["type"] == mapping.primary.type.value
        assert d["injection"]["fallback"]["type"] == mapping.fallback.type.value
        assert isinstance(d["notes"], list)

    @given(mappings())
    def test_primary_and_fallback_are_different_objects(self, mapping: InjectionMapping):
        """Primary e fallback são instâncias independentes."""
        assert mapping.primary is not mapping.fallback

    @given(injection_points())
    def test_injection_point_type_is_enum(self, point: InjectionPoint):
        assert isinstance(point.type, InjectionType)


# ---------------------------------------------------------------------------
# Propriedades do mapper (manifest → mapping)
# ---------------------------------------------------------------------------

class TestMapperProperties:
    @given(
        package=class_names,
        app_class=st.one_of(st.none(), class_names),
        has_flutter=st.booleans(),
    )
    @settings(
        max_examples=50,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    )
    def test_mapper_always_returns_valid_mapping(self, tmp_path, package, app_class, has_flutter):
        """Qualquer manifest bem formado produz um InjectionMapping válido."""
        # Usa subdiretório único por exemplo para evitar colisão
        example_dir = tmp_path / f"ex_{hash((package, app_class, has_flutter)) & 0xffffffff}"
        example_dir.mkdir(parents=True, exist_ok=True)

        app_attr = f'android:name="{app_class}"' if app_class else ""
        manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<manifest package="{package}" xmlns:android="http://schemas.android.com/apk/res/android">
    <application {app_attr}>
        <activity android:name="com.example.MainActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>'''
        (example_dir / "AndroidManifest.xml").write_text(manifest)

        if has_flutter:
            lib = example_dir / "lib" / "arm64-v8a"
            lib.mkdir(parents=True, exist_ok=True)
            (lib / "libflutter.so").write_bytes(b"\x00")

        mapper = ManifestInjectionMapper()
        result = mapper.map(example_dir)

        # Propriedades que sempre devem valer
        assert isinstance(result, InjectionMapping)
        assert result.package == package
        assert result.confidence in ("high", "medium", "low")
        assert isinstance(result.primary.type, InjectionType)
        assert isinstance(result.fallback.type, InjectionType)

        if has_flutter:
            assert result.app_type == AppType.FLUTTER
        else:
            assert result.app_type == AppType.NATIVE

        if app_class:
            assert result.primary.type == InjectionType.APPLICATION_ONCREATE
            assert result.primary.class_name == app_class
            assert result.confidence == "high"
