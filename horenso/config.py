"""設定値。スプレッドシートIDなどは secrets.toml / 環境変数で上書きできる。"""
import os

DEFAULTS = {
    # 報連相AIレポート 管理台帳
    "LEDGER_ID": "1fc6_hDyjuYgxahKtzsDHGAULfFxb6k_LOD-N8VBiFL4",
    # 報連相チェック回答管理表（Googleフォームの回答先）
    "SURVEY_ID": "1o6NGMh4KNTxroGYppZgDJv-Q4kcqJYkuv-5xM7iiD5s",
    # 読み込んだ内容を使い回す時間（秒）。「最新を読み込む」ボタンで即時更新できる
    "CACHE_TTL": "600",
}

TABS = {
    # 管理台帳
    "cases": "案件",
    "caselog": "案件ログ",
    "links": "紐づけ",
    "pages": "ページ",
    "clients": "クライアント",
    # アンケート回答管理表
    "survey": "フォームの回答 1",
    "settings": "分析",
}
LEDGER_KINDS = {"cases", "caselog", "links", "pages", "clients"}


def get(key: str) -> str:
    """secrets.toml の [horenso] → 環境変数 → 既定値 の順に探す。"""
    try:
        import streamlit as st
        sec = st.secrets.get("horenso", {})
        if key in sec:
            return str(sec[key])
    except Exception:
        pass
    return os.environ.get("HORENSO_" + key, DEFAULTS[key])
