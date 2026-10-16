"""Google スプレッドシートの読み込み（読み取り専用）。

認証は次の順に探す。
1. Secrets の gcp_service_account_json … 鍵の JSON をそのまま貼ったもの（いちばん簡単）
2. Secrets の [gcp_service_account] … 鍵の JSON を項目ごとに書いたもの
3. 実行環境の既定の認証情報 … Cloud Run に割り当てたサービスアカウント、または手元の gcloud ログイン
   （Streamlit Community Cloud にはこれがないので、1 か 2 が必須）
どの場合も、そのサービスアカウントのメールアドレスを、管理台帳とアンケートのスプレッドシートに「閲覧者」で共有しておく。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

import google.auth.exceptions
import gspread
import requests
import streamlit as st

from . import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]   # 書けるかどうかは共有の権限で決まる（管理台帳・アンケートは閲覧者、配信設定だけ編集者）
JST = dt.timezone(dt.timedelta(hours=9))
LOADED: dict = {}          # (シートID, タブ) → 実際に Google から読み込んだ時刻

NO_KEY = ("サービスアカウントの鍵が Secrets に登録されていません。"
          "Streamlit Cloud の「Manage app」→「Settings」→「Secrets」に、gcp_service_account_json として鍵の JSON を貼ってください（README の手順 B）。")
BAD_JSON = ("Secrets の gcp_service_account_json が JSON として読めません。"
            "鍵ファイルの中身を、最初の { から最後の } まで省略せずに、''' と ''' の間に貼ってください。")


class SheetError(Exception):
    """画面に出すための、わかりやすい読み込みエラー。"""


def _parse_key_json(raw) -> dict:
    """貼り付けた鍵の JSON を、よくある崩れ（"\"\"\"" で囲んだ・引用符が “ ” に変わった・全角スペース）を直して読む。"""
    if not isinstance(raw, str):
        return dict(raw)
    s = raw.replace("﻿", "").replace("　", " ").replace(" ", " ")
    s = s.translate(str.maketrans({"“": '"', "”": '"', "„": '"', "＂": '"', "｛": "{", "｝": "}", "：": ":", "，": ","}))
    i, j = s.find("{"), s.rfind("}")
    if i < 0:
        raise SheetError(BAD_JSON + "（最初の { が見つかりません）")
    if j < i:
        raise SheetError(BAD_JSON + "（最後の } が見つかりません。途中で切れていないか確認してください）")
    try:
        # strict=False … "\"\"\"" で囲むと private_key の \n が本物の改行になるため、それも受け付ける
        return json.loads(s[i:j + 1], strict=False)
    except json.JSONDecodeError as e:
        raise SheetError(BAD_JSON + f"（貼り付けた {e.lineno} 行目付近の書き方が崩れています）") from None


def _secret_info():
    """Secrets からサービスアカウントの鍵を取り出す。なければ None。"""
    try:
        sec = st.secrets
        raw = sec.get("gcp_service_account_json") or sec.get("horenso", {}).get("gcp_service_account_json")
        if raw:                                                          # [horenso] の下に貼ってしまった場合も拾う
            return _parse_key_json(raw)
        if "gcp_service_account" in sec:
            return dict(sec["gcp_service_account"])
        if "connections" in sec and "gsheets" in sec["connections"]:     # st-gsheets-connection の書き方
            return dict(sec["connections"]["gsheets"])
        if sec.get("type") == "service_account":                         # 見出しなしで項目だけ貼った場合
            return {k: sec[k] for k in sec.keys() if isinstance(sec[k], str)}
    except SheetError:
        raise
    except Exception:                                                    # secrets.toml がない場合など
        return None
    return None


def _has_default_credentials() -> bool:
    adc = os.path.join(os.path.expanduser("~"), ".config", "gcloud", "application_default_credentials.json")
    return bool(os.environ.get("K_SERVICE") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.path.exists(adc))


@st.cache_resource(show_spinner=False)
def _client():
    info = _secret_info()
    if info:
        from google.oauth2.service_account import Credentials
        missing = [k for k in ("client_email", "private_key", "token_uri") if not info.get(k)]
        if missing:
            raise SheetError("Secrets の鍵に " + "・".join(missing) + " がありません。鍵の JSON を省略せずに貼ってください。")
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif _has_default_credentials():                                     # Cloud Run・手元の gcloud ログイン
        import google.auth
        creds, _ = google.auth.default(scopes=SCOPES)
    else:
        raise SheetError(NO_KEY)
    return gspread.authorize(creds), getattr(creds, "service_account_email", "")


def service_account_email() -> str:
    try:
        return _client()[1] or ""
    except Exception:
        return ""


def _ttl() -> int:
    try:
        return int(config.get("CACHE_TTL"))
    except ValueError:
        return 600


@st.cache_data(ttl=_ttl(), show_spinner="スプレッドシートを読み込んでいます…")
def load_values(sheet_id: str, tab: str) -> list[list[str]]:
    """タブ全体を、画面に表示されている書式どおりの文字列で返す。"""
    try:
        gc, email = _client()
    except SheetError:
        raise
    except Exception as e:  # 鍵が壊れている など
        raise SheetError("Google の認証情報を読み込めませんでした。Secrets に貼った鍵を確認してください。（" + type(e).__name__ + "）") from e
    share = (email + " を閲覧者として共有してください。") if email else ""
    try:
        values = gc.open_by_key(sheet_id).worksheet(tab).get_values()
        LOADED[(sheet_id, tab)] = dt.datetime.now(JST)
        return values
    except gspread.exceptions.WorksheetNotFound as e:
        raise SheetError("スプレッドシートに「" + tab + "」タブが見つかりません。タブ名が変わっていないか確認してください。") from e
    except gspread.exceptions.SpreadsheetNotFound as e:
        raise SheetError("スプレッドシートが見つからないか、共有されていません。" + share) from e
    except PermissionError as e:                     # gspread は 403 をこの形で返す
        raise SheetError(_forbidden_message(e, sheet_id, share)) from e
    except (google.auth.exceptions.RefreshError, google.auth.exceptions.TransportError, requests.exceptions.ConnectionError) as e:
        raise SheetError("Google にログインできませんでした。Secrets の鍵が正しいか（削除・無効化された鍵でないか）確認してください。（" + type(e).__name__ + "）") from e
    except gspread.exceptions.APIError as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code == 403:
            raise SheetError(_forbidden_message(e, sheet_id, share)) from e
        if code == 429:
            raise SheetError("Google の読み込み回数の上限に達しました。1分ほど待ってから再読み込みしてください。") from e
        raise SheetError("スプレッドシートを読み込めませんでした（" + str(code) + "）。") from e


def _forbidden_message(e: Exception, sheet_id: str, share: str) -> str:
    """403 の理由（API が無効／共有されていない）を見分けて案内を作る。"""
    api = e if isinstance(e, gspread.exceptions.APIError) else e.__cause__
    text = ""
    try:
        text = api.response.text if api is not None else ""
    except Exception:
        pass
    if "SERVICE_DISABLED" in text or "has not been used" in text or "is disabled" in text:
        m = re.search(r"project[s]?/?\s*(\d+)", text)
        return ("Google Sheets API が有効になっていません。Google Cloud コンソールの「API とサービス」→「ライブラリ」で "
                "Google Sheets API を開き、「有効にする」を押してください" + (f"（プロジェクト番号 {m.group(1)}）" if m else "") +
                "。有効にしてから数分後に「最新を読み込む」を押してください。")
    name = {config.get("LEDGER_ID"): "報連相AIレポート 管理台帳", config.get("DELIVERY_ID"): "報連相AI 配信設定"}.get(sheet_id, "報連相チェック回答管理表")
    return (f"「{name}」を読む権限がありません。スプレッドシートの「共有」で、" + (share or "サービスアカウントのメールアドレスを閲覧者として共有してください。")
            + " 共有後、「最新を読み込む」を押してください。")


def sheet_id_of(kind: str) -> str:
    if kind in config.LEDGER_KINDS:
        return config.get("LEDGER_ID")
    if kind in config.DELIVERY_KINDS:
        return config.get("DELIVERY_ID")
    return config.get("SURVEY_ID")


def load(kind: str) -> list[list[str]]:
    """kind は config.TABS のキー（cases / caselog / links / pages / clients / linegroups / delivery / survey / settings）"""
    return load_values(sheet_id_of(kind), config.TABS[kind])


def save_row(kind: str, row_number: int, updates: dict) -> None:
    """見出し名 → 値 の updates を、その行（1始まり。見出しが1行目）に書き込む。書いたら読み込み直す。"""
    try:
        gc, email = _client()
        ws = gc.open_by_key(sheet_id_of(kind)).worksheet(config.TABS[kind])
        head = [str(h).strip() for h in ws.row_values(1)]
        cells = []
        for h, v in updates.items():
            if h not in head:
                raise SheetError("「" + config.TABS[kind] + "」タブに「" + h + "」の列が見つかりません。")
            cells.append(gspread.Cell(row_number, head.index(h) + 1, v))
        ws.update_cells(cells, value_input_option="RAW")
    except SheetError:
        raise
    except PermissionError as e:
        raise SheetError("「報連相AI 配信設定」に書き込む権限がありません。サービスアカウントを「編集者」で共有してください。") from e
    except gspread.exceptions.APIError as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code == 403:
            raise SheetError("「報連相AI 配信設定」に書き込む権限がありません。サービスアカウントを「編集者」で共有してください。") from e
        raise SheetError("保存できませんでした（" + str(code) + "）。少し待ってからもう一度お試しください。") from e
    load_values.clear()


def loaded_at():
    """いちばん古い読み込み時刻（表示中のデータがいつ時点か）。まだなければ None。"""
    return min(LOADED.values()) if LOADED else None


def reload_all():
    load_values.clear()
    _client.clear()
    LOADED.clear()
