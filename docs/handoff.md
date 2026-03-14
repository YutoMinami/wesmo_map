# Handoff

Last updated: 2026-03-15

## Current State

- Branch: `main`
- `main` and `origin/main` are aligned at `d8feccc`
- GitHub Pages should reflect the latest category-first UI and popup formatting once cache refreshes

## Recent Changes Already On `main`

- Category-first UI:
  - large category chips above the other controls
  - category select kept in sync with the chips
- Popup formatting:
  - line 1: `チェーン名-店舗名`
  - line 2: `[カテゴリ]・(決済方法)`
  - line 3: address
- Prefecture-split delivery:
  - `data/prefectures/index.json`
  - `data/prefectures/*.json`
  - frontend loads only intersecting prefectures
- Matsuya fetch pipeline added
- Category policy documented in `README.md`

## Category Model

- `source_category` is the original category from the upstream source
- `category` is the normalized UI-facing category
- `data/category_mapping.csv` maps `source_system + source_category -> category`
- Smart Code categories should generally be preserved in UI form rather than over-compressed
- `shopping` was intentionally removed
- `ベビー・子ども` is the main approved custom category
  - used for chains like Nishimatsuya
  - intended future fit for Toys"R"Us / Babies"R"Us as well

## Current UI Intent

- This product is for people who want to know whether there is a usable Wesmo!/Smart Code shop nearby
- The main value is proximity + category, not chain-name discovery by itself
- Category should be visible before chain name
- Chain name is still useful, but lower priority than "what kind of place is nearby?"

## Data / Pipeline Status

- Active major chains on map now include Nishimatsuya and Matsuya
- `shops.json` is still generated, but prefecture-split JSON is now also produced
- Batch geocoding still uses `jageocoder`
- Browser-side search currently uses `gsi` by default

## Known Open Threads

- Lawson is still blocked / investigatory due to source and terms concerns
- Search provider quality can still improve for some station queries
- Prefecture split works, but preload/intersection behavior can be optimized later
- Geocode unresolved rows still exist for some chains, especially Nishimatsuya edge cases

## Suggested Next Tasks

1. Add another chain with a clean official store source
2. Improve category coverage / mapping as more chains are added
3. Measure and optimize prefecture JSON loading behavior
4. Revisit search provider quality if station-name ambiguity remains annoying
