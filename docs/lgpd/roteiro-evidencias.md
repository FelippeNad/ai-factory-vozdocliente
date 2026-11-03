# Roteiro de demonstração e evidências — Etapa 2

Revisão: 02/11/2026. Usar branch `etapa-2`, fixtures sintéticas e ambiente local.
Não acessar serviços de produção, revelar tokens, habilitar limpeza ou fazer deploy
para apresentar esta entrega. A ordem abaixo é uma sugestão, não resultado de uma
apresentação já realizada.

## Registro das evidências existentes

| Evidência | O que se observa / alcance | O que não comprova |
| --- | --- | --- |
| [Canvas sanitização](../evidencias/etapa2-sanitizacao-pii-n8n.png) | Webhook ligado a `Sanitizar PII` antes de `LLM PROD`; sanitizador com indicação de execução | Input/output da máscara, versão exata, chamada LLM bem-sucedida, ausência de dados pessoais fixados ou deploy ativo |
| [Canvas retenção](../evidencias/etapa2-retencao-dry-run.png) | Percurso da agenda/motor/guard/gate e stub `Airtable DEV operacao` do tipo Code; retorno ao resumo | Exclusão real, persistência no Airtable, métricas finais ou aprovação jurídica |
| [Relatório da rotação simulada](../security/evidencias/rotacao-simulada.json) | 38 cenários executados em memória, checksum e hashes antes/depois; script permite repetir a checagem | Rotação/revogação em fornecedor, criptografia n8n, custódia ou titularidade de conta |
| [Evidências históricas](../evidencias/evidencias-projeto.md) | Relatos/capturas da Etapa 1, identificados como históricos | Estado atual da produção ou execução dos controles novos |

As duas capturas de canvas já estavam no baseline e foram inspecionadas visualmente
nesta revisão; não foram criadas novas capturas de UI. Revisar material antes de
compartilhar: o fato de estar no Git não o torna automaticamente seguro/publicável.

## Demonstração recomendada

1. **Escopo e integridade.** Mostrar `git status --short --branch` e
   `git log -1 --oneline`; explicar baseline `718ce4d` e alterações locais sem commit.
   Não abrir `.env` real, Raw Editor, cofres ou console com variáveis. Conferir com
   `git diff --name-only` que os workflows funcionais não foram editados.
2. **Mapa e escolhas.** Mostrar [mapa](mapa-dados-pessoais.md): original entra no
   Webhook, v4 reduz prompt/Slack mas conserva original no Airtable; PostgreSQL/logs
   são outro armazenamento. Apontar hipóteses legais e papéis ainda não aprovados.
3. **Transferência.** Abrir a [matriz por fornecedor](transferencia-internacional.md).
   Explicar a diferença entre hipótese de tratamento, mecanismo internacional e
   região de conta; mostrar referências brasileiras e dossiê pendente, sem inventar DPA.
4. **Sanitização.** Executar testes abaixo. Na UI, usar fixtures e uma cópia com
   stubs para APIs; mostrar input/output do sanitizador e bloquear texto ausente.
   Não clicar no HTTP de produção. Capturar exemplos sintéticos e erro genérico.
5. **Retenção DRY_RUN.** Seguir o
   [roteiro offline existente](../etapa-2-retencao-exclusao.md#demonstração-local-sem-apis-e-sem-credenciais).
   Importar a DEMO inativa e executar manualmente. Mostrar que o transporte é Code,
   não HTTP. Esperado: 6 analisados, 2 elegíveis, 0 excluídos, 3 páginas, 2 inválidos;
   `partial` é intencional. Capturar também o painel do resumo e os settings.
6. **Rotação simulada.** Executar os comandos de geração/verificação abaixo. Abrir
   os cenários de token inválido, troca, revogação e rollback bloqueado; no modelo
   n8n, mostrar falha da troca cega de mestra e restauração do par correspondente.
   Exibir as flags que negam rotação real e a identidade dos hashes antes/depois.
7. **Histórico interno e recuperação.** Mostrar no Compose dedicado a proposta de
   sete dias/1000 execuções, contrastando com 30 dias demonstrativos das reviews e
   máximo de 90 dias de logs no briefing. Explicar que não foi aplicada a produção
   e que pruning/lixeira/backups têm limitações; não apagar volume para “demonstrar”.
8. **Pendências e revisão.** Apresentar [checklist](checklist-etapa-2.md), responsáveis
   a nomear e critérios para integração DEV, segurança e jurídico. Registrar dúvidas
   do professor e validações futuras, sem declarar nível ou conformidade integral.

## Comandos offline na raiz do repositório

```powershell
python tests/validate_workflows.py
python tests/test_routing_logic.py
python -m unittest discover -s tests -v
python scripts/build_retention_workflow.py --check
node tests/test_pii_sanitization.cjs
node tests/test_retention.cjs
python scripts/simular_rotacao_credenciais.py --output docs/security/evidencias/rotacao-simulada.json
python scripts/simular_rotacao_credenciais.py --verify docs/security/evidencias/rotacao-simulada.json
git diff --check
```

Python 3.12+ e Node 22+; não há instalação npm necessária. Se Node não estiver no
PATH desta máquina, o executável usado nas validações está em
`%LOCALAPPDATA%\Programs\Bionic\resources\app\.webpack-bionic\bin\node.exe`.
Isso é caminho local, não dependência a hardcodear no CI.

Validação efetivamente repetida nesta revisão: 29 verificações estruturais,
10 verificações de roteamento, 22 testes Python, 102 casos de sanitização e
97 casos de retenção aprovados; exports de retenção sincronizados. A simulação
aprovou seus 38 cenários, e a verificação aceitou o relatório original e rejeitou
checksum adulterado, resultado adulterado com checksum recalculado e schema inválido.
Os links locais examinados não tinham destinos ausentes; `git diff --check` passou.
O CI remoto, a engine n8n e os fornecedores não foram executados nesta revisão.

`--output` atualiza o relatório da simulação com novo timestamp. Para verificar a
evidência já entregue sem regravá-la, usar apenas `--verify`. A verificação compara
os artefatos operacionais atuais; após mudança aprovada, a evidência precisa ser
regenerada. Checksum é consistência, não assinatura digital ou atestado de terceiro.

## Capturas adicionais a produzir e validação manual

| Captura / registro | Critério de aceitação |
| --- | --- |
| Terminal de testes | Comandos, versão do runtime, contagens e falhas visíveis; sem dumps de variáveis |
| Input/output da sanitização | Apenas dados sintéticos; marcador e frase útil preservados; nenhum fallback |
| Resumo DEMO e settings | DRY_RUN, métricas esperadas e workflow inativo; identificar que auditoria é simulada |
| Integração Airtable DEV, opcional e autorizada | Base dedicada, credencial sem valor visível, reviews intactas antes/depois, auditoria agregada real e DRY_RUN; nenhuma exclusão |
| Revisão de contas/contratos | Aprovação real, versão/documento/parte/região identificados em registro restrito; não substituir por print de página pública |
| Ensaio n8n criptográfico e backup | Laboratório isolado, versões/chave/estado compatíveis e restauração comprovada; permanece pendente |
| Pruning em execução | Histórico sintético e horários observados, considerando buffer e exceções; permanece pendente |

Nomear novas capturas com componente e escopo, por exemplo `etapa2-retencao-demo-resumo.png`.
Registrar data, versão do workflow/engine, autor e revisão. A sessão não produz
aprovação humana automaticamente. Segredos e dados pessoais reais não devem aparecer
em terminal, prints, vídeo, issues, PRs, anexos ou logs publicados.
