const DEFAULT_CENTER = [34.707463069292885, 135.49508639737775];
const DEFAULT_ZOOM = 13;
const SEARCH_ZOOM = 14;
const DISTANCE_DECIMALS_KM = 1;
const NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search";

const map = L.map("map").setView(DEFAULT_CENTER, DEFAULT_ZOOM);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const locateButton = document.getElementById("locate-button");
const addressForm = document.getElementById("address-form");
const addressInput = document.getElementById("address-input");
const addressSearchButton = document.getElementById("address-search-button");
const searchResultsPanel = document.getElementById("search-results-panel");
const searchResultCount = document.getElementById("search-result-count");
const searchResultList = document.getElementById("search-result-list");
const radiusSelect = document.getElementById("radius-select");
const statusText = document.getElementById("status-text");
const resultCount = document.getElementById("result-count");
const shopList = document.getElementById("shop-list");

let userMarker = null;
let radiusCircle = null;
let shopMarkers = [];
let shops = [];
let currentPosition = null;
let addressCandidates = [];

init().catch((error) => {
  console.error(error);
  setStatus("加盟店データの読み込みに失敗しました。");
});

async function init() {
  const response = await fetch("./data/shops.json");
  shops = await response.json();
  refreshResults();
}

locateButton.addEventListener("click", () => {
  if (!navigator.geolocation) {
    setStatus("このブラウザは現在地取得に対応していません。");
    return;
  }

  setStatus("現在地を取得しています...");

  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      currentPosition = {
        lat: coords.latitude,
        lng: coords.longitude,
      };
      addressInput.value = "";
      clearAddressCandidates();
      refreshResults();
    },
    (error) => {
      console.error(error);
      setStatus("現在地を取得できませんでした。位置情報の許可を確認してください。");
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 60000,
    },
  );
});

addressForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = addressInput.value.trim();
  if (!query) {
    setStatus("住所か駅名を入力してください。");
    addressInput.focus();
    return;
  }

  setAddressSearchPending(true);
  setStatus("入力した住所を検索しています...");

  try {
    const results = await searchAddress(query);
    if (results.length === 0) {
      throw new Error("No address match.");
    }

    renderAddressCandidates(query, results);
    if (results.length === 1) {
      selectAddressCandidate(results[0], query);
    } else {
      setStatus(`「${query}」の候補から選んでください。`);
    }
  } catch (error) {
    console.error(error);
    clearAddressCandidates();
    setStatus("住所を見つけられませんでした。地名や駅名を変えて試してください。");
  } finally {
    setAddressSearchPending(false);
  }
});

radiusSelect.addEventListener("change", () => {
  refreshResults();
});

map.on("moveend", () => {
  if (!currentPosition) {
    refreshResults();
  }
});

function refreshResults() {
  const radiusKm = Number(radiusSelect.value);
  const searchCenter = currentPosition ?? {
    lat: map.getCenter().lat,
    lng: map.getCenter().lng,
  };
  const enrichedShops = shops
    .map((shop) => ({
      ...shop,
      distanceKm: haversineKm(
        searchCenter.lat,
        searchCenter.lng,
        shop.lat,
        shop.lng,
      ),
    }))
    .filter((shop) => shop.distanceKm <= radiusKm)
    .sort((left, right) => left.distanceKm - right.distanceKm);

  renderSearchArea(searchCenter, radiusKm);
  renderShops(enrichedShops);
  renderShopList(enrichedShops);
  setStatus(buildStatusMessage(radiusKm, enrichedShops.length));
}

function renderSearchArea(searchCenter, radiusKm) {
  const latLng = [searchCenter.lat, searchCenter.lng];

  if (currentPosition) {
    if (!userMarker) {
      userMarker = L.marker(latLng).addTo(map).bindPopup("現在地");
    } else {
      userMarker.setLatLng(latLng);
    }
  } else if (userMarker) {
    userMarker.remove();
    userMarker = null;
  }

  if (!radiusCircle) {
    radiusCircle = L.circle(latLng, {
      radius: radiusKm * 1000,
      color: "#166534",
      fillColor: "#4ade80",
      fillOpacity: 0.14,
    }).addTo(map);
  } else {
    radiusCircle.setLatLng(latLng);
    radiusCircle.setRadius(radiusKm * 1000);
  }

  if (currentPosition) {
    map.setView(latLng, 14);
  }
}

function renderShops(filteredShops) {
  shopMarkers.forEach((marker) => marker.remove());
  shopMarkers = filteredShops.map((shop) =>
    L.marker([shop.lat, shop.lng])
      .addTo(map)
      .bindPopup(
        `<strong>${escapeHtml(shop.chain)}</strong><br>${escapeHtml(shop.name)}<br>${escapeHtml(shop.address)}`,
      ),
  );
}

function renderShopList(filteredShops) {
  resultCount.textContent = `${filteredShops.length}件`;

  if (filteredShops.length === 0) {
    shopList.innerHTML =
      '<li class="empty-state">条件に合う加盟店はまだありません。現在地取得後に半径を変えて試してください。</li>';
    return;
  }

  shopList.innerHTML = filteredShops
    .map(
      (shop) => `
        <li class="shop-item">
          <p class="shop-name">${escapeHtml(shop.name)}</p>
          <p class="shop-meta">${formatShopMeta(shop)}</p>
          <p class="shop-meta">${escapeHtml(shop.address)}</p>
        </li>
      `,
    )
    .join("");
}

function setStatus(message) {
  statusText.textContent = message;
}

function buildStatusMessage(radiusKm, count) {
  if (currentPosition) {
    return `現在地から ${radiusKm}km 圏内に ${count} 件の加盟店があります。`;
  }

  return `地図の中心から ${radiusKm}km 圏内に ${count} 件の加盟店を表示しています。地図を動かすと再検索し、現在地を取得すると現在地基準に切り替わります。`;
}

function formatShopMeta(shop) {
  if (typeof shop.distanceKm === "number") {
    return `${escapeHtml(shop.chain)} / ${shop.distanceKm.toFixed(DISTANCE_DECIMALS_KM)}km`;
  }
  return escapeHtml(shop.chain);
}

function haversineKm(lat1, lng1, lat2, lng2) {
  const earthRadiusKm = 6371;
  const dLat = toRadians(lat2 - lat1);
  const dLng = toRadians(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) *
      Math.cos(toRadians(lat2)) *
      Math.sin(dLng / 2) ** 2;

  return earthRadiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function toRadians(value) {
  return (value * Math.PI) / 180;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setAddressSearchPending(isPending) {
  addressSearchButton.disabled = isPending;
  addressSearchButton.textContent = isPending ? "検索中..." : "地図を移動";
}

async function searchAddress(query) {
  const callbackName = `wesmoMapGeocode_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  const params = new URLSearchParams({
    q: query,
    format: "jsonv2",
    limit: "5",
    countrycodes: "jp",
    "accept-language": "ja",
    json_callback: callbackName,
  });
  const url = `${NOMINATIM_SEARCH_URL}?${params.toString()}`;

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    const timeoutId = window.setTimeout(() => {
      cleanup();
      reject(new Error("Address lookup timed out."));
    }, 10000);

    function cleanup() {
      window.clearTimeout(timeoutId);
      delete window[callbackName];
      script.remove();
    }

    window[callbackName] = (payload) => {
      cleanup();
      const results = (Array.isArray(payload) ? payload : [])
        .map((result) => ({
          name: result.name || result.display_name.split(",")[0] || query,
          label: result.display_name,
          lat: Number(result.lat),
          lng: Number(result.lon),
        }))
        .filter((result) => Number.isFinite(result.lat) && Number.isFinite(result.lng));

      resolve(results);
    };

    script.onerror = () => {
      cleanup();
      reject(new Error("Address lookup failed."));
    };
    script.src = url;
    document.body.append(script);
  });
}

function renderAddressCandidates(query, results) {
  addressCandidates = results;
  searchResultsPanel.classList.remove("hidden");
  searchResultCount.textContent = `${results.length}件`;
  searchResultList.innerHTML = results
    .map(
      (result, index) => `
        <li>
          <button class="search-result-item" type="button" data-candidate-index="${index}">
            <p class="search-result-name">${escapeHtml(result.name || `候補 ${index + 1}`)}</p>
            <p class="search-result-address">${escapeHtml(result.label)}</p>
          </button>
        </li>
      `,
    )
    .join("");

  searchResultList.querySelectorAll("[data-candidate-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.candidateIndex);
      const result = addressCandidates[index];
      if (result) {
        selectAddressCandidate(result, query);
      }
    });
  });
}

function clearAddressCandidates() {
  addressCandidates = [];
  searchResultsPanel.classList.add("hidden");
  searchResultCount.textContent = "0件";
  searchResultList.innerHTML = "";
}

function selectAddressCandidate(result, query) {
  currentPosition = null;
  map.setView([result.lat, result.lng], SEARCH_ZOOM);
  refreshResults();
  setStatus(`「${query}」の候補: ${result.label}`);
}
