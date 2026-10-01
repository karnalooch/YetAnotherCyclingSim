"""Synthetic mixed-surface reference tests; not calibrated gravel or UE proof."""

import importlib.util
import json
import math
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from cycling_physics.grip_policy import SurfaceGripPolicy, SurfaceGripRule
from cycling_physics.model import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    rolling_resistance_force_n,
    step_simulation,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "run_mixed_surface.py"
spec = importlib.util.spec_from_file_location("mixed_surface_example", EXAMPLE)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)


class TestMixedSurfaceReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run = example.run_reference()

    def setUp(self):
        self.profile = example.make_profile()
        self.policy = example.make_grip_policy()
        self.rolling = {"asphalt": 1.0, "gravel": 2.0}
        self.ambient = Environment(0.0, 0.0, 1.225)
        self.rider = RiderParameters(75.0, 10.0, 0.4, 0.004, 0.97)
        self.input = RiderInput(250.0, 90.0)

    def resolve(self, distance, **options):
        return example.environment_at(
            options.get("profile", self.profile),
            SimulationState(8.0, distance, 12.0),
            options.get("ambient", self.ambient),
            options.get("policy", self.policy),
            options.get("rolling", self.rolling),
        )

    def test_exact_surface_boundaries(self):
        for distance, expected in (
            (0.0, "asphalt"),
            (math.nextafter(100.0, 0.0), "asphalt"),
            (100.0, "gravel"),
            (math.nextafter(200.0, 0.0), "gravel"),
            (200.0, "asphalt"),
            (300.0, "asphalt"),
        ):
            with self.subTest(distance=distance):
                self.assertEqual(self.resolve(distance)[0], expected)

    def test_one_continuous_asphalt_gravel_asphalt_ride(self):
        self.assertEqual(
            [entry["surface_id"] for entry in self.run["transitions"]],
            ["asphalt", "gravel", "asphalt"],
        )
        self.assertGreaterEqual(self.run["final_state"]["distance_m"], 300.0)
        self.assertEqual(len(self.run["states"]), self.run["steps"] + 1)

    def test_transitions_use_the_existing_state_without_resets(self):
        states = self.run["states"]
        for entry in self.run["transitions"][1:]:
            index = states.index(entry["state"])
            boundary = 100.0 if entry["surface_id"] == "gravel" else 200.0
            self.assertLess(states[index - 1]["distance_m"], boundary)
            self.assertGreaterEqual(entry["state"]["distance_m"], boundary)
            self.assertGreater(entry["state"]["elapsed_time_s"], 0.0)

    def test_no_distance_or_time_teleport(self):
        states = self.run["states"]
        for before, after in zip(states, states[1:]):
            self.assertAlmostEqual(
                after["elapsed_time_s"] - before["elapsed_time_s"],
                example.FIXED_STEP_S,
                places=11,
            )
            self.assertAlmostEqual(
                after["distance_m"] - before["distance_m"],
                0.5 * (before["speed_mps"] + after["speed_mps"]) * example.FIXED_STEP_S,
                places=11,
            )
            self.assertEqual(after["lateral_position_m"], before["lateral_position_m"])

    def test_results_are_finite_and_forward(self):
        for state in self.run["states"]:
            self.assertTrue(all(math.isfinite(value) for value in state.values()))
            self.assertGreaterEqual(state["speed_mps"], 0.0)
            self.assertGreaterEqual(state["distance_m"], 0.0)

    def test_replay_is_exactly_deterministic(self):
        self.assertEqual(example.run_reference(), self.run)

    def test_substep_batching_does_not_change_the_result(self):
        self.assertEqual(example.run_reference(batch_size=7), self.run)

    def test_missing_rolling_policy_fails(self):
        with self.assertRaisesRegex(ValueError, "Missing rolling policy"):
            self.resolve(100.0, rolling={"asphalt": 1.0})

    def test_missing_grip_policy_fails(self):
        policy = SurfaceGripPolicy("Missing gravel", (SurfaceGripRule("asphalt", 1.0, 1.0),))
        with self.assertRaisesRegex(ValueError, "not configured"):
            self.resolve(100.0, policy=policy)

    def test_unknown_surface_does_not_fall_back_to_asphalt(self):
        samples = list(self.profile.samples)
        samples[1] = replace(samples[1], surface_id="unknown")
        profile = replace(self.profile, samples=tuple(samples))
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.resolve(100.0, profile=profile)

    def test_rolling_and_grip_compose_without_mutating_ambient(self):
        ambient = replace(self.ambient, rolling_resistance_multiplier=1.5, grip_multiplier=0.8)
        _, resolved = self.resolve(100.0, ambient=ambient)
        self.assertEqual(resolved.rolling_resistance_multiplier, 3.0)
        self.assertAlmostEqual(resolved.grip_multiplier, 0.6)
        self.assertEqual(self.resolve(100.0, ambient=ambient)[1], resolved)
        self.assertEqual(ambient.rolling_resistance_multiplier, 1.5)
        self.assertEqual(ambient.grip_multiplier, 0.8)

    def test_invalid_rolling_coefficients_are_rejected(self):
        for value in (0.0, -1.0, math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.resolve(100.0, rolling={"gravel": value})

    def test_wetness_uses_explicit_grip_policy(self):
        _, environment = self.resolve(100.0, profile=example.make_profile(wetness=0.5))
        self.assertEqual(environment.surface_wetness, 0.5)
        self.assertEqual(environment.grip_multiplier, 0.625)
        self.assertEqual(environment.rolling_resistance_multiplier, 2.0)

    def test_return_to_asphalt_preserves_legacy_step_exactly(self):
        state = SimulationState(8.0, 200.0, 12.0)
        _, environment = self.resolve(200.0)
        self.assertEqual(environment, self.ambient)
        self.assertEqual(
            step_simulation(self.rider, environment, self.input, state, example.FIXED_STEP_S),
            step_simulation(self.rider, self.ambient, self.input, state, example.FIXED_STEP_S),
        )

    def test_rolling_change_uses_force_not_a_speed_penalty(self):
        _, asphalt = self.resolve(0.0)
        _, gravel = self.resolve(100.0)
        self.assertAlmostEqual(
            rolling_resistance_force_n(self.rider, gravel),
            2.0 * rolling_resistance_force_n(self.rider, asphalt),
        )
        state = SimulationState(8.0, 100.0, 12.0)
        after_gravel = step_simulation(self.rider, gravel, self.input, state, example.FIXED_STEP_S)
        after_asphalt = step_simulation(self.rider, asphalt, self.input, state, example.FIXED_STEP_S)
        self.assertLess(after_gravel.speed_mps, after_asphalt.speed_mps)
        self.assertEqual(state.speed_mps, 8.0)

    def test_grip_alone_is_not_a_straight_line_speed_penalty(self):
        state = SimulationState(8.0, 100.0, 12.0)
        self.assertEqual(
            step_simulation(self.rider, self.ambient, self.input, state, example.FIXED_STEP_S),
            step_simulation(self.rider, replace(self.ambient, grip_multiplier=0.25), self.input, state, example.FIXED_STEP_S),
        )

    def test_invalid_batch_sizes_fail(self):
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                example.run_reference(batch_size=value)

    def test_cli_marks_synthetic_evidence_and_emits_summary(self):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, str(EXAMPLE)],
            check=True, capture_output=True, text=True, env=environment, timeout=30,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["notice"], example.FIXTURE_NOTICE)
        self.assertNotIn("states", report)
        self.assertEqual(report["final_state"], self.run["final_state"])


if __name__ == "__main__":
    unittest.main()
