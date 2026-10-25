"""Domínio - Entidades e Value Objects"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AppType(str, Enum):
    FLUTTER = "flutter"
    NATIVE = "native"
    REACT_NATIVE = "react_native"
    UNKNOWN = "unknown"


class InjectionType(str, Enum):
    APPLICATION_ONCREATE = "application_oncreate"
    CONTENT_PROVIDER = "content_provider"
    ACTIVITY_ONCREATE = "activity_oncreate"
    NATIVE_SO = "native_so"


@dataclass(frozen=True)
class InjectionPoint:
    type: InjectionType
    class_name: Optional[str] = None
    method: str = "onCreate"


@dataclass
class InjectionMapping:
    package: str
    app_type: AppType
    primary: InjectionPoint
    fallback: InjectionPoint
    confidence: str  # high | medium | low
    application_class: Optional[str] = None
    launcher_activity: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "package": self.package,
            "app_type": self.app_type.value,
            "application_class": self.application_class,
            "launcher_activity": self.launcher_activity,
            "injection": {
                "primary": {
                    "type": self.primary.type.value,
                    "class": self.primary.class_name,
                    "method": self.primary.method,
                },
                "fallback": {
                    "type": self.fallback.type.value,
                    "class": self.fallback.class_name,
                },
            },
            "confidence": self.confidence,
            "notes": self.notes,
        }


@dataclass
class BuildRequest:
    input_path: str
    output_path: str
    elastic_url: str
    keystore_path: str
    keystore_password: str
    key_alias: Optional[str] = None
    keep_workdir: bool = False


@dataclass
class BuildResult:
    output_path: str
    mapping: InjectionMapping
    success: bool
    message: str = ""
