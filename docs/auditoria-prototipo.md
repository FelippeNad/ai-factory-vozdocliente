# Auditoria do protótipo VozDoCliente

**Data:** 04/10/2026  
**Escopo:** estado herdado do repositório `ai-factory-vozdocliente`, antes das melhorias de robustez, segurança e operação. Esta auditoria não altera a lógica do sistema.

A análise abrange os workflows Make/n8n, Docker Compose, documentação, configuração de exemplo e testes existentes. As constatações sobre os arquivos foram verificadas no repositório; o funcionamento das integrações locais abaixo foi informado pelo responsável pelo projeto e não foi reexecutado nesta auditoria. Não foram inspecionadas as contas externas nem o workflow salvo na instância n8n.

## 1. O que já funciona

### Arquitetura atual

O protótipo recebe uma avaliação via webhook, classifica sentimento e tema com um LLM, interpreta a resposta JSON, grava os dados no Airtable e envia alerta ao Slack quando o sentimento é negativo.

```text
Webhook POST /review
  → LLM: sentiment + theme
  → interpretação do JSON e combinação com a avaliação original
  → criação de registro no Airtable (Reviews)
  → condição: sentiment == "negativo"
      → verdadeiro: alerta no Slack (#cx-alertas)
      → falso: encerramento sem alerta
```

- **Make herdado:** blueprint com seis módulos, incluindo webhook, OpenAI, parse JSON, Airtable, router e Slack. A documentação registra cenário em conta pessoal e operação manual; sua execução atual não foi verificada.
- **Espelho n8n:** seis nós, com chamadas HTTP para LLM, Airtable e Slack, nó `Code` para parse e nó `IF` para negativas. O fluxo grava no Airtable antes de avaliar o envio ao Slack. Há um canal fixo de alerta; não há roteamento implementado para equipes diferentes por tema.
- **Infraestrutura local:** Docker Compose com imagem fixada `n8nio/n8n:2.28.7`, volume persistente `n8n_data`, reinício `unless-stopped` e porta `127.0.0.1:5678`. O acesso utiliza conta de dono local, conforme os comentários do Compose.
- **Dados:** entrada com `review_id`, `customer_name`, `source`, `rating` e `review_text`; saída acrescenta `sentiment`, `theme` e `processed_at`.

### Execução local já realizada

Conforme informado pelo responsável, estão funcionais: n8n via Docker, recebimento pelo webhook, classificação com **Qwen3-4B local via LM Studio**, gravação real no Airtable, roteamento de avaliação negativa e alerta real no Slack.

**Distinção entre execução local e arquivos:** os dois workflows versionados ainda configuram OpenAI (`gpt-5.4-mini`), e os READMEs descrevem esse provedor. A configuração Qwen/LM Studio da instância local não está representada nesses JSONs. O export n8n também contém `active: false`, exigindo ativação na instância. Portanto, os arquivos não reproduzem integralmente o estado local informado.

### Dependências

| Dependência | Papel no protótipo |
| --- | --- |
| Docker e Docker Compose | Execução local do n8n e persistência em volume. |
| n8n | Orquestração do espelho local e armazenamento de credenciais pela interface. |
| LM Studio e Qwen3-4B | Classificação local informada; dependem do serviço e dos recursos da máquina. |
| Airtable | Persistência externa na tabela `Reviews`, mediante base configurada e PAT. |
| Slack | Alerta externo via bot e acesso ao canal de CX. |
| Make.com e OpenAI | Dependências do fluxo herdado/exportado; conexões precisam ser recriadas. |
| Python, biblioteca padrão | Execução dos dois scripts de teste offline. |

## 2. Lacunas encontradas

| Área | Evidência e limitação atual |
| --- | --- |
| Respostas inválidas do LLM | `Parse + Merge` acessa `choices[0].message.content` e executa `JSON.parse` sem `try/catch`. Resposta ausente, estrutura inesperada ou JSON inválido interrompe o fluxo. O Make também não apresenta rota de recuperação no blueprint. Não há fila de falhas, fallback ou alerta específico. |
| Deduplicação | Não há consulta, bloqueio ou atualização por `review_id` antes da criação no Airtable. O campo primário documentado não constitui garantia de unicidade. Reenvios podem gerar registros e alertas duplicados. |
| Validação de classificação | O n8n aplica apenas `.toLowerCase().trim()`, sem verificar tipo, campos obrigatórios ou pertencimento aos conjuntos permitidos. Esperam-se sentimentos `positivo`, `neutro`, `negativo` e temas `entrega`, `produto`, `atendimento`, `preco`, `app_bug`. O Make compara o sentimento diretamente. Valores inesperados podem impedir o alerta ou comprometer a gravação e os relatórios. |
| Validação da entrada | Não há etapa explícita de validação dos campos do webhook, incluindo identificador, texto e faixa de nota. |
| LGPD e PII | Não há mapeamento documentado de base legal, minimização, anonimização, acesso ou retenção implementada. O briefing exige retenção de logs de até 90 dias, mas não há configuração explícita dessa política nos arquivos examinados. |
| Custo | Não são registrados tokens, custo por avaliação, consumo por cliente ou consolidação mensal. O relato herdado de aproximadamente US$ 12/mês é uma estimativa histórica, sem medição auditável. O LLM local também não possui medição de recursos ou custo operacional. |
| CI/CD | Não há pipeline de integração ou entrega contínua no repositório. Os testes são executados manualmente; as variáveis Make API de `.env.example` são preparatórias, não uma integração implementada. |
| Ambientes | Existe uma configuração local, sem separação explícita de dev/prod para workflows, bases, canais, credenciais ou volumes. |
| Deploy público | Não há deploy público do espelho n8n documentado ou configurado. O Compose limita o acesso ao loopback e usa HTTP local. O relato de uso herdado no Make não comprova um deploy público do espelho. |
| Rollback | Há versionamento Git e imagem Docker fixada, mas não há procedimento de rollback testado, backup/restauração validado ou evidência de recuperação do volume e das credenciais. |
| Healthcheck e observabilidade | O Compose não define `healthcheck`. Não há métricas, painel ou alertas operacionais configurados. O n8n salva progresso e execuções manuais, mas isso não constitui monitoramento de disponibilidade ou entrega. |
| Confirmação e falhas de integração | O webhook exportado responde ao receber (`onReceived`), antes de concluir Airtable/Slack; resposta HTTP de sucesso não comprova processamento completo. Não há verificação explícita do resultado lógico da API Slack nem recuperação específica de falhas externas. |
| Reprodutibilidade e documentação | A configuração local do LLM não está exportada. O README do espelho menciona `admin/admin`, divergindo da conta de dono descrita no Compose e no README principal. |

### Estado dos testes existentes

Executados durante a validação inicial do projeto, sem Docker e sem chamadas a serviços externos:

| Script | Resultado | Cobertura real |
| --- | --- | --- |
| `tests/validate_workflows.py` | 16 verificações aprovadas; saída 0. | Leitura dos dois JSONs, estrutura básica, presença de componentes e referências das conexões n8n. |
| `tests/test_routing_logic.py` | 10 verificações aprovadas; 0 falhas; saída 0. | Classificação por regras simuladas, normalização e decisão de alertar apenas negativas. |

O teste de lógica reproduz parte do fluxo em Python; não executa os nós reais nem avalia o Qwen. O caso `theme = "frete"` passa justamente por demonstrar que um tema fora da lista permanece aceito pela lógica simulada. Não há cobertura automatizada de integração, JSON inválido, tipos inesperados, deduplicação, indisponibilidade externa, PII, custo, deploy ou rollback. Os dez exemplos de reviews documentados são material de teste manual, não uma suíte automática de avaliação do modelo.

## 3. Riscos

- **Credenciais e continuidade:** a documentação do protótipo herdado e os nomes das conexões indicam uso de credenciais pessoais da Sther para OpenAI e Airtable, o que representa risco de continuidade caso essas credenciais sejam revogadas. Na configuração local atual, esse risco foi parcialmente mitigado: a classificação está sendo realizada com Qwen3-4B via LM Studio, sem uso da chave pessoal da OpenAI, e o Airtable foi configurado com uma nova base e um novo Personal Access Token. Ainda é necessário, porém, formalizar a gestão de credenciais para um ambiente de produção e garantir separação entre desenvolvimento e produção.

- **Gestão de secrets:** os JSONs contêm referências e nomes de credenciais, sem valores de autenticação; `.env.example` contém campos vazios. O `.env` local do espelho tem identificador de base preenchido e campos de tokens vazios, e está ignorado pelo Git. Isso não comprova ausência de secrets no histórico ou na instância. Não há procedimento documentado de rotação e recuperação; `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` permite acesso de nós às variáveis de ambiente.
- **Dados pessoais:** `customer_name` identifica o cliente; `review_text` pode conter telefone, número de pedido e outros identificadores. Ambos são enviados ao Airtable e incluídos nos alertas Slack. Nos exports examinados, o prompt envia explicitamente apenas `review_text`, que pode conter PII; a documentação herdada afirma envio também do nome, divergência que exige confirmação na instância. O LLM local reduz o envio ao provedor de IA externo nesse caminho, mas não elimina o compartilhamento com Airtable/Slack nem possíveis cópias nos registros de execução.
- **Perda de tratativa:** falha no parse ou no Airtable impede etapas seguintes; falha no Slack pode deixar uma negativa gravada sem alerta. Não há recuperação operacional implementada. A mensagem pede resposta em 24 horas, mas não existe controle de responsável, resposta ou SLA no fluxo.
- **Qualidade e duplicidade:** classificações fora do contrato podem ocultar negativas ou produzir dados inconsistentes. Reenvios podem duplicar registros e notificações, aumentando ruído e esforço de atendimento.
- **Operação e orçamento:** dependência da máquina local, ausência de monitoramento, ambientes separados e rollback validado dificultam continuidade e recuperação. Sem medição, não é possível demonstrar cumprimento do orçamento de US$ 100/mês previsto no briefing.

## 4. Prioridades para evolução

As prioridades abaixo são recomendações futuras; nenhuma foi implementada nesta auditoria.

| Prioridade | Evolução proposta |
| --- | --- |
| **P1 — Segurança e privacidade** | Confirmar titularidade e escopos, migrar credenciais pessoais para gestão corporativa e definir rotação. Mapear PII, finalidade, base legal, acesso, minimização e retenção antes de ampliar o uso de dados reais. |
| **P1 — Integridade do processamento** | Validar entrada e saída do LLM, tratar JSON/estrutura inválidos e falhas das APIs, registrar falhas e permitir reprocessamento controlado. Implementar deduplicação por `review_id`, considerando concorrência e entrega de alertas. |
| **P2 — Baseline reproduzível e testes** | Exportar a configuração local efetivamente utilizada, alinhar documentação e ampliar testes para o workflow real, contratos, negativas, duplicatas e falhas. |
| **P2 — Operação e custo** | Adicionar healthcheck, métricas e alertas de falha; medir consumo/custo por execução e recursos locais, com registros compatíveis com a política de privacidade. |
| **P3 — Entrega controlada** | Separar dev/prod, instituir CI/CD, planejar deploy público com configuração apropriada e validar backup, restauração e rollback antes de um piloto externo. |

**Referências internas:** `README.md`, `BRIEFING.md`, `CHANGELOG.md`, `.env.example`, `.gitignore`, `docs/notas-sther.md`, `docs/airtable-schema.md`, `docs/exemplos-reviews.md`, `n8n-mirror/README.md`, `n8n-mirror/docker-compose.yml`, os dois workflows JSON e os dois scripts de teste.
