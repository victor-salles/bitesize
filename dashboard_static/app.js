const GROUP_ORDER = ["integrations", "ai", "books", "feed", "filter", "epub", "cli"];

const FIELD_UNITS = {
  gemini_timeout: "unitSeconds",
  gemini_check_timeout: "unitSeconds",
  ollama_timeout: "unitSeconds",
  feed_timeout: "unitSeconds",
  calendar_lookahead_days: "unitDays",
  calendar_lookback_days: "unitDays",
  gmail_lookback_hours: "unitHours",
  truncate_chars: "unitChars",
  min_body_chars: "unitChars",
  min_summary_chars: "unitChars",
};

const FIELD_CHOICES = {
  ai_backend: ["antigravity", "gemini", "ollama"],
};

// TODO(human): list the settings keys that belong under "Advanced".
const ADVANCED_SETTINGS = new Set([]);

const BOOL_KEYS = new Set([
  "kindle_delivery_enabled",
  "integration_gmail",
  "integration_google_calendar",
  "cli_select_all_sources",
  "jev_triage_enabled",
]);

const KINDLE_KEYS = [
  "kindle_email",
  "smtp_user",
  "smtp_password",
  "smtp_host",
  "smtp_port",
  "kindle_delivery_enabled",
];

let settingsData = {};

const TOKEN_KEY = "bitesize_dashboard_token";
const LANG_KEY = "bitesize_ui_lang";
let uiLangCode = "en";

function uiLang() {
  const stored = localStorage.getItem(LANG_KEY);
  if (stored === "pt" || stored === "en") return stored;
  const fromSettings = settingsData?.cli?.ui_language;
  if (fromSettings === "pt" || fromSettings === "pt-BR") return fromSettings === "pt-BR" ? "pt" : fromSettings;
  if (fromSettings === "en") return "en";
  return "en";
}

function t(key, vars = {}) {
  const table = (typeof I18N !== "undefined" && I18N[uiLangCode]) || I18N.en;
  let s = table[key] ?? I18N.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) {
    s = s.replace(`{${k}}`, String(v));
  }
  return s;
}

function formatJevWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const day = d.getDate();
  const mon = months[d.getMonth()];
  const year = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${day} ${mon} ${year}, ${hh}:${mm}`;
}

function pctBar(pct, { warn } = {}) {
  if (pct == null || Number.isNaN(Number(pct))) {
    return '<span class="text-xs text-slate-300">—</span>';
  }
  const p = Math.max(0, Math.min(100, Math.round(Number(pct))));
  const fill = warn && p >= 40 ? "bg-rose-500" : "bg-slate-400";
  return `<div class="flex items-center gap-2 min-w-[4.5rem]" title="${p}%">
    <span class="w-8 text-right text-xs tabular-nums text-slate-600">${p}%</span>
    <span class="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
      <span class="block h-full ${fill}" style="width:${p}%"></span>
    </span>
  </div>`;
}

function applyStaticI18n() {
  uiLangCode = uiLang();
  const map = {
    ".subtitle": "headerSubtitle",
    'label[for="dashboard-token"]': "tokenLabel",
    "#save-settings": "saveSettings",
    "#run-digest": "runDigest",
    "#token-help": "tokenHelp",
    "#panel-jev .preview-intro": "jevIntro",
    "#refresh-jev": "reloadRuns",
    "#export-jev-labels": "exportLabels",
    "footer p": "footerJev",
  };
  for (const [sel, key] of Object.entries(map)) {
    const el = $(sel);
    if (!el) continue;
    el.textContent = t(key);
  }
  const tokenEl = $("#dashboard-token");
  if (tokenEl) tokenEl.placeholder = t("tokenPlaceholder");
  const runBtn = $("#run-digest");
  if (runBtn) runBtn.title = t("digestHint");
  paintTokenSummary();
  const tabKeys = {
    settings: "tabSettings",
    sources: "tabSources",
    preview: "tabPreview",
    jev: "tabJev",
    kindle: "tabKindle",
  };
  $$(".tab").forEach((btn) => {
    const k = tabKeys[btn.dataset.tab];
    if (k) btn.textContent = t(k);
  });
}

function dashboardToken() {
  const el = $("#dashboard-token");
  const v = (el?.value || localStorage.getItem(TOKEN_KEY) || "").trim();
  if (el && v && !el.value) el.value = v;
  return v;
}

function paintTokenSummary() {
  const summary = $("#token-summary");
  if (!summary) return;
  const set = !!dashboardToken();
  summary.textContent = t(set ? "tokenSet" : "tokenMissing");
  summary.classList.toggle("is-missing", !set);
}

function authHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = dashboardToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return [...document.querySelectorAll(sel)]; }

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: authHeaders(),
    ...opts,
  });
  const data = r.headers.get("content-type")?.includes("json")
    ? await r.json()
    : null;
  if (!r.ok) throw new Error(data?.error || data?.message || r.statusText);
  return data;
}

function setStatus(el, msg, ok) {
  el.textContent = msg || "";
  el.className = "status" + (msg ? (ok ? " ok" : " err") : "");
}

function fieldLabel(key) {
  const k = `f_${key}`;
  const s = t(k);
  return s === k ? key.replace(/_/g, " ") : s;
}

function fieldHint(key) {
  const k = `h_${key}`;
  const s = t(k);
  return s === k ? "" : s;
}

function settingsField(key, value) {
  const row = document.createElement("div");
  const input = inputForKey(key, value);
  input.id = `set-${key}`;
  const hint = fieldHint(key);
  if (input.type === "checkbox") {
    row.className = "field field--toggle";
    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.className = "field__label";
    label.textContent = fieldLabel(key);
    row.append(input, label);
  } else {
    row.className = "field";
    const label = document.createElement("label");
    label.htmlFor = input.id;
    label.className = "field__label";
    label.textContent = fieldLabel(key);
    const control = document.createElement("div");
    control.className = "field__control";
    control.appendChild(input);
    if (FIELD_UNITS[key]) {
      const unit = document.createElement("span");
      unit.className = "field__unit";
      unit.textContent = t(FIELD_UNITS[key]);
      control.appendChild(unit);
    }
    row.append(label, control);
  }
  if (hint) {
    const p = document.createElement("p");
    p.className = "field__hint";
    p.id = `${input.id}-hint`;
    p.textContent = hint;
    input.setAttribute("aria-describedby", p.id);
    row.appendChild(p);
  }
  return row;
}

function inputForKey(key, value) {
  if (FIELD_CHOICES[key]) {
    const sel = document.createElement("select");
    for (const v of FIELD_CHOICES[key]) sel.add(new Option(v, v, false, v === value));
    sel.dataset.key = key;
    return sel;
  }
  if (BOOL_KEYS.has(key) || typeof value === "boolean") {
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !!value;
    cb.dataset.key = key;
    return cb;
  }
  const input = document.createElement("input");
  input.type = key.includes("password") ? "password"
    : key.includes("email") ? "email"
    : typeof value === "number" ? "number"
    : "text";
  input.value = value ?? "";
  input.dataset.key = key;
  return input;
}

function renderSettingsGroups() {
  const root = $("#settings-groups");
  root.innerHTML = "";
  const rank = (g) => (GROUP_ORDER.includes(g) ? GROUP_ORDER.indexOf(g) : GROUP_ORDER.length);
  const groups = Object.keys(settingsData)
    .filter((g) => g !== "kindle")
    .sort((a, b) => rank(a) - rank(b));
  const advanced = document.createElement("details");
  advanced.className = "group group--advanced";
  advanced.innerHTML = `<summary>${esc(t("advancedSettings"))}</summary>`;
  for (const group of groups) {
    const entries = Object.entries(settingsData[group]);
    const basic = entries.filter(([k]) => !ADVANCED_SETTINGS.has(k));
    const extra = entries.filter(([k]) => ADVANCED_SETTINGS.has(k));
    if (basic.length) {
      const card = document.createElement("div");
      card.className = "group";
      card.innerHTML = `<h2>${esc(t(`g_${group}`))}</h2>`;
      basic.forEach(([k, v]) => card.appendChild(settingsField(k, v)));
      root.appendChild(card);
    }
    if (extra.length) {
      const sub = document.createElement("div");
      sub.className = "group__sub";
      sub.innerHTML = `<h3>${esc(t(`g_${group}`))}</h3>`;
      extra.forEach(([k, v]) => sub.appendChild(settingsField(k, v)));
      advanced.appendChild(sub);
    }
  }
  if (advanced.children.length > 1) root.appendChild(advanced);
}

function renderKindleFields() {
  const root = $("#kindle-fields");
  root.innerHTML = "";
  const fields = settingsData.kindle || {};
  for (const key of KINDLE_KEYS) {
    if (key === "smtp_password_set") continue;
    const row = settingsField(key, fields[key]);
    const input = row.querySelector("[data-key]");
    if (key === "smtp_password" && fields.smtp_password_set && !fields[key]) {
      input.placeholder = "•••••••• (unchanged)";
    }
    input.dataset.kindle = "1";
    root.appendChild(row);
  }
}

function collectInputs(container) {
  const out = {};
  container.querySelectorAll("[data-key]").forEach((el) => {
    const key = el.dataset.key;
    if (key === "smtp_password" && !el.value.trim()) {
      return;
    }
    out[key] = el.type === "checkbox" ? el.checked : el.value;
  });
  return out;
}

function paintLangSwitcher() {
  const current = uiLang();
  $$("#ui-lang-switch [data-ui-lang]").forEach((btn) => {
    btn.setAttribute("aria-pressed", String(btn.dataset.uiLang === current));
  });
}

function setUiLang(lang, { persist = false } = {}) {
  uiLangCode = lang === "pt" ? "pt" : "en";
  if (persist) localStorage.setItem(LANG_KEY, uiLangCode);
  applyStaticI18n();
  paintLangSwitcher();
  if (Object.keys(settingsData).length) {
    renderSettingsGroups();
    renderKindleFields();
  }
  if (jevThemesDraft.length) renderJevThemeEditor();
  if (jevOpenRun) {
    const snap = { ...jevFilter };
    renderJevRunDetail(jevOpenRun);
    for (const [sel, val] of [
      ["#jev-q", snap.q],
      ["#jev-source", snap.source],
      ["#jev-tipo", snap.tipo],
      ["#jev-tema", snap.tema],
      ["#jev-skip", snap.skip],
      ["#jev-group", snap.group],
    ]) {
      const el = $(sel);
      if (el && val != null) el.value = val;
    }
    readJevFilters();
  }
  if (lastDigestSnap) paintDigestProgress(lastDigestSnap);
}

const DIGEST_STEP_KEYS = {
  feeds: "stepFeeds",
  fulltext: "stepFulltext",
  score: "stepScore",
  covers: "stepCovers",
  epub: "stepEpub",
  kindle: "stepKindle",
  books: "stepBooks",
};
const DIGEST_STATE_KEYS = {
  pending: "stepPending",
  running: "stepRunning",
  done: "stepDone",
  skipped: "stepSkipped",
  error: "stepError",
};

let digestPoll = null;
let lastDigestSnap = null;
let lastDigestStatus = "idle";

function paintDigestProgress(data) {
  lastDigestSnap = data;
  const list = $("#digest-steps");
  const log = $("#digest-log");
  const btn = $("#run-digest");
  if (!list || !data) return;
  paintLastDigest(data.last_digest);
  const progress = $("#digest-progress");
  if (progress) progress.hidden = (data.status || "idle") === "idle";
  const mark = { pending: "○", running: "●", done: "✓", skipped: "–", error: "✕" };
  const color = {
    pending: "text-slate-500",
    running: "text-sky-700 font-medium",
    done: "text-emerald-700",
    skipped: "text-slate-500",
    error: "text-rose-700",
  };
  list.innerHTML = (data.steps || [])
    .map((s) => {
      const state = s.state || "pending";
      return `<li class="flex items-center justify-between gap-3 text-sm ${color[state] || "text-slate-500"}">
        <span>${mark[state] || "○"} ${esc(t(DIGEST_STEP_KEYS[s.id] || s.label || s.id))}</span>
        <span class="text-[11px] uppercase tracking-wide">${esc(t(DIGEST_STATE_KEYS[state] || "stepPending"))}</span>
      </li>`;
    })
    .join("");
  const lines = (data.lines || []).slice(-16);
  if (log) {
    log.hidden = !lines.length;
    log.textContent = lines.join("\n");
    if (lines.length) log.scrollTop = log.scrollHeight;
  }
  if (btn) btn.disabled = data.status === "running";
  const st = $("#digest-run-status");
  if (!st) return;
  if (data.status === "running") setStatus(st, t("digestRunning"), true);
  else if (data.status === "done") setStatus(st, t("digestDone"), true);
  else if (data.status === "error") setStatus(st, data.error || t("digestFailed"), false);
}

function paintLastDigest(last) {
  const el = $("#last-digest");
  if (!el) return;
  if (!last) {
    el.textContent = t("lastDigestNone");
    return;
  }
  const when = new Date(last.finished_at).toLocaleString(uiLangCode === "pt" ? "pt-BR" : "en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  el.textContent = t("lastDigest", { when });
  el.title = last.file;
}

function startDigestPoll() {
  if (digestPoll) return;
  digestPoll = setInterval(() => {
    refreshDigestProgress().catch(() => {});
  }, 500);
}

function stopDigestPoll() {
  if (!digestPoll) return;
  clearInterval(digestPoll);
  digestPoll = null;
}

async function refreshDigestProgress() {
  const data = await api("/api/digest/run");
  const wasRunning = lastDigestStatus === "running";
  paintDigestProgress(data);
  lastDigestStatus = data.status || "idle";
  if (data.status === "running") startDigestPoll();
  else stopDigestPoll();
  if (wasRunning && data.status === "done") {
    loadJevRuns().catch(() => {});
  }
}

async function startDigest() {
  const st = $("#digest-run-status");
  if (!dashboardToken()) {
    setStatus(st, t("digestNeedToken"), false);
    return;
  }
  try {
    const r = await fetch("/api/digest/run", { method: "POST", headers: authHeaders() });
    const data = await r.json().catch(() => ({}));
    if (r.status === 409) {
      paintDigestProgress(data);
      setStatus(st, t("digestBusy"), false);
      startDigestPoll();
      return;
    }
    if (!r.ok) throw new Error(data.error || r.statusText);
    lastDigestStatus = "running";
    paintDigestProgress(data);
    startDigestPoll();
  } catch (e) {
    setStatus(st, e.message, false);
  }
}

async function loadSettings() {
  settingsData = await api("/api/settings");
  uiLangCode = uiLang();
  applyStaticI18n();
  paintLangSwitcher();
  renderSettingsGroups();
  renderKindleFields();
}

async function saveSettings(container, statusEl) {
  try {
    const updates = collectInputs(container);
    settingsData = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify(updates),
    });
    setStatus(statusEl, "Saved.", true);
    renderKindleFields();
  } catch (e) {
    setStatus(statusEl, e.message, false);
  }
}

function rowMenu(label, items) {
  const menu = document.createElement("details");
  menu.className = "row-menu";
  const summary = document.createElement("summary");
  summary.setAttribute("aria-label", label);
  summary.textContent = "⋯";
  const pop = document.createElement("div");
  pop.className = "row-menu__pop";
  for (const { text, danger, onClick } of items) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    if (danger) b.className = "danger";
    b.onclick = () => {
      menu.open = false;
      onClick();
    };
    pop.appendChild(b);
  }
  menu.append(summary, pop);
  return menu;
}

function textInput(value, label, placeholder = "") {
  const input = document.createElement("input");
  input.type = "text";
  input.value = value;
  input.placeholder = placeholder;
  input.setAttribute("aria-label", label);
  return input;
}

async function saveFeed(feed, name, url, enabled) {
  const status = $("#sources-status");
  try {
    await api(`/api/feeds/${feed.id}`, {
      method: "PUT",
      body: JSON.stringify({
        name: name.value.trim(),
        url: url.value.trim(),
        enabled: enabled.checked,
      }),
    });
    setStatus(status, t("feedSaved", { name: name.value.trim() }), true);
  } catch (e) {
    setStatus(status, e.message, false);
  }
}

function renderSources(data) {
  const root = $("#sources-list");
  root.innerHTML = "";
  for (const cat of data.categories) {
    const card = document.createElement("div");
    card.className = "card source-card";
    const header = document.createElement("div");
    header.className = "category-header";
    const nameInput = textInput(cat.name, t("categoryName"));
    nameInput.className = "category-header__name";
    nameInput.addEventListener("change", async () => {
      try {
        await api(`/api/categories/${cat.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: nameInput.value.trim() }),
        });
        setStatus($("#sources-status"), t("categorySaved", { name: nameInput.value.trim() }), true);
      } catch (e) {
        setStatus($("#sources-status"), e.message, false);
      }
    });
    const count = document.createElement("span");
    count.className = "category-header__count";
    count.textContent = `${cat.feeds.filter((f) => f.enabled).length}/${cat.feeds.length}`;
    header.append(
      nameInput,
      count,
      rowMenu(t("moreActions"), [
        {
          text: t("deleteCategory"),
          danger: true,
          onClick: async () => {
            if (!confirm(`Delete category "${cat.name}" and all feeds?`)) return;
            await api(`/api/categories/${cat.id}`, { method: "DELETE" });
            await refreshSources();
          },
        },
      ]),
    );
    card.appendChild(header);

    for (const feed of cat.feeds) {
      const row = document.createElement("div");
      row.className = "feed-row" + (feed.enabled ? "" : " is-off");
      const name = textInput(feed.name, t("feedName"));
      const url = textInput(feed.url, t("feedUrl"));
      url.classList.add("feed-row__url");
      const toggle = document.createElement("label");
      toggle.className = "feed-row__toggle";
      const enabled = document.createElement("input");
      enabled.type = "checkbox";
      enabled.checked = feed.enabled;
      toggle.append(enabled, document.createTextNode(t("feedOn")));
      const save = () => saveFeed(feed, name, url, enabled);
      name.addEventListener("change", save);
      url.addEventListener("change", save);
      enabled.addEventListener("change", () => {
        row.classList.toggle("is-off", !enabled.checked);
        save();
      });
      row.append(
        name,
        url,
        toggle,
        rowMenu(t("moreActions"), [
          {
            text: t("deleteFeed"),
            danger: true,
            onClick: async () => {
              await api(`/api/feeds/${feed.id}`, { method: "DELETE" });
              await refreshSources();
            },
          },
        ]),
      );
      card.appendChild(row);
    }

    const addRow = document.createElement("div");
    addRow.className = "feed-add";
    const newName = textInput("", t("feedName"), t("feedName"));
    const newUrl = textInput("", t("feedUrl"), t("feedUrl"));
    const addBtn = document.createElement("button");
    addBtn.textContent = t("addFeed");
    addBtn.onclick = async () => {
      await api("/api/feeds", {
        method: "POST",
        body: JSON.stringify({
          category_id: cat.id,
          name: newName.value.trim(),
          url: newUrl.value.trim(),
        }),
      });
      await refreshSources();
    };
    addRow.append(newName, newUrl, addBtn);
    card.appendChild(addRow);
    root.appendChild(card);
  }
}

async function refreshSources() {
  const data = await api("/api/sources");
  renderSources(data);
}

let previewLoaded = false;
let jevLoaded = false;
let jevThemesDraft = [];
let jevOpenRun = null;
let jevSelectedIndex = -1;
let jevFilter = defaultJevFilter();
let jevSort = { key: null, dir: "desc" };
let jevCollapsed = new Set();

function defaultJevFilter() {
  return {
    q: "",
    source: "",
    tipo: "",
    tema: "",
    skip: "",
    group: "none",
  };
}

$$(".tab").forEach((btn, i, tabs) => {
  btn.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!step) return;
    const next = tabs[(i + step + tabs.length) % tabs.length];
    next.focus();
    next.click();
  });
  btn.addEventListener("click", () => {
    $$(".tab").forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
      b.tabIndex = -1;
    });
    $$(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    btn.tabIndex = 0;
    $(`#panel-${btn.dataset.tab}`).classList.add("active");
    document.body.classList.toggle("jev-wide", btn.dataset.tab === "jev");
    if (btn.dataset.tab === "preview" && !previewLoaded) {
      previewLoaded = true;
      loadPreview();
    }
    if (btn.dataset.tab === "jev" && !jevLoaded) {
      jevLoaded = true;
      loadJevThemes();
      loadJevRuns();
    }
  });
});

$("#save-settings").onclick = () =>
  saveSettings($("#panel-settings"), $("#settings-status"));

$("#save-kindle").onclick = () =>
  saveSettings($("#kindle-fields"), $("#kindle-status"));

$("#test-kindle").onclick = async () => {
  const status = $("#kindle-status");
  try {
    await saveSettings($("#kindle-fields"), status);
    const res = await api("/api/kindle/test", { method: "POST" });
    setStatus(status, res.message, res.ok);
  } catch (e) {
    setStatus(status, e.message, false);
  }
};

$("#add-category").onclick = async () => {
  const name = $("#new-category-name").value.trim();
  if (!name) return;
  await api("/api/categories", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  $("#new-category-name").value = "";
  await refreshSources();
};

async function loadPreview() {
  const status = $("#preview-status");
  const root = $("#preview-list");
  setStatus(status, "Fetching headlines…", true);
  root.innerHTML = "";
  try {
    const data = await api("/api/preview");
    renderPreview(data);
    setStatus(status, "Headlines loaded. Use Include to keep or drop a source.", true);
  } catch (e) {
    setStatus(status, e.message, false);
  }
}

function renderPreview(data) {
  const root = $("#preview-list");
  root.innerHTML = "";
  for (const cat of data.categories || []) {
    const card = document.createElement("div");
    card.className = "card";
    const h = document.createElement("h2");
    h.textContent = cat.name;
    card.appendChild(h);
    for (const feed of cat.feeds || []) {
      const block = document.createElement("div");
      block.className = "preview-feed";
      const header = document.createElement("div");
      header.className = "preview-feed-header";
      const title = document.createElement("strong");
      title.textContent = feed.name;
      const toggle = document.createElement("label");
      toggle.className = "preview-toggle";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = !!feed.enabled;
      cb.onchange = async () => {
        try {
          await api(`/api/feeds/${feed.id}`, {
            method: "PUT",
            body: JSON.stringify({ enabled: cb.checked }),
          });
          setStatus(
            $("#preview-status"),
            cb.checked ? `${feed.name} included.` : `${feed.name} removed from the digest.`,
            true,
          );
        } catch (e) {
          cb.checked = !cb.checked;
          setStatus($("#preview-status"), e.message, false);
        }
      };
      toggle.append(cb, document.createTextNode(" Include in digest"));
      header.append(title, toggle);
      block.appendChild(header);
      if (feed.error) {
        const err = document.createElement("p");
        err.className = "preview-error";
        err.textContent = feed.error;
        block.appendChild(err);
      }
      const items = feed.headlines || [];
      const list = document.createElement("ol");
      list.className = "preview-headlines";
      const moreBtn = document.createElement("button");
      moreBtn.type = "button";
      moreBtn.className = "preview-more";
      let expanded = false;

      const paintHeadlines = () => {
        list.innerHTML = "";
        const visible = expanded ? items : items.slice(0, 5);
        for (const item of visible) {
          const li = document.createElement("li");
          if (item.url) {
            const a = document.createElement("a");
            a.href = item.url;
            a.target = "_blank";
            a.rel = "noopener";
            a.textContent = item.title;
            li.appendChild(a);
          } else {
            li.textContent = item.title;
          }
          if (item.published) {
            const t = document.createElement("span");
            t.className = "preview-time";
            t.textContent = item.published;
            li.append(" ", t);
          }
          list.appendChild(li);
        }
        if (items.length > 5) {
          const hidden = items.length - 5;
          moreBtn.hidden = false;
          moreBtn.textContent = expanded
            ? "Show fewer"
            : `Show more (${hidden} more)`;
        } else {
          moreBtn.hidden = true;
        }
      };
      moreBtn.onclick = () => {
        expanded = !expanded;
        paintHeadlines();
      };

      if (!items.length && !feed.error) {
        const empty = document.createElement("p");
        empty.className = "preview-empty";
        empty.textContent = "No headlines returned.";
        block.appendChild(empty);
      } else {
        block.appendChild(list);
        block.appendChild(moreBtn);
        paintHeadlines();
      }
      card.appendChild(block);
    }
    root.appendChild(card);
  }
}

$("#refresh-preview").onclick = loadPreview;

function renumberJevThemesDraft() {
  jevThemesDraft.forEach((th, i) => {
    th.rank = i + 1;
  });
}

function moveJevTheme(from, to) {
  if (from === to || from < 0 || to < 0) return;
  if (from >= jevThemesDraft.length || to >= jevThemesDraft.length) return;
  const [item] = jevThemesDraft.splice(from, 1);
  jevThemesDraft.splice(to, 0, item);
  renumberJevThemesDraft();
}

const THEME_HANDLE_ICON =
  '<svg width="12" height="16" viewBox="0 0 12 16" aria-hidden="true"><circle cx="3" cy="3" r="1.35" fill="currentColor"/><circle cx="9" cy="3" r="1.35" fill="currentColor"/><circle cx="3" cy="8" r="1.35" fill="currentColor"/><circle cx="9" cy="8" r="1.35" fill="currentColor"/><circle cx="3" cy="13" r="1.35" fill="currentColor"/><circle cx="9" cy="13" r="1.35" fill="currentColor"/></svg>';

function renderJevThemeEditor() {
  const root = $("#jev-theme-editor");
  if (!root) return;
  const rows = jevThemesDraft
    .map((th, i) => {
      const off = th.enabled ? "" : " is-off";
      return `<div class="theme-row${off}" data-theme-row data-theme-i="${i}">
      <input type="checkbox" class="theme-row__on" data-theme-enabled="${i}" ${th.enabled ? "checked" : ""}
        aria-label="${esc(t("themeEnabled"))}">
      <button type="button" class="theme-row__handle" data-theme-handle
        aria-label="${esc(t("dragTheme"))}">${THEME_HANDLE_ICON}</button>
      <span class="theme-row__rank">${i + 1}</span>
      <label class="theme-row__cell theme-row__en">
        <input type="text" class="theme-row__field" data-theme-field="label_en" data-theme-i="${i}"
          value="${esc(th.label_en)}" aria-label="${esc(t("themeLabelEn"))}">
      </label>
      <label class="theme-row__cell theme-row__pt">
        <input type="text" class="theme-row__field" data-theme-field="label_pt" data-theme-i="${i}"
          value="${esc(th.label_pt)}" aria-label="${esc(t("themeLabelPt"))}">
      </label>
    </div>`;
    })
    .join("");
  root.innerHTML = `<h3 class="theme-editor__title">${esc(t("themeEditorTitle"))}</h3>
    <p class="theme-editor__hint">${esc(t("ranksNextDigest"))}</p>
    <div class="theme-list">
      <div class="theme-list__head" aria-hidden="true">
        <span>${esc(t("themeEnabled"))}</span>
        <span></span>
        <span>#</span>
        <span>${esc(t("themeLabelEn"))}</span>
        <span>${esc(t("themeLabelPt"))}</span>
      </div>
      ${rows}
    </div>
    <div class="theme-editor__actions">
      <button type="button" id="jev-theme-add">${esc(t("addTheme"))}</button>
      <button type="button" id="jev-theme-save" class="primary">${esc(t("saveThemes"))}</button>
    </div>`;

  root.querySelectorAll("[data-theme-field]").forEach((input) => {
    input.addEventListener("input", () => {
      const i = Number(input.dataset.themeI);
      const field = input.dataset.themeField;
      if (jevThemesDraft[i]) jevThemesDraft[i][field] = input.value;
    });
  });
  root.querySelectorAll("[data-theme-enabled]").forEach((box) => {
    box.addEventListener("change", () => {
      const i = Number(box.dataset.themeEnabled);
      if (!jevThemesDraft[i]) return;
      jevThemesDraft[i].enabled = box.checked;
      box.closest(".theme-row")?.classList.toggle("is-off", !box.checked);
    });
  });
  bindThemeDrag(root);
  $("#jev-theme-add").onclick = () => {
    jevThemesDraft.push({
      id: "",
      label_en: "",
      label_pt: "",
      rank: jevThemesDraft.length + 1,
      enabled: true,
    });
    renderJevThemeEditor();
  };
  $("#jev-theme-save").onclick = () =>
    saveJevThemes().catch((e) => setStatus($("#jev-status"), e.message, false));
}

function bindThemeDrag(root) {
  root.querySelectorAll("[data-theme-row]").forEach((row) => {
    const handle = row.querySelector("[data-theme-handle]");
    if (!handle) return;
    handle.addEventListener("pointerdown", () => {
      row.setAttribute("draggable", "true");
    });
    row.addEventListener("dragstart", (e) => {
      if (!row.getAttribute("draggable")) {
        e.preventDefault();
        return;
      }
      const from = Number(row.dataset.themeI);
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(from));
      row.classList.add("is-dragging");
    });
    row.addEventListener("dragend", () => {
      row.removeAttribute("draggable");
      root.querySelectorAll(".theme-row").forEach((r) => r.classList.remove("is-dragging", "is-drop-target"));
    });
    handle.addEventListener("keydown", (e) => {
      const i = Number(row.dataset.themeI);
      if (e.key === "ArrowUp" && i > 0) {
        e.preventDefault();
        moveJevTheme(i, i - 1);
        renderJevThemeEditor();
        root.querySelector(`[data-theme-i="${i - 1}"] [data-theme-handle]`)?.focus();
      }
      if (e.key === "ArrowDown" && i < jevThemesDraft.length - 1) {
        e.preventDefault();
        moveJevTheme(i, i + 1);
        renderJevThemeEditor();
        root.querySelector(`[data-theme-i="${i + 1}"] [data-theme-handle]`)?.focus();
      }
    });
    row.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      row.classList.add("is-drop-target");
    });
    row.addEventListener("dragleave", (e) => {
      if (!row.contains(e.relatedTarget)) row.classList.remove("is-drop-target");
    });
    row.addEventListener("drop", (e) => {
      e.preventDefault();
      row.classList.remove("is-drop-target");
      const from = Number(e.dataTransfer.getData("text/plain"));
      const to = Number(row.dataset.themeI);
      moveJevTheme(from, to);
      renderJevThemeEditor();
    });
  });
}

async function loadJevThemes() {
  const root = $("#jev-theme-editor");
  if (!root) return;
  try {
    const data = await api("/api/jev/themes");
    jevThemesDraft = (data.themes || []).map((th) => ({ ...th }));
    renderJevThemeEditor();
  } catch (e) {
    root.innerHTML = `<p class="text-xs text-rose-600">${esc(t("themeEditorTitle"))}: ${esc(e.message)}</p>
      <p class="text-xs text-slate-500 mt-1">Restart the dashboard if this stays after a refresh.</p>`;
  }
}

async function saveJevThemes() {
  renumberJevThemesDraft();
  const body = jevThemesDraft.map((th) => ({
    id: th.id || "",
    label_en: (th.label_en || "").trim(),
    label_pt: (th.label_pt || "").trim(),
    rank: th.rank,
    enabled: Boolean(th.enabled),
  }));
  const data = await api("/api/jev/themes", { method: "PUT", body: JSON.stringify(body) });
  jevThemesDraft = (data.themes || []).map((th) => ({ ...th }));
  renderJevThemeEditor();
  setStatus($("#jev-status"), t("themesSaved"), true);
}

async function loadJevRuns() {
  const status = $("#jev-status");
  const list = $("#jev-run-list");
  const detail = $("#jev-run-detail");
  detail.innerHTML = "";
  setStatus(status, t("loadingRuns"), true);
  try {
    const data = await api("/api/jev/runs");
    renderJevRunList(data.runs || []);
    const n = (data.runs || []).length;
    setStatus(status, n ? t("runsOnDisk", { n }) : t("noRunsYet"), true);
  } catch (e) {
    list.innerHTML = "";
    setStatus(status, e.message, false);
  }
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pct(v) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return `${Math.round(n * 100)}%`;
}

function tipoEditor(item, i) {
  const tipoVal = humanOr(item, "tipo", item.tipo);
  const btn = (value, label, onCls, offCls) => {
    const on = tipoVal === value;
    return `<button type="button" data-jev-label="tipo" data-jev-i="${i}" data-value="${value}"
      class="chip ${on ? onCls : offCls}">${label}</button>`;
  };
  return `<div class="flex gap-1">${btn("artigo-completo", t("tipoCompleto"), "bg-amber-50 text-amber-800", "bg-white text-slate-500 border border-slate-200")}
    ${btn("resumo", t("tipoResumo"), "bg-slate-200 text-slate-700", "bg-white text-slate-500 border border-slate-200")}</div>`;
}

const TEMA_PILL = {
  política: "bg-violet-50 text-violet-800",
  saúde: "bg-rose-50 text-rose-800",
  economia: "bg-emerald-50 text-emerald-800",
  tecnologia: "bg-sky-50 text-sky-800",
  mundo: "bg-indigo-50 text-indigo-800",
  brasil: "bg-yellow-50 text-yellow-800",
  cultura: "bg-fuchsia-50 text-fuchsia-800",
  esportes: "bg-orange-50 text-orange-800",
  ciência: "bg-cyan-50 text-cyan-800",
  opinião: "bg-slate-100 text-slate-700",
  clima: "bg-lime-50 text-lime-800",
};

function shownTemas(item) {
  if (item.human && Array.isArray(item.human.temas)) return item.human.temas;
  return item.temas || [];
}

function themeLabel(themeId, run) {
  const catalog = run?.themes || jevOpenRun?.themes || [];
  const row = catalog.find((th) => th.id === themeId);
  if (!row) return themeId;
  return uiLangCode === "pt" ? row.label_pt || row.id : row.label_en || row.id;
}

function temaScoresMap(item) {
  const fromHuman = item.human?.temas;
  if (fromHuman && typeof fromHuman === "object" && !Array.isArray(fromHuman)) {
    return fromHuman;
  }
  return item.jev?.answers?.temas || {};
}

function compactTemasCell(item) {
  const ids = shownTemas(item);
  if (!ids.length) return '<span class="text-xs text-slate-300">—</span>';
  return `<div class="flex flex-wrap gap-1">${ids
    .map((id) => {
      const cls = TEMA_PILL[id] || "bg-slate-100 text-slate-600";
      return `<span class="inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${cls}">${esc(themeLabel(id, jevOpenRun))}</span>`;
    })
    .join("")}</div>`;
}

function temaEditor(item, i) {
  const on = new Set(shownTemas(item));
  const catalog = (jevOpenRun?.themes || []).filter((th) => th.enabled);
  const ids = catalog.length ? catalog.map((th) => th.id) : Object.keys(TEMA_PILL);
  return `<div class="flex flex-wrap gap-1 mt-2">${ids
    .map((tid) => {
      const active = on.has(tid);
      const cls = active ? TEMA_PILL[tid] : "bg-white text-slate-300 border border-slate-200";
      const label = themeLabel(tid, jevOpenRun);
      return `<button type="button" data-jev-label="tema" data-jev-i="${i}" data-value="${esc(tid)}"
        class="chip ${cls}">${esc(label)}</button>`;
    })
    .join("")}</div>`;
}

function themeScoresSidebar(item) {
  const scores = temaScoresMap(item);
  const catalog = (jevOpenRun?.themes || []).filter((th) => th.enabled);
  const rows = [];
  for (const th of catalog) {
    const raw = scores[th.id];
    if (raw == null || raw === "") continue;
    const p = Math.round(Number(raw) * 100);
    if (Number.isNaN(p)) continue;
    rows.push(`<div class="mb-1.5">
      <div class="flex items-baseline justify-between gap-2 text-[10px] uppercase tracking-wide text-slate-500">
        <span>${esc(themeLabel(th.id, jevOpenRun))}</span>
        <span class="tabular-nums text-slate-600">${p}%</span>
      </div>
      <div class="flex mt-0.5">${extraScoreVizBar(p, false)}</div>
    </div>`);
  }
  if (!rows.length) return "";
  return `<div class="mt-3 pt-3 border-t border-slate-100">${rows.join("")}</div>`;
}

function humanOr(item, key, fallback) {
  if (item.human && item.human[key] != null) return item.human[key];
  return fallback;
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt"));
}

function adVal(item) {
  return Number(humanOr(item, "ad", item.jev?.answers?.ad));
}

function filteredJevItems() {
  const items = (jevOpenRun?.items || []).map((item, i) => ({ item, i }));
  const f = jevFilter;
  const q = f.q.trim().toLowerCase();
  return items.filter(({ item }) => {
    if (q) {
      const hay = `${item.title || ""} ${item.source || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (f.source && item.source !== f.source) return false;
    if (f.tipo && humanOr(item, "tipo", item.tipo) !== f.tipo) return false;
    if (f.tema && !shownTemas(item).includes(f.tema)) return false;
    if (f.skip === "kept" && item.skip) return false;
    if (f.skip === "skipped" && !item.skip) return false;
    if (f.skip === "error" && !item.error) return false;
    return true;
  });
}

function groupKey(item) {
  if (jevFilter.group === "source") return item.source || "(no source)";
  if (jevFilter.group === "tipo") return item.tipo || "(no tipo)";
  if (jevFilter.group === "tema") return (item.temas && item.temas[0]) || "(no tema)";
  if (jevFilter.group === "skip") {
    if (item.error) return "error";
    return item.skip ? `skipped:${item.skip_reason || "skip"}` : "kept";
  }
  return "";
}

function skipSortVal(item) {
  if (item.error) return item.error;
  if (item.skip) return item.skip_reason || "skip";
  return "";
}

function sortValue(item, key) {
  if (key === "story") return (item.title || "").toLowerCase();
  if (key === "temas") return shownTemas(item).join(" ").toLowerCase();
  if (key === "tipo") return humanOr(item, "tipo", item.tipo) || "";
  if (key === "rel") return Number(humanOr(item, "relevance", item.relevance)) || 0;
  if (key === "ad") {
    const n = adVal(item);
    return Number.isNaN(n) ? -1 : n;
  }
  if (key === "skip") return skipSortVal(item).toLowerCase();
  return 0;
}

function sortedJevRows(rows) {
  const key = jevSort.key;
  if (!key) return rows;
  const dir = jevSort.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = sortValue(a.item, key);
    const vb = sortValue(b.item, key);
    let cmp = 0;
    if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
    else cmp = String(va).localeCompare(String(vb), "pt");
    if (cmp === 0) return a.i - b.i;
    return cmp * dir;
  });
}

function jevRowHtml(item, i) {
  const title = esc(item.title || "(no title)");
  const href = item.url ? esc(item.url) : "";
  const titleHtml = href
    ? `<a class="text-slate-900 hover:underline" href="${href}" target="_blank" rel="noopener">${title}</a>`
    : title;
  const selected = i === jevSelectedIndex ? "bg-slate-50" : "";
  const rel = humanOr(item, "relevance", item.relevance);
  const ad = adVal(item);
  const adPct = Number.isNaN(ad) ? null : ad * 100;
  return `<tr data-jev-i="${i}" class="border-b border-slate-100 cursor-pointer hover:bg-slate-50 ${selected}">
    <td class="py-3 pr-4 pl-4">
      <div class="text-sm leading-snug">${titleHtml}</div>
      <div class="text-xs text-slate-500 mt-0.5">${esc(item.source || "")}</div>
    </td>
    <td class="py-3 px-2">${compactTemasCell(item)}</td>
    <td class="py-3 px-2 whitespace-nowrap">${tipoEditor(item, i)}</td>
    <td class="py-3 px-2">${pctBar(rel)}</td>
    <td class="py-3 px-2">${pctBar(adPct, { warn: true })}</td>
    <td class="py-3 pl-2 pr-4">${skipCell(item)}</td>
  </tr>`;
}

function paintJevSortHeaders() {
  $$("#jev-run-detail [data-jev-sort]").forEach((th) => {
    const on = th.dataset.jevSort === jevSort.key;
    const mark = on ? (jevSort.dir === "asc" ? " ↑" : " ↓") : "";
    const label = th.dataset.jevLabel;
    th.textContent = label + mark;
    th.classList.toggle("text-slate-700", on);
    th.classList.toggle("text-slate-500", !on);
  });
}

function groupHeaderHtml(key, members) {
  const collapsed = jevCollapsed.has(key);
  const chev = collapsed ? "▸" : "▾";
  return `<tr data-jev-group="${esc(key)}" class="cursor-pointer select-none bg-slate-100 hover:bg-slate-200/80 border-y-2 border-slate-200">
    <td colspan="6" class="px-4 py-5">
      <span class="inline-flex items-center gap-2 text-sm font-semibold tracking-wide text-slate-700">
        <span class="w-4 text-slate-500">${chev}</span>
        ${esc(groupDisplayLabel(key))}
        <span class="rounded-md bg-white px-2 py-0.5 text-xs font-medium text-slate-500">${members.length}</span>
      </span>
    </td>
  </tr>`;
}

function paintJevRows() {
  const tbody = $("#jev-tbody");
  const countEl = $("#jev-filter-count");
  if (!tbody || !jevOpenRun) return;
  const rows = sortedJevRows(filteredJevItems());
  const total = (jevOpenRun.items || []).length;
  if (countEl) countEl.textContent = t("showingCount", { n: rows.length, total });
  if (jevFilter.group === "none") {
    tbody.innerHTML = rows.map(({ item, i }) => jevRowHtml(item, i)).join("");
    paintJevSortHeaders();
    return;
  }
  const groups = new Map();
  for (const row of rows) {
    const key = groupKey(row.item);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  const keys = [...groups.keys()].sort((a, b) => a.localeCompare(b, "pt"));
  tbody.innerHTML = keys
    .map((key) => {
      const members = groups.get(key);
      const header = groupHeaderHtml(key, members);
      if (jevCollapsed.has(key)) return header;
      return header + members.map(({ item, i }) => jevRowHtml(item, i)).join("");
    })
    .join("");
  paintJevSortHeaders();
}

function readJevFilters() {
  const val = (id) => $(id)?.value ?? "";
  const nextGroup = val("#jev-group") || "none";
  if (nextGroup !== jevFilter.group) jevCollapsed = new Set();
  jevFilter.q = val("#jev-q");
  jevFilter.source = val("#jev-source");
  jevFilter.tipo = val("#jev-tipo");
  jevFilter.tema = val("#jev-tema");
  jevFilter.skip = val("#jev-skip");
  jevFilter.group = val("#jev-group") || "none";
  paintJevRows();
}

function skipCell(item) {
  if (item.error) {
    return `<span class="text-xs font-medium text-red-600">${esc(item.error)}</span>`;
  }
  if (item.skip) {
    return `<span class="text-xs font-medium text-slate-500">${esc(item.skip_reason || "skip")}</span>`;
  }
  return '<span class="text-xs text-slate-300">—</span>';
}

function renderJevRunList(runs) {
  const root = $("#jev-run-list");
  root.className = "flex flex-wrap gap-2 mb-4";
  root.innerHTML = "";
  for (const run of runs) {
    const row = document.createElement("button");
    row.type = "button";
    row.className =
      "rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 shadow-sm hover:border-slate-300";
    const when = formatJevWhen(run.started_at) || esc(run.id);
    row.innerHTML = `<span class="block font-medium text-slate-800">${esc(when)}</span>
      <span class="block text-xs text-slate-500">${run.article_count} ${t("stories").toLowerCase()} · ${run.skipped} ${t("skipped").toLowerCase()}</span>`;
    row.onclick = () => loadJevRun(run.id);
    root.appendChild(row);
  }
}

async function loadJevRun(runId) {
  const status = $("#jev-status");
  setStatus(status, t("loadingRun", { runId }), true);
  try {
    const run = await api(`/api/jev/runs/${encodeURIComponent(runId)}`);
    jevSelectedIndex = -1;
    jevFilter = defaultJevFilter();
    jevSort = { key: null, dir: "desc" };
    jevCollapsed = new Set();
    renderJevRunDetail(run);
    const when = formatJevWhen(run.started_at) || run.id;
    setStatus(status, `${run.article_count} ${t("stories").toLowerCase()} · ${when}`, true);
  } catch (e) {
    $("#jev-run-detail").innerHTML = "";
    setStatus(status, e.message, false);
  }
}

function jevTokenTotals(run) {
  let inn = 0;
  let out = 0;
  for (const item of run.items || []) {
    const u = item.jev?.answers?.usage;
    if (!u) continue;
    inn += Number(u.input_tokens) || 0;
    out += Number(u.output_tokens) || 0;
  }
  return { inn, out };
}

function optionList(values, emptyLabel) {
  return [`<option value="">${emptyLabel}</option>`]
    .concat(values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`))
    .join("");
}

function themeFilterOptions(ids, run) {
  return [`<option value="">${esc(t("allThemes"))}</option>`]
    .concat(
      ids.map(
        (id) =>
          `<option value="${esc(id)}">${esc(themeLabel(id, run))}</option>`,
      ),
    )
    .join("");
}

function groupDisplayLabel(key) {
  if (jevFilter.group === "tema") return themeLabel(key, jevOpenRun);
  if (jevFilter.group === "tipo") {
    if (key === "artigo-completo") return t("tipoCompleto");
    if (key === "resumo") return t("tipoResumo");
  }
  return key;
}

function renderJevRunDetail(run) {
  jevOpenRun = run;
  const root = $("#jev-run-detail");
  const items = run.items || [];
  const tokens = jevTokenTotals(run);
  const sources = uniqueSorted(items.map((it) => it.source));
  const temas = uniqueSorted(items.flatMap((it) => it.temas || []));
  const runWhen = formatJevWhen(run.started_at) || esc(run.id);
  const statusLabel = run.errors ? `${run.errors} ${t("failed")}` : t("complete");

  root.innerHTML = `
    <div class="jev-run-header flex flex-wrap items-center justify-between gap-2 mb-3 px-1">
      <h2 class="text-base font-semibold text-slate-800 m-0">${esc(runWhen)}</h2>
      <span class="text-xs text-slate-500">${run.article_count} ${t("stories").toLowerCase()}</span>
    </div>
    <div class="flex flex-col lg:flex-row gap-6 items-start">
      <div class="flex-1 min-w-0 bg-white rounded-xl border border-slate-200">
        <div class="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2 p-3 border-b border-slate-100">
          <input id="jev-q" aria-label="${esc(t("searchPlaceholder"))}" type="search" placeholder="${esc(t("searchPlaceholder"))}" class="col-span-2 rounded-md border border-slate-200 px-2 py-1.5 text-xs">
          <select id="jev-source" aria-label="${esc(t("allSources"))}" class="rounded-md border border-slate-200 px-2 py-1.5 text-xs">${optionList(sources, t("allSources"))}</select>
          <select id="jev-tipo" aria-label="${esc(t("allTypes"))}" class="rounded-md border border-slate-200 px-2 py-1.5 text-xs">
            <option value="">${esc(t("allTypes"))}</option>
            <option value="artigo-completo">${esc(t("tipoCompleto"))}</option>
            <option value="resumo">${esc(t("tipoResumo"))}</option>
          </select>
          <select id="jev-tema" aria-label="${esc(t("allThemes"))}" class="rounded-md border border-slate-200 px-2 py-1.5 text-xs">${themeFilterOptions(temas, run)}</select>
          <select id="jev-skip" aria-label="${esc(t("keptAndSkipped"))}" class="rounded-md border border-slate-200 px-2 py-1.5 text-xs">
            <option value="">${esc(t("keptAndSkipped"))}</option>
            <option value="kept">${esc(t("keptOnly"))}</option>
            <option value="skipped">${esc(t("skippedOnly"))}</option>
            <option value="error">${esc(t("errorsOnly"))}</option>
          </select>
          <select id="jev-group" aria-label="${esc(t("groupNone"))}" class="rounded-md border border-slate-200 px-2 py-1.5 text-xs">
            <option value="none">${esc(t("groupNone"))}</option>
            <option value="source">${esc(t("groupSource"))}</option>
            <option value="tipo">${esc(t("groupType"))}</option>
            <option value="tema">${esc(t("groupTheme"))}</option>
            <option value="skip">${esc(t("groupSkip"))}</option>
          </select>
          <p id="jev-filter-count" class="col-span-2 xl:col-span-6 self-end text-xs text-slate-500 m-0"></p>
        </div>
        <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs font-medium text-slate-500 border-b border-slate-200">
              <th data-jev-sort="story" data-jev-label="${esc(t("story"))}" class="py-2.5 px-4 font-medium cursor-pointer select-none hover:text-slate-700">${esc(t("story"))}</th>
              <th data-jev-sort="temas" data-jev-label="${esc(t("themes"))}" class="py-2.5 px-2 font-medium cursor-pointer select-none hover:text-slate-700">${esc(t("themes"))}</th>
              <th data-jev-sort="tipo" data-jev-label="${esc(t("type"))}" class="py-2.5 px-2 font-medium cursor-pointer select-none hover:text-slate-700">${esc(t("type"))}</th>
              <th data-jev-sort="rel" data-jev-label="${esc(t("rel"))}" class="py-2.5 px-2 font-medium cursor-pointer select-none hover:text-slate-700">${esc(t("rel"))}</th>
              <th data-jev-sort="ad" data-jev-label="${esc(t("ad"))}" class="py-2.5 px-2 font-medium cursor-pointer select-none hover:text-slate-700">${esc(t("ad"))}</th>
              <th data-jev-sort="skip" data-jev-label="${esc(t("skip"))}" class="py-2.5 px-4 font-medium cursor-pointer select-none hover:text-slate-700">${esc(t("skip"))}</th>
            </tr>
          </thead>
          <tbody id="jev-tbody"></tbody>
        </table>
        </div>
      </div>
      <aside class="w-full lg:w-80 shrink-0 rounded-xl border border-slate-200 bg-white p-4 sticky top-4">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-slate-800 m-0">${esc(t("run"))}</h2>
          <span class="text-xs text-emerald-700">${esc(statusLabel)}</span>
        </div>
        <p class="text-[11px] text-slate-500 break-all mb-3">${esc(run.path || "")}</p>
        <div class="grid grid-cols-2 gap-y-2 text-sm mb-3">
          <span class="text-slate-500">${esc(t("stories"))}</span><span class="text-right font-medium">${run.article_count}</span>
          <span class="text-slate-500">${esc(t("skipped"))}</span><span class="text-right font-medium">${run.skipped}</span>
          <span class="text-slate-500">${esc(t("workers"))}</span><span class="text-right font-medium">${run.workers ?? "—"}</span>
          <span class="text-slate-500">${esc(t("minRelevance"))}</span><span class="text-right font-medium">${run.min_relevance ?? run.min_keep ?? 0}</span>
        </div>
        <div class="grid grid-cols-2 gap-y-1 text-sm mb-4">
          <span class="text-slate-500">${esc(t("tokensIn"))}</span><span class="text-right">${tokens.inn.toLocaleString()}</span>
          <span class="text-slate-500">${esc(t("tokensOut"))}</span><span class="text-right">${tokens.out.toLocaleString()}</span>
        </div>
        <pre id="jev-json" class="text-[11px] leading-snug text-slate-600 bg-slate-50 rounded-lg p-3 max-h-64 overflow-auto whitespace-pre-wrap m-0">${esc(t("clickRowJson"))}</pre>
        <div id="jev-extra-labels" class="mt-3 hidden"></div>
      </aside>
    </div>`;

  ["#jev-q", "#jev-source", "#jev-tipo", "#jev-tema", "#jev-skip", "#jev-group"].forEach((id) => {
    $(id)?.addEventListener("input", readJevFilters);
    $(id)?.addEventListener("change", readJevFilters);
  });
  paintJevRows();
  root.oninput = (ev) => {
    const el = ev.target.closest("#jev-extra-labels [data-jev-label]");
    if (!el || el.tagName !== "INPUT") return;
    const bar = el.parentElement?.querySelector("[data-jev-viz]");
    if (!bar) return;
    const p = Math.max(0, Math.min(100, Number(el.value) || 0));
    bar.style.width = `${p}%`;
  };
  root.onchange = (ev) => {
    const el = ev.target.closest("[data-jev-label]");
    if (!el || el.tagName !== "INPUT") return;
    const index = Number(el.dataset.jevI);
    const field = el.dataset.jevLabel;
    let raw = Number(el.value);
    if (Number.isNaN(raw)) raw = 0;
    raw = Math.max(0, Math.min(100, raw));
    el.value = String(raw);
    const patch = field === "relevance" ? { relevance: raw } : { [field]: raw / 100 };
    persistJevLabel(index, patch).catch((e) => setStatus($("#jev-status"), e.message, false));
  };

  root.onclick = (ev) => {
    const labelEl = ev.target.closest("[data-jev-label]");
    if (labelEl && labelEl.tagName === "BUTTON") {
      ev.preventDefault();
      const index = Number(labelEl.dataset.jevI);
      const item = jevOpenRun.items[index];
      const field = labelEl.dataset.jevLabel;
      if (field === "tipo") {
        persistJevLabel(index, { tipo: labelEl.dataset.value }).catch((e) => setStatus($("#jev-status"), e.message, false));
        return;
      }
      if (field === "tema") {
        const temaId = labelEl.dataset.value;
        const current = new Set(shownTemas(item));
        if (current.has(temaId)) current.delete(temaId);
        else current.add(temaId);
        persistJevLabel(index, { temas: [...current] }).catch((e) => setStatus($("#jev-status"), e.message, false));
      }
      return;
    }
    if (ev.target.closest("[data-stop-row], [data-jev-label]")) return;
    const group = ev.target.closest("[data-jev-group]");
    if (group) {
      const key = group.dataset.jevGroup;
      if (jevCollapsed.has(key)) jevCollapsed.delete(key);
      else jevCollapsed.add(key);
      paintJevRows();
      return;
    }
    const th = ev.target.closest("[data-jev-sort]");
    if (th) {
      const key = th.dataset.jevSort;
      if (jevSort.key === key) {
        jevSort.dir = jevSort.dir === "asc" ? "desc" : "asc";
      } else {
        jevSort.key = key;
        jevSort.dir = key === "story" || key === "temas" || key === "tipo" || key === "skip" ? "asc" : "desc";
      }
      paintJevRows();
      return;
    }
    const tr = ev.target.closest("[data-jev-i]");
    if (!tr || !jevOpenRun) return;
    if (ev.target.closest("a")) return;
    jevSelectedIndex = Number(tr.dataset.jevI);
    const item = jevOpenRun.items[jevSelectedIndex];
    showJevJson(item);
    root.querySelectorAll("[data-jev-i]").forEach((row) => {
      row.classList.toggle("bg-slate-50", row === tr);
    });
  };
}

function showJevJson(item) {
  const pre = $("#jev-json");
  if (pre) pre.textContent = JSON.stringify(item, null, 2);
  paintExtraLabels(item);
}

function extraScoreVizBar(pct, warn) {
  const p = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
  const fill = warn && p >= 40 ? "bg-rose-500" : "bg-emerald-500";
  return `<span class="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-100">
    <span data-jev-viz class="block h-full ${fill}" style="width:${p}%"></span>
  </span>`;
}

function extraScoreRow(i, key, label, pct, warn) {
  const p = Math.max(0, Math.min(100, Math.round(Number(pct) || 0)));
  return `<label class="mb-2 flex flex-col gap-0.5 text-[10px] uppercase tracking-wide text-slate-500">${esc(label)}
    <span class="flex items-center gap-2">
      <input type="number" min="0" max="100" step="1" value="${p}"
        data-jev-label="${esc(key)}" data-jev-i="${i}"
        class="w-14 rounded-md border border-slate-200 px-1.5 py-0.5 text-xs tabular-nums text-slate-700">
      ${extraScoreVizBar(p, warn)}
    </span>
  </label>`;
}

function extraNoulRow(item, i, key, label, warn) {
  const frac = humanOr(item, key, item.jev?.answers?.[key]);
  const p = frac == null || frac === "" ? 0 : Number(frac) * 100;
  return extraScoreRow(i, key, label, p, warn);
}

function paintExtraLabels(item) {
  const box = $("#jev-extra-labels");
  if (!box || !jevOpenRun) return;
  const i = jevSelectedIndex;
  if (i < 0) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  const rel = humanOr(item, "relevance", item.relevance);
  const ad = adVal(item);
  const adP = Number.isNaN(ad) ? 0 : ad * 100;
  box.innerHTML = `<p class="text-xs font-medium text-slate-600 mb-2">${esc(t("correctScores"))}</p>
    ${extraScoreRow(i, "relevance", t("rel"), rel, false)}
    ${extraScoreRow(i, "ad", t("ad"), adP, true)}
    ${extraNoulRow(item, i, "clickbait", "Clickbait")}
    ${extraNoulRow(item, i, "press_release", "Press release")}
    ${extraNoulRow(item, i, "paywall_teaser", "Paywall teaser")}
    ${themeScoresSidebar(item)}
    ${temaEditor(item, i)}`;
}

async function persistJevLabel(index, patch) {
  if (!jevOpenRun) return;
  const res = await api("/api/jev/labels", {
    method: "POST",
    body: JSON.stringify({ run_id: jevOpenRun.id, index, ...patch }),
  });
  const item = jevOpenRun.items[index];
  item.human = { ...(item.human || {}), ...(res.human || {}) };
  paintJevRows();
  if (index === jevSelectedIndex) showJevJson(item);
}

$("#refresh-jev").onclick = loadJevRuns;

$("#export-jev-labels").onclick = async () => {
  const status = $("#jev-status");
  try {
    const data = await api("/api/jev/labels/export");
    const blob = new Blob([JSON.stringify(data.rows, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "jev-labels.json";
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(status, t("exportedLabels", { n: data.rows.length }), true);
  } catch (e) {
    setStatus(status, e.message, false);
  }
};

$$("#ui-lang-switch [data-ui-lang]").forEach((btn) => {
  btn.addEventListener("click", () => setUiLang(btn.dataset.uiLang, { persist: true }));
});

loadSettings().then(refreshSources).catch((e) => {
  setStatus($("#settings-status"), e.message, false);
});

$("#run-digest")?.addEventListener("click", startDigest);
refreshDigestProgress().catch(() => {});

const tokenInput = $("#dashboard-token");
if (tokenInput) {
  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) tokenInput.value = saved;
  tokenInput.addEventListener("change", () => {
    const v = tokenInput.value.trim();
    if (v) localStorage.setItem(TOKEN_KEY, v);
    else localStorage.removeItem(TOKEN_KEY);
    paintTokenSummary();
  });
}
paintTokenSummary();
if (!dashboardToken()) $("#token-menu")?.setAttribute("open", "");
