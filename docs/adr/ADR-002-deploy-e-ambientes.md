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

O ambiente de produção será hospedado em infraestrutura pública independente da máquina local.

O ambiente utilizará:

- n8n publicado em serviço de hospedagem;
- API externa de LLM;
- credenciais próprias de produção;
- variáveis de ambiente configuradas na plataforma de hospedagem;
- workflow correspondente à versão publicada no repositório.

O deploy será integrado ao GitHub Actions, de forma que alterações aprovadas e enviadas para a branch `main` possam acionar automaticamente a atualização do ambiente de produção.

## Gestão de configuração e secrets

Credenciais e tokens não serão armazenados diretamente no repositório.

Arquivos `.env` permanecerão ignorados pelo Git.

O repositório conterá apenas `.env.example`, documentando as variáveis necessárias sem valores reais.

Desenvolvimento e produção utilizarão credenciais diferentes.

Segredos de produção deverão ser armazenados na plataforma de hospedagem e/ou em GitHub Secrets, conforme a necessidade do pipeline.

## Versionamento do workflow

O workflow n8n será exportado em formato JSON e armazenado no repositório.

Cada alteração relevante no fluxo deverá ser acompanhada pela atualização do arquivo versionado.

Isso permite rastrear mudanças, associá-las a commits e recuperar versões anteriores.

## Deploy

O fluxo esperado para produção será:

1. alteração e validação no ambiente de desenvolvimento;
2. execução dos testes automatizados;
3. atualização do workflow versionado;
4. commit e push;
5. abertura ou integração da alteração na branch `main`;
6. execução do GitHub Actions;
7. atualização automática do ambiente de produção;
8. execução de smoke tests.

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