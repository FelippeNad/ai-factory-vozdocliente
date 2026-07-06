# Exemplos de avaliações — VozDoCliente

Coletânea sintética (baseada em casos reais anonimizados) pra testar o roteador. Use no `curl` do `n8n-mirror/README.md` trocando o corpo, ou alimente o `tests/test_routing_logic.py`.

Cada review tem: `review_id`, `customer_name`, `source`, `rating` (1–5) e `review_text`. O esperado de `sentiment`/`theme` é a **expectativa humana** — serve de gabarito pra você comparar com o que o LLM devolve.

## Negativas (devem disparar Slack)

1. **R-1001** — Marina Souza — app-store — ⭐1
   "Comprei e o produto chegou todo quebrado. Mandei e-mail pro SAC e ninguém respondeu até agora."
   → esperado: `negativo` / `produto` (ou `atendimento` — ver ambíguas)

2. **R-1002** — Carlos Eduardo Lima — formulario — ⭐1
   "Faz 12 dias que comprei e o pedido nem saiu pra entrega. Prazo era 3 dias úteis. Absurdo."
   → esperado: `negativo` / `entrega`

3. **R-1003** — Patrícia Gomes — app-store — ⭐2
   "O app trava toda vez que tento finalizar a compra. Já reinstalei e nada."
   → esperado: `negativo` / `app_bug`

4. **R-1004** — Rafael Antunes — marketplace — ⭐1
   "Cobraram um valor diferente do que aparecia no carrinho. Me senti enganado."
   → esperado: `negativo` / `preco`

5. **R-1005** — Juliana Castro — formulario — ⭐2
   "A atendente foi extremamente ríspida no chat e encerrou sem resolver meu problema."
   → esperado: `negativo` / `atendimento`

## Positivas (NÃO devem disparar Slack)

6. **R-1006** — Bruno Tavares — app-store — ⭐5
   "Entrega chegou antes do prazo e o produto é ótimo. Recomendo demais!"
   → esperado: `positivo` / `entrega` (ou `produto`)

7. **R-1007** — Aline Ferreira — formulario — ⭐5
   "Atendimento nota mil, resolveram minha troca em minutos. Parabéns ao time."
   → esperado: `positivo` / `atendimento`

## Neutras (NÃO devem disparar Slack)

8. **R-1008** — Diego Moreira — app-store — ⭐3
   "O produto é ok. Vocês têm previsão de lançar a versão com mais memória?"
   → esperado: `neutro` / `produto`

9. **R-1009** — Sem nome informado — formulario — ⭐3
   "Como faço pra acompanhar meu pedido pelo app? Não achei onde."
   → esperado: `neutro` / `app_bug` (ou `entrega`)

## Ambíguas (boas pra estressar o classificador)

10. **R-1010** — Fernanda Ribeiro — marketplace — ⭐2
    "Não chegou no prazo E quando chegou veio o produto errado. Quero meu dinheiro de volta."
    → esperado: `negativo` / `entrega` **ou** `produto` **ou** `preco` (reembolso) — o LLM vai ter que escolher um. Bom caso pra discutir multi-tema na evolução.

> Dica: rode a #10 algumas vezes. Com `temperature 0.1` costuma estabilizar, mas o tema escolhido pode variar — é exatamente o tipo de fragilidade descrita na dívida técnica ("matching de tema frágil").
