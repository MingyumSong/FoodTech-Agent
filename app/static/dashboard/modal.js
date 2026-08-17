/* 모달 부품 (T-027 3단계).
 *
 * 대시보드의 어법은 "요약은 섹션에, 상세와 조작은 모달에"다. 새 섹션도 이걸 그대로 쓴다:
 *
 *   import { openModal, closeModal, api, toast } from './modal.js';
 *   openModal({ title: '행사 관리', subtitle: '…', render: () => '<p>…</p>' });
 *
 * render 는 열릴 때와 refresh() 때마다 불린다 — 목록을 다시 그리려면 refresh() 를 부르면 된다.
 */

let current = null;
let lastFocus = null;

export function closeModal() {
  const el = document.getElementById("modal-root");
  if (el) el.innerHTML = "";
  current = null;
  document.body.style.overflow = "";
  // 열기 전에 있던 자리로 초점을 되돌린다 — 키보드로만 쓰는 사람이 길을 잃지 않게.
  if (lastFocus && lastFocus.focus) lastFocus.focus();
  lastFocus = null;
}

/** 모달을 다시 그린다(데이터가 바뀐 뒤). 열려 있지 않으면 아무 일도 하지 않는다. */
export async function refresh() {
  if (!current) return;
  const body = document.getElementById("modal-body");
  if (body) body.innerHTML = await current.render();
}

export async function openModal({ title, subtitle = "", render }) {
  const root = document.getElementById("modal-root");
  if (!root) return;
  lastFocus = document.activeElement;
  current = { render };

  root.innerHTML = `
    <div class="backdrop" data-close role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="modal">
        <div class="modal-head">
          <div>
            <h3>${esc(title)}</h3>
            ${subtitle ? `<p class="sub">${esc(subtitle)}</p>` : ""}
          </div>
          <button class="modal-x" data-close aria-label="닫기">✕</button>
        </div>
        <div class="modal-body" id="modal-body"></div>
      </div>
    </div>`;

  document.body.style.overflow = "hidden";
  root.querySelector(".modal-x")?.focus();
  await refresh();
}

/** 배경 클릭·닫기 버튼·Esc 로 닫는다. 모달 안쪽 클릭은 통과시킨다. */
document.addEventListener("click", (e) => {
  const t = e.target;
  if (t instanceof Element && t.hasAttribute("data-close")) closeModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && current) closeModal();
});

/* ---------------------------------------------------------------- 도우미 */

export function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

/** 모달 위쪽에 결과 한 줄. 성공도 알려야 사용자가 "눌렸나?" 하고 다시 누르지 않는다. */
export function toast(message, kind = "good") {
  const body = document.getElementById("modal-body");
  if (!body) return;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  body.prepend(el);
}

/** JSON API 호출. 실패하면 서버가 준 사유를 그대로 올려보낸다 — 삼키지 않는다. */
export async function api(url, { method = "GET", body } = {}) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* 본문이 비었을 수 있다 */
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : `HTTP ${res.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

/** 버튼을 눌린 동안 잠근다 — 발송·삭제가 두 번 실행되는 걸 막는 유일한 장치다. */
export async function withBusy(btn, fn) {
  if (btn.disabled) return;
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "…";
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}
