/* 푸드테크 대시보드 — 섹션 등록과 렌더 (T-027 1단계)
 *
 * ┌─ 새 섹션을 만들려면 여기만 보면 된다 ────────────────────────────────┐
 * │ 1. 아래 SECTIONS 배열에 항목을 추가한다.                              │
 * │ 2. endpoint 에 JSON API 주소를 적는다 (서버는 app/routes/admin.py).   │
 * │ 3. render(data) 를 채운다 — 응답을 받아 섹션 본문 HTML 문자열을 만든다.│
 * │ endpoint 를 null 로 두면 "아직 비어 있음" 자리로 그려진다.            │
 * └──────────────────────────────────────────────────────────────────────┘
 *
 * 데이터를 여기서 직접 가공하지 않는다. 계산은 서버가 끝내서 보내고, 이 파일은 그리기만 한다.
 * (그래야 같은 숫자가 화면과 CSV·API에서 갈라지지 않는다.)
 */

const SECTIONS = [
  {
    no: "01",
    id: "overview",
    title: "Overview",
    sub: "관리 인원 및 활동 현황",
    owner: "랩실",
    endpoint: null,
    render: null,
  },
  {
    no: "02",
    id: "events",
    title: "Events",
    sub: "행사 참여 현황",
    owner: "랩실",
    endpoint: null,
    render: null,
  },
  {
    no: "03",
    id: "programs",
    title: "Programs",
    sub: "교육과정 참여 현황",
    owner: "랩실",
    endpoint: null,
    render: null,
  },
  {
    no: "04",
    id: "newsletter",
    title: "Newsletter",
    sub: "뉴스레터 발송·참여 현황",
    owner: "뉴스레터 팀",
    mine: true, // 우리가 채우는 섹션 — 빈 자리라도 나머지와 구분해 보여준다
    // 2단계에서 붙인다. 지금은 자리만 잡아 나머지 셋과 같은 모양인지 확인한다.
    endpoint: null,
    render: null,
  },
];

/* ---------------------------------------------------------------- 도우미 */

/** HTML 이스케이프. 사람 이름·소속이 그대로 들어오므로 렌더 전에 반드시 통과시킨다. */
export function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

function sectionShell(s) {
  return `
    <section class="section" id="section-${s.id}">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2 class="section-title"><span class="num">${s.no}</span>${esc(s.title)}</h2>
            <p class="section-sub" id="sub-${s.id}">${esc(s.sub)}</p>
          </div>
          <div class="section-actions" id="actions-${s.id}"></div>
        </div>
        <div id="body-${s.id}"></div>
      </div>
    </section>`;
}

function placeholder(s) {
  // 같은 "빈 자리"라도 누가 언제 채우는지는 다르다 — 형태로 구분해 계획이 화면에 드러나게 한다.
  const note = s.mine
    ? "곧 실제 데이터가 연결됩니다."
    : "아직 데이터가 연결되지 않았습니다.";
  return `
    <div class="placeholder${s.mine ? " next" : ""}">
      <div class="who">${esc(s.owner ?? "미정")}이 채울 자리</div>
      <div>${note}</div>
      <div class="hint">app/static/dashboard/dashboard.js → SECTIONS['${esc(s.id)}']</div>
    </div>`;
}

function loading() {
  return `
    <div class="panel">
      <div class="stack">
        <div class="skeleton" style="width:38%"></div>
        <div class="skeleton" style="width:72%"></div>
        <div class="skeleton" style="width:55%"></div>
      </div>
    </div>`;
}

/** 실패 이유를 화면에 남긴다 — 빈 화면과 고장 난 화면은 구분되어야 한다. */
function errorState(message) {
  return `<div class="panel"><div class="state error">${esc(message)}</div></div>`;
}

async function loadSection(s) {
  const body = document.getElementById(`body-${s.id}`);
  if (!body) return;

  if (!s.endpoint || !s.render) {
    body.innerHTML = placeholder(s);
    return;
  }

  body.innerHTML = loading();
  try {
    const res = await fetch(s.endpoint, { headers: { Accept: "application/json" } });
    if (res.status === 401 || res.status === 403) {
      body.innerHTML = errorState("로그인이 필요합니다. 새로고침 후 다시 시도해 주세요.");
      return;
    }
    if (!res.ok) {
      body.innerHTML = errorState(`데이터를 불러오지 못했습니다 (HTTP ${res.status})`);
      return;
    }
    body.innerHTML = s.render(await res.json());
  } catch (e) {
    body.innerHTML = errorState(`데이터를 불러오지 못했습니다 — ${e && e.message ? e.message : e}`);
  }
}

/* ---------------------------------------------------------------- 시작 */

export function mount(root) {
  root.innerHTML = SECTIONS.map(sectionShell).join("");
  // 섹션끼리 기다리지 않게 각자 불러온다 — 하나가 느려도 나머지는 먼저 뜬다.
  SECTIONS.forEach(loadSection);
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("sections");
  if (root) mount(root);
});
