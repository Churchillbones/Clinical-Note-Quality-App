# Phase 2 – Behavioural Enhancements & Production Hardening

This phase focuses on **feature expansion** and **operational robustness** while deprecating legacy code paths introduced in Phase 1.  We will deliver a performant, asynchronous pipeline, richer user-experience, and production-grade observability.

---
## 1 — Goals & Non-Goals

### Goals
1. Replace blocking Azure calls with **async/await** + concurrency.
2. Introduce **Nine Rings** PDQI strategy with parity to O3.
3. Ship a **CLI & SDK** for batch grading and third-party integration.
4. Modernise the **UI** (HTMX/React) while keeping Flask backend.
5. Remove legacy `grading.*` modules (after emitting warnings for one release).
6. Add **observability**: structured logging, metrics, tracing.
7. Achieve ≥ 90 % test coverage; enforce via CI.
8. Produce comprehensive **docs** (architecture, API, user guide).

### Non-Goals
* Persistent DB storage (Phase 3).
* Full micro-service decomposition.

---
## 2 — Milestones & Exit Criteria

| # | Milestone | Key Tasks | Exit Criteria |
|---|-----------|-----------|---------------|
| 1 | **Async Azure Adapter** | • Refactor `AzureLLMClient` → `AsyncAzureLLMClient` using `httpx.AsyncClient`.<br>• Replace `asyncio.run()` call-sites with proper awaits.<br>• Provide sync wrapper for backwards compatibility. | All service layer calls non-blocking under async context; legacy sync wrapper passes existing tests. |
| 2 | **Nine Rings Strategy** | • Port `agents/NineRingsOrchestrator` into `services.pdqi_service`.<br>• Implement feature flag & weight tuning.<br>• Extend domain model to capture model provenance. | New strategy returns PDQI-9 dict ±5 % variance of O3 for test fixtures. |
| 3 | **Grading Pipeline Concurrency** | • Use `anyio` task group to parallelise PDQI, Heuristic, Factuality subsystems.<br>• Timeouts & circuit-breaker retries.<br>• Benchmark vs Phase 1. | End-to-end latency ≤ 60 % of Phase 1 baseline under test load. |
| 4 | **CLI & SDK** | • `clinical_note_quality/cli.py` with `grade file|dir|stdin` commands.<br>• Expose `ClinicalNoteGrader` high-level class.<br>• Package entry-points in `pyproject.toml`. | `pipx run clinical-note-quality grade sample.md` outputs JSON; documented in README. |
| 5 | **Web UI Upgrade** | • Replace vanilla templates with HTMX-enhanced forms for async feedback.<br>• Optional React+Vite SPA in `/frontend` served via Flask static.<br>• Design system with Tailwind. | Users can drag-drop note, see streaming progress bar; Lighthouse performance ≥ 90. |
| 6 | **Observability** | • Integrate `structlog` + OpenTelemetry tracing.<br>• Expose Prometheus metrics endpoint (`/metrics`).<br>• Add request/response correlation IDs. | Logs JSON-serialisable; `pytest` verifies trace headers propagate. |
| 7 | **Legacy Removal** | • Migrate tests off `grading.*` shims.<br>• Delete deprecated modules; bump major version. | No imports from `grading.*` remain; tests green. |
| 8 | **Coverage & Static-Analysis** | • Extend tests to edge cases (domain validators, heuristics).<br>• Add mutation testing (`mutmut`) gates in CI.<br>• `mypy --strict` passes with 0 errors. | Coverage ≥ 90 %, CI badge green. |
| 9 | **Documentation & Release** | • `mkdocs-material` site under `/docs` with diagrams (Mermaid).<br>• Changelog, contribution guide, code-of-conduct.<br>• Publish `v2.0.0` tag & PyPI package. | Public docs deployed via GitHub Pages; PyPI upload succeeds. |

---
## 3 — Detailed Task Breakdown

### 3.1 Async Azure Adapter
* Create `adapters/azure/async_client.py` with `AsyncLLMClientProtocol`.
* Use `@asynccontextmanager` for connection pooling.
* Implement exponential-backoff with `asyncio.sleep` + jitter.
* Write `pytest.mark.anyio` unit tests with `respx` mocking.

### 3.2 Pipeline Concurrency
* In `GradingService.grade_async`, launch tasks:
  ```python
  async with anyio.create_task_group() as tg:
      pdqi_task = tg.start_soon(self._pdqi.score, note)
      heur_task = tg.start_soon(self._heuristic.analyse, note)
      fact_task = tg.start_soon(self._factuality.check, note, transcript)
  ```
* Gather results, compute weights.
* Add timeout & fallback logic.

### 3.3 CLI
* Typer-based CLI with `--output json|html`, `--precision high`.
* Support glob patterns & stdin.
* Provide progress bar via `tqdm`.

### 3.4 UI Upgrade
* Build minimal React app (Vite, TS, Tailwind).
* Use `socket.io` or SSE to stream grading progress.
* Dockerfile multi-stage build to serve static files via Flask.

### 3.5 Observability
* `structlog.configure` for JSON logs.
* `fastapi-instrumentation`-style middleware for Flask traces.
* Prometheus client: request latency histograms.

### 3.6 Testing & Quality Gates
* Parametrised heuristic boundary tests.
* Hypothesis property-based tests for PDQI value ranges.
* Mutation tests (`mutmut --paths clinical_note_quality`).
* Configure CI matrix: Windows & Ubuntu; Python 3.12 / 3.13-beta.

---
## 4 — Timeline (Effort-Based)
| Week | Focus |
|------|-------|
| 1 | Milestones 1-2 (Async adapter, Nine Rings) |
| 2 | Milestone 3 (Concurrency) + start CLI |
| 3 | Finish CLI; begin UI upgrade |
| 4 | UI polish, observability plumbing |
| 5 | Legacy removal, coverage push |
| 6 | Docs, release prep |

---
## 5 — Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Async bugs / race conditions | Med | Use `anyio` test utilities & linters (`ruff ASYNC`) |
| Nine Rings cost & latency | Med | Feature flag & caching |
| UI scope creep | Med | Start with HTMX; escalate to React only if time permits |
| Breaking API changes | High | Maintain semantic-versioning, deprecate before removal |

---
## 6 — Success Criteria
* P95 grading latency reduced by ≥40 %.
* End-user can grade batch of notes via CLI.
* Web UI shows live progress & passes accessibility audit.
* Codebase `mypy --strict`, `ruff --select ALL`, mutation score ≥70 %.
* All tests & CI green; version `v2.0.0` released. 