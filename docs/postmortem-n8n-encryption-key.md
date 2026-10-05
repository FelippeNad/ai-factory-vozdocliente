# Post-mortem — Persistência da chave de criptografia do n8n

## Resumo

Durante a configuração do ambiente de produção do VozDoCliente no Railway, o serviço n8n apresentou falhas após reinicializações.

O erro observado indicava que uma chave de assinatura armazenada não podia ser lida utilizando a chave de criptografia da instância atual.

A falha impedia a inicialização consistente do ambiente e poderia comprometer a disponibilidade do serviço após novos deployments ou restarts.

## Impacto

O incidente ocorreu durante a implantação inicial do ambiente de produção.

Enquanto a configuração estava inconsistente:

- o n8n podia falhar após reinicializações;
- o editor e os workflows podiam ficar temporariamente indisponíveis;
- novos deployments não possuíam garantia de inicialização consistente.

Não houve impacto em usuários finais, pois o problema foi identificado e corrigido durante a preparação do ambiente de produção.

## Detecção

O problema foi identificado através dos logs do Railway durante a inicialização do container.

A mensagem principal observada foi relacionada à impossibilidade de ler a chave `signing.hmac` utilizando a chave de criptografia da instância.

## Causa raiz

A implantação inicial utilizava uma imagem em que o processo era executado como `root`.

Ao mesmo tempo, o volume persistente do Railway estava montado em:

`/home/node/.n8n`

Sem a definição explícita do diretório utilizado pelo n8n e sem uma chave de criptografia fixa, diferentes inicializações poderiam utilizar configurações incompatíveis com os dados persistidos anteriormente.

Isso fazia com que informações criptografadas por uma instância não pudessem ser lidas corretamente após uma nova inicialização.

## Correção

Foram realizadas as seguintes alterações no ambiente de produção:

- definição explícita de `N8N_USER_FOLDER=/home/node`;
- utilização do volume persistente em `/home/node/.n8n`;
- definição de uma `N8N_ENCRYPTION_KEY` fixa e armazenada como secret no Railway;
- reinicialização do armazenamento interno do n8n durante a configuração inicial, quando ainda não existiam dados produtivos relevantes;
- validação do comportamento após restart.

Após essas alterações, o serviço reiniciou normalmente e o usuário administrador permaneceu persistido.

## Ações preventivas

Para reduzir a possibilidade de recorrência:

- a chave `N8N_ENCRYPTION_KEY` deve permanecer fixa no ambiente de produção;
- a chave nunca deve ser armazenada no repositório Git;
- o diretório de dados do n8n deve permanecer associado ao volume persistente;
- mudanças na configuração de persistência devem ser testadas antes de serem aplicadas em produção;
- a versão da imagem do n8n foi fixada no `Dockerfile`, evitando alterações inesperadas causadas pela tag `latest`;
- deployments são acompanhados por validações automatizadas e testes do endpoint público.

## Aprendizados

O incidente demonstrou que containers descartáveis não eliminam a necessidade de persistência consistente para aplicações stateful.

No caso do n8n, banco de dados, arquivos persistentes e chave de criptografia fazem parte do estado da aplicação e precisam permanecer compatíveis entre diferentes execuções.

A resolução também reforçou a importância de observar logs de inicialização e testar explicitamente reinicializações durante a preparação de um ambiente produtivo.