/* 푸드테크 대시보드 — 섹션 등록과 렌더 (T-027 1단계)
 *
 * ┌─ 새 섹션을 만들려면 여기만 보면 된다 ────────────────────────────────┐
 * │ 1. 아래 SECTIONS 배열에 항목을 추가한다.                              │
 * │ 2. endpoint 에 JSON API 주소를 적는다 (서버는 app/routes/admin.py).   │
 * │ 3. render(data) 를 채운다 — 응답을 받아 섹션 본문 HTML 문자열을 만든다.│
 * │ 4. 조작이 필요하면 actions 에 버튼을 선언한다 — 상세는 모달로 연다.   │
 * │ endpoint 를 null 로 두면 "아직 비어 있음" 자리로 그려진다.            │
 * └──────────────────────────────────────────────────────────────────────┘
 *
 * 데이터를 여기서 직접 가공하지 않는다. 계산은 서버가 끝내서 보내고, 이 파일은 그리기만 한다.
 * (그래야 같은 숫자가 화면과 CSV·API에서 갈라지지 않는다.)
 */

import { openMembersModal } from "./members-modal.js";

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
    actions: [{ label: "👥 회원 관리", run: openMembersModal }],
  },
];

/* ---------------------------------------------------------------- 공통 조각
 * 아래 세 개는 어느 섹션에서나 쓴다. 새 섹션도 이걸 조합해 만들면 모양이 저절로 맞는다.
 */

/** KPI 한 줄. note 는 집계 범위다 — 나란히 놓인 숫자의 기준이 다를 수 있어 반드시 보여준다. */
function kpis(items) {
  const cell = (k) => {
    // 값이 null 이면 0이 아니라 "잴 수 없음"이다. 0%로 보여주면 거짓말이 된다.
    const v = k.value === null || k.value === undefined ? "—" : fmt(k.value);
    const unit = k.value === null || k.value === undefined ? "" : esc(k.unit ?? "");
    return `<div class="kpi">
        <div class="v">${v}<span class="u">${unit}</span></div>
        <div class="k">${esc(k.label)}${k.note ? ` · ${esc(k.note)}` : ""}</div>
      </div>`;
  };
  return `<div class="kpis">${items.map(cell).join("")}</div>`;
}

/** 가로 막대 목록. 길이는 최댓값 대비 비율 — 축이 0이라 길이를 그대로 비교해도 된다. */
function hbars(rows, { className = "" } = {}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return rows
    .map(
      (r) => `<div class="hbar ${esc(r.variant ?? className)}">
        <div class="lbl">${esc(r.label)}</div>
        <div class="track"><span class="fill" style="width:${Math.round((r.count / max) * 100)}%"></span></div>
        <div class="n">${fmt(r.count)}</div>
      </div>`,
    )
    .join("");
}

/** 1,234 형태로. 소수는 그대로 둔다(점수 51.1 을 51 로 바꾸면 순위가 흐려진다). */
function fmt(n) {
  if (typeof n !== "number") return esc(n);
  return Number.isInteger(n) ? n.toLocaleString("ko-KR") : String(n);
}

/* ---------------------------------------------------------------- 04 Newsletter */

/** 등급 칩의 색은 서버가 준 **키**(active/warm/…)로 고른다.
 * 한글 라벨로 고르면 라벨 문구가 바뀔 때 색이 조용히 틀어진다. */
const TIER_KEYS = ["active", "warm", "dormant", "unknown", "unsubscribed"];

function tierChip(row) {
  const key = TIER_KEYS.includes(row.tier_key) ? row.tier_key : "unknown";
  return `<span class="chip chip-${key}">${esc(row.tier)}</span>`;
}

export function renderNewsletter(d) {
  const cats = d.categories.ranked.length
    ? hbars(d.categories.ranked)
    : `<p class="note-line">아직 클릭이 없습니다.</p>`;

  const dw = d.dwell;
  const dwellRows = [
    { label: "💨 튕김 (10초 미만)", count: dw.bounce, variant: "bounce" },
    { label: "중간 (10~60초)", count: dw.middle, variant: "middle" },
    { label: "🤔 정독 (60초 이상)", count: dw.engaged, variant: "engaged" },
  ];

  const tiers = d.tiers.filter((t) => t.count > 0);

  return `
    ${kpis(d.kpis)}
    <div style="height:16px"></div>
    <div class="cols">
      <div class="stack">
        <div class="panel">
          <p class="panel-title">인기 분야 · 최근 ${esc(d.categories.days)}일</p>
          <p class="note-line">
            클릭 ${fmt(d.categories.clicks_total)}건 중 ${fmt(d.categories.matched)}건이
            기사와 매칭됐습니다. 매칭 안 된 클릭은 집계에서 빠집니다.
          </p>
          ${cats}
        </div>
        <div class="panel">
          <p class="panel-title">읽은 깊이 (추정)</p>
          <p class="note-line">
            원문 체류는 잴 수 없어(남의 서버) <b>같은 편 안의 연속 클릭 간격</b>으로 근사합니다.
            클릭 ${fmt(dw.clicks_total)}건 중 ${fmt(dw.measurable)}건만 측정 가능 ·
            중앙값 ${dw.median_seconds === null ? "—" : Math.round(dw.median_seconds) + "초"}.
          </p>
          ${hbars(dwellRows)}
        </div>
      </div>
      <div class="stack">
        <div class="panel">
          <p class="panel-title">참여도 TOP ${d.top.length}</p>
          ${
            d.top.length
              ? d.top
                  .map(
                    (r) => `<div class="rank-row">
                      <div class="rk">${String(r.rank).padStart(2, "0")}</div>
                      <div class="nm">${esc(r.name)}${tierChip(r)}</div>
                      <!-- 점수는 항상 소수 한 자리 — 21 과 51.1 이 섞이면 자릿수가 흔들려 읽기 어렵다 -->
                      <div class="sc">${r.score.toFixed(1)}<span class="u">점</span></div>
                    </div>`,
                  )
                  .join("")
              : `<p class="note-line">아직 점수를 낼 발송 이력이 없습니다.</p>`
          }
        </div>
        <div class="panel">
          <p class="panel-title">등급 분포</p>
          ${
            tiers.length
              ? hbars(tiers.map((t) => ({ label: t.label, count: t.count })))
              : `<p class="note-line">분류할 회원이 없습니다.</p>`
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
    const data = await res.json();
    body.innerHTML = s.render(data);
    // 부제는 집계 범위를 담는다("발송 22편 · 파일럿 25명 기준"). 서버가 준 게 있으면 갈아 끼운다.
    const sub = document.getElementById(`sub-${s.id}`);
    if (sub && data.subtitle) sub.textContent = data.subtitle;
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
      btn.className = "btn";
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
