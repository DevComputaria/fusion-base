"""Interfaces - CLI"""
import argparse
import os
import sys

from fusionbase.application.use_cases import ProtectAppUseCase
from fusionbase.domain import BuildRequest
from fusionbase.infrastructure import (
    ApkSigner,
    ApktoolRepackager,
    ApktoolUnpacker,
    ManifestInjectionMapper,
    SmaliInjector,
)


def build_use_case() -> ProtectAppUseCase:
    """Composition Root"""
    return ProtectAppUseCase(
        unpacker=ApktoolUnpacker(),
        mapper=ManifestInjectionMapper(),
        injector=SmaliInjector(),
        repackager=ApktoolRepackager(),
        signer=ApkSigner(),
    )


def main():
    parser = argparse.ArgumentParser(prog="fusion-base", description="Fusion Base")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Protege um AAB/APK")
    run_p.add_argument("--input", required=True)
    run_p.add_argument("--output", required=True)
    run_p.add_argument("--elastic-url", required=True)
    run_p.add_argument("--keystore", required=True)
    run_p.add_argument("--ks-pass", required=True, help="Senha ou env:VAR")
    run_p.add_argument("--key-alias", default=None)
    run_p.add_argument("--keep-workdir", action="store_true")

    args = parser.parse_args()

    if args.command == "run":
        password = args.ks_pass
        if password.startswith("env:"):
            password = os.environ.get(password[4:], "")

        request = BuildRequest(
            input_path=args.input,
            output_path=args.output,
            elastic_url=args.elastic_url,
            keystore_path=args.keystore,
            keystore_password=password,
            key_alias=args.key_alias,
            keep_workdir=args.keep_workdir,
        )

        use_case = build_use_case()
        result = use_case.execute(request)

        if result.success:
            print(f"[ok] {result.message}")
            print(f"[ok] Output: {result.output_path}")
            print(f"[ok] Mapping: {result.output_path}.mapping.json")
            sys.exit(0)
        else:
            print(f"[error] {result.message}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
