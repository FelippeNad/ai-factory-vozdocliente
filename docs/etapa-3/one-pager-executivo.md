# VozDoCliente CX | Da triagem manual à priorização de reclamações

**Resumo executivo — AI Factory / PUCPR · Etapa 3 · 23 de novembro de 2026**

## O problema

A **VozDoCliente Tecnologia Ltda.**, empresa fictícia de SaaS para Customer Experience, recebe avaliações de clientes de lojas e marketplaces. O desafio é não deixar reclamações negativas sem encaminhamento: atrasos de análise prejudicam a experiência do consumidor e a capacidade de resposta do time de CX. O fluxo herdado já fazia classificação e alertas, mas dependia de contas pessoais, tinha pouca rastreabilidade e carecia de controles de deduplicação e privacidade.

## A solução entregue

**VozDoCliente CX** é uma aplicação web de demonstração que recebe avaliações **fictícias**, apresenta indicadores de sentimento e tema e se integra a um fluxo automatizado **n8n DEV**. O processo classifica avaliações com **OpenAI**, valida a saída, registra o resultado no **Airtable DEV** e encaminha as avaliações negativas ao **Slack DEV**. A arquitetura usa **Node.js e Railway** para o site, com acesso protegido por senha e webhook autenticado. Um precheck por `review_id` evita chamadas desnecessárias ao LLM em reenvios.

**Demonstração:** https://ai-factory-vozdocliente-production.up.railway.app  
**Repositório (branch):** https://github.com/FelippeNad/ai-factory-vozdocliente/tree/etapa-3

## Resultados verificáveis

| Indicador | Resultado |
| --- | --- |
| Redução de chamadas ao LLM | **66,67%** — 15 para 5 no benchmark DEV |
| Redução na latência média por execução | **35,34%** — 2.396,87 para 1.549,93 ms |
| Redução do custo estimado de LLM no lote | **66,67%** — US$ 0,000675 para US$ 0,000225 |
| Trade-off | Consultas Airtable aumentaram de 15 para 20 (+33,33%) |
| Demonstração integrada em 23/11 | Classificação positiva, alerta negativo no Slack, deduplicação antes do LLM e HTTP 403 para webhook sem autenticação |

**Base de comparação:** 15 requisições sintéticas e sequenciais por versão, com 10 duplicatas. A validade estrutural foi 100% no lote; **a acurácia semântica desse benchmark não foi medida**. Em avaliação separada de cinco exemplos rotulados, a acurácia conjunta foi 80%, abaixo da meta de 90%. Os resultados não representam produção, retorno financeiro ou economia total de infraestrutura.

## Valor para o negócio

O protótipo demonstra a viabilidade de **centralizar sinais de insatisfação**, **encaminhar críticas rapidamente** e **reduzir processamento redundante**. A solução também traz código versionado, ambientes de desenvolvimento isolados, sanitização antes do LLM e documentação técnica para manutenção. O valor de negócio projetado depende de validação com clientes reais e medição de tempo de resposta — **ainda não demonstradas**.

## Riscos e decisão proposta

A solução é adequada a uma **demonstração acadêmica com dados sintéticos**, não a um rollout irrestrito. Há limites de autenticação (senha única), sanitização baseada em padrões, armazenamento do texto original no Airtable DEV e possibilidade de corrida em envios concorrentes. **Recomendação:** manter a demonstração isolada e avançar apenas após validar segurança, governança de dados, métricas de qualidade e operação com um piloto autorizado. O orçamento-alvo de US$ 100/mês do briefing não foi demonstrado para um piloto real.
