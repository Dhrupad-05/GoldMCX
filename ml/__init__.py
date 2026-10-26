"""MCX Gold Intelligence ML training/inference package (root-level).

Layers:
- data_sources: coordinate configured official/provider history collection
  through the backend adapters (no scraping, no fabricated prices).
- dataset: validated aligned pair datasets with lineage + exclusion reasons.
- features: versioned contract-aware relative-value features shared by
  training and inference (train/score parity is tested).
- train: sklearn novelty pipeline with temporal (walk-forward) validation.
- evaluate: coverage/stability metrics plus the robust-MAD baseline.
- inference: loads the ACTIVE registered artifact, verifies checksum/schema,
  scores validated observations.
- jobs: idempotent daily sync -> features -> scoring workflow.
- train_model: one-command CLI that produces the .joblib artifact.

Nothing in this package fabricates observations: an insufficient validated
history FAILS explicitly instead of manufacturing rows.
"""
