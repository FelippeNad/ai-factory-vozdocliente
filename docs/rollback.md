# Teste de Rollback — VozDoCliente

## Objetivo

Validar que uma versão anterior conhecida do ambiente de produção pode ser restaurada e permanecer funcional em caso de falha em um novo deployment.

## Ambiente

- Plataforma: Railway
- Serviço: n8n
- Ambiente: produção
- Endpoint:

`https://n8n-production-7813.up.railway.app/webhook/review`

## Procedimento

Foi utilizado o histórico de deployments do Railway.

A versão ativa foi temporariamente revertida para o deployment anterior utilizando a funcionalidade de rollback da plataforma.

Após o rollback, o serviço retornou ao estado `ACTIVE`.

## Validação após rollback

Foi enviada uma requisição ao endpoint público com o identificador:

`ROLLBACK-TEST-001`

O workflow foi executado normalmente e o registro foi persistido no Airtable PROD.

Resultado:

**PASSOU**

Isso confirmou que a aplicação permaneceu funcional após a restauração de uma versão anterior.

## Restauração da versão atual

Após a validação do rollback, o deployment mais recente foi executado novamente através da opção de redeploy do Railway.

A versão atual retornou ao estado `ACTIVE`.

Foi então realizada uma nova validação utilizando:

`ROLLBACK-RESTORE-001`

O workflow foi processado normalmente no ambiente de produção.

Resultado:

**PASSOU**

## Resultado final

O procedimento confirmou que o ambiente permite:

- restaurar uma versão anterior conhecida;
- manter o endpoint público funcional após rollback;
- retornar posteriormente à versão mais recente;
- preservar a operação da aplicação durante o processo de recuperação.

O teste de rollback foi concluído com sucesso.