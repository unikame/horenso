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
    return [("home", "ホーム")] + [("p:" + p, p) for p in persons] + [("client", "クライアント"), ("settings", "配信設定"), ("survey", "報連相チェック")]


def appbar(items, active: str) -> str:
    t = sheets.loaded_at()
    stamp = f"最終読み込み {t.month}/{t.day} {t:%H:%M}" if t else ""
    def tab(k, label):
        if k == "survey" and config.get("SURVEY_APP_URL"):      # 報連相チェックは集計アプリへ移動
            return f'<a href="{_html.escape(config.get("SURVEY_APP_URL"))}" data-ext>{_html.escape(label)}</a>'
        return f'<a href="#" data-nav="{_html.escape(k)}"{" aria-current=\"page\"" if k == active else ""}>{_html.escape(label)}</a>'
    tabs = "".join(tab(k, label) for k, label in items)
    return (f'<header class="appbar"><div class="appbar-in"><div class="brand"><h1>報連相AI 管理画面</h1>'
            f'<div class="meta"><span>{stamp}</span><a class="btn" href="#" data-reload>最新を読み込む</a>'
            f'<a class="btn" href="https://docs.google.com/spreadsheets/d/{config.get("LEDGER_ID")}/edit" target="_blank" rel="noopener">管理台帳</a></div></div>'
            f'<nav class="tabs" aria-label="画面の切り替え">{tabs}</nav></div></header>')


# 画面の中のタブ・「最新を読み込む」の動き（親ページのURLを切り替える）
NAV_JS = """<script>
(function(){
  function parentUrl(){ try { return new URL(window.parent.location.href); } catch (e) { return null; } }
  // 画面全体を移動する。この枠（iframe）からは直接移動できないため、親ページにリンクを作って押す
  function topNav(url){
    try {
      var d = window.parent.document, a = d.createElement("a");
      a.href = url; a.target = "_self"; a.style.display = "none";
      d.body.appendChild(a); a.click(); a.remove();
    } catch (e) { window.open(url, "_blank", "noopener"); }
  }
  function goParent(tab, reload){
    var u = parentUrl(); if (!u) { location.reload(); return; }
    var base = u.pathname.replace(/\\/(survey|settings)\\/?$/, "/");
    if (tab === "survey") { u.pathname = base.replace(/\\/$/, "") + "/survey"; u.search = ""; }
    else if (tab) { u.pathname = base; u.search = "?tab=" + encodeURIComponent(tab); }
    if (reload) u.searchParams.set("reload", "1");
    topNav(u.toString());
  }
  document.querySelectorAll("[data-nav]").forEach(function(a){
    a.addEventListener("click", function(e){
      e.preventDefault();
      var t = a.getAttribute("data-nav");
      if (window.__localNav && window.__localNav(t)) return;
      goParent(t, false);
    });
  });
  // 別のアプリへ移動する。Streamlit Cloud ではアプリ自体が枠の中で動いているため、いちばん外側の画面ごと切り替える。
  // 外側に触れない場合は、新しいタブで開く
  function openExternal(url){
    try {
      var d = window.top.document, a = d.createElement("a");
      a.href = url; a.target = "_top"; a.rel = "noopener"; a.style.display = "none";
      d.body.appendChild(a); a.click(); a.remove();
    } catch (e) { window.open(url, "_blank", "noopener"); }
  }
  document.querySelectorAll("[data-ext]").forEach(function(a){
    a.addEventListener("click", function(e){ e.preventDefault(); openExternal(a.href); });
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
    if tab == "settings":            # 配信設定（URL は /?tab=settings。Streamlit Cloud の非公開アプリでは /settings のような下の階層が開けないことがあるため）
        settings_page()
        return
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


# ---------------- 配信設定（役員ごとに、毎朝の個別配信で受け取るスペースを選ぶ） ----------------
DELIVERY_COLS = {"spaces": "受け取るスペース（スペースID・読点区切り）", "mode": "届け方", "on": "配信",
                 "dm": "DMスペース（自動）", "added": "アプリ追加日（自動）"}

SETTINGS_CSS = """<style>
[data-testid="stMainBlockContainer"] { padding: 0 0 48px !important; }
.st-key-settings { max-width: 860px; margin: 0 auto; padding: 24px 16px 0; }
.st-key-settings h2 { font-size: 22px; margin: 0 0 4px; }
.hs-lead { color: #5b6472; font-size: 14px; margin: 0 0 18px; }
.hs-ok { color: #1f7a3f; font-weight: 600; } .hs-ng { color: #b42318; font-weight: 600; }
</style>"""


def viewer_email() -> str:
    """Streamlit Community Cloud にログインして見ている人のメールアドレス（分からなければ空）。"""
    try:
        return str(st.user.get("email") or "").strip().lower()
    except Exception:
        return ""


def space_choices() -> list[dict]:
    """選べるスペース：紐づけ・案件・LINEグループに出てくるもの（スペースIDで重複を除く）。"""
    out, seen = [], set()

    def add(sid, name, group):
        sid, name = str(sid or "").strip(), str(name or "").strip()
        if not sid or sid in seen or not (sid.startswith("spaces/") or sid.startswith("line:")):
            return
        seen.add(sid)
        out.append({"id": sid, "name": name or sid, "group": group})
    for pair in str(config.get("EXTRA_SPACES") or "").split("、"):
        if "=" in pair:
            add(pair.split("=", 1)[0], pair.split("=", 1)[1], "社内のチャット")
    for r in table(load_or_none("links") or []):
        add(r.get("スペースID（自動）"), r.get("スペース名"),
            "クライアントのチャット" if r.get("種類") == "クライアント" else "社内のチャット")
    for r in table(load_or_none("cases") or []):
        add(r.get("スペースID"), r.get("スペース"), "社内のチャット")
    for r in table(load_or_none("linegroups") or []):
        if r.get("グループID"):
            add("line:" + r["グループID"], "LINE：" + (r.get("グループ名") or r["グループID"][-6:]), "LINE グループ")
    order = {"社内のチャット": 0, "クライアントのチャット": 1, "LINE グループ": 2}
    return sorted(out, key=lambda x: order.get(x["group"], 9))


def settings_page():
    try:
        rows = table(sheets.load("delivery"))
    except sheets.SheetError as e:
        show_error(e)
        st.stop()
    pages = table(load_or_none("pages") or [])
    components.html(base_page_shell(appbar(nav_items(pages), "settings")), height=118, scrolling=False)
    st.html(SETTINGS_CSS)
    with st.container(key="settings"):
        st.markdown("## 配信設定")
        st.html('<p class="hs-lead">毎朝、チャットアプリ「報連相AI」から1対1のメッセージで届く要約の受け取り方を選びます。</p>')
        if not rows:
            st.info("「報連相AI 配信設定」に役員の行がありません。")
            return
        me = viewer_email()
        mine = [i for i, r in enumerate(rows) if r.get("メール", "").strip().lower() == me] if me else []
        names = [r.get("役員名") or r.get("メール") or f"{i + 2}行目" for i, r in enumerate(rows)]
        if mine:
            idx = mine[0]
            st.caption(f"{names[idx]}（{me}）の設定")
        else:
            idx = st.selectbox("どなたの設定ですか", range(len(rows)), format_func=lambda i: names[i])
        row = rows[idx]
        if row.get(DELIVERY_COLS["dm"]):
            st.html(f'<p class="hs-ok">● 「報連相AI」は追加済みです（{_html.escape(row.get(DELIVERY_COLS["added"], ""))}）</p>')
        else:
            st.html('<p class="hs-ng">● まだ「報連相AI」が追加されていません。Google Chat の「＋ チャットを新規作成」→「アプリを検索」で'
                    '「報連相AI」を探して追加すると、翌朝から届きます。</p>')

        choices = space_choices()
        chosen = {s for s in str(row.get(DELIVERY_COLS["spaces"], "")).replace(",", "、").replace("，", "、").split("、") if s.strip()}
        with st.form(f"delivery_{idx}"):
            on = st.toggle("毎朝の配信を受け取る", value=row.get(DELIVERY_COLS["on"], "する") != "しない")
            mode = st.radio("届け方", ["まとめて1通", "スペースごと"], horizontal=True,
                            index=1 if row.get(DELIVERY_COLS["mode"]) == "スペースごと" else 0,
                            help="まとめて1通：選んだスペースの要確認・フォローを1通に。スペースごと：各スペースの要約をそのまま1通ずつ。")
            st.markdown("**受け取るスペース**")
            picked = []
            group = None
            for s in choices:
                if s["group"] != group:
                    group = s["group"]
                    st.caption(group)
                if st.checkbox(s["name"], value=s["id"] in chosen, key=f"sp_{idx}_{s['id']}"):
                    picked.append(s["id"])
            unknown = sorted(chosen - {s["id"] for s in choices})     # 一覧にない（なくなった）スペースは残す
            if unknown:
                st.caption("一覧にないスペース（そのまま残します）：" + "、".join(unknown))
            submitted = st.form_submit_button("保存する", type="primary")
        if submitted:
            now = sheets.dt.datetime.now(sheets.JST)
            try:
                sheets.save_row("delivery", idx + 2, {
                    DELIVERY_COLS["spaces"]: "、".join(picked + unknown),
                    DELIVERY_COLS["mode"]: mode,
                    DELIVERY_COLS["on"]: "する" if on else "しない",
                    "最終更新": f"{now:%Y-%m-%d %H:%M}",
                    "更新者": me or "管理画面",
                })
            except sheets.SheetError as e:
                show_error(e)
            else:
                st.success(f"保存しました（{len(picked + unknown)}スペース・{mode}・{'配信する' if on else '配信しない'}）。明日の朝の配信から反映されます。")


def base_page_shell(appbar_html: str) -> str:
    """ヘッダー（タブ）だけの小さな画面。"""
    return ('<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>' + base_css() +
            'body{margin:0;background:transparent}</style></head><body>' + appbar_html + NAV_JS + '</body></html>')


# 「最新を読み込む」から ?reload=1 付きで開かれたら、読み込み済みの内容を捨てて読み直す
if st.query_params.get("reload"):
    sheets.reload_all()
    del st.query_params["reload"]

pg = st.navigation([
    st.Page(admin_page, title="報連相AI 管理画面", url_path="", default=True),
    st.Page(survey_page, title="報連相チェック集計", url_path="survey"),
], position="hidden")
pg.run()
