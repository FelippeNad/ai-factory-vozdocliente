# Etapa 2 — retenção e exclusão periódica

Complemento documental após `718ce4d`: [mapa e retenções por destino](lgpd/mapa-dados-pessoais.md),
[checklist LGPD](lgpd/checklist-etapa-2.md), [procedimento de rotação](security/rotacao-credenciais.md)
e [roteiro de evidências](lgpd/roteiro-evidencias.md). A captura agora versionada
`evidencias/etapa2-retencao-dry-run.png` mostra o percurso com stub Code; não
comprova DELETE ou auditoria em base real. O briefing limita logs a 90 dias,
distinto dos prazos demonstrativos descritos abaixo e sujeito à verificação real.

O usuário informou sucesso operacional DEV em `retention-6` (4 analisados,
2 elegíveis, 0 excluídos/falhas, 2 páginas e auditoria persistida/finalizada).
A nova [observabilidade DEV](etapa-2-observabilidade.md) reaproveita esse resumo;
logs, latência e entrega Slack novos ainda exigem validação manual da importação.

Implementado na branch `etapa-2`, a partir de `f66cb79`, sem alterações nas versões
v3/v4 de classificação. Nenhuma exclusão real, chamada a APIs, alteração de
credenciais, ativação, deploy ou commit foi realizado nesta implementação.

## Finalidade e alcance da política

Reduzir o tempo de armazenamento das avaliações identificáveis que já não precisam
permanecer na fila operacional. O parâmetro inicial é **30 dias demonstrativos**,
não uma exigência legal. O responsável pelo tratamento precisa aprovar um prazo
adequado à finalidade, obrigações aplicáveis, tratativas abertas e eventuais deveres
de preservação antes de habilitar exclusão. Este mecanismo não toma essa decisão.

A exclusão remove o registro inteiro da tabela DEV selecionada por ID (nome esperado
em `RETENTION_TABLE_NAME`, padrão `Reviews`), incluindo nome e texto original.
Ela não anonimiza registros, não atende automaticamente todos os direitos do
titular e não apaga mensagens Slack, dados no LLM, histórico n8n, cópias na origem,
lixeira ou backups. Remover identificadores diretos não torna um dado anônimo.

Dois artefatos independentes e **inativos**:

- `n8n-mirror/workflows/vozdocliente-retencao-v1.json`: mecanismo operacional,
  restrito à base DEV configurada, com transporte HTTP real e DRY_RUN padrão.
- `n8n-mirror/workflows/vozdocliente-retencao-demo.json`: demonstração totalmente
  offline; nenhum node HTTP, nenhuma credencial e DRY_RUN fixo. A API e a auditoria
  são simuladas em memória, usando a mesma política e o mesmo grafo operacional.

## Campo de data e critério de elegibilidade

Se a execução retorna `SCHEMA_INVALID` antes da listagem, consultar o
[diagnóstico de schema](diagnostico-schema-retencao.md). A v1 exige o nome exato
configurado em `RETENTION_TABLE_NAME` (padrão `Reviews`) e o nome fixo
`RetentionAudit`, além da seleção por ID e dos tipos de campos. Para usar a tabela
isolada existente, configurar `RETENTION_TABLE_NAME=ReviewsRetentionTest` e seu ID;
não é necessário renomear tabelas nem alterar o schema da classificação.

A v3/v4 produz `processed_at` com `new Date().toISOString()`. O schema do projeto
documenta **Date com horário**. Segundo a
[documentação de datas do Airtable](https://support.airtable.com/articles/1819632575-date-field-type),
a API retorna ISO 8601 em UTC, independentemente da apresentação na interface.
O workflow não supõe que uma string visível como `02/11/2026` seja o valor da API:
consulta os metadados e exige campo `processed_at` de tipo **`dateTime`**, não
`date`, texto ou fórmula. Não foi consultada a base real nesta sessão; essa
verificação ocorrerá a cada execução operacional.

O instante de referência é fixado no início da execução:

```text
cutoff = início_UTC - RETENTION_DAYS × 24 horas
elegível ⇔ processed_at válido e estritamente anterior ao cutoff
```

Datas no instante exato do limite são mantidas. Datas recentes, ausentes,
impossíveis, locais sem fuso ou futuras não são excluídas. O parser verifica
calendário, ano bissexto, hora e fuso antes de aceitar `Date.parse`; não aceita a
normalização silenciosa de 30 de fevereiro. Datas inválidas são contadas como
falhas de qualidade e não impedem a análise dos demais registros. Se o lote contém
registros inválidos, o resultado é `partial`, mesmo no DRY_RUN.

O prazo usa o processamento, conforme solicitado; não necessariamente a criação
ou o último contato do cliente. Reprocessar uma avaliação pode renovar esse prazo.

## Funcionamento e barreiras de exclusão

```text
Schedule Trigger (03:00, America/Sao_Paulo)
  -> Motor de retenção
  -> espera de 1 segundo
  -> Validar operação DEV
  -> Há operação segura?
     sim -> Operação com body?
              sim -> HTTP auditoria (POST/PATCH, Send Body=true)
              não -> HTTP sem body (GET/DELETE, Send Body=false)
            -> Receber resposta -> Motor de retenção
     não -> Resumo sem PII
```

O motor percorre os estados de metadados, listagem, auditoria inicial, releitura,
DELETE e atualização da auditoria. O guard constrói cada URL/método autorizado;
não recebe um endpoint arbitrário do webhook. Há dois nodes de transporte, domínio
fixo `https://api.airtable.com`, redirects desativados e timeout de 15 segundos.

O HTTP Request **4.1** declara `sendBody` como booleano com
**`noDataExpression: true`**. A expressão usada anteriormente nesse parâmetro era
incompatível com o contrato do node; explicitar apenas `contentType=json` não
corrigia esse erro. A condição `={{ $json.request.body !== undefined }}` foi movida
para o IF **`Operacao com body?`**, após as barreiras de segurança existentes:

- `Airtable DEV operacao`: `sendBody: true` **literal**, `contentType: json`,
  `specifyBody: json`, `jsonBody: ={{ JSON.stringify($json.request.body) }}`.
  Recebe POST/PATCH de auditoria e envia o envelope completo `{"fields": {...}}`.
- `Airtable DEV sem body`: `sendBody: false` **literal**, sem parâmetros de payload.
  Recebe GET de metadados/listagem/releitura e DELETE já autorizado pelo guard.

Os dois nodes retornam para `Receber resposta`; nenhum contorna Motor, guard ou
`Ha operacao segura?`. A validação estrutural rejeita expressões em `sendBody`,
booleanos incorretos, formato diferente de JSON, serialização sem envelope,
inversão de ramos ou bypass das barreiras por qualquer um dos transportes.

Reimportar a v1 regenerada como novo workflow inativo e selecionar a **mesma
credencial DEV existente nos dois nodes HTTP Airtable**. O Slack opt-in usa sua
própria credencial DEV, conforme documentação de observabilidade. Não reutilizar o node antigo que
mantinha `sendBody` como expressão. A DEMO também foi regenerada: os dois transportes
são Code, sem HTTP ou credenciais, mantendo os mesmos resultados sintéticos.

### Evidência local do contrato HTTP Request

Foi consultado somente o container `vozdocliente-retencao-dev`, n8n **2.28.7**,
sem acessar PROD, `.env`, credenciais reais ou APIs. No pacote instalado
`n8n-nodes-base`, os arquivos relativos a `dist/nodes/HttpRequest/` confirmaram:

- `HttpRequest.node.js`, linha 28: versão `4.1` usa `HttpRequestV3`.
- `V3/Description.js`, linhas 340–345: `sendBody`, `type: 'boolean'`,
  `default: false`, `noDataExpression: true`.
- `V3/Description.js`, linhas 351–354 e 467–472: os parâmetros de body dependem
  de `sendBody: [true]`, além do formato JSON.
- `V3/HttpRequestV3.node.js`, linhas 169 e 262–273: lê `sendBody` com default falso;
  só monta o body com envio habilitado e usa o JSON completo informado.

Também foi executado `HttpRequestV3.execute()` instalado, com os parâmetros dos
dois nodes exportados, contexto de teste, credencial **sintética** e helper HTTP
substituído por transporte em memória. Foram bloqueados `http`/`https`, conexão
TCP, `dns.lookup` e `fetch` nesse processo. Os quatro casos passaram: POST/PATCH com `fields`,
GET/DELETE sem propriedade `body`, zero chamadas de rede. Isso valida o contrato
e a montagem da requisição pelo código instalado, **não** uma importação na UI,
uma execução persistida na engine ou integração com Airtable real. As referências
de linha são específicas do pacote inspecionado, não de todas as versões n8n.

1. **Configuração:** exige `RETENTION_ENV=DEV`, IDs válidos e distintos para
   a tabela de reviews e `RetentionAudit`, base DEV explícita e ausência dela na denylist.
   Nunca usa `AIRTABLE_BASE_ID` da classificação como fallback.
2. **Schema:** confirma o nome esperado configurado e o nome fixo `RetentionAudit`,
   `processed_at=dateTime` e os 18 pares de nome/tipo da auditoria antes de ler avaliações.
3. **Seleção:** solicita apenas ID técnico e `fields[]=processed_at`. Pagina por
   `offset`, codificando o token como query parameter. Não baixa nome, texto,
   telefone ou e-mail. Não filtra por data no servidor: assim conta recentes e
   campos ausentes também, dentro do limite de leitura.
4. **Integridade da leitura:** todas as páginas precisam terminar antes de qualquer
   DELETE. Offset repetido/inválido, registro repetido/malformado, página excessiva
   ou limite de leitura bloqueiam o lote inteiro. Não exclui enquanto pagina.
5. **Auditoria prévia:** grava `planned` em `RetentionAudit` antes de qualquer
   DELETE. Falta de permissão, schema ou confirmação dessa gravação impede excluir.
   No DRY_RUN, grava apenas o resultado agregado da simulação.
6. **Releitura:** consulta cada candidato via listagem filtrada por `RECORD_ID()` e
   apenas `processed_at`. Se o registro sumiu ou sua data mudou, pula a exclusão.
   Continua exigindo a mesma data antiga e o mesmo cutoff.
7. **Exclusão:** somente `RETENTION_DRY_RUN=false` literal, ambiente DEV, denylist
   não vazia, confirmação exata da base e frase de confirmação habilitam DELETE.
   O guard revalida a configuração em cada operação. Campos vazios/omitidos
   mantêm DRY_RUN; booleanos malformados como `FALSE` ou `0` bloqueiam o fluxo.
8. **Checkpoint:** confirma `{id, deleted: true}`, contabiliza e atualiza a auditoria
   antes de avançar. Uma falha de DELETE ou checkpoint interrompe novas exclusões.

Não há retry automático. `429`, `4xx`, `5xx`, falhas de rede e respostas inválidas
geram códigos fixos e encerramento controlado. Em DELETE com timeout/5xx ou sem
confirmação, `unknown_outcome` aumenta: o registro pode ter sido removido mesmo sem
confirmação. O mecanismo não afirma que foi excluído e não repete cegamente.

Há intervalo de um segundo entre operações desta execução. A documentação do
[Airtable sobre limites](https://support.airtable.com/articles/7735693959-managing-api-call-limits-in-airtable)
descreve limites compartilhados por base; outras integrações também consomem a
cota. Em `429`, investigar a cota e aguardar antes de nova tentativa; não disparar
reexecuções imediatas em sequência.

## Configuração

Os nomes estão documentados em `.env.example`. IDs reais ficam somente no `.env`
local ignorado pelo Git. Nenhum token novo foi escrito em arquivo ou no workflow.

| Variável | Padrão / condição |
| --- | --- |
| `RETENTION_ENV` | Vazio; precisa ser exatamente `DEV`, inclusive para DRY_RUN operacional |
| `RETENTION_DRY_RUN` | `true` |
| `RETENTION_DAYS` | `30`; inteiro entre 1 e 3650 |
| `RETENTION_DEV_BASE_ID` | Obrigatório; único destino permitido |
| `RETENTION_TABLE_ID` | Obrigatório; ID da tabela de reviews DEV, mesmo ao configurar outro nome |
| `RETENTION_TABLE_NAME` | `Reviews` quando ausente; nome exato da tabela selecionada por ID. Para testes: `ReviewsRetentionTest` |
| `RETENTION_AUDIT_TABLE_ID` | ID distinto da tabela `RetentionAudit` DEV |
| `RETENTION_PROTECTED_BASE_IDS` | IDs proibidos separados por vírgula, sem espaços; obrigatório e não vazio para DELETE |
| `RETENTION_CONFIRM_DEV_BASE_ID` | Vazio no DRY_RUN; deve repetir exatamente o ID DEV para DELETE |
| `RETENTION_DELETE_CONFIRMATION` | Vazio no DRY_RUN; DELETE exige `DELETE_DEV_EXPIRED_REVIEWS` |
| `RETENTION_PAGE_SIZE` | 100; máximo 100 |
| `RETENTION_MAX_PAGES` | 10; teto absoluto 50 |
| `RETENTION_MAX_ANALYZED` | 1000; teto absoluto 5000 |
| `RETENTION_MAX_DELETE` | 10; teto absoluto 100 |

O nome é sensível a maiúsculas e não é normalizado. Valor explicitamente vazio,
não textual, maior que 255 caracteres, com espaços nas extremidades ou caracteres
de controle/invisíveis bloqueia com `CONFIG_INVALID`. Essa é uma restrição local de
configuração, não uma declaração sobre limites da API Airtable. Divergência entre
nome válido configurado e metadados retorna `SCHEMA_INVALID`. O Compose usa
`${RETENTION_TABLE_NAME-Reviews}` para preservar o vazio explícito e permitir esse
bloqueio. O nome é incorporado ao estado; mudanças durante a execução são bloqueadas
pelo guard antes da próxima operação. URLs continuam usando somente IDs.

Exceder `MAX_DELETE` bloqueia **todas** as exclusões daquela execução; não elimina
os primeiros N silenciosamente. O preview é limitado a N IDs/datas com indicador
`preview_truncated`. O motor limita o processamento a dez minutos e tenta finalizar
a auditoria; o workflow tem timeout externo de quinze minutos. O timeout/crash
externo pode impedir essa finalização.

Configurar nos dois nodes HTTP Airtable, pelo editor, a mesma credencial Header Auth **exclusiva DEV**,
com PAT limitado à base DEV e escopos necessários de metadados/leitura/escrita.
Mesmo DRY_RUN precisa escrever a auditoria, mas não emite DELETE para `Reviews`.
O export não referencia IDs nem nomes de credenciais existentes. As palavras DEV
e os IDs em variáveis não provam o ambiente: restringir o PAT à base DEV é a defesa
contra configuração incorreta. Não apontar credenciais de produção para esse node.

Não há instrução de executar exclusões reais nesta entrega. Um eventual uso futuro
exige revisão separada da política, dos IDs, das permissões e das retenções
excepcionais, além de autorização explícita fora desta implementação.

## Auditoria e métricas

Criar manualmente **somente na base DEV** a tabela `RetentionAudit` com estes
nomes/tipos exatos (nenhum campo é criado automaticamente):

| Campos | Tipo Airtable |
| --- | --- |
| `run_id` (campo primário), `mode`, `status`, `error_codes` | Single line text |
| `retention_days`, `analyzed`, `eligible`, `deleted`, `failures`, `invalid_dates`, `recent`, `pages`, `attempted`, `skipped_changed`, `unknown_outcome` | Number, precisão inteira |
| `cutoff`, `started_at`, `updated_at` | Date com horário (`dateTime`) |

`analyzed` conta registros únicos efetivamente validados na leitura inicial;
`eligible` é a quantidade antiga nessa leitura; `deleted` conta somente
confirmações positivas; `attempted` conta DELETEs preparados; `failures` conta
ocorrências de falha, não necessariamente registros distintos. `invalid_dates`
também pode crescer na releitura; `skipped_changed` registra candidatos não mais
iguais à seleção. `pages` conta páginas válidas e `unknown_outcome` exige revisão.
Nenhuma métrica de sucesso é inferida de uma requisição que apenas foi enviada.

A auditoria contém apenas contagens, instantes, modo, ID de execução e códigos
fixos. Não contém nomes, texto de reviews, IDs dos registros excluídos, headers,
tokens, offsets ou mensagens do provedor. O preview contém IDs técnicos e datas
apenas para inspeção transitória no DRY_RUN; esses IDs são correlacionáveis e não
devem ser tratados como anônimos ou publicados com dados reais.

`audit_persisted` e `audit_finalized` no resumo distinguem confirmação da auditoria
e finalização. Na DEMO essas confirmações são **simuladas**, não persistência real.
Sem configuração válida ou schema, não há destino seguro para auditar: o resumo
registra a falha, sem HTTP. Uma queda pode deixar `planned`/`running`; investigar
esses estados e a ausência de execução esperada. Se a auditoria falhar depois de
um DELETE, a contagem durável pode estar atrasada; o fluxo para imediatamente.

O status do n8n pode ser sucesso técnico mesmo com resumo `blocked`/`partial`,
pois erros esperados são tratados para produzir métricas. Acompanhar os campos da
auditoria e o resumo, não apenas a cor verde do canvas. O resumo agora segue para a
[observabilidade DEV](etapa-2-observabilidade.md), com evento e métricas sem PII,
alerta de falha Slack opt-in e tratamento de sua entrega. Não há monitor externo;
crashes antes do resumo continuam descobertos.

## Histórico interno do n8n: política independente

Excluir uma review do Airtable não remove a entrada original do webhook nas
execuções anteriores do n8n. A v4 já desabilita salvamento por workflow; a v3 foi
preservada e pode manter o comportamento global da instância. O fluxo de retenção
também desabilita salvamento de sucesso/erro/manual/progresso e não fixa dados.

Foi adicionado `n8n-mirror/docker-compose.retention.yml`, um Compose **independente**:
porta `127.0.0.1:5680`, container e volume separados da classificação. Ele propõe e
aplica, apenas quando iniciado explicitamente nessa instância DEV:

```dotenv
EXECUTIONS_DATA_SAVE_ON_SUCCESS=none
EXECUTIONS_DATA_SAVE_ON_ERROR=none
EXECUTIONS_DATA_SAVE_ON_PROGRESS=false
EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=false
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168
EXECUTIONS_DATA_PRUNE_MAX_COUNT=1000
EXECUTIONS_DATA_HARD_DELETE_BUFFER=1
EXECUTIONS_DATA_PRUNE_SOFT_DELETE_INTERVAL=60
EXECUTIONS_DATA_PRUNE_HARD_DELETE_INTERVAL=15
N8N_LOG_LEVEL=warn
N8N_CONCURRENCY_PRODUCTION_LIMIT=1
```

`168` são **horas**, equivalentes a sete dias demonstrativos; não os trinta dias
das reviews. Os intervalos são em minutos, salvo o buffer em horas. A limpeza é
assíncrona, com marcação e remoção posteriores; não promete remoção física no
instante do limite. Salvamento desabilitado não apaga por si só o histórico antigo.
Settings explícitos de outros workflows podem prevalecer sobre padrões globais.

A [documentação de variáveis n8n](https://docs.n8n.io/hosting/configuration/environment-variables/executions/)
e a [documentação de pruning](https://github.com/n8n-io/n8n-docs/blob/main/docs/deploy/host-n8n/configure-n8n/scaling/manage-execution-data.md)
distinguem histórico concluído, execuções ativas/em espera e execuções anotadas.
Ativas/em espera e anotadas podem permanecer fora do pruning; inspecionar esses
casos na versão instalada. Não limpar tabelas internas por SQL improvisado nem
remover o volume, que também armazena workflows e credenciais. SQLite pode
reutilizar páginas liberadas sem reduzir o arquivo. Backups, snapshots, logs,
binários, editor e filas precisam de políticas próprias e acesso restrito.

O limite de concorrência não serializa execuções manuais. Não iniciar duas limpezas
manualmente ao mesmo tempo. Não foi implementado lock distribuído nem transação
compare-and-delete: uma mudança entre releitura e DELETE ainda é possível. Não
compartilhar o PAT DEV com um processo concorrente que altere esses registros.

Essas configurações não foram aplicadas ao Railway nem à instância local existente.
A imagem de demonstração mantém n8n `2.28.7`; o Dockerfile permanece `2.41.7`.
A compatibilidade de importação/engine nas versões usadas deve ser evidenciada.

## Demonstração local sem APIs e sem credenciais

1. Se for necessário iniciar uma instância nova, executar manualmente na raiz:

   ```powershell
   cd n8n-mirror
   docker compose -p vozdocliente-retencao --env-file ../.env.example -f docker-compose.retention.yml config --quiet
   docker compose -p vozdocliente-retencao --env-file ../.env.example -f docker-compose.retention.yml up -d
   ```

   Abrir `http://localhost:5680`, criar o owner local e não conectar contas reais.
   Esse comando usa volume próprio; não recria nem reaproveita a instância de
   classificação. O download inicial da imagem pode exigir internet.
2. Importar **`vozdocliente-retencao-demo.json`**, como novo workflow. Confirmar
   que está inativo e que os dois nodes `Airtable DEV ...` são **Code**, não HTTP Request.
3. Clicar **Execute Workflow**, sem publicar/ativar a agenda. Inspecionar o último
   resultado em `Resumo sem PII`. A demonstração leva alguns segundos por causa
   do intervalo entre operações.
4. Resultado esperado: `mode=DRY_RUN`, `analyzed=6`, `eligible=2`, `deleted=0`,
   `pages=3`, `recent=2`, `invalid_dates=2`, `failures=2`, `status=partial`, preview
   de dois candidatos. As duas datas inválidas/ausentes são intencionais para
   mostrar o bloqueio desses registros. A fixture usa datas relativas ao início;
   não envelhece com o calendário. Não há persistência Airtable nessa demonstração.
5. Capturar canvas, configuração da agenda, página com offset, bloqueio de datas,
   resumo e settings. Não fixar nem exportar dados pessoais reais.

Para demonstrar bloqueio de configuração no fluxo operacional, é possível importar
`vozdocliente-retencao-v1.json` e executá-lo com as variáveis vazias do exemplo:
ele termina `CONFIG_INVALID`, sem alcançar o HTTP. A DEMO offline é suficiente
para o percurso completo e não precisa de configuração de `.env`.

## DRY_RUN operacional com Airtable DEV, opcional

Esse roteiro é para execução posterior pelo responsável; não foi executado aqui.

1. Usar somente uma base DEV dedicada. Usar `Reviews` ou a tabela isolada existente
   `ReviewsRetentionTest`, com `processed_at` Date com horário, e `RetentionAudit`
   conforme tabela acima. Inserir manualmente
   reviews **sintéticas**, com datas antigas, recentes e exatamente no limite.
   Campo DateTime real rejeita certas datas impossíveis: os casos inválidos ficam
   no stub; no Airtable é possível demonstrar um campo de data vazio.
2. Preencher no `.env` local `RETENTION_ENV=DEV`, os três IDs DEV e manter
   `RETENTION_DRY_RUN=true`. Informar `RETENTION_TABLE_NAME=ReviewsRetentionTest`
   quando esse for o nome da tabela selecionada por `RETENTION_TABLE_ID`.
   Para visualizar paginação com poucos registros, usar
   `RETENTION_PAGE_SIZE=2`. Manter as duas confirmações de exclusão vazias.
3. Recriar somente o serviço da instância dedicada com o Compose independente e
   `--env-file ../.env`. Não usar o Compose da classificação. Não alterar secrets
   da produção nem mapear tokens de produção.
4. Importar a v1 como novo workflow inativo. Selecionar manualmente a credencial
   DEV exclusiva nos dois nodes HTTP Airtable. Executar o fluxo completo pelo Schedule
   em modo manual; não executar o HTTP isoladamente com dados arbitrários.
5. Conferir preview, contagens, `mode=DRY_RUN`, `deleted=0`, registro agregado na
   tabela de auditoria e **quantidade inalterada de reviews** antes/depois. DRY_RUN
   grava a auditoria, mas não exclui nem atualiza reviews.
6. Capturar evidência com fixtures e ocultar credenciais, IDs reais de bases e
   quaisquer dados de terceiros. Manter o workflow inativo após a demonstração.

### Atualizar uma instalação DEV que rejeitava `ReviewsRetentionTest`

No arquivo de ambiente **efetivamente usado** pelo Compose, ajustar somente a
configuração de retenção; os IDs existentes precisam continuar apontando à base
DEV, à tabela de teste e à auditoria. Nenhuma chave/token deve ser alterada:

```dotenv
RETENTION_ENV=DEV
RETENTION_DRY_RUN=true
RETENTION_TABLE_NAME=ReviewsRetentionTest
RETENTION_CONFIRM_DEV_BASE_ID=
RETENTION_DELETE_CONFIRMATION=
```

Se o arquivo escolhido for `.env` da raiz, executar manualmente **na raiz do repo**:

```powershell
docker compose -p vozdocliente-retencao --env-file .env -f n8n-mirror/docker-compose.retention.yml config --quiet
docker compose -p vozdocliente-retencao --env-file .env -f n8n-mirror/docker-compose.retention.yml up -d --force-recreate n8n
```

Se estiver usando `n8n-mirror/.env`, substituir **ambas** as ocorrências de
`--env-file .env` por `--env-file n8n-mirror/.env`. Não manter configurações
divergentes nem imprimir `config` completo, que pode expor variáveis. Um simples
`restart` não carrega novas variáveis; a recriação local deve preservar o volume.
Estes comandos ficam para execução pelo responsável, não foram executados aqui.

Reimportar `n8n-mirror/workflows/vozdocliente-retencao-v1.json` como **novo workflow
inativo** e selecionar a mesma credencial DEV já existente nos dois HTTP Airtable.
O terceiro HTTP é `Slack DEV falha`, com credencial Slack DEV própria e alerta
desabilitado por padrão; ver o roteiro de observabilidade. Manter a
versão anterior inativa; não substituir nem ativar a v3/v4. Confirmar no código
importado `reviews?.name !== config.tableName`; atualizar só o `.env` não corrige
o JavaScript de um workflow antigo. Não reutilizar estado/pinData de execuções
anteriores: iniciar uma execução completa, manual, sem ativar a agenda.

No item da fase `schema`, confirmar `state.config.tableName=ReviewsRetentionTest`
e correspondência dos IDs localmente; se necessário usar a projeção do diagnóstico,
sem divulgar estado completo. O resultado esperado depende dos registros: ausência
de `SCHEMA_INVALID`, `mode=DRY_RUN`, `deleted=0` e auditoria confirmada se schema,
permissões e transporte estiverem corretos. DRY_RUN grava a auditoria agregada;
não altera as reviews. Nenhuma chamada de validação à base real foi feita aqui.

## Recuperação e riscos remanescentes

Não há rollback automático nem cópia do payload antes de excluir, pois isso criaria
outra retenção de PII. Rollback de deployment não restaura registros excluídos.

Em exclusão indevida: manter/desativar a agenda, voltar a `DRY_RUN=true`, bloquear
as confirmações de DELETE, preservar apenas a auditoria agregada e investigar as
permissões/configuração. Acessar a lixeira da base via responsável autorizado.
O Airtable documenta recuperação de registros na lixeira por até sete dias, sujeita
à disponibilidade e às permissões; não é garantia de recuperação desta solução.
Consultar [lixeira do Airtable](https://support.airtable.com/articles/4837035377-managing-trash-in-airtable).

Se houver snapshot apropriado, restaurá-lo em **outra base isolada** e avaliar
somente os registros necessários. A restauração cria uma nova base e depende do
plano e da disponibilidade, segundo a
[documentação de snapshots](https://support.airtable.com/articles/2163132802-taking-and-restoring-snapshots-in-airtable).
Não reconectar automaticamente essa cópia às integrações. Restaurar também pode
reintroduzir dados que deveriam ser descartados; avaliar finalidade e pendências
antes de qualquer retorno. A existência de lixeira/snapshots significa que DELETE
da API não equivale a apagamento imediato de todas as cópias do fornecedor.

Outros riscos: tratativas abertas/ordens de preservação não são detectadas pelo
schema atual; escrita concorrente não tem CAS; auditoria não é imutável e pode ser
alterada por usuários da base; falhas/crashes podem deixar um checkpoint incompleto;
invalidade de datas pode reter dados indefinidamente sem correção; limites podem
bloquear bases grandes até revisão do responsável. O processo não decide base
legal nem comprova conformidade integral com a LGPD.

`RetentionAudit` também deve ter prazo e acesso definidos (por exemplo, 90 dias
demonstrativos para evidências agregadas). Essa tabela não é apagada pelo mecanismo
de reviews e seu descarte ainda precisa de rotina/política própria. Logs externos
e erros da plataforma devem evitar bodies/headers; o workflow não copia mensagens
do provedor para seus resumos nem usa `console.log`, mas não controla logs externos.

## Testes e evidências

```bash
python scripts/build_retention_workflow.py --check
python tests/validate_workflows.py
python tests/test_routing_logic.py
python -m unittest discover -s tests -v
node tests/test_pii_sanitization.cjs
node tests/test_retention.cjs
node tests/test_retention_schema_diagnostic.cjs
node tests/test_observability.cjs
node scripts/simular_falha_observabilidade.cjs
git diff --check
```

Fontes JavaScript em `n8n-mirror/retention/` são incorporadas de forma determinística
por `scripts/build_retention_workflow.py`. Depois de editar fonte, regenerar os
dois JSONs e executar `--check`. O CI também verifica igualdade das fontes/exports.
Os testes executam o JS e as expressões do JSON, percorrendo suas conexões com
transporte em memória. Não representam uma execução da engine n8n nem acesso a
uma base real. A exclusão real só foi simulada em testes, inclusive os casos de
sucesso, timeout e checkpoint com falha.

Na validação local desta correção: 165 cenários de retenção, 49 de diagnóstico,
102 de sanitização, 25 testes Python e 15 cenários novos de observabilidade,
10 verificações legadas e 29 estruturais passaram. O Compose independente foi
validado por `docker compose ... config --quiet`, sem iniciar container. Python
3.14.7, Node 25.5.0; CI usa Python 3.12 e Node 22 e não foi disparado nesta sessão.

Para a entrega, anexar saída dos testes e evidências **a produzir**:

- versão da engine e importação dos dois fluxos inativos;
- agenda diária, DRY_RUN e ausência de HTTP na DEMO;
- paginação de três páginas e resumo esperado da DEMO;
- em DEV opcional, preview, auditoria persistida e reviews intactas;
- bloqueio de configuração e ausência de tentativas de DELETE;
- settings e verificação do pruning interno com execuções sintéticas concluídas,
  observando os intervalos/buffer e exceções de execuções anotadas/em andamento.

Além da inspeção do contrato e do teste isolado do `execute()` descritos acima,
nenhuma captura nova de UI, auditoria Airtable real, teste de restauração, pruning
em execução ou importação na engine foi produzida nesta implementação. Registrar
explicitamente quais evidências são simulação e quais são integração DEV.
