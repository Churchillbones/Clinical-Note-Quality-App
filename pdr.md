# Project Design Requirements (PDR)

## 1. Purpose

Provide a lightweight, VA‐compliant Flask service that grades clinician notes against the **PDQI‑9** rubric plus hybrid heuristics, using **Azure OpenAI O3** as the LLM judge.

## 2. Scope

* **Input**: JSON payload or HTML form containing a clinical note (mandatory) and an optional encounter transcript.
* **Output**: PDQI‑9 scores, heuristic stats, hybrid composite (JSON + rendered HTML).
* **Constraints**: Runs inside VA OpenShift; no PHI leaves tenant; external calls limited to Azure OpenAI (O3).

## 3. High‑Level Architecture

```mermaid
graph LR
A[Browser / API caller]
A -- POST /api/grade --> B(Flask App: app.py)
B --> C[o3_judge.py\n(O3 PDQI scoring)]
B --> D[heuristics.py\n(length, redundancy)]
B --> E[factuality.py\n(entailment check)]
C --> F[hybrid.py\n(weighted merge)]
F --> B
B -- JSON / HTML --> A
```

## 4. Code Layout

```
note-quality-app/
│ app.py              # Flask routes
│ config.py           # Azure creds + prompts
│ grading/
│   ├─ o3_judge.py    # LLM scoring
│   ├─ heuristics.py  # rule‑based metrics
│   ├─ factuality.py  # NLI entailment
│   └─ hybrid.py      # combine scores
│ templates/          # result.html, index.html
│ tests/              # pytest suite (see §8)
└─ requirements.txt   # pinned deps
```

## 5. Functional Requirements

|  ID  | Requirement                                                                              | Acceptance Criteria                  |   |
| ---- | ---------------------------------------------------------------------------------------- | ------------------------------------ | - |
|  F‑1 | **/api/grade** must return 200 with PDQI‑9 & hybrid JSON within 30 s for ≤6 k‑token note | Unit test passes & manual curl check |   |
|  F‑2 | **/ (HTML route)** renders a table of PDQI‑9 scores & overall grade                      | Selenium/Flask test client snapshot  |   |
|  F‑3 | Service must reject input > 20 000 characters with 413 status                            | test\_heuristics length penalty      | = |
|  F‑4 | All external HTTP calls are mocked during CI                                             | pytest passes without network        |   |

## 6. Non‑Functional Requirements

* **Security**: Use service account with least privilege; no secrets in logs.
* **Performance**: p95 latency ≤ 30 s; 20 RPS sustained (limited by O3 RPM).
* **Scalability**: Stateless Flask pods; scale via HPA on CPU or queue length.
* **Observability**: Prometheus metrics (`pipeline_elapsed_seconds`, `o3_tokens_total`).

## 7. Prompts & Models

* **O3 Deployment**: `gpt-o3` (Azure OpenAI 2024‑02‑15‑preview).
* **Prompt**: see `config.PDQI_INSTRUCTIONS` – must stay < 400 tokens.
* **Temperature**: `0.0` for deterministic grading.

## 8. Testing Strategy

### 8.1 Unit / Component (pytest)

* `test_o3_judge.py` – mock `openai.ChatCompletion.create`, assert 9 keys & 1‑5 range.
* `test_heuristics.py` – test length & redundancy penalties.
* `test_factuality.py` – mock NLI pipeline; assert entailment scoring.
* `test_hybrid.py` – full merge returns overall 0‑5.
* `test_app_routes.py` – Flask test client smoke tests `/` and `/api/grade`.

### 8.2 Integration

Nightly job (needs Azure creds) runs 10 sample notes through live O3; compare with stored golden JSON.

### 8.3 Coverage Goal

≥ 85 % line coverage on `grading/`.

## 9. Deployment

* **Container**: `python:3.11-slim` base; non‑root UID 1001.
* **Env Vars**: `AZ_OPENAI_ENDPOINT`, `AZ_OPENAI_KEY`, `AZ_O3_DEPLOYMENT`.
* **K8s Manifests**: see `k8s/` folder (Deployment, Service, Route, HPA).

## 10. Milestones (4‑week sprints)

|  Week | Deliverable                                        |
| ----- | -------------------------------------------------- |
|  1    | Flask skeleton, PDQI prompt, unit mocks            |
|  2    | Heuristics & factuality modules, full pytest green |
|  3    | HTML template, Dockerfile, OpenShift dev deploy    |
|  4    | Integration tests, docs, stakeholder demo          |

## 11. Open Questions

1. Final weight scheme for hybrid composite?  (Stakeholder calibration.)
2. Do we store graded notes for audits?  If yes, need encrypted PVC.
3. Which NLI model to standardize on for factuality (DeBERTa vs RoBERTa)?

## 12. References

* Stetson et al., *PDQI‑9: A Physician Documentation Quality Instrument*, J Biomed Inform 2012.
* Human Notes Evaluator (Sultan 2024) – [https://huggingface.co/spaces/abachaa/HNE](https://huggingface.co/spaces/abachaa/HNE).
* Croxford et al., *LLM as a Judge for PDQI‑9*, 2025 preprint.
