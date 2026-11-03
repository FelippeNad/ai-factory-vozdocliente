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
   benchmark 120 → 30 chamadas LLM exclusivamente simuladas.
4. [Retenção DRY_RUN e auditoria](etapa-2-retencao-exclusao.md): validação DEV
   `retention-6`, sem exclusão real; [diagnóstico de schema](diagnostico-schema-retencao.md).
5. [Observabilidade da retenção](etapa-2-observabilidade.md): alerta sintético
   enviado/recebido no Slack DEV conforme validação informada pelo responsável.
6. [Mapa LGPD](lgpd/mapa-dados-pessoais.md), [transferências](lgpd/transferencia-internacional.md),
   [rotação](security/rotacao-credenciais.md), [checklist](lgpd/checklist-etapa-2.md)
   e [roteiro de evidências](lgpd/roteiro-evidencias.md).

## Experimental: não apresentar como integração validada

- [Router observável](etapa-2-observabilidade-router.md): três exports inativos,
  sem credenciais, com integração no engine ainda pendente.
- [Relatório de 23 eventos](evidencias/router-observabilidade-simulacao.html):
  **SIMULAÇÃO OFFLINE**, sem métricas de produção. p50/p95/p99 são do harness.
- Dashboard alimentado por coleta n8n real, custos/latências reais, acurácia humana
  e watchdog externo permanecem pendentes.

## Referências históricas

[ADRs](adr/ADR-001-stack.md), [deploy e ambientes](adr/ADR-002-deploy-e-ambientes.md),
[C4 contexto](architecture/c4-context.md), [C4 containers](architecture/c4-container.md),
[smoke tests](smoke-tests.md), [rollback](rollback.md),
[postmortem](postmortem-n8n-encryption-key.md) e
[capturas da Etapa 1](evidencias/evidencias-projeto.md) preservam decisões e fatos
relatados anteriormente. Não comprovam disponibilidade atual do Railway nem
validação da observabilidade experimental. Algumas capturas históricas exigem
revisão de identificadores pessoais; nenhuma limpeza de histórico foi executada.

Os exemplos herdados são material didático; não considerar comprovada a
anonimização de dados reais por essa descrição. Preferir fixtures controladas em
`tests/fixtures/`. Referências jurídicas e contratos continuam sujeitos à revisão;
não há declaração de conformidade integral com a LGPD.
