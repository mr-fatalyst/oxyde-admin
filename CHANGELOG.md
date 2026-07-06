# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-05-01

### Added
- Enum field support: `$ref` definitions for Pydantic enums are inlined into the
  schema with their `enum` list, so the frontend renders a dropdown instead of
  treating them as foreign keys.
- Array field support: columns typed as `list[T]` are exposed via
  `x-db-array` / `x-db-array-item-type` metadata.

### Changed
- M2M synchronization now uses `bulk_create` for junction rows instead of
  per-row `create()` calls, collapsing N (and N×M for bulk updates) inserts
  into a single statement.

## [0.3.0] - 2026-03-13

### Changed
- Bumped minimum `oxyde` version to `>=0.5.0`.
- Adapted `bulk_update` to the new `QuerySet.update()` return value in
  `oxyde 0.5.0`: it now returns the affected-row count directly instead of
  a list of rows.

## [0.2.0] - 2026-03-02

### Added
- Quart adapter (`QuartAdmin`).
- Falcon adapter (`FalconAdmin`).
- Many-to-many relation support: prefetched on list/detail and synced on
  create/update via the through model.
- Bulk M2M sync for `bulk_update` operations.
- Mapped framework exceptions to consistent JSON error responses
  (404 / 403 / 409 / 422).

### Changed
- Replaced `PUT` with `PATCH` for record updates to reflect partial-update
  semantics. **API breaking** for clients calling `PUT /api/<model>/<pk>`.
- Refreshed `README.md` with per-framework integration examples.
- Deduplicated framework adapter code paths.

### Fixed
- `date` / `datetime` serialization in JSON responses across adapters.
- Stale table-name cache after registering models.

## [0.1.0] - 2026-02-27

### Added
- Initial release.
- Framework-agnostic `AdminSite` core with FastAPI, Litestar, and Sanic
  adapters.
- Auto-generated CRUD: list, detail, create, edit, delete.
- Search across configurable fields and column-level filters
  (FK / bool / int / string).
- Foreign key dropdowns with inline-create dialog and `display_field`
  resolution.
- CSV / JSON export with applied filters, chunked streaming, configurable
  `export_chunk_size` and `max_export_rows`.
- Bulk delete and bulk update from the list view.
- Pluggable authentication via `auth_check` callback (sync or async) with
  configurable `login_url`.
- Theming via `Preset`, `PrimaryColor`, and `Surface` enums.
- Sidebar grouping and per-model icons (PrimeIcons).
- Per-column labels and configurable default ordering.
- JSON Schema enriched with `x-db-*` extensions
  (primary key, nullable, unique, index, FK, db_column, db_type, max_length,
  default, comment) for frontend rendering.
- Concurrent model count loading via `asyncio.gather`.

[Unreleased]: https://github.com/mr-fatalyst/oxyde-admin/compare/v0.4.0...HEAD
[0.5.0]: https://github.com/mr-fatalyst/oxyde-admin/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/mr-fatalyst/oxyde-admin/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mr-fatalyst/oxyde-admin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mr-fatalyst/oxyde-admin/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mr-fatalyst/oxyde-admin/releases/tag/v0.1.0
