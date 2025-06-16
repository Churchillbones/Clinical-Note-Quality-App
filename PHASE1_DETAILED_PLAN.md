# Phase 1 – Foundational Refactor Plan

This phase lays the groundwork for a sustainable, test-driven, and extensible codebase.  The objective is **structural realignment**—introducing clear boundaries, core domain models, and infrastructure seams—while keeping all existing external behaviour (CLI, Flask routes, unit tests) green.

---

## 1. Scope & Objectives

* Carve out **Domain**, **Service**, **Adapter**, and **HTTP** layers (Clean Architecture alignment).
* Extract core **domain models** using `@dataclass`es with full type-hints.
* Introduce **strategy interfaces** for PDQI, Heuristics, and Factuality evaluation.
* Wrap Azure OpenAI SDK in a **singleton/factory client** to decouple service code from vendor SDK.
* Replace global config access with **pydantic-based settings** object injected where needed.
* Establish **tooling baseline**: `black`, `ruff`, `mypy`, `pytest-cov` (CI-ready).
* Maintain backward compatibility—Flask routes and public APIs must not break.

> Deliverables: new package skeleton, migrated domain models, service interfaces, Azure adapter, CI tooling, green tests.

---

## 2. Milestone Breakdown

| # | Milestone | Tasks | Owner | Exit Criteria |
|---|-----------|-------|-------|---------------|
| 1 | **Project Scaffolding** | • Create root package `clinical_note_quality/`.<br>• Add `domain/`, `services/`, `adapters/azure/`, `http/` sub-packages with `__init__.py`.<br>• Move existing modules but do **not** change logic yet. | BE | Directory tree exists, imports succeed. |
| 2 | **Domain Models** | • Move `viewmodels.py` → `domain/models.py`.<br>• Split into `PDQIScore`, `HeuristicResult`, `FactualityResult`, `HybridResult` dataclasses.<br>• Ensure immutability via `frozen=True` where appropriate.<br>• Write `mypy`-checked unit tests for constructors & `.to_dict()` helpers. | BE | Models pass lint/mypy, tests green. |
| 3 | **Settings Refactor** | • Install `pydantic[dotenv]`.<br>• Convert `config.py` to `settings.py` subclassing `BaseSettings`.<br>• Provide `Settings()` factory in `clinical_note_quality/__init__.py`.<br>• Update consumers (`grading/*`) to accept `settings: Settings` injected param (default to global singleton for now to avoid churn). | BE | App boots using env var or `.env`, settings override precedence verified via tests. |
| 4 | **Azure Client Adapter** | • Create `adapters/azure/client.py`.
  * Implements `class AzureLLMClient(LLMClientProtocol)` (PEP 544).<br>  * Ensures **Singleton** behaviour via private module-level instance or [`functools.lru_cache`](https://docs.python.org/3/library/functools.html#functools.lru_cache) factory.<br>  * Provides `chat_complete()` method with retry, logging, json coercion. | BE | Unit tests using `unittest.mock` validate retries & singleton semantics. |
| 5 | **PDQI Strategy Interface** | • Define `services/pdqi_service.py` implementing `PDQIService` protocol.<br>• Wrap `O3Judge` as `O3Strategy`.<br>• Stub `NineRingsStrategy`. | BE | Existing tests refactored; still green. |
| 6 | **Heuristic & Factuality Services** | • Move heuristics logic into service class.<br>• Create `FactualityService` protocol. | BE | Heuristic & factuality tests pass. |
| 7 | **GradingService Facade** | • Compose PDQI, Heuristic, Factuality services; proxy legacy function. | BE | Routes/tests functional, deprecation warning emitted. |
| 8 | **HTTP Layer Refactor** | • Convert `app.py` to blueprint and factory; keep compatibility. | BE | Flask app & tests pass. |
| 9 | **Tooling & CI** | • Add `pyproject.toml`, `pre-commit`, `pytest-cov` etc. | DevOps | Pipeline green. |

---

## 3. Detailed Task Checklist

### 3.1 Domain Layer
- [x] Define enumeration `PDQIDimension` for nine rubric keys.
- [x] Provide custom `__post_init__` validation ensuring scores ∈ 1-5.
- [x] Implement convenience `.average()` on `PDQIScore`.
- [ ] Add unit tests for edge cases (non-numeric, boundaries).

### 3.2 Adapter Layer
- [x] Implement back-off strategy (`exponential` with jitter) in `AzureLLMClient`.
- [ ] Centralise JSON repair logic (currently duplicated in `o3_judge`).
- [x] Support dependency injection of mock client via `LLMClientProtocol`.

### 3.3 Service Layer
- [x] Introduce `PDQIService` protocol and `O3Strategy` implementation.
- [ ] Refactor `heuristics` metrics into discrete private helpers but expose single public API.
- [ ] Ensure `mypy --strict` compliance.
- [ ] Write parameterised tests for heuristic categories.

### 3.4 Compatibility Patches
- [ ] Maintain shim functions in `grading/` that import and forward to new services for immediate backward compatibility.
- [ ] Mark with `warnings.warn("Module deprecated, use services.*", DeprecationWarning)`.

### 3.5 Documentation
- [ ] Update README architecture section with new diagram.
- [ ] Provide docstrings for every public class/method following Google style.

---

## 4. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Break existing API responses | High | Keep view-model serialisation unchanged until Phase 2; add contract tests using `pytest-schema` |
| Azure SDK rate limits while writing tests | Medium | Use `unittest.mock` patch; never hit network in unit tests |
| Big-bang refactor stalls progress | High | Work in vertical slices per milestone; CI must stay green after each PR |

---

## 5. Acceptance Criteria

* **All existing tests + new tests** pass with ≥ 95 % coverage at end of phase.
* `mypy --strict` and `ruff --fix --exit-non-zero-on-fix` produce no errors.
* Running `python -m clinical_note_quality.main` serves identical routes & payloads.
* Codebase directory structure matches **Module Breakdown** in `REFACTOR_PLAN.md`.

---

## 6. Timeline (Effort-Based)

| Week | Focus |
|------|-------|
| 1 | Milestones 1-3 (Scaffolding, Domain Models, Settings) |
| 2 | Milestones 4-6 (Azure Adapter, PDQI, Heuristics/Factuality) |
| 3 | Milestone 7 (GradingService) + legacy shims |
| 4 | Milestones 8-9 (HTTP refactor, Tooling/CI) + buffer & demos |

---

_Milestones 1-5 complete. Proceeding to milestone 6._ 