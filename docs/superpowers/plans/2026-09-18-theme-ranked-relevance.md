# Theme-ranked relevance and English Jev UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Jev’s separate Keep + Likert relevance with a compiled 0–100 relevance from per-theme scores times the reader’s ranked interests; let the reader edit themes; make the Jev dashboard English-first with compact percent bars and a cleaner header.

**Architecture:** Theme catalog (id, English label, Portuguese label, rank) lives in SQLite next to other settings. Jev still asks one Noul per theme (no Keep question, no Score relevance). Policy computes `relevance = round(100 * sum(noul_t * weight_t) / sum(weights))` where rank 1 (most interesting) gets the highest weight. Dashboard talks English by default; Portuguese copy is a second string table. Numeric columns look like TypeSafe inbox percent + thin bar, not radial rings. Filter min/max sliders go away.

**Tech Stack:** Python 3, pytest, Flask dashboard, Tailwind CDN (`preflight: false`), existing `typesafe_sdk` Noul/Choice.

## Global Constraints

- Dashboard UI chrome is **English** by default. Portuguese is an alternate via `ui_language` (`en` | `pt`). Theme **ids** stay the current Portuguese slugs (`economia`, …) so existing digest tags and Jev JSON keep matching.
- Do not send Keep or a Likert relevance Score to Jev. Compiled relevance is policy, not a Jev question.
- Weight for rank `r` in a list of `n` themes: `weight = n - r + 1` (rank 1 → `n`). Missing theme scores count as `0`.
- `jev_min_keep` still exists; it now means **minimum compiled relevance** (0–100). Stories below it skip with reason `weak`.
- Filter toolbar: **no** min/max relevance, min keep, or max ad **sliders**. Search + dropdowns + grouping stay.
- Rel and Ad (and each visible theme score) use **percent text + a thin horizontal bar**, same visual idea as TypeSafe inbox Spam/Reply columns — not conic-gradient rings.
- Format run timestamps for humans: `18 Sep 2026, 18:20` (local offset already in ISO). Do not show raw `2026-09-18T18:20:37-03:00` as the primary label.
- Secrets stay off git. Dashboard writes still need Bearer token. Tests first. Do not commit `.env` or `data/`.
- Commit messages: plain-language why; no Co-Authored-By; no `--trailer`.
- Update `ROADMAP.md` when behavior changes. Do not grow `CLAUDE.md` with status.

## File map

| File | Role |
|------|------|
| `themes.py` | Default catalog, load/save ranks, `compiled_relevance`, slug ids |
| `settings_store.py` | Table `jev_themes` + `ui_language` setting |
| `tags.py` | `TEMAS` derived from catalog (enabled ids) |
| `jev_questions.py` | Noul per catalog theme; drop keep + Score relevance |
| `jev_policy.py` | Skip ads; tipo/paywall; temas from noul; compiled relevance; min compiled |
| `jev_triage.py` / `jev_labels.py` | Stop treating keep as a first-class label |
| `dashboard.py` | Theme CRUD + rank PUT; attach catalog on Jev run GET |
| `dashboard_static/i18n.js` | `en` / `pt` strings |
| `dashboard_static/app.js` | Header, bars, no sliders, theme editor, no Keep column |
| `dashboard_static/index.html` | English copy; language toggle if needed |
| `tests/test_themes.py` | Catalog + compiled score |
| `tests/test_jev_triage.py` | No keep in questions; compiled rel |
| `tests/test_dashboard_api.py` | Theme API + ui_language |

---

### Task 1: Theme catalog and compiled relevance

**Files:**
- Create: `themes.py`
- Create: `tests/test_themes.py`
- Modify: `settings_store.py` (table `jev_themes`, `ui_language` default `en`)
- Modify: `tags.py` so `TEMAS` is the enabled catalog ids (fallback to today’s frozenset if DB empty)

**Interfaces:**
- Consumes: none
- Produces:
  - `DEFAULT_THEMES`: list of `{id, label_en, label_pt}` for the current 11 ids
  - `list_themes() -> list[dict]` with `id`, `label_en`, `label_pt`, `rank` (1 = most interesting), `enabled`
  - `save_themes(themes: list[dict]) -> list[dict]`
  - `compiled_relevance(tema_scores: dict[str, float], ranked_ids: list[str] | None = None) -> int`

- [ ] **Step 1: Write failing tests** in `tests/test_themes.py`

```python
from themes import compiled_relevance, DEFAULT_THEMES

def test_compiled_relevance_prefers_high_rank_theme():
    ranked = ["economia", "esportes"]
    high_econ = compiled_relevance({"economia": 1.0, "esportes": 0.0}, ranked)
    high_sport = compiled_relevance({"economia": 0.0, "esportes": 1.0}, ranked)
    assert high_econ > high_sport
    assert 0 <= high_econ <= 100

def test_compiled_relevance_missing_theme_is_zero():
    assert compiled_relevance({}, ["economia"]) == 0

def test_default_theme_ids_match_legacy_temas():
    from tags import TEMAS
    assert {t["id"] for t in DEFAULT_THEMES} == set(TEMAS)
```

- [ ] **Step 2:** `pytest tests/test_themes.py -v` — fail on missing `themes` module.

- [ ] **Step 3:** Implement `compiled_relevance`:

```python
def compiled_relevance(tema_scores, ranked_ids=None):
    ids = list(ranked_ids or [])
    if not ids:
        return 0
    n = len(ids)
    total_w = 0.0
    acc = 0.0
    for i, tid in enumerate(ids):
        w = n - i
        total_w += w
        acc += float(tema_scores.get(tid) or 0) * w
    return max(0, min(100, int(round(100 * acc / total_w))))
```

Persist themes in SQLite: `id TEXT PRIMARY KEY, label_en, label_pt, rank INTEGER, enabled INTEGER`. Seed from `DEFAULT_THEMES` with rank = enumeration order (política first today — **re-seed ranks as 1..n in current DEFAULT_THEMES list order**). `list_themes` sorts by rank.

`tags.TEMAS`: if `list_themes` available, `frozenset(t["id"] for t in list_themes() if t["enabled"])`, else the current hardcoded set. Avoid import cycles: `themes.py` must not import `tags.py`. `tags.py` may import `list_themes` inside a function or keep a `_FALLBACK_TEMAS` constant that `themes.DEFAULT_THEMES` copies.

- [ ] **Step 4:** Tests pass. Add `ui_language` to `SETTINGS_DEFAULTS` as `("cli", "str", "en")` and `Settings.ui_language`.

- [ ] **Step 5:** Commit: why — ranked themes can compute a personal relevance without a second Jev score.

---

### Task 2: Jev questions and policy without Keep

**Files:**
- Modify: `jev_questions.py`, `jev_policy.py`, `jev_triage.py`, `jev_labels.py`
- Modify: `tests/test_jev_triage.py`, `tests/test_jev_policy.py` (create if missing), `tests/test_jev_labels.py`

**Interfaces:**
- Consumes: `list_themes()`, `compiled_relevance()`, `TEMA_NOULS` rebuilt from enabled theme ids
- Produces: `news_questions()` has **no** `keep` and **no** `relevance` Score. `flatten_response` has no keep. `judgment_from_answers` sets `relevance` via `compiled_relevance(answers["temas"], ranked_ids)` and skips `weak` when that integer `< min_keep`.

- [ ] **Step 1: Failing tests**

```python
def test_news_questions_omit_keep_and_score_relevance():
    qs = news_questions()
    assert "keep" not in qs
    assert "relevance" not in qs
    assert "ad" in qs
    assert any(k.startswith("tema_") for k in qs)

def test_judgment_compiles_theme_scores(monkeypatch):
    answers = {
        "ad": 0.01,
        "clickbait": 0.0,
        "press_release": 0.0,
        "paywall_teaser": 0.0,
        "tipo": "artigo-completo",
        "temas": {"economia": 1.0, "esportes": 0.0},
    }
    # monkeypatch ranked ids to ["economia", "esportes"]
    j = judgment_from_answers(answers, min_keep=0, ranked_ids=["economia", "esportes"])
    assert j["skip"] is False
    assert j["relevance"] == compiled_relevance(answers["temas"], ["economia", "esportes"])
```

Update fake `_response` in triage tests: drop `keep=`. Existing tests that assert `answers["keep"]` must switch to tema/ad.

`jev_labels.NOUL_KEYS` drop `keep`. Human labels may still include per-theme maps under `temas_scores` later; for this task allow labeling `ad` and per-theme by saving `temas` (applied tags) plus optional `tema_scores` dict. Minimum: drop keep from export predicted/label.

- [ ] **Step 2:** Run the new tests — fail.

- [ ] **Step 3:** Implement. `TEMA_NOULS` from `list_themes()` enabled ids. Instructions still say `snippet`. Tipo Choice stays. Ad, clickbait, press_release, paywall_teaser stay.

`classify_article` passes `ranked_ids=[t["id"] for t in list_themes() if t["enabled"]]` into `judgment_from_answers`.

- [ ] **Step 4:** `pytest tests/test_jev_triage.py tests/test_jev_labels.py tests/test_themes.py tests/test_tags.py -v`

- [ ] **Step 5:** Commit: why — Keep duplicated relevance; personal rank should drive the number.

---

### Task 3: Dashboard English chrome, header, bars, no sliders

**Files:**
- Create: `dashboard_static/i18n.js` with `I18N.en` and `I18N.pt` covering tabs, Jev intro, filters, table headers (`Story`, `Themes`, `Type`, `Rel`, `Ad`, `Skip`), `Reload runs`, `Export labels`, `Complete`, `Stories`, `Skipped`, `Workers`, `Min relevance`
- Modify: `dashboard_static/index.html` — English visible copy; `<script src="/i18n.js">` before `app.js`; bump cache query
- Modify: `dashboard_static/app.js` — `t(key)` from `I18N[lang]`; `formatJevWhen(iso)` → `18 Sep 2026, 18:20`; run cards use that; **delete** min/max rel, min keep, max ad slider markup and `jevFilter` fields; replace `ringMeter` / keep column with `pctBar(pct)`:

```javascript
function pctBar(pct, {warn} = {}) {
  if (pct == null || Number.isNaN(Number(pct))) return '<span class="text-xs text-slate-300">—</span>';
  const p = Math.max(0, Math.min(100, Math.round(Number(pct))));
  const fill = warn && p >= 40 ? "bg-rose-500" : "bg-slate-400";
  return `<div class="flex items-center gap-2 min-w-[4.5rem]" title="${p}%">
    <span class="w-8 text-right text-xs tabular-nums text-slate-600">${p}%</span>
    <span class="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
      <span class="block h-full ${fill}" style="width:${p}%"></span>
    </span>
  </div>`;
}
```

Rel column: `pctBar(humanOr(item,"relevance", item.relevance))`. Ad: `pctBar(adFrac*100, {warn:true})`. No Keep column. Theme cell: for each enabled theme with score (from `item.jev.answers.temas` or noul map), a compact `pctBar(noul*100)` stacked or wrapped with the English label (`label_en` from `run.themes` attached in GET). If GET has no `themes`, fall back to id.

- Modify: `dashboard.py` `get_jev_run` to include `"themes": themes.list_themes()`.
- Modify: `ROADMAP.md` Jev bullet.

**Interfaces:**
- Consumes: compiled `item.relevance`, `answers.temas`, `list_themes()`
- Produces: English Jev table without Keep and without those four sliders

- [ ] **Step 1:** Tests: `test_jev_run_includes_theme_catalog` on GET run JSON. No JS unit tests unless the repo already has them — do not add Vitest in this task.

- [ ] **Step 2–4:** Implement UI. Apply `t()` to Jev panel first; Settings field keys can stay snake_case this task (YAGNI) **except** tab labels and Jev strings must be English. Language: `localStorage.bitesize_ui_lang` or settings `ui_language`; read settings on load.

- [ ] **Step 5:** Commit: why — one language on the review screen, and scores that scan like a mail inbox.

**Manual check:** open Jev tab, load a run, confirm no Keep, no four sliders, dates readable, Rel/Ad are bar+percent.

---

### Task 4: Theme editor and rank

**Files:**
- Modify: `dashboard.py` — `GET/PUT /api/jev/themes` (PUT replaces list; auth required). Body: `[{id, label_en, label_pt, rank, enabled}]`. New theme id: lowercase `[a-z0-9_-]+` from `label_en` slug, unique.
- Modify: `dashboard_static/app.js` + `index.html` — on Jev tab, above run list: list of themes with English label, Portuguese label, rank up/down, enabled checkbox, add row, Save themes (Bearer). Rank 1 = most interesting. Saving reorders ranks 1..n.
- Tests: `tests/test_dashboard_api.py` create/reorder/reject bad id.

**Interfaces:**
- Consumes: Task 1 `save_themes` / `list_themes`
- Produces: next digest uses new catalog for Jev Nouls and compiled weights

- [ ] **Step 1:** Failing API tests (401 without token; 200 list includes `economia`; PUT rank swap persists).

- [ ] **Step 2–4:** Implement. After save, if a run is open, Rel numbers do **not** rewrite historical JSON; only **new** classify runs use new ranks. Show a one-line note: “Ranks apply to the next digest.”

- [ ] **Step 5:** Commit: why — the reader’s topic order is the relevance model.

Human labels: clicking a theme bar is out of scope unless cheap; keep existing per-field label controls for Ad/tipo/temas **without Keep**.

---

## Spec coverage

- Drop Keep: Task 2 + 3
- Compiled relevance from themes × ranks: Task 1–2
- Edit categories/themes: Task 4
- Remove filter sliders: Task 3
- Header/dates/UI: Task 3
- Percent bars like inbox: Task 3
- English first, Portuguese alternate: Task 3 (`i18n.js`) + theme `label_en`/`label_pt`

## Placeholder scan

None intentional. `tests/test_jev_policy.py` “create if missing” is allowed: add the file in Task 2 with the judgment test.
