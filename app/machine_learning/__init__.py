"""
Machine learning layer.

Contract: code in this package is *pure* with respect to infrastructure.
Functions take and return in-memory data (DataFrames, arrays, loaded model
objects) and never touch the database, S3, or HTTP. The service layer
(``app/services``) loads data via repositories / adapters, calls into this
package, and persists the results.

Stages (one package each; add modules as needed):

    preprocessing/       raw records -> cleaned, aggregated tables
    feature_engineering/ cleaned tables -> model-ready feature matrices
    training/            feature matrices -> fitted models (returned, not saved)
    inference/           fitted models + features -> predictions
    evaluation_metrics/  predictions + actuals -> scores, best-model selection
    postprocessing/      raw predictions -> constrained / reconciled outputs

Feature code must be shared between training and inference so both build
identical inputs (avoids train/serve skew).
"""
