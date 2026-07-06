# Schema Airtable — Base `VozDoCliente CX`, tabela `Reviews`

Base ID: `appXXXXXXXXXXXXXX` (conta Airtable corporativa — esse ativo já está com a VozDoCliente, ok)
Tabela: `Reviews`

## Campos

| Campo            | Tipo Airtable           | Notas                                                                       |
| ---------------- | ----------------------- | -------------------------------------------------------------------------- |
| `review_id`      | Single line text        | **Primary field**. ID da review na origem. Deveria ser único — **não tem unique de verdade** (ver dívida). |
| `customer_name`  | Single line text        | Nome do cliente final. **PII** — entra aqui e no prompt do LLM sem anonimização. |
| `source`         | Single select           | `app-store`, `formulario`, `marketplace`, `reclame-aqui`.                  |
| `rating`         | Number (integer, 1–5)   | Nota da avaliação (quando a origem fornece).                               |
| `review_text`    | Long text               | Texto livre da avaliação. Às vezes traz telefone / nº de pedido (**PII**). |
| `sentiment`      | Single select           | Saída do LLM: `positivo`, `neutro`, `negativo`. Gravado como string crua.  |
| `theme`          | Single select           | Saída do LLM: `entrega`, `produto`, `atendimento`, `preco`, `app_bug`.     |
| `processed_at`   | Date (with time)        | Timestamp da execução (`{{now}}` no Make / `new Date().toISOString()` no n8n). |

## Problemas conhecidos do schema

- **Sem unique constraint em `review_id`:** review reprocessado (reenvio da app store, duplo-submit do form) gera **linha duplicada**. Airtable não força unicidade — precisa checar no fluxo antes de gravar.
- **`sentiment`/`theme` como Single select gravados via string crua:** se o LLM responder fora da lista (ex.: `"Negativo"` com maiúscula, `"frete"`), o Airtable **cria uma opção nova** e bagunça os relatórios. Mesma armadilha do `Multiple select` do projeto antigo.
- **`customer_name` e `review_text` carregam PII** e não têm marcação de sensibilidade, anonimização nem política de retenção. Pendência LGPD.
- **Sem campo `cost_usd`** por execução — impossível auditar custo de LLM por review.
- **Sem campo de status de tratativa** (ex.: `respondido`, `responsavel`, `respondido_em`) — o alerta vai pro Slack mas o ciclo de resposta não fecha dentro do Airtable. Bom candidato pra evolução (fechar o loop da missão "nenhuma reclamação sem resposta").
