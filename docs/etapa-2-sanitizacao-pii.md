# Etapa 2 — sanitização de PII antes do LLM

Complemento documental após `718ce4d`: [mapa LGPD](lgpd/mapa-dados-pessoais.md),
[transferências internacionais](lgpd/transferencia-internacional.md),
[checklist](lgpd/checklist-etapa-2.md) e [roteiro de evidências](lgpd/roteiro-evidencias.md).
A captura `evidencias/etapa2-sanitizacao-pii-n8n.png` agora está versionada e mostra
o canvas/sanitizador, sem comprovar execução integral das APIs. As pendências
descritas na implementação original abaixo precisam ser lidas com esse alcance.

Implementação local na branch `etapa-2`, em 02/11/2026. A v3 foi analisada e
preservada; a v4 é uma candidata **inativa**, sem deploy. Nenhuma API foi chamada,
nenhuma credencial foi alterada e nenhum dado pessoal real foi usado nos testes.

Continuação após o commit `f66cb79`: a política de retenção e exclusão foi
implementada em workflows independentes, sem alterar v3/v4. Consulte
[retenção, auditoria e demonstração local](etapa-2-retencao-exclusao.md). As
pendências registradas abaixo descrevem o estado ao concluir a sanitização;
a nova rotina adiciona retenção DEV, sem aplicar configurações à produção.

## Diagnóstico anterior à alteração

- A v3 conecta `Webhook Review` diretamente a `LLM PROD`, que lê
  `$json.body.review_text`. O nome em campo separado não entra nesse prompt,
  mas nomes e outros identificadores escritos na avaliação podem entrar.
- `Parse + Merge` retoma o payload original para Airtable e Slack. Erros de parse
  incluíam a resposta completa do LLM, e erros de enums incluíam valores retornados.
- Os testes existentes passaram antes da edição: validador estrutural do Make/v3
  e 10 verificações de roteamento com mock. Não executavam o JavaScript dos nodes.
- Dockerfile fixa n8n `2.41.7`; Compose fixa `2.28.7`. As versões não foram alteradas.
  A divergência precisa ser resolvida em trabalho de infraestrutura separado.

## Fluxo e contrato

```text
Webhook Review -> Sanitizar PII -> LLM PROD -> Parse + Merge
 -> Airtable Buscar review_id -> deduplicação
    -> encontrado: encerra
    -> não encontrado: Airtable PROD -> É negativo? -> Slack PROD
```

`Sanitizar PII` é um node Code `typeVersion: 2`, JavaScript, modo
`runOnceForAllItems`. Usa apenas recursos padrão da linguagem e `$input.all()`;
não importa bibliotecas, não acessa rede, não registra valores em console.

Entrada: `item.json.body.review_text`, uma string não vazia de até **20.000 unidades
UTF-16** (o limite é `String.length`, antes da normalização). Body ausente, array,
texto não string, vazio após normalização ou acima do limite interrompem o fluxo
com `Entrada invalida para sanitizacao.`. Não há coerção de objetos em texto.
Esse limite protege o processamento local; não substitui limite de tamanho no proxy.

Saída: somente `{ review_text_sanitized: "..." }` em `json`, com `pairedItem`
para cada entrada. Headers, body original, campos extras e um eventual campo
sanitizado enviado pelo cliente não são copiados. Um item inválido interrompe o
lote. O webhook de produção continua representando uma avaliação por execução;
o suporte a lote do sanitizador não transforma o restante do workflow em API de lote.

O texto recebe normalização NFKC e remoção de caracteres invisíveis comuns
(`U+200B`–`U+200D`, `U+FEFF`). Depois são aplicadas substituições globais:

| Padrão | Formatos cobertos | Substituição |
| --- | --- | --- |
| CPF | Pontuado, compacto, grupos com espaços, espaços ao redor da pontuação | `[CPF]` |
| CNPJ | Numérico pontuado/compacto/com espaços; alfanumérico pontuado ou compacto | `[CNPJ]` |
| E-mail | Maiúsculas/minúsculas, alias `+`, subdomínios e letras Unicode | `[EMAIL]` |
| Telefone | DDD, fixo/celular, `+55`, espaços/pontos/hífens, nono dígito separado; local com separador ou rótulo; 0300/0500/0800 | `[TELEFONE]` |
| CEP | Oito dígitos compactos ou grupos 5+3 com hífen, ponto ou espaço | `[CEP]` |
| URL | HTTP(S), FTP, `www`, domínio sem protocolo, caminhos/query/fragmentos | `[URL]` |

A ordem é intencional: URLs completas antes de e-mails; e-mails e CNPJ antes de
domínios sem protocolo; CPF antes dos demais telefones e CEP. Não se validam
dígitos verificadores, DDD ou existência de domínio: valores inválidos também
devem ser removidos. CNPJ alfanumérico é uma regra de máscara, sem validação fiscal.
Pontuação no final de URLs é preservada. Aplicar novamente as máscaras mantém o resultado.

`LLM PROD` aceita **exclusivamente** `$json.review_text_sanitized`. A expressão
verifica tipo e conteúdo e lança erro genérico antes de montar o request se o campo
não for válido. Não há `||`, `??` ou consulta ao webhook como fallback. Model,
schema, categorias, endpoints, credenciais e versões dos nodes existentes foram
preservados. Não foi verificada disponibilidade do modelo por chamada externa.

Exemplo inteiramente sintético:

```text
Antes:  O app trava no login. CEP 00000-000, email teste@example.invalid.
Depois: O app trava no login. CEP [CEP], email [EMAIL].
```

Reclamação, negação, tema, preço e nota permanecem quando fora do padrão mascarado.
Os seis cenários compartilhados cobrem todos os cinco temas e os três sentimentos.
O mock mantém classificação e decisão de alerta; isso não demonstra a qualidade
de classificação de um LLM real, que não foi chamado.

## Tratamento separado por destino

| Destino | Decisão implementada na v4 | Risco remanescente / ação necessária |
| --- | --- | --- |
| LLM | Somente texto sanitizado; sem nome, metadados ou body original | PII não reconhecida ainda pode sair. Avaliar detecção adicional, minimização na origem, contratos e retenção do fornecedor. |
| Airtable | Mantém `customer_name`, `review_text` e demais campos originais para preservar a fila de tratativa, schema e deduplicação | Continua tratando PII e dados potencialmente sensíveis. Definir necessidade dos campos, acesso mínimo, prazo de retenção, descarte, atendimento ao titular e regras de compartilhamento. O workflow não implementa esses controles. |
| Slack | Somente tema validado, nota inteira entre 1 e 5 e instrução fixa de consultar a fila restrita no Airtable | Não envia nome, origem, ID, texto original nem texto sanitizado. O alerta não identifica uma review individual; a equipe consulta a fila. Mensagens antigas continuam contendo PII e precisam de revisão de acesso/retenção. |
| Logs e erros | Sanitizador e parser não fazem logs e usam mensagens fixas; o parser não interpola resposta ou valores inválidos | Erros de HTTP, proxy, plataforma, observabilidade e respostas dos fornecedores podem incluir request/resposta. Não foi inspecionada a infraestrutura. Desabilitar captura de bodies/headers e acesso de debug; não encaminhar objetos de erro completos. |
| Execuções n8n | `saveDataErrorExecution=none`, `saveDataSuccessExecution=none`, `saveManualExecutions=false`, `saveExecutionProgress=false`; `pinData` vazio | O webhook e o merge ainda contêm o original em memória. Editor, execuções em andamento, banco/fila temporários, crash dumps, backups e histórico anterior podem expor dados. Configuração não apaga o passado nem protege outros workflows ou logs externos. |

O original é retomado **depois** da classificação, exclusivamente para a saída
operacional do merge/Airtable. Descartá-lo na saída do sanitizador não apaga o item
do webhook da memória do n8n. O conteúdo sanitizado também não deve ser tratado
como dado anônimo: nomes, endereços e contexto identificável podem continuar nele.

A opção de não salvar execuções reduz a rastreabilidade operacional e a capacidade
de repetir/debugar falhas. Monitoramento deve usar contagens e códigos de erro sem
payload. As opções são configurações por workflow, conforme a
[documentação oficial de settings do n8n](https://docs.n8n.io/workflows/settings/).
O modo do node segue a [documentação oficial de Code](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code/).
Não foram adicionados recursos novos de redaction dependentes de versão/licença.

## Limitações e problemas conhecidos

- Regex não reconhece identidade nem comprova anonimização. Nomes, endereços,
  documentos por extenso, números de pedido, identificadores fora do padrão,
  informações de saúde e combinações de contexto podem permanecer.
- `teste arroba example ponto invalid`, telefone estrangeiro fora do padrão BR e
  celular local de nove dígitos sem separador/rótulo são exemplos de não detecção
  cobertos por testes que **registram a limitação**, sem afirmar proteção nesses casos.
- Onze dígitos compactos podem ser CPF ou telefone: são mascarados como `[CPF]`.
  Oito dígitos sem rótulo podem ser CEP ou telefone local: são mascarados como `[CEP]`.
  Um número de pedido também pode ser mascarado. Essas ambiguidades não justificam
  liberar o valor ao LLM.
- Domínios sem protocolo podem gerar falsos positivos em texto com pontos. URLs
  com espaços, IPs sem protocolo, ofuscações arbitrárias, homógrafos e todas as
  variantes internacionais não estão cobertos. A normalização tem alcance limitado.
- Uma reclamação cujo contexto está apenas no caminho de uma URL perde esse
  contexto. NFKC pode alterar tipografia. A preservação semântica é testada em
  amostra sintética, sem garantia universal; ampliar corpus é necessário.
- O conteúdo livre continua sendo não confiável: mascarar PII não impede prompt
  injection. O parser limita a saída aos enums permitidos, mas não valida a verdade
  da classificação.
- A deduplicação continua **depois do LLM**: duplicatas ainda podem gerar chamadas
  de classificação. Busca seguida de criação não resolve corrida concorrente no
  Airtable. Nenhum desses comportamentos foi alterado nesta etapa.
- Os testes executam o JavaScript real em `node:vm` com interfaces n8n simuladas.
  Não equivalem à importação/execução na engine n8n. Compatibilidade está baseada
  em Code v2 e nas versões de nodes já presentes, sem atualização de dependências.
- Implementar essas regex **não declara conformidade integral com a LGPD**. Base
  legal, finalidade, necessidade, direitos dos titulares, governança, retenção,
  acesso e relações com operadores exigem avaliação própria.

## Como verificar sem APIs

Pré-requisitos: Python 3.12+ e Node.js 22+ disponíveis no PATH; nenhuma biblioteca
de terceiros ou instalação npm é necessária.

```bash
python tests/validate_workflows.py
python tests/test_routing_logic.py
python -m unittest discover -s tests -v
node tests/test_pii_sanitization.cjs
git diff --check
```

O teste JS carrega `jsCode` e expressões do **arquivo v4**, sem copiar a regex para
outra implementação. Fixtures em `tests/fixtures/pii_semantic_cases.json` conectam
o resultado real da sanitização aos testes Python do mock legado. Todas as entradas
são sintéticas: documentos com zeros, DDD fictício e domínio reservado `.invalid`.

O validador inspeciona v3 e v4. Para a v4, remove logicamente `Sanitizar PII` do
grafo e exige que o LLM se torne inalcançável a partir do webhook. Considera todos
os ramos/tipos de conexão, impede outra origem de entrada no LLM, verifica a
expressão sem fallback e exige interrupção em caso de erro. Testes de mutação
provam que bypass direto/indireto/por erro, ciclos, node desabilitado e fallback
reintroduzido são rejeitados. Hash do blob Git original da v3:
`8c21523b18d2dc0fca3aba6456b042036d7b379e`.

Resultados locais em 02/11/2026 (Python 3.14.7, Node.js 25.5.0):

| Verificação | Resultado |
| --- | --- |
| Validação estrutural Make + v3 + v4 | 27 verificações aprovadas |
| Roteamento legado | 10 verificações aprovadas |
| Unittest de segurança e preservação da classificação | 14 testes aprovados; seis cenários semânticos |
| JavaScript real e expressões exportadas | 102 casos aprovados |

Node não estava no PATH desta máquina; foi usado o executável instalado em
`%LOCALAPPDATA%\Programs\Bionic\resources\app\.webpack-bionic\bin\node.exe`.
O CI foi configurado para Python 3.12 e Node 22, mas não foi executado no GitHub
nesta sessão. O sandbox bloqueou uma tentativa inicial de iniciar Python a partir
do teste JS (`spawnSync EPERM`); fixtures compartilhadas removeram essa dependência.

## Evidências para a entrega

Já disponíveis no repositório: v3 preservada, v4 revisável, testes sintéticos,
fixtures e documentação. Anexar à entrega a saída dos comandos acima com revisão
do diff e identificação do commit quando houver commit manual. Não há prints novos
de produção nem comprovante de deploy nesta implementação.

Ainda produzir em ambiente isolado, **sem APIs reais**:

1. Importar a v4 como novo workflow inativo, sem sobrescrever a v3, nas versões
   efetivamente usadas (`2.28.7` e `2.41.7`) ou justificar a convergência para uma.
   Capturar versão e canvas com `Webhook -> Sanitizar PII -> LLM`.
2. Em cópia DEV, substituir os HTTP Requests por stubs locais com saída contratual.
   Capturar input/output do sanitizador e request destinado ao stub do LLM, usando
   somente fixtures. Confirmar que entradas inválidas não chegam ao stub e que
   não há `customer_name`, original ou headers no request de classificação.
3. Capturar roteamento negativo/positivo/neutro e duplicata com stubs de Airtable
   e Slack. Conferir que o stub do Slack não recebe nome, ID ou texto. Os alertas
   continuam restritos a reviews negativas e novas.
4. Capturar settings de não retenção e testar sucesso/erro/manual, verificando o
   histórico após término. Usar apenas dados sintéticos mesmo durante a inspeção
   manual; não fixar payloads reais no editor nem exportá-los.
5. Registrar revisão separada de permissões/retenção do Airtable e Slack, logs de
   proxy/n8n/provedor, backups e histórico antigo. A revisão de política e acessos
   não é comprovada pela execução dos testes unitários.

Evidências de integração/engine, governança e retenção permanecem **pendentes**;
não devem ser apresentadas como executadas por este relatório.
