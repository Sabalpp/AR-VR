"""
Temporal model for multi-label musculoskeletal condition classification.

Architecture: a 1D temporal convolutional stack (captures local movement
dynamics) followed by a bidirectional GRU (captures the whole-movement arc),
global pooling, and a sigmoid multi-label head — a recording can exhibit more
than one condition.

Input : (batch, SEQ_LEN, F)
Output: (batch, num_conditions) independent probabilities.
"""
from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import layers, models


def build_model(seq_len: int, n_features: int, n_classes: int,
                width: int = 64) -> tf.keras.Model:
    inp = layers.Input(shape=(seq_len, n_features), name="movement")

    x = inp
    for filters, k in [(width, 7), (width, 5), (width * 2, 3)]:
        x = layers.Conv1D(filters, k, padding="same")(x)
        x = layers.BatchNormalization()(x)
        x = layers.Activation("relu")(x)
        x = layers.MaxPooling1D(2)(x)

    x = layers.Bidirectional(layers.GRU(width, return_sequences=True))(x)
    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dense(width * 2, activation="relu")(x)
    x = layers.Dropout(0.4)(x)
    out = layers.Dense(n_classes, activation="sigmoid", name="conditions")(x)

    model = models.Model(inp, out, name="arpt_condition_net")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.AUC(name="auc", multi_label=True),
            tf.keras.metrics.BinaryAccuracy(name="acc", threshold=0.5),
        ],
    )
    return model
