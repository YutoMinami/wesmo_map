import { createRenderer } from "./js/domRenderers.js?v=20260314a";
import { searchAddress } from "./js/searchProviders.js?v=20260314a";
import {
  buildCategoryOptions,
  buildStatusMessage,
  filterShops,
  groupShopsForMap,
} from "./js/shopUtils.js?v=20260314a";

const DEFAULT_CENTER = [34.707463069292885, 135.49508639737775];
const DEFAULT_ZOOM = 13;
const SEARCH_ZOOM = 14;
const DEFAULT_RADIUS_KM = 3;
const ADDRESS_SEARCH_PROVIDER = "gsi";

const map = L.map("map").setView(DEFAULT_CENTER, DEFAULT_ZOOM);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const elements = {
  locateButton: document.getElementById("locate-button"),
  addressForm: document.getElementById("address-form"),
  addressInput: document.getElementById("address-input"),
  addressSearchButton: document.getElementById("address-search-button"),
  searchResultsPanel: document.getElementById("search-results-panel"),
  searchResultCount: document.getElementById("search-result-count"),
  searchResultList: document.getElementById("search-result-list"),
  radiusSelect: document.getElementById("radius-select"),
  categorySelect: document.getElementById("category-select"),
  statusText: document.getElementById("status-text"),
  resultCount: document.getElementById("result-count"),
  shopList: document.getElementById("shop-list"),
};

const renderer = createRenderer(map, elements);

const state = {
  shops: [],
  currentPosition: null,
};

init().catch((error) => {
  console.error(error);
  renderer.setStatus("加盟店データの読み込みに失敗しました。");
});

async function init() {
  const response = await fetch("./data/shops.json");
  state.shops = await response.json();
  populateCategorySelect(state.shops);
  bindEvents();
  refreshResults();
}

function bindEvents() {
  elements.locateButton.addEventListener("click", handleLocateClick);
  elements.addressForm.addEventListener("submit", handleAddressSearch);
  elements.radiusSelect.addEventListener("change", refreshResults);
  elements.categorySelect.addEventListener("change", refreshResults);
  map.on("moveend", () => {
    if (!state.currentPosition) {
      refreshResults();
    }
  });
}

function populateCategorySelect(shops) {
  const options = buildCategoryOptions(shops);
  elements.categorySelect.innerHTML = [
    '<option value="">すべて</option>',
    ...options.map(
      (option) =>
        `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`,
    ),
  ].join("");
}

function handleLocateClick() {
  if (!navigator.geolocation) {
    renderer.setStatus("このブラウザは現在地取得に対応していません。");
    return;
  }

  renderer.setStatus("現在地を取得しています...");

  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      state.currentPosition = {
        lat: coords.latitude,
        lng: coords.longitude,
      };
      elements.addressInput.value = "";
      renderer.clearAddressCandidates();
      refreshResults();
    },
    (error) => {
      console.error(error);
      renderer.setStatus(
        "現在地を取得できませんでした。位置情報の許可を確認してください。",
      );
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 60000,
    },
  );
}

async function handleAddressSearch(event) {
  event.preventDefault();

  const query = elements.addressInput.value.trim();
  if (!query) {
    renderer.setStatus("住所か駅名を入力してください。");
    elements.addressInput.focus();
    return;
  }

  renderer.setAddressSearchPending(true);
  renderer.setStatus("入力した住所を検索しています...");

  try {
    const results = await searchAddress(query, ADDRESS_SEARCH_PROVIDER);
    if (results.length === 0) {
      throw new Error("No address match.");
    }

    renderer.renderAddressCandidates(query, results, (result) => {
      selectAddressCandidate(result, query);
    });

    if (results.length === 1) {
      selectAddressCandidate(results[0], query);
    } else {
      renderer.setStatus(`「${query}」の候補から選んでください。`);
    }
  } catch (error) {
    console.error(error);
    renderer.clearAddressCandidates();
    renderer.setStatus(
      "住所を見つけられませんでした。地名や駅名を変えて試してください。",
    );
  } finally {
    renderer.setAddressSearchPending(false);
  }
}

function selectAddressCandidate(result, query) {
  state.currentPosition = null;
  map.setView([result.lat, result.lng], SEARCH_ZOOM);
  refreshResults();
  renderer.setStatus(`「${query}」の候補: ${result.label}`);
}

function refreshResults() {
  const radiusKm = Number(elements.radiusSelect.value || DEFAULT_RADIUS_KM);
  const category = elements.categorySelect.value;
  const searchCenter = state.currentPosition ?? {
    lat: map.getCenter().lat,
    lng: map.getCenter().lng,
  };

  const filteredShops = filterShops(state.shops, {
    searchCenter,
    radiusKm,
    category,
  });
  const groupedShops = groupShopsForMap(filteredShops);

  renderer.renderSearchArea(searchCenter, radiusKm, state.currentPosition);
  renderer.renderShops(groupedShops);
  renderer.renderShopList(filteredShops);
  renderer.setStatus(
    buildStatusMessage({
      radiusKm,
      count: filteredShops.length,
      currentPosition: state.currentPosition,
      category,
    }),
  );
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
