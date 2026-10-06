# ADR-002 — Estratégia de deploy e separação de ambientes

## Status

Aceito

## Contexto

O protótipo herdado do VozDoCliente foi desenvolvido inicialmente para execução em ambiente controlado, com dependências de contas pessoais e sem separação formal entre desenvolvimento e produção.

A evolução do projeto exige:

- deploy público;
- independência da máquina do desenvolvedor;
- CI/CD;
- separação entre desenvolvimento e produção;
- gerenciamento distinto de secrets;
- possibilidade de rollback;
- reprodutibilidade da implantação.

O ambiente local atual utiliza n8n em Docker e Qwen3-4B por meio do LM Studio.

Essa configuração é adequada para desenvolvimento, mas não pode ser utilizada como única infraestrutura de produção porque depende da máquina local.

## Decisão

Serão mantidos dois ambientes distintos:

### Desenvolvimento

O ambiente de desenvolvimento será executado localmente com:

- n8n via Docker Compose;
- LM Studio;
- Qwen3-4B;
- credenciais específicas de desenvolvimento;
- workflow exportado e versionado no Git.

Esse ambiente será utilizado para testes, alterações no workflow e validação antes do envio para produção.

### Produção

O ambiente de produção é hospedado no Railway e independe da máquina do desenvolvedor.

A infraestrutura utiliza:

- n8n hospedado no Railway;
- imagem `n8nio/n8n:2.41.7`, definida no `Dockerfile`;
- PostgreSQL para persistência interna do n8n;
- OpenAI API para classificação das avaliações;
- Airtable PROD para persistência dos resultados;
- Slack PROD para alertas de avaliações negativas;
- variáveis de ambiente e secrets configurados diretamente na plataforma.

O endpoint público de produção é:

`https://n8n-production-7813.up.railway.app/webhook/review`

O workflow publicado também é exportado e versionado no Git para garantir rastreabilidade das alterações.

## Gestão de configuração e secrets

Credenciais e tokens não serão armazenados diretamente no repositório.

Arquivos `.env` permanecerão ignorados pelo Git.

O identificador da base Airtable é fornecido através da variável:

`AIRTABLE_BASE_ID`

Dessa forma, o workflow não precisa armazenar o identificador da base diretamente em seus nodes.

Credenciais de OpenAI, Airtable, Slack e a chave de criptografia do n8n não são versionadas no repositório.

O repositório conterá apenas `.env.example`, documentando as variáveis necessárias sem valores reais.

Desenvolvimento e produção utilizarão credenciais diferentes.

Segredos de produção deverão ser armazenados na plataforma de hospedagem e/ou em GitHub Secrets, conforme a necessidade do pipeline.

## Versionamento do workflow

O workflow n8n será exportado em formato JSON e armazenado no repositório.

Cada alteração relevante no fluxo deverá ser acompanhada pela atualização do arquivo versionado.

Isso permite rastrear mudanças, associá-las a commits e recuperar versões anteriores.

A versão atual do workflow de produção é:

`n8n-mirror/workflows/vozdocliente-router-v3.json`

## Deploy

O repositório está conectado diretamente ao Railway.

O processo atual é:

1. alteração e validação do workflow;
2. exportação da versão atualizada para o Git;
3. execução dos testes locais;
4. commit e push para a branch `main`;
5. execução automática do GitHub Actions;
6. validação estrutural do workflow;
7. execução dos testes de lógica de roteamento;
8. detecção automática do novo commit pelo Railway;
9. build da imagem definida no `Dockerfile`;
10. deploy automático do serviço;
11. validação do endpoint público por smoke test.

O GitHub Actions está configurado em:

`.github/workflows/ci.yml`

O `Dockerfile` fixa a versão do n8n utilizada em produção:

```dockerfile
FROM n8nio/n8n:2.41.7
```

## Rollback

Uma versão estável do sistema será identificada por tags SemVer.

Caso uma nova versão apresente falha, o rollback será realizado retornando para uma versão estável anterior e executando novamente o processo de deploy.

O procedimento deverá ser testado e sua evidência registrada no repositório.

## Alternativas consideradas

### Executar produção na máquina local

Descartada porque:

- depende da disponibilidade da máquina;
- não fornece disponibilidade pública confiável;
- dificulta CI/CD;
- não atende ao requisito de independência da máquina do desenvolvedor.

### Utilizar apenas Make.com

A alternativa reduziria a responsabilidade pela infraestrutura, porém ofereceria menor controle sobre versionamento do workflow e sobre o processo de deploy utilizado neste projeto.

### Usar um único ambiente para desenvolvimento e produção

Descartado porque aumenta o risco de alterações experimentais afetarem o ambiente público e dificulta o uso de credenciais e dados separados.

## Consequências

### Positivas

- isolamento entre testes e produção;
- menor risco de alterações locais afetarem usuários;
- secrets distintos por ambiente;
- possibilidade de CI/CD;
- produção independente da máquina do desenvolvedor;
- rollback baseado em versões conhecidas;
- melhor rastreabilidade das alterações.

### Negativas

- necessidade de manter configurações distintas;
- maior complexidade operacional;
- necessidade de uma infraestrutura externa para produção;
- necessidade de sincronizar workflow local, repositório e ambiente publicado.

## Referências

- `docs/auditoria-prototipo.md`
- `docs/matriz-decisao-stack.md`
- `docs/adr/ADR-001-stack.md`
- `.env.example`
- `n8n-mirror/docker-compose.yml`
- `n8n-mirror/workflows/`