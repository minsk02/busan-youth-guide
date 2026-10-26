const $ = (id) => document.getElementById(id);
const state = { mode: "search", page: 1, selected: new Map(), criteria: null, loading: false };

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function api(path, data) {
  let response;
  try {
    response = await fetch(path, data === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data),
    });
  } catch {
    throw new Error("서버와 연결하지 못했습니다. 연결 상태를 확인한 뒤 다시 시도해주세요.");
  }
  let result;
  try { result = await response.json(); }
  catch { throw new Error("서버 응답을 읽지 못했습니다. 잠시 후 다시 시도해주세요."); }
  if (!response.ok) throw new Error(result.error?.message || "요청을 처리하지 못했습니다.");
  return result;
}

function showMessage(text) {
  $("message").textContent = text;
  $("message").hidden = !text;
}

function period(start, end) {
  return `${start || "확인 불가"} ~ ${end || "확인 불가"}`;
}

function shortDate(value) {
  return value ? value.slice(5).replace("-", ".") : "—";
}

function externalLink(url, label) {
  const link = element("a", label);
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function readFilters() {
  return {
    category: $("category").value || null,
    keywords: $("keywords").value.split(",").map((word) => word.trim()).filter(Boolean),
    target_keyword: $("target").value.trim() || null,
    apply_from: $("apply-from").value || null,
    apply_until: $("apply-until").value || null,
    only_open: $("only-open").checked,
  };
}

function fillFilters(criteria) {
  $("category").value = criteria.category || "";
  $("keywords").value = criteria.keywords.join(", ");
  $("target").value = criteria.target_keyword || "";
  $("apply-from").value = criteria.apply_from || "";
  $("apply-until").value = criteria.apply_until || "";
  $("only-open").checked = criteria.only_open;
}

function statusTag(program) {
  return element("span", program.status_label, `status-tag ${program.status}`);
}

function updateSelection() {
  const count = state.selected.size;
  $("compare-tray").hidden = count === 0;
  document.body.classList.toggle("has-selection", count > 0);
  $("selected-count").textContent = count;
  $("selected-names").textContent = [...state.selected.values()].join(" · ");
  $("open-compare").disabled = count < 2;
  document.querySelectorAll("input[data-program-id]").forEach((input) => {
    input.checked = state.selected.has(Number(input.dataset.programId));
  });
}

function renderCard(program) {
  const card = element("article", null, "program-card");
  const tags = element("div", null, "card-tags");
  tags.append(element("span", program.category || "분야 확인 필요", "category-tag"), statusTag(program));
  card.append(tags, element("h3", program.title));
  const info = element("dl", null, "card-info");
  for (const [label, value] of [["신청기간", period(program.application_start, program.application_end)], ["주관기관", program.organizer || "확인 불가"]]) {
    info.append(element("dt", label), element("dd", value));
  }
  card.append(info);
  if (program.reasons.length) {
    const reasons = element("div", null, "reasons");
    reasons.append(element("p", "이 조건과 맞는 점"));
    program.reasons.forEach((reason) => reasons.append(element("p", `· ${reason}`)));
    card.append(reasons);
  }
  const bottom = element("div", null, "card-bottom");
  const label = element("label", null, "compare-label");
  const checkbox = element("input");
  checkbox.type = "checkbox";
  checkbox.dataset.programId = program.id;
  checkbox.checked = state.selected.has(program.id);
  checkbox.setAttribute("aria-label", `${program.title} 비교 대상으로 선택`);
  checkbox.addEventListener("change", () => {
    if (checkbox.checked && state.selected.size >= 3) {
      checkbox.checked = false;
      showMessage("최대 3개까지 비교할 수 있습니다. 기존 선택을 해제해주세요.");
      return;
    }
    if (checkbox.checked) state.selected.set(program.id, program.title);
    else state.selected.delete(program.id);
    updateSelection();
  });
  label.append(checkbox, element("span", "비교에 담기"));
  const detailButton = element("button", "자세히 보기 →", "detail-button");
  detailButton.type = "button";
  detailButton.addEventListener("click", () => openDetail(program.id));
  bottom.append(label, detailButton);
  card.append(bottom);
  return card;
}

async function loadResults(page = 1) {
  if (state.loading) return;
  state.loading = true;
  $("results").setAttribute("aria-busy", "true");
  $("result-count").textContent = "불러오는 중…";
  showMessage("");
  try {
    const result = await api("/api/search", { criteria: state.criteria || readFilters(), mode: state.mode, page });
    state.page = result.page;
    $("results").replaceChildren(...result.items.map(renderCard));
    $("result-count").textContent = `총 ${result.total.toLocaleString()}건`;
    if (!result.total || !result.items.length) showMessage(result.notice);
    $("pagination").replaceChildren();
    if (result.pages > 1) {
      const previous = element("button", "← 이전");
      previous.disabled = result.page <= 1;
      previous.addEventListener("click", () => loadResults(result.page - 1));
      const next = element("button", "다음 →");
      next.disabled = result.page >= result.pages;
      next.addEventListener("click", () => loadResults(result.page + 1));
      $("pagination").append(previous, element("span", `${result.page} / ${result.pages}`), next);
    }
  } catch (error) {
    $("results").replaceChildren();
    $("pagination").replaceChildren();
    $("result-count").textContent = "조회 실패";
    showMessage(error.message);
  } finally {
    state.loading = false;
    $("results").setAttribute("aria-busy", "false");
  }
}

async function openDetail(id) {
  try {
    const program = await api(`/api/programs/${id}`);
    const title = element("h2", program.title);
    title.id = "detail-title";
    const list = element("dl", null, "detail-list");
    for (const [label, value] of [
      ["분야", program.category], ["신청기간", period(program.application_start, program.application_end)],
      ["운영기간", period(program.schedule_start, program.schedule_end)], ["지원 대상", program.target_text],
      ["원천 상태", program.source_status], ["주관기관", program.organizer], ["문의", program.contact_phone],
      ["등록일", program.source_registered_at], ["수집 시점", program.fetched_at?.replace("T", " ")],
    ]) list.append(element("dt", label), element("dd", value || "확인 불가"));
    const links = element("div", null, "detail-links");
    if (program.homepage_url) links.append(externalLink(program.homepage_url, "안내 홈페이지 ↗"));
    else links.append(element("span", "홈페이지 주소 확인 불가"));
    links.append(externalLink(program.source_url, "공공데이터 출처 ↗"));
    $("detail-content").replaceChildren(statusTag(program), title, list, links, element("p", program.notice, "detail-notice"));
    $("detail-dialog").showModal();
  } catch (error) { showMessage(error.message); }
}

async function openComparison() {
  try {
    const result = await api("/api/compare", { ids: [...state.selected.keys()] });
    const table = element("table", null, "comparison-table");
    const head = element("thead");
    const titleRow = element("tr");
    titleRow.append(element("th", "프로그램"));
    result.items.forEach((item) => titleRow.append(element("td", item.title)));
    head.append(titleRow);
    const tbody = element("tbody");
    for (const [label, format] of [
      ["분야", (item) => item.category], ["상태", (item) => item.status_label],
      ["신청기간", (item) => period(item.application_start, item.application_end)],
      ["운영기간", (item) => period(item.schedule_start, item.schedule_end)],
      ["지원 대상", (item) => item.target_text], ["주관기관", (item) => item.organizer],
      ["문의", (item) => item.contact_phone],
    ]) {
      const row = element("tr");
      const heading = element("th", label); heading.scope = "row";
      row.append(heading);
      result.items.forEach((item) => row.append(element("td", format(item) || "확인 불가")));
      tbody.append(row);
    }
    const linkRow = element("tr");
    linkRow.append(element("th", "원문 확인"));
    result.items.forEach((item) => {
      const cell = element("td");
      cell.append(externalLink(item.homepage_url || item.source_url, item.homepage_url ? "홈페이지 ↗" : "데이터 출처 ↗"));
      linkRow.append(cell);
    });
    tbody.append(linkRow);
    table.append(head, tbody);
    $("compare-content").replaceChildren(table, element("p", "대상과 실제 접수 여부는 각 원문에서 확인해주세요.", "detail-notice"));
    $("compare-dialog").showModal();
  } catch (error) { showMessage(error.message); }
}

$("ai-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("ai-submit").disabled = true;
  $("ai-submit").textContent = "조건 읽는 중…";
  $("ai-feedback").classList.remove("error");
  $("ai-feedback").textContent = "질문을 검색 조건으로 정리하고 있습니다.";
  try {
    const result = await api("/api/interpret", { query: $("question").value.trim() });
    fillFilters(result.criteria);
    $("ai-feedback").textContent = "아래 조건에 반영했습니다. 확인한 뒤 ‘이 조건으로 검색’을 눌러주세요.";
    const unsupported = result.unsupported_conditions;
    $("condition-note").textContent = unsupported.length
      ? `적용하지 못한 조건: ${unsupported.join(", ")}. 이 조건들은 확인되지 않았습니다. 검색 전에 확인해주세요.`
      : "AI가 정리한 조건입니다. 필요하면 수정한 뒤 검색해주세요.";
    $("filter-form").scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    $("ai-feedback").textContent = error.message;
    $("ai-feedback").classList.add("error");
  } finally {
    $("ai-submit").disabled = false;
    $("ai-submit").textContent = "조건 읽기 →";
  }
});

$("filter-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.loading) return;
  state.criteria = readFilters();
  loadResults();
});
$("reset").addEventListener("click", () => {
  if (state.loading) return;
  $("filter-form").reset();
  state.criteria = readFilters();
  $("condition-note").textContent = "조건을 초기화했습니다. 현재 신청기간인 항목을 보여줍니다.";
  loadResults();
});
for (const mode of ["search", "recommend"]) {
  $(`${mode}-tab`).addEventListener("click", () => {
    if (state.loading) return;
    state.mode = mode;
    for (const name of ["search", "recommend"]) {
      $(`${name}-tab`).classList.toggle("active", mode === name);
      $(`${name}-tab`).setAttribute("aria-pressed", String(mode === name));
    }
    $("mode-help").textContent = mode === "recommend"
      ? "현재 신청기간인 항목을 먼저, 조건 일치 점수 순으로 추천합니다. 같은 점수는 마감일 순입니다."
      : "신청기간 내 항목을 먼저, 마감일이 가까운 순서로 보여줍니다.";
    state.criteria = readFilters();
    loadResults();
  });
}
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => {
  $("question").value = button.dataset.example;
  $("question").focus();
}));
document.querySelectorAll(".close-dialog").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
$("clear-selection").addEventListener("click", () => { state.selected.clear(); updateSelection(); });
$("open-compare").addEventListener("click", openComparison);

async function start() {
  try {
    const status = await api("/api/status");
    $("total-count").textContent = status.total.toLocaleString();
    $("open-count").textContent = status.open_count.toLocaleString();
    $("as-of").textContent = shortDate(status.as_of);
    $("freshness").textContent = status.fetched_at ? `수집 ${status.fetched_at.slice(0, 16).replace("T", " ")}` : "아직 수집된 데이터가 없습니다.";
    if (status.last_sync_status === "failed") $("freshness").textContent += " · 최근 수집 실패, 이전 자료 사용";
    if (!status.ai_configured) {
      $("ai-submit").disabled = true;
      $("ai-feedback").textContent = "AI 연결이 설정되지 않았습니다. 직접 조건을 골라 검색할 수 있습니다.";
    }
  } catch (error) { showMessage(error.message); }
  state.criteria = readFilters();
  await loadResults();
}
start();
