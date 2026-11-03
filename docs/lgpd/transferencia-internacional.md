# Transferências internacionais — avaliação documental

Revisão: **02/11/2026**. Nenhum contrato foi fornecido, nenhuma conta foi acessada
e nenhuma região efetiva foi confirmada. Os endpoints dos exports comprovam o
destino lógico, não o país de processamento. A [matriz de dados](mapa-dados-pessoais.md)
identifica o conteúdo que pode circular. A afirmação “OpenAI (EUA)” nas notas
herdadas não é prova da configuração atual ou de todos os suboperadores.

## Critério jurídico e fontes brasileiras

Há duas decisões separadas: hipótese para tratar dados e mecanismo para a
transferência. Usar API, HTTPS, DPA estrangeiro ou máscara de PII não resolve
automaticamente nenhuma delas. Referências: arts. **7º/11 e 33–36 da LGPD** no
[texto atualizado](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html).

A [Resolução CD/ANPD nº 19/2024, com retificação indicada na página oficial](https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-19-de-23-de-agosto-de-2024)
regulamenta mecanismos e traz cláusulas-padrão brasileiras. Seu Anexo I, art. 4º,
exige avaliar a operação; o art. 16 trata da adoção integral das cláusulas por
exportador/importador. O prazo transitório de doze meses contado da publicação
de 23/08/2024 já terminou nesta revisão; não tratá-lo como prazo futuro disponível.

O [portal de transferência da ANPD](https://www.gov.br/anpd/pt-br/assuntos/assuntos-internacionais/transferencia-internacional-de-dados)
informa adequação da União Europeia pela Resolução nº 32/2026 e distingue cláusulas
brasileiras de equivalentes reconhecidas. Não estender essa decisão a destinatários
nos EUA, a toda “Europa”, a todos os serviços de uma marca ou a transferências
posteriores sem examinar seu alcance. SCCs europeias ou DPF, isoladamente, não
comprovam mecanismo brasileiro para o caminho do projeto.

Mecanismos a analisar pelo jurídico incluem adequação (art. 33, I), garantias
contratuais aplicáveis (art. 33, II) ou outra hipótese pertinente. Art. 33, IX se
refere às hipóteses do art. 7º, II/V/VI; não abrange automaticamente legítimo
interesse. Consentimento específico para transferência (art. 33, VIII) não foi
obtido/proposto como solução universal. As alternativas não são intercambiáveis.

Coleta direta pelo fornecedor estrangeiro e compartilhamento entre agentes não
são presumidos idênticos; classificar o ingresso no webhook hospedado e os envios
posteriores segundo os arts. 3º–6º do regulamento. A localização do titular, a
entidade exportadora e os acessos remotos precisam ser documentados.

## Avaliação por fornecedor, sem equiparar contratos ou regiões

| Destino | Confirmado nos artefatos / fonte pública | Não confirmado / evidência a obter |
| --- | --- | --- |
| **OpenAI API** | V3/v4 usam `https://api.openai.com/v1/chat/completions`; texto original na v3 e sanitizado na v4. [OpenAI Docs — controles de dados](https://developers.openai.com/api/docs/guides/your-data) distingue logs de monitoramento e estado de aplicação; controles de retenção/residência dependem de elegibilidade e configuração | Entidade contratante/importadora, projeto/conta, DPA e anexos aplicáveis ao Brasil, suboperadores, locais de inferência/armazenamento/suporte, opções efetivamente habilitadas e exceções do endpoint/modelo |
| **Airtable** | Consulta e persistência do original em `Reviews`; retenção DEV também envia metadados/auditoria. Há [DPA público do Airtable](https://www.airtable.com/company/dpa), que trata conteúdo de cliente, dados de conta e transferências | Instrumento efetivamente aceito, papel em cada finalidade, região da base, backups, suporte, suboperadores e mecanismo brasileiro. A existência do DPA público não comprova adesão nem cláusula brasileira assinada |
| **Slack** | `chat.postMessage` recebe dados originais na v3 e tema/nota na v4. [Residência de dados Slack](https://slack.com/help/articles/360035633934-Data-residency-for-Slack) descreve escopo/limitações da opção; o [Trust Center](https://slack.com/trust) aponta documentos contratuais | Plano e configuração do workspace, entidade/DPA vigente, dados cobertos e excluídos da residência, apps, Slack Connect, notificações, suporte, suboperadores e mecanismo brasileiro |
| **Railway / banco / volumes** | ADRs descrevem hospedagem n8n/PostgreSQL. [DPA público Railway](https://railway.com/legal/dpa) documenta uma oferta contratual; não há contrato do projeto no repositório | Região de cada serviço, banco e volume; localização de logs/backups/suporte; entidade e suboperadores; contrato aceito e mecanismo brasileiro. Região do serviço não prova região de todas as cópias |

Na OpenAI API, a documentação informa que o uso para treinamento depende de opção
de compartilhamento e trata retenções separadamente. “Não usado para treinamento”
não significa “não armazenado” nem “não transferido”. Não foi comprovado ZDR,
residência brasileira ou outro controle na conta do projeto. O prazo demonstrativo
de trinta dias das reviews não determina o prazo do fornecedor.

LM Studio/Qwen local reduz o envio de inferência nesse caminho, mas não elimina
Airtable/Slack/Railway. Não confundir teste offline com autorização de fluxo real.

## Dossiê a preencher por caminho de transferência

O responsável técnico levanta e o controlador/jurídico valida, **por fornecedor e
finalidade**, os seguintes campos; todos permanecem pendentes de comprovação:

| Campo | Evidência necessária / critério para fechar |
| --- | --- |
| Exportador/importador e papel | Razão social, país, cadeia loja → VozDoCliente → prestador, instrução e contrato; não presumir que destinatário técnico é controlador |
| Dados e finalidade | Versão do fluxo, campos enviados, necessidade, frequência e volume medido; não inventar métricas de uso |
| Locais | Países de armazenamento/inferência/suporte/backups e transferências posteriores, com confirmação da conta/serviço |
| Base e mecanismo | Justificativa aprovada; artigo aplicável; instrumento brasileiro ou decisão de adequação com alcance identificado |
| Contrato | Versão, data, partes, comprovação de adesão/assinatura e anexos preenchidos; armazenar documentos sensíveis em repositório restrito, apenas referência aqui |
| Suboperadores e acesso estatal | Lista vigente, acessos remotos, garantias e avaliação de riscos conforme caminho; registrar mudanças |
| Retenção e titulares | Prazo por cópia, exclusão/restauração, contatos, informações de transparência, cooperação em direitos/incidentes |
| Aprovação | Nomeação efetiva do aprovador, data, validade da análise e gatilhos de revisão: novo país, finalidade, fornecedor, plano ou versão |

Se forem adotadas cláusulas-padrão, conferir sua incorporação e anexos com o jurídico;
não substituir o texto oficial por este documento. Avaliar também as medidas de
transparência do regulamento, inclusive informações ao titular, sem publicar segredos
ou contratos completos indiscriminadamente. Aprovações são internas: este trabalho
não solicitou ou obteve autorização da ANPD nem se comunicou com fornecedores.

## Decisão desta etapa

Não há mecanismo contratual comprovado para o projeto, nem declaração de que
todos os fornecedores são irregulares. O estado é **pendente de validação jurídica
e contratual**. As demonstrações da disciplina devem usar dados sintéticos e stubs.
Um piloto com dados pessoais reais depende de fechar o dossiê e as demais pendências
do [checklist](checklist-etapa-2.md); máscara regex não libera o envio por si só.
