# CHANGELOG

<!-- version list -->

## v1.6.0 (2026-07-31)

### Features

- Add ods_to_jaquel ([#18](https://github.com/totonga/wodson/pull/18),
  [`1e285e9`](https://github.com/totonga/wodson/commit/1e285e9e592acf6da7c82958ce4365e38e2f0868))

- Add ods_to_jaquel feature and refactor PathResolver
  ([#18](https://github.com/totonga/wodson/pull/18),
  [`1e285e9`](https://github.com/totonga/wodson/commit/1e285e9e592acf6da7c82958ce4365e38e2f0868))

### Refactoring

- Renamed PathResolver to FilePathResolver to make clear which kind of path is meant
  ([#18](https://github.com/totonga/wodson/pull/18),
  [`1e285e9`](https://github.com/totonga/wodson/commit/1e285e9e592acf6da7c82958ce4365e38e2f0868))


## v1.5.1 (2026-07-25)

### Bug Fixes

- Some cleanup in the FilePathResolver ([#16](https://github.com/totonga/wodson/pull/16),
  [`b66a96d`](https://github.com/totonga/wodson/commit/b66a96dcae4e155a6998bfed4b6d74003418b066))


## v1.5.0 (2026-07-24)

### Features

- Added FilePathResolver ([#15](https://github.com/totonga/wodson/pull/15),
  [`b039fd4`](https://github.com/totonga/wodson/commit/b039fd47b38403632e9c32a5d06347a907ada1a7))


## v1.4.0 (2026-07-24)

### Features

- Do lazy loading of bulk data ([#14](https://github.com/totonga/wodson/pull/14),
  [`b3b08d4`](https://github.com/totonga/wodson/commit/b3b08d45c2c5fd443538f402e3fceadbd43f7379))

- Lazy loading of bulk data and test refactoring ([#14](https://github.com/totonga/wodson/pull/14),
  [`b3b08d4`](https://github.com/totonga/wodson/commit/b3b08d45c2c5fd443538f402e3fceadbd43f7379))

### Refactoring

- Reorder and extend tests ([#14](https://github.com/totonga/wodson/pull/14),
  [`b3b08d4`](https://github.com/totonga/wodson/commit/b3b08d45c2c5fd443538f402e3fceadbd43f7379))


## v1.3.0 (2026-05-30)

### Bug Fixes

- Linting ...
  ([`08ec571`](https://github.com/totonga/wodson/commit/08ec5710fe4060d6c0b4f00dd180bf9cdea2153c))

### Features

- Added helper methods to AtfxFile
  ([`b11baab`](https://github.com/totonga/wodson/commit/b11baab0c2882b8d0e15451c56412b493f7b38ff))

- Added simple Measurements
  ([`0bbfa22`](https://github.com/totonga/wodson/commit/0bbfa2208917f5ff6f37c2ef3fba9abb3c297443))


## v1.2.5 (2026-05-29)

### Bug Fixes

- Joins to n relations did not work
  ([`28adcdf`](https://github.com/totonga/wodson/commit/28adcdfd3b8c085132c87f7a668e54007cad2046))


## v1.2.4 (2026-05-29)

### Bug Fixes

- Update file-map registration for external component references and improve AoFile resolution logic
  ([`1d03aad`](https://github.com/totonga/wodson/commit/1d03aad767532642b0a6a0d1bb30194ae880384c))


## v1.2.3 (2026-05-28)

### Bug Fixes

- Query should use query
  ([`affcc59`](https://github.com/totonga/wodson/commit/affcc59374319b17824ec73028e076cef5ecd41d))


## v1.2.2 (2026-05-28)

### Bug Fixes

- Implement fix_complex_values function to correctly handle complex ODS data types
  ([`25e5879`](https://github.com/totonga/wodson/commit/25e5879a99bbc7a8875e74f6424a05fbc6ec22f6))


## v1.2.1 (2026-05-28)

### Bug Fixes

- Cache resolved "id" column names in _QueryContext for improved performance
  ([`e017762`](https://github.com/totonga/wodson/commit/e0177621403c31d4e5e0574439fe4f9c7a3a7681))


## v1.2.0 (2026-05-28)

### Features

- Add fallback for relation range from base model in build_model
  ([`c32017e`](https://github.com/totonga/wodson/commit/c32017ebc834d3fcc574a9d90767ac137eed8f49))


## v1.1.1 (2026-05-28)

### Bug Fixes

- Return enums as int
  ([`004c6b0`](https://github.com/totonga/wodson/commit/004c6b04b6c59e71a13c1514b6ff35d076654d42))


## v1.1.0 (2026-05-25)

### Bug Fixes

- Improve data_read ([#8](https://github.com/totonga/wodson/pull/8),
  [`bea9763`](https://github.com/totonga/wodson/commit/bea97639f008c35d433e03475befff4bd7913b31))

### Features

- Improve performance and data handling ([#8](https://github.com/totonga/wodson/pull/8),
  [`bea9763`](https://github.com/totonga/wodson/commit/bea97639f008c35d433e03475befff4bd7913b31))

- Performace add index ([#8](https://github.com/totonga/wodson/pull/8),
  [`bea9763`](https://github.com/totonga/wodson/commit/bea97639f008c35d433e03475befff4bd7913b31))


## v1.0.0 (2026-05-25)

- Initial Release
