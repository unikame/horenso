"""報連相AI 管理画面（Streamlit）

ページ
- 管理画面（/）     … 担当役員ごと・クライアントごとに、案件（要確認・フォロー・Good）を表示
- 報連相チェック（/survey） … Googleフォームの回答の集計

データは Python（サービスアカウント）でスプレッドシートから読み、画面（horenso/*.html）に埋め込む。
画面の中の切り替え（タブ・絞り込み・週と月など）はブラウザ側で動く。

起動： streamlit run app.py
"""
import html as _html
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from horenso import config, sheets

HERE = Path(__file__).parent / "horenso"

st.set_page_config(page_title="報連相AI 管理画面", page_icon=":material/space_dashboard:", layout="wide", initial_sidebar_state="collapsed")

# Streamlit 標準の飾り（上部のバー・余白・サイドバー）を消して、画面だけを全面に出す
st.html("""<style>
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], #MainMenu, footer { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: none !important; }
[data-testid="stMainBlockContainer"] > div { gap: 0 !important; }
iframe { display: block; border: 0; }
</style>""")


def js(obj) -> str:
    """<script> の中に安全に埋め込める JSON にする。"""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def table(values) -> list[dict]:
    """1行目を見出しにした行の一覧（空行は除く）。"""
    if not values:
        return []
    head = [str(h).strip() for h in values[0]]
    out = []
    for r in values[1:]:
        r = list(r) + [""] * (len(head) - len(r))
        if any(str(c).strip() for c in r):
            out.append({h: str(r[i]) for i, h in enumerate(head) if h})
    return out


def load_or_none(kind: str):
    try:
        return sheets.load(kind)
    except sheets.SheetError:
        return None


def nav_items(pages: list[dict]) -> list[tuple[str, str]]:
    persons = [p["ページ名"] for p in pages if p.get("種類") == "人" and p.get("ページ名")]
    return [("home", "ホーム")] + [("p:" + p, p) for p in persons] + [("client", "クライアント"), ("survey", "報連相チェック")]


def appbar(items, active: str) -> str:
    t = sheets.loaded_at()
    stamp = f"最終読み込み {t.month}/{t.day} {t:%H:%M}" if t else ""
    tabs = "".join(
        f'<a href="#" data-nav="{_html.escape(k)}"{" aria-current=\"page\"" if k == active else ""}>{_html.escape(label)}</a>'
        for k, label in items)
    return (f'<header class="appbar"><div class="appbar-in"><div class="brand"><h1>報連相AI 管理画面</h1>'
            f'<div class="meta"><span>{stamp}</span><a class="btn" href="#" data-reload>最新を読み込む</a>'
            f'<a class="btn" href="https://docs.google.com/spreadsheets/d/{config.get("LEDGER_ID")}/edit" target="_blank" rel="noopener">管理台帳</a></div></div>'
            f'<nav class="tabs" aria-label="画面の切り替え">{tabs}</nav></div></header>')


# 画面の中のタブ・「最新を読み込む」の動き（親ページのURLを切り替える）
NAV_JS = """<script>
(function(){
  function parentUrl(){ try { return new URL(window.parent.location.href); } catch (e) { return null; } }
  function goParent(tab, reload){
    var u = parentUrl(); if (!u) { location.reload(); return; }
    var base = u.pathname.replace(/\\/survey\\/?$/, "/");
    if (tab === "survey") { u.pathname = base.replace(/\\/$/, "") + "/survey"; u.search = ""; }
    else if (tab) { u.pathname = base; u.search = "?tab=" + encodeURIComponent(tab); }
    if (reload) u.searchParams.set("reload", "1");
    window.parent.location.href = u.toString();
  }
  document.querySelectorAll("[data-nav]").forEach(function(a){
    a.addEventListener("click", function(e){
      e.preventDefault();
      var t = a.getAttribute("data-nav");
      if (window.__localNav && window.__localNav(t)) return;
      goParent(t, false);
    });
  });
  document.querySelectorAll("[data-reload]").forEach(function(a){
    a.addEventListener("click", function(e){ e.preventDefault(); goParent(null, true); });
  });
})();
</script>"""


def show_error(e: Exception):
    with st.container(border=True):
        st.error(str(e), icon=":material/error:")


def base_css() -> str:
    page = (HERE / "dashboard.html").read_text(encoding="utf-8")
    return page.split("<style>", 1)[1].split("</style>", 1)[0]


def admin_page():
    try:
        cases = table(sheets.load("cases"))
        links = table(sheets.load("links"))
        pages = table(sheets.load("pages"))
        clients = table(sheets.load("clients"))
        logs = table(load_or_none("caselog") or [])
    except sheets.SheetError as e:
        show_error(e)
        st.stop()
    tab = st.query_params.get("tab", "home")
    page = (HERE / "admin.html").read_text(encoding="utf-8")
    page = (page.replace("/*__BASE_CSS__*/", base_css())
                .replace("__APPBAR__", appbar(nav_items(pages), tab if not tab.startswith("c:") else "client"))
                .replace("__NAV_JS__", NAV_JS)
                .replace("__CASES__", js(cases)).replace("__LOGS__", js(logs)).replace("__LINKS__", js(links))
                .replace("__PAGES__", js(pages)).replace("__CLIENTS__", js(clients))
                .replace("__TAB__", js(tab))
                .replace("__LEDGER_URL__", js(f"https://docs.google.com/spreadsheets/d/{config.get('LEDGER_ID')}/edit")))
    components.html(page, height=900, scrolling=False)


def survey_page():
    try:
        values = sheets.load("survey")
    except sheets.SheetError as e:
        show_error(e)
        st.stop()
    settings = load_or_none("settings") or []          # 対象人数・回答率の目標（なくても動く）
    pages = table(load_or_none("pages") or [])         # タブの並び（読めなければ最小限）
    page = (HERE / "dashboard.html").read_text(encoding="utf-8")
    page = (page.replace("__APPBAR__", appbar(nav_items(pages), "survey"))
                .replace("__NAV_JS__", NAV_JS)
                .replace("__VALUES__", js(values))
                .replace("__SETTINGS__", js(settings))
                .replace("__SHEET_URL__", f"https://docs.google.com/spreadsheets/d/{config.get('SURVEY_ID')}/edit"))
    components.html(page, height=900, scrolling=False)


# 「最新を読み込む」から ?reload=1 付きで開かれたら、読み込み済みの内容を捨てて読み直す
if st.query_params.get("reload"):
    sheets.reload_all()
    del st.query_params["reload"]

pg = st.navigation([
    st.Page(admin_page, title="報連相AI 管理画面", url_path="", default=True),
    st.Page(survey_page, title="報連相チェック集計", url_path="survey"),
], position="hidden")
pg.run()
