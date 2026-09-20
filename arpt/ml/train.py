"""
Training entry point for the condition classifier.

Usage:
    # train on real recordings labeled via a manifest
    python -m arpt.ml.train --manifest recordings/labels.json

    # bootstrap / validate the pipeline with synthetic data (no labels needed)
    python -m arpt.ml.train --synthetic

Saves to models/:
    condition_net.keras        the trained model
    label_space.json           condition id ordering for decoding
    training_meta.json         feature kind, seq len, metrics
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .dataset import (SEQ_LEN, ANGLE_KEYS, LabelSpace,
                      build_dataset, make_synthetic, load_manifest)
from .model import build_model

MODELS_DIR = Path("models")


def _split(X, Y, val_frac=0.2, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X))
    n_val = max(1, int(len(X) * val_frac))
    v, t = idx[:n_val], idx[n_val:]
    return X[t], Y[t], X[v], Y[v]


def train(manifest_path: str | None, synthetic: bool, kind: str,
          epochs: int, augment_factor: int, recordings_dir: str) -> None:
    labels = LabelSpace.default()

    if synthetic or manifest_path is None:
        print("Building SYNTHETIC dataset (pipeline validation mode)...")
        X, Y = make_synthetic(labels, kind=kind, per_class=60)
    else:
        print(f"Building dataset from manifest {manifest_path} ...")
        manifest = load_manifest(manifest_path)
        X, Y, labels = build_dataset(recordings_dir, manifest, kind=kind,
                                     augment_factor=augment_factor)

    print(f"Dataset: X={X.shape}  Y={Y.shape}  classes={len(labels.ids)}")
    Xtr, Ytr, Xval, Yval = _split(X, Y)

    model = build_model(SEQ_LEN, X.shape[-1], len(labels.ids))
    model.summary(print_fn=lambda s: print("  " + s))

    MODELS_DIR.mkdir(exist_ok=True)
    ckpt = MODELS_DIR / "condition_net.keras"
    callbacks = [
        __import__("tensorflow").keras.callbacks.ModelCheckpoint(
            str(ckpt), monitor="val_auc", mode="max", save_best_only=True),
        __import__("tensorflow").keras.callbacks.EarlyStopping(
            monitor="val_auc", mode="max", patience=8, restore_best_weights=True),
    ]

    hist = model.fit(Xtr, Ytr, validation_data=(Xval, Yval),
                     epochs=epochs, batch_size=32, callbacks=callbacks, verbose=2)

    model.save(ckpt)
    (MODELS_DIR / "label_space.json").write_text(json.dumps(labels.to_json(), indent=2))
    (MODELS_DIR / "training_meta.json").write_text(json.dumps({
        "feature_kind": kind,
        "seq_len": SEQ_LEN,
        "n_features": int(X.shape[-1]),
        "angle_keys": ANGLE_KEYS if kind == "angles" else None,
        "final_val_auc": float(max(hist.history.get("val_auc", [0]))),
        "final_val_acc": float(max(hist.history.get("val_acc", [0]))),
        "synthetic": bool(synthetic or manifest_path is None),
    }, indent=2))
    print(f"\nSaved model -> {ckpt}")
    print(f"Best val AUC: {max(hist.history.get('val_auc', [0])):.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=None, help="labels.json path")
    ap.add_argument("--synthetic", action="store_true", help="use synthetic data")
    ap.add_argument("--kind", default="angles", choices=["angles", "pose"])
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--augment-factor", type=int, default=40)
    ap.add_argument("--recordings-dir", default="recordings")
    args = ap.parse_args()
    train(args.manifest, args.synthetic, args.kind,
          args.epochs, args.augment_factor, args.recordings_dir)


if __name__ == "__main__":
    main()
