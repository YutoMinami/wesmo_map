const ADDRESS_SEARCH_LIMIT = 5;
const NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search";
const GSI_ADDRESS_SEARCH_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch";
const CSIS_GEOCODE_URL = "https://geocode.csis.u-tokyo.ac.jp/cgi-bin/simple_geocode.cgi";

export async function searchAddress(query, provider) {
  if (provider === "gsi") {
    return searchAddressWithGsi(query);
  }

  if (provider === "csis") {
    return searchAddressWithCsis(query);
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
  const results = (Array.isArray(payload) ? payload : [])
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
    .filter((result) => Number.isFinite(result.lat) && Number.isFinite(result.lng));

  return rerankAddressResults(results, query);
}

async function searchAddressWithCsis(query) {
  const params = new URLSearchParams({ addr: query });
  const response = await fetch(`${CSIS_GEOCODE_URL}?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`CSIS search failed with status ${response.status}`);
  }

  const xmlText = await response.text();
  const xml = new DOMParser().parseFromString(xmlText, "application/xml");
  const candidates = [...xml.querySelectorAll("candidate")].map((candidate) => {
    const label = (candidate.querySelector("address")?.textContent || "").replaceAll("/", "");
    return {
      name: label.split(/[、,]/)[0] || query,
      label: label || query,
      lat: Number(candidate.querySelector("latitude")?.textContent || ""),
      lng: Number(candidate.querySelector("longitude")?.textContent || ""),
    };
  });

  return rerankAddressResults(
    candidates.filter((result) => Number.isFinite(result.lat) && Number.isFinite(result.lng)),
    query,
  );
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

      resolve(rerankAddressResults(results, query));
    };

    script.onerror = () => {
      cleanup();
      reject(new Error("Address lookup failed."));
    };
    script.src = url;
    document.body.append(script);
  });
}

function rerankAddressResults(results, query) {
  const variants = buildQueryVariants(query);
  const scored = results
    .map((result) => ({
      ...result,
      score: scoreAddressResult(result.label, variants),
    }))
    .filter((result) => result.score > 0);

  if (scored.length > 0) {
    return scored
      .sort((left, right) => right.score - left.score)
      .slice(0, ADDRESS_SEARCH_LIMIT)
      .map(({ score, ...result }) => result);
  }

  return results.slice(0, ADDRESS_SEARCH_LIMIT);
}

function buildQueryVariants(query) {
  const normalized = normalizeQuery(query);
  const variants = [normalized];

  if (normalized.endsWith("駅") && normalized.length > 1) {
    variants.push(normalized.slice(0, -1));
  }

  return [...new Set(variants.filter((value) => value.length > 0))];
}

function scoreAddressResult(label, variants) {
  const normalizedLabel = normalizeQuery(label);
  let bestScore = 0;

  for (const variant of variants) {
    if (!variant) {
      continue;
    }

    if (normalizedLabel.includes(variant)) {
      bestScore = Math.max(bestScore, 100 + variant.length * 10);
    }

    if (normalizedLabel.startsWith(variant)) {
      bestScore = Math.max(bestScore, 140 + variant.length * 10);
    }

    if (variant.endsWith("駅") && normalizedLabel.includes(variant)) {
      bestScore = Math.max(bestScore, 180 + variant.length * 10);
    }
  }

  return bestScore;
}

function normalizeQuery(value) {
  return value.replaceAll(/\s+/g, "").normalize("NFKC");
}
