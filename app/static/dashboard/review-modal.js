/* 발송 검토 모달 (T-027 3b) — 04 Newsletter 섹션에서 연다.
 *
 * **이 화면에서만 실제 메일이 나간다.** 그래서 다른 모달과 다르게 잡은 것들:
 *  - 발송 가능 여부를 화면이 판단하지 않는다. 서버가 준 can_send·blocked_reason 을 그대로 쓴다.
 *    화면이 가드를 따로 들고 있으면 상한이 바뀔 때 "보낼 수 있다"고 해놓고 서버는 400을 낸다.
 *  - 확인 문구에 **받는 사람 수와 편 제목**을 넣는다. "정말요?"는 아무것도 알려주지 않는다.
 *  - 미리보기를 발송 버튼보다 앞에 둔다. 보고 나서 누르는 순서가 되게.
 */

import { api, esc, openModal, refresh, toast, withBusy } from "./modal.js";

export function openReviewModal() {
  return openModal({
    title: "발송 검토",
    subtitle: "오늘 편을 확인하고 보냅니다",
    render: renderBody,
  });
}

async function renderBody() {
  try {
    return renderReview(await api("/admin/api/review"));
  } catch (e) {
    return `<div class="toast bad">불러오지 못했습니다 — ${esc(e.message)}</div>`;
  }
}

/** 순수 렌더 — 가져오기와 분리해 둬야 이 부분만 따로 검수할 수 있다. */
export function renderReview(d) {
  const s = d.settings;
  const ed = d.edition;

  const editionBox = ed
    ? `<div class="panel" style="margin-bottom:16px">
         <p class="panel-title">오늘 편</p>
         <div style="font-size:15px;font-weight:700;margin-bottom:6px">${esc(ed.subject)}</div>
         <p class="note-line" style="margin:0">
           기사 ${ed.items}꼭지 · 상태 ${esc(ed.status)}
           ${ed.already_sent ? `· <b>이미 ${ed.already_sent}명에게 발송됨</b>` : "· 아직 발송 전"}
         </p>
       </div>`
    : `<div class="panel" style="margin-bottom:16px">
         <p class="panel-title">오늘 편</p>
         <p class="note-line" style="margin:0">아직 조립되지 않았습니다. 아래 [오늘 편 조립]을 누르세요.</p>
       </div>`;

  // 보낼 수 없으면 이유를 크게 보여주고 버튼을 잠근다 — 눌러보고 실패하게 두지 않는다.
  const gate = d.can_send
    ? `<div class="toast good" style="margin:0 0 12px">
         받는 사람 <b>${d.recipients}명</b> · 상한 ${d.max_recipients}명
       </div>`
    : `<div class="toast bad" style="margin:0 0 12px">${esc(d.blocked_reason)}</div>`;

  return `
    ${editionBox}

    <div class="panel" style="margin-bottom:16px">
      <p class="panel-title">발송 구성</p>
      <p class="note-line">
        에피타이저+메인(${s.total})과 국내+해외(${s.n_domestic + s.n_overseas})의 합이 같아야
        저장됩니다. 저장해도 <b>이미 조립된 오늘 편에는 반영되지 않습니다</b> — 다시 조립하세요.
      </p>
      <div class="row">
        ${num("에피타이저", "n_headlines", s.n_headlines)}
        ${num("메인", "n_mains", s.n_mains)}
        ${num("국내", "n_domestic", s.n_domestic)}
        ${num("해외", "n_overseas", s.n_overseas)}
        ${num("최근 일수", "days", s.days)}
        <button class="btn" id="r-save">구성 저장</button>
      </div>
    </div>

    <!-- 받는 사람 수를 버튼 **위에** 둔다. 아래 두면 누르고 나서 몇 명인지 알게 된다. -->
    ${gate}

    <div class="row" style="margin:0">
      <button class="btn" id="r-build">🧩 오늘 편 조립</button>
      <a class="btn" href="/admin/review/preview" target="_blank" rel="noreferrer"
         ${ed ? "" : 'style="pointer-events:none;opacity:.45"'}>👀 미리보기</a>
      <span style="flex:1"></span>
      <button class="btn btn-primary" id="r-send" ${d.can_send ? "" : "disabled"}>
        📨 지금 발송
      </button>
    </div>`;
}

function num(label, name, value) {
  return `<label style="font-size:12.5px;color:var(--ink-3)">${esc(label)}
    <input class="field" type="number" id="r-${name}" value="${value}" style="width:64px;margin-left:4px"></label>`;
}

/* ---------------------------------------------------------------- 조작 */

function readSettings() {
  const get = (n) => {
    const el = document.getElementById(`r-${n}`);
    return el instanceof HTMLInputElement ? Number(el.value) : 0;
  };
  return {
    n_headlines: get("n_headlines"),
    n_mains: get("n_mains"),
    n_domestic: get("n_domestic"),
    n_overseas: get("n_overseas"),
    days: get("days"),
  };
}

document.addEventListener("click", async (e) => {
  const t = e.target;
  if (!(t instanceof HTMLElement)) return;

  if (t.id === "r-save") {
    await withBusy(t, async () => {
      try {
        await api("/admin/api/review/settings", { method: "POST", body: readSettings() });
        await refresh();
        toast("구성을 저장했습니다. 오늘 편에 반영하려면 다시 조립하세요.");
      } catch (err) {
        toast(`저장 실패 — ${err.message}`, "bad");
      }
    });
    return;
  }

  if (t.id === "r-build") {
    await withBusy(t, async () => {
      try {
        await api("/admin/api/review/build", { method: "POST" });
        await refresh();
        toast("오늘 편을 조립했습니다. 미리보기로 확인하세요.");
      } catch (err) {
        toast(`조립 실패 — ${err.message}`, "bad");
      }
    });
    return;
  }

  if (t.id === "r-send") {
    const info = document.querySelector("#modal-body .toast.good");
    const who = info ? info.textContent.trim() : "수신자";
    // 되돌릴 수 없는 조작이라 무엇이 누구에게 가는지 문장으로 확인받는다.
    if (!window.confirm(`지금 발송할까요? 되돌릴 수 없습니다.\n\n${who}`)) return;
    await withBusy(t, async () => {
      try {
        const r = await api("/admin/api/review/send", { method: "POST" });
        await refresh();
        toast(`${r.recipients}명에게 발송을 시작했습니다. 잠시 후 새로고침하면 결과가 보입니다.`);
      } catch (err) {
        toast(`발송 실패 — ${err.message}`, "bad");
      }
    });
  }
});
