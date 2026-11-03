# Checklist de segurança e LGPD — Etapa 2

Revisão de preparação: **03/11/2026**, HEAD local `27652b0` mais alterações ainda sem commit.
Esta matriz cobre os requisitos informados na conversa e no briefing. A rubrica
integral da PUCPR não está anexada ao repositório; a atribuição do nível **Autônomo**
cabe ao professor. Não é certificação de conformidade nem autorização de produção.

**Implementado** = artefato/mecanismo presente. **Validado** = verificação com
escopo indicado. **Pendente** = execução, aprovação ou evidência ausente.
**Revisão jurídica** = conclusão depende de contexto, contratos e responsável.
Uma validação offline não comprova aplicação no ambiente publicado.

| Requisito | Estado e evidência disponível | Pendência / critério para fechar | Responsável proposto |
| --- | --- | --- | --- |
| Inventário de coleta, processamento e destinos | Implementado: [mapa M01–M10](mapa-dados-pessoais.md), por versão e componente | Validar versão ativa, dados efetivamente coletados e inventário das contas | Operação + privacidade |
| Categorias pessoais, inferências e dados incidentais | Implementado: D1–D5, sem inferir anonimização | Verificar minimização na origem e casos sensíveis/menores antes de dados reais | Controlador + jurídico |
| Base legal por finalidade | Revisão jurídica: hipóteses B1–B5 com artigos e condições | Registrar decisão por operação; evidência contratual ou avaliação de legítimo interesse quando pertinente | Controlador + jurídico |
| Controlador, operador e destinatários | Implementado como hipóteses fundamentadas no briefing | Nomear entidades/pessoas e formalizar instruções; nenhum contrato foi comprovado | Controlador + gestão |
| Transferência internacional | Implementado: [avaliação e dossiê](transferencia-internacional.md), LGPD/Res. 19/2024 e referência à adequação UE | Confirmar país, cadeia, conta e instrumento aplicável **por fornecedor** | Jurídico + compras + operação |
| Aviso e canal do titular | Pendente | Aviso que reflita destinos/prazos reais, canal e responsáveis nomeados | Controlador/encarregado |
| Acesso, correção, oposição e exclusão do titular | Pendente; retenção periódica não substitui esse processo | Validar identidade proporcionalmente, localizar cópias e registrar decisões por solicitação | CX + privacidade |
| Decisões automatizadas e revisão | Pendente; LLM apenas classifica no código examinado | Avaliar efeitos reais do roteamento e necessidade de revisão/contestação, art. 20 | Produto + jurídico |
| PII antes do LLM | Implementado na v4; testes JS/grafo e validação local informada pelo responsável; [captura do canvas](../evidencias/etapa2-sanitizacao-pii-n8n.png) existente | Evidência adicional do input/output sintético; confirmar versão publicada sem inferir do export | Operação |
| Ausência de fallback e erros customizados sem conteúdo | Implementado/validado offline na v4 | Rever erros HTTP, proxy e logging de infraestrutura | Segurança + operação |
| Risco de reidentificação | Documentado: regex não cobre nomes/contexto nem torna dado anônimo | Avaliar corpus, minimização e usos posteriores | Privacidade + produto |
| Minimização Slack / Airtable | Implementada minimização Slack v4; Airtable conserva original | Rever necessidade de campos e acesso; tratar mensagens/copias antigas | CX + segurança |
| Retenção periódica configurável | Implementado na retenção v1; Schedule, 30 dias demonstrativos, DRY_RUN e limites | Aprovar prazo/finalidade; permanece DEV e inativo; não houve DELETE real | Controlador + operação |
| Paginação, datas e bloqueios | Testes offline; usuário informou `retention-6` DEV: 4 analisados, 2 elegíveis, 2 páginas, 0 exclusões/falhas | Revalidar importação com observabilidade; preservar reviews e DRY_RUN | Operação |
| Auditoria de quantidade e falhas | Usuário informou persistência/finalização em `retention-6`; sem texto/IDs individuais na auditoria | Definir acesso, prazo e descarte próprio; nova importação ainda precisa de regressão DEV | Operação + segurança |
| Observabilidade DEV | [Retenção](../etapa-2-observabilidade.md) e [Router integrado](../etapa-2-observabilidade-router.md): eventos mínimos, métricas, alerta opt-in e relatório local; testes/simulação sem rede. Usuário informou validação anterior do Router otimizado e Slack DEV, sem validar esta integração nova | Validar subworkflows, saídas de erro no engine, Error Trigger automático, Console/stdout, entrega e ausência de alerta duplicado. Crash/watchdog, coleta durável, descarte por idade e acurácia humana pendentes | Operação + segurança |
| Retenção interna n8n / logs ≤90 dias do briefing | Configuração proposta/validada sintaticamente no Compose dedicado: 7 dias/1000 execuções; export v4 sem salvar payloads | Pruning em execução, exceções, PostgreSQL e logs/backups Railway não comprovados; não aplicar automaticamente à produção | Infraestrutura |
| Recuperação / legal hold | Procedimento documentado; corridas e desfechos incertos reconhecidos | Testar restauração em isolamento; tratar casos abertos/preservação antes de habilitar exclusão | Operação + controlador |
| Gestão corporativa de credenciais | Procedimento e inventário documental implementados | Comprovar donos corporativos, escopos e segregação; nomes no JSON não provam titularidade | Administradores + segurança |
| Rotação e rollback de tokens | [Procedimento](../security/rotacao-credenciais.md) implementado; 38 cenários **simulados** validados | Autorização e ensaio DEV real separados; nenhum token real foi rotacionado | Segurança + administradores |
| Chave n8n / DEK / compatibilidade | Distinção documentada; modelo de estado simulado | Verificar suporte nas versões, backup/restauração e migração; sem ensaio criptográfico real | Operação n8n |
| Exposição em Git e incidentes | Procedimento de contenção, revogação e coordenação documentado | Gitleaks local e revisão visual nesta preparação. Originais de capturas com identificação permanecem no histórico público; ocultação no workspace não os remove. Tratar publicação/histórico somente com autorização específica; ver auditoria da entrega | Segurança |
| Controle de acesso / autenticação | Pendente de verificação de instância; Compose limita porta local | Confirmar MFA quando disponível, RBAC, acesso de editores, webhook e segregação por cliente; revisar `$env` | Segurança + infraestrutura |
| Evidências verificáveis | Relatório simulado com cenários e hashes; testes disponíveis; [roteiro](roteiro-evidencias.md) | Registrar apresentação e aprovações humanas sem secrets; não transformar mock em prova de fornecedor | Autor da entrega + revisor |

## Registro de revisão e aceite

| Decisão | Estado nesta entrega |
| --- | --- |
| Aprovação dos prazos e exceções | Pendente — nenhum aprovador nomeado |
| Aprovação de base legal / transferências | Pendente de revisão jurídica e contratual |
| Acesso a produção / rotação real / exclusão real | Fora do escopo autorizado desta entrega |
| Resultado do exercício simulado | 38 cenários aprovados; [relatório](../security/evidencias/rotacao-simulada.json) verificável pelo script |
| Resultado de integração com contas reais | Responsável informou sanitização, Router otimizado (nova/duplicata/falha segura), retenção DRY_RUN com auditoria e alerta sintético recebido no Slack DEV. Três workflows observáveis posteriores e dashboard real continuam pendentes; nenhuma API do produto executada nesta auditoria |

O [roteiro](roteiro-evidencias.md) separa o que já existe do que ainda precisa ser
capturado. Caso testes/artefatos mudem, atualizar a evidência correspondente sem
reescrever como realizados controles que permanecem pendentes.
