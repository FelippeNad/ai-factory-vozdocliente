# Etapa 2 — evitar LLM em duplicatas conhecidas

## Escolha e alcance

A v4 já sanitiza PII e deduplica por `review_id`, mas consulta o Airtable somente
depois da classificação. Uma review existente ainda consome uma chamada LLM cujo
resultado acaba descartado. Não havia precheck, cache ou batching antes do LLM.

A única otimização é um **precheck antes do LLM**, preservando também a consulta
final para detectar duplicatas que aparecem durante a classificação. Não é cache
de respostas nem agrupamento de prompts. Sanitizador, modelo, prompt, JSON Schema
e parser permanecem idênticos aos da v4.

- Antes: `vozdocliente-router-v4.json`, preservado byte a byte como baseline.
- Depois: `vozdocliente-router-v4-otimizado-dev.json`, candidato derivado do fluxo
  principal, **inativo e sem credenciais**, com caminho de webhook próprio.
- V3, PROD, retenção e credenciais reais não foram alterados.

```text
ANTES
Webhook -> Sanitizar PII -> LLM -> Parse + Merge
  -> buscar ID -> duplicata? sim: encerrar / não: gravar -> alerta negativo

DEPOIS (DEV)
Webhook -> Sanitizar PII -> Preparar deduplicacao DEV
  -> Airtable Precheck DEV -> Validar busca e restaurar texto -> Ja existe? DEV
       true: encerrar sem LLM
       false: LLM DEV -> Parse + Merge -> Airtable Buscar review_id
         -> Validar busca final DEV -> Confirmar novo? DEV
              true (duplicata): encerrar
              false: Airtable DEV -> roteamento negativo -> Slack DEV
```

Ambas as consultas pedem somente `review_id`, `maxRecords=1`. Resposta ausente,
malformada, com identidade divergente ou erro bloqueia o fluxo, sem fallback para
o LLM. O texto destinado ao LLM vem **somente do sanitizador**, nunca do Airtable
ou de um campo sanitizado fornecido pelo cliente. Não há cache persistente, hash
de texto pessoal ou novo armazenamento de PII.

## Metodologia reproduzível

`tests/router_optimization_harness.cjs` percorre as conexões dos dois JSONs e
executa seus Code nodes e expressões reais em VMs. HTTP é substituído por funções
em memória: Airtable usa Map; LLM devolve a resposta da fixture para o texto
sanitizado exato; Slack registra a requisição simulada. Sem SDK/cliente HTTP,
leitura de `.env`, sockets ou APIs.

Carga fixa em `tests/fixtures/optimization_load.json`:

- **120 eventos**, 30 IDs opacos sintéticos repetidos quatro vezes, round-robin,
  sequencial. Store vazio em cada variante/lote. Primeira passagem grava 30
  reviews; as demais são duplicatas. Não mede concorrência.
- Seis casos de `pii_semantic_cases.json`: três sentimentos, cinco temas e PII
  sintética. Nenhum dado pessoal real.
- Um lote de aquecimento por variante e **nove pares medidos**, alternando a ordem
  antes/depois. Nenhuma suíte em paralelo ao benchmark.
- `performance.now()` mede tempo real **do harness local por lote**: VMs,
  interpolação, validação, mocks e processamento do grafo. Sem sleeps, atrasos
  artificiais ou latência remota assumida.
- Cada par compara registros completos persistidos e textos dos alertas. O relógio
  das expressões é fixo para `processed_at`; o cronômetro usa o relógio monotônico
  real, não o relógio da fixture.

## Resultados medidos

Execução: **2026-11-03 02:42:44 UTC**, Node **v25.5.0**, Windows x64. Contagens por
lote representam **chamadas simuladas**, não chamadas reais:

| Medida | Antes | Depois |
| --- | ---: | ---: |
| Eventos | 120 | 120 |
| Chamadas LLM simuladas | 120 | 30 |
| Consultas Airtable simuladas | 120 | 150 |
| Gravações simuladas | 30 | 30 |
| Alertas negativos simulados | 20 | 20 |
| Registros persistidos idênticos | 30 | 30 |
| Média local do lote (ms) | 458,654 | 555,445 |
| Mediana local do lote (ms) | 446,538 | 556,454 |
| p95 local do lote (ms) | 525,778 | 615,576 |
| Chamadas reais a APIs/LLM | 0 | 0 |
| Latência real do LLM / produção | Não medida | Não medida |

**90 chamadas LLM simuladas evitadas, redução de 75%.** A checagem final preservada
custa 30 consultas Airtable adicionais. O tempo médio do harness **aumentou
96,791 ms por lote, aproximadamente 21,1%**. Não houve ganho de latência offline.
O mock LLM é quase imediato; validações/nodes adicionais têm custo local.

Não extrapolar para LLM remoto, custo faturado, webhook ou produção. O webhook
original responde no início por padrão; duração do lote também não é tempo de
resposta HTTP do webhook. O p95 de nove amostras é descritivo, não estimativa de
uma distribuição produtiva. A diferença local não possui intervalo de confiança.

O [relatório JSON](evidencias/otimizacao-v4-benchmark.json) registra todas as amostras,
hashes SHA-256 da carga, dos exports, harness e benchmark, parâmetros e flags
`real_external_api_calls=0`, `real_llm_calls=0`, `real_n8n_engine=false`.
As hashes vinculam medição e artefatos; não são assinatura ou prova de autoria.

## Qualidade e PII

Gerador/testes comparam byte a byte o código de `Sanitizar PII`, `Parse + Merge`
e o body inteiro de LLM (modelo, mensagens e schema). Os 30 registros completos e
os textos dos 20 alertas foram idênticos antes/depois. Prompts do mock correspondem
exatamente aos textos sanitizados esperados; campo sanitizado injetado é ignorado.

Testes cobrem ausência de duplicatas, todos os IDs existentes, ID com texto
alterado, resposta de consulta inválida, ambiente/IDs/texto inválidos, saída LLM
inválida e duplicata que aparece durante o LLM e é barrada na checagem final.
O validador rejeita bypass do sanitizador/precheck, gravação sem consulta final,
alteração do prompt/parser, credenciais no export e fallback para base publicada.
A suíte original de PII permanece passando.

Isso demonstra **equivalência sintética**, não acurácia de um LLM real. Não houve
avaliação de modelo remoto, corpus real ou qualidade humana. O input sanitizado,
modelo, prompt e parser iguais para reviews novas preservam os critérios de
classificação; variação estocástica do provedor exige avaliação própria.

## Trade-offs e limites

- Sem duplicatas, chamadas LLM permanecem iguais e há **uma consulta adicional por
  review nova**. Ganho depende das repetições; não prometer economia monetária sem
  preços, tokens e tráfego reais.
- Mais consultas consomem cota e podem aumentar falhas Airtable. Falha interrompe
  o fluxo; não há classificação ignorando deduplicação.
- Consulta final não é transação: continua a corrida entre última leitura e criação.
  Não há lock distribuído, constraint única ou exactly-once.
- `review_id` opaco exige 1–128 caracteres ASCII alfanuméricos, `_` e `-`.
  Espaços/aspas/outros caracteres falham, sem normalização silenciosa. Validar o
  contrato das origens; divergência de ID/capitalização na resposta falha fechada.
- ID reutilizado com texto novo não atualiza o registro, como na v4 original.
  Apenas deixa de calcular a classificação que seria descartada.
- HTTP DEV tem timeout de 15 segundos, sem retry/redirect/continuação em erro.
  Code usa erros fixos; logs/erros da plataforma ainda requerem revisão própria.
- Airtable conserva o original como na v4; regex não garante anonimização. A
  retenção de dados/histórico não foi flexibilizada.

## Reprodução e evidências

Na raiz, sem serviços ou credenciais:

```powershell
python scripts/build_router_optimized_workflow.py --check
python tests/validate_workflows.py
python -m unittest discover -s tests -v
node tests/test_pii_sanitization.cjs
node tests/test_router_optimization.cjs
node scripts/benchmark_router_optimization.cjs
```

O último comando mede novamente sem sobrescrever a evidência. Tempos variam por
máquina/carga. `--write` atualiza `docs/evidencias/otimizacao-v4-benchmark.json`;
atualizar esta tabela quando medição/hashes mudarem. Não executar suítes em paralelo.
CI valida testes/exports, sem exigir ganho de tempo variável.

Para apresentar: mostrar os dois grafos, precheck e consulta final; executar
testes/benchmark; enquadrar flags offline, 120/30 chamadas simuladas e tempo local
**mais lento**. Mostrar hashes e `saved_reviews_identical`, sem abrir `.env` ou
credenciais. Explicar consulta extra e corrida remanescente. Medição futura DEV
precisará separar tempos de Airtable, LLM e fluxo completo, com avaliações
emparelhadas e autorização para APIs; não faz parte da evidência atual.

## Validação local informada e reprodução

Importar o candidato como **novo workflow inativo** em n8n DEV, nunca sobre o
publicado; conferir caminho `review-v4-otimizado-dev`. Versões Code/HTTP/IF foram
reaproveitadas da v4. O responsável informou validação no n8n local dos três
cenários: avaliação nova com classificação, duplicata antes do LLM e falha segura
do precheck. O agente não repetiu APIs nesta auditoria. Essa validação não
abrange a candidata observável posterior, que permanece experimental.

Exige `CLASSIFIER_ENV=DEV`, `CLASSIFIER_DEV_BASE_ID`, `CLASSIFIER_DEV_TABLE_ID` e
`CLASSIFIER_SLACK_DEV_CHANNEL_ID` para alertas negativos. Repassar explicitamente ao
ambiente n8n DEV; escrever no `.env` sozinho não injeta variáveis. O Compose de
classificação da porta 5678 repassa essas variáveis; retenção permanece separada. Selecionar credenciais DEV por serviço após revisão;
nenhuma referência de credencial é exportada. IDs/variáveis não comprovam isolamento.
A tabela DEV precisa do schema completo da classificação; não presumir que a
tabela mínima de teste de retenção seja compatível.

O usuário informou sucesso anterior do Slack DEV (`sent`, erro nulo, logs e
métricas). Isso valida o alerta da retenção, não o Router observável experimental nem
latência real do LLM. O Router otimizado anterior foi validado separadamente
conforme os três cenários informados acima. Nenhuma API externa, alteração produtiva, deploy ou commit nesta entrega.
