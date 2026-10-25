"""Injector de telemetria por modificação segura de Smali."""
import re
from pathlib import Path

from fusionbase.domain import (
    InjectionMapping,
    InjectionResult,
    InjectionStatus,
    InjectionType,
)


class SmaliInjector:
    _MARKER = "# FusionBaseTelemetry"
    _ONCREATE = re.compile(
        r"^\s*\.method\b[^\r\n]*\bonCreate\(\)V(?:\s*#.*)?\s*$"
    )
    _REGISTER_DIRECTIVE = re.compile(
        r"^(?P<indent>\s*)\.(?:locals|registers)\s+\d+\b"
    )

    def inject(
        self,
        unpacked_dir: Path,
        mapping: InjectionMapping,
        elastic_url: str,
    ) -> InjectionResult:
        point = mapping.primary
        if (
            point.type != InjectionType.APPLICATION_ONCREATE
            or not point.class_name
            or point.method != "onCreate"
        ):
            return InjectionResult(
                status=InjectionStatus.UNSUPPORTED_MAPPING,
                class_name=point.class_name,
                method=point.method,
                message=(
                    "O injetor Smali requer uma classe Application com "
                    "o método onCreate()V"
                ),
            )

        result, smali_root = self._inject_oncreate(
            unpacked_dir,
            point.class_name,
        )
        if result.successful and smali_root is not None:
            self._write_telemetry_class(smali_root, elastic_url)
        return result

    def _smali_roots(self, unpacked: Path) -> list[Path]:
        def dex_number(path: Path) -> int:
            if path.name == "smali":
                return 1
            match = re.fullmatch(r"smali_classes(\d+)", path.name)
            return int(match.group(1)) if match else 2**31

        roots = [
            path
            for path in unpacked.iterdir()
            if path.is_dir()
            and re.fullmatch(r"smali(?:_classes\d+)?", path.name)
        ]
        return sorted(roots, key=lambda path: (dex_number(path), path.name))

    def _class_to_path(
        self,
        unpacked: Path,
        class_name: str,
    ) -> tuple[Path, Path] | None:
        normalized = class_name.removeprefix("L").removesuffix(";")
        rel = Path(normalized.replace(".", "/") + ".smali")
        for smali_root in self._smali_roots(unpacked):
            candidate = smali_root / rel
            if candidate.is_file():
                return candidate, smali_root
        return None

    def _inject_oncreate(
        self,
        unpacked: Path,
        class_name: str,
    ) -> tuple[InjectionResult, Path | None]:
        resolved = self._class_to_path(unpacked, class_name)
        if resolved is None:
            return (
                InjectionResult(
                    status=InjectionStatus.CLASS_NOT_FOUND,
                    class_name=class_name,
                    method="onCreate",
                    message=f"Classe Smali não encontrada: {class_name}",
                ),
                None,
            )

        path, smali_root = resolved
        text = path.read_text()
        lines = text.splitlines(keepends=True)

        method_start = next(
            (index for index, line in enumerate(lines) if self._ONCREATE.match(line)),
            None,
        )
        if method_start is None:
            return (
                InjectionResult(
                    status=InjectionStatus.METHOD_NOT_FOUND,
                    class_name=class_name,
                    method="onCreate",
                    target_path=str(path.relative_to(unpacked)),
                    message=f"Método onCreate()V não encontrado em {class_name}",
                ),
                smali_root,
            )

        target_path = str(path.relative_to(unpacked))
        method_end = next(
            (
                index
                for index in range(method_start + 1, len(lines))
                if lines[index].strip() == ".end method"
            ),
            None,
        )
        if method_end is None:
            return (
                InjectionResult(
                    status=InjectionStatus.INVALID_METHOD,
                    class_name=class_name,
                    method="onCreate",
                    target_path=target_path,
                    message=(
                        "Método onCreate()V sem diretiva .end method "
                        f"em {class_name}"
                    ),
                ),
                smali_root,
            )

        if any(
            self._MARKER in line
            for line in lines[method_start + 1:method_end]
        ):
            return (
                InjectionResult(
                    status=InjectionStatus.ALREADY_APPLIED,
                    class_name=class_name,
                    method="onCreate",
                    target_path=target_path,
                    message=f"Telemetria já aplicada em {class_name}.onCreate()V",
                ),
                smali_root,
            )

        register_index = None
        register_match = None
        for index in range(method_start + 1, method_end):
            match = self._REGISTER_DIRECTIVE.match(lines[index])
            if match:
                register_index = index
                register_match = match
                break

        if register_index is None or register_match is None:
            return (
                InjectionResult(
                    status=InjectionStatus.INVALID_METHOD,
                    class_name=class_name,
                    method="onCreate",
                    target_path=target_path,
                    message=(
                        "Método onCreate()V sem diretiva .locals ou .registers "
                        f"em {class_name}"
                    ),
                ),
                smali_root,
            )

        directive = lines[register_index]
        newline = "\r\n" if directive.endswith("\r\n") else "\n"
        indent = register_match.group("indent")
        injection = [
            f"{indent}{self._MARKER}{newline}",
            (
                f"{indent}invoke-static {{}}, "
                f"Lcom/fusionbase/Telemetry;->start()V{newline}"
            ),
        ]
        lines[register_index + 1:register_index + 1] = injection
        path.write_text("".join(lines))

        return (
            InjectionResult(
                status=InjectionStatus.APPLIED,
                class_name=class_name,
                method="onCreate",
                target_path=target_path,
                message=f"Telemetria aplicada em {class_name}.onCreate()V",
            ),
            smali_root,
        )

    def _write_telemetry_class(self, smali_root: Path, elastic_url: str) -> None:
        dest = smali_root / "com" / "fusionbase"
        dest.mkdir(parents=True, exist_ok=True)
        smali = dest / "Telemetry.smali"
        content = f'''# Fusion Base Telemetry
.class public Lcom/fusionbase/Telemetry;
.super Ljava/lang/Object;

.method public static start()V
    .locals 2
    const-string v0, "FusionBase"
    const-string v1, "Telemetry started -> {elastic_url}"
    invoke-static {{v0, v1}}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method
'''
        if not smali.exists() or smali.read_text() != content:
            smali.write_text(content)
