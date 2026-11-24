# Kindle redesign — handoff para implementação

Design aprovado no canvas (claude.ai, privado). Este arquivo + `mockups/` são a fonte da verdade para implementar.

- `mockups/*.dc.html` — um arquivo por tela, 600×800 (proporção 3:4 do Kindle). HTML com estilos inline: cores, tamanhos, espaçamentos e estrutura estão ali. `{{x}}`, `<sc-for>` e `<sc-if>` são templates do editor; os dados de exemplo ficam em `renderVals()` no `<script>` de cada arquivo. **Leia como especificação visual, não copie o HTML** (o Kindle não roda JS nem flex/grid de forma confiável).
- Conteúdo de exemplo é fictício. Números de demo (tempo de leitura, "Edição 312", tendências "vs. ontem") precisam ser calculados.

## Regras gerais

1. **Só tons de cinza.** Paleta: `#111111 #3d3d3d #636363 #8a8a8a #b0b0b0 #d0d0d0`, papel `#ffffff`, texto secundário `#595959`, fios claros `#cfcfcf`.
2. **Dentro do livro não mexemos em fonte, tamanho nem espaçamento de corpo** — o leitor controla isso no Kindle. O trabalho é estrutura: hierarquia, ordem, divisão, navegação.
3. **Capa e gráficos são imagens geradas em PIL** (`cover_art.py`). Ali fonte e tamanho são nossos: embarcar fontes OFL no repo (Fraunces para display/números, Inter para rótulos) para o resultado ser igual em qualquer máquina.
4. Sem JavaScript, sem SVG inline no XHTML. Navegação só com links internos.
5. Não usar glifos que a fonte pode não ter (o `▸` virava `☐`). Em PIL, desenhar formas.

## Telas

### Capa — `Main.dc.html` (Capa A · Jornal) e `CoverB.dc.html` (Capa B · Número do dia)
- Proporção **3:4, 1236×1648** (hoje é 1600×2560, 1:1.6 → faixa branca lateral).
- Configuração nova `cover_style: jornal | numero` (dashboard + settings_store).
- **A**: linha de data/contagem no topo + fio duplo; relevância da manchete como **barra de 10 quadrados** + nota; manchete em Fraunces; "Também nesta edição" com 3 chamadas (número, editoria·fonte, título, tempo de leitura); **barra única segmentada de temas** (parte-do-todo, tipo a barra de contexto do Claude) com legenda nome + %; logo BiteSIze pequeno, centralizado embaixo entre fios. Variante `invert` (fundo preto).
- **B**: bloco preto com "Destaques de hoje" (3 chamadas curtas) e o dia em numeral gigante + mês/ano/dia da semana; manchete; 3 colunas de editoria com contagem **à esquerda** do nome + lead curto; rodapé: "7 matérias · 21 min" | logo centralizado | "Edição N".
- Chamadas curtas da B precisam de título curto (pedir ao modelo ou truncar).

### Sumário — `Opening.dc.html` (padrão) e `OpeningTwoCol.dc.html` (variação)
- Manchete (01) destacada, sem fio embaixo.
- Grupos por editoria: título **centralizado em Fraunces** com **linhas onduladas irregulares cinza-claras** dos dois lados (~125px cada; no EPUB, gerar como imagem PNG pequena) e "N matérias" embaixo.
- Itens sem divisórias entre si: número, título, fonte · relevância, tempo de leitura à direita.
- **Numeração contínua 01–NN em todo o livro.**
- Variação 2 colunas: usar `<table>` de 2 células (column-count não é confiável no Kindle).

### Temas da edição — `TopicsPie.dc.html` ou `TopicsSquares.dc.html` (escolher um)
- Página nova logo após o sumário.
- **Parte-do-todo**: todos os temas no mesmo total. Hoje o total = **menções de tema** (uma matéria pode ter vários `temas`; 7 matérias → 14 menções). Decisão pendente: menções vs. tema principal por matéria (ver abaixo).
- Pizza: gráfico + pills de % nas fatias, tabela tema / nº / % (vírgula decimal), "Onde ler" com pills de número linkando para cada matéria.
- Barra de unidades: 3 cards (Tema do dia, Matéria mais cruzada, Novidade), uma fileira com 1 quadrado por menção agrupada por tema, tabela com pill de tendência "vs. ontem", nota curta, nº e %.
- O gráfico vira **imagem PIL**; os links ficam numa lista HTML abaixo (link dentro de imagem não funciona).
- Tendência/novidade exigem **persistir contagem de temas por edição** (tabela nova no `data/bitesize.db`).

### Abertura de editoria — `Section.dc.html`
- Faixa preta **de ponta a ponta e do topo**, com "Editoria X de Y · N matérias · M min", nome em Fraunces grande e fontes.
- Destaque da editoria + demais matérias (número, fonte, título, linha fina, meta). Nada de meia página vazia.
- Rodapé: ← Sumário · Começar a ler · Próxima editoria →.

### Matéria — `Article.dc.html`
- Cabeçalho "NN · Editoria" / "i de N nesta editoria"; título; fonte · data humana (`8 nov, 06:30`, não ISO) · tempo de leitura.
- Bloco Resumo entre fio grosso em cima e fino embaixo (sem borda lateral): rótulo, barra de relevância, texto, tags como pills.
- **Capitular no primeiro parágrafo de toda matéria** (já existe em `_body_paragraphs`; manter sempre ligada).
- Rodapé: fonte original, ← Editoria · Sumário · Próxima →.

### Matéria longa — `ArticleLong.dc.html` / `ArticleLongEnd.dc.html`
- Acima de ~8 min: "Pontos-chave" (3 itens pedidos ao modelo) no lugar do resumo, e "Neste artigo" com links para os subtítulos existentes no HTML da fonte (sem subtítulos → some).
- Fim: ■ de fechamento, link "voltar ao início da matéria", cartão "A seguir" com a próxima matéria, rodapé de navegação.

## Onde mexer (verificar — o repo mudou desde o design)
- `cover_art.py` → `render_magazine_cover` (capas A/B, barra de temas, gráficos de temas, linhas onduladas).
- `epub.py` → `_global_cover_xhtml`, `_section_cover_xhtml`, `_section_index_page_xhtml`, `_article_xhtml`, `_body_paragraphs`, CSS `_CSS`.
- `magazine_layers.py` → chamadas, leads, numeração.
- `tags.py` → `temas` por matéria (base dos gráficos).
- `settings_store.py` + dashboard → `cover_style`, escolha do gráfico de temas, sumário 1/2 colunas.

## Decisões (Victor, 2026-11-22)
1. Capa: as duas atrás de `cover_style`; **B é a padrão**.
2. Página de temas: **barra de unidades** (`TopicsSquares`). A pizza não será feita.
3. Total dos gráficos: **menções de tema**.
4. Sumário: **1 coluna**. `OpeningTwoCol` não será feito.

## Como validar
- Testes primeiro (`pytest tests/ -v`), seguindo o CLAUDE.md do repo.
- Gerar `python main.py --all --no-kindle --no-books` e abrir no Kindle Previewer 3; comparar com os mockups.
- Atualizar ISSUES.md / ROADMAP.md na mesma mudança.
