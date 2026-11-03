# Changelog

Todas as mudanças relevantes do projeto são registradas neste arquivo.

## [Não lançado] — Etapa 2

- Preparada a entrega local sem novas funcionalidades: README/índice separam
  validações n8n informadas pelo responsável, evidências offline e experimentos.
  Railway indisponível após o período gratuito; deploy/smoke tests/ADRs antigos
  identificados como históricos. Actions permanece só testes, com token de leitura.
- Revisadas capturas `02` a `06`, `08`, `09`, `11` com recorte/tarjas sólidos, sem IA
  generativa e preservando pixels técnicos; preparado resumo retention-6 sem
  preview. Confirmada presença dos originais no histórico público; limpeza exige
  decisão/autorização separada e não foi executada.
- Executado Gitleaks local com redação de achados, regra de falso positivo
  restrita por AND, proteção de arquivos locais e auditoria de publicação.
  Evidência de rotação de estados atualizada para hashes atuais, sem rotação real.
  Nenhum commit, push, merge, force push, deploy ou configuração externa alterada.

- Nova candidata `vozdocliente-router-v4-observavel-dev.json`, observador por
  subworkflow e Error Workflow separados, inativos e sem credenciais. Preservados
  v3/v4, candidata otimizada anterior, retenção, PII/precheck/deduplicação final.
- Eventos por lista de campos permitidos, correlação por execução, métricas de
  tentativas/respostas LLM, persistência confirmada, duração e custos condicionais
  a uso/preços. Captura explícita das falhas operacionais também no modo manual;
  parada segura após observação. Error Trigger cobre interrupções automáticas,
  com correlação parcial identificada quando o ID original não está disponível.
- Reutilizados transporte/IF/resultado Slack da retenção; alerta Router P1 opt-in
  em DEV. Compose local prevê IDs de integração, preços vazios, stdout opt-in e
  rotação por tamanho. Relatório HTML sem rede calcula percentis e separa fontes;
  simulação reproduzível e manifesto com hashes, testes/CI e roteiro manual.
  Nenhuma API externa, ativação, deploy, alteração de credenciais ou commit.

- Adicionado candidato DEV derivado da v4 com precheck de duplicatas antes do LLM,
  preservando consulta final, sanitizador, prompt/schema e parser. Baselines v3/v4
  intactos; export novo inativo, caminho próprio, sem credenciais e sem fallback PROD.
- Benchmark offline com a mesma carga de 120 eventos: 120 -> 30 chamadas LLM
  simuladas, 120 -> 150 consultas Airtable, mesmos 30 registros e 20 textos de alerta.
  Média local do harness 458,654 -> 555,445 ms/lote (mais lenta); latência de APIs/LLM
  real não medida. Registradas amostras/hashes, testes, trade-offs e evidências.

- Reaproveitado o resumo da retenção para observabilidade DEV: evento estruturado
  sem conteúdo de avaliações, contadores por execução, quantidade analisada e
  duração total. Alerta Slack opt-in, somente DEV, com campos permitidos e falha
  de entrega tratada sem resposta do provedor ou retry. DEMO permanece sem HTTP.
- Acrescentados testes, simulação de HTTP 503 reproduzível, relatório explicitamente
  sintético e roteiro de evidências/manuais. Compose dedicado prevê stdout de Code
  em modo não manual e rotação Docker por tamanho; descarte por idade segue pendente.
  Mantidos v3/v4, motor, guard e schema Airtable. Nenhuma API/deploy/commit executado.

- Corrigido o envio de auditoria no HTTP Request 4.1 após confirmar no n8n DEV
  instalado que `sendBody` tem `noDataExpression: true`: removida a expressão
  incompatível desse parâmetro, adicionados IF de transporte e nodes com
  `sendBody: true` literal para POST/PATCH JSON com `fields` e `false` literal
  para GET/DELETE sem body. Explicitar somente `contentType=json` na correção
  anterior era insuficiente. Exports operacional/DEMO regenerados; validação
  estrutural cobre os dois ramos e rejeita retorno à expressão. Código instalado
  testado com transporte em memória, credencial sintética e rede bloqueada.
  Nenhuma proteção DEV, DRY_RUN, schema ou DELETE foi alterada.

- Tornado configurável o nome esperado da tabela de retenção via
  `RETENTION_TABLE_NAME` (padrão `Reviews`), permitindo `ReviewsRetentionTest`
  sem renomear tabelas. Mantidos seleção por IDs, auditoria `RetentionAudit` com
  18 campos obrigatórios, DRY_RUN e barreiras de DELETE; mudança de nome durante
  execução bloqueia a próxima operação.
- Atualizados fontes, gerador, exports inativos e Compose de retenção; adicionados
  diagnóstico local de nomes/tipos e testes offline de aceitação/rejeição e
  proteções. Documentada atualização local/reimportação sem tocar em credenciais
  ou v3/v4. Nenhuma chamada externa, exclusão real, deploy ou commit realizado.

- Adicionados mapa de dados pessoais, análise de transferências internacionais,
  checklist de estados/pendências e roteiro de demonstração em `docs/lgpd/`.
- Documentadas hipóteses legais e papéis sujeitos à validação, sem presumir
  consentimento universal, contratos ou conformidade integral com a LGPD.
- Adicionado procedimento de rotação por fornecedor, recuperação, tratamento de
  exposição em Git e distinção entre token, DEK e chave mestra n8n.
- Executado exercício offline com 38 cenários simulados e relatório verificável
  por checksum e hashes dos artefatos; nenhuma credencial real foi rotacionada.
- Atualizadas referências dos ADRs e documentos existentes. Na alteração
  documental de conformidade/rotação, workflows, Compose, variáveis de exemplo e
  credenciais foram preservados.

- Adicionados workflows independentes e inativos de retenção DEV e demonstração
  offline sem HTTP, mantendo os arquivos v3/v4 de classificação intactos.
- Política configurável (30 dias demonstrativos), Schedule Trigger diário,
  DRY_RUN padrão, verificação de schema `processed_at`, paginação e limites.
- Exclusão condicionada a DEV/confirmações, com auditoria agregada prévia,
  releitura do candidato e checkpoint; falhas interrompem novas exclusões.
- Adicionados fontes/gerador determinístico, testes sintéticos do grafo real,
  Compose DEV isolado com proposta de pruning n8n, variáveis e roteiro de evidências.
- Documentados recuperação, desfechos incertos, concorrência e retenções separadas
  em `docs/etapa-2-retencao-exclusao.md`. Nenhuma exclusão real ou deploy executado.

- Adicionada v4 inativa com node Code `Sanitizar PII` antes do LLM, máscaras de
  CPF/CNPJ/e-mail/telefone/CEP/URLs e campo sanitizado obrigatório sem fallback.
- Preservadas v3, credenciais, versões dos nodes e persistência original no Airtable.
- Reduzido o alerta Slack a tema/nota; erros customizados não incluem conteúdo
  recebido; salvamento de execuções desabilitado nas configurações da v4.
- Adicionados testes do JavaScript exportado, bypass no grafo, entradas inválidas,
  limites de detecção e preservação de classificação com fixtures sintéticas; CI atualizado.
- Documentados riscos separados por destino e evidências ainda pendentes em
  `docs/etapa-2-sanitizacao-pii.md`. Sem deploy nem declaração de conformidade LGPD.

## [1.0.0] - 2026-10-05

### Adicionado

- ambiente de desenvolvimento local com n8n via Docker;
- uso de LM Studio com Qwen3-4B no ambiente DEV;
- ambiente público de produção hospedado no Railway;
- integração de produção com OpenAI API;
- persistência separada no Airtable PROD;
- notificações separadas no Slack PROD;
- PostgreSQL para persistência interna do n8n em produção;
- deduplicação de avaliações por `review_id`;
- validação defensiva das respostas do LLM;
- JSON Schema para saída estruturada do modelo em produção;
- separação entre ambientes DEV e PROD;
- variáveis e secrets específicos por ambiente;
- uso de `AIRTABLE_BASE_ID` como variável de ambiente;
- workflow n8n versionado até `vozdocliente-router-v3.json`;
- Dockerfile com versão fixa `n8nio/n8n:2.41.7`;
- GitHub Actions para validação automatizada;
- deploy automático no Railway a partir da branch `main`;
- três smoke tests executados em produção;
- documentação de evidências dos smoke tests;
- auditoria do protótipo herdado;
- matriz de decisão de stack;
- ADR-001 para decisão de stack;
- ADR-002 para estratégia de deploy e ambientes;
- diagramas C4 de contexto e containers;
- documentação atualizada da arquitetura e operação.

### Alterado

- n8n passou a ser o principal orquestrador da solução;
- o protótipo original em Make.com foi preservado apenas como referência histórica;
- o fluxo passou a validar `sentiment` e `theme` contra listas permitidas;
- avaliações negativas continuam gerando alertas, enquanto positivas e neutras não geram notificações;
- credenciais herdadas foram substituídas por credenciais específicas dos ambientes atuais;
- configuração do Airtable deixou de utilizar Base ID hardcoded no workflow;
- imagem de produção deixou de depender da tag `latest`.

### Corrigido

- tratamento de respostas inválidas ou ausentes do LLM;
- risco de registros duplicados no Airtable;
- risco de alertas duplicados no Slack;
- dependência do ambiente de produção da máquina local;
- configuração de persistência do n8n no Railway;
- problema de chave de criptografia do n8n após reinicializações do serviço.

### Segurança

- secrets não são armazenados diretamente no repositório;
- arquivos `.env` permanecem ignorados pelo Git;
- credenciais DEV e PROD são mantidas separadamente;
- identificadores e configurações de ambiente foram externalizados quando aplicável.

---

## [0.2] - Protótipo herdado

- adicionado espelho executável do fluxo em n8n;
- filtro de alerta ajustado para `sentiment == "negativo"`;
- normalização básica com `.toLowerCase().trim()`.

## [0.1] - Protótipo herdado

- primeira versão em Make.com;
- webhook para recebimento de avaliações;
- classificação por LLM;
- persistência no Airtable;
- alertas no Slack.
