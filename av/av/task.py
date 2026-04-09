import numpy as np
import os
from keras.models import Model
from keras.layers import Input, Dense, Flatten, Reshape
from typing import Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CURRENT_DIR  = os.path.dirname(os.path.abspath(__file__))            # av/av/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_DIR))         # project root
_CAN_DIR      = os.path.join(_PROJECT_ROOT, "gp", "can_processed")    # gp/can_processed/

# Client ID → attack-type name mapping (one client per attack dataset)
CLIENT_DATASETS = {
    0: "DoS",
    1: "Fuzzy",
    2: "RPM",
    3: "gear",
}


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_npy(name: str, split: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load a preprocessed (name)_X_{split}.npy / (name)_y_{split}.npy pair."""
    X = np.load(os.path.join(_CAN_DIR, f"{name}_X_{split}.npy"))
    y = np.load(os.path.join(_CAN_DIR, f"{name}_y_{split}.npy")).astype(np.float32)
    # Add channel dim for Conv1D: (N, features) → (N, features, 1)
    X = np.expand_dims(X, axis=2)
    print(f"Loaded {name} {split} — X: {X.shape}, y: {y.shape}")
    return X, y


def load_can_data(client_id: int, split: str = "train") -> Tuple[np.ndarray, np.ndarray]:
    """
    Load the preprocessed CAN sliding-window dataset for a given client.

    Args:
        client_id: Integer 0-3, maps to DoS / Fuzzy / RPM / gear respectively.
        split:     'train' or 'test'.
    """
    name = CLIENT_DATASETS[client_id]
    return _load_npy(name, split)


def load_server_data(split: str = "train") -> Tuple[np.ndarray, np.ndarray]:
    """
    Load the combined server dataset (normal + all 4 attack types).
    Used for server-side pre-training and evaluation.

    Args:
        split: 'train' or 'test'.
    """
    return _load_npy("server", split)


# ---------------------------------------------------------------------------
# GIDS model architecture
#   D1  — supervised discriminator  (detects known attacks)
#   D2  — adversarial discriminator (anomaly detector, trained vs Generator)
#   G   — generator                 (produces fake normal samples from noise)
# ---------------------------------------------------------------------------

LATENT_DIM = 100   # Gaussian noise input dimension for the Generator


def build_discriminator_1(input_shape: tuple) -> Model:
    """
    1st Discriminator (D1) — supervised binary classifier.
    Trained on labeled data (normal=0, attack=1) to detect known attacks.
    DNN architecture mirrors the discriminator in the GIDS paper.
    """
    inp = Input(shape=input_shape, name='d1_input')
    x   = Flatten(name='d1_flatten')(inp)
    x   = Dense(128, activation='relu',    name='d1_dense1')(x)
    x   = Dense(64,  activation='relu',    name='d1_dense2')(x)
    out = Dense(1,   activation='sigmoid', name='d1_output')(x)
    model = Model(inputs=inp, outputs=out, name='discriminator_1')
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model


def build_discriminator_2(input_shape: tuple) -> Model:
    """
    2nd Discriminator (D2) — adversarial anomaly detector.
    Trained to distinguish real normal CAN samples (label=1) from Generator
    fakes (label=0).  At inference, samples scoring < 0.5 are flagged as
    anomalies (they do not look like real normal traffic).
    """
    inp = Input(shape=input_shape, name='d2_input')
    x   = Flatten(name='d2_flatten')(inp)
    x   = Dense(128, activation='relu',    name='d2_dense1')(x)
    x   = Dense(64,  activation='relu',    name='d2_dense2')(x)
    out = Dense(1,   activation='sigmoid', name='d2_output')(x)
    model = Model(inputs=inp, outputs=out, name='discriminator_2')
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model


def build_generator(input_shape: tuple) -> Model:
    """
    Generator (G) — maps Gaussian noise → fake normal CAN feature vectors.
    Output shape matches the discriminator input so D2 can evaluate fakes.
    The Generator is kept local on each client and never federated.
    """
    n_features = input_shape[0]
    inp = Input(shape=(LATENT_DIM,), name='g_input')
    x   = Dense(64,         activation='relu', name='g_dense1')(inp)
    x   = Dense(128,        activation='relu', name='g_dense2')(x)
    x   = Dense(256,        activation='relu', name='g_dense3')(x)
    x   = Dense(n_features, activation='tanh', name='g_dense4')(x)
    out = Reshape((n_features, 1),             name='g_output')(x)
    return Model(inputs=inp, outputs=out, name='generator')


def build_gan(generator: Model, d2: Model) -> Model:
    """
    Combined GAN: Generator feeds into a *frozen* D2.
    Used exclusively to train G to fool D2.
    After building, D2's standalone trainability is restored so it can
    still be trained directly with train_on_batch.
    """
    d2.trainable = False
    noise    = Input(shape=(LATENT_DIM,), name='gan_input')
    fake     = generator(noise)
    validity = d2(fake)
    gan      = Model(inputs=noise, outputs=validity, name='gan')
    gan.compile(optimizer='adam', loss='binary_crossentropy')
    # Restore D2 for standalone training
    d2.trainable = True
    d2.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return gan


# ---------------------------------------------------------------------------
# Shared GAN training loop (used by both server pre-training and clients)
# ---------------------------------------------------------------------------

def train_gan_epochs(
    generator: Model,
    d2: Model,
    gan: Model,
    X_normal: np.ndarray,
    epochs: int = 2,
    batch_size: int = 256,
) -> None:
    """
    Train the GAN for `epochs` epochs on normal-only CAN samples.
      • D2 step: real normal (label=1) vs Generator fakes (label=0)
      • G  step: noise → fake → D2, target=1  (G tries to fool D2)
    The Generator is called directly (.numpy()) to avoid Keras predict overhead.
    """
    N   = len(X_normal)
    idx = np.arange(N)
    for epoch in range(epochs):
        np.random.shuffle(idx)
        d2_losses, g_losses = [], []
        for start in range(0, N, batch_size):
            bi     = idx[start:start + batch_size]
            X_real = X_normal[bi]
            bs     = len(X_real)

            # --- Train D2: real=1, fake=0 ---
            noise  = np.random.normal(0, 1, (bs, LATENT_DIM)).astype(np.float32)
            X_fake = generator(noise, training=False).numpy()
            X_d2   = np.concatenate([X_real, X_fake], axis=0)
            y_d2   = np.concatenate([np.ones(bs), np.zeros(bs)]).astype(np.float32)
            d2_res = d2.train_on_batch(X_d2, y_d2)

            # --- Train G via GAN: noise → D2(fake), target=1 ---
            noise2 = np.random.normal(0, 1, (bs, LATENT_DIM)).astype(np.float32)
            g_res  = gan.train_on_batch(noise2, np.ones(bs).astype(np.float32))

            d2_losses.append(d2_res[0] if isinstance(d2_res, (list, tuple)) else d2_res)
            g_losses.append(g_res[0]   if isinstance(g_res,  (list, tuple)) else g_res)

        print(f"  GAN Epoch {epoch+1}/{epochs} "
              f"— D2 loss: {np.mean(d2_losses):.4f}  "
              f"G loss: {np.mean(g_losses):.4f}")