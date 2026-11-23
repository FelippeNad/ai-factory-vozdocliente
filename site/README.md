# VozDoCliente CX — Etapa 3 (site de demonstração)

Interface web profissional, leve e responsiva para demonstrar o workflow DEV de classificação de avaliações. **Não altera o workflow de produção** e **não escreve diretamente no Airtable**: o envio passa pelo webhook n8n DEV. Os dados de listagem vêm do Airtable DEV por leitura no servidor.

## Arquitetura

```text
Navegador (senha de demo)
         │ HTTPS / sessão HttpOnly
         ▼
Site Node.js / Railway (serviço separado, sem banco)
    ├── GET /api/reviews ──► Airtable CX TESTE (somente metadados)
    └── POST /api/submit ─► Webhook n8n DEV publicado
                                    │
                     Sanitizar PII → precheck de duplicatas
                        → LLM → validação → Airtable DEV
                                           └→ Slack DEV (negativas)
         ▲
         └── consulta Airtable DEV até confirmar a classificação
```

O webhook padrão responde assim que o workflow inicia. O site somente anuncia que o registro foi **classificado** após localizar a classificação na base DEV. Caso não apareça, informa que o envio foi recebido, porém não confirmado.

## Implantação rápida no Railway

**Serviço novo, separado de n8n e PostgreSQL.** Não substitua o n8n existente nem mude volumes/credenciais PROD.

1. Suba a pasta `site/` para a branch `etapa-3` no repositório `FelippeNad/ai-factory-vozdocliente`.
2. Railway → projeto atual → `+ New` → `GitHub Repo` → escolha este repositório, na branch `etapa-3`.
3. Na configuração do **novo serviço web**, defina **Root Directory = `/site`**. O Dockerfile dentro dessa pasta será usado, sem dependências npm. Se o primeiro build falhar por ter começado na raiz, ajuste o Root Directory e faça redeploy.
4. No serviço WEB recém-criado, em **Variables**, defina (com seus próprios valores, sem enviar tokens a terceiros):

| Variável | Valor |
|---|---|
| `APP_PASSWORD` | Senha de demonstração forte (mínimo 10 caracteres). Entregue-a ao avaliador, se houver login. |
| `SESSION_SECRET` | String aleatória de 32 bytes ou mais, hexadecimal recomendado. PowerShell (Windows 5.1+): `$b=New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [BitConverter]::ToString($b).Replace("-","")` |
| `CLASSIFIER_DEV_BASE_ID` | Mesmo **ID TESTE** configurado no serviço n8n (`app...`), sem copiar base PROD. |
| `CLASSIFIER_DEV_TABLE_ID` | Mesmo **ID da tabela Reviews TESTE** (`tbl...`). |
| `AIRTABLE_DEV_PAT` | Token Airtable com `data.records:read` para a base CX TESTE; idealmente novo token só de leitura. |
| `N8N_DEV_WEBHOOK_URL` | **Production URL** do nó Webhook Review do workflow **DEV** publicado: `https://.../webhook/review-v4-otimizado-dev` (não `webhook-test` e não o workflow PROD). |
| `N8N_DEV_WEBHOOK_AUTH_HEADER` | Opcional e recomendado: nome do cabeçalho de autenticação do webhook DEV. |
| `N8N_DEV_WEBHOOK_AUTH_VALUE` | Opcional e recomendado: valor secreto configurado no webhook DEV. |

5. **No n8n DEV:** o workflow precisa estar publicado (com webhook de produção ativo). Confira as credenciais DEV e os IDs; não publique o workflow PROD novo nem importe credenciais históricas. Na aba **Production URL** do Webhook, copie o endereço e use-o no serviço web. Não configure a Test URL no site.
6. Railway → serviço WEB → Settings → Networking → Generate Domain. Abra a URL HTTPS gerada. Entre com a `APP_PASSWORD`.
7. Faça um teste com exemplo **positivo**; confirme que Airtable CX TESTE recebeu `ETAPA3-DEMO-*` e que o resultado apareceu no site. Faça um teste **negativo** e verifique Slack DEV. Em seguida, grave vídeo de backup. Documente hora de publicação, intervalo observado e eventuais reinicializações; não afirme uptime de 24h se não houve.

**Atenção:** o serviço web é separado, então precisa de suas **próprias** variáveis. O token Airtable é configurado somente no backend; jamais colocar PAT/API keys em `public/` ou em commits. Limite alertas, validações e uso de LLM ao ambiente DEV.

### Proteção adicional do webhook (recomendada antes de compartilhar)

Sem autenticação no Webhook Review, terceiros que conheçam a URL do n8n podem acessá-lo diretamente, mesmo que o site tenha login. No nó **Webhook Review** do workflow DEV, configure **Authentication → Header Auth** com credencial exclusiva para DEV (ex.: `X-Demo-Key` e um valor aleatório). Configure o mesmo nome/valor em `N8N_DEV_WEBHOOK_AUTH_HEADER` e `N8N_DEV_WEBHOOK_AUTH_VALUE` do serviço web. **Teste antes de compartilhar**; se houver erro 401, confira a correspondência e se o workflow foi republicado. Não envie esse segredo ao avaliador; somente a senha `APP_PASSWORD` é compartilhada.

## Verificação local

Com Node.js 22 instalado:

```powershell
cd site
$env:APP_PASSWORD="SENHA_DE_TESTE_FORTE"
$env:SESSION_SECRET="chave_local_para_teste_com_mais_de_24_caracteres"
node server.js
```

Abra `http://localhost:3000`. O site carrega, mas a integração informa que faltam as variáveis DEV até serem configuradas. Testes offline, sem acesso externo:

```powershell
node --test tests/smoke.test.js
```

## Funcionalidades e segurança

- Login por senha de demonstração e cookie assinado, HttpOnly e Secure (HTTPS), expirando em 12 horas; sem persistência de contas.
- Formulário com avaliação sintética e nota de 1 a 5, ID aleatório, limite de 8 envios/tentativas por IP em janela de 10 minutos. **Não utilizar dados reais**.
- O servidor rejeita algumas formas evidentes de contato/documentos/URLs; não é anonimização completa. O n8n já implementa sanitização antes do LLM, mas **armazena o texto original no Airtable DEV**.
- O token Airtable fica exclusivamente no servidor; a API retorna **apenas** ID, sentimento, tema, nota, origem e horário. Nunca exibe o texto original nem nomes de clientes.
- Dashboard e gráficos usam até **100 registros DEV** retornados pela consulta, sem afirmar totais da produção. Tabela exibe até 20 registros dessa amostra. Percentual de negativos usa apenas classificações conhecidas.
- Números de benchmark exibidos provêm da Etapa 2: 15 envios por versão; chamadas LLM 15→5 (−66,67%); latência média 2396,87→1549,93 ms (−35,34%); validade estrutural 100% nesse lote. A acurácia dos registros desse benchmark **não foi medida**. A coleta separada de cinco exemplos teve 80% de acurácia conjunta, abaixo da meta de 90%. Não equivale a ROI ou produção.
- Limitações: sondagem de resultado depende de Airtable DEV, fluxo n8n publicado, token e rede; o retorno pode dizer 'enviado mas não confirmado'; teste sem dados pessoais é obrigatório. Sem atomicidade na criação do Airtable, conforme documentação Etapa 2. Senha única e limitador em memória atendem **apenas à demonstração acadêmica**, não equivalem a autenticação multiusuário para produção.

## Troubleshooting

| Sintoma | Verificar |
|---|---|
| Site retorna 502 ou 503 | Variáveis `CLASSIFIER_DEV_*`, `AIRTABLE_DEV_PAT`, webhook DEV HTTPS e permissões da conta TESTE; não cole segredos em prints. |
| `Webhook DEV respondeu HTTP 404` | Workflow DEV não publicado ou Production URL incorreta; não usar `webhook-test`. |
| `Webhook DEV respondeu HTTP 401` | Header Auth do n8n e `N8N_DEV_WEBHOOK_AUTH_*` não coincidem. |
| Avaliação enviada, sem confirmação | Abra **Executions** no n8n DEV e confira LLM, Airtable e validações; ACK do webhook não significa processamento concluído. |
| Airtable retorna 403 | Token sem `data.records:read`, escopo/base TESTE incorretos ou usuário sem acesso. |
| Nenhum registro no painel | Tabela `Reviews` DEV vazia, dados fora da amostra de 100, ou integrações sem conexão. |
| Site não abre no Railway | Confirme Root Directory `/site`, logs do Dockerfile, a variável `PORT` injetada pela plataforma e domínio publicado. |
| Credencial do n8n ausente | Reassocie credenciais ao nó correto; nunca use credenciais de PROD no DEV. |
| O site publica mas não permite login | Confira `APP_PASSWORD` com pelo menos 10 caracteres, `SESSION_SECRET` com pelo menos 24 e acesso HTTPS. |

## Arquivos

```text
site/
  Dockerfile               Node.js 22 pinado, sem dependências npm
  .dockerignore
  .env.example             variáveis documentadas, sem segredos reais
  server.js                sessão, proxy DEV, validação, consulta Airtable
  public/index.html       interface responsiva
  public/styles.css       estilos do dashboard
  public/app.js           dados reais DEV, formulário e indicadores
  tests/                   smoke tests offline
```

Rota de health: `GET /health` (não confirma conexão a fornecedores). Rota de leitura: `GET /api/reviews` (login exigido). Envio: `POST /api/submit` (login exigido). O código e o backend não publicam ou alteram workflows n8n automaticamente.
