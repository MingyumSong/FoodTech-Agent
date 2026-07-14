---
name: ticket-done
description: 티켓 완료 루틴 일괄 처리. "/ticket-done T-00X", "티켓 완료", "티켓 마감" 요청 시 사용.
---

# /ticket-done — 티켓 완료 루틴

구현이 끝난 티켓을 검증하고 DONE 처리·커밋까지 마친다. 인자로 티켓 번호를 받는다 (예: `/ticket-done T-005`).

## 절차

1. `docs/tickets/T-00X_*.md`를 열어 **Acceptance Criteria를 하나씩 실제 코드/동작과 대조** — 미충족 항목이 있으면 여기서 중단하고 보고.
2. 티켓의 **Verification 절차를 실제로 수행** (라이브 검증 포함 — 테스트 통과만으로 대체하지 않는다).
3. 검증 일괄 실행: `bash scripts/check.sh` (ruff + pyright + pytest).
4. 티켓 Status 갱신: `Status: DONE (날짜 — AC n/n 충족, 핵심 검증 결과 1~2줄, 주요 산출물 경로)`.
5. **CLAUDE.md 동기화**: "추천 다음 작업"에서 해당 항목 취소선+완료 요약, 관련 결정이 생겼으면 "확정한 결정"에 반영 (200줄 이내 유지).
6. 커밋: 레포 컨벤션 준수 — `feat:`/`research:`/`docs:` 접두사 + 한국어 한 줄 요약 + 본문 불릿, `Co-Authored-By` 푸터.
7. 마지막에 리마인드 출력: "노션 주차 페이지에 반영할까요?" (주간 싱크 자료용 — 노션 MCP 인증 필요).

## 금지

- AC 미충족 상태로 DONE 처리 (부분 완료면 티켓에 남은 항목을 명시하고 Status는 DOING 유지)
- 테스트 실패 상태로 커밋
- Scope 밖 파일이 diff에 섞인 채 커밋 (분리하거나 사유를 커밋 메시지에 명시)
