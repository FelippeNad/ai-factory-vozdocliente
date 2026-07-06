#!/usr/bin/env python3
"""
Teste de logica do roteador com LLM MOCKADO.

Reproduz, em Python puro, a logica que vive no fluxo (Make/n8n):
  1. parse do JSON que o LLM "devolve" (mockado, sem rede),
  2. normalizacao (lowercase/trim) -> mesma gambiarra do node Parse + Merge,
  3. decisao de roteamento: alerta no Slack SOMENTE se sentiment == "negativo".

NAO chama OpenAI/Anthropic/Slack/Airtable. Tudo offline.

Uso:  python tests/test_routing_logic.py
"""
import json
import sys

THEMES = {"entrega", "produto", "atendimento", "preco", "app_bug"}
SENTIMENTS = {"positivo", "neutro", "negativo"}


# --- LLM mockado: dado um texto, devolve a string JSON que o modelo "responderia" ---
def mock_llm(review_text: str) -> str:
    t = review_text.lower()
    # sentiment
    if any(w in t for w in ["quebrad", "nao respond", "não respond", "absurdo",
                            "trava", "enganad", "rispida", "ríspida", "errado",
                            "pessimo", "péssimo", "dinheiro de volta"]):
        sentiment = "negativo"
    elif any(w in t for w in ["recomendo", "otimo", "ótimo", "nota mil",
                              "parabens", "parabéns", "antes do prazo"]):
        sentiment = "positivo"
    else:
        sentiment = "neutro"
    # theme
    if any(w in t for w in ["prazo", "entrega", "chegou", "frete"]):
        theme = "entrega"
    elif any(w in t for w in ["app", "trava", "login", "checkout", "finalizar a compra"]):
        theme = "app_bug"
    elif any(w in t for w in ["valor", "cobrar", "cobr", "preço", "preco", "carrinho"]):
        theme = "preco"
    elif any(w in t for w in ["atendente", "sac", "chat", "troca", "reembolso"]):
        theme = "atendimento"
    else:
        theme = "produto"
    return json.dumps({"sentiment": sentiment, "theme": theme})


# --- logica do fluxo (espelha o node Parse + Merge + IF) ---
def classify(review_text: str, llm=mock_llm) -> dict:
    raw = llm(review_text)
    parsed = json.loads(raw)  # no fluxo real: sem try/catch (divida tecnica)
    return {
        "sentiment": (parsed.get("sentiment") or "").lower().strip(),
        "theme": (parsed.get("theme") or "").lower().strip(),
    }


def should_alert(classification: dict) -> bool:
    """Mesma decisao do Router(Make)/IF(n8n): so negativo dispara Slack."""
    return classification["sentiment"] == "negativo"


# --- mini-harness de asserts ---
passed = 0
failed = 0


def expect(label, got, want):
    global passed, failed
    ok = got == want
    print(f"[{'OK' if ok else 'FALHA'}] {label} -> got={got!r} want={want!r}")
    if ok:
        passed += 1
    else:
        failed += 1


if __name__ == "__main__":
    print("=== Classificacao (LLM mockado) ===")
    neg = classify("Comprei e o produto chegou quebrado e o SAC nao responde.")
    expect("review negativo: sentiment", neg["sentiment"], "negativo")
    expect("review negativo: tema valido", neg["theme"] in THEMES, True)

    pos = classify("Entrega chegou antes do prazo e recomendo demais!")
    expect("review positivo: sentiment", pos["sentiment"], "positivo")

    neu = classify("O produto e ok. Tem previsao de versao nova?")
    expect("review neutro: sentiment", neu["sentiment"], "neutro")

    appbug = classify("O app trava toda vez que tento finalizar a compra.")
    expect("review de app: tema", appbug["theme"], "app_bug")

    print("\n=== Decisao de roteamento (alerta Slack) ===")
    expect("negativo dispara alerta", should_alert(neg), True)
    expect("positivo NAO dispara alerta", should_alert(pos), False)
    expect("neutro NAO dispara alerta", should_alert(neu), False)

    print("\n=== Validacao defensiva (sentiment fora do conjunto) ===")
    weird = classify("qualquer coisa", llm=lambda _: '{"sentiment":"Negativo","theme":"frete"}')
    # apos normalizacao vira "negativo" -> deve alertar (mostra valor da normalizacao)
    expect("'Negativo' normalizado dispara alerta", should_alert(weird), True)
    # mas o tema 'frete' NAO esta na lista permitida -> evidencia divida 'matching fragil'
    expect("tema 'frete' fica FORA da lista permitida", weird["theme"] in THEMES, False)

    print("\n" + "-" * 48)
    print(f"RESULTADO: {passed} passaram, {failed} falharam")
    sys.exit(0 if failed == 0 else 1)
