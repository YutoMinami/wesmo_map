const DISTANCE_DECIMALS_KM = 1;
const GROUP_DISTANCE_METERS = 35;
const PAYMENT_TAG_LABELS = {
  smart_code: "Smart Code",
  wesmo: "Wesmo!",
  blue_tag: "BLUEタグ",
};

export function filterShops(shops, { searchCenter, radiusKm, category }) {
  return shops
    .filter((shop) => !category || shop.category === category)
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
}

export function groupShopsForMap(shops) {
  const groups = [];

  for (const shop of shops) {
    const match = groups.find((group) => shouldGroup(group, shop));
    if (match) {
      match.shops.push(shop);
      match.lat = average(match.shops.map((item) => item.lat));
      match.lng = average(match.shops.map((item) => item.lng));
      continue;
    }

    groups.push({
      lat: shop.lat,
      lng: shop.lng,
      shops: [shop],
    });
  }

  return groups;
}

export function buildStatusMessage({ radiusKm, count, currentPosition, category }) {
  const categoryText = category ? " / カテゴリ絞り込み中" : "";

  if (currentPosition) {
    return `現在地から ${radiusKm}km 圏内に ${count} 件の加盟店があります。${categoryText}`;
  }

  return `地図の中心から ${radiusKm}km 圏内に ${count} 件の加盟店を表示しています。地図を動かすと再検索し、現在地を取得すると現在地基準に切り替わります。${categoryText}`;
}

export function buildCategoryOptions(shops) {
  const options = new Map();

  for (const shop of shops) {
    if (shop.category && shop.categoryLabel && !options.has(shop.category)) {
      options.set(shop.category, {
        value: shop.category,
        label: shop.categoryLabel,
      });
    }
  }

  return [...options.values()].sort((left, right) => left.label.localeCompare(right.label, "ja"));
}

export function formatShopMeta(shop) {
  if (typeof shop.distanceKm === "number") {
    return `${shop.distanceKm.toFixed(DISTANCE_DECIMALS_KM)}km`;
  }

  return "";
}

export function buildPopupHtml(group) {
  if (group.shops.length === 1) {
    const [shop] = group.shops;
    return `
      <div class="popup-shop-title">${escapeHtml(formatShopTitle(shop))}</div>
      ${buildShopInfoLine(shop, "popup-shop-detail")}
      <div class="popup-shop-address">${escapeHtml(shop.address)}</div>
    `;
  }

  return `
    <div class="popup-group-title">この周辺に ${group.shops.length} 店舗</div>
    <div class="popup-group-list">
      ${group.shops
        .map(
          (shop) => `
            <div class="popup-group-item">
              <div class="popup-shop-title">${escapeHtml(formatShopTitle(shop))}</div>
              ${buildShopInfoLine(shop, "popup-shop-detail")}
              <div class="popup-shop-address">${escapeHtml(shop.address)}</div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function shouldGroup(group, shop) {
  return (
    group.shops.some((existing) => existing.address === shop.address) ||
    group.shops.some(
      (existing) =>
        haversineKm(existing.lat, existing.lng, shop.lat, shop.lng) * 1000 <=
        GROUP_DISTANCE_METERS,
    )
  );
}

function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function formatShopTitle(shop) {
  return `${shop.chain}-${shop.name}`;
}

export function buildShopInfoLine(shop, className = "") {
  const fragments = [];
  if (shop.categoryLabel) {
    fragments.push(
      `<span class="shop-category-badge">${escapeHtml(shop.categoryLabel)}</span>`,
    );
  }
  const paymentLabel = formatPaymentTags(shop.paymentTags);
  if (paymentLabel) {
    fragments.push(`<span class="shop-payment-label">${escapeHtml(paymentLabel)}</span>`);
  }

  if (fragments.length === 0) {
    return "";
  }

  const classAttribute = className ? ` class="${className}"` : "";
  return `<div${classAttribute}>${fragments.join('<span class="shop-detail-separator"></span>')}</div>`;
}

export function formatPaymentTags(paymentTags) {
  if (!Array.isArray(paymentTags)) {
    return "";
  }

  return paymentTags
    .map((tag) => PAYMENT_TAG_LABELS[tag] || tag)
    .filter(Boolean)
    .join(" / ");
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
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
