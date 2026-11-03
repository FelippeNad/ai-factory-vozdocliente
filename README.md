# VozDoCliente — AI Review Router

Sistema de triagem automática de avaliações de clientes utilizando IA para classificação de sentimento e tema, persistência estruturada e roteamento de alertas para o time de CX.

Este projeto é uma evolução de um protótipo herdado originalmente implementado em Make.com. A solução foi revisada e evoluída para uma arquitetura baseada em n8n, com separação entre desenvolvimento e produção, workflow versionado, testes automatizados, deploy público e CI/CD.

## Objetivo

Automatizar o processamento de avaliações recebidas de diferentes canais.

Cada avaliação é:

1. recebida por webhook;
2. sanitizada para reduzir PII antes da classificação (v4 da Etapa 2);
3. classificada por um LLM usando exclusivamente o campo sanitizado;
4. validada e normalizada;
5. verificada contra registros existentes;
6. persistida no Airtable;
7. encaminhada ao Slack quando possui sentimento negativo.

O princípio funcional do sistema é:

> Nenhuma reclamação sem resposta.

## Fluxo principal

```text
Review
  ↓
Webhook n8n
  ↓
Sanitizar PII (v4)
  ↓
LLM
  ↓
Parse + validação
  ↓
Busca por review_id
  ↓
Deduplicação
  ↓
Airtable
  ↓
Sentimento negativo?
  ├── Não → fim
  └── Sim → Slack
```

A classificação utiliza:

### Sentimento

- `positivo`
- `neutro`
- `negativo`

### Tema

- `entrega`
- `produto`
- `atendimento`
- `preco`
- `app_bug`

## Como rodar localmente

O ambiente de desenvolvimento utiliza n8n em Docker e LM Studio com Qwen3-4B.

Para iniciar o n8n local:

```bash
cd n8n-mirror
docker compose up -d
```

## Ambientes

### Desenvolvimento

O ambiente de desenvolvimento utiliza:

- n8n em Docker;
- LM Studio;
- Qwen3-4B;
- Airtable DEV;
- Slack DEV;
- credenciais específicas de desenvolvimento.

Esse ambiente permite desenvolver e testar o workflow sem depender da infraestrutura de produção e sem necessidade de utilizar uma API externa de LLM.

### Produção

O ambiente de produção utiliza:

- n8n hospedado no Railway;
- OpenAI API;
- modelo `gpt-5.6-luna`;
- Airtable PROD;
- Slack PROD;
- PostgreSQL para persistência interna do n8n;
- variáveis e secrets configurados no ambiente de produção.

URL pública do n8n:

```text
https://n8n-production-7813.up.railway.app
```

Endpoint de produção:

```text
POST https://n8n-production-7813.up.railway.app/webhook/review
```

## Exemplo de requisição

```json
{
  "review_id": "R-1001",
  "customer_name": "Cliente Exemplo",
  "source": "app-store",
  "rating": 1,
  "review_text": "Produto chegou quebrado e o atendimento nao respondeu."
}
```

Exemplo com PowerShell:

```powershell
curl -Method POST https://n8n-production-7813.up.railway.app/webhook/review `
  -ContentType "application/json" `
  -Body '{"review_id":"R-1001","customer_name":"Cliente Exemplo","source":"app-store","rating":1,"review_text":"Produto chegou quebrado e o atendimento nao respondeu."}'
```

## Deduplicação

Antes da criação de um registro, o workflow consulta o Airtable utilizando `review_id`.

Caso o identificador já exista:

```text
review_id encontrado
       ↓
deduplicação = TRUE
       ↓
fluxo encerrado
```

Isso evita:

- registros duplicados;
- alertas duplicados no Slack.

A busca continua depois do LLM, portanto duplicatas ainda podem gerar chamadas
de classificação. Busca e criação não são uma operação atômica.

## Validação da saída do LLM

A saída do modelo é processada pelo node `Parse + Merge`.

O fluxo:

- verifica se existe resposta do LLM;
- realiza o parse do JSON;
- normaliza os valores;
- valida `sentiment`;
- valida `theme`;
- interrompe a execução em caso de resposta inválida.

Em produção, a chamada à OpenAI utiliza JSON Schema com valores permitidos para sentimento e tema.

## Workflow versionado

As versões exportadas do workflow n8n estão em:

```text
n8n-mirror/workflows/
```

Versão candidata da Etapa 2 (inativa, sem deploy):

```text
vozdocliente-router-v4.json
```

A v3 permanece como referência sem modificações. A sanitização obrigatória antes
do LLM e os riscos de Airtable, Slack, logs e histórico estão documentados em
[Etapa 2 — sanitização de PII](docs/etapa-2-sanitizacao-pii.md). Regex não garante
anonimização nem conformidade integral com a LGPD. O Airtable ainda recebe dados
originais; o Slack da v4 recebe apenas tema, nota e instrução fixa de tratativa.

Retenção da Etapa 2: `vozdocliente-retencao-v1.json` é independente, inativo e usa
Schedule Trigger, prazo configurável de 30 dias demonstrativos, paginação,
auditoria agregada e DRY_RUN por padrão. DELETE exige DEV e confirmações explícitas.
A [política de retenção e roteiro de evidências](docs/etapa-2-retencao-exclusao.md)
separa reviews do Airtable do histórico interno n8n e descreve riscos/recuperação.

Para demonstrar sem APIs nem credenciais, importe
`n8n-mirror/workflows/vozdocliente-retencao-demo.json` no n8n local, mantenha inativo
e clique **Execute Workflow**. O resumo esperado é: 6 analisados, 2 elegíveis,
0 excluídos, 3 páginas e 2 datas inválidas/ausentes intencionais (`status=partial`).
Uma instância isolada opcional está em `n8n-mirror/docker-compose.retention.yml`,
na porta `5680` com volume próprio. Não foram iniciados containers nesta entrega.

As credenciais não são armazenadas diretamente no JSON exportado. Cada ambiente mantém suas próprias credenciais.

O identificador da base Airtable é obtido por variável de ambiente:

```text
AIRTABLE_BASE_ID
```

## Testes

Os testes automatizados podem ser executados sem acessar APIs externas:

```bash
python tests/validate_workflows.py
python tests/test_routing_logic.py
python -m unittest discover -s tests -v
node tests/test_pii_sanitization.cjs
node tests/test_retention.cjs
python scripts/build_retention_workflow.py --check
```

`validate_workflows.py` verifica a estrutura dos workflows e suas conexões.

`test_routing_logic.py` utiliza um LLM mockado para validar classificação e lógica de roteamento.

Os novos testes executam o JavaScript real da v4, validam ausência de fallback e
de caminhos que contornem a sanitização, e preservação das categorias com dados
sintéticos. Requerem Python 3.12+ e Node.js 22+, sem dependências adicionais.

Os testes de retenção percorrem os nodes e conexões exportados com Airtable
simulado, incluindo falhas, datas, paginação e bloqueios de exclusão. As fontes
em `n8n-mirror/retention/` geram os exports via
`python scripts/build_retention_workflow.py`; o CI verifica sua sincronização.

## Smoke tests de produção

Foram executados três smoke tests no endpoint público de produção:

| Cenário | Resultado |
| --- | --- |
| Review negativa | Airtable + alerta Slack |
| Review positiva | Airtable, sem alerta Slack |
| Review duplicada | bloqueada pela deduplicação |

Resultado:

```text
3/3 testes aprovados
```

A documentação completa está em:

```text
docs/smoke-tests.md
```

As evidências estão armazenadas em:

```text
docs/evidencias/
```

## CI/CD

O repositório possui GitHub Actions configurado em:

```text
.github/workflows/ci.yml
```

Em alterações enviadas para a branch `main`, o pipeline executa:

```text
Push main
   ↓
GitHub Actions
   ↓
Validação estrutural do workflow
   ↓
Testes de roteamento
   ↓
Railway detecta o novo commit
   ↓
Build da imagem
   ↓
Deploy automático
```

A imagem de produção utiliza uma versão fixa do n8n através do `Dockerfile`:

```dockerfile
FROM n8nio/n8n:2.41.7
```

Isso evita alterações inesperadas causadas pelo uso de uma tag `latest`.

## Estrutura principal

```text
ai-factory-vozdocliente/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── adr/
│   ├── architecture/
│   ├── evidencias/
│   ├── auditoria-prototipo.md
│   ├── matriz-decisao-stack.md
│   └── smoke-tests.md
├── n8n-mirror/
│   ├── docker-compose.yml
│   └── workflows/
│       ├── vozdocliente-router-v0.json
│       ├── vozdocliente-router-v1.json
│       ├── vozdocliente-router-v2.json
│       ├── vozdocliente-router-v3.json
│       └── vozdocliente-router-v4.json
├── tests/
│   ├── validate_workflows.py
│   ├── test_routing_logic.py
│   ├── test_pii_sanitization.cjs
│   ├── test_pii_classification.py
│   ├── test_workflow_security.py
│   └── fixtures/pii_semantic_cases.json
├── workflows/
│   └── vozdocliente-make-blueprint.json
├── Dockerfile
├── .env.example
├── CHANGELOG.md
└── README.md
```

## Arquitetura e decisões

A evolução arquitetural está documentada em:

```text
docs/auditoria-prototipo.md
docs/matriz-decisao-stack.md
docs/architecture/c4-context.md
docs/architecture/c4-container.md
docs/adr/ADR-001-stack.md
docs/adr/ADR-002-deploy-e-ambientes.md
```

## Segurança

A documentação de LGPD da Etapa 2 distingue controles presentes no código,
evidências offline e validações jurídicas/operacionais ainda pendentes:

- [Mapa de dados pessoais](docs/lgpd/mapa-dados-pessoais.md): categorias,
  operações, finalidade, hipóteses legais e papéis a validar.
- [Transferência internacional](docs/lgpd/transferencia-internacional.md):
  análise por fornecedor, LGPD/ANPD e dossiê contratual pendente.
- [Rotação de credenciais](docs/security/rotacao-credenciais.md): procedimentos
  por provedor, diferença entre tokens, DEK e `N8N_ENCRYPTION_KEY`, rollback e Git.
- [Checklist da Etapa 2](docs/lgpd/checklist-etapa-2.md) e
  [roteiro de evidências para apresentação](docs/lgpd/roteiro-evidencias.md).

O exercício de rotação usa somente estados fictícios e não acessa provedores,
cofres ou `.env` reais. Para verificar a evidência já gerada:

```powershell
python scripts/simular_rotacao_credenciais.py --verify docs/security/evidencias/rotacao-simulada.json
```

Foram aprovados 38 cenários simulados. Isso não comprova rotação real, criptografia
n8n ou conformidade integral com a LGPD. Contratos, bases legais, regiões efetivas,
titularidade corporativa e responsáveis nomeados continuam sujeitos à validação.
O briefing fixa máximo de 90 dias para logs; os prazos demonstrativos de 30 dias
das reviews e sete dias do histórico n8n têm escopos diferentes.

Secrets e credenciais não devem ser armazenados no repositório.

Arquivos `.env` são ignorados pelo Git e o projeto mantém apenas `.env.example`.

A separação de credenciais DEV/PROD é prevista na arquitetura; sua aplicação,
titularidade e escopos precisam ser confirmados nas contas, sem revelar valores.

Exemplos de informações que não devem ser commitadas:

```text
OpenAI API keys
Airtable Personal Access Tokens
Slack Bot Tokens
N8N_ENCRYPTION_KEY
```

## Histórico

O projeto partiu de um protótipo herdado baseado em Make.com.

A evolução preservou a finalidade original do sistema, mas adicionou:

- n8n como orquestrador principal;
- ambiente de desenvolvimento local;
- ambiente público de produção;
- separação DEV/PROD;
- validação defensiva da resposta do LLM;
- deduplicação;
- versionamento do workflow;
- testes automatizados;
- CI/CD;
- deploy no Railway;
- documentação arquitetural.

O blueprint original do Make.com foi mantido em `workflows/` para preservar o histórico e permitir rastreabilidade da evolução.
