/**
 * Pokémon Card Tracker – front-end: search, price charts, watchlists.
 */

const API = "/api";

let currentPage = 1;
let totalPages = 1;
let selectedCardId = null;
let currentWatchlistId = null;
let priceChart = null;

// ---------- API helpers ----------
async function get(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function post(path, body = null) {
  const opts = { method: "POST" };
  if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function del(path) {
  const r = await fetch(API + path, { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ---------- Sets (for filter) ----------
async function loadSets() {
  const data = await get("/sets");
  const sel = document.getElementById("setFilter");
  sel.innerHTML = '<option value="">All sets</option>';
  (data.sets || []).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name || s.id;
    sel.appendChild(opt);
  });
}

// ---------- Available sets (add more) ----------
async function loadAvailableSets() {
  const data = await get("/sets/available");
  const sel = document.getElementById("availableSets");
  const first = sel.options[0];
  sel.innerHTML = "";
  sel.appendChild(first);
  (data.sets || []).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id || "";
    const count = s.cardCount != null ? ` (${s.cardCount} cards)` : "";
    opt.textContent = (s.name || s.id) + count + (s.alreadyAdded ? " ✓ added" : "");
    opt.disabled = !!s.alreadyAdded;
    sel.appendChild(opt);
  });
}

async function importSet() {
  const setId = document.getElementById("availableSets").value;
  const limitInput = document.getElementById("importLimit").value.trim();
  const statusEl = document.getElementById("importStatus");
  if (!setId) {
    statusEl.textContent = "Choose a set first.";
    statusEl.className = "import-status error";
    return;
  }
  const btn = document.getElementById("importSetBtn");
  btn.disabled = true;
  statusEl.textContent = "Importing…";
  statusEl.className = "import-status";
  try {
    const url = "/ingest/set/" + encodeURIComponent(setId) + (limitInput ? "?limit=" + Math.min(500, parseInt(limitInput, 10) || 0) : "");
    const result = await post(url);
    statusEl.textContent = "Imported " + (result.stored ?? 0) + " cards from " + setId + ".";
    statusEl.className = "import-status success";
    document.getElementById("importLimit").value = "";
    await loadSets();
    await loadAvailableSets();
  } catch (e) {
    statusEl.textContent = "Import failed: " + e.message;
    statusEl.className = "import-status error";
  }
  btn.disabled = false;
}

// ---------- Search ----------
function buildQuery() {
  const q = document.getElementById("searchInput").value.trim();
  const setId = document.getElementById("setFilter").value.trim();
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (setId) params.set("set_id", setId);
  params.set("page", currentPage);
  params.set("per_page", 20);
  return "?" + params.toString();
}

async function doSearch() {
  currentPage = 1;
  await runSearch();
}

async function runSearch() {
  const container = document.getElementById("searchResults");
  const paginationEl = document.getElementById("searchPagination");
  container.classList.add("loading");
  try {
    const data = await get("/cards" + buildQuery());
    totalPages = Math.max(1, Math.ceil((data.total || 0) / (data.per_page || 20)));
    renderCardGrid(container, data.cards || [], true);
    renderPagination(paginationEl, data.page, totalPages);
  } catch (e) {
    container.innerHTML = '<p class="empty-msg">Search failed: ' + e.message + "</p>";
    paginationEl.innerHTML = "";
  }
  container.classList.remove("loading");
}

function renderPagination(el, page, total) {
  el.innerHTML = "";
  if (total <= 1) return;
  const prev = document.createElement("button");
  prev.textContent = "Previous";
  prev.disabled = page <= 1;
  prev.addEventListener("click", () => {
    currentPage = Math.max(1, page - 1);
    runSearch();
  });
  el.appendChild(prev);
  const span = document.createElement("span");
  span.textContent = ` Page ${page} of ${total} `;
  span.className = "pagination-info";
  el.appendChild(span);
  const next = document.createElement("button");
  next.textContent = "Next";
  next.disabled = page >= total;
  next.addEventListener("click", () => {
    currentPage = Math.min(total, page + 1);
    runSearch();
  });
  el.appendChild(next);
}

function renderCardGrid(container, cards, fromSearch = false) {
  container.innerHTML = "";
  if (!cards.length) {
    container.innerHTML = '<p class="empty-msg">No cards found.</p>';
    return;
  }
  cards.forEach((card) => {
    const priceStr = formatCardPrice(card.latestPrice);
    const tile = document.createElement("div");
    tile.className = "card-tile" + (selectedCardId === card.id ? " selected" : "");
    tile.dataset.cardId = card.id;
    tile.innerHTML = `
      <img src="${escapeAttr(card.imageUrl || "/static/placeholder-card.svg")}" alt="${escapeAttr(card.name)}" loading="lazy" onerror="this.src='/static/placeholder-card.svg'"/>
      <div class="name">${escapeHtml(card.name)}</div>
      ${priceStr ? `<div class="card-price">${escapeHtml(priceStr)}</div>` : ""}
      <div class="meta">${escapeHtml((card.set && card.set.name) || card.id)}</div>
      <div class="actions"></div>
    `;
    const actions = tile.querySelector(".actions");
    const addBtn = document.createElement("button");
    addBtn.className = "btn-sm";
    addBtn.textContent = "Add to list";
    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      addCardToCurrentWatchlist(card.id);
    });
    actions.appendChild(addBtn);
    if (fromSearch) {
      tile.addEventListener("click", () => selectCard(card.id));
    } else {
      const removeBtn = document.createElement("button");
      removeBtn.className = "btn-sm remove";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeCardFromWatchlist(currentWatchlistId, card.id);
      });
      actions.appendChild(removeBtn);
      tile.addEventListener("click", () => selectCard(card.id));
    }
    container.appendChild(tile);
  });
}

function escapeAttr(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatCardPrice(latestPrice) {
  if (!latestPrice) return "";
  const parts = [];
  if (latestPrice.tcgMarket != null) parts.push("$" + Number(latestPrice.tcgMarket).toFixed(2));
  if (latestPrice.cmTrend != null) parts.push("€" + Number(latestPrice.cmTrend).toFixed(2));
  return parts.length ? parts.join(" · ") : "";
}

function selectCard(cardId) {
  selectedCardId = cardId;
  document.querySelectorAll(".card-tile").forEach((t) => t.classList.toggle("selected", t.dataset.cardId === cardId));
  document.getElementById("chartCardName").textContent = "Loading…";
  loadPriceChart(cardId);
}

// ---------- Price chart ----------
const priceSourceKey = {
  tcg_market: { obj: "tcg", key: "market" },
  tcg_low: { obj: "tcg", key: "low" },
  cm_trend: { obj: "cardmarket", key: "trend" },
  cm_avg: { obj: "cardmarket", key: "avg" },
};

async function loadPriceChart(cardId) {
  const days = document.getElementById("daysFilter").value;
  const url = `/cards/${encodeURIComponent(cardId)}/prices` + (days ? "?days=" + days : "");
  const data = await get(url);
  const cardRes = await get("/cards/" + encodeURIComponent(cardId));
  document.getElementById("chartCardName").textContent = cardRes.name + " (" + cardId + ")";

  const source = document.getElementById("priceSource").value;
  const { obj, key } = priceSourceKey[source] || priceSourceKey.tcg_market;
  const points = (data.prices || []).map((p) => ({
    t: p.recordedAt,
    y: p[obj] && p[obj][key] != null ? p[obj][key] : null,
  })).filter((d) => d.y != null);

  const ctx = document.getElementById("priceChart").getContext("2d");
  if (priceChart) priceChart.destroy();
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: points.map((d) => d.t ? new Date(d.t).toLocaleDateString() : ""),
      datasets: [
        {
          label: source.replace(/_/g, " "),
          data: points.map((d) => d.y),
          borderColor: "#22c55e",
          backgroundColor: "rgba(34, 197, 94, 0.1)",
          fill: true,
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#a1a1aa", maxTicksLimit: 8 },
        },
        y: {
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#a1a1aa" },
        },
      },
    },
  });
}

async function refreshPrice() {
  if (!selectedCardId) return;
  await post("/cards/" + encodeURIComponent(selectedCardId) + "/refresh");
  await loadPriceChart(selectedCardId);
}

// ---------- Watchlists ----------
async function loadWatchlists() {
  const data = await get("/watchlists");
  const tabs = document.getElementById("watchlistTabs");
  tabs.innerHTML = "";
  (data.watchlists || []).forEach((w) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "watchlist-tab" + (currentWatchlistId === w.id ? " active" : "");
    tab.dataset.watchlistId = w.id;
    tab.innerHTML = escapeHtml(w.name) + " (" + (w.cardCount || 0) + ") <span class=\"delete-tab\" data-action=\"delete\">×</span>";
    tab.addEventListener("click", (e) => {
      if (e.target.dataset.action === "delete") {
        e.stopPropagation();
        deleteWatchlist(w.id);
        return;
      }
      setCurrentWatchlist(w.id);
    });
    tabs.appendChild(tab);
  });
}

function setCurrentWatchlist(id) {
  currentWatchlistId = id;
  document.querySelectorAll(".watchlist-tab").forEach((t) => t.classList.toggle("active", parseInt(t.dataset.watchlistId, 10) === id));
  loadWatchlistCards(id);
}

async function loadWatchlistCards(watchlistId) {
  const container = document.getElementById("watchlistCards");
  try {
    const data = await get("/watchlists/" + watchlistId);
    renderCardGrid(container, data.cards || [], false);
  } catch (e) {
    container.innerHTML = '<p class="empty-msg">Failed to load watchlist.</p>';
  }
}

async function createWatchlist() {
  const name = document.getElementById("newWatchlistName").value.trim() || "My Watchlist";
  const w = await post("/watchlists", { name });
  document.getElementById("newWatchlistName").value = "";
  await loadWatchlists();
  setCurrentWatchlist(w.id);
}

async function deleteWatchlist(id) {
  if (!confirm("Delete this watchlist?")) return;
  await del("/watchlists/" + id);
  if (currentWatchlistId === id) {
    currentWatchlistId = null;
    document.getElementById("watchlistCards").innerHTML = '<p class="empty-msg">Select or create a watchlist.</p>';
  }
  await loadWatchlists();
}

async function addCardToCurrentWatchlist(cardId) {
  if (!currentWatchlistId) {
    const name = prompt("Create a new watchlist first. Name:");
    if (!name) return;
    const w = await post("/watchlists", { name: name.trim() || "My Watchlist" });
    await loadWatchlists();
    currentWatchlistId = w.id;
    document.querySelectorAll(".watchlist-tab").forEach((t) => t.classList.toggle("active", parseInt(t.dataset.watchlistId, 10) === w.id));
  }
  await post("/watchlists/" + currentWatchlistId + "/cards/" + encodeURIComponent(cardId));
  await loadWatchlistCards(currentWatchlistId);
  await loadWatchlists();
}

async function removeCardFromWatchlist(watchlistId, cardId) {
  await del("/watchlists/" + watchlistId + "/cards/" + encodeURIComponent(cardId));
  await loadWatchlistCards(watchlistId);
  await loadWatchlists();
}

// ---------- Event bindings ----------
document.getElementById("searchBtn").addEventListener("click", doSearch);
document.getElementById("searchInput").addEventListener("keydown", (e) => e.key === "Enter" && doSearch());
document.getElementById("priceSource").addEventListener("change", () => selectedCardId && loadPriceChart(selectedCardId));
document.getElementById("daysFilter").addEventListener("change", () => selectedCardId && loadPriceChart(selectedCardId));
document.getElementById("refreshPrices").addEventListener("click", refreshPrice);
document.getElementById("createWatchlist").addEventListener("click", createWatchlist);
document.getElementById("importSetBtn").addEventListener("click", importSet);

// ---------- Init ----------
(async function init() {
  await loadSets();
  await loadAvailableSets();
  await loadWatchlists();
  const firstTab = document.querySelector(".watchlist-tab");
  if (firstTab) setCurrentWatchlist(parseInt(firstTab.dataset.watchlistId, 10));
})();
