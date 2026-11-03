# Auditoria de preparação da Etapa 2

Revisão local: **03/11/2026**, branch **`etapa-2`**, HEAD
`27652b0`. Sem commit, staging pelo agente, push, merge, force push, deploy,
ativação de workflow, alteração de credenciais ou configurações externas.
Nenhuma nova funcionalidade do produto foi implementada nesta preparação.

**Publicação ainda bloqueada:** a ocultação das capturas no workspace não remove
os originais do histórico público, e autodeploy/webhooks externos não foram
confirmados pelo responsável. Os arquivos podem ser revisados para um commit
local, mas isso não é autorização ou indicação de segurança para push.

## Problemas encontrados e organização realizada

- README misturava infraestrutura histórica com estado atual, recomendava
  protótipo v0 e apresentava Railway/endpoint como disponíveis. Foi reorganizado
  em **VALIDADO NO N8N**, **VALIDADO OFFLINE** e **EXPERIMENTAL / PENDENTE**.
- O guia local continha `admin/admin`, instruções históricas de ativação e
  referências nominais de credenciais. Foi substituído por catálogo e configuração
  DEV explícita, sem tokens, sem ativação e sem instrução para chamar PROD.
- ADRs/C4/smoke tests/rollback/postmortem passaram a indicar seu caráter histórico
  e a indisponibilidade do Railway após o período gratuito. Decisões antigas foram
  preservadas como registros, não como estado operacional atual.
- Removida a alegação não comprovada de anonimização dos exemplos herdados.
  As fixtures automatizadas controladas continuam sintéticas; regex não torna
  o dado anônimo nem demonstra conformidade integral com a LGPD.
- O relatório visual de **23 eventos** continua explicitamente **SIMULAÇÃO
  OFFLINE**. p50=5 ms, p95=31 ms, p99=31 ms e taxa de falha 1/3 pertencem ao
  cenário sintético do harness, N=3, não à instância n8n ou a fornecedores.
- A evidência de rotação estava desatualizada em relação aos Composes e
  `.env.example` alterados em fases anteriores. Foi regenerado o exercício
  **offline de 38 cenários**, com hashes atuais; não houve rotação real.
- Gitleaks não estava instalado. Obtido o executável oficial **8.30.1**, em pasta
  ignorada `.tools/`, com SHA-256 do ZIP conferido contra o checksum do release.
  As varreduras rodam localmente, sem upload de conteúdo do projeto.
- A exceção de falso positivo no `.gitleaks.toml` ganhou `condition="AND"`:
  commit, caminho e placeholder precisam coincidir. Não foi criada exceção ampla
  por arquivo, regra ou diretório para mascarar achados.
- `.env.*` e `*.env` foram protegidos no ignore, mantendo `.env.example` como
  exceção. A cópia original local do resumo de retenção com preview de IDs ficou
  ignorada; foi preparado um recorte público sem esse preview.
- Corrigido um problema de codificação durante a edição: textos foram conferidos
  em UTF-8, sem alterar os workflows. Não ficaram substituições de acentos por `?`.

## Privacidade das capturas e histórico público

Com autorização explícita para recorte/tarjas programáticos, **sem IA generativa**:

| Arquivo | Revisão no workspace |
| --- | --- |
| `docs/evidencias/02-llm-local-qwen.png` | Valor de `customer_name` ocultado; configuração local e classificação preservadas |
| `docs/evidencias/03-parse-merge-dev.png` | Nome de cliente ocultado; campos, parser e saída de classificação preservados |
| `docs/evidencias/04-roteamento-negativo.png` | Nome de cliente e IDs internos de registro ocultados; condição e resultado preservados |
| `docs/evidencias/05-airtable-dev.png` | Nome de cliente ocultado; colunas e classificação preservadas |
| `docs/evidencias/06-slack-dev.png` | Recorte da mensagem técnica; nome/avatar/identificação pessoal e linha do cliente ocultados. Tema, mensagem e instrução técnica preservados |
| `docs/evidencias/08-github-actions-ci.png` | Nome/handle/avatar de conta ocultados; resultado, commit e branch preservados |
| `docs/evidencias/09-railway-deploy-success.png` | Avatares ocultados e diagnóstico inferior com identificação de conta recortado; status e resultados técnicos preservados |
| `docs/evidencias/11-railway-rollback-action.png` | Avatares ocultados; commits, estados e opções de rollback preservados |
| `docs/evidencias/retention-6-resumo-redigido.png` | Novo recorte da captura local, sem preview ou IDs de registros; números e confirmações de auditoria são os pixels originais |

As alterações foram inspecionadas visualmente e comparadas pixel a pixel com o
recorte original: fora das tarjas, os pixels permanecem idênticos. Metadados PNG
foram removidos. A ocultação de identificadores visuais não é comprovação de
anonimização integral ou de funcionamento atual do sistema.

**A imagem original do Slack já está pública.** Confirmado por consulta somente
de leitura ao GitHub, não apenas por referências locais:

- Repositório `FelippeNad/ai-factory-vozdocliente`, visibilidade pública,
  default branch `main`.
- Introdução das capturas históricas revisadas (`02` a `06`, `08`, `09`, `11`):
  [commit `0146fef7e0ab009b33945a35bd2ba81174598047`](https://github.com/FelippeNad/ai-factory-vozdocliente/commit/0146fef7e0ab009b33945a35bd2ba81174598047),
  mensagem `docs: add project delivery evidence`, data **06/10/2026**.
- A árvore pública de `main`, commit
  `7bb5dc890d50eadcd0180ab5956956aa597fe57b`, ainda contém
  `docs/evidencias/06-slack-dev.png`, blob Git SHA-1
  `0856bc29bf7369afcc587645007a3a0ba103faaf` (733409 bytes), idêntico ao objeto local
  anterior à ocultação. As demais capturas revisadas também constam dessa árvore.
- O original é alcançável localmente por `main`, `origin/main` e `etapa-2`.
  Não houve remoção, alteração de refs ou reescrita de commits.

### Opções seguras a decidir, sem executar automaticamente

1. Um futuro commit com as versões ocultadas corrige a árvore nova, **mas não
   remove as versões antigas** acessíveis por commit/branch/tag/cópia.
2. Se for exigida remoção do histórico, preparar plano autorizado e coordenado
   com o administrador: listar branches/tags afetadas, backup restrito, limpar
   os caminhos em uma cópia isolada, validar tudo e só então decidir como atualizar
   refs remotas. Isso pode exigir force push e sincronização dos clones; nada
   disso foi autorizado ou executado.
3. Avaliar com o administrador e suporte do GitHub referências/caches e cópias
   remanescentes após eventual limpeza. Não prometer apagamento de forks,
   downloads ou clones de terceiros.
4. Uma entrega sanitizada em repositório novo, sem importar o histórico antigo,
   é outra opção sujeita à autorização; não remove a exposição do repositório
   original. Mudanças de visibilidade/configuração são decisão manual externa.

Até essa decisão, não declarar ausência de informações pessoais no histórico
público e não publicar a branch por considerar apenas o Gitleaks aprovado.

## Gitleaks e conteúdo candidato

A lista de publicação é `git ls-files --cached --others --exclude-standard`:
arquivos rastreados mais novos não ignorados. Foi copiada para diretório local
ignorado, sem `.git`, `.env` reais, ferramenta baixada ou relatórios brutos.
`gitleaks dir` verifica esse snapshot; `gitleaks git --log-opts=etapa-2` verifica
os **23 commits alcançáveis** da branch, sem varrer branches externas ao escopo.
Ambos usam configuração explícita, `--redact`, `--ignore-gitleaks-allow` e saída
JSON em `logs/`, fora da publicação.

Primeira execução: **0 achados** no snapshot e **0 achados** no histórico com a
regra restrita do projeto. Uma varredura adicional sem allowlist encontrou
**1 falso positivo comprovado**: placeholder fictício de Airtable no commit
`c56be04a404f7e43467d36480e7fa8e2f9899829`, `.env.example`, linha 19. A exceção AND
é específica para esse caso. Não se trata de uma credencial real descoberta.

O scan final do conteúdo organizado e do histórico também terminou com **0 achados**
em cada escopo, usando a regra restrita do projeto. Gitleaks não faz auditoria de
PII em imagens, não verifica escopos de contas e não comprova segurança integral.
Os resultados não serão descritos como garantia de ausência de todos os segredos.

## Workflows e configurações preservadas

- Router DEV recomendado, retenção DEV/DEMO e os três experimentos: **inativos**,
  `pinData` vazio, nenhuma referência de credencial e nenhum header secreto literal.
- V0/v1/v2: históricos inativos, com referências nominais/IDs de credenciais.
- V3 histórica: `active=true` e quatro referências de credenciais. **Não importar
  ou ativar** para a demonstração. Foi preservada, conforme restrições anteriores.
- V4 original: inativa, quatro referências antigas sem valores secretos.
  Mantida como baseline; o candidato otimizado limpo é o DEV recomendado.
- V3, v4, candidato otimizado e fontes/exports funcionais não foram alterados
  por esta revisão de publicação. Arquivos de retenção modificados no inventário
  já pertenciam às implementações anteriores desta Etapa 2.
- `.env` da raiz e `n8n-mirror/.env` estão ignorados e não são rastreados.
  Somente `.env.example` integra a entrega. Não foram lidos/impressos ou alterados
  valores dos `.env` reais durante a preparação.

## Gatilhos de deploy auditados e risco antes do push

| Componente | Constatação local/pública | Efeito possível |
| --- | --- | --- |
| `.github/workflows/ci.yml` local | Único YAML de Actions; push `main`, PR com base `main`, `workflow_dispatch`; token `contents: read` | Só checkout/setup e testes offline. Push apenas `etapa-2` não satisfaz o gatilho de push |
| Actions da `main` pública | Consulta de leitura confirmou apenas o mesmo arquivo, com testes e sem job de deploy | Não há comando Railway, HTTP do produto, Docker build/run ou secrets de provedores no YAML auditado |
| `Dockerfile` | Referência histórica passiva de n8n 2.41.7; não modificado | Só constrói/inicia se algum sistema o executar; presença do arquivo não desabilita uma integração externa |
| Composes locais | Somente instâncias locais 5678/5680; validação via `config`, sem `up` | Não executam deploy por push |
| Scripts/tests | Transportes em memória e geradores locais; sem chamadas de produto durante os testes | Não realizam operações Airtable/LLM/Slack reais |
| Hooks Git locais | Sem `core.hooksPath` configurado e sem hooks executáveis além dos exemplos padrão | Nenhum gatilho local de deploy identificado |
| Railway/GitHub Apps/webhooks | **Responsável ainda não confirmou configurações externas** | Podem reagir a push independentemente do YAML, inclusive com o serviço atualmente indisponível |

Não foi adicionada execução de deploy ou integração nova. Checkout e setup no CI
usam serviços do GitHub para obter código/runtimes, sem acesso aos provedores do
produto. Nenhuma execução remota foi disparada por esta preparação.

### Conferência manual indispensável

**Railway, sem executar deploy:** abrir o projeto/serviço correto e conferir
repositório vinculado, source branch, autodeploy e eventuais deploy hooks.
Verificar serviços/ambientes além do n8n e qualquer integração GitHub independente
dos checks. Não assumir que fim do período gratuito remove gatilhos. Se houver
gatilho para `etapa-2`, suspender a publicação e decidir a ação com o administrador;
o agente não altera essa configuração.

**GitHub, sem disparar workflows:** conferir todos os arquivos em Actions nas
branches relevantes, Settings → Webhooks (eventos como `push`), Settings →
Integrations/GitHub Apps e repositórios autorizados, Environments/Deployments e
integrações de hospedagem. Conferir também `main` antes de qualquer PR/merge:
Actions e aplicações externas são controles distintos. Não copiar secrets,
assinaturas ou payloads de entrega para evidências públicas.

Registrar quem conferiu, data, branch monitorada e resultado sem credenciais.
Sem essa conferência não é possível garantir, apenas pelo checkout, que o push
não terá efeitos externos. **Nenhum push foi feito.**

## Validações executadas

<!-- BEGIN VALIDATION -->
| Verificação executada localmente | Resultado |
| --- | --- |
| `python tests/validate_workflows.py` | 42 verificações aprovadas |
| `python tests/test_routing_logic.py` | 10 casos aprovados |
| `python -m unittest discover -s tests -v` | 44 testes aprovados |
| `node tests/test_pii_sanitization.cjs` | 102 casos aprovados |
| `node tests/test_retention.cjs` | 165 casos aprovados |
| `node tests/test_retention_schema_diagnostic.cjs` | 49 casos aprovados |
| `node tests/test_observability.cjs` | 15 casos aprovados |
| `node tests/test_router_optimization.cjs` | 31 casos aprovados |
| `node tests/test_router_observability.cjs` | 34 casos aprovados |
| Três geradores com `--check` | Seis exports correspondem às fontes |
| Rotação simulada `--verify` | 38 cenários e hashes atuais aprovados; nenhuma rotação real |
| Benchmark repetido sem `--write` | 120 eventos; LLM simulado 120 → 30; consultas 120 → 150; 30 registros e 20 alertas idênticos |
| Dois Composes com `.env.example` e `config` | Sintaxe, imagem 2.28.7, portas locais e defaults aprovados; sem iniciar contêineres |
| YAML de Actions | Interpretado via extensão `x-ci` do parser Compose; apenas testes, gatilhos documentados e `contents: read` |
| Gitleaks 8.30.1 — árvore candidata e 23 commits | 0 achados com regra restrita; scan adicional sem exceção: 1 placeholder fictício |
| Workflows e privacidade | 11 exports inspecionados; seis DEV/DEMO inativos, sem referências de credenciais ou pinData; ressalvas históricas acima |
| Integridade funcional nesta preparação | 52 arquivos de fontes/scripts/tests/exports idênticos ao snapshot inicial da auditoria |
| Ignores e histórico de nomes de arquivos | Oito caminhos privados cobertos por ignore; só `.env.example` no conteúdo candidato; nenhum `.env` real/chave por nome no histórico alcançável |
| Markdown, UTF-8 e whitespace | Links locais resolvidos, sem whitespace final nos textos alterados; `git diff --check` aprovado |
| Git | Branch `etapa-2`, HEAD `27652b0`, index vazio; sem alteração de refs |

As seis suítes JavaScript somam **396 casos aprovados**, além dos testes Python,
da validação estrutural e do exercício de rotação. Não somar essas contagens como
se fossem medições de qualidade humana do classificador. O Node utilizado nesta
máquina foi 24.22.1 e Python 3.14; o CI está configurado para Node 22/Python 3.12,
mas nenhuma execução remota foi disparada nesta preparação.

A repetição do benchmark confirmou equivalência funcional apenas no corpus
sintético e não sobrescreveu as amostras publicáveis. Houve **zero chamadas reais
ao LLM ou às APIs do produto**. Os números de latência no README continuam os do
relatório original, não uma alegação de redução de latência real.

Logs locais de validação e scanners ficaram em `logs/`, ignorados. As únicas
consultas de rede desta auditoria foram leituras públicas no GitHub para conferir
histórico/CI e obter o release oficial do scanner; não houve upload de arquivos,
consulta Airtable/Slack/LLM, deploy ou alteração externa.
<!-- END VALIDATION -->

## Inventário completo para revisão de commit

O workspace já tinha alterações de implementações anteriores. `M` indica arquivo
rastreado modificado; `??` indica arquivo novo ainda não rastreado. Nada foi
adicionado ao index pelo agente. A lista não é autorização para publicar antes
de resolver os bloqueios acima.

<!-- BEGIN STATUS -->
**41 arquivos rastreados modificados e 45 arquivos novos**,
total de **86 arquivos para revisar**. Nenhum arquivo staged.

```text
 M .env.example
 M .github/workflows/ci.yml
 M .gitignore
 M .gitleaks.toml
 M CHANGELOG.md
 M README.md
 M docs/adr/ADR-001-stack.md
 M docs/adr/ADR-002-deploy-e-ambientes.md
 M docs/airtable-schema.md
 M docs/architecture/c4-container.md
 M docs/architecture/c4-context.md
 M docs/etapa-2-retencao-exclusao.md
 M docs/etapa-2-sanitizacao-pii.md
 M docs/evidencias/02-llm-local-qwen.png
 M docs/evidencias/03-parse-merge-dev.png
 M docs/evidencias/04-roteamento-negativo.png
 M docs/evidencias/05-airtable-dev.png
 M docs/evidencias/06-slack-dev.png
 M docs/evidencias/08-github-actions-ci.png
 M docs/evidencias/09-railway-deploy-success.png
 M docs/evidencias/11-railway-rollback-action.png
 M docs/evidencias/evidencias-projeto.md
 M docs/exemplos-reviews.md
 M docs/lgpd/checklist-etapa-2.md
 M docs/lgpd/roteiro-evidencias.md
 M docs/postmortem-n8n-encryption-key.md
 M docs/rollback.md
 M docs/security/evidencias/rotacao-simulada.json
 M docs/security/rotacao-credenciais.md
 M docs/smoke-tests.md
 M n8n-mirror/README.md
 M n8n-mirror/docker-compose.retention.yml
 M n8n-mirror/docker-compose.yml
 M n8n-mirror/retention/common.js
 M n8n-mirror/retention/demo-transport.js
 M n8n-mirror/workflows/vozdocliente-retencao-demo.json
 M n8n-mirror/workflows/vozdocliente-retencao-v1.json
 M scripts/build_retention_workflow.py
 M tests/test_retention.cjs
 M tests/test_retention_workflow.py
 M tests/validate_workflows.py
?? .gitattributes
?? docs/README.md
?? docs/diagnostico-schema-retencao.md
?? docs/entrega-etapa-2.md
?? docs/etapa-2-observabilidade-router.md
?? docs/etapa-2-observabilidade.md
?? docs/etapa-2-otimizacao-v4.md
?? docs/evidencias/observabilidade-falha-simulada.json
?? docs/evidencias/otimizacao-v4-benchmark.json
?? docs/evidencias/retention-6-RetentionAudit-table.png
?? docs/evidencias/retention-6-resumo-redigido.png
?? docs/evidencias/router-observabilidade-simulacao.html
?? docs/evidencias/router-observabilidade-simulacao.json
?? docs/evidencias/router-observabilidade-simulacao.ndjson
?? n8n-mirror/observability/router-alert.js
?? n8n-mirror/observability/router-common.js
?? n8n-mirror/observability/router-contract.json
?? n8n-mirror/observability/router-error.js
?? n8n-mirror/observability/router-result.js
?? n8n-mirror/retention/observe-result.js
?? n8n-mirror/retention/observe.js
?? n8n-mirror/router-dev/prepare-dedup.js
?? n8n-mirror/router-dev/validate-lookup.js
?? n8n-mirror/workflows/vozdocliente-erros-router-dev.json
?? n8n-mirror/workflows/vozdocliente-observabilidade-router-dev.json
?? n8n-mirror/workflows/vozdocliente-router-v4-observavel-dev.json
?? n8n-mirror/workflows/vozdocliente-router-v4-otimizado-dev.json
?? scripts/benchmark_router_optimization.cjs
?? scripts/build_router_observability.py
?? scripts/build_router_optimized_workflow.py
?? scripts/diagnosticar_schema_retencao.cjs
?? scripts/extrair_schema_retencao_n8n.js
?? scripts/router_observability_report.py
?? scripts/router_observability_validation.py
?? scripts/simular_falha_observabilidade.cjs
?? scripts/simular_router_observabilidade.cjs
?? tests/fixtures/optimization_load.json
?? tests/router_observability_harness.cjs
?? tests/router_optimization_harness.cjs
?? tests/test_observability.cjs
?? tests/test_retention_schema_diagnostic.cjs
?? tests/test_router_observability.cjs
?? tests/test_router_observability.py
?? tests/test_router_optimization.cjs
?? tests/test_router_optimization.py
```
<!-- END STATUS -->

## Fora da lista de publicação

- `.env`, `n8n-mirror/.env`, variações de `.env` reais e arquivos `*.env`.
- `.tools/`, executável/checksums baixados e cópias temporárias de trabalho.
- `logs/` e `gitleaks-report.json`, inclusive snapshots/reports da auditoria.
- `router-local*.ndjson`, `router-local*.json`, `router-local*.html` da raiz.
- `docs/evidencias/retention-6-Resumo sem PII.png`: original local com preview.

Não usar `git add -f` para contornar esses ignores. Antes de um futuro commit
autorizado, revisar o diff staged e repetir scanner no conteúdo efetivamente
selecionado. Não confundir artefatos experimentais versionáveis com integração
validada, nem uma versão ocultada com remoção do histórico público.
