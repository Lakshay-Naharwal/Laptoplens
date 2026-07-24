# LaptopLens repository improvement audit

Reviewed 2026-07-05 using the codebase knowledge graph, direct inspection of every tracked source/configuration area, Python compilation and import smoke tests, Flask test-client probes, Ruff, and a Vite production build attempt.

## Highest-priority findings

1. **[Critical correctness] Recommendation cache keys omit most inputs.** `backend/api/app.py:479` keys only on predicted price, confidence band, and use case. It omits RAM, processor/CPU tier, GPU, brand, `use_live`, and future ranking inputs. A test-client probe confirmed that requests for different specs return identical cached laptops. Serialize every normalized ranking input (and a cache/data schema version) into the key.

2. **[High availability/security] Public requests can launch browsers.** `POST /api/recommend` accepts `use_live`, and `GET /api/laptop-image` can start Selenium for arbitrary names. There is no authentication, rate limit, concurrency limit, queue, or circuit breaker. One caller can exhaust CPU, RAM, browser processes, and worker slots. Disable live scraping in the public API by default, restrict it server-side, validate input length, rate-limit it, and move browser work to a bounded job worker.

3. **[High deployment] Playwright system dependency installation runs after switching to a non-root user.** In `Dockerfile:29-42`, `USER user` precedes `playwright install-deps chromium`; that command normally needs root for apt packages. `|| echo` then hides failure, producing a successful image with broken live scraping. Install OS/browser dependencies as root, then switch users; fail explicitly when live scraping is enabled.

4. **[High ML validity] Outlier removal leaks information across folds.** `backend/ml/data_cleaning.py:115-125` fits preprocessing on the entire dataset before cross-validated outlier predictions, then removes rows before the later model CV. Validation folds influence feature encoding and inclusion. Put all learned preprocessing/outlier logic inside each training fold, or derive cleaning thresholds on training folds only.

5. **[High ML validity] There is no untouched final test set.** `backend/ml/train_model.py:84-113` uses cross-validation scores for reporting and then fits on all data. This is fine for model selection only if a separate test set or external temporal evaluation exists. Preserve a final holdout (ideally time/source/group split) and report both CV and holdout results.

6. **[High reliability] The in-memory cache is inconsistent across Gunicorn workers.** `Dockerfile` starts two workers, each with its own `scrape_cache`. Hits, invalidations, and browser suppression differ by worker and disappear on restart. Use Redis or another shared bounded cache, or deliberately run one worker and document the tradeoff.

7. **[High reliability] Cache growth is unbounded.** `TTLCache` lazily expires only accessed keys and has no maximum size or cleanup pass. Arbitrary price/band/use-case combinations can accumulate for three hours per worker. Add `maxsize`, periodic expiry, canonicalized/bucketed keys, and metrics.

8. **[High API hygiene] Internal exception strings are returned to clients.** `backend/api/app.py:438-440` and `:545-548` turn unexpected exceptions into public 400 responses. This misclassifies server faults and may expose paths/library details. Return stable error codes/messages, use 500 for unexpected failures, and retain details only in logs.

9. **[High reproducibility] Python dependencies are not locked.** `requirements.txt` uses only lower bounds. Future image builds can silently change NumPy, pandas, scikit-learn, XGBoost, Selenium, or Flask and break pickle compatibility. Produce a hashed lock/constraints file, document the Python version, and rebuild model artifacts under the same environment.

10. **[High supply-chain/reproducibility] Runtime unpickling trusts checked-in binary artifacts.** `backend/api/app.py:56-60` and the CLI load pickle files at startup. Pickle executes code and is version-sensitive. Treat artifacts as trusted release assets with checksums/provenance; consider safer model formats or signed artifacts.

## Backend and API

11. Add explicit request schemas (Pydantic/Marshmallow/dataclasses) instead of permissive coercion. Missing/malformed numbers currently become defaults, so typos can yield plausible but wrong predictions rather than a 422 response.

12. Validate `Content-Type: application/json`; `_json_body()` silently turns any invalid body into `{}`. Distinguish malformed JSON from missing required fields.

13. Set `MAX_CONTENT_LENGTH` and reject oversized bodies before parsing.

14. Validate categorical values against metadata server-side. The API only checks non-empty strings, while the model silently ignores unknown one-hot categories.

15. Validate `use_case` against the supported enum. Unknown strings bypass filters and fragment the cache.

16. Reject or normalize non-finite floats (`NaN`, `Infinity`) explicitly in `_as_float` using `math.isfinite`.

17. Move `NUM_BOUNDS` to module configuration shared by API, UI metadata, training, and tests; duplicated implicit bounds will drift.

18. The recommendation endpoint docstring says source is `mock|live`, but implementation also returns `real`. Update the contract and frontend types/comments.

19. The recommendation cache should not use truthiness (`if cached:`); check `is not None` so valid empty results are cacheable.

20. Include dataset/model version in recommendation cache keys to prevent stale results after deployments.

21. Precompute normalized recommendation features when loading the CSV. `_recommend_from_real_data` reparses and rebuilds vectors for all 6,184 rows on every cache miss.

22. Avoid `DataFrame.iterrows()` at import time. Use vectorized cleanup/`to_dict("records")`, validate the CSV schema, and quarantine malformed rows instead of abandoning the whole load.

23. Do not perform model and full-dataset loading as import side effects. Use an app factory/lifespan initialization so tests, CLI tools, and worker preload behavior are controllable.

24. Consider Gunicorn `--preload` after measuring copy-on-write behavior; two workers currently load duplicate model/data state.

25. `run_async` creates a new event loop inside a synchronous request. Move async scraping behind a worker, or use a consistent async server boundary; also ensure pending tasks/async generators are cleaned up.

26. Add API versioning (`/api/v1`) before the response contract grows further.

27. Add structured request IDs, latency/error metrics, cache hit metrics, scraper outcomes, and model/data version fields to logs.

28. Add health/readiness endpoints that separately report process health, model availability, dataset availability, and optional scraper readiness.

29. Avoid global `logging.basicConfig` in an imported module; configure logging in the application entry point/Gunicorn configuration.

30. `render.yaml` explicitly sets `CORS_ORIGINS` to an empty value, which disables the documented default origins. Make same-origin intent explicit or set the actual split-frontend origin per environment.

31. The catch-all frontend route returns HTML 404s for unknown `/api/...` GET routes. Add an API-specific JSON 404 handler and ensure the SPA fallback never masks API mistakes.

32. Add standard security headers (CSP appropriate for the app, `X-Content-Type-Options`, Referrer Policy, frame policy) at Flask or the hosting layer.

33. Validate/sanitize outbound product and image URLs to allowed `https` domains before returning them. Scraped CSV values currently flow to browser `href`/`src` fields.

## Scrapers and data quality

34. Consolidate the duplicate Flipkart implementations (`flipkart_scraper.py` and `amazon_flipkart_scraper.py`). They use different drivers, parsing, result schemas, retry behavior, and product IDs.

35. Put every Selenium driver shutdown in `finally`. Several paths manually call `quit()`, so unexpected errors/rebuild failures can leak processes.

36. Replace bare `except:` at `amazon_flipkart_scraper.py:398` and `:557` with narrow exceptions; never swallow `KeyboardInterrupt`/`SystemExit`.

37. Replace long string chains used to detect dead WebDriver sessions with typed Selenium exceptions and one bounded retry policy.

38. URL-encode queries with `urllib.parse.urlencode/quote_plus`, not `.replace(" ", "+")`; punctuation and non-ASCII model names are otherwise malformed.

39. Add retry caps and exponential backoff with jitter. Smartprix 403/429 and timeout branches can retry the same page forever.

40. Reuse a `requests.Session`, set a complete retry adapter, and honor `Retry-After` for Smartprix.

41. Version selectors and store fixture HTML tests. Marketplace CSS selectors are brittle and currently untested.

42. Do not fabricate unknown specs as real facts. `_parse_specs_from_title` defaults unknown CPU to Core i5, gaming GPU to RTX 4060, OS to Windows 11, and display/resolution/storage to common values. Add confidence/provenance fields and represent unknowns as null; otherwise training and recommendations are systematically biased.

43. Expand processor/GPU parsing beyond Apple M1-M3; current patterns miss newer generations and many AMD/Intel naming variants.

44. Distinguish screen centimeters from inches. The display regex mentions `cm/` but reads the captured number as inches.

45. Detect storage and RAM independently across multiple matches; the first generic `GB` match can still misclassify titles with unusual ordering.

46. Deduplicate by stable marketplace product ID/URL, not MD5 of normalized name. Different variants can share a title and the same product can change titles.

47. Use a non-cryptographic explicit stable ID or SHA-256 if collision resistance matters; MD5 is confusing even though it is not being used for security here.

48. Validate CSV rows and URLs before incremental writes; add atomic replacement plus backups. File locking alone does not protect against malformed partial data or schema drift.

49. `image_cache.json` is process-local file state with whole-file rewrites and broad exception swallowing. Use the shared cache/database, atomic writes, and corruption telemetry.

50. The scraper intentionally masks automation signals despite the repository acknowledging Terms-of-Service concerns. For a production portfolio, prefer official affiliate/product APIs and remove anti-detection behavior.

## Machine learning

51. Group train/test splits by product family/model and preferably source/time. Near-duplicate listings across marketplaces can otherwise leak into multiple folds and inflate scores.

52. Use a regression-aware split strategy and publish uncertainty across folds, not only mean metrics.

53. Fit an imputer inside the pipeline. Missing numerical/categorical values can currently break training or inference depending on library behavior.

54. Dense one-hot encoding (`sparse_output=False`) can consume substantial memory as categories grow. Keep sparse output where estimator support permits, or constrain/category-encode high-cardinality processor/GPU fields.

55. Reconsider scaling tree inputs and ordinal assumptions; document why a VotingRegressor of XGBoost and Ridge is preferable to the README’s claimed model.

56. Feature importance is taken only from the XGBoost member of the ensemble, then presented as model explainability. Label it accurately or use permutation/SHAP on the complete prediction pipeline.

57. Persist training configuration, git/data hashes, library versions, timestamp, and evaluation results alongside the model.

58. Add deterministic dataset snapshots and data-quality checks: duplicates, missingness, impossible RAM/storage/resolution combinations, price distribution by source, and parser-confidence coverage.

59. `extract_number` joins every digit/dot in a value; strings containing multiple numbers can become invalid or misleading. Use a single well-defined regex and units.

60. `clean_gpu` performs quadratic list membership deduplication and contains redundant replacements/imports. More importantly, token deduplication can alter meaningful GPU names; use canonical mapping rules with tests.

61. Training scripts execute expensive work at import time. Put them under `main()`, expose arguments, and make comparison/training functions reusable and testable.

62. Remove unused imports and late imports; Ruff reports 66 issues, including 22 auto-fixable ones.

## Frontend

63. Add ESLint, Prettier, and type checking (TypeScript or at least JSDoc-checking). The package has build only—no lint/test/check scripts.

64. Add component and API-contract tests (Vitest + Testing Library) and at least one browser smoke test for metadata → prediction → recommendations.

65. Split the 322-line `SpecForm` (cognitive complexity 38) into hooks and field components. Move CPU parsing/filtering out of render and memoize derived option lists.

66. The UI maintains `_cpuBrand`/`_cpuTier` inside the submitted values object. Keep transient UI state separate so internal keys never leak into API payloads.

67. Associate all labels with controls using `htmlFor`/`id`; most labels in `SpecForm` are visually adjacent but not programmatically connected.

68. Give the loading spinner an accessible status/name and mark decorative emoji appropriately. Announce prediction/recommendation/toast changes with suitable live regions.

69. Manage toast timers with a ref/effect. Multiple toasts currently leave older timers that can clear newer messages, and timers survive unmount.

70. Cancel `requestAnimationFrame` in the count-up hook cleanup to prevent state updates after unmount or target changes.

71. Cancel or supersede Axios requests when a new prediction starts/unmount occurs; stale responses can overwrite newer state.

72. Add explicit empty, retry, offline, and partial-data states instead of relying mainly on toast messages.

73. Centralize Axios error normalization and distinguish timeout, validation, server, and network failures.

74. The 30-second frontend timeout conflicts with server/browser work that may take much longer. Prefer asynchronous jobs; at minimum align and communicate timeouts.

75. Remove unused `chart.js` and `react-chartjs-2` dependencies unless charts are restored; they add install/bundle/security surface.

76. Do not commit a personal deployment URL in `.env.production`. Configure production URL in deployment settings, or use same-origin requests when Flask serves the bundle.

77. Add runtime validation of API responses so malformed/older backend payloads fail gracefully.

78. Add image dimensions/aspect ratio and robust domain/referrer behavior; remote marketplace image hotlinks often expire or block embeds.

79. Lazy image fallback invokes the expensive backend image scraper for every missing image. Prefer a static placeholder or preprocessed image service, with bounded background enrichment.

80. Audit responsive layout, keyboard focus visibility, contrast, reduced-motion support, and screen-reader flow with automated accessibility checks plus manual keyboard testing.

## Repository, documentation, and operations

81. Add CI for Python compile/lint/tests, frontend install/lint/test/build, dependency checks, Docker build, and a Flask smoke test.

82. Add actual unit tests; `scratch/test_*` scripts are ignored and are not a maintained test suite.

83. Correct README commands: backend files live under `backend/...`, so root-level `python train_model.py` and `python app.py` are wrong.

84. Correct README architecture: the current trainer is an XGBoost+Ridge voting ensemble with transformed target, while the README alternately claims Random Forest, HistGradientBoosting, and XGBoost.

85. Correct README data statements: it claims 900+, ~6,000, and a curated `data.csv` with `--data-source`, but the current script uses `backend/data/raw/data_real.csv` and exposes no such argument.

86. Replace the stale project tree, which lists nonexistent root files/database assets and omits the current backend structure.

87. Add a license file; a README sentence is not a complete distributable license.

88. Add contribution/development guidance, code style, test commands, supported platforms, and scraper/legal constraints.

89. Pin the Node version (`.nvmrc`/`.node-version`/package `engines`) and use `npm ci` consistently in docs and CI.

90. Add Python project configuration (`pyproject.toml`) for Ruff, tests, packaging/import paths, and supported Python version.

91. Add dependency vulnerability and license scanning with a documented update cadence.

92. Remove generated/runtime artifacts from source where practical. Large CSV/model binaries should have documented provenance and may belong in versioned release/object storage or Git LFS.

93. Add `.dockerignore` coverage checks so local caches, graphs, scratch content, and unnecessary assets do not inflate build context.

94. Use a Docker health check and pin base images by digest for reproducible releases.

95. Avoid swallowing the Playwright installation failure in Docker; build variants (`core` and `scraper`) are clearer and smaller.

96. Review system packages in the image: both Selenium and Playwright stacks are installed even though production normally uses neither, increasing image size and attack surface.

97. Fix source/text encoding consistency. The PowerShell inspection displayed mojibake for rupee signs, arrows, emoji, and box drawing; enforce UTF-8 through `.editorconfig`, CI, and terminal/docs guidance.

98. Keep the codebase knowledge graph artifact/index refreshed in CI or documented developer workflow so architectural review does not drift.

## Verification notes

- Knowledge graph: ready; 397 nodes, 855 edges, 39 indexed files, 98 functions/methods, five HTTP routes.
- Python: `python -m compileall -q backend` passed.
- Flask import/route smoke test passed; model loaded with MAE 17,337.38 and 6,184 recommendation rows.
- Cache collision probe failed as described in finding 1.
- Ruff 0.15.20 found 66 issues (22 auto-fixable); no fixes were applied during this review.
- Vite transformed all 87 modules, then the environment denied creation of both repository and temporary output directories (`EPERM`). This is not evidence of a source compilation failure, but the production artifact could not be fully emitted in this sandbox.
- CodeRabbit was not run: it was absent, and the remote install-script execution was rejected by the security approval layer. No result in this document is attributed to CodeRabbit.

## Suggested execution order

1. Fix findings 1-10 and add regression/API tests.
2. Establish CI, locks, and a real test suite (81, 82, 89-91).
3. Repair ML evaluation/data provenance (4, 5, 51-60).
4. Isolate or remove public live scraping (2, 3, 34-50, 95-96).
5. Refactor frontend/backend hotspots and complete accessibility/observability work.
6. Reconcile documentation with the verified implementation.
