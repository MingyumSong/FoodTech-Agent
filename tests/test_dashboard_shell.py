"""T-027 1단계 — 대시보드 셸. 인증·섹션 골격·정적 마운트 우회 방지."""

import base64
import re

from fastapi.testclient import TestClient

from app.config import settings

TOKEN = "secret-token"


def _auth(password: str = TOKEN) -> dict[str, str]:
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_dashboard_requires_auth(client: TestClient, monkeypatch):
    """페이지 전체가 인증 뒤에 있다 (결정 5, 안 1)."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    assert client.get("/admin/dashboard").status_code == 401
    assert client.get("/admin/dashboard", headers=_auth("wrong")).status_code == 401
    assert client.get("/admin/dashboard", headers=_auth()).status_code == 200


def test_dashboard_html_is_not_reachable_through_static_mount(client: TestClient):
    """`/static`은 공개 마운트다 — 셸 HTML이 거기 있으면 인증이 통째로 우회된다.

    1단계에서 실제로 처음엔 `app/static/dashboard/index.html`에 뒀다가 옮겼다.
    다시 그 자리로 돌아가면 이 테스트가 잡는다.
    """
    for path in (
        "/static/dashboard/index.html",
        "/static/dashboard/dashboard.html",
        "/static/templates/dashboard.html",
    ):
        assert client.get(path).status_code == 404, f"{path}가 인증 없이 열린다"


def test_dashboard_assets_are_public_and_load(client: TestClient):
    """CSS·JS는 데이터가 없어 공개로 둔다. 다만 실제로 서빙되긴 해야 화면이 뜬다."""
    css = client.get("/static/dashboard/dashboard.css")
    js = client.get("/static/dashboard/dashboard.js")
    assert css.status_code == 200 and js.status_code == 200
    assert "--gold" in css.text  # 디자인 토큰이 실려 있다
    assert "SECTIONS" in js.text  # 섹션 등록부가 실려 있다


def test_shell_declares_all_four_sections(client: TestClient, monkeypatch):
    """네 섹션이 모두 선언돼 있어야 랩실이 어디를 채울지 안다."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    body = client.get("/admin/dashboard", headers=_auth()).text
    assert '<main id="sections">' in body

    js = client.get("/static/dashboard/dashboard.js").text
    for section in ("overview", "events", "programs", "newsletter"):
        assert f'id: "{section}"' in js, f"{section} 섹션이 등록부에 없다"


def test_shell_credits_the_design_source(client: TestClient, monkeypatch):
    """가져온 디자인의 출처를 남긴다 (T-027 AC7)."""
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    body = client.get("/admin/dashboard", headers=_auth()).text
    assert "HeejeongH/foodtech-dashboard" in body


def test_shell_carries_no_data(client: TestClient, monkeypatch):
    """셸엔 숫자가 없다 — 데이터는 전부 인증된 JSON API에서만 나온다.

    저쪽 대시보드가 손으로 적은 값 때문에 낡아버린 게 이 티켓의 출발점이라,
    셸에 숫자가 섞여 들어가는 걸 처음부터 막는다.
    """
    monkeypatch.setattr(settings, "admin_token", TOKEN)
    body = client.get("/admin/dashboard", headers=_auth()).text
    # 저쪽에 박제된 값들이 전부 이 모양이었다: "1,463명", "클릭 92건", "중앙값 11초"
    assert not re.search(r"\d{1,3},\d{3}", body), "셸에 자릿수 구분된 수치가 박혀 있다"
    assert not re.search(r"\d+\s*(건|명|초|%)", body), "셸에 집계 수치가 박혀 있다"
