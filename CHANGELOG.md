# Changelog

## [v0.2] (Sther)
- Adicionado espelho rodável em n8n (`n8n-mirror/`) — Make não roda local
- Filtro do alerta agora compara `sentiment == "negativo"` (antes alertava todo review)
- Gambiarra `.toLowerCase().trim()` no parse do n8n pra reduzir furo de string

## [v0.1] (Sther)
- Versão inicial no Make.com: webhook → OpenAI (sentiment + theme) → Airtable → Slack
- Em produção (manual, scheduler na conta pessoal)

## Pendências conhecidas (não resolvidas)
- Migrar pra conta corporativa (scheduler + connections)
- Trocar API key pessoal da OpenAI
- Error handling, deduplicação, rastreio de custo
- Mapa LGPD (reviews contêm PII)
- Validar `theme`/`sentiment` contra lista permitida
