# Fusion Base 2.0 — Roadmap de evolução para Mobile Application Protection

> **Projeto:** [DevComputaria/fusion-base](https://github.com/DevComputaria/fusion-base)  
> **Data-base:** 24 de outubro de 2026  
> **Status:** proposta arquitetural e planejamento; implementações futuras não devem ser confundidas com recursos existentes.  
> **Horizonte indicativo:** novembro de 2026 a agosto/setembro de 2027 (8–10 meses); sujeito a equipe, validação técnica, compatibilidade e revisão de licenças.  
> **Visão:** *Open Mobile Application Protection Platform*.

## 1. Visão executiva

Transformar o Fusion Base — hoje um pipeline Python de injeção de telemetria em artefatos Android — numa plataforma extensível de proteção mobile que combine:

- proteção de binários (ofuscação, transformação DEX, empacotamento e proteções nativas);
- sensores RASP e verificação de integridade em runtime;
- observabilidade e eventos de segurança sem exposição desnecessária de dados;
- atestação de aplicativo/dispositivo e avaliação de risco no backend;
- automação de testes de segurança, compatibilidade e funcionalidades;
- execução no GitHub Actions, Azure Pipelines e CLI, orientada a políticas;
- proveniência, hashes, SBOM, licenças e evidências verificáveis.

**Princípio diretor:** proteção não é sinônimo de ofuscação. Uma proteção só é considerada aplicada após uma verificação independente e testes em artefato real.

**Não objetivo inicial:** replicar as centenas de funcionalidades comerciais do Appdome ou prometer proteção iOS arbitrária, pós-assinatura e no-code. A v1.0 será focada em Android estável; iOS permanece experimental até validação específica.

## 2. Diagnóstico do repositório atual (v0.1.0)

Base lida em 24/10/2026: `README.md`, `pyproject.toml`, `src/fusionbase/domain/*`, `src/fusionbase/application/use_cases.py`, `src/fusionbase/infrastructure/*`, `src/fusionbase/interfaces/cli.py`, `.github/workflows/ci.yml` e testes.

| Camada/componente | Presença no repositório | Estado |
|---|---|---|
| Domain | `BuildRequest`, `BuildResult`, `InjectionMapping`, `InjectionPoint` e Ports | Base reutilizável |
| Application | `ProtectAppUseCase` | Pipeline sequencial rígido |
| Unpacker | Apktool e bundletool | APK e conversão AAB → APK universal |
| Mapper | AndroidManifest e detecção heurística de Flutter | Cobertura parcial; sem resolução completa de nomes |
| Injector | Modificação Smali | Telemetria demonstrativa |
| Repackager | Apktool | Saída APK |
| Signer | apksigner | Assina APK, não um AAB recompilado |
| CLI | argparse, `fusion-base run` | Entrada única |
| Testes | pytest, Hypothesis, JSON Schema | Bons testes unitários, sem prova E2E real |
| CI | GitHub Actions, Bandit, unit/property/schema tests | Integração com artefato real excluída |
| Licença do Fusion Base | MIT | Revisar obrigações de cada dependência externa |

### 2.1. Achados críticos

1. **[P0] AAB não preservado:** `ApktoolUnpacker._aab_to_universal_apk` converte AAB em APK; o fluxo seguinte recompila para `unsigned.apk` e assina APK. Informar nome de saída `.aab` não gera um AAB publicável. Dividir estratégias APK e AAB.
2. **[P0] Injeção Smali insegura para montagem:** `SmaliInjector._inject_oncreate` injeta `invoke-static` logo após `.method`, antes de `.locals`/`.registers` no exemplo coberto por teste. Corrigir sintaxe, localização e ordem, montando APK real.
3. **[P0] Falha silenciosa:** caso a classe/método não exista, o injetor pode retornar sem aplicar proteção enquanto `ProtectAppUseCase` informa sucesso. Adotar verificação *fail-closed*.
4. **[P0] Assinatura:** `ApkSigner` usa senha na forma `pass:...` em argumentos de subprocesso; extrair a senha da CLI e repassá-la não elimina exposição. Isolar chaves e segredos, assinar com mecanismo adequado por formato e verificar assinatura final.
5. **[P1] Entrada não confiável:** `elastic_url` entra como string literal Smali sem escape adequado; exige validação rigorosa e emissão segura de literais.
6. **[P1] Telemetria é stub:** `Telemetry.start()` só produz `Log.i`, sem cliente de coleta autenticado, esquema de eventos ou política de privacidade.
7. **[P0] Ausência de teste real:** `TestIntegration.test_full_pipeline_with_real_apk` está explicitamente ignorado; o workflow exclui testes de integração.
8. **[P1] CI não fixa todas as versões de ferramentas e não comprova assinatura, instalação ou comportamento em runtime.**

**Nota de rigor:** são achados de leitura de código; é preciso confirmar falhas de montagem, instalação e compatibilidade em ambiente de testes. Não há alegação de que testes E2E foram executados nesta análise.

### 2.2. Arquitetura atual

    src/fusionbase/
    ├── domain/               # entidades, value objects e portas
    ├── application/          # ProtectAppUseCase
    ├── infrastructure/       # Apktool, mapper, injector, repackager, signer
    └── interfaces/           # CLI e composition root

Regras a preservar: domain sem dependência externa; application só depende de domain; infrastructure implementa portas; interfaces compõem dependências.

## 3. Arquitetura alvo

    GitHub Actions / Azure Pipelines / CLI / API
                         |
                         v
           Protection Orchestrator
       (inspect -> plan -> execute -> verify)
                         |
          +--------------+----------------+
          |                               |
          v                               v
      Android adapters                iOS adapters
      Smali / Obfuscapk               Xcode build integration
      dpt-shell / XopProtector        O-MVLL (quando aplicável)
      CyberArmor (PoC)                runtime SDK / App Attest
      RASP / native adapters
          |                               |
          +---------------+---------------+
                          v
                Security Evaluation
          (MobSF, APKiD, JADX, Androguard,
             testes reais, Frida/Objection)
                          |
                          v
              Verified Artifact + Evidence
         (hash, assinatura, SBOM, relatório,
          política, proveniência, métricas)

    Em runtime, serviço separado:
    Mobile app -> Atestation & Telemetry API
               -> Fact Resolver -> OPA/Rego
               -> ALLOW / STEP_UP / REVIEW / DENY
               -> Auditoria / Observabilidade

### 3.1. Três planos

- **Protection Plane:** inspecionar, transformar, empacotar e assinar artefatos.
- **Validation Plane:** validar transformação, assinatura, instalação, funções e resistência a cenários de ataque definidos.
- **Trust Plane:** verificar evidências criptográficas e sinais de runtime e produzir decisões auditáveis no backend.

O core permanece um pacote Python e a execução de ferramentas é feita via adaptadores isolados. Não introduzir microserviços desnecessários no início. O Trust API é separado por ter perfil operacional e requisitos de segurança distintos.

### 3.2. Contratos do domínio planejados

| Contrato | Responsabilidade |
|---|---|
| `ArtifactInspectorPort` | Tipo APK/AAB/IPA/projeto, package, ABI, SDK, permissões, assinatura |
| `ProtectionPlannerPort` | Plano ordenado com dependências e conflitos |
| `ProtectionAdapterPort` | Aplicação de transformação por ferramenta |
| `ArtifactValidatorPort` | Formato, hash, assinatura, instalação |
| `SecurityEvaluatorPort` | Testes de resistência com evidências |
| `SigningProviderPort` | Separar assinatura do processamento de artefatos |
| `EvidencePublisherPort` | Publicar relatórios e proveniência |
| `PolicyEvaluatorPort` | Aplicar política de build/release |

Proposta de interface Python:

    from dataclasses import dataclass
    from pathlib import Path
    from typing import Protocol

    @dataclass(frozen=True)
    class ProtectionContext:
        input_path: Path
        workdir: Path
        policy_path: Path
        artifact_type: str

    @dataclass(frozen=True)
    class ProtectionResult:
        output_path: Path
        adapter_id: str
        applied: bool
        evidence_path: Path

    class ProtectionAdapter(Protocol):
        def validate(self, ctx: ProtectionContext) -> None: ...
        def apply(self, ctx: ProtectionContext) -> ProtectionResult: ...
        def verify(self, result: ProtectionResult) -> bool: ...

O `applied=True` de um adapter não substitui verificação independente. Cada adapter declara formatos aceitos, sistema operacional, nível de maturidade, versão, licença, pré-requisitos, incompatibilidades e procedimentos de rollback.

## 4. Linha do tempo e releases

| Versão | Janela indicativa (sequencial com paralelismo) | Objetivo | Gate mínimo |
|---|---|---|---|
| **v0.2 — Foundation Hardening** | Semanas 1–3 | Corrigir Smali, fluxo APK/AAB, assinatura, testes reais | APK instalável, execução confirmada e falha fechada |
| **v0.3 — Plugin Architecture** | Semanas 4–7 | Portas, planner, registry, CLI e políticas | Adapter fake + real verificáveis; schemas validados |
| **v0.4 — Telemetry Engine** | Semanas 8–11 | Sinais de runtime e gateway autenticado | Coleta confiável, sem credenciais embutidas |
| **v0.5 — Android Hardening** | Semanas 12–17 | Obfuscapk + packers de laboratório | Compatibilidade e ganhos testados |
| **v0.6 — RASP Engine** | Semanas 18–22 | Root, debug, hooking, tamper, resposta | Detectores testados e falsos positivos medidos |
| **v0.7 — Security Evaluation** | Semanas 21–25 | Avaliação estática/dinâmica automatizada | Gates de avaliação e relatórios reprodutíveis |
| **v0.8 — Identity & Trust** | Semanas 25–30 | Play Integrity, Fact Resolver, OPA/Rego | Provas validadas e decisões vinculadas à requisição |
| **v0.9 — iOS Experimental** | Semanas 28–34 | Integrações Xcode/SDK e App Attest | Build/assinatura e testes em dispositivo físico |
| **v1.0 — Android Stable** | Semanas 32–35 | Compatibilidade, docs, rollback e distribuição | Critérios de release aprovados |
| **v2.0 — Platform GA** | Semanas 36–40 | Control plane, catálogo e distribuição evoluída | Escopo multiplataforma condicionado à evidência |

O cronograma é orientativo, com fases parcialmente paralelas. Releases não devem ser anunciadas por calendário: usar os critérios de saída.

## 5. Backlog detalhado por versão

### v0.2 — Foundation Hardening (P0)

**Objetivo:** parar de produzir artefatos potencialmente inválidos ou falsamente classificados como protegidos.

- **FB-001 — Corrigir injeção Smali:** identificar e validar `onCreate`, inserir instruções após `.locals`/`.registers`, evitar duplicação, resolver classe/dex e retornar status explícito; teste com montagem real.
- **FB-002 — Manifest Mapper confiável:** classes com nomes relativos, Application padrão, fallback, Flutter, React Native, múltiplos DEX e segurança de XML; nunca afirmar que um fallback foi aplicado sem implementação.
- **FB-003 — Separar APK/AAB:** inspecionar formato de entrada, impedir mudança silenciosa, criar estratégias de saída específicas e marcar AAB unsupported até pipeline de reconstrução íntegro.
- **FB-004 — Assinatura segura:** não passar senha em argumentos, keystore de teste no CI, suporte a signer apropriado por formato, `zipalign` na ordem correta, validação criptográfica pós-build.
- **FB-005 — Sanitização e workspace:** validar parâmetros, escapar literais Smali, proteger contra archive traversal/zip bombs, limitar execução e controlar arquivos temporários e logs.
- **FB-006 — Testes E2E:** fixture APK open source ou autoral, compilação, injeção, assinatura, instalação, execução e verificação de telemetria. Remover `skip` somente quando houver infraestrutura real.
- **FB-007 — Artefatos verificáveis:** SHA-256 da entrada/saída, diff de permissões/manifest, relatório de mapping e resultado dos testes; falhar em anomalias.
- **FB-008 — CI inicial:** ferramentas pinadas, lint/type checks, Bandit, pytest/Hypothesis, integração real em runner apto, artefatos e política fail-closed.

**Gate:** a release jamais pode informar sucesso se falhou injeção obrigatória, rebuild, alinhamento, assinatura ou instalação. AAB publicável não deve ser anunciado até existir suporte completo.

### v0.3 — Extensible Protection Pipeline

- Criar contratos e registry para adaptadores versionados; health/capabilities/compatibility.
- Criar `ProtectionPlanner` determinístico com DAG, ordem, conflitos, dry-run, verificação e logs redigidos.
- Definir `ProtectionProfile` YAML/JSON Schema com profiles `mobile-standard` e `mobile-high-security`.
- Evoluir CLI para `inspect`, `plan`, `protect`, `verify`, `evaluate`, `report` e `adapters list`.
- Códigos de saída por categoria (configuração, transformador, assinatura, avaliação, política).
- Testar adapter falso, execução idempotente, incompatibilidades e desativação segura de plugins.

Exemplo de policy proposta (não implementada):

    apiVersion: fusionbase.dev/v1alpha1
    kind: ProtectionProfile
    metadata:
      name: mobile-high-security
    spec:
      platform: android
      input:
        format: apk
      protections:
        - id: telemetry
          adapter: fusionbase.telemetry
          enabled: true
        - id: obfuscation
          adapter: obfuscapk
          enabled: true
        - id: dex-packing
          adapter: dpt-shell
          enabled: false
          experimental: true
        - id: rasp
          adapter: fusionbase.rasp
          enabled: true
          sensors: [debugger, root, hooking, tampering]
      validation:
        artifactIntegrity: required
        signature: required
        installTest: required
        functionalTests: required
        securityEvaluation: required
      release:
        failOnRequiredProtectionFailure: true
        requireEvidence: true
        signingProfile: external

### v0.4 — Telemetry Engine

- Substituir `Log.i` por SDK/routine de transporte e buffer com limites, retry e backoff.
- Definir contratos versionados para `runtime.integrity.signal` e eventos de build/eval.
- Implementar gateway autenticado, com proteção anti-replay, limites, minimização de dados e encaminhamento a observabilidade.
- Evitar incorporar segredo Elastic ou tokens persistentes em APK.
- Operação com telemetria indisponível não deve quebrar a aplicação sem política explícita.
- Avaliar coleta de dispositivo e PII conforme finalidade, consentimento/base legal e políticas do produto.

Evento normalizado proposto:

    {
      "schemaVersion": "1.0",
      "eventType": "runtime.integrity.signal",
      "platform": "android",
      "application": {"packageId": "com.example.app", "version": "1.2.0"},
      "protection": {"profileId": "mobile-standard", "buildId": "build-123"},
      "signal": {"type": "debugger_detected", "observed": true, "confidence": "medium"},
      "timestamp": "2026-10-24T12:00:00Z"
    }

### v0.5 — Android Hardening

| Adapter | Ferramenta | Política inicial |
|---|---|---|
| `obfuscapk` | [Obfuscapk](https://github.com/Mobile-IoT-Security-Lab/Obfuscapk) | Primeira integração pós-build |
| `dpt-shell` | [dpt-shell](https://github.com/luoyesiqiu/dpt-shell) | Laboratório de DEX packing |
| `xop-protector` | [XopProtector](https://github.com/xopJack/XopProtector) | Laboratório VMP/packer |
| `cyber-armor` | [CyberArmor](https://github.com/VexoraWebServices/CyberArmor) | Laboratório comparativo |
| `dex2c` | [DCC](https://github.com/amimo/dcc) | PoC de tradução seletiva |
| `o-mvll` | [O-MVLL](https://github.com/open-obfuscator/o-mvll) | Build-time para código nativo elegível |

Critérios: versões pinadas, isolamento do executor, SBOM/licenças, relatório de alteração e comparação pré/pós. Não encadear packers por padrão; primeira release suporta Obfuscapk, os outros permanecem experimentais até testes A/B.

### v0.6 — RASP Engine

- Sensores: root (incluindo RootBeer como referência), debugger, hooking/Frida, emulador, integridade e tamper.
- Avaliar `android-rasp` como referência aberta; freeRASP apenas como opção híbrida após due diligence de licença.
- Evitar bloqueio local absoluto baseado em sinal fraco; classificar confiança e executar política de resposta.
- Validar sensores em versões de Android, modelos físicos, builds de depuração e ambientes corporativos.
- Garantir tolerância a erro, baixa latência e ausência de loops/crashes.

### v0.7 — Security Evaluation Framework

- Integrar [MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF), [JADX](https://github.com/skylot/jadx), [Androguard](https://github.com/androguard/androguard) e [APKiD](https://github.com/rednaga/APKiD) para avaliações estáticas e estruturais.
- Usar [Frida](https://github.com/frida/frida) e [Objection](https://github.com/sensepost/objection) em testes dinâmicos autorizados, com fixtures e ambientes controlados.
- Criar casos alinhados a OWASP MASVS/MASTG, comparando original vs protegido no mesmo cenário.
- Reportar se a proteção mitigou cenário testado ou apenas aumentou complexidade/tamanho.
- Conservar evidências e métricas por versão da ferramenta, dispositivo, OS, ABI e artefato.

### v0.8 — Identity-First e Trust Engine

- Integrar Google Play Integrity no app e validação criptográfica no backend.
- Vincular a prova ao conteúdo sensível de uma operação e à sessão; usar hash canônico, nonce/requestHash, validade temporal e controles de replay conforme API.
- Implementar `Fact Resolver` e decisão auditável OPA/Rego: `ALLOW` / `STEP_UP` / `REVIEW` / `DENY`.
- Sinais locais são evidências adicionais, não substitutos da validação do servidor.
- Exemplo de fluxo Pix: correlacionar prova do app à mesma transação e ao contexto de autorização, sem depender de um booleano enviado pelo cliente.

### v0.9 — iOS Experimental

- Adapters de integração Xcode/build, assinatura e verificação de entitlements.
- O-MVLL apenas onde toolchain e código são elegíveis.
- SDK de runtime com controles de jailbreak/debug, respeitando limitações e licenças.
- Apple App Attest: registrar chave por instalação, verificar atestação e assertions no backend, prevenir replay.
- Testes em dispositivos iOS físicos, simuladores para compatibilidade não criptográfica e fixtures abertas.
- Não prometer injeção geral em IPA assinada nem produto no-code completo nesta fase.

### v1.0 — Android Stable

- APK comprovadamente reconstruído, alinhado, assinado e instalado; AAB somente se houver validação completa e publicação suportada.
- Conjunto explícito de perfis e proteções com compatibilidade documentada.
- RASP calibrado com falsos positivos e respostas graduais.
- Laboratório automatizado e relatórios reproduzíveis por build.
- Rollback de políticas, documentação de suporte e threat model.
- Release reproduzível, SBOM, hashes, licença, proveniência e gestão de chaves.

### v2.0 — Platform GA

- Control plane/API, registry de artefatos/proteções, catálogo de profiles, relatórios centralizados e políticas por organização/equipe.
- Suporte consistente a GitHub Actions e Azure Pipelines; runners isolados; operações de assinatura externas.
- Possível separação do Trust API para serviço/repositório dedicado.
- Promover iOS a GA somente após passar por gates de compatibilidade/segurança específicos.
- Documentação operacional, ADRs, exemplos Flutter/React Native/nativo e matriz de suporte.

## 6. Estrutura de diretórios proposta

    fusion-base/
    ├── src/fusionbase/
    │   ├── domain/
    │   │   ├── artifacts.py
    │   │   ├── protection.py
    │   │   ├── policies.py
    │   │   ├── evidence.py
    │   │   └── ports.py
    │   ├── application/
    │   │   ├── inspect_artifact.py
    │   │   ├── plan_protection.py
    │   │   ├── protect_app.py
    │   │   ├── validate_artifact.py
    │   │   └── evaluate_security.py
    │   ├── infrastructure/
    │   │   ├── android/{apktool,bundletool,smali,signing}/
    │   │   ├── ios/
    │   │   ├── runners/
    │   │   └── telemetry/
    │   ├── adapters/
    │   │   ├── obfuscapk/
    │   │   ├── dpt_shell/
    │   │   ├── xop_protector/
    │   │   ├── cyber_armor/
    │   │   ├── rasp/
    │   │   ├── mob_sf/
    │   │   └── o_mvll/
    │   ├── orchestration/{registry,planner,executor,compatibility}.py
    │   └── interfaces/{cli.py,api/}
    ├── runtime/{android-sdk,ios-sdk,trust-api}/
    ├── contracts/{policy.schema.json,evidence.schema.json,telemetry.schema.json}
    ├── policies/{mobile-standard.yaml,mobile-high-security.yaml,rego/}
    ├── tests/{unit,property,contract,integration,compatibility,security,fixtures}/
    ├── examples/{android-native,flutter,react-native}/
    ├── deployments/{docker,kubernetes}/
    ├── .github/workflows/
    └── doc/{ROADMAP.md,architecture/,adr/,threat-model/}

Essa é uma estrutura-alvo, não uma representação do estado presente do repositório. Evitar migração estrutural total antes da v0.3.

## 7. Experiência CLI planejada

    fusion-base inspect app.apk
    fusion-base plan --input app.apk --profile policies/mobile-high-security.yaml
    fusion-base protect --input app.apk --output protected.apk --profile policies/mobile-high-security.yaml
    fusion-base verify protected.apk
    fusion-base evaluate --original app.apk --protected protected.apk
    fusion-base report --format json --output evidence.json
    fusion-base adapters list

A CLI deve produzir códigos de saída específicos para configuração, transformações, assinatura, integridade e violações de política. `plan` não modifica o artefato; `verify` executa validações independentes.

## 8. CI/CD e security gates

| Gate | Verificação | Critério de saída proposto |
|---|---|---|
| G01 — Qualidade | Ruff, mypy, Bandit, pytest, Hypothesis | Sem erro impeditivo |
| G02 — Supply Chain | Dependências pinadas, SBOM, licença, proveniência | Sem bloqueio de política |
| G03 — Build Fixtures | APK de demonstração, keystore descartável | Build reproduzível |
| G04 — Protection Pipeline | Mapeamento, injeção, ofuscação, reconstrução | Transformações requeridas verificadas |
| G05 — Artifact Verification | Manifest, tipo, ZIP, hash, zipalign, assinatura | Artefato válido |
| G06 — Runtime | Instalação, startup, autenticação, operações sensíveis | 100% dos testes críticos |
| G07 — Security Evaluation | MobSF, JADX, APKiD, Frida e casos MASVS | Evidências por cenário |
| G08 — Policy Gate | OPA/Rego sobre evidências e riscos | Release aprovada/reprovada |
| G09 — Release | Publicação do artefato, hash, relatório, SBOM | Assinatura verificada e rastreável |

Rodar pull requests sem chaves produtivas; usar keystores descartáveis e runners de teste. Habilitar releases com ambiente protegido e aprovação. Preservar execução CLI idêntica em GitHub Actions/Azure DevOps. Segurança dinâmica apenas em laboratório autorizado.

### 8.1. Metas de qualidade (propostas, não medições)

| Métrica | Meta inicial |
|---|---|
| Transformações obrigatórias aplicadas | 100% ou reprovar build |
| Fixtures suportados recompilados e validados | 100% |
| Fluxos funcionais críticos | 100% aprovados |
| Regressões críticas conhecidas | 0 em release |
| Overhead de startup | Até +20% (calibrar após baseline) |
| Crescimento do artefato | Até +15% (calibrar após baseline) |
| Cobertura do orquestrador | ≥85% |
| Evidência dos builds de release | 100% |
| Exposição conhecida de segredos | 0 |

Matriz inicial de teste: versões Android suportadas conforme disponibilidade (incluindo 13–17 quando viável), ARM64, debug/release, bibliotecas nativas, páginas de memória de 16 KB, Flutter/React Native e alterações de distribuição. Não inferir suporte sem execução.

## 9. Matriz de componentes e decisões de adoção

| Ferramenta | Função | Decisão |
|---|---|---|
| [Obfuscapk](https://github.com/Mobile-IoT-Security-Lab/Obfuscapk) | Ofuscação de APK/AAB (AAB requer validação) | Primeiro adapter |
| [dpt-shell](https://github.com/luoyesiqiu/dpt-shell) | DEX packing/hollowing | Avaliação isolada |
| [XopProtector](https://github.com/xopJack/XopProtector) | DEX/VMP/RASP | Pesquisa/PoC |
| [CyberArmor](https://github.com/VexoraWebServices/CyberArmor) | Shell/packing | Pesquisa/PoC |
| [DCC / Dex2C](https://github.com/amimo/dcc) | DEX → C seletivo | PoC opcional |
| [O-MVLL](https://github.com/open-obfuscator/o-mvll) | Ofuscação LLVM nativa | Build-time, quando elegível |
| [dProtect](https://github.com/open-obfuscator/dProtect) | Ofuscação JVM/Dex | Opcional, revisão GPL |
| R8/ProGuard | Baseline de ofuscação/otimização | Build-time, não RASP |
| [android-rasp](https://github.com/securevale/android-rasp) | Sensores RASP | Referência aberta |
| [RootBeer](https://github.com/scottyab/rootbeer) | Sinais de root | Sensor auxiliar |
| [freeRASP](https://github.com/talsec/Free-RASP-Community) | RASP multiplataforma | Híbrido; opcional após licença |
| [MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF) | Análise mobile | Laboratório de avaliação |
| [APKiD](https://github.com/rednaga/APKiD) | Detecção de packers | Laboratório de avaliação |
| [Androguard](https://github.com/androguard/androguard) | Inspeção DEX/APK | Laboratório de avaliação |
| [JADX](https://github.com/skylot/jadx) | Decompilação | Laboratório de avaliação |
| [LIEF](https://github.com/lief-project/LIEF) | Análise ELF/Mach-O | Avaliação especializada |
| [Frida](https://github.com/frida/frida) | Instrumentação | Laboratório autorizado |
| [Objection](https://github.com/sensepost/objection) | Testes dinâmicos | Laboratório autorizado |
| [IOSSecuritySuite](https://github.com/securing/IOSSecuritySuite) | Sinais iOS | Não incluir sem revisão da EULA |
| [ARMANDroid](https://github.com/Mobile-IoT-Security-Lab/ARMANDroid) | Anti-repackaging | Pesquisa; atenção AGPL |
| [SwiftShield](https://github.com/rockbruno/swiftshield) | Ofuscação Swift | Não adotar como base produtiva |
| [ByteX](https://github.com/bytedance/ByteX) | Transformação Gradle | Referência arquitetural, compatibilidade antiga |

Licença pública não equivale a licença permissiva. Revisar inclusive ferramentas GPL/AGPL e SDKs que tenham partes proprietárias. Executar em subprocesso não garante, por si só, isolamento de obrigações.

## 10. Riscos técnicos e medidas de controle

1. **DEX criptografado se materializa no runtime:** não alegar segredo permanente de código, nem resistência absoluta contra adversário no dispositivo.
2. **Packers competem entre si:** manter matriz de exclusão, ordem do pipeline e política de seleção única por família até evidência contrária.
3. **Android evolui:** acompanhar carregamento dinâmico, Android 14+, páginas de 16 KB, ABI, target SDK, NDK e mudanças de loaders.
4. **AAB e assinatura:** chave de upload não é a chave da assinatura final Play App Signing; não supor que uma verificação local tem o mesmo certificado que a distribuição.
5. **Code transparency:** gerar evidências depois de transformações relevantes, nunca alterar código depois de assinar/transparência.
6. **iOS code signing e entitlements:** não prometer pós-build genérico ou alteração de IPA já assinada.
7. **Observabilidade versus anti-debug:** bloquear ferramentas de diagnóstico pode dificultar análise de crashes; medir custo e manter respostas graduais.
8. **Risco do próprio packer:** executar em sandbox, fixar digest, SBOM, bloquear rede desnecessária e nunca repassar chaves de produção.
9. **Falsos positivos RASP:** testar ambientes corporativos, acessibilidade, VPN, emuladores e jailbreak rootless.
10. **Proteção client-side é sinal parcial:** decisão de autorização permanece no backend; atestação deve ser validada criptograficamente e vinculada à requisição.

## 11. Primeiros PRs sugeridos

1. **PR-01 — Fix Smali Injection:** corrigir inserção, resolução de classe e falha silenciosa.
2. **PR-02 — Artifact Pipeline:** separar APK/AAB, validar assinatura, tipo, hash e alinhamento.
3. **PR-03 — Integration Test Harness:** fixture real, keystore de teste, instalação e smoke tests.
4. **PR-04 — Protection Adapter Contract:** registry, planner, JSON Schema e CLI expandida.
5. **PR-05 — Obfuscapk Integration:** primeiro adapter de ofuscação com evidência independente.

Ordem sugerida: PR-01 → PR-02 → PR-03 → PR-04 → PR-05. Preferir PRs pequenos em vez de migração monolítica.

## 12. Critérios de sucesso do produto

Uma versão suporta oficialmente determinada combinação de app/formato/plataforma apenas se:

1. inspeciona o artefato e identifica seu tipo de forma correta;
2. escolhe um perfil de proteção válido e resolve incompatibilidades;
3. executa e **comprova** cada controle obrigatório;
4. gera artefato no formato correto, com assinatura verificada;
5. instala e executa nos ambientes declarados;
6. não quebra os fluxos de negócio críticos;
7. produz métricas e evidências dos cenários de segurança;
8. entrega hash, proveniência, inventário de componentes e logs controlados;
9. publica matriz de suporte, riscos residuais e rollback.

## 13. Integração com DevRiskOps

Os relatórios de cada build devem ser relacionados ao inventário de software e à aplicação avaliada, incluindo SBOM, controles de segurança, proteções e evidências de testes. Uma aplicação pode ser vinculada por identidade, versão e hash do artefato a políticas executadas e decisões de release.

Potencial de associação com TEA / DueDiligenceAssessment e modelos canônicos existentes: Organization → Product → Service/Application → artifact hash → protection profile → build evidence → runtime trust. Esta integração é planejada e não constitui funcionalidade existente.

## 14. Rastreabilidade de issues

Issues do GitHub serão criadas com prefixo de versão e prioridade, descrição técnica, entregáveis, critérios de aceite e dependências. A lista de tickets está disponível em [Issues](https://github.com/DevComputaria/fusion-base/issues). Os identificadores de backlog `FB-001` a `FB-010` acima são IDs de planejamento e não substituem os números de issue.

## 15. Referências

- [Fusion Base — código e README](https://github.com/DevComputaria/fusion-base)
- [Android App Bundle](https://developer.android.com/guide/app-bundle)
- [Android Play Integrity](https://developer.android.com/google/play/integrity)
- [Apple App Attest](https://developer.apple.com/documentation/devicecheck)
- [OWASP MASVS](https://mas.owasp.org/MASVS/) e [MASTG](https://mas.owasp.org/MASTG/)
- Ferramentas e repositórios em `9. Matriz de componentes`.

---

**Decisão recomendada:** começar corrigindo Smali, formatos e assinatura; instalar e executar um APK real; só então integrar Obfuscapk como primeiro adapter. Manter dpt-shell/XopProtector/CyberArmor isolados em laboratório, com escolha baseada em evidências.