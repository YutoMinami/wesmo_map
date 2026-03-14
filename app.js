import { createRenderer } from "./js/domRenderers.js?v=20260314c";
import { searchAddress } from "./js/searchProviders.js?v=20260314c";
import {
  buildStatusMessage,
  filterShops,
  groupShopsForMap,
} from "./js/shopUtils.js?v=20260314c";

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
  categoryChipList: document.getElementById("category-chip-list"),
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
  allShops: [],
  loadedShops: new Map(),
  loadedPrefectures: new Set(),
  prefectureIndex: null,
  currentPosition: null,
};

init().catch((error) => {
  console.error(error);
  renderer.setStatus("加盟店データの読み込みに失敗しました。");
});

async function init() {
  state.prefectureIndex = await loadPrefectureIndex();
  populateCategorySelect(state.prefectureIndex);
  bindEvents();
  await refreshResults();
}

function bindEvents() {
  elements.locateButton.addEventListener("click", handleLocateClick);
  elements.addressForm.addEventListener("submit", handleAddressSearch);
  elements.radiusSelect.addEventListener("change", () => {
    void refreshResults();
  });
  elements.categorySelect.addEventListener("change", () => {
    updateCategoryChips();
    void refreshResults();
  });
  map.on("moveend", () => {
    if (!state.currentPosition) {
      void refreshResults();
    }
  });
}

function populateCategorySelect(indexData) {
  const options = indexData?.categories ?? [];
  elements.categorySelect.innerHTML = [
    '<option value="">すべて</option>',
    ...options.map(
      (option) =>
        `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`,
    ),
  ].join("");
  elements.categoryChipList.innerHTML = [
    '<button class="category-chip is-active" type="button" data-category="">すべて</button>',
    ...options.map(
      (option) =>
        `<button class="category-chip" type="button" data-category="${escapeHtml(option.value)}">${escapeHtml(option.label)}</button>`,
    ),
  ].join("");

  elements.categoryChipList
    .querySelectorAll("[data-category]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        elements.categorySelect.value = button.dataset.category ?? "";
        updateCategoryChips();
        void refreshResults();
      });
    });
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
      void refreshResults();
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
  void refreshResults();
  renderer.setStatus(`「${query}」の候補: ${result.label}`);
}

async function refreshResults() {
  const radiusKm = Number(elements.radiusSelect.value || DEFAULT_RADIUS_KM);
  const category = elements.categorySelect.value;
  const searchCenter = state.currentPosition ?? {
    lat: map.getCenter().lat,
    lng: map.getCenter().lng,
  };
  await ensureShopsLoaded(searchCenter, radiusKm);

  const filteredShops = filterShops(state.allShops, {
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

function updateCategoryChips() {
  const currentCategory = elements.categorySelect.value;
  elements.categoryChipList
    .querySelectorAll("[data-category]")
    .forEach((button) => {
      button.classList.toggle(
        "is-active",
        (button.dataset.category ?? "") === currentCategory,
      );
    });
}

async function loadPrefectureIndex() {
  try {
    const response = await fetch("./data/prefectures/index.json");
    if (!response.ok) {
      throw new Error(`Failed to load prefecture index: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error(error);
    const response = await fetch("./data/shops.json");
    state.allShops = await response.json();
    return { categories: buildFallbackCategories(state.allShops), prefectures: [] };
  }
}

async function ensureShopsLoaded(searchCenter, radiusKm) {
  if (!state.prefectureIndex?.prefectures?.length) {
    return;
  }

  const neededPrefectures = findIntersectingPrefectures(
    state.prefectureIndex.prefectures,
    searchCenter,
    radiusKm,
  );

  const pendingLoads = neededPrefectures
    .filter((prefecture) => !state.loadedPrefectures.has(prefecture.code))
    .map(async (prefecture) => {
      const response = await fetch(`./data/prefectures/${prefecture.code}.json`);
      if (!response.ok) {
        throw new Error(`Failed to load prefecture JSON: ${prefecture.code}`);
      }
      const shops = await response.json();
      for (const shop of shops) {
        state.loadedShops.set(shop.id, shop);
      }
      state.loadedPrefectures.add(prefecture.code);
    });

  if (pendingLoads.length > 0) {
    await Promise.all(pendingLoads);
    state.allShops = [...state.loadedShops.values()];
  }
}

function findIntersectingPrefectures(prefectures, searchCenter, radiusKm) {
  const radiusBounds = buildRadiusBounds(searchCenter, radiusKm);
  return prefectures.filter((prefecture) =>
    boundsIntersect(radiusBounds, {
      minLat: Number(prefecture.minLat),
      maxLat: Number(prefecture.maxLat),
      minLng: Number(prefecture.minLng),
      maxLng: Number(prefecture.maxLng),
    }),
  );
}

function buildRadiusBounds(searchCenter, radiusKm) {
  const latDelta = radiusKm / 111;
  const lngDelta =
    radiusKm /
    Math.max(111 * Math.cos((searchCenter.lat * Math.PI) / 180), 0.01);
  return {
    minLat: searchCenter.lat - latDelta,
    maxLat: searchCenter.lat + latDelta,
    minLng: searchCenter.lng - lngDelta,
    maxLng: searchCenter.lng + lngDelta,
  };
}

function boundsIntersect(left, right) {
  return !(
    left.maxLat < right.minLat ||
    left.minLat > right.maxLat ||
    left.maxLng < right.minLng ||
    left.minLng > right.maxLng
  );
}

function buildFallbackCategories(shops) {
  const options = new Map();
  for (const shop of shops) {
    if (shop.category && shop.categoryLabel && !options.has(shop.category)) {
      options.set(shop.category, {
        value: shop.category,
        label: shop.categoryLabel,
      });
    }
  }
  return [...options.values()].sort((left, right) =>
    left.label.localeCompare(right.label, "ja"),
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
