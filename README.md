# Fusion Base

Pipeline de injeção automática de camada de telemetria em AAB/APK.

Organizado em **Clean Architecture** para facilitar evolução (novos injetores, ofuscação, bloqueio, suporte a mais frameworks etc.).

## Arquitetura

```
src/fusionbase/
├── domain/            # Entidades, Value Objects e Ports (interfaces)
│   ├── __init__.py    # InjectionMapping, BuildRequest, BuildResult...
│   └── ports.py
├── application/       # Casos de uso
│   └── use_cases.py   # ProtectAppUseCase
├── infrastructure/    # Implementações concretas
│   ├── apktool_unpacker.py
│   ├── manifest_mapper.py
 # Mapeamento automático
│   ├── smali_injector.py
│   ├── apktool_repackager.py
│   └── apksigner.py
└── interfaces/        # Entrada (CLI)
    └── cli.py         # Composition Root + argparse
```

### Regras de dependência

- `domain` não depende de nada externo
- `application` depende apenas de `domain`
- `infrastructure` implementa os ports do `domain`
- `interfaces` compõe tudo (Composition Root)

## Instalação

```bash
cd fusion-base
pip install -e .
```

## Uso

```bash
fusion-base run \
  --input app-release.aab \
  --output app-protected.aab \
  --elastic-url https://elastic.example.com/telemetry \
  --keystore release.jks \
  --ks-pass env:KEYSTORE_PASSWORD \
  --key-alias upload
```

## Pré-requisitos

- Python 3.9+
- `apktool`
- `bundletool` (para AAB)
- `apksigner` (Android SDK build-tools)

## Evolução futura

Pontos naturais de extensão:

| Necessidade              | Onde estender                          |
|--------------------------|----------------------------------------|
| Novo tipo de injeção     | Novo `InjectorPort` + implementação    |
| Ofuscação                | Novo passo no `ProtectAppUseCase`      |
| Envio real ao Elastic    | Substituir stub em `SmaliInjector`     |
| Suporte a mais frameworks| Regras em `ManifestInjectionMapper`    |
| API HTTP                 | Novo adapter em `interfaces/`          |
| Bloqueio                 | Nova política no domínio + injector    |

## Limitações atuais (MVP)

- Telemetria só faz `Log.i` (stub)
- Injeção principal apenas em `Application.onCreate`
- Sem ofuscação ainda
- Sem testes automatizados de instalação
