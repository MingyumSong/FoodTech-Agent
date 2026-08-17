/* 회원 관리 모달 (T-027 3a) — 04 Newsletter 섹션에서 연다.
 *
 * 기존 관리자 '회원 관리' 탭이 하던 일을 그대로 옮겼다. 다만 두 가지가 다르다:
 *  - "발송 대상" 토글이 새로 생겼다. 지금까지 관리자 화면엔 **이미 있는 회원을 발송 대상에
 *    넣는 기능이 없어서**, 요청이 올 때마다 스크립트를 돌려야 했다(2026-08-17 실제 사례).
 *  - '구분' 필터는 옮기지 않았다. category 컬럼이 3,400여 건 전부 비어 있어 선택지가
 *    만들어지지 않는 죽은 컨트롤이었다.
 */

import { api, closeModal, esc, openModal, refresh, toast, withBusy } from "./modal.js";

const state = { q: "", program: "", page: 0, pilot: "pilot-daily" };

export function openMembersModal() {
  state.q = "";
  state.program = "";
  state.page = 0;
  return openModal({
    title: "회원 관리",
    subtitle: "발송 대상과 구독 상태를 여기서 바꿉니다",
    render: renderBody,
  });
}

async function renderBody() {
  const params = new URLSearchParams({ page: String(state.page) });
  if (state.q) params.set("q", state.q);
  if (state.program) params.set("program", state.program);

  try {
    return renderMembers(await api(`/admin/api/members?${params}`));
  } catch (e) {
    return `<div class="toast bad">목록을 불러오지 못했습니다 — ${esc(e.message)}</div>`;
  }
}

/** 순수 렌더 — 응답을 받아 HTML만 만든다. 가져오기와 분리해 둬야 이 부분만 따로 볼 수 있다. */
export function renderMembers(d) {
  state.pilot = d.pilot_program;

  const from = d.page * d.per_page;
  const shown = d.members.length;
  const options = d.programs
    .map(
      (p) =>
        `<option value="${esc(p)}"${p === state.program ? " selected" : ""}>${esc(p)}</option>`,
    )
    .join("");

  return `
    <div class="row">
      <input class="field" id="m-q" placeholder="이름·이메일 검색" value="${esc(state.q)}"
             style="flex:1 1 220px">
      <select class="field" id="m-program">
        <option value="">프로그램 전체</option>${options}
      </select>
      <button class="btn" id="m-search">찾기</button>
      <button class="btn btn-primary" id="m-add-open">+ 회원 추가</button>
    </div>

    <div id="m-add" hidden>
      <div class="row">
        <input class="field" id="m-name" placeholder="이름 (필수)" style="flex:1 1 130px">
        <input class="field" id="m-email" placeholder="이메일" style="flex:1 1 190px">
        <input class="field" id="m-org" placeholder="소속" style="flex:1 1 150px">
        <select class="field" id="m-newprogram">
          <option value="">프로그램 없음</option>${d.programs
            .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`)
            .join("")}
        </select>
        <button class="btn btn-primary" id="m-create">추가</button>
      </div>
    </div>

    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>이름</th><th>이메일</th><th>소속</th>
          <th>발송 대상</th><th>구독</th><th></th>
        </tr></thead>
        <tbody>${d.members.map(row).join("") || empty()}</tbody>
      </table>
    </div>

    <div class="pager">
      <span>전체 ${d.total.toLocaleString("ko-KR")}명 · ${
        shown ? `${from + 1}–${from + shown}번째` : "결과 없음"
      }</span>
      <span>
        <button class="btn btn-sm" id="m-prev"${d.page === 0 ? " disabled" : ""}>← 이전</button>
        <button class="btn btn-sm" id="m-next"${
          from + shown >= d.total ? " disabled" : ""
        }>다음 →</button>
      </span>
    </div>`;
}

function empty() {
  return `<tr><td colspan="6" style="color:var(--ink-3)">조건에 맞는 회원이 없습니다.</td></tr>`;
}

function row(m) {
  // 명단에 있어도 수신거부면 메일은 안 간다. "발송 중"이라 적으면 거짓말이 된다 —
  // 실제로 시드 데이터에서 '발송 중 + 수신거부'가 나란히 뜨는 걸 보고 고쳤다.
  const pilot = m.in_pilot
    ? m.subscribed
      ? `<button class="btn btn-sm btn-on" data-act="pilot-off" data-id="${m.id}">발송 중</button>`
      : `<button class="btn btn-sm btn-warn" data-act="pilot-off" data-id="${m.id}"
           title="명단에는 있지만 수신거부 상태라 발송되지 않습니다">발송 보류</button>`
    : `<button class="btn btn-sm" data-act="pilot-on" data-id="${m.id}">대상 아님</button>`;
  const sub = m.subscribed
    ? `<button class="btn btn-sm" data-act="unsub" data-id="${m.id}">구독중</button>`
    : `<button class="btn btn-sm btn-danger" data-act="resub" data-id="${m.id}">수신거부</button>`;
  return `<tr data-name="${esc(m.name)}">
    <td style="white-space:nowrap">${esc(m.name)}</td>
    <td>${esc(m.email) || '<span style="color:var(--ink-3)">—</span>'}</td>
    <td>${esc(m.organization)}</td>
    <td>${pilot}</td>
    <td>${sub}</td>
    <td><button class="btn btn-sm btn-danger" data-act="del" data-id="${m.id}">삭제</button></td>
  </tr>`;
}

/* ---------------------------------------------------------------- 조작 */

// 확인 문구는 **무슨 일이 벌어지는지**를 적는다. "정말요?"는 아무것도 알려주지 않는다.
const CONFIRM = {
  "pilot-on": (n) => `${n} 님을 발송 대상에 넣을까요? 내일 13:00부터 매일 받게 됩니다.`,
  "pilot-off": (n) => `${n} 님을 발송 대상에서 뺄까요? 더 이상 발송되지 않습니다.`,
  unsub: (n) => `${n} 님의 수신을 해지할까요?`,
  resub: (n) => `${n} 님을 다시 구독시킬까요? 본인이 요청한 경우에만 누르세요.`,
  del: (n) => `${n} 님을 삭제할까요? 되돌릴 수 없습니다 (발송·추적 기록은 남습니다).`,
};

async function act(kind, id, name, btn) {
  if (!window.confirm(CONFIRM[kind](name))) return;
  await withBusy(btn, async () => {
    try {
      if (kind === "del") {
        await api(`/admin/api/members/${id}`, { method: "DELETE" });
      } else if (kind === "unsub" || kind === "resub") {
        await api(`/admin/api/members/${id}/subscribed`, {
          method: "POST",
          body: { subscribed: kind === "resub" },
        });
      } else {
        await api(`/admin/api/members/${id}/program`, {
          method: "POST",
          body: { program: state.pilot, joined: kind === "pilot-on" },
        });
      }
      await refresh();
      toast("반영했습니다.");
    } catch (e) {
      toast(`실패 — ${e.message}`, "bad");
    }
  });
}

/* 모달 본문은 매번 새로 그려지므로 개별 요소에 리스너를 달면 사라진다.
 * 문서 한 곳에서 위임으로 받는다. */
document.addEventListener("click", async (e) => {
  const t = e.target;
  if (!(t instanceof HTMLElement)) return;

  if (t.id === "m-search") return void refreshWith();
  if (t.id === "m-prev") return void refreshWith(state.page - 1);
  if (t.id === "m-next") return void refreshWith(state.page + 1);
  if (t.id === "m-add-open") {
    document.getElementById("m-add")?.toggleAttribute("hidden");
    return;
  }
  if (t.id === "m-create") return void create(t);

  const act_ = t.dataset.act;
  if (act_ && CONFIRM[act_]) {
    const name = t.closest("tr")?.dataset.name ?? "이 회원";
    await act(act_, t.dataset.id, name, t);
  }
});

// Enter 로도 검색되게 — 돋보기 버튼을 찾아 누르게 만들지 않는다.
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target instanceof HTMLElement && e.target.id === "m-q") {
    refreshWith();
  }
});

function readFilters() {
  const q = document.getElementById("m-q");
  const p = document.getElementById("m-program");
  if (q instanceof HTMLInputElement) state.q = q.value.trim();
  if (p instanceof HTMLSelectElement) state.program = p.value;
}

async function refreshWith(page = 0) {
  readFilters();
  state.page = Math.max(0, page);
  await refresh();
}

async function create(btn) {
  const val = (id) => {
    const el = document.getElementById(id);
    return el instanceof HTMLInputElement || el instanceof HTMLSelectElement ? el.value.trim() : "";
  };
  const name = val("m-name");
  if (!name) {
    toast("이름은 필수입니다.", "bad");
    return;
  }
  await withBusy(btn, async () => {
    try {
      await api("/admin/api/members", {
        method: "POST",
        body: {
          name,
          email: val("m-email") || null,
          organization: val("m-org") || null,
          program: val("m-newprogram") || null,
        },
      });
      await refresh();
      toast(`${name} 님을 추가했습니다.`);
    } catch (e) {
      toast(`추가 실패 — ${e.message}`, "bad");
    }
  });
}

export { closeModal };
