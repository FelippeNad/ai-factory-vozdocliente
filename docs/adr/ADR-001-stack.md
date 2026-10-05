# ADR-001 — Stack principal do VozDoCliente

## Status

Aceito

## Contexto

O protótipo herdado do VozDoCliente foi originalmente desenvolvido em Make.com com uso de OpenAI, Airtable e Slack.

Durante a evolução do projeto, foi necessário definir uma stack que permitisse maior controle técnico, versionamento em Git, reprodutibilidade, facilidade de manutenção e preparação para deploy automatizado.

Foram avaliadas três alternativas:

1. n8n + LM Studio
2. n8n + OpenAI API
3. Make.com + OpenAI API

A comparação foi registrada em `docs/matriz-decisao-stack.md`.

O desenvolvimento local também precisa permitir testes com baixo custo, enquanto o ambiente de produção deve permanecer disponível independentemente da máquina do desenvolvedor.

## Decisão

Será utilizado **n8n como plataforma principal de orquestração**.

Para desenvolvimento local, o workflow utilizará **LM Studio com Qwen3-4B**, através de endpoint compatível com a API da OpenAI.

Para produção, será utilizada uma **API de LLM externa**, permitindo que o sistema funcione de forma independente da infraestrutura local.

Airtable será utilizado para persistência dos resultados das avaliações e Slack para envio de alertas relacionados a avaliações negativas.

Os workflows n8n serão exportados e versionados no repositório Git.

## Alternativas consideradas

### Make.com + OpenAI API

Vantagens:
- facilidade inicial de configuração;
- infraestrutura gerenciada;
- baixa necessidade de manutenção operacional.

Desvantagens:
- menor controle sobre execução e infraestrutura;
- versionamento menos integrado ao Git;
- menor flexibilidade para CI/CD e automações customizadas.

### n8n + LM Studio

Vantagens:
- baixo custo de inferência local;
- maior controle sobre o modelo utilizado;
- bom ambiente para desenvolvimento e testes.

Desvantagens:
- depende da disponibilidade da máquina local;
- não é adequado, isoladamente, para disponibilização pública contínua.

### n8n + API externa de LLM

Vantagens:
- independência da máquina local;
- facilidade de implantação em ambiente público;
- integração com CI/CD;
- maior reprodutibilidade operacional.

Desvantagens:
- custo variável por requisição;
- dependência de um provedor externo.

## Consequências

### Positivas

- workflows podem ser versionados no Git;
- desenvolvimento e produção podem utilizar a mesma estrutura de workflow;
- desenvolvimento local pode ser realizado sem consumo de API externa;
- produção não depende da máquina do desenvolvedor;
- maior facilidade de integração com pipelines de CI/CD;
- maior controle sobre configuração e evolução da solução.

### Negativas

- existirão configurações distintas de LLM entre desenvolvimento e produção;
- será necessário gerenciar secrets e variáveis de ambiente separadamente;
- o ambiente de produção terá dependência de um provedor externo de LLM;
- alterações no workflow deverão ser exportadas e sincronizadas com o repositório.

## Referências

- `docs/auditoria-prototipo.md`
- `docs/matriz-decisao-stack.md`
- `n8n-mirror/workflows/`