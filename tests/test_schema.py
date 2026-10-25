"""Validação de schema do InjectionMapping.to_dict()"""
import json
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck
from jsonschema import validate, ValidationError, Draft202012Validator

from fusionbase.domain import InjectionMapping
from tests.test_properties import mappings


# Schema oficial do mapping.json
MAPPING_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["package", "app_type", "injection", "confidence", "notes"],
    "additionalProperties": False,
    "properties": {
        "package": {"type": "string", "minLength": 1},
        "app_type": {
            "type": "string",
            "enum": ["flutter", "native", "react_native", "unknown"],
        },
        "application_class": {"type": ["string", "null"]},
        "launcher_activity": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "injection": {
            "type": "object",
            "required": ["primary", "fallback"],
            "additionalProperties": False,
            "properties": {
                "primary": {"$ref": "#/$defs/injection_point"},
                "fallback": {"$ref": "#/$defs/injection_point"},
            },
        },
    },
    "$defs": {
        "injection_point": {
            "type": "object",
            "required": ["type"],
            "additionalProperties": False,
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [
                        "application_oncreate",
                        "content_provider",
                        "activity_oncreate",
                        "native_so",
                    ],
                },
                "class": {"type": ["string", "null"]},
                "method": {"type": "string"},
            },
        }
    },
}


class TestSchemaValidation:
    def test_schema_itself_is_valid(self):
        """O schema é um JSON Schema válido."""
        Draft202012Validator.check_schema(MAPPING_SCHEMA)

    @given(mappings())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_to_dict_always_matches_schema(self, mapping: InjectionMapping):
        """Qualquer InjectionMapping.to_dict() valida contra o schema."""
        data = mapping.to_dict()
        # Não deve lançar
        validate(instance=data, schema=MAPPING_SCHEMA)

    def test_example_valid_payload(self):
        """Payload de exemplo conhecido passa."""
        payload = {
            "package": "com.example.app",
            "app_type": "flutter",
            "application_class": "com.example.MainApplication",
            "launcher_activity": "com.example.MainActivity",
            "confidence": "high",
            "notes": ["Flutter detectado"],
            "injection": {
                "primary": {
                    "type": "application_oncreate",
                    "class": "com.example.MainApplication",
                    "method": "onCreate",
                },
                "fallback": {
                    "type": "content_provider",
                    "class": "com.fusionbase.TelemetryProvider",
                },
            },
        }
        validate(instance=payload, schema=MAPPING_SCHEMA)

    def test_invalid_app_type_rejected(self):
        """app_type fora do enum é rejeitado."""
        payload = {
            "package": "com.example",
            "app_type": "invalid_framework",
            "confidence": "high",
            "notes": [],
            "injection": {
                "primary": {"type": "application_oncreate"},
                "fallback": {"type": "content_provider"},
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=payload, schema=MAPPING_SCHEMA)

    def test_missing_required_field_rejected(self):
        """Campo obrigatório ausente é rejeitado."""
        payload = {
            "package": "com.example",
            "app_type": "native",
            # confidence ausente
            "notes": [],
            "injection": {
                "primary": {"type": "native_so"},
                "fallback": {"type": "content_provider"},
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=payload, schema=MAPPING_SCHEMA)
