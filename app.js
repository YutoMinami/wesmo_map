const DEFAULT_CENTER = [34.707463069292885, 135.49508639737775];
const DEFAULT_ZOOM = 13;
const DISTANCE_DECIMALS_KM = 1;

const map = L.map("map").setView(DEFAULT_CENTER, DEFAULT_ZOOM);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const locateButton = document.getElementById("locate-button");
const radiusSelect = document.getElementById("radius-select");
const statusText = document.getElementById("status-text");
const resultCount = document.getElementById("result-count");
const shopList = document.getElementById("shop-list");

let userMarker = null;
let radiusCircle = null;
let shopMarkers = [];
let shops = [];
let currentPosition = null;

init().catch((error) => {
  console.error(error);
  setStatus("加盟店データの読み込みに失敗しました。");
});

async function init() {
  const response = await fetch("./data/shops.json");
  shops = await response.json();
  renderShopList([]);
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

radiusSelect.addEventListener("change", () => {
  if (currentPosition) {
    refreshResults();
  }
});

function refreshResults() {
  const radiusKm = Number(radiusSelect.value);
  const enrichedShops = shops
    .map((shop) => ({
      ...shop,
      distanceKm: haversineKm(
        currentPosition.lat,
        currentPosition.lng,
        shop.lat,
        shop.lng,
      ),
    }))
    .filter((shop) => shop.distanceKm <= radiusKm)
    .sort((left, right) => left.distanceKm - right.distanceKm);

  renderUserLocation(radiusKm);
  renderShops(enrichedShops);
  renderShopList(enrichedShops);
  setStatus(`${radiusKm}km圏内に ${enrichedShops.length} 件の加盟店があります。`);
}

function renderUserLocation(radiusKm) {
  const latLng = [currentPosition.lat, currentPosition.lng];

  if (!userMarker) {
    userMarker = L.marker(latLng).addTo(map).bindPopup("現在地");
  } else {
    userMarker.setLatLng(latLng);
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

  map.setView(latLng, 14);
}

function renderShops(filteredShops) {
  shopMarkers.forEach((marker) => marker.remove());
  shopMarkers = filteredShops.map((shop) =>
    L.marker([shop.lat, shop.lng])
      .addTo(map)
      .bindPopup(
        `<strong>${escapeHtml(shop.name)}</strong><br>${escapeHtml(shop.chain)}<br>${escapeHtml(shop.address)}`,
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
          <p class="shop-meta">${escapeHtml(shop.chain)} / ${shop.distanceKm.toFixed(DISTANCE_DECIMALS_KM)}km</p>
          <p class="shop-meta">${escapeHtml(shop.address)}</p>
        </li>
      `,
    )
    .join("");
}

function setStatus(message) {
  statusText.textContent = message;
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
