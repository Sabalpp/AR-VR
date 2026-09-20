"""
Inference: load a trained condition classifier and predict from a .skel file.

Falls back cleanly if no model has been trained yet, so the rest of the system
(Gemini diagnosis, portal) keeps working without a model artifact.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..core.skel import parse_skel
from .dataset import featurize, LabelSpace

MODELS_DIR = Path("models")


class ConditionClassifier:
    def __init__(self, models_dir: str | Path = MODELS_DIR):
        self.dir = Path(models_dir)
        self.model = None
        self.labels: LabelSpace | None = None
        self.meta: dict = {}

    @property
    def available(self) -> bool:
        return (self.dir / "condition_net.keras").exists()

    def load(self) -> "ConditionClassifier":
        import tensorflow as tf
        self.model = tf.keras.models.load_model(self.dir / "condition_net.keras")
        self.labels = LabelSpace(**json.loads((self.dir / "label_space.json").read_text()))
        self.meta = json.loads((self.dir / "training_meta.json").read_text())
        return self

    def predict_file(self, skel_path: str, threshold: float = 0.5) -> list[dict]:
        if self.model is None:
            self.load()
        rec = parse_skel(skel_path)
        kind = self.meta.get("feature_kind", "angles")
        x = featurize(rec, kind)[None, ...]
        probs = self.model.predict(x, verbose=0)[0]
        return [
            {"condition_id": cid, "confidence": round(conf, 3)}
            for cid, conf in self.labels.decode(probs, threshold)
        ]
