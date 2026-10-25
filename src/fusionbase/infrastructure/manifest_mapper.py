"""Mapper baseado em AndroidManifest + detecção de Flutter"""
from pathlib import Path

from defusedxml import ElementTree as ET

from fusionbase.domain import (
    AppType,
    InjectionMapping,
    InjectionPoint,
    InjectionType,
)


class ManifestInjectionMapper:
    def map(self, unpacked_dir: Path) -> InjectionMapping:
        manifest = unpacked_dir / "AndroidManifest.xml"
        tree = ET.parse(manifest)
        root = tree.getroot()

        android_ns = "{http://schemas.android.com/apk/res/android}"

        app_elem = root.find("application")
        app_name = None
        if app_elem is not None:
            app_name = app_elem.get(f"{android_ns}name")

        package = root.get("package", "unknown")

        # Launcher
        launcher = None
        for act in root.findall(".//activity"):
            for intent in act.findall("intent-filter"):
                actions = [
                    a.get(f"{android_ns}name")
                    for a in intent.findall("action")
                ]
                cats = [
                    c.get(f"{android_ns}name")
                    for c in intent.findall("category")
                ]
                if (
                    "android.intent.action.MAIN" in actions
                    and "android.intent.category.LAUNCHER" in cats
                ):
                    launcher = act.get(f"{android_ns}name")
                    break

        is_flutter = self._detect_flutter(unpacked_dir)
        app_type = AppType.FLUTTER if is_flutter else AppType.NATIVE

        # Decisão de ponto
        if app_name:
            primary = InjectionPoint(
                type=InjectionType.APPLICATION_ONCREATE,
                class_name=app_name,
            )
            confidence = "high"
        elif launcher:
            primary = InjectionPoint(
                type=InjectionType.ACTIVITY_ONCREATE,
                class_name=launcher,
            )
            confidence = "medium"
        else:
            primary = InjectionPoint(type=InjectionType.NATIVE_SO)
            confidence = "low"

        fallback = InjectionPoint(
            type=InjectionType.CONTENT_PROVIDER,
            class_name="com.fusionbase.TelemetryProvider",
        )

        return InjectionMapping(
            package=package,
            app_type=app_type,
            primary=primary,
            fallback=fallback,
            confidence=confidence,
            application_class=app_name,
            launcher_activity=launcher,
            notes=["Flutter detectado"] if is_flutter else [],
        )

    def _detect_flutter(self, unpacked: Path) -> bool:
        lib = unpacked / "lib"
        if lib.exists() and any(lib.rglob("libflutter.so")):
            return True
        for smali in unpacked.rglob("*.smali"):
            try:
                if "io/flutter" in smali.read_text(errors="ignore"):
                    return True
            except Exception:
                continue
        return False
