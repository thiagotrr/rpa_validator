"""Minimização de dados pessoais nas saídas (tela, PDF, Markdown). Os dados completos só ficam no Firestore."""

PARTICULAS = frozenset({"DE", "DA", "DO", "DAS", "DOS", "E", "D", "DI", "DU"})


def ofuscar_nome(nome: str | None) -> str | None:
    """'SEBASTIAO FERNANDO DE MELO' -> 'SEBASTIAO F******* DE M***'. Primeiro nome inteiro; sobrenomes com a inicial."""
    if not nome or not nome.strip():
        return None
    primeiro, *resto = nome.split()
    partes = [primeiro]
    for p in resto:
        partes.append(p if p.upper() in PARTICULAS else p[0] + "*" * (len(p) - 1))
    return " ".join(partes)
