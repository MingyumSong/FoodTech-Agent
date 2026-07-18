import io

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models.member import Member
from app.models.member_program import MemberProgram
from app.services.member_import import import_members

AUTH = {"Authorization": "Bearer test-admin-token"}

# 합성 데이터만 사용 (C6: 실명단 PII 금지). 시트처럼 제목·설명 행이 헤더 위에 있다.
CSV_TEXT = (
    "푸드테크 명단 (합성 테스트),,,,,,\n"
    ",,,,,,\n"
    "연번,성명,이메일,휴대폰,소분류,구분,소속\n"
    "1,김테스트,kim@example.com,010-1111-2222,원우(10기),기업,테스트푸드\n"
    "2,이합성,lee@example.com,010-3333-4444,원우(11기),대학,합성대학교\n"
    "3,박무메일,,010-5555-6666,원우(10기),기관,가상재단\n"
)


@pytest.fixture(autouse=True)
def _admin_token(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "test-admin-token")


def _xlsx_bytes(text: str = CSV_TEXT) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for line in text.strip().split("\n"):
        ws.append(line.split(","))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _members(session: Session) -> list[Member]:
    return list(session.exec(select(Member).order_by(Member.id)).all())  # pyright: ignore[reportArgumentType]


def test_csv_cp949_with_title_rows(session: Session):
    report = import_members(session, CSV_TEXT.encode("cp949"), "명단.csv")
    assert report["encoding"] == "cp949"
    assert report["header_row"] == 3
    assert report["created"] == 3 and report["errors"] == []
    members = _members(session)
    assert [m.name for m in members] == ["김테스트", "이합성", "박무메일"]
    assert members[0].email == "kim@example.com"
    assert members[0].phone == "010-1111-2222"
    assert members[2].email is None
    assert all(m.unsubscribe_token for m in members)


def test_xlsx_import(session: Session):
    report = import_members(session, _xlsx_bytes(), "명단.xlsx")
    assert report["format"] == "xlsx"
    assert report["created"] == 3


def test_reimport_is_idempotent(session: Session):
    import_members(session, CSV_TEXT.encode("utf-8"), "명단.csv", program="최고책임자과정")
    report = import_members(session, CSV_TEXT.encode("utf-8"), "명단.csv", program="최고책임자과정")
    assert report["created"] == 0 and report["updated"] == 3
    assert report["linked_program"] == 0  # 이미 연결됨 — 중복 연결 없음
    assert len(_members(session)) == 3
    assert len(list(session.exec(select(MemberProgram)).all())) == 3


def test_missing_email_matches_by_name_and_org(session: Session):
    import_members(session, CSV_TEXT.encode("utf-8"), "명단.csv")
    # 박무메일(이메일 없음)의 직위만 채운 부분 시트 재임포트
    partial = "성명,소속,직위\n박무메일,가상재단,본부장\n"
    report = import_members(session, partial.encode("utf-8"), "부분.csv")
    assert report["created"] == 0 and report["updated"] == 1
    member = next(m for m in _members(session) if m.name == "박무메일")
    assert member.position == "본부장"
    assert member.phone == "010-5555-6666"  # 빈 셀이 기존 값을 지우지 않음 (AC6)


def test_dry_run_writes_nothing(session: Session):
    report = import_members(session, CSV_TEXT.encode("utf-8"), "명단.csv", dry_run=True)
    assert report["dry_run"] is True and report["created"] == 3
    assert _members(session) == []


def test_program_links_with_cohort(session: Session):
    import_members(session, CSV_TEXT.encode("utf-8"), "명단.csv", program="최고책임자과정")
    links = list(session.exec(select(MemberProgram)).all())
    assert {link.program for link in links} == {"최고책임자과정"}
    assert sorted(link.cohort or "" for link in links) == ["원우(10기)", "원우(10기)", "원우(11기)"]


def test_import_api_requires_token_and_reports(client: TestClient, session: Session):
    files = {"file": ("명단.csv", CSV_TEXT.encode("utf-8"), "text/csv")}
    assert client.post("/api/members/import", files=files).status_code == 401

    resp = client.post(
        "/api/members/import",
        files={"file": ("명단.csv", CSV_TEXT.encode("utf-8"), "text/csv")},
        params={"dry_run": "true"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 3 and body["dry_run"] is True
    assert _members(session) == []
