# Clinical Note Quality App – Refactoring & Modularization Roadmap

## 1. Current State Snapshot

* **Frameworks/Libraries:** Flask for HTTP layer, Azure OpenAI SDK for LLM calls, vanilla functions for heuristics/factuality.
* **Structure:** Flat package with tightly-coupled modules (`app.py`, `grading/*`, misc util files).
* **Issues Identified**
  * Cross-cutting concerns mixed together (HTTP logic, business logic, external API code in same modules).
  * Large functions performing multiple responsibilities (e.g. `grade_note_hybrid`).
  * Direct instantiation of Azure clients → hard to mock & test.
  * Scattered configuration access (via global `Config`).
  * Inconsistent error handling & logging.
  * Functional style where OOP abstraction would aid extensibility (PDQI vs Nine-Rings, heuristics strategies).

## 2. Target Architecture (Clean/Hexagonal Hybrid)

```
┌──────────────┐   depends on    ┌────────────────┐   depends on    ┌───────────────┐
│  HTTP Layer  │ ───────────────▶│ Application    │ ───────────────▶│  Domain       │
│  (Flask)     │                 │  Services      │                 │  Models       │
└──────────────┘                 └────────────────┘                 └───────────────┘
                            ▲                                          ▲
                            │ uses                                     │
                            │                                          │
                     ┌──────────────┐                           ┌──────────────┐
                     │Infrastructure│◀──────────────────────────│ Ports/Adapters│
                     │(Azure, etc.) │                           └──────────────┘
                     └──────────────┘
```

* **Domain Layer** – Pure Python dataclasses/enums describing PDQI scores, heuristics, factuality results. No external deps.
* **Application Services** – Orchestrate grading workflows. Contains `GradingService`, which composes smaller strategy objects.
* **Ports/Adapters** – Interfaces abstracting LLM providers (`LLMClient`), plus concrete Azure implementation.
* **Infrastructure** – Azure OpenAI SDK wrapper, persistence (future), etc.
* **HTTP Layer** – Thin Flask blueprints mapping JSON↔domain objects.

## 3. Module Breakdown

```
clinical_note_quality/
│   __init__.py
│   config.py
│
├── domain/
│   ├── models.py          # PDQIScore, HeuristicResult, FactualityResult, HybridResult
│   └── exceptions.py      # Service-level exceptions
│
├── services/
│   ├── pdqi_service.py    # Interface + O3/NineRings implementations (Strategy pattern)
│   ├── heuristic_service.py
│   ├── factuality_service.py
│   └── grading_service.py # Coordinates above, calculates hybrid score
│
├── adapters/
│   └── azure/
│       ├── client.py      # AzureLLMClient (Factory + Singleton for pool reuse)
│       └── pdqi_adapter.py
│
├── http/
│   └── routes.py          # Flask blueprints using GradingService
│
└── main.py                # create_app() factory + run
```

## 4. Design Patterns Applied

* **Factory & Singleton** – Produce configured `AzureLLMClient` instances once.
* **Strategy** – Swappable PDQI evaluators (`O3Strategy`, `NineRingsStrategy`).
* **Facade** – `GradingService` exposes simple `grade()` hiding internal steps.
* **Adapter** – Wrap Azure SDK behind `LLMClient` port for easy mocking.
* **Dependency Injection** – Pass interfaces into services; keep globals only in `main.py`.

## 5. Migration Steps

1. **Create `domain` models** using `@dataclass`, move `viewmodels.py` logic here.
2. **Extract `AzureLLMClient`** wrapper (handles retries, json parsing, logging).
3. **Refactor PDQI logic**
   * Convert `O3Judge` into `O3PDQIStrategy` implementing `PDQIService` protocol.
   * Move Nine-Rings orchestration under same interface.
4. **Refactor factuality** into `FactualityService` with sync (O3) & async (GPT-4o) paths.
5. **Convert heuristics functions** into a stateless `HeuristicService` class.
6. **Implement `GradingService`**
   * Inject PDQI, Heuristic, Factuality services.
   * Provide `grade_note()` returning `HybridResult`.
7. **HTTP layer**
   * Replace `app.py` with Flask application factory (`create_app`).
   * Organize routes in `http/routes.py`; marshmallow / pydantic for validation.
8. **Configuration**
   * Keep `config.py` but expose via `pydantic.BaseSettings` for type-safe env parsing.
9. **Testing**
   * Update tests to target service interfaces.
   * Use `pytest` fixtures + `unittest.mock` for Azure client.
10. **CI/Lint**
   * Enable `ruff` + `mypy` for static analysis.

## 6. Code Quality Checklist

- [ ] Full type hints & `mypy` clean.
- [ ] PEP 8 via `ruff`/`black` autofmt.
- [ ] No side-effectful code at import-time (only in `main.py`).
- [ ] Centralized logging configuration.
- [ ] Exhaustive unit tests for every service (> 90% coverage).

## 7. Stretch Goals

* Plug-in support for additional LLM providers.
* Async Flask (Quart/FastAPI) for higher throughput.
* Front-end rewrite in React + Tailwind (API-first backend remains unchanged).

---

_This roadmap serves as the single source of truth throughout the refactor. Keep PRs small and incremental, guided by sections above._ 