# ADR-003 — Processamento DEV com pré-checagem de duplicatas e sanitização de PII

**Status:** Aceito para demonstração DEV · **Registro:** 23/11/2026

## Contexto

O protótipo herdado classificava avaliações antes de verificar duplicatas e não possuía proteção explícita para dados pessoais contidos no texto. Isso provocava processamento redundante e exposição desnecessária ao provedor de LLM. O briefing exige deduplicação por `review_id` e cuidado com LGPD, credenciais e custos.

## Decisão

No Router v4 otimizado DEV, manter `Sanitizar PII` antes do LLM, sem permitir fallback para texto bruto no prompt; em seguida, realizar `Airtable Precheck DEV` por `review_id`. Quando o ID já existir, encerrar o processamento sem consultar o modelo. Quando não existir, classificar com a OpenAI, validar a saída contra os valores permitidos, consultar novamente o Airtable antes da gravação e enviar alerta ao Slack DEV somente para avaliações negativas. Falhas de pré-checagem e saídas inválidas devem interromper o fluxo sem criar uma classificação presumida.

## Alternativas consideradas

1. **Classificar antes de deduplicar:** mais simples, porém gera chamadas desnecessárias ao LLM em reenvios.
2. **Remover a consulta final:** menos leituras ao Airtable, porém amplia a janela de gravação duplicada quando há concorrência.
3. **Enviar texto original ao LLM:** simplifica o prompt, mas aumenta a exposição de dados pessoais e conflita com a orientação de minimização.

## Consequências positivas

- Reduz chamadas ao modelo quando há duplicatas e impede que padrões comuns de PII sejam encaminhados no texto do prompt.
- Mantém validação de enum/JSON e confirmação de persistência como barreiras distintas.
- É verificável por testes DEV e possui documentação e benchmarks reproduzíveis.

## Consequências negativas e limitações

- A consulta extra ao Airtable adiciona custo operacional, latência para casos novos e dependência da API.
- A pré-checagem e a criação **não são atômicas**: dois envios simultâneos podem atravessar a consulta.
- Regex não identifica todos os dados pessoais; o texto original ainda pode ser mantido no Airtable DEV para tratativa.
- O benchmark sintético da Etapa 2 (15 envios por versão; 10 duplicatas) **não representa produção**; resultados não são equivalentes a economia de infraestrutura total, ROI ou conformidade LGPD.

## Evidência disponível

- Benchmark DEV: 15 → 5 chamadas ao LLM (−66,67%); média 2.396,87 → 1.549,93 ms (−35,34%); GETs Airtable 15 → 20 (+33,33%).
- Na demonstração da Etapa 3, o segundo envio do ID `ETAPA3-DUP-d96c520aecc2` encerrou antes do nó `LLM DEV`.
- Sanitização e limites estão descritos na documentação da Etapa 2; não houve novo teste específico de PII nesta rodada.

## Referências

- [ADR-001 — Stack](ADR-001-stack.md)
- [ADR-002 — Ambientes e deploy](ADR-002-deploy-e-ambientes.md)
- [Sanitização PII](../etapa-2-sanitizacao-pii.md)
- [Otimização Router v4](../etapa-2-otimizacao-v4.md)
- [Benchmark real DEV](../benchmark-real-deduplicacao-dev.md)
- [Validação da Etapa 3](../etapa-3/validacao-evidencias.md)
