"""Domain - Ports (interfaces que a infraestrutura deve implementar)"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from fusionbase.domain import InjectionMapping, BuildRequest, BuildResult


class BinaryUnpacker(Protocol):
    def unpack(self, input_path: Path, dest: Path) -> None: ...


class InjectionMapperPort(Protocol):
    def map(self, unpacked_dir: Path) -> InjectionMapping: ...


class InjectorPort(Protocol):
    def inject(self, unpacked_dir: Path, mapping: InjectionMapping, elastic_url: str) -> None: ...


class Repackager(Protocol):
    def repackage(self, unpacked_dir: Path, output_apk: Path) -> None: ...


class Signer(Protocol):
    def sign(self, unsigned_apk: Path, output_path: Path, keystore: str, password: str, alias: str | None) -> None: ...
