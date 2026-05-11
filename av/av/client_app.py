"""
Federated GIDS — Flower Client App
=====================================
4 clients, one per attack type:
  Client 0 → DoS
  Client 1 → Fuzzy
  Client 2 → RPM
  Client 3 → gear

GIDS federation strategy per round:
  1. Receive global D1 + D2 weights from server.
  2. Train GAN (Generator + D2) on local NORMAL samples — D2 learns to
     distinguish real normal traffic from Generator fakes (unsupervised).
  3. Train D1 on all labeled local data (supervised, normal vs attack).
  4. Return updated D1 + D2 weights to the server for FedAvg aggregation.

Privacy: the Generator is kept entirely local and is never federated.
"""

import flwr as fl
import numpy as np
from typing import Dict, List, Tuple

from .task import (
    load_can_data,
    build_discriminator_1,
    build_discriminator_2,
    build_generator,
    build_gan,
    train_gan_epochs,
    CLIENT_DATASETS,
)

_N_CLIENTS = len(CLIENT_DATASETS)   # 4


# ---------------------------------------------------------------------------
# Flower Client
# ---------------------------------------------------------------------------

class FlowerClient(fl.client.NumPyClient):

    def __init__(self, node_id: int) -> None:
        self.X_train, self.y_train = load_can_data(node_id, split="train")
        self.X_test,  self.y_test  = load_can_data(node_id, split="test")

        input_shape    = (self.X_train.shape[1], 1)
        self.d1        = build_discriminator_1(input_shape)
        self.d2        = build_discriminator_2(input_shape)
        self.generator = build_generator(input_shape)
        self.gan       = build_gan(self.generator, self.d2)  # G→frozen D2

        self._n_d1 = len(self.d1.get_weights())   # used to split incoming params

        print(
            f"[Client {node_id}] Dataset: {CLIENT_DATASETS[node_id]}  "
            f"train={len(self.X_train):,}  test={len(self.X_test):,}  "
            f"features={self.X_train.shape[1]}"
        )

    # --- Parameter helpers ---

    def _get_weights(self) -> List:
        """Return D1 weights + D2 weights.  Generator stays local (private)."""
        return self.d1.get_weights() + self.d2.get_weights()

    def _set_weights(self, parameters: List) -> None:
        """Split incoming parameters: first _n_d1 arrays → D1, rest → D2."""
        params = list(parameters)
        self.d1.set_weights(params[:self._n_d1])
        self.d2.set_weights(params[self._n_d1:])

    # --- Flower interface ---

    def get_parameters(self, config: Dict) -> List:
        return self._get_weights()

    def fit(
        self,
        parameters: List,
        config: Dict,
    ) -> Tuple[List, int, Dict]:
        self._set_weights(parameters)

        # --- Step 1: GAN training (unsupervised) on local NORMAL samples ---
        X_normal = self.X_train[self.y_train == 0]
        print(f"  → GAN training on {len(X_normal):,} normal samples (2 epochs)")
        train_gan_epochs(
            self.generator, self.d2, self.gan,
            X_normal, epochs=2, batch_size=256,
        )

        # --- Step 2: D1 supervised training on all labeled local data ---
        print(f"  → D1 supervised training (2 epochs)")
        self.d1.fit(
            self.X_train, self.y_train,
            epochs=2, batch_size=256, verbose=0,
        )

        # Return D1 + D2 weights; Generator is never sent to the server
        return self._get_weights(), len(self.X_train), {}

    def evaluate(
        self,
        parameters: List,
        config: Dict,
    ) -> Tuple[float, int, Dict]:
        self._set_weights(parameters)

        # GIDS combined detection (mirrors server evaluate_fn)
        d1_pred = (self.d1.predict(self.X_test, verbose=0) > 0.5).astype(int).flatten()
        d2_pred = (self.d2.predict(self.X_test, verbose=0) < 0.5).astype(int).flatten()
        y_pred  = np.maximum(d1_pred, d2_pred)
        accuracy = float(np.mean(y_pred == self.y_test.astype(int)))

        loss, _ = self.d1.evaluate(self.X_test, self.y_test, verbose=0)
        return loss, len(self.X_test), {"accuracy": accuracy}


# ---------------------------------------------------------------------------
# Flower ClientApp entry point
# ---------------------------------------------------------------------------

def client_fn(context: fl.common.Context) -> fl.client.Client:
    raw = context.node_config.get("node_id")
    node_id = int(raw) if raw is not None else int(context.node_id) % _N_CLIENTS
    return FlowerClient(node_id).to_client()


client_app = fl.client.ClientApp(client_fn=client_fn)
