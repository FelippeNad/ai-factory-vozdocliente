# Documentação da Etapa 2

O [README principal](../README.md) é a fonte do estado atual: validação no n8n
informada pelo responsável, validação offline e experimentos são categorias
distintas. Railway está indisponível após o período gratuito. Não executar os
procedimentos históricos de produção para apresentar esta entrega.

## Caminho recomendado para apresentação

1. [Auditoria e preparação da publicação](entrega-etapa-2.md): testes, arquivos,
   Gitleaks, revisão de imagens e bloqueios antes de commit/push.
2. [Sanitização PII](etapa-2-sanitizacao-pii.md): regra obrigatória antes do LLM e
   limites da regex. O responsável informou validação local no n8n.
3. [Router otimizado DEV](etapa-2-otimizacao-v4.md): precheck validado no n8n;
   histórico offline de 120 → 30 chamadas LLM e benchmark real separado abaixo.
4. [Retenção DRY_RUN e auditoria](etapa-2-retencao-exclusao.md): validação DEV
   `retention-6`, sem exclusão real; [diagnóstico de schema](diagnostico-schema-retencao.md).
5. [Observabilidade da retenção](etapa-2-observabilidade.md): alerta sintético
   enviado/recebido no Slack DEV conforme validação informada pelo responsável.
6. [Observabilidade Router DEV: thresholds e resultados](etapa-2-observabilidade-router.md#thresholds-iniciais-dev-e-resultados-observados):
   coleta real de 11 execuções controladas, 5 avaliações rotuladas e P1 validado
   no Slack DEV. Limites de latência, custo, erro normal, volume, acurácia e
   validade estrutural justificados individualmente. Amostra sintética e limitada;
   conjunta de 80% abaixo da meta de 90%; 27,27% de falha inclui falhas intencionais
   e não representa operação normal. P2/P3 sem notificações automáticas.
7. [Mapa LGPD](lgpd/mapa-dados-pessoais.md), [transferências](lgpd/transferencia-internacional.md),
   [rotação](security/rotacao-credenciais.md), [checklist](lgpd/checklist-etapa-2.md)
   e [roteiro de evidências](lgpd/roteiro-evidencias.md).

## Benchmark real e limites da validação

- [Benchmark real antes/depois DEV](benchmark-real-deduplicacao-dev.md): concluído,
  15 requisições por versão, LLM 15 → 5, custo US$ 0,000675 → 0,000225 e
  latência média 2396,87 → 1549,93 ms. Consultas Airtable 15 → 20; cinco registros
  e dez duplicatas por versão. Sem falhas, validade estrutural de 100%; acurácia
  persistida não avaliada. Carga sintética limitada, sem inferência de produção.
  [Relatório HTML](evidencias/benchmark-dev-real.html),
  [amostras numéricas](evidencias/benchmark-dev-amostras.json) e
  [manifesto verificável](evidencias/etapa-2-evidencias-manifesto.json).

- [Router observável](etapa-2-observabilidade-router.md): exports inativos e sem
  credenciais; coleta DEV/P1 não comprovam todos os cenários nativos de Error Trigger.
- [Relatório de 23 eventos](evidencias/router-observabilidade-simulacao.html):
  **SIMULAÇÃO OFFLINE**, sem métricas de produção. p50/p95/p99 são do harness.
- [Dashboard real de observabilidade](evidencias/router-observabilidade-dev-real.html)
  com coleta n8n e avaliação manual separado do benchmark;
  watchdog externo, carga representativa e indicadores de produção permanecem
  sem comprovação. Custos desconhecidos não entram na média como zero.

## Referências históricas

[ADRs](adr/ADR-001-stack.md), [deploy e ambientes](adr/ADR-002-deploy-e-ambientes.md),
[C4 contexto](architecture/c4-context.md), [C4 containers](architecture/c4-container.md),
[smoke tests](smoke-tests.md), [rollback](rollback.md),
[postmortem](postmortem-n8n-encryption-key.md) e
[capturas da Etapa 1](evidencias/evidencias-projeto.md) preservam decisões e fatos
relatados anteriormente. Não comprovam disponibilidade atual do Railway nem
validação atual de todos os cenários de observabilidade. Algumas capturas históricas exigem
revisão de identificadores pessoais; nenhuma limpeza de histórico foi executada.

Os exemplos herdados são material didático; não considerar comprovada a
anonimização de dados reais por essa descrição. Preferir fixtures controladas em
`tests/fixtures/`. Referências jurídicas e contratos continuam sujeitos à revisão;
não há declaração de conformidade integral com a LGPD.
