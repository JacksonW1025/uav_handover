"""Recompute the published tight-turn entry treatments using the frozen policy archive."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile

import numpy as np


def gru_action(policy, observation, history):
    encoded = np.maximum(0, policy["input_weights"] @ observation + policy["input_bias"])
    from_input = policy["gru_input_weights"] @ encoded + policy["gru_input_bias"]
    from_history = policy["gru_hidden_weights"] @ history + policy["gru_hidden_bias"]
    input_reset, input_update, input_candidate = np.split(from_input, 3)
    hidden_reset, hidden_update, hidden_candidate = np.split(from_history, 3)
    reset = 1 / (1 + np.exp(-(input_reset + hidden_reset)))
    update = 1 / (1 + np.exp(-(input_update + hidden_update)))
    candidate = np.tanh(input_candidate + reset * hidden_candidate)
    next_history = (1 - update) * candidate + update * history
    return policy["output_weights"] @ next_history + policy["output_bias"]


def read_policy(policy_bytes):
    tensors = {
        "input_weights": ("0/weights", (16, 22)),
        "input_bias": ("0/biases", (16,)),
        "gru_input_weights": ("1/weights_input", (48, 16)),
        "gru_input_bias": ("1/biases_input", (48,)),
        "gru_hidden_weights": ("1/weights_hidden", (48, 16)),
        "gru_hidden_bias": ("1/biases_hidden", (48,)),
        "output_weights": ("2/weights", (4, 16)),
        "output_bias": ("2/biases", (4,)),
    }
    with tarfile.open(fileobj=BytesIO(policy_bytes)) as archive:
        policy = {}
        for name, (parameter, shape) in tensors.items():
            with archive.extractfile(f"actor/layers/{parameter}/parameters/data") as stream:
                policy[name] = np.frombuffer(stream.read(), dtype="<f4").reshape(shape).astype(float)
    return policy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path, help="Frozen policy.tar from the original build")
    args = parser.parse_args()
    evidence = json.loads(Path(__file__).with_name("replay.json").read_text())
    policy_bytes = args.policy.read_bytes()
    if sha256(policy_bytes).hexdigest() != evidence["policy_sha256"]:
        parser.error("policy archive SHA-256 differs from the frozen experiment")
    policy = read_policy(policy_bytes)
    frame = evidence["case"]["frames"][0]
    physical_reference = frame["physical_reference_input"]
    previous = frame["previous_action_input"]
    history = np.array(frame["gru_input"])
    observed_motor = (np.clip(previous, -1, 1)[[0, 2, 3, 1]] + 1) / 2
    for name, previous_input, gru_input in (
        ("reset", np.zeros(4), np.zeros(16)),
        ("action_only", previous, np.zeros(16)),
        ("gru_only", np.zeros(4), history),
        ("both", previous, history),
    ):
        raw = gru_action(policy, np.r_[physical_reference, previous_input], gru_input)
        recorded = frame["variants"][name]
        np.testing.assert_allclose(raw, recorded["raw_action"], rtol=0, atol=1e-6)
        motor = (np.clip(raw, -1, 1)[[0, 2, 3, 1]] + 1) / 2
        print(f"{name}: max motor step {np.max(np.abs(motor - observed_motor)):.6f}")


if __name__ == "__main__":
    main()
