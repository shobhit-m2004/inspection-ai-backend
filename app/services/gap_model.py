from functools import lru_cache
from typing import Tuple, List

import numpy as np

try:
    import xgboost as xgb
except Exception:
    xgb = None

SEVERITY_LABELS = {0: "Low", 1: "Medium", 2: "High"}


@lru_cache(maxsize=1)
def _load_model():
    if xgb is None:
        return None

    # Enhanced Synthetic training data
    # features: [avg_similarity, coverage, temporal_consistency, similarity_std]
    # temporal_consistency: 1.0 means log steps follow SOP order, 0.0 means random/reverse
    X = np.array([
        [0.95, 0.95, 1.0, 0.02], [0.9, 0.85, 0.9, 0.05], [0.88, 0.8, 0.95, 0.04],  # Low
        [0.7, 0.7, 0.6, 0.15], [0.65, 0.6, 0.5, 0.2], [0.6, 0.55, 0.7, 0.18],     # Medium
        [0.45, 0.4, 0.3, 0.25], [0.35, 0.3, 0.2, 0.3], [0.25, 0.2, 0.1, 0.35],    # High
    ], dtype=np.float32)
    y = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2], dtype=np.int32)

    dtrain = xgb.DMatrix(X, label=y)
    params = {
        "objective": "multi:softprob",
        "num_class": 3,
        "max_depth": 4,
        "eta": 0.2,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "mlogloss",
        "seed": 42,
    }
    model = xgb.train(params, dtrain, num_boost_round=50)
    return model


def predict_severity(
    avg_similarity: float, 
    coverage: float, 
    temporal_consistency: float = 1.0, 
    similarity_std: float = 0.05
) -> Tuple[str, float]:
    """
    Predict gap severity using XGBoost.

    :param avg_similarity: Average similarity between matched SOP chunks and logs
    :param coverage: Ratio of SOP chunks with at least one match above threshold
    :param temporal_consistency: Score (0-1) reflecting how well log events match SOP sequence
    :param similarity_std: Standard deviation of similarity scores (higher indicates inconsistent matching)
    """
    if xgb is None:
        # Fallback heuristic
        score = (avg_similarity * 0.4) + (coverage * 0.4) + (temporal_consistency * 0.2)
        if score >= 0.8:
            return "Low", 0.9
        if score >= 0.5:
            return "Medium", 0.6
        return "High", 0.8

    model = _load_model()
    if model is None:
        return "Medium", 0.5

    X = np.array([[avg_similarity, coverage, temporal_consistency, similarity_std]], dtype=np.float32)
    dtest = xgb.DMatrix(X)
    probs = model.predict(dtest)[0]
    label = int(np.argmax(probs))
    return SEVERITY_LABELS.get(label, "Medium"), float(np.max(probs))