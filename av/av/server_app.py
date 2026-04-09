"""
Federated GIDS — Flower Server App
====================================
The server:
  1. Pre-trains D1 (supervised) on the combined server dataset
     (normal + all 4 attack types) so clients start with a useful classifier.
  2. Pre-trains the GAN (Generator + D2) on normal data only, giving D2
     an initial ability to distinguish real normal samples from fakes.
  3. Distributes D1 + D2 initial weights to every client (Generator is local).
  4. After each round, evaluates the aggregated D1+D2 using GIDS combined
     detection: flag as attack if D1(x) > 0.5 OR D2(x) < 0.5.
"""

import flwr as fl
import numpy as np
from flwr.server.strategy import FedAvg
from flwr.common import ndarrays_to_parameters
from typing import Dict, List, Optional, Tuple

from .task import (
    load_server_data,
    build_discriminator_1,
    build_discriminator_2,
    build_generator,
    build_gan,
    train_gan_epochs,
)

# ---------------------------------------------------------------------------
# Server-side data and models
# ---------------------------------------------------------------------------

X_train_srv, y_train_srv = load_server_data(split="train")
X_test_srv,  y_test_srv  = load_server_data(split="test")

input_shape = (X_train_srv.shape[1], 1)

d1_model  = build_discriminator_1(input_shape)
d2_model  = build_discriminator_2(input_shape)
generator = build_generator(input_shape)
gan_model = build_gan(generator, d2_model)

_N_D1 = len(d1_model.get_weights())   # weight-array count for D1 (used to split params)


# ---------------------------------------------------------------------------
# Pre-training
# ---------------------------------------------------------------------------

def get_initial_parameters() -> List[np.ndarray]:
    """Pre-train D1 (supervised) and GAN (D2 + G) on the server dataset."""

    # --- D1: supervised binary classification (normal vs attack) ---
    print("\n--- SERVER: Pre-training D1 supervised (5 epochs) ---")
    d1_model.fit(X_train_srv, y_train_srv, epochs=5, batch_size=256, verbose=1)

    # --- GAN: train D2 + G on normal-only data ---
    print("\n--- SERVER: Pre-training GAN on normal data (3 epochs) ---")
    X_normal = X_train_srv[y_train_srv == 0]
    # Cap at 50 K samples so pre-training stays fast
    if len(X_normal) > 50_000:
        idx = np.random.choice(len(X_normal), 50_000, replace=False)
        X_normal = X_normal[idx]
    train_gan_epochs(generator, d2_model, gan_model, X_normal, epochs=3)

    print("--- SERVER: Pre-training complete ---\n")
    # Send D1 weights + D2 weights as the initial global parameters
    return d1_model.get_weights() + d2_model.get_weights()


# ---------------------------------------------------------------------------
# Server-side evaluation callback
# ---------------------------------------------------------------------------

def evaluate_fn(
    server_round: int,
    parameters: fl.common.NDArrays,
    config: Dict,
) -> Optional[Tuple[float, Dict]]:
    """
    GIDS combined detection:
      - D1(x) > 0.5  → known attack   (supervised discriminator)
      - D2(x) < 0.5  → anomaly        (adversarial discriminator)
      - attack if either condition holds
    """
    params = list(parameters)
    d1_model.set_weights(params[:_N_D1])
    d2_model.set_weights(params[_N_D1:])

    d1_pred = (d1_model.predict(X_test_srv, verbose=0) > 0.5).astype(int).flatten()
    d2_pred = (d2_model.predict(X_test_srv, verbose=0) < 0.5).astype(int).flatten()
    y_pred  = np.maximum(d1_pred, d2_pred)   # attack if either detector fires

    accuracy = float(np.mean(y_pred == y_test_srv.astype(int)))
    loss, _  = d1_model.evaluate(X_test_srv, y_test_srv, verbose=0)

    print(f"[Server  Round {server_round:2d}]  "
          f"D1 loss={loss:.4f}  GIDS accuracy={accuracy:.4f}")
    return loss, {"accuracy": accuracy}


# ---------------------------------------------------------------------------
# Strategy and app
# ---------------------------------------------------------------------------

strategy = FedAvg(
    fraction_fit=1.0,
    fraction_evaluate=1.0,
    min_fit_clients=4,
    min_evaluate_clients=4,
    min_available_clients=4,
    evaluate_fn=evaluate_fn,
    initial_parameters=ndarrays_to_parameters(get_initial_parameters()),
)

app = fl.server.ServerApp(
    config=fl.server.ServerConfig(num_rounds=3),
    strategy=strategy,
)
