"""Caso de uso principal: proteger um app"""
import shutil
import tempfile
from pathlib import Path

from fusionbase.domain import BuildRequest, BuildResult
from fusionbase.domain.ports import (
    BinaryUnpacker,
    InjectionMapperPort,
    InjectorPort,
    Repackager,
    Signer,
)


class ProtectAppUseCase:
    def __init__(
        self,
        unpacker: BinaryUnpacker,
        mapper: InjectionMapperPort,
        injector: InjectorPort,
        repackager: Repackager,
        signer: Signer,
    ):
        self.unpacker = unpacker
        self.mapper = mapper
        self.injector = injector
        self.repackager = repackager
        self.signer = signer

    def execute(self, request: BuildRequest) -> BuildResult:
        workdir = Path(tempfile.mkdtemp(prefix="fusionbase_"))
        try:
            input_path = Path(request.input_path).resolve()
            if not input_path.exists():
                return BuildResult(
                    output_path="",
                    mapping=None,  # type: ignore
                    success=False,
                    message=f"Arquivo não encontrado: {input_path}",
                )

            unpacked = workdir / "unpacked"
            unpacked.mkdir(parents=True)

            # 1. Unpack
            self.unpacker.unpack(input_path, unpacked)

            # 2. Map
            mapping = self.mapper.map(unpacked)

            # 3. Inject
            self.injector.inject(unpacked, mapping, request.elastic_url)

            # 4. Repackage
            unsigned = workdir / "unsigned.apk"
            self.repackager.repackage(unpacked, unsigned)

            # 5. Sign
            output = Path(request.output_path).resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            self.signer.sign(
                unsigned,
                output,
                request.keystore_path,
                request.keystore_password,
                request.key_alias,
            )

            # Persiste mapping
            mapping_path = output.with_suffix(".mapping.json")
            mapping_path.write_text(
                __import__("json").dumps(mapping.to_dict(), indent=2)
            )

            return BuildResult(
                output_path=str(output),
                mapping=mapping,
                success=True,
                message="Proteção aplicada com sucesso",
            )
        except Exception as e:
            return BuildResult(
                output_path="",
                mapping=None,  # type: ignore
                success=False,
                message=str(e),
            )
        finally:
            if not request.keep_workdir:
                shutil.rmtree(workdir, ignore_errors=True)
