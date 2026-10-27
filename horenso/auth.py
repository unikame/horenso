"""Google アカウントでのログイン（Streamlit の st.login を使う）

secrets.toml の [auth] に Google の OAuth クライアントを登録すると、ログインが必要になる。
[auth] がなければ、ログインなしで動く（手元での確認・テスト用）。
入れるのは ALLOWED_DOMAINS のドメイン（既定：glug.co.jp）のアカウントと、ALLOWED_EMAILS に書いた人だけ。
"""
from horenso import config


def enabled() -> bool:
    """secrets.toml に [auth]（Google の OAuth クライアント）が登録されているか。"""
    try:
        import streamlit as st
        a = st.secrets.get("auth", {})
        return bool(a.get("client_id") and a.get("client_secret") and a.get("redirect_uri"))
    except Exception:
        return False


def _split(key: str) -> set[str]:
    return {s.strip().lower().lstrip("@") for s in str(config.get(key) or "").replace("、", ",").split(",") if s.strip()}


def allowed(email: str, verified=True) -> bool:
    """このアカウントで入ってよいか（社内のドメイン、または個別に許可した人）。"""
    email = str(email or "").strip().lower()
    if "@" not in email or verified is False:
        return False
    if email in _split("ALLOWED_EMAILS"):
        return True
    return email.rsplit("@", 1)[1] in _split("ALLOWED_DOMAINS")
