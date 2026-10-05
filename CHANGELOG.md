# Changelog

Todas as mudanças relevantes do projeto são registradas neste arquivo.

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