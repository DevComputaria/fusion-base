"""Injector via modificação de smali"""
from pathlib import Path

from fusionbase.domain import InjectionMapping, InjectionType


class SmaliInjector:
    def inject(self, unpacked_dir: Path, mapping: InjectionMapping, elastic_url: str) -> None:
        self._write_telemetry_class(unpacked_dir, elastic_url)

        if mapping.primary.type == InjectionType.APPLICATION_ONCREATE and mapping.primary.class_name:
            self._inject_oncreate(unpacked_dir, mapping.primary.class_name)
        else:
            # MVP: apenas garante que a classe existe
            pass

    def _class_to_path(self, unpacked: Path, class_name: str) -> Path | None:
        rel = class_name.replace(".", "/") + ".smali"
        for smali_dir in unpacked.glob("smali*"):
            candidate = smali_dir / rel
            if candidate.exists():
                return candidate
        return None

    def _inject_oncreate(self, unpacked: Path, class_name: str) -> None:
        path = self._class_to_path(unpacked, class_name)
        if not path:
            return

        text = path.read_text()
        if "FusionBaseTelemetry" in text:
            return

        needle_public = ".method public onCreate()V"
        needle_protected = ".method protected onCreate()V"
        injection = (
            "\n    # FusionBaseTelemetry\n"
            "    invoke-static {}, Lcom/fusionbase/Telemetry;->start()V\n"
        )

        if needle_public in text:
            text = text.replace(needle_public, needle_public + injection, 1)
        elif needle_protected in text:
            text = text.replace(needle_protected, needle_protected + injection, 1)
        else:
            return

        path.write_text(text)

    def _write_telemetry_class(self, unpacked: Path, elastic_url: str) -> None:
        dest = unpacked / "smali" / "com" / "fusionbase"
        dest.mkdir(parents=True, exist_ok=True)
        smali = dest / "Telemetry.smali"
        smali.write_text(f'''# Fusion Base Telemetry
.class public Lcom/fusionbase/Telemetry;
.super Ljava/lang/Object;

.method public static start()V
    .locals 2
    const-string v0, "FusionBase"
    const-string v1, "Telemetry started -> {elastic_url}"
    invoke-static {{v0, v1}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method
''')
