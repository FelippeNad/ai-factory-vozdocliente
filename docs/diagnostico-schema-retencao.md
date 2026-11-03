# Diagnóstico local de `SCHEMA_INVALID` na retenção

O diagnóstico não muda o schema esperado nem executa rede, DELETE, criação de
auditoria, alteração de credenciais ou leitura de `.env`. Os metadados reais da
execução relatada não estão disponíveis no repositório. A conclusão abaixo se
baseia no código versionado e numa reprodução sintética, não em inspeção da base.

## Causa do bloqueio por nome e correção configurável

Em [common.js](../n8n-mirror/retention/common.js), `checkSchema` seleciona tabelas
pelos IDs de `config.table` e `config.auditTable`, **depois** compara nomes exatos:

```javascript
const reviews = body.tables.find(table => table.id === config.table);
const audit = body.tables.find(table => table.id === config.auditTable);
if (reviews?.name !== config.tableName || audit?.name !== 'RetentionAudit') return false;
```

A versão anterior exigia o literal `Reviews`, causando o bloqueio relatado para
`ReviewsRetentionTest` mesmo com todos os tipos corretos. Agora `settings` lê
`RETENTION_TABLE_NAME`, com padrão `Reviews` **somente quando ausente**, e guarda
o nome em `config.tableName`. Configurar `ReviewsRetentionTest` e manter seu ID
permite a tabela isolada, sem renomeá-la. Apenas ajustar `RETENTION_TABLE_ID` não
muda o nome esperado. A comparação é sensível a maiúsculas; não há aliases ou
normalização. Valor vazio, não textual, acima de 255 caracteres, com espaços nas
extremidades ou controles/invisíveis bloqueia já na configuração.

A base e as duas tabelas continuam obrigatórias por ID; nomes não substituem IDs
nas URLs. A auditoria mantém o nome literal `RetentionAudit` e os 18 pares de
nome/tipo. O guard revalida a configuração, incluindo o nome, antes de cada operação.

O [motor](../n8n-mirror/retention/engine.js) emite `SCHEMA_INVALID` somente na ação
`schema`, depois de resposta HTTP 2xx, quando `checkSchema` retorna `false`.
`schema_verified` continua falso, então `auditOrFinish` encerra sem criar auditoria.
Por isso são esperados zero registros analisados/excluídos e `audit_persisted=false`.
Isso não aponta, por si, para problema de permissão de escrita na auditoria.

## Todas as condições que retornam `false`

| Etapa | Condição de rejeição | Categoria |
| --- | --- | --- |
| Envelope | Body ausente/falso ou `body.tables` não é array; inclui JSON mantido como string ou nível errado do envelope | Estrutura/configuração de resposta |
| Estado | `config.tableName` ausente, não textual ou inválido (defesa adicional; `settings` já impede esses valores no início) | Configuração |
| Seleção | ID de `config.table` ou `config.auditTable` não encontra tabela; ID trocado ou apontando para outra tabela pode falhar aqui/na comparação seguinte | Configuração de seleção |
| Nomes | Tabela de reviews selecionada não se chama exatamente `config.tableName` ou auditoria não se chama `RetentionAudit` | Nome |
| Campos | `reviews.fields` ou `audit.fields` não é array | Estrutura |
| Review | Quantidade de campos que atendem **simultaneamente** `name === 'processed_at'` e `type === 'dateTime'` é diferente de **1** | Nome, tipo ou quantidade de correspondências |
| Auditoria | Algum dos 18 pares de `AUDIT_TYPES` não tem **ao menos uma** correspondência exata de nome e tipo | Nome ou tipo; campo obrigatório ausente |

A função retorna no primeiro erro. O novo comparador coleta também as divergências
de campos após um erro de nome, sem usar esse diagnóstico para autorizar operações.

Os formatos dos IDs e as variáveis de segurança são checados antes, em `settings`:
uma falha ali produz `CONFIG_INVALID`, não `SCHEMA_INVALID`. Falhas HTTP não 2xx
produzem códigos de transporte. Elementos malformados como `null` dentro de
`tables`/`fields` podem lançar exceção no código atual em vez de retornar `false`;
o comparador distingue essa situação, sem apresentá-la como mais uma rejeição normal.

## Contrato exato de campos

| Tabela esperada | Campos | `type` exigido |
| --- | --- | --- |
| `RETENTION_TABLE_NAME` (padrão `Reviews`) | `processed_at` | `dateTime` |
| `RetentionAudit` | `run_id`, `mode`, `status`, `error_codes` | `singleLineText` |
| `RetentionAudit` | `retention_days`, `analyzed`, `eligible`, `deleted`, `failures`, `invalid_dates`, `recent`, `pages`, `attempted`, `skipped_changed`, `unknown_outcome` | `number` |
| `RetentionAudit` | `cutoff`, `started_at`, `updated_at` | `dateTime` |

O código verifica `type === 'dateTime'`, **não** `date` nem uma fórmula cujo resultado
seja uma data. Para texto, `singleSelect`, `multilineText` e `autoNumber` não equivalem
a `singleLineText`; `currency`/`count` não equivalem a `number`.

Não verifica `options`, Include time, `timeZone`, `dateFormat`, `timeFormat`,
`precision`, `primaryFieldId`, ID de cada campo ou nome de view. A interface com
Include time ativado não substitui a inspeção de `fields[].type` da resposta efetiva.
Não há requisito adicional de opções para `dateTime` nesse validador.

**Não exige quantidade total exata de campos.** Reviews pode ter outros campos e
a auditoria pode ter campos extras. Os 18 pares obrigatórios precisam existir;
não basta ter qualquer conjunto de 18 campos. A auditoria usa `some`: duplicatas
não são rejeitadas se existir um par correto. Na review, duas correspondências
`processed_at/dateTime` falham, mas dois nomes iguais com apenas um `dateTime`
passam pela regra atual. Esses detalhes são descrição do código, não sugestões
para criar duplicatas ou enfraquecer o contrato.

## Comparador local

[diagnosticar_schema_retencao.cjs](../scripts/diagnosticar_schema_retencao.cjs)
carrega `checkSchema`, `expectedTableName` e `AUDIT_TYPES` do **JSON exportado v1**, sem executar o motor
ou guard. Mostra nomes/tipos esperados/recebidos, correspondências e categorias;
não imprime IDs, estado completo, headers, descrições, opções ou valores de registros.

Reprodução sintética do nome informado, com todos os tipos corretos:

```powershell
node scripts/diagnosticar_schema_retencao.cjs --demo
```

Resultado: `checkSchema: false`, todos os campos `[OK]` e somente
`NOME_DE_TABELA_INCOMPATIVEL (reviews)`. Exit code **1** é esperado nesse caso;
0 indica schema aprovado e seleção verificada; 2 indica erro de entrada/contrato.
O comparador não executa qualquer operação no Airtable, mesmo se retornar 0.

Para comparar metadados reais reduzidos, guardados somente no ambiente local:

```powershell
node scripts/diagnosticar_schema_retencao.cjs --input <arquivo-local-de-metadados.json>
```

`--json` produz relatório JSON; `--input -` permite ler JSON pela entrada padrão.
Não usar `.env` como entrada, nem salvar export completo de execução no Git.
Se houver somente a resposta HTTP sem o estado de seleção, é possível comparar
provisoriamente por nomes:

```powershell
node scripts/diagnosticar_schema_retencao.cjs --input <metadados.json> --reviews-name ReviewsRetentionTest --audit-name RetentionAudit
```

Nesse modo, `check_schema_result=null` e `IDS_CONFIGURADOS_NAO_VERIFICADOS` indicam
que o comparador não confirmou a seleção pelos IDs da execução. `--reviews-name`
e `--audit-name` selecionam tabelas somente para diagnóstico; não alteram a expectativa.

Quando a captura contém `state.config.tableName` ou a projeção contém
`expected_reviews_name`, esse é o nome esperado usado pelo comparador. Sem esse
campo (captura legada), a saída informa `expected_name_source=default_Reviews`:
é o padrão, não uma leitura do ambiente atual do container. Para uma resposta HTTP
sem estado, pode-se testar a expectativa local explicitamente:

```powershell
node scripts/diagnosticar_schema_retencao.cjs --input <metadados.json> --expected-table-name ReviewsRetentionTest
```

Essa opção não configura o n8n, não comprova IDs e não pode sobrepor um nome
divergente já capturado no estado. Uma captura nova após a atualização deve trazer
o nome configurado. `--demo` continua reproduzindo o caso de **nome padrão Reviews
versus tabela ReviewsRetentionTest**, intencionalmente rejeitado.

Se Node não estiver no PATH desta máquina, o executável usado nos testes está em
`%LOCALAPPDATA%\Programs\Bionic\resources\app\.webpack-bionic\bin\node.exe`.

## O que extrair do n8n, sem segredos ou dados pessoais

1. Na execução **já realizada**, selecionar o run de `Receber resposta` com
   `state.action === 'schema'`. Não selecionar outro run de listagem/releitura nem
   executar de novo o node HTTP apenas para coletar a evidência.
2. Confirmar localmente que os IDs em `state.config.table` e
   `state.config.auditTable` correspondem às tabelas pretendidas. Não enviar IDs,
   base, URL, `.env` ou tokens: bastam os indicadores de correspondência abaixo.
   Extrair também `state.config.tableName` como `expected_reviews_name`; se ausente,
   a captura é legada e o comparador explicitará o padrão `Reviews`.
3. Extrair `response.body.tables[].name` e, para cada tabela selecionada, somente
   `fields[].name` e `fields[].type`, incluindo **todos** os campos de auditoria.
4. Para gerar a projeção, usar
   [extrair_schema_retencao_n8n.js](../scripts/extrair_schema_retencao_n8n.js)
   em um node Code **isolado**, numa cópia de diagnóstico sem HTTP e sem ligação
   ao motor. Alimentá-lo somente com o item já obtido do passo 1 e executar apenas
   o extrator; não reconectar essa cópia ao workflow operacional. A saída remove
   IDs, options, headers, descriptions e estado e inclui flags de seleção. Não
   fixar, compartilhar ou exportar o item completo que serviu de entrada.

Formato reduzido esperado (exemplo parcial, não suficiente para avaliar auditoria):

```json
{
  "kind": "retention_schema_metadata_v1",
  "selection_verified": true,
  "expected_reviews_name": "ReviewsRetentionTest",
  "tables_is_array": true,
  "tables": [
    {
      "name": "ReviewsRetentionTest",
      "selected_reviews": true,
      "selected_audit": false,
      "fields": [{"name": "processed_at", "type": "dateTime"}]
    },
    {
      "name": "RetentionAudit",
      "selected_reviews": false,
      "selected_audit": true,
      "fields": [{"name": "run_id", "type": "singleLineText"}]
    }
  ]
}
```

Não substituir campos faltantes por tipos “esperados” ao extrair: copiar o valor
efetivamente retornado. O comparador aceita o objeto acima ou uma cópia de um único
item n8n que o contenha. O nome de tabela/campo também é metadado: revisar antes de
publicar caso alguém tenha colocado informação pessoal nesses rótulos.

## Correção mínima após confirmar a seleção e a versão

Conferir no `Motor de retencao` importado a condição `reviews?.name !== config.tableName`.
Se ainda houver o literal `Reviews`, a instância usa o código anterior e precisa
reimportar o JSON corrigido. Não editar o validador manualmente nem remover o teste.

No `.env` efetivamente usado pelo Compose dedicado, definir
`RETENTION_TABLE_NAME=ReviewsRetentionTest`, mantendo os três IDs DEV corretos,
`RETENTION_DRY_RUN=true` e as confirmações de DELETE vazias. Recriar somente o
container DEV com o Compose de retenção e `--env-file` explícito; `restart` sozinho
não atualiza variáveis. Reimportar a v1 corrigida como novo workflow inativo,
selecionar a credencial DEV existente e iniciar uma execução completa, sem estado
antigo ou dados fixados. Ver os comandos e cuidados no
[roteiro de atualização local](etapa-2-retencao-exclusao.md#atualizar-uma-instalação-dev-que-rejeitava-reviewsretentiontest).
Não há necessidade de alterar nomes/tabelas no Airtable, credenciais ou v3/v4.

Corrigir divergências adicionais somente depois de diagnosticá-las. Não converter
campos que contêm dados sem avaliar impacto; não mudar `dateTime` para aceitar `date`,
fórmula ou texto. Manter DRY_RUN e confirmações de DELETE vazias. Primeiro repetir
o comparador offline; eventual reexecução operacional em DRY_RUN pode gravar auditoria
e requer os cuidados DEV já documentados. Nenhuma reexecução foi feita nesta análise.

## Verificação realizada

49 casos sintéticos do diagnóstico passaram, incluindo aceitação do nome configurado,
rejeição de nomes divergentes, projeção do nome esperado e reprodução do bloqueio com
todos os tipos corretos, falsos nomes/tipos, seleção ausente/invertida, opções extras,
quantidades, proteção da saída e a execução do motor com transporte em memória.
O caso reproduzido faz apenas um GET **simulado** de schema e não prepara escritas.

```powershell
node tests/test_retention_schema_diagnostic.cjs
python scripts/build_retention_workflow.py --check
```

Os dois exports de retenção foram regenerados a partir das fontes e permanecem
inativos; v3/v4 foram preservados. Não há metadados reais no relatório; a confirmação
completa depende da projeção da execução, com nome esperado e nomes/tipos efetivos.
