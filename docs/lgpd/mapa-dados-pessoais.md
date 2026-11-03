# Mapa de dados pessoais — VozDoCliente

Revisão documental: **02/11/2026**, branch `etapa-2`, baseline `718ce4d`.
O briefing descreve uma empresa fictícia. Este mapa prepara a avaliação do cenário
empresarial; não comprova contratos, nomeações, bases legais ou conformidade integral.
O exercício acadêmico não autoriza usar dados reais de clientes.

## Escopo e evidências

Foram examinados [README](../../README.md), [ADR-001](../adr/ADR-001-stack.md),
[ADR-002](../adr/ADR-002-deploy-e-ambientes.md), [schema Airtable](../airtable-schema.md),
[variáveis de exemplo](../../.env.example), os dois Compose, workflows v3/v4 e
retenção v1/DEMO e suas fontes. A arquitetura documenta Railway e PostgreSQL em
produção; o Compose local usa volume n8n e não provisiona PostgreSQL.

**Confirmado no código** não significa confirmado no ambiente publicado:

- V3: export `active=true`; LLM recebe texto original; Airtable recebe os originais;
  Slack recebe nome, origem, nota e texto. Parser pode incluir resposta em erro.
- V4: export inativo; somente `review_text_sanitized` segue ao LLM, sem fallback;
  Airtable ainda recebe os originais; Slack recebe tema, nota e instrução fixa.
- Retenção v1/DEMO: inativas. A v1 permite exclusão DEV sob bloqueios e DRY_RUN
  padrão. A DEMO não tem HTTP. Não há comprovação de limpeza produtiva nesta revisão.
- Settings da instância, permissões, região, fornecedores contratados e versão
  efetivamente ativa precisam de inspeção autorizada pelo responsável.

## Categorias e titulares

| Grupo | Dados / pessoas potencialmente afetadas |
| --- | --- |
| D1 — identificação e contato | `customer_name`; CPF, e-mail, telefone, CEP, endereço, identificadores em URLs e pedidos escritos no texto; cliente final e terceiros mencionados |
| D2 — avaliação e inferências | `review_id`, `source`, `rating`, `review_text`, `sentiment`, `theme`, `processed_at`; vinculáveis ao cliente por cruzamento |
| D3 — tráfego e operação | IP, headers, cookies, query, timestamps, IDs de execução e eventos de erro potencialmente disponíveis no ingresso/proxy/editor; coleta efetiva ainda a verificar |
| D4 — administração e segurança | Contas de administradores/CX, e-mails corporativos, permissões e trilhas de acesso, conforme serviços utilizados; tokens e chaves são segredos, não automaticamente dados pessoais |
| D5 — conteúdo incidental | Saúde, religião, opinião política, dados de crianças ou de terceiros podem aparecer em texto livre; não são solicitados e não há detector completo |

CNPJ de pessoa jurídica não é automaticamente dado pessoal; associação a MEI ou
pessoa identificável exige análise. As categorias são inventário de possibilidade,
não afirmação de que todos esses dados foram encontrados na base.

## Hipóteses legais a avaliar, não bases já aprovadas

Referência: [LGPD, texto atualizado da Câmara](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html).

| Código | Hipótese e condição |
| --- | --- |
| B1 | Art. 7º, V: atendimento necessário ao contrato com o titular; contrato B2B, sozinho, não prova essa condição |
| B2 | Art. 7º, IX e art. 10: legítimo interesse, sujeito a avaliação de necessidade, expectativas, impactos e salvaguardas |
| B3 | Art. 7º, II: obrigação legal/regulatória identificada; não basta chamar armazenamento de “compliance” |
| B4 | Art. 7º, VI: exercício regular de direitos, com necessidade e contexto demonstrados |
| B5 | Art. 7º, I e art. 8º: consentimento específico, demonstrável e revogável, somente se adequado ao caso |

Para B2, preencher avaliação antes da escolha, conforme
[orientação da ANPD sobre legítimo interesse](https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-lanca-guia-orientativo-sobre-legitimo-interesse).
Nenhuma dessas hipóteses é adotada universalmente por este projeto. Dados sensíveis
exigem exame do art. 11; crianças/adolescentes, do art. 14. A exceção acadêmica do
art. 4º, II, b não dispensa os arts. 7º e 11. Não usar a disciplina como justificativa
para um piloto empresarial com dados reais. Segurança dos arts. 46–49 não é, por
si, hipótese do art. 7º.

## Operações e destinos

Os códigos B representam alternativas condicionais para o responsável avaliar por
operação. A escolha precisa registrar justificativa, contrato/instrução, aprovador
e data. Componentes de infraestrutura não criam uma finalidade autônoma de CX.

| ID / componente | Coleta, processamento, armazenamento ou compartilhamento | Finalidade | Hipótese a avaliar | Retenção/exclusão e pendência |
| --- | --- | --- | --- | --- |
| M01 — canal / Webhook | Recebe D1/D2; envelope pode conter D3; entrada de avaliações de canais externos | Receber solicitação e encaminhar tratativa | B1 ou B2; B5 apenas se escolhido e comprovado | Sanitização ocorre depois da entrada; autenticação/rate limit e aviso na origem precisam ser verificados |
| M02 — n8n | Mantém original em memória; v4 mascara padrões e valida saída; merge retoma o original; pode manter execuções/editor | Orquestrar triagem e atendimento | A hipótese da operação de CX, B1/B2, conforme instrução | V4 não salva sucesso/erro/manual/progresso; isso não apaga memória, itens em andamento ou passado |
| M03 — OpenAI | HTTP `/v1/chat/completions`; v3 envia `review_text`; v4 envia só texto sanitizado, ainda potencialmente pessoal; recebe classificação | Inferir tema e sentimento | B1/B2 somente após demonstrar necessidade desse fornecedor; mais mecanismo internacional | Retenção/configuração da conta não comprovada; excluir Airtable não exclui cópias do provedor |
| M04 — Airtable `Reviews` | Consulta `review_id`; grava nome, origem, nota, texto original, inferências e data | Fila de CX e consulta de resultados | B1/B2; B3/B4 apenas para preservação justificada | Política demonstrativa de 30 dias só implementada para DEV; lixeira, snapshots e produção pendentes |
| M05 — Slack | V3 replica nome/texto; v4 envia tema/nota sem ID/nome/texto; membros e apps do canal recebem alerta | Mobilizar CX para negativas | B1/B2, avaliando necessidade do compartilhamento | Limpeza de mensagens antigas, notificações, exports e apps não implementada; nota/tempo ainda podem permitir correlação |
| M06 — Railway | Hospeda serviço n8n; pode processar corpo em trânsito/memória, eventos, logs, volumes e backups; D4 na administração | Disponibilizar infraestrutura | A hipótese da operação hospedada; segurança/logs sob B2 ou B3 se fundamentados | Região, acesso de suporte, logs e backups não inspecionados; padrões DEV não foram aplicados à produção |
| M07 — PostgreSQL | Banco interno n8n segundo ADRs; pode conter execuções originais, usuários e credenciais cifradas, conforme settings | Persistir estado da automação | A hipótese de CX para payloads; B2/B3 avaliados separadamente para trilhas | Pruning é independente do Airtable; verificar banco e configurações reais; backups requerem política própria |
| M08 — retenção DEV | Lê metadados, IDs técnicos e só `processed_at`; seleciona, relê, exclui sob condições | Descartar registros fora da finalidade operacional | Instrução do controlador; arts. 15/16 e princípios do art. 6º, não uma “nova autorização” genérica | DRY_RUN padrão; limites e auditoria prévia; DELETE real não demonstrado e não autorizado nesta entrega |
| M09 — `RetentionAudit` | Contagens, datas, modo, códigos fixos e ID da execução; preview transitório de IDs/datas no DRY_RUN | Demonstrar execução e falhas da política | B2/B3, se justificados; art. 37 como referência de registro | Prazo de auditoria ainda a aprovar; 90 dias é proposta demonstrativa, sem rotina própria de descarte |
| M10 — Git / evidências / máquina DEV | JSONs e capturas podem revelar exemplos, IDs, nomes, conteúdo e segredos se mal exportados | Reprodutibilidade e avaliação acadêmica | Somente fixtures sintéticas na entrega; qualquer dado real exige avaliação própria | Revisar capturas e histórico; não publicar `.env`, dumps ou exports decifrados; exclusão Git não revoga tokens |

Na v4, o caminho do original ao Airtable é intencional e continua no escopo de
proteção; sanitização antes do LLM não cobre todos os destinos. A deduplicação
ocorre depois do LLM e não impede novos envios do texto em reprocessamentos.

## Papéis, instruções e acesso

A referência de papéis é o art. 5º, VI/VII/IX e a
[orientação da ANPD sobre agentes](https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-publica-guia-orientativo-sobre-agentes-de-tratamento-e-encarregado).
**Nenhum papel contratual ou nomeação foi comprovado** nesta revisão.

| Participante | Fato disponível | Hipótese que exige validação |
| --- | --- | --- |
| Loja/marketplace cliente | Briefing diz que dados dos clientes finais vêm das lojas | Controlador do atendimento, se decide finalidade/meios essenciais; comprovar relação com titular e instruções |
| VozDoCliente | SaaS fictício coordena o fluxo segundo briefing | Operador na tratativa sob instruções; possível controlador em finalidades próprias, a avaliar separadamente |
| OpenAI, Airtable, Slack e Railway | Destinos técnicos/infraestrutura documentados | Operador ou suboperador para conteúdo de cliente conforme cadeia contratual; possíveis finalidades próprias de conta/segurança; não presumir papel único |
| n8n / PostgreSQL | Software de orquestração e tecnologia de banco | O software não é agente por si; identificar entidade que hospeda/administra e eventual acesso do fornecedor |
| Equipe CX e administradores | Destinatários funcionais previstos | Acesso sob autorização, segregação por cliente e confidencialidade; não presumir que todo membro de um canal precisa de acesso |
| Encarregado, responsável de segurança e aprovadores | Funções necessárias ao procedimento | Pessoas, poderes, canal e substitutos ainda não nomeados; personagens do briefing não são nomeações comprovadas |

Antes de piloto, obter instruções por cliente, matriz de acesso, donos das contas,
relação de suboperadores e evidência de revisão. Contratos não foram consultados.

## Retenção, reidentificação e riscos

[Retenção técnica](../etapa-2-retencao-exclusao.md): 30 dias demonstrativos em
`Reviews` DEV; igualdade ao cutoff, datas inválidas e recentes são mantidas.
DELETE exige DEV, confirmações, leitura completa, limites, auditoria e releitura.
Lixeira/snapshots não são eliminados pelo workflow. Não foi implementado legal hold
ou identificação automática de tratativa aberta: isso bloqueia adoção irrestrita.

[Compose dedicado](../../n8n-mirror/docker-compose.retention.yml): propõe não salvar
payloads e pruning interno de sete dias/1000 execuções, com buffer/intervalos.
Não comprova limpeza produtiva. O [briefing](../../BRIEFING.md) limita logs a
**90 dias**, um requisito do projeto, não um prazo da LGPD. Aprovar prazos menores
por finalidade e verificar exceções, logs Railway, PostgreSQL, backups e fornecedores.

Nomes, endereço livre e contexto raro podem sobreviver às regex. IDs técnicos,
datas, nota e tema permitem correlação; máscaras não demonstram anonimização
(referência: art. 12). Separar ou cifrar dados também não elimina sua natureza
pessoal. O histórico n8n pode conter o original; errors HTTP/proxy, debug e
capturas podem copiá-lo. `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` amplia a importância
de restringir editores e nodes: não conceder edição de workflow a pessoas sem
autorização para o ambiente.

Para cada risco, registrar responsável e evidência no
[checklist de conformidade](checklist-etapa-2.md). Direitos dos titulares (arts.
18–20), aviso de privacidade, canal, revisão humana e resposta a incidentes ainda
precisam de procedimento validado. O sentimento não deve, sem avaliação adicional,
decidir direitos ou prioridade discriminatória. Este mapa não substitui RIPD,
teste de balanceamento, contrato ou parecer.

Próximos documentos: [transferência internacional](transferencia-internacional.md),
[rotação de credenciais](../security/rotacao-credenciais.md) e
[roteiro de evidências](roteiro-evidencias.md).
