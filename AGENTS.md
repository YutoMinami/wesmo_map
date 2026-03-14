# wesmo_map Agent Notes

## Workflow

- This project is currently single-maintainer.
- Small and medium changes may be committed directly to `main`.
- Pull requests are optional. Use them only when a change is large, risky, or worth reviewing as a separate unit.
- Feature branches are still useful for exploratory work, scraper experiments, and UI changes that may need iteration.
- Keep commits small and scoped to one purpose.

## Git Conventions

- Prefer short-lived branches such as `feature/...` when trying a new fetch flow or UI behavior.
- If a branch is already pushed and the change is accepted, fast-forward it into `main` and delete the branch afterwards.
- Do not rewrite published history unless explicitly requested.

## Product Direction

- This is a static GitHub Pages project.
- Favor simple HTML/CSS/JS with minimal dependencies.
- Prefer approaches that keep the site deployable as static files.
- Current UX should work both with geolocation and without it.
- PC users should be able to search by address or station name, not only by GPS.

## Data Sources

- Be conservative about licenses and terms of use.
- Do not reintroduce Google My Maps / KML-derived data unless the user explicitly revisits the legal and operational decision.
- When evaluating a new data source, check terms first if there is any doubt.
- If a source looks technically usable but contractually questionable, treat it as blocked or TODO rather than building on it.

## Data Pipeline

- Keep source data, generated intermediate files, and published output clearly separated.
- `shops_manual.csv` is the place for manual corrections and overrides.
- `shops_scraped.csv` is generated data and may be regenerated.
- `shops_raw.csv` is a merged/generated file and should not be manually edited.
- `shops_geocoded.csv` is generated from raw shop data plus coordinates.
- `shops.json` is the published frontend payload.
- If unresolved rows remain, it is acceptable to publish only rows with coordinates.
- When `chains_master.csv` gains new columns, review every dependent script for schema drift before assuming the pipeline still works.

## Geocoding

- Batch geocoding currently uses `jageocoder`.
- Browser-side address search may use a different provider if the batch provider is not browser-friendly.
- Keep unresolved rows visible in `geocode_unresolved.csv`.
- Prefer incremental normalization improvements first, then manual fixes for the remaining small set.
- Closed stores should not be geocoded for map display; keep them in separate files when needed.
- If a chain needs special address cleanup, isolate it as a chain-specific strategy instead of mixing it directly into generic logic.

## Chain Metadata

- Preserve both source-specific metadata and normalized metadata.
- Use `source_tags` for where the chain was observed.
- Use `payment_tags` for which payment/service categories the chain supports.
- Use `source_category` for the original category from each source.
- Use `category` for normalized UI-facing grouping.

## UI Expectations

- Default map behavior should avoid showing nationwide results all at once when that hurts usability.
- Favor radius-based local views around current location, searched location, or map center.
- When address search is ambiguous, prefer explicit candidate selection over silently picking the first result.
- Keep mobile usability in mind for controls, spacing, and map behavior.
- As the UI grows, prefer splitting large browser files by responsibility instead of letting `app.js` keep accumulating unrelated state.

## Documentation

- Update `README.md` when workflow or file roles change.
- Add future ideas or deferred work to `TODO.md` instead of leaving them implicit.
- If a new scraper or source requires investigation notes, add them under `docs/`.
- Keep temporary project status, branch state, and next-step handoff notes in `docs/handoff.md` rather than overloading `AGENTS.md`.
