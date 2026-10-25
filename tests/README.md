## Validação de schema

```bash
pytest tests/test_schema.py -v
```

Garante que todo `InjectionMapping.to_dict()`:

- Segue o JSON Schema definido
- Rejeita `app_type` inválido
- Rejeita campos obrigatórios ausentes
- É estável sob geração aleatória (Hypothesis)
