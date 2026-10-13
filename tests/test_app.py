"""動作確認（架空のデータで、画面が表示されるか・データが安全に埋め込まれるかを見る）

実行： python tests/test_app.py   （「すべてOK」と出れば成功）
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

L = {5: "5：10割できた", 4: "4：9割できた", 3: "3：8〜9割できた", 2: "2：5〜8割できた", 1: "1：5割未満"}
SURVEY = [["タイムスタンプ", "1. 氏名", "2. 部署", "3. 【報告】今週…", "4. 【連絡】今週…", "5. 【相談】今週…", "6. うまくいったこと", "7. 委員会への要望 (参考)"],
          ["2026/09/25 16:10:00", "社員 A", "営業部", L[3], L[4], L[5]],
          ["2026/10/02 16:00:00", "社員A", "営業部", L[4], L[4], L[5], "</script><b>テスト</b>"],
          ["2026/10/02 16:30:00", "社員B", "管理部", L[1], L[2], L[2], "", "要望"]]
SETTINGS = [["分析"], ["トライアル対象人数", "4", "人"], ["回答率の目標", "70%"]]
CASES = [["案件ID", "ステータス", "件名", "クライアントID", "スペース", "今の状況", "決まったこと", "未解決のこと", "次に動く人", "次にやること", "期限",
          "止まっている所", "止まり始めた日", "判定の理由", "Goodの理由", "関係者", "開始日", "最終更新日", "スペースID", "止まっている営業日数", "確認状況", "確認メモ", "確認者", "最終レポートID"],
         ["A-1", "🔴 要確認", "納期の再調整", "C001", "花糸チーム", "</script>回答待ち", "", "・可否", "小山", "確認", "2026-10-14", "小山の確認待ち", "2026-10-07", "停滞", "", "小山", "2026-10-05", "2026-10-12", "spaces/AAA", "4", "未確認", "", "", "R"]]
LEDGER = {
    "cases": CASES,
    "caselog": [["記録日", "対象期間", "案件ID", "スペース", "ステータス", "件名", "今の状況"], ["2026-10-12", "10/9〜10/12", "A-1", "花糸チーム", "🔴 要確認", "納期の再調整", "回答待ち"]],
    "links": [["種類", "対象（ページ名 または クライアントID）", "対象の名前（自動）", "スペース名", "スペースURL", "スペースID（自動）"], ["人", "前田社長", "前田社長", "花糸チーム", "", "spaces/AAA"], ["クライアント", "C001", "花糸", "花糸チーム", "", "spaces/AAA"]],
    "pages": [["ページ名", "種類"], ["前田社長", "人"], ["クライアント", "クライアント"]],
    "clients": [["クライアントID", "会社名"], ["C001", "合同会社花糸（岩渕）様"]],
}


def test_app_renders():
    from streamlit.testing.v1 import AppTest
    import streamlit.components.v1 as components
    import horenso.sheets as sheets
    sheets.load = lambda kind: dict(LEDGER, survey=SURVEY, settings=SETTINGS)[kind]
    pages = []
    original = components.html
    components.html = lambda html, **kw: pages.append(html)
    try:
        at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60).run()      # 管理画面（最初のページ）
        assert not at.exception, [e.message for e in at.exception]
        assert not at.error, [e.value for e in at.error]
        # 報連相チェックのページ：ページの切り替えを「2番目のページを表示」に差し替えて動かす
        import streamlit as st
        original_nav = st.navigation

        st.navigation = lambda pages, **kw: original_nav([pages[1]], **kw)
        try:
            at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60).run()
        finally:
            st.navigation = original_nav
        assert not at.exception, [e.message for e in at.exception]
    finally:
        components.html = original
    assert len(pages) == 2, "画面が表示されていません"
    admin, survey = pages
    for page in pages:
        assert "__" + "APPBAR__" not in page and "__" + "NAV_JS__" not in page
    assert "__CASES__" not in admin and "納期の再調整" in admin and "前田社長" in admin
    assert "</script>回答待ち" not in admin             # 案件の文字で画面のプログラムが壊れない
    assert "__VALUES__" not in survey and "社員B" in survey and "トライアル対象人数" in survey
    assert "</script><b>" not in survey                # 回答の文字で画面のプログラムが壊れない


def test_sheet_error_shows_message():
    from streamlit.testing.v1 import AppTest
    import horenso.sheets as sheets

    def fail(kind):
        raise sheets.SheetError("「報連相AIレポート 管理台帳」を読む権限がありません。")
    sheets.load = fail
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=60).run()
    assert not at.exception
    assert any("権限がありません" in e.value for e in at.error)


if __name__ == "__main__":
    test_app_renders()
    test_sheet_error_shows_message()
    print("すべてOK")
