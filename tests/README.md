## Validação de schema

```bash
pytest tests/test_schema.py -v
```

Garante que todo `InjectionMapping.to_dict()`:

- Segue o JSON Schema definido
- Rejeita `app_type` inválido
- Rejeita campos obrigatórios ausentes
- É estável sob geração aleatória (Hypothesis)

## Injeção Smali

```bash
pytest tests/test_fusionbase.py -v
```

Os testes unitários cobrem inserção após `.locals` e `.registers`, múltiplos dex,
idempotência, classe/método ausente e interrupção *fail-closed* do pipeline.

## Integração com Apktool

```bash
APKTOOL_JAR=/caminho/apktool_3.0.3.jar \
  pytest tests/test_smali_integration.py -m integration -v
```

O teste remonta uma fixture APK multidex após a injeção e cobre resultados
explícitos para classe e método ausentes. Ele comprova a montagem Smali, mas não
instala, assina ou executa o APK em dispositivo. O CI fixa o Apktool 3.0.3 pelo
SHA-256 e publica `coverage.xml`, `test-results.xml` e este documento no artefato
`test-evidence`.
