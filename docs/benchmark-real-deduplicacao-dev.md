# Benchmark real de deduplicação antecipada — DEV

**Estado final em 23/11/2026: benchmark real DEV concluído pelo responsável.**
Benchmark ID: **`097ec2ffc37c4e4081bb54d9a0c174c0`**, coleta original local em
`router-benchmark-local-02/`. `plan.json`, 30 registros e 30 envios foram conferidos;
o resultado existente coincide com o recálculo offline por
`scripts/router_real_benchmark.py`. Nesta consolidação não houve novas chamadas
externas, alteração de workflows ou execução de outro lote.

## Resultado real consolidado

| Métrica | Antes | Depois |
| --- | ---: | ---: |
| Requisições / terminais | 15 / 15 | 15 / 15 |
| Sucessos / duplicatas / falhas | 5 / 10 / 0 | 5 / 10 / 0 |
| Chamadas LLM / respostas | 15 / 15 | 5 / 5 |
| GETs Airtable antecipados / finais / total | 0 / 15 / 15 | 15 / 5 / 20 |
| Registros persistidos | 5 | 5 |
| Tokens entrada / saída | 1611 / 294 | 537 / 98 |
| Custo estimado LLM (USD) | 0,000675 | 0,000225 |
| Latência média (ms) | 2396,87 | 1549,93 |
| p50 / p95 / p99 (ms) | 1950 / 5770 / 5770 | 695 / 3437 / 3437 |
| Validade estrutural | 100% (15/15) | 100% (5/5) |
| Acurácia persistida | Não avaliada | Não avaliada |

**66,67% menos chamadas LLM e custo estimado; 35,34% menos latência média.**
Cinco GETs adicionais (+33,33%); mesmas quantidades de persistência/duplicatas,
zero falhas neste lote e reconciliação de 100% por variante. Custos e durações
têm cobertura completa; custo médio por classificação conhecida de US$ 0,000045
em ambas. Reduções são `(antes − depois) / antes × 100`, usando valores não
arredondados (médias 2396,866666… e 1549,933333… ms).

Não houve snapshot de classificação persistida (0 avaliados, 5 desconhecidos por
versão): **não afirmar equivalência semântica nem acurácia**. A lista vazia de
casos divergentes no JSON acompanha `persisted_cases_compared=0`, não cinco
classificações iguais. A avaliação separada de cinco exemplos, com conjunta 80%,
pertence à coleta operacional de 11 runs e não foi aplicada a este benchmark.
Validade estrutural permanece independente. Zero falhas no lote não comprova
taxa de operação normal/produção; a amostra é sintética, limitada e sequencial.

Evidência pública sanitizada: [HTML](evidencias/benchmark-dev-real.html),
[agregados JSON](evidencias/benchmark-dev-real.json),
[amostras numéricas](evidencias/benchmark-dev-amostras.json) e
[manifesto com hashes](evidencias/etapa-2-evidencias-manifesto.json).
Logs, destinos, referências de credenciais e planos completos continuam locais.
Reproduzir a consolidação **sem chamadas**:

```powershell
python scripts/export_etapa2_evidence.py
python scripts/export_etapa2_evidence.py --check
```

O primeiro comando exige as coletas locais originais e verifica o resultado
antes de exportar apenas campos permitidos. O segundo usa somente os artefatos
do repositório, confere hashes, recalcula métricas das amostras numéricas e
reconstrói os HTMLs. Hashes demonstram consistência, não autenticação independente.
Não é necessário repetir o benchmark real para apresentar ou conferir a entrega.

A coleta de 11 runs e o [dashboard de qualidade separado](evidencias/router-observabilidade-dev-real.html)
não são um par deste benchmark. A evidência de 120 eventos continua
[exclusivamente offline](etapa-2-otimizacao-v4.md).

## Desenho e controles

Duas cópias **novas, inativas e sem credenciais**, fora dos workflows atuais:

| Cópia em `n8n-mirror/benchmarks/` | Comportamento | Webhook local exclusivo |
| --- | --- | --- |
| `router-before-benchmark-dev.json` | Baseline: sanitização → configuração DEV → LLM → deduplicação final → persistência se novo → Slack CX quando negativo | `/webhook/benchmark-router-before-dev` |
| `router-after-benchmark-dev.json` | Mesma lógica do Router observável atual, com precheck antes do LLM e verificação final preservada | `/webhook/benchmark-router-after-dev` |

`scripts/build_router_benchmark.py` parte do **export observável atual**. No
baseline, restaura a ordem LLM antes da deduplicação de `vozdocliente-router-v4.json`;
não importa a configuração histórica PROD. Remove o precheck/decisão antecipada
e sua instrumentação, ajustando o contexto do início do LLM. Conserva configuração
DEV, sanitizador, modelo, prompt, parser, verificação final, HTTP sem retries/
redirects, saídas de erro seguras, observador e Stop And Error. O Router atual
não é modificado. Sem consulta antecipada, o baseline não detecta indisponibilidade
do Airtable antes do LLM; a verificação final continua falhando fechada.

Ambas recebem o mesmo adaptador de benchmark: entrada restrita às fixtures,
captura mínima e resposta final. A única diferença de negócio é a deduplicação
antecipada; IDs de nodes, caminhos e namespaces diferem para isolamento.

As cinco avaliações em `n8n-mirror/benchmarks/cases.json` são sintéticas, sem PII,
uma por tema, com rótulos esperados. A ordem é **1, 2, 3, 4, 5, repetida três vezes**:
**15 requisições por versão**, sequenciais. Texto, rating, marcador sintético de
cliente e source são idênticos; mudam somente IDs/metadados técnicos.

Cada plano gera UUID novo e dez IDs: `BMR-<uuid>-before-01` até `05` e
`BMR-<uuid>-after-01` até `05`. Não limpa a tabela nem exclui registros existentes.
Os cinco primeiros envios de cada versão exigem sucesso/persistência; duplicata
nessa primeira passagem indica colisão/interferência e aborta o lote. As demais
passagens exigem duplicata sem nova persistência. Executar sem outros produtores
concorrentes na tabela DEV durante o par. Plano usado não pode ser repetido.

## Coleta e conclusão

O webhook habitual responde no início. **Não se usa esse ACK nem o tempo HTTP
como latência.** Nas cópias, `responseMode=responseNode`: a resposta de sucesso
é o **último node**, após negócio (inclusive Slack CX aplicável), evento terminal
e retorno do observador. O executor aguarda o pacote final validado antes do
próximo POST. As estatísticas usam exclusivamente **`report.duration_ms`** do
contrato existente: de `obsStart` ao terminal. Guard inicial e entrega posterior
do observador ficam fora dessa duração nas duas versões.

Uma falha operacional responde com pacote permitido e segue para Stop And Error;
o executor aborta e não envia outro evento. Timeout, ACK antecipado, pacote inválido
ou resposta perdida também abortam, **sem retry/resume**. Uma resposta perdida pode
ocorrer após gravação: não presumir ausência de registro; preservar a coleta parcial
e preparar novo plano/namespace.

Não depende de histórico de execuções: salvamento de payloads continua desabilitado,
sem polling de dados de execuções. Confirma término do processamento de negócio
pela resposta final, sem alegar auditoria do encerramento interno do engine.
A API local lê somente as definições das cópias no preflight.

Não habilita logs globais/`CODE_ENABLE_STDOUT`. Coleta apenas run ID técnico,
lote/caso/sequência, contadores, tempos, custos e enums confirmados na resposta
de criação do Airtable. Sem texto original/LLM, nomes, record IDs, headers,
credenciais ou erros brutos. Destinos/preços são conferidos em memória; os
identificadores de configuração/credenciais persistidos são hashes.

## Reprodução futura, somente se um novo ensaio for autorizado

Python 3.12+, Node.js 22+ para testes VM; sem pacotes adicionais. Comandos na raiz.
**`prepare`, `report` e testes são offline. Só `run --execute-real-dev` executa
chamadas reais. O par acima já foi realizado; os comandos seguintes documentam
um novo ensaio, não foram executados nesta consolidação.** Não reutilizar
`router-benchmark-local-01` (aborto com marcador) ou `local-02` (concluído).

### 1. Conferir e preparar offline

```powershell
python scripts/build_router_benchmark.py --check
python -m unittest discover -s tests -v
node tests/test_router_real_benchmark.cjs
python scripts/router_real_benchmark.py prepare --output-dir router-benchmark-local-03 --dev-base-id "<APP_DEV_VALIDADO>" --dev-table-id "<TABELA_DEV_VALIDADA>" --dev-slack-channel-id "<CANAL_SLACK_DEV_VALIDADO>"
```

Substituir os três identificadores pelos recursos DEV conferidos, sem tokens.
`prepare` não lê `.env`, não acessa rede e não cria dados no Airtable. Gera
`plan.json` e duas cópias de importação em pasta nova, sem sobrescrever. O plano
vincula UUID, ordem, fixtures e hashes dos workflows/Router de origem. Pastas
de raiz `router-benchmark-local*` são ignoradas pelo Git.

### 2. Importar/publicar somente as duas cópias locais

1. Usar **`http://127.0.0.1:5678`**, instância de classificação DEV. Importar os
   dois JSONs de `router-benchmark-local-03` **como workflows novos**. Não substituir
   o Router atual nem importar a v4 histórica neste ensaio.
2. Selecionar as **mesmas credenciais DEV** nos nodes correspondentes: OpenAI,
   Airtable e Slack; precheck e busca final com a mesma credencial. Confirmar
   base/tabela com schema completo da classificação e canal DEV. O nome de uma
   credencial sozinho não comprova isolamento.
3. Conferir o ambiente n8n existente: `CLASSIFIER_ENV=DEV`, IDs
   `CLASSIFIER_DEV_BASE_ID`, `CLASSIFIER_DEV_TABLE_ID`, `CLASSIFIER_SLACK_DEV_CHANNEL_ID`
   iguais ao plano; `ROUTER_OBSERVER_WORKFLOW_ID` válido, apontando ao observador
   DEV já validado. O guard rejeita divergência **antes de qualquer HTTP externo**.
   Sem fallback PROD e sem alteração nos workflows atuais.
4. Congelar modelo, prompt, parâmetros, credenciais, observador/opt-in P1 e
   configuração durante todo o par. Conferir os preços existentes em
   `OBS_LLM_INPUT_USD_PER_MILLION` e `OBS_LLM_OUTPUT_USD_PER_MILLION`; anotar
   data/fonte aplicável. O script não busca/inventa preços. Ausência de preço ou
   usage gera custo desconhecido e impede calcular sua redução.
5. Preservar salvamento de sucesso/erro/manual/progresso desabilitado. Não habilitar
   logs globais. Publicar **somente as duas cópias locais**, anotar seus IDs.
   `/webhook/` é uma rota de localhost, não Railway/PROD. Não criar agendas,
   publicar ou alterar os originais.

O preflight lê as definições pela API local e confere grafo, parâmetros,
proteções, referências iguais de credenciais e estado publicado. Rejeita versão
salva/publicada divergente quando esses IDs são expostos pela API. Não corrige
divergências automaticamente. Conferir na UI as duas versões publicadas e o
suporte ao Respond to Webhook nessa instância antes do primeiro par: a VM não
substitui validação de importação/engine. No n8n 2.28.7, defaults podem ser omitidos
ao importar/exportar; o comparador os recompõe somente em memória por tipo/versão
comprovados. `onError` ausente equivale a `stopWorkflow` apenas nos quatro nós
do adaptador, com `continueOnFail` ausente/`false`. Código/expressões, conexões,
políticas operacionais, retries, timeouts, credenciais e retenção continuam verificados.
Retenção ausente não é normalizada: restaurar erro/sucesso=`none`, manual/progresso=
`false`, salvar e republicar. Essas configurações foram verificadas nas duas
cópias publicadas antes do benchmark concluído.

### 3. Executar o par real sequencial

Usar uma chave da **API local n8n**, com leitura das duas cópias. Ela serve ao
preflight, não é token de provedor. Carregar no ambiente do processo sem gravá-la
no plano/repositório nem revelá-la no terminal:

```powershell
$env:N8N_BENCHMARK_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Chave da API local n8n' -AsSecureString)).Password
python scripts/router_real_benchmark.py run --plan router-benchmark-local-03/plan.json --before-workflow-id "<ID_BASELINE_LOCAL>" --after-workflow-id "<ID_OTIMIZADO_LOCAL>" --execute-real-dev
Remove-Item Env:\N8N_BENCHMARK_API_KEY
```

Aceita somente HTTP loopback na porta 5678, desabilita proxies/redirects e não
retransmite a chave ao webhook. Não aceita Railway, host remoto ou outra porta.
O n8n fará chamadas reais aos fornecedores DEV **nessa execução futura**.
No caminho saudável, haverá dez registros novos e poderão ocorrer quatro mensagens
CX no Slack DEV (dois casos negativos novos por versão); P1 mantém o opt-in em falhas.

`started.json` reserva o plano antes de qualquer POST, inclusive se o preflight
reprovar. `session.json` registra os hashes conferidos; `dispatch.ndjson` é
gravado/flush antes de cada POST e registra **tentativas**, não comprova aceite.
`records.ndjson` recebe somente respostas finais válidas e correlacionadas.
Falhas não são reenviadas, nem resultados de pares distintos são misturados.
Os contadores agregam somente os terminais recebidos; um envio sem resposta
permanece inconclusivo, não é convertido em zero chamadas, consultas ou custo.

### 4. Gerar o comparativo offline

```powershell
python scripts/router_real_benchmark.py report --plan router-benchmark-local-03/plan.json --records router-benchmark-local-03/records.ndjson
```

Abrir `router-benchmark-local-03/report.html`; `report.json` contém os mesmos
indicadores estruturados. Não sobrescreve relatórios. Lote parcial pode gerar
diagnóstico, mas não aprova o par nem calcula reduções. Indicadores sem dados
ficam não medidos. Manter arquivos locais e revisar antes de compartilhar.

Depois, despublicar somente as cópias na UI. Os registros novos permanecem no DEV;
não há DELETE. Para repetir, usar outra pasta/plano, por exemplo
`prepare ... --output-dir router-benchmark-local-04 --first after`, com os mesmos
IDs DEV confirmados. Reutilizar as duas cópias, sem importar webhooks concorrentes.
Cada par tem UUID novo. Não completar um par com resultados de outro.

## Métricas e trade-offs

| Medida | Cálculo e cobertura |
| --- | --- |
| Chamadas LLM | `llm_calls_attempted` e respostas do terminal, separadas; tentativa não comprova faturamento. |
| Consultas Airtable | Marcadores existentes de início de precheck e busca final; separa os dois tipos. São tentativas de GET, não incluem POSTs de criação nem comprovam fatura. |
| Tokens | Prompt/completion do usage; total somente se todos conhecidos; subtotais conhecidos e cobertura separados. |
| Custo | Subtotal conhecido, cobertura e média **por classificação com custo conhecido**; total `null` se alguma chamada tem custo desconhecido. Zeros de duplicatas sem LLM não diluem a média. Estimativa LLM não é fatura/custo total. |
| Latência | Média e p50/p95/p99 nearest-rank de `report.duration_ms` conhecido, incluindo duplicatas; N conhecido/desconhecido explícito. Não é tempo HTTP ou inferência isolada. |
| Volume | Tentativas do journal versus terminais correlacionados, além dos 15 previstos por versão; sem journal, reconciliação não aferida. |
| Persistência/duplicatas | Soma de `persisted` confirmado e status `duplicate`; timeout de criação não prova ausência de gravação. |
| Validade estrutural | `classification_valid / llm_responses` conhecidas, incluindo classificações desperdiçadas no baseline; independente da acurácia. |
| Qualidade persistida | Enums confirmados na resposta de criação versus ground truth das cinco fixtures; sentimento, tema, conjunta, cobertura e casos divergentes entre versões. Snapshot ausente é desconhecido. Sem releitura independente do Airtable. |
| Reduções | `100 × (antes − depois) / antes`; só em par completo saudável com configuração consistente. Custo exige cobertura completa e denominador positivo; subtotal parcial não gera alegação de economia. |

**Expectativas teóricas**, não resultados medidos nem preenchimento de ausências:

| Operação no lote de 15 | Antes | Depois |
| --- | ---: | ---: |
| Tentativas LLM | 15 | 5 |
| GETs antecipados | 0 | 15 |
| GETs finais | 15 | 5 |
| GETs Airtable totais | 15 | 20 |
| Criações confirmadas | 5 | 5 |
| Duplicatas | 10 | 10 |

Trade-off esperado: **10 chamadas LLM evitadas (66,67%)** por **5 GETs Airtable
adicionais (+33,33% nas consultas)**. Com os cinco POSTs, as operações Airtable
passam de 20 para 25 (+25%). O precheck acrescenta consulta, latência e exposição
a limites/indisponibilidade do Airtable para cada caso novo. Duplicatas evitam
LLM e busca final. A verificação final impede persistir duplicata surgida durante
o LLM, mas leitura/criação continuam sem atomicidade: corridas não foram eliminadas.

Não monetizar consultas adicionais sem tarifa/medição aplicável. Economia LLM
não garante redução do custo total ou da latência dos casos novos. Usage e saídas
podem variar mesmo com o mesmo modelo/prompt; não presumir redução de custo igual
à de chamadas. Não declarar qualidade preservada só por JSON válido/cinco registros.

Com N=15, p95/p99 escolhem o máximo. A amostra é pequena, sintética, sequencial,
com proporção artificial de 2/3 de duplicatas. Cache, rede, tempo e ordem das versões
podem influir; repetir pares com ordem invertida/IDs novos antes de generalizar.
Não mede concorrência, disponibilidade ou produção. Interpretar os
[thresholds DEV](etapa-2-observabilidade-router.md#thresholds-iniciais-dev-e-resultados-observados)
com essas limitações.

## Testes da preparação

A suíte Python cobre geração/preservação, carga/isolamento, sequência, uso único,
preflight, validação da coleta, duplicatas, reconciliação, falhas parciais e
custos desconhecidos. A VM executa ambos os grafos com mocks e testa contadores,
qualidade, entradas restritas e falhas seguras. Não gera evidência simulada como
real nem valida engine/fornecedores. CI executa somente verificações offline,
sem comando `run`, segredo ou deploy.
