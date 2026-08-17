/* 푸드테크 대시보드 — 섹션 등록과 렌더 (T-027)
 *
 * ┌─ 새 섹션을 만들려면 여기만 보면 된다 ────────────────────────────────┐
 * │ 1. 아래 SECTIONS 배열에 항목을 추가한다.                              │
 * │ 2. endpoint 에 JSON API 주소를 적는다 (서버는 app/routes/admin.py).   │
 * │ 3. render(data) 를 채운다 — 응답을 받아 섹션 본문 HTML 문자열을 만든다.│
 * │ 4. 조작이 필요하면 actions 에 버튼을 선언한다 — 상세는 모달로 연다.   │
 * │ 5. 본문 밖(예: 히어로)을 건드려야 하면 postRender(data) 를 쓴다.      │
 * │ endpoint 를 null 로 두면 "아직 비어 있음" 자리로 그려진다.            │
 * └──────────────────────────────────────────────────────────────────────┘
 *
 * **클래스 이름은 원본(HeejeongH/foodtech-dashboard)을 그대로 쓴다.** 원본 index.html 을
 * 열어 보고 싶은 마크업을 찾으면 그 클래스가 dashboard.css 에 그대로 있다.
 * 새 이름을 지으면 그 대응이 끊기니 짓지 말 것. 쓸 만한 조각들:
 *   .snu-panel / .snu-panel-title      판 하나
 *   .snu-events-layout                 2열(1.4fr 1fr) 배치
 *   .snu-stat-grid + .snu-stat         KPI 격자 (칸 수에 따라 자동 접힘)
 *   .snu-hbar-row                      가로 막대 한 줄
 *   .snu-top-presenters + .snu-presenter  순위 목록(네이비+골드 강조 판)
 *   .data-table + .table-wrap          표 (가로 스크롤 포함)
 *   .status-pill + .status-*           상태 칩
 *
 * 데이터를 여기서 직접 가공하지 않는다. 계산은 서버가 끝내서 보내고, 이 파일은 그리기만 한다.
 * (그래야 같은 숫자가 화면과 CSV·API에서 갈라지지 않는다.)
 */

import { openMembersModal } from "./members-modal.js";
import { openReviewModal } from "./review-modal.js";

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
    endpoint: "/admin/api/newsletter",
    render: renderNewsletter,
    postRender: renderHeroStats, // KPI 넷은 본문이 아니라 히어로 카드로 올라간다
    actions: [
      { label: "👥 회원 관리", run: openMembersModal },
      { label: "📨 발송 검토", run: openReviewModal },
    ],
  },
];

/* ---------------------------------------------------------------- 공통 조각 */

/** 가로 막대 목록. 길이는 최댓값 대비 비율 — 축이 0이라 길이를 그대로 비교해도 된다.
 * 막대 색은 원본이 정한 블루→골드 그라디언트 하나다. 항목마다 색을 달리 주지 않는다
 * (구분은 라벨이 한다 — 색까지 쓰면 원본의 막대 어법에서 벗어난다). */
function hbars(rows) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return rows
    .map(
      (r) => `<div class="snu-hbar-row">
        <div class="lbl">${esc(r.label)}</div>
        <div class="bar"><span style="width:${Math.round((r.count / max) * 100)}%"></span></div>
        <div class="n">${fmt(r.count)}</div>
      </div>`,
    )
    .join("");
}

/** 설명 한 줄. 원본은 이 자리에 `.t-body` 를 12px 로 줄여 쓴다. */
function note(html) {
  return `<p class="t-body" style="margin:0 0 12px; font-size:12px">${html}</p>`;
}

/** 1,234 형태로. 소수는 그대로 둔다(점수 51.1 을 51 로 바꾸면 순위가 흐려진다). */
function fmt(n) {
  if (typeof n !== "number") return esc(n);
  return Number.isInteger(n) ? n.toLocaleString("ko-KR") : String(n);
}

/* ---------------------------------------------------------------- 히어로 KPI
 * 원본은 이 유리질 카드에 '가입 파이프라인' 깔때기를 넣는다. 우리에겐 그 4단계가 없어서
 * 04 Newsletter 의 KPI 넷을 넣되, **단계 화살표와 비율 막대는 쓰지 않는다** —
 * 편·명·건·초는 단위가 다르고 이어지는 관계도 아니라서 그리면 거짓말이 된다.
 */

function renderHeroStats(d) {
  const box = document.getElementById("hero-stats");
  const row = document.getElementById("hero-stats-row");
  if (!box || !row || !d.kpis) return;

  row.innerHTML = d.kpis
    .map((k) => {
      // 값이 null 이면 0이 아니라 "잴 수 없음"이다. 0으로 보여주면 거짓말이 된다.
      const missing = k.value === null || k.value === undefined;
      const v = missing ? "—" : fmt(k.value);
      const unit = missing ? "" : esc(k.unit ?? "");
      return `<div class="snu-stage">
          <div class="snu-stage-label">${esc(k.label)}</div>
          <div class="snu-stage-value">${v}<span class="unit">${unit}</span></div>
          ${k.note ? `<div class="snu-stage-note">${esc(k.note)}</div>` : ""}
        </div>`;
    })
    .join("");
  box.hidden = false;
}

/* ---------------------------------------------------------------- 04 Newsletter */

/** 등급 칩의 색은 서버가 준 **키**(active/warm/…)로 고른다.
 * 한글 라벨로 고르면 라벨 문구가 바뀔 때 색이 조용히 틀어진다.
 * 값은 원본 `.status-*` 변종이다 — 다섯 등급이 다섯 색에 1:1로 맞는다. */
const TIER_CLASS = {
  active: "status-joined", // 초록
  warm: "status-pending", // 골드
  dormant: "status-none", // 회색
  unknown: "status-scheduled", // 파랑 — 판단 보류(창 안 발송 0)를 휴면과 구분한다
  unsubscribed: "status-cancelled", // 빨강
};

function tierPill(row) {
  const cls = TIER_CLASS[row.tier_key] ?? TIER_CLASS.unknown;
  return `<span class="status-pill ${cls}">${esc(row.tier)}</span>`;
}

export function renderNewsletter(d) {
  const cats = d.categories.ranked.length
    ? hbars(d.categories.ranked)
    : note("아직 클릭이 없습니다.");

  const dw = d.dwell;
  // 라벨을 짧게 쓴다 — 원본 `.snu-hbar-row .lbl` 은 100px 고정이라 긴 한글이 두 줄로 접힌다.
  // 구간 경계는 위 설명 줄로 옮겼다(같은 정보, 접히지 않는 자리).
  const dwellRows = [
    { label: "💨 튕김", count: dw.bounce },
    { label: "중간", count: dw.middle },
    { label: "🤔 정독", count: dw.engaged },
  ];

  const tiers = d.tiers.filter((t) => t.count > 0);

  return `
    <div class="snu-events-layout">
      <div style="display:flex; flex-direction:column; gap:24px">
        <div class="snu-panel">
          <div class="snu-panel-title">인기 분야 · 최근 ${esc(d.categories.days)}일</div>
          ${note(
            `클릭 ${fmt(d.categories.clicks_total)}건 중 ${fmt(d.categories.matched)}건이
             기사와 매칭됐습니다. 매칭 안 된 클릭은 집계에서 빠집니다.`,
          )}
          ${cats}
        </div>
        <div class="snu-panel">
          <div class="snu-panel-title">읽은 깊이 (추정)</div>
          ${note(
            `원문 체류는 잴 수 없어(남의 서버) <b>같은 편 안의 연속 클릭 간격</b>으로 근사합니다.
             클릭 ${fmt(dw.clicks_total)}건 중 ${fmt(dw.measurable)}건만 측정 가능 ·
             중앙값 ${dw.median_seconds === null ? "—" : Math.round(dw.median_seconds) + "초"}.
             <br>튕김 10초 미만 · 중간 10~60초 · 정독 60초 이상.`,
          )}
          ${hbars(dwellRows)}
        </div>
      </div>
      <div style="display:flex; flex-direction:column; gap:24px">
        <div class="snu-top-presenters">
          <p class="snu-top-title">참여도 TOP ${d.top.length}</p>
          ${
            d.top.length
              ? d.top
                  .map(
                    (r) => `<div class="snu-presenter">
                      <div class="rank">${String(r.rank).padStart(2, "0")}</div>
                      <!-- 등급 칩은 이름과 **같은 줄**에 둔다. 원본 .snu-presenter 의 둘째 줄(.org)은
                           소속처럼 긴 문자열을 담는 자리라, 두 글자 칩을 거기 넣으면 한 줄이 63px 이
                           되고 10줄이면 오른쪽 기둥만 300px 넘게 길어진다(실측). -->
                      <div class="info">
                        <div class="name">${esc(r.name)}${tierPill(r)}</div>
                      </div>
                      <!-- 점수는 항상 소수 한 자리 — 21 과 51.1 이 섞이면 자릿수가 흔들려 읽기 어렵다 -->
                      <div class="count">${r.score.toFixed(1)}<span class="u">점</span></div>
                    </div>`,
                  )
                  .join("")
              : note("아직 점수를 낼 발송 이력이 없습니다.")
          }
        </div>
        <div class="snu-panel">
          <div class="snu-panel-title">등급 분포</div>
          ${
            tiers.length
              ? hbars(tiers.map((t) => ({ label: t.label, count: t.count })))
              : note("분류할 회원이 없습니다.")
          }
        </div>
      </div>
    </div>`;
}

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
    <section class="snu-section" id="section-${s.id}">
      <div class="snu-section-head">
        <div>
          <h2 class="snu-section-title"><span class="num">${s.no}</span>${esc(s.title)}</h2>
          <p class="snu-section-sub" id="sub-${s.id}">${esc(s.sub)}</p>
        </div>
        <div class="snu-hero-ctas" id="actions-${s.id}" style="margin-top:0"></div>
      </div>
      <div id="body-${s.id}"></div>
    </section>`;
}

function placeholder(s) {
  // 같은 "빈 자리"라도 누가 언제 채우는지는 다르다 — 형태로 구분해 계획이 화면에 드러나게 한다.
  const msg = s.mine ? "곧 실제 데이터가 연결됩니다." : "아직 데이터가 연결되지 않았습니다.";
  return `
    <div class="placeholder${s.mine ? " next" : ""}">
      <div class="who">${esc(s.owner ?? "미정")}이 채울 자리</div>
      <div>${msg}</div>
      <div class="hint">app/static/dashboard/dashboard.js → SECTIONS['${esc(s.id)}']</div>
    </div>`;
}

function loading() {
  return `
    <div class="snu-panel">
      <div class="skeleton" style="width:38%"></div>
      <div class="skeleton" style="width:72%"></div>
      <div class="skeleton" style="width:55%"></div>
    </div>`;
}

/** 실패 이유를 화면에 남긴다 — 빈 화면과 고장 난 화면은 구분되어야 한다. */
function errorState(message) {
  return `<div class="snu-panel"><div class="state error">${esc(message)}</div></div>`;
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
    const data = await res.json();
    body.innerHTML = s.render(data);
    // 부제는 집계 범위를 담는다("발송 22편 · 파일럿 25명 기준"). 서버가 준 게 있으면 갈아 끼운다.
    const sub = document.getElementById(`sub-${s.id}`);
    if (sub && data.subtitle) sub.textContent = data.subtitle;
    // 본문 밖(히어로 등)을 채운다. 실패하면 그 자리는 그냥 비어 있게 둔다 — 본문은 이미 떴다.
    if (s.postRender) s.postRender(data);
  } catch (e) {
    body.innerHTML = errorState(`데이터를 불러오지 못했습니다 — ${e && e.message ? e.message : e}`);
  }
}

/* ---------------------------------------------------------------- 시작 */

export function mount(root) {
  root.innerHTML = SECTIONS.map(sectionShell).join("");

  // 섹션이 선언한 버튼을 머리에 단다. 눌렀을 때 하는 일은 섹션이 정한다(대개 모달 열기).
  for (const s of SECTIONS) {
    const box = document.getElementById(`actions-${s.id}`);
    if (!box || !s.actions) continue;
    for (const a of s.actions) {
      const btn = document.createElement("button");
      btn.className = "snu-btn snu-btn-ghost";
      btn.textContent = a.label;
      btn.addEventListener("click", () => a.run());
      box.appendChild(btn);
    }
  }

  // 섹션끼리 기다리지 않게 각자 불러온다 — 하나가 느려도 나머지는 먼저 뜬다.
  SECTIONS.forEach(loadSection);
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("sections");
  if (root) mount(root);
});
