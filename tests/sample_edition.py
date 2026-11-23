"""A small fictional pt-BR edition for EPUB tests and sample renders."""

from datetime import datetime

NOW = datetime(2026, 11, 8, 6, 50)


def _ts(hour: int, minute: int) -> int:
    return int(datetime(2026, 11, 8, hour, minute).timestamp())


def _body(paragraphs: int, words: int = 60) -> str:
    sentence = "Texto de exemplo para a edição de teste do BiteSIze com palavras suficientes. "
    paragraph = (sentence * (words // 12 + 1)).strip()
    return "\n".join(paragraph for _ in range(paragraphs))


def sample_sections() -> dict[str, list[dict]]:
    return {
        "Tecnologia": [
            {"title": "Cidade testa ônibus elétricos sem motorista em linha noturna",
             "short_title": "Ônibus sem motorista", "source": "Jornal Exemplo",
             "url": "https://jornalexemplo.com.br/onibus-noturno", "published": "06:30",
             "published_ts": _ts(6, 30), "relevance": 92, "relevance_source": "ai",
             "summary": "Piloto de seis meses cobre 12 km entre o centro e o aeroporto, com um operador a bordo. A prefeitura avalia ampliar a linha.",
             "tipo": "artigo-completo", "temas": ["tecnologia", "brasil"], "content": _body(5)},
            {"title": "Nova bateria de sódio promete carga completa em dez minutos",
             "short_title": "Bateria de sódio", "source": "Revista Modelo",
             "url": "https://revistamodelo.com.br/bateria", "published": "05:10", "published_ts": _ts(5, 10),
             "relevance": 81, "relevance_source": "ai",
             "summary": "Laboratório divulga protótipo sem lítio. Produção em escala depende de testes.",
             "tipo": "artigo-completo", "temas": ["tecnologia", "ciência"], "content": _body(4)},
            {"title": "Aplicativo de leitura ganha modo offline para trens e metrô",
             "source": "Portal Fictício", "url": "https://portalficticio.com.br/app", "published": "04:00",
             "relevance": 64, "relevance_source": "ai",
             "summary": "Atualização baixa as edições do dia de madrugada. Marcações sincronizam depois.",
             "tipo": "resumo", "temas": ["tecnologia"], "content": ""},
        ],
        "Ciência": [
            {"title": "Sonda registra gêiseres de gelo em lua de Saturno",
             "short_title": "Gêiseres em Saturno", "source": "Revista Modelo",
             "url": "https://revistamodelo.com.br/geiseres", "published": "05:10", "published_ts": _ts(5, 10),
             "relevance": 88, "relevance_source": "ai",
             "summary": "Imagens mostram jatos de até 200 km. A equipe vai procurar compostos orgânicos.",
             "key_points": ["Imagens de alta resolução mostram jatos de até 200 km de altura.",
                            "A equipe vai procurar compostos orgânicos no próximo sobrevoo.",
                            "Resultados completos só saem após a análise espectral."],
             "tipo": "artigo-completo", "temas": ["ciência", "clima"],
             "content": "\n".join([_body(3, 120), "O sobrevoo", _body(4, 120), "Como os jatos se formam",
                                   _body(4, 120), "Próximos passos", _body(3, 120)])},
            {"title": "Recife artificial atrai 60 espécies de peixes em dois anos",
             "source": "Portal Fictício", "url": "https://portalficticio.com.br/recife",
             "relevance": 72, "relevance_source": "ai",
             "summary": "Estrutura de concreto virou berçário. Pescadores relatam mais peixes.",
             "tipo": "artigo-completo", "temas": ["ciência", "clima"], "content": _body(3)},
        ],
        "Economia": [
            {"title": "Feiras de bairro passam a aceitar pagamento por aproximação",
             "source": "Diário Demo", "url": "https://diariodemo.com.br/feiras",
             "relevance": 77, "relevance_source": "ai",
             "summary": "Prefeitura distribui maquininhas. Feirantes relatam mais vendas.",
             "tipo": "artigo-completo", "temas": ["economia", "brasil", "tecnologia"], "content": _body(3)},
            {"title": "Cooperativa de café do sul de Minas exporta direto para o Japão",
             "source": "Gazeta de Teste", "url": "https://gazetadeteste.com.br/cafe",
             "relevance": 69, "relevance_source": "ai",
             "summary": "Primeiro contêiner sai em dezembro. Preço pago ao produtor sobe.",
             "tipo": "artigo-completo", "temas": ["economia", "mundo", "brasil"], "content": _body(2)},
        ],
    }
