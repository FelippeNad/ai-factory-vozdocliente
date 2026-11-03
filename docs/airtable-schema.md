# Schema Airtable — Base `VozDoCliente CX`, tabela `Reviews`

> Etapa 2 / v4: o schema e o envio dos campos originais ao Airtable foram
> preservados para a tratativa. Somente o texto sanitizado segue ao LLM; o nome
> em campo separado não é incluído no prompt da v3 nem da v4. Slack na v4 recebe
> apenas tema validado, nota e mensagem fixa. Os riscos e controles pendentes
> estão em [sanitização de PII](etapa-2-sanitizacao-pii.md).

Base ID: `appXXXXXXXXXXXXXX` (conta Airtable corporativa — esse ativo já está com a VozDoCliente, ok)
Tabela: `Reviews`

## Campos

| Campo            | Tipo Airtable           | Notas                                                                       |
| ---------------- | ----------------------- | -------------------------------------------------------------------------- |
| `review_id`      | Single line text        | **Primary field**. ID da review na origem. Deveria ser único — **não tem unique de verdade** (ver dívida). |
| `customer_name`  | Single line text        | Nome do cliente final. **PII** — mantido no Airtable; não enviado como campo ao LLM. |
| `source`         | Single select           | `app-store`, `formulario`, `marketplace`, `reclame-aqui`.                  |
| `rating`         | Number (integer, 1–5)   | Nota da avaliação (quando a origem fornece).                               |
| `review_text`    | Long text               | Texto livre da avaliação. Às vezes traz telefone / nº de pedido (**PII**). |
| `sentiment`      | Single select           | Saída normalizada e validada na v3/v4: `positivo`, `neutro`, `negativo`. |
| `theme`          | Single select           | Saída do LLM: `entrega`, `produto`, `atendimento`, `preco`, `app_bug`.     |
| `processed_at`   | Date (with time)        | Timestamp da execução (`{{now}}` no Make / `new Date().toISOString()` no n8n). API: ISO 8601 UTC, tipo de metadados `dateTime`. Usado pela retenção. |

## Problemas conhecidos do schema

- **Sem unique constraint em `review_id`:** review reprocessado (reenvio da app store, duplo-submit do form) gera **linha duplicada**. Airtable não força unicidade — precisa checar no fluxo antes de gravar.
- **Schema não substitui validação:** na v3/v4, `sentiment`/`theme` são normalizados e validados antes da persistência. Escritas por outros fluxos ainda precisam de controles próprios.
- **`customer_name` e `review_text` carregam PII** sem anonimização comprovada. Há política demonstrativa de retenção DEV; aplicação produtiva, marcação de sensibilidade e prazos aprovados continuam pendentes. Ver [mapa LGPD](lgpd/mapa-dados-pessoais.md).
- **Sem campo `cost_usd`** por execução — impossível auditar custo de LLM por review.
- **Sem campo de status de tratativa** (ex.: `respondido`, `responsavel`, `respondido_em`) — o alerta vai pro Slack mas o ciclo de resposta não fecha dentro do Airtable. Bom candidato pra evolução (fechar o loop da missão "nenhuma reclamação sem resposta").

## Retenção DEV — Etapa 2

O workflow independente `vozdocliente-retencao-v1.json` verifica o tipo `dateTime`
antes de selecionar registros por `processed_at`. O padrão é DRY_RUN com prazo
demonstrativo de 30 dias. O schema de `Reviews` permanece inalterado; a rotina
não detecta tratativas abertas nem deveres de preservação automaticamente.

Criar na base DEV uma tabela separada `RetentionAudit`, com campos agregados,
conforme [política, schema da auditoria e demonstração](etapa-2-retencao-exclusao.md).
Ela não recebe nomes, texto ou IDs individuais das reviews e não é criada
automaticamente. Não configurar essa rotina em produção nesta entrega.
