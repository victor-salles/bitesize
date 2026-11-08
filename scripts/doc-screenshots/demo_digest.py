"""Build a demo digest EPUB for the documentation screenshots.

    python scripts/doc-screenshots/demo_digest.py <out.epub>

Runs the real EPUB builder on made-up stories, so the pictures show the actual
layout without fetching feeds, calling an AI backend or reprinting anyone's article.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from epub import generate_epub  # noqa: E402

BODY = (
    "Este é um texto de exemplo para a documentação do BiteSize. Ele ocupa o lugar do "
    "artigo completo que o digest extrai da fonte original, com parágrafos, capitular e "
    "a mesma tipografia que aparece no Kindle.\n\n"
    "Na edição real, cada matéria traz o texto da fonte, um resumo escrito pelo modelo "
    "escolhido nas configurações e uma nota de relevância de 0 a 10 calculada a partir "
    "dos temas que você ordenou no painel.\n\n"
    "As seções aparecem da mais relevante para a menos relevante, e a capa destaca a "
    "matéria principal da edição junto com as chamadas de outras seções."
)


def story(title: str, source: str, summary: str, relevance: int, temas: list[str], tipo: str = "artigo-completo") -> dict:
    slug = title.lower().replace(" ", "-")[:40]
    return {
        "title": title,
        "source": source,
        "url": f"https://example.com/{slug}",
        "published": "2026-11-08T06:30:00",
        "summary": summary,
        "content": BODY,
        "relevance": relevance,
        "relevance_source": "demo",
        "tipo": tipo,
        "temas": temas,
    }


SECTIONS = {
    "Tecnologia": [
        story("Cidade testa ônibus elétricos sem motorista em linha noturna",
              "Jornal Exemplo", "Piloto de seis meses cobre 12 km entre o centro e o aeroporto, com um operador a bordo.",
              92, ["tecnologia", "brasil"]),
        story("Nova bateria de sódio promete carga completa em dez minutos",
              "Revista Modelo", "Laboratório divulga protótipo sem lítio; produção em escala ainda depende de testes de durabilidade.",
              81, ["tecnologia", "ciência"]),
        story("Aplicativo de leitura ganha modo offline para trens e metrô",
              "Portal Fictício", "Atualização baixa as edições do dia de madrugada e sincroniza as marcações depois.",
              64, ["tecnologia"], tipo="resumo"),
    ],
    "Economia": [
        story("Feiras de bairro passam a aceitar pagamento por aproximação",
              "Diário Demo", "Prefeitura distribui maquininhas a 300 feirantes; taxa fica zerada no primeiro ano.",
              77, ["economia", "brasil"]),
        story("Cooperativa de café do sul de Minas exporta direto para o Japão",
              "Gazeta de Teste", "Contrato de três anos elimina intermediários e paga prêmio por qualidade.",
              69, ["economia", "mundo"]),
        story("Aluguel de bicicletas cresce 40% em capitais no último ano",
              "Jornal Exemplo", "Levantamento aponta ciclovias novas e bicicletas elétricas como principais motivos.",
              55, ["economia"], tipo="resumo"),
    ],
    "Ciência": [
        story("Sonda registra gêiseres de gelo em lua de Saturno",
              "Revista Modelo", "Imagens de alta resolução mostram jatos de 200 km; equipe busca sinais de compostos orgânicos.",
              88, ["ciência", "mundo"]),
        story("Recife artificial atrai 60 espécies de peixes em dois anos",
              "Portal Fictício", "Estruturas de concreto poroso no litoral nordestino viram berçário para espécies locais.",
              72, ["ciência", "clima"]),
    ],
}

GLOBAL_COVER = {
    "headline": SECTIONS["Tecnologia"][0]["title"],
    "editorial": "Uma edição de exemplo, montada com matérias fictícias para mostrar o layout do digest.",
}


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "demo.epub")
    generate_epub(SECTIONS, {}, GLOBAL_COVER, out)
    print(out)


if __name__ == "__main__":
    main()
