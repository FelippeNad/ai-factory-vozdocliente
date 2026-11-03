# Rotação de credenciais — procedimento operacional

Revisão documental: **02/11/2026**, baseline `718ce4d`. Este é um procedimento
para uso futuro autorizado e um exercício offline. **Nenhuma credencial real foi
lida, criada, substituída, revogada ou rotacionada nesta etapa.** Não houve deploy.

## Responsáveis e gatilhos

Funções abaixo são propostas: o projeto ainda precisa nomear titulares e substitutos.
Não considerar personagens do briefing como responsáveis formalmente designados.

| Função | Responsabilidade e evidência |
| --- | --- |
| Dono do serviço / CX | Aprovar janela, impacto e critérios de retomada; registrar autorização |
| Administrador do fornecedor | Criar/revogar credencial no ambiente correto e comprovar escopos/recursos sem revelar valor |
| Operação n8n/Railway | Inventariar consumidores, alterar a referência correta, verificar processos/workers e realizar rollback aprovado |
| Segurança | Revisar escopos, custódia, acesso, revogação e logs de uso; coordenar exposição/incidente |
| Segundo revisor | Conferir DEV/PROD, dependências e evidências antes de ação irreversível |
| Controlador/encarregado/jurídico | Avaliar impacto nos titulares e eventual comunicação; validar papel, contrato e canal |

Gatilhos: exposição/suspeita de uso indevido, desligamento ou mudança de acesso,
vencimento, migração de conta pessoal e revisão periódica. **Proposta interna**, a
aprovar: inventário mensal e revisão de validade/necessidade a cada 90 dias para
tokens estáticos, ajustando às políticas do provedor. Não é prazo legal nem
periodicidade para trocar cegamente a chave mestra do n8n.

## Inventário técnico confirmado e pendências

Os JSONs v3/v4 apontam para Credentials `openAiApi` e `httpHeaderAuth`, contendo
referências/nomes, não os valores. A retenção v1 exige selecionar uma credencial
DEV no único node HTTP e não exporta uma credencial preexistente.

| Ativo | Onde atua / como registrar |
| --- | --- |
| OpenAI API Key | Credential `openAiApi` em `LLM PROD`; registrar organização/projeto e dono real, pendentes de verificação |
| Airtable PAT | Credentials Header Auth da busca/criação e, separadamente, retenção DEV; mapear todos os consumidores antes de revogar |
| Slack Bot Token | Credential Header Auth no alerta; identificar app, workspace, instalação e associação ao canal |
| `N8N_ENCRYPTION_KEY` | Configuração persistente da instância, diferente das chaves dos provedores; banco/volume e chave precisam permanecer compatíveis |
| Segredos Railway | Variáveis por serviço/ambiente, referências compartilhadas, credenciais de banco, tokens de plataforma e integrações **se existentes**; inventário real não foi acessado |
| Variáveis não secretas | Base IDs, URLs, timezone e `RETENTION_*` não equivalem a senhas, mas alterações podem mudar destinos e habilitar exclusão; exigir revisão de mudança |

`.env.example` documenta nomes; **editar `OPENAI_API_KEY`, `AIRTABLE_PAT` ou
`SLACK_BOT_TOKEN` no ambiente não substitui automaticamente a Credential do n8n**
referenciada pelo workflow. Os Compose não repassam esses três tokens. Confirmar
a fonte efetiva em cada consumidor antes de mudar qualquer valor. Registrar
identificadores/versionamento do cofre, nunca token ou trecho reutilizável dele.

## Sequência comum para tokens, com autorização separada

1. Abrir registro de mudança: ativo, ambiente, dono, consumidores, escopos, motivo,
   janela, validação, rollback e segundo revisor. Verificar contas corporativas e
   menor privilégio; não copiar secrets de produção para DEV.
2. Definir se é rotação planejada ou incidente. Em exposição, a contenção pode
   exigir revogação imediata, mesmo com indisponibilidade; não manter token suspeito
   válido para “facilitar rollback”. Acionar segurança.
3. Em rotação planejada, criar substituto restrito **se o fornecedor permitir
   coexistência**. Guardar no cofre autorizado, com custódia separada das evidências.
   Para regeneração que invalida o antigo ou mudança de instalação, planejar janela.
4. Validar em DEV com dados sintéticos e atualizar todos os consumidores do ativo.
   A validação real necessita autorização própria; os testes desta entrega são mocks.
5. Na janela aprovada, aplicar a referência correta e verificar comportamento,
   permissões e identidade. Não ampliar escopos para resolver erro sem diagnóstico.
6. Após aceite, revogar o antigo no provedor e confirmar sua rejeição e a aceitação
   do novo em teste autorizado. Revalidar depois da revogação, inclusive canal Slack.
7. Encerrar com horários, IDs de mudança/versão, resultados, aprovadores e pendências.
   Revisar logs e remover cópias temporárias conforme política. Sem segredos em prints.

Antes de revogar, rollback pode retornar à referência anterior **apenas se ela
continua válida e não está comprometida**. Depois de revogar, rollback é recuperar
configuração e emitir outro token válido; não se “desrevoga” por restaurar um deploy.
Não foi implementada fila automática de contingência: parada/retomada exige plano
operacional e controle de reenvios/deduplicação.

## Particularidades por fornecedor

### OpenAI API Key

O administrador confirma projeto, permissões, validade e titularidade corporativa.
Cria substituta, atualiza a Credential do LLM e valida uma classificação sintética
no projeto correto, sem PII. Conferir contrato de saída, custo/autorização da chamada
e erros de autenticação/permissão. Após aceite, revoga a antiga e confirma que o
serviço continua usando a nova. A
[orientação oficial OpenAI de produção](https://developers.openai.com/api/docs/guides/production-best-practices)
recomenda esse ciclo e políticas de validade. Não executar endpoints administrativos
ou smoke tests reais como parte do exercício deste repositório.

### Airtable Personal Access Token

No Developer Hub, criar PAT substituto limitado à base necessária; não selecionar
todos os workspaces futuros. A
[documentação Airtable](https://support.airtable.com/articles/9934989703-creating-personal-access-tokens)
distingue criação, regeneração e exclusão: regenerar invalida o valor anterior.
Coexistência deve usar tokens separados e ser verificada, não presumida.

A classificação precisa de leitura/escrita de registros conforme seu contrato.
A retenção DEV usa `schema.bases:read`, `data.records:read` e `data.records:write`
para metadados, seleção e auditoria; DRY_RUN também grava auditoria. A permissão
de escrita é sensível e não prova autorização para excluir. Usar token e base
DEV exclusivos, manter `RETENTION_DRY_RUN=true` e as confirmações de DELETE vazias.
Validar metadados, leitura e auditoria sintética, sem DELETE. Atualizar busca,
criação e outros consumidores mapeados antes de revogar token compartilhado.

### Slack Bot Token

Identificar instalação e escopo mínimo para a postagem pretendida; verificar acesso
ao canal e evitar permissões amplas. Obter substituto por fluxo de instalação/OAuth
suportado pelo app; não presumir que reinstalar mantém o token antigo ou que dois
tokens do mesmo bot funcionam como chaves independentes.

Validar autenticação e postagem sintética em canal DEV autorizado. HTTP 200 não
basta: conferir `ok: true` no corpo. Revogar um bot token pode desativar o bot e
remover associações a canais; a retomada pode exigir nova autorização e entrada
no canal. Referência: [Slack `auth.revoke`](https://docs.slack.dev/reference/methods/auth.revoke/).
Não usar esse método nem seu modo de teste com tokens reais neste exercício.

A [rotação nativa Slack](https://docs.slack.dev/authentication/using-token-rotation/)
introduz access tokens de curta duração e refresh tokens; a documentação indica
expiração em 12 horas e alerta sobre habilitação não reversível. Os nodes atuais
são HTTP com Header Auth estático, sem ciclo de refresh implementado. Não habilitar
essa opção sem projeto e teste específicos; trocar o token estático não implementa
renovação OAuth. Client secret/signing secret também não são o bot token.

### Railway: segredos e configuração

Inventariar serviço, ambiente, referências e consumidores sem exportar valores.
Usar cofre corporativo como origem de recuperação e avaliar sealed variables:
segundo a [documentação Railway](https://docs.railway.com/guides/variables), elas
não revelam valores pela UI/API e têm restrições de cópia. Isso não protege contra
aplicação que imprime o valor. Nunca executar `env`, `printenv`, dump de variáveis
ou Raw Editor em gravações da demonstração.

No procedimento real, mudanças de variáveis ficam staged e precisam ser revisadas
e implantadas para produzir efeito. Aqui, **nem staging de segredo nem deploy foi
feito**. Alterar uma senha de banco, se configurada, também exige coordenar o lado
do banco e seus clientes; mudar só a URL/variável não rotaciona a senha no servidor.
Rotacionar token de acesso à plataforma, quando existente, é outra operação.

Registrar o conjunto de referências compatível antes da mudança. Um rollback de
deployment pode recuperar variáveis antigas e apontar para token já revogado:
conferir política real de restauração, variáveis por ambiente, workers e referências.
Um segredo sealed precisa de cópia de recuperação no cofre, não de screenshot.
Manter `RETENTION_DRY_RUN=true` em validações; não liberar exclusões durante rotação.

## n8n: chave mestra, chave de dados e recuperação

O [post-mortem do projeto](../postmortem-n8n-encryption-key.md) mostra o risco de
incompatibilidade entre chave e persistência. O reset feito na implantação inicial
não é procedimento de rotação para um banco com dados. Não apagar banco, config
ou volume para tentar recuperar credenciais.

**Troca de token:** o conteúdo de uma Credential muda; a chave da instância fica.
**Rotação DEK:** nas versões/configurações compatíveis, n8n troca a chave de dados,
mantendo `N8N_ENCRYPTION_KEY`. A
[documentação atual de rotação n8n](https://docs.n8n.io/hosting/securing/encryption-key-rotation/)
descreve recriptografia progressiva e incompatibilidades de rollback. Não equivale
a substituir a variável de ambiente. O projeto fixa `2.28.7` no Compose e `2.41.7`
no Dockerfile; recurso e estado efetivos não foram verificados. A documentação
alerta para desabilitação antes de `2.40.3`: não aplicar uma receita de versão nova
à instância antiga. Nenhum recurso novo foi habilitado nesta entrega.

**Substituição de `N8N_ENCRYPTION_KEY`:** mudança excepcional de chave mestra,
distinta das duas anteriores. A [configuração oficial](https://docs.n8n.io/hosting/configuration/configuration-examples/encryption-key/)
e a persistência precisam ser tratadas em conjunto. Trocar somente a variável pode
tornar dados cifrados ilegíveis; voltar à antiga só ajuda se o estado correspondente
ainda é recuperável. Todas as instâncias/workers devem usar o conjunto compatível.

Procedimento de preparação para uma futura intervenção autorizada:

1. Identificar versão exata, modo de execução, feature flags e todos os dados
   cifrados: Credentials, OAuth e outros segredos/estado de assinatura. Não presumir
   que exportar somente Credentials cobre tudo.
2. Suspender escritas conforme plano, produzir backup consistente de banco e estado
   persistente, e custodiar a chave original separadamente. Testar restauração em
   cópia isolada com egress bloqueado; nunca ligar clone produtivo às integrações.
3. Se o objetivo for DEK, verificar suporte/documentação da versão e validar em
   laboratório a operação suportada. Não alterar a mestra. Registrar impacto de
   formato e requisitos de versão antes de habilitar o recurso.
4. Se a mestra estiver comprometida e precisar ser substituída, exigir plano de
   migração suportado para **todo** o estado cifrado, ou reconstrução controlada de
   instância/credenciais e reautorizações, com revisão especializada. Não há uma
   migração da mestra validada para este projeto; na ausência dela, parar aqui.
5. Validar leitura e uso das credenciais sintéticas, restart, todos os workers e
   restauração do par antigo em laboratório. A mera abertura do editor não comprova
   decifragem. Não fazer downgrade de formato sem procedimento suportado.
6. Rollback usa versão, banco/volume/config e chave correspondentes ao snapshot,
   evitando mistura de estado novo e chave antiga. Se a chave antiga foi exposta,
   isolar a recuperação e avaliar também a revogação dos tokens que ela protegia.

Exportações de Credentials com `--decrypted`, previstas na
[CLI oficial](https://docs.n8n.io/hosting/cli-commands/), contêm segredos em texto
claro. Não gerá-las na demonstração, no repositório, em logs ou storage temporário
sem controle. Export cifrado sem a chave necessária não é recuperação comprovada.
Não foram fornecidos comandos de migração real para uma versão não validada.

## Credencial exposta no histórico Git

1. Tratar como potencial comprometimento: registrar ocorrência sem copiar o valor,
   conter/revogar com o administrador e substituir conforme procedimento de incidente.
2. Identificar superfícies: commits/branches/tags, forks, clones, caches, PRs, CI,
   artifacts, imagens e capturas. Restringir acesso às evidências de investigação.
3. Avaliar acessos/custos e dados pessoais alcançáveis. Acionar controlador/encarregado
   para art. 48 e [regras ANPD de incidentes](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis).
   A necessidade de comunicação depende de risco/dano relevante e regras aplicáveis;
   o procedimento geral indica três dias úteis, com ressalvas. Não aguardar limpeza
   Git para avaliar o prazo. Nenhuma comunicação foi realizada por este exercício.
4. Depois da contenção, preparar plano de expurgo com administradores: reescrita de
   histórico afeta hashes/assinaturas, exige coordenação de clones e pode não remover
   cópias externas. Não executar force push ou reescrita automaticamente.
5. Reexaminar histórico e working tree com scanner aprovado e saída redigida;
   guardar versão/configuração/hash do relatório. Um resultado antigo “sem leaks”
   não prova ausência atual; `.gitignore` não remove commits anteriores.

O repositório contém um relato histórico de Gitleaks e uma allowlist estreita para
um placeholder. Isso não comprova rotação ou migração de conta pessoal. Não ampliar
allowlist para esconder segredo real. Não houve nova varredura completa do histórico
nesta etapa, nem foram lidos `.env` reais ou relatórios que possam conter tokens.

## Exercício simulado, reproduzível e sem contas reais

O script [simular_rotacao_credenciais.py](../../scripts/simular_rotacao_credenciais.py)
usa identificadores abstratos em memória. Quatro casos com nomes de provedores
usam **o mesmo protocolo fictício**, não suas APIs: token inválido, rollback antes
de revogar, troca validada, isolamento DEV, revogação e bloqueio do rollback após
revogação. O modelo n8n demonstra compatibilidade chave/estado, sem criptografia
n8n, migração ou backup real; um cenário bloqueia rotação Slack sem refresh.

```powershell
python scripts/simular_rotacao_credenciais.py --output docs/security/evidencias/rotacao-simulada.json
python scripts/simular_rotacao_credenciais.py --verify docs/security/evidencias/rotacao-simulada.json
```

Resultado efetivamente obtido: **38 cenários simulados aprovados**, zero chamadas
de rede, artefatos operacionais inalterados. O
[relatório gerado](evidencias/rotacao-simulada.json) registra timestamp UTC,
expectativa/resultado de cada cenário e hashes antes/depois de quatro workflows,
dois Compose, Dockerfile e `.env.example`, além do hash da fonte do simulador.

`--verify` verifica checksum, repete os cenários e compara os artefatos atuais.
Hashes de JSON usam serialização canônica; texto usa LF e codificação JSON antes
do SHA-256. Não confundir com hash de blob Git. Alterar artefato torna a evidência
desatualizada; gerar novo relatório somente depois de revisar a mudança. O checksum
não é assinatura nem prova de autoria e não impede alguém de editar e recalculá-lo.

O relatório informa `real_rotation=false`, `real_provider_validation=false` e
`n8n_crypto_validated=false`. Ele comprova o exercício de estados, **não comprova
revogação em fornecedor, decifragem n8n, migração corporativa ou execução no Railway**.
Validação real permanece manual e depende de autorização separada.

Para apresentar: mostrar o inventário sem valores, executar os dois comandos,
abrir os cenários de rejeição/rollback e comparar hashes. Complementar com o
[roteiro de evidências](../lgpd/roteiro-evidencias.md) e
[checklist de pendências](../lgpd/checklist-etapa-2.md).
