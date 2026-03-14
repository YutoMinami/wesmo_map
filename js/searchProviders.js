const ADDRESS_SEARCH_LIMIT = 5;
const NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search";
const GSI_ADDRESS_SEARCH_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch";

export async function searchAddress(query, provider) {
  if (provider === "gsi") {
    return searchAddressWithGsi(query);
  }

  if (provider === "nominatim") {
    return searchAddressWithNominatim(query);
  }

  throw new Error(`Unsupported address search provider: ${provider}`);
}

async function searchAddressWithGsi(query) {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(`${GSI_ADDRESS_SEARCH_URL}?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`GSI search failed with status ${response.status}`);
  }

  const payload = await response.json();
  return (Array.isArray(payload) ? payload : [])
    .map((feature) => {
      const coordinates = feature?.geometry?.coordinates ?? [];
      const title = feature?.properties?.title ?? "";
      return {
        name: title.split(/[、,]/)[0] || query,
        label: title || query,
        lat: Number(coordinates[1]),
        lng: Number(coordinates[0]),
      };
    })
    .filter((result) => Number.isFinite(result.lat) && Number.isFinite(result.lng))
    .slice(0, ADDRESS_SEARCH_LIMIT);
}

function searchAddressWithNominatim(query) {
  const callbackName = `wesmoMapGeocode_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
  const params = new URLSearchParams({
    q: query,
    format: "jsonv2",
    limit: String(ADDRESS_SEARCH_LIMIT),
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
