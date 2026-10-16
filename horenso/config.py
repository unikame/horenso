"""設定値。スプレッドシートIDなどは secrets.toml / 環境変数で上書きできる。"""
import os

DEFAULTS = {
    # 報連相AIレポート 管理台帳
    "LEDGER_ID": "1fc6_hDyjuYgxahKtzsDHGAULfFxb6k_LOD-N8VBiFL4",
    # 報連相チェック回答管理表（Googleフォームの回答先）
    "SURVEY_ID": "1o6NGMh4KNTxroGYppZgDJv-Q4kcqJYkuv-5xM7iiD5s",
    # 報連相AI 配信設定（役員ごとに、個別配信で受け取るスペースを選ぶ。管理画面から書き込む）
    "DELIVERY_ID": "1ZH-5AI3hPZrR3BXsqQHgQaaI0Yxg1q0h9IYoJozN_U4",
    # 配信設定で選べるスペースに必ず出すもの（紐づけタブにないスペース）。「スペースID=名前」を読点区切り
    "EXTRA_SPACES": "spaces/AAQAdiRb6-Q=報連相普及委員会",
    # 読み込んだ内容を使い回す時間（秒）。「最新を読み込む」ボタンで即時更新できる
    "CACHE_TTL": "600",
    # ヘッダーの「報連相チェック」を押したときに開く画面（集計アプリ）
    "SURVEY_APP_URL": "https://horenso-report.streamlit.app/",
}

TABS = {
    # 管理台帳
    "cases": "案件",
    "caselog": "案件ログ",
    "links": "紐づけ",
    "pages": "ページ",
    "clients": "クライアント",
    "linegroups": "LINEグループ",
    # 配信設定
    "delivery": "配信設定",
    # アンケート回答管理表
    "survey": "フォームの回答 1",
    "settings": "分析",
}
LEDGER_KINDS = {"cases", "caselog", "links", "pages", "clients", "linegroups"}
DELIVERY_KINDS = {"delivery"}


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
