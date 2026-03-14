import { buildPopupHtml, formatShopMeta } from "./shopUtils.js";

export function createRenderer(map, elements) {
  let userMarker = null;
  let radiusCircle = null;
  let shopMarkers = [];
  let addressCandidates = [];

  return {
    clearAddressCandidates,
    renderAddressCandidates,
    renderSearchArea,
    renderShopList,
    renderShops,
    setAddressSearchPending,
    setStatus,
  };

  function renderSearchArea(searchCenter, radiusKm, currentPosition) {
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

  function renderShops(groupedShops) {
    shopMarkers.forEach((marker) => marker.remove());
    shopMarkers = groupedShops.map((group) => {
      if (group.shops.length === 1) {
        return L.marker([group.lat, group.lng])
          .addTo(map)
          .bindPopup(buildPopupHtml(group));
      }

      return L.circleMarker([group.lat, group.lng], {
        radius: 12,
        color: "#166534",
        fillColor: "#4ade80",
        fillOpacity: 0.92,
        weight: 2,
      })
        .addTo(map)
        .bindPopup(buildPopupHtml(group));
    });
  }

  function renderShopList(filteredShops) {
    elements.resultCount.textContent = `${filteredShops.length}件`;

    if (filteredShops.length === 0) {
      elements.shopList.innerHTML =
        '<li class="empty-state">条件に合う加盟店はまだありません。現在地取得後に半径やジャンルを変えて試してください。</li>';
      return;
    }

    elements.shopList.innerHTML = filteredShops
      .map(
        (shop) => `
          <li class="shop-item">
            <p class="shop-name">${escapeHtml(shop.name)}</p>
            <p class="shop-meta">${escapeHtml(formatShopMeta(shop))}</p>
            ${shop.categoryLabel ? `<p class="shop-meta">${escapeHtml(shop.categoryLabel)}</p>` : ""}
            <p class="shop-meta">${escapeHtml(shop.address)}</p>
          </li>
        `,
      )
      .join("");
  }

  function setStatus(message) {
    elements.statusText.textContent = message;
  }

  function setAddressSearchPending(isPending) {
    elements.addressSearchButton.disabled = isPending;
    elements.addressSearchButton.textContent = isPending ? "検索中..." : "検索";
  }

  function renderAddressCandidates(query, results, onSelect) {
    addressCandidates = results;
    elements.searchResultsPanel.classList.remove("hidden");
    elements.searchResultCount.textContent = `${results.length}件`;
    elements.searchResultList.innerHTML = results
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

    elements.searchResultList
      .querySelectorAll("[data-candidate-index]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          const index = Number(button.dataset.candidateIndex);
          const result = addressCandidates[index];
          if (result) {
            onSelect(result, query);
          }
        });
      });
  }

  function clearAddressCandidates() {
    addressCandidates = [];
    elements.searchResultsPanel.classList.add("hidden");
    elements.searchResultCount.textContent = "0件";
    elements.searchResultList.innerHTML = "";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
