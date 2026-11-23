#!/usr/bin/env python3
"""Recompute the published T1–T4 observations without starting the simulator."""

import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def near(actual, expected, tolerance):
    assert math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance), (actual, expected)


def check_t1():
    turn = EVIDENCE / "t1/turn"
    summary = read_json(turn / "results.json")["arms"]
    timing = read_json(turn / "timing.json")
    for arm, expected in {"C2": 25.895, "N": 42.900, "PRE": 43.010}.items():
        row = summary[arm]
        native_peak = row["profile_peak_tilt"]["value"]
        near(native_peak, expected, 0.001)
        trajectory = read_csv(turn / f"{arm}-trajectory.csv")
        # The exported trajectory samples attitude at position timestamps.
        near(max(float(x["tilt_deg"]) for x in trajectory), native_peak, 0.01)
        near(
            max(float(x["descent_from_profile_m"]) for x in trajectory),
            row["profile_descent_peak"]["value"],
            1e-6,
        )
        if arm == "C2":
            assert row["first_35_us"] is None
            continue
        first_crossing = next(x for x in trajectory if float(x["tilt_deg"]) > 35)
        near(int(first_crossing["native_us"]), row["first_35_us"], 4000)
        info = timing[arm]
        active = info["first_active_native_us"]
        assert info["first_neural_actuator_us"] - active == 12000
        assert list(info["first_four_motor_application_us"].values()) == [active + 16000] * 4
        braking = read_csv(EVIDENCE / "t1/braking" / f"{arm}-dynamics.csv")
        clipped = [x for x in braking if abs(float(x["error_velocity_0"])) > 1]
        assert clipped and all(abs(float(x["input_velocity_0"])) == 1 for x in clipped)
        assert int(float(clipped[0]["native_us"])) < row["first_35_us"]
    print("T1 · three tight-turn arms, native takeover and input clipping")


def check_t2():
    straight = EVIDENCE / "t2/straight"
    arms = read_json(straight / "summary.json")["arms"]
    for arm, step, loss in [("N4", 0.02168, 0.01332), ("N2", 0.12972, 0.02633)]:
        row = arms[arm]
        actual_step = max(abs(a - b) for a, b in zip(row["first_output"], row["last_classic_output"]))
        near(actual_step, step, 5e-6)
        curve = read_csv(straight / f"{arm}-2.csv")
        first_second = [float(x["value"]) for x in curve if 0 <= float(x["seconds_from_entry"]) <= 1]
        near(max(first_second), loss, 5e-6)
        assert len(row["gazebo_first_neural_application"]) == 4
        for motor in row["gazebo_first_neural_application"].values():
            assert motor["applied_sample_us"] - row["entry_us"] == 12000
            assert motor["sim_us"] - row["entry_us"] == 16000
            assert motor["identity_match"] and motor["matches_first_published_neural"]
    replay = read_json(EVIDENCE / "t2/turn/replay.json")
    frame = replay["case"]["frames"][0]
    verification = replay["action_verification"]["frames"][0]
    assert frame["time_us"] == verification["time_us"] == replay["case"]["entry_us"]
    assert verification["entry_input_max_error"] == 0
    assert verification["minimum_clipped_action_error"] < 1e-6
    previous = [(frame["previous_action_input"][i] + 1) / 2 for i in (0, 2, 3, 1)]
    for name, expected in [("both", 0.0873), ("action_only", 0.1588)]:
        motors = frame["variants"][name]["output_motor"]
        near(max(abs(motor - last) for motor, last in zip(motors, previous)), expected, 5e-5)
    print("T2 · closed-loop straight pair and native turn-frame replay")


def check_t3():
    straight = EVIDENCE / "t3/straight/flight-analysis"
    cases = read_json(straight / "summary.json")["cases"]
    payloads = read_json(straight / "accepted-payload.json")
    assert len(cases) == len(payloads) == 2
    assert payloads[0]["accepted_payload"] == payloads[1]["accepted_payload"]
    for row, payload, gap, expected in zip(cases, payloads, (16, 80), (2.89, 7.28)):
        assert row["case"] == payload["case"]
        assert payload["accepted_payload"] == payload["sent_payload_float32"]
        payload_hash = hashlib.sha256(struct.pack("<8f", *payload["accepted_payload"])).hexdigest()
        assert payload_hash == payload["float32_payload_sha256"]
        assert payload["read_native_us"] == row["first_valid_reference_read_us"]
        assert row["first_valid_reference_read_us"] - row["first_four_application_us"] == gap * 1000
        assert row["all_pre_reference_targets_zero"]
        attitude = read_csv(straight / f"{row['case']}-physical.csv")
        near(max(float(x["tilt_deg"]) for x in attitude), expected, 0.005)

    turn = EVIDENCE / "t3/turn"
    rows = read_json(turn / "f1-summary.json")["rows"]
    expected_gaps = {"E1": [None, None], "E2": [156, 168], "E3": [16, 16]}
    actual_gaps = {arm: [] for arm in expected_gaps}
    for row in rows:
        run = turn / (row["case"] + "-a1")
        attitude = read_csv(run / "physical-attitude.csv.gz")
        position = read_csv(run / "physical-position.csv.gz")
        peak = max(float(x["tilt_deg"]) for x in attitude)
        near(peak, row["physical"]["peak_tilt_deg"], 1e-8)
        near(
            max(float(x["altitude_loss_entry_m"]) for x in position),
            row["physical"]["altitude_loss_entry_m"],
            1e-6,
        )
        chain = row.get("chain")
        gap = None
        if chain:
            gap = (chain["first_read_us"] - chain["first_four_application_us"]) / 1000
            assert gap == chain["first_read_minus_first_four_ms"]
            assert len(chain["four_motor_records"]) == 4
            assert chain["first_send"]["before_ns"] > max(
                motor["step_wall_ns"] for motor in chain["four_motor_records"]
            )
        actual_gaps[row["arm"]].append(gap)
        assert (peak > 55) == (row["arm"] == "E2")
    assert actual_gaps == expected_gaps
    print("T3 · fixed-payload straight pair and six tight-turn trajectories")


def check_t4():
    hover = EVIDENCE / "t4/hover"
    for line in (hover / "manifest.sha256").read_text().splitlines():
        checksum, path = line.split("  ", 1)
        assert hashlib.sha256((hover / path).read_bytes()).hexdigest() == checksum, path
    deliveries = read_json(hover / "raw-audit.json")["delivery"]
    accounting = read_json(hover / "sample-accounting.json")
    assert len(deliveries) == len(accounting) == 2
    for record, audited, delay, ordinal in zip(accounting, deliveries, (24, 4), (6, 1)):
        applied = record["first_N_apply_native_us"]
        publication = audited["first_publication_us"]
        assert applied - publication == delay * 1000
        samples = record["sample_details"]
        assert len(samples) == ordinal
        assert not any(any(x["four_applied"]) for x in samples[:-1])
        assert all(samples[-1]["four_applied"])
        assert len(audited["motors"]) == 4
        for motor in audited["motors"]:
            first_neural = next(x for x in motor["window"] if x["owner"] == [1])
            assert first_neural["sim_us"] == applied
            assert first_neural["sample_us"] == samples[-1]["sample_us"]
            assert first_neural["bridge_error"] == 0
    print("T4 · hover pair, motor-sample chain and archive hashes")


def check_docs():
    for document in ROOT.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            path = target.split("#", 1)[0]
            if path and "://" not in path:
                assert (document.parent / path).exists(), (document, path)


if __name__ == "__main__":
    check_t1()
    check_t2()
    check_t3()
    check_t4()
    check_docs()
    print("PASS · published T1–T4 evidence and local documentation links")
