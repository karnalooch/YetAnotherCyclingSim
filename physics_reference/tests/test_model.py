"""Unit tests for the reference cycling physics data contracts."""

import dataclasses
import math
import unittest

from cycling_physics import (
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
)


def _valid_rider():
    return RiderParameters(
        rider_mass_kg=75.0,
        bike_mass_kg=8.5,
        cda_m2=0.32,
        rolling_resistance_coefficient=0.004,
        drivetrain_efficiency=0.97,
    )


def _valid_environment():
    return Environment(
        grade_decimal=0.05,
        wind_speed_mps=0.0,
        air_density_kg_m3=1.225,
    )


def _valid_rider_input():
    return RiderInput(power_w=250.0, cadence_rpm=90.0)


def _valid_simulation_state():
    return SimulationState(speed_mps=10.0, distance_m=1200.0, elapsed_time_s=120.0)


class TestValidData(unittest.TestCase):
    def test_rider_parameters_accepted(self):
        rider = _valid_rider()
        self.assertEqual(
            rider,
            RiderParameters(75.0, 8.5, 0.32, 0.004, 0.97),
        )

    def test_environment_accepted(self):
        env = _valid_environment()
        self.assertEqual(env.grade_decimal, 0.05)
        self.assertEqual(env.wind_speed_mps, 0.0)
        self.assertEqual(env.air_density_kg_m3, 1.225)

    def test_rider_input_accepted(self):
        rider_input = _valid_rider_input()
        self.assertEqual(rider_input.power_w, 250.0)
        self.assertEqual(rider_input.cadence_rpm, 90.0)

    def test_simulation_state_accepted(self):
        state = _valid_simulation_state()
        self.assertEqual(state.speed_mps, 10.0)
        self.assertEqual(state.distance_m, 1200.0)
        self.assertEqual(state.elapsed_time_s, 120.0)

    def test_fields_are_stored_as_floats(self):
        rider = _valid_rider()
        for field in dataclasses.fields(rider):
            self.assertIsInstance(getattr(rider, field.name), float)

    def test_integer_input_is_stored_as_float(self):
        rider = RiderParameters(75, 8, 0.32, 0.004, 0.97)
        self.assertIsInstance(rider.rider_mass_kg, float)
        self.assertEqual(rider.rider_mass_kg, 75.0)


class TestBoundaryValues(unittest.TestCase):
    def test_zero_allowed_for_non_negative_fields(self):
        rider = RiderParameters(75.0, 8.5, 0.32, 0.0, 1.0)
        self.assertEqual(rider.rolling_resistance_coefficient, 0.0)

        rider_input = RiderInput(power_w=0.0, cadence_rpm=0.0)
        self.assertEqual(rider_input.power_w, 0.0)
        self.assertEqual(rider_input.cadence_rpm, 0.0)

        state = SimulationState(speed_mps=0.0, distance_m=0.0, elapsed_time_s=0.0)
        self.assertEqual(state.speed_mps, 0.0)
        self.assertEqual(state.distance_m, 0.0)
        self.assertEqual(state.elapsed_time_s, 0.0)

    def test_grade_and_wind_may_be_negative(self):
        env = _valid_environment()
        self.assertEqual(env.grade_decimal, 0.05)

        descent = Environment(grade_decimal=-0.08, wind_speed_mps=0.0, air_density_kg_m3=1.2)
        self.assertEqual(descent.grade_decimal, -0.08)

        tailwind = Environment(grade_decimal=0.0, wind_speed_mps=-4.5, air_density_kg_m3=1.2)
        self.assertEqual(tailwind.wind_speed_mps, -4.5)


class TestValidationErrors(unittest.TestCase):
    def assert_raises_value_error(self, factory, field_name, value):
        with self.assertRaises(ValueError) as context:
            factory(**{field_name: value})
        self.assertIn(field_name, str(context.exception))

    def test_positive_fields_reject_zero_and_negative(self):
        for value in (0.0, -1.0, -0.001):
            with self.subTest(value=value):
                self.assert_raises_value_error(
                    lambda **kw: RiderParameters(
                        rider_mass_kg=kw.get("rider_mass_kg", 75.0),
                        bike_mass_kg=kw.get("bike_mass_kg", 8.5),
                        cda_m2=kw.get("cda_m2", 0.32),
                        rolling_resistance_coefficient=kw.get("rolling_resistance_coefficient", 0.004),
                        drivetrain_efficiency=kw.get("drivetrain_efficiency", 0.97),
                    ),
                    "rider_mass_kg",
                    value,
                )
                self.assert_raises_value_error(
                    lambda **kw: RiderParameters(
                        rider_mass_kg=75.0,
                        bike_mass_kg=kw.get("bike_mass_kg", 8.5),
                        cda_m2=0.32,
                        rolling_resistance_coefficient=0.004,
                        drivetrain_efficiency=0.97,
                    ),
                    "bike_mass_kg",
                    value,
                )
                self.assert_raises_value_error(
                    lambda **kw: RiderParameters(
                        rider_mass_kg=75.0,
                        bike_mass_kg=8.5,
                        cda_m2=kw.get("cda_m2", 0.32),
                        rolling_resistance_coefficient=0.004,
                        drivetrain_efficiency=0.97,
                    ),
                    "cda_m2",
                    value,
                )
                self.assert_raises_value_error(
                    lambda **kw: Environment(
                        grade_decimal=0.0,
                        wind_speed_mps=0.0,
                        air_density_kg_m3=kw.get("air_density_kg_m3", 1.225),
                    ),
                    "air_density_kg_m3",
                    value,
                )

    def test_non_negative_fields_reject_negative_values(self):
        negative = -0.5

        with self.subTest(field="rolling_resistance_coefficient"):
            self.assert_raises_value_error(
                lambda **kw: RiderParameters(
                    rider_mass_kg=75.0,
                    bike_mass_kg=8.5,
                    cda_m2=0.32,
                    rolling_resistance_coefficient=kw.get("rolling_resistance_coefficient", 0.004),
                    drivetrain_efficiency=0.97,
                ),
                "rolling_resistance_coefficient",
                negative,
            )

        for field in ("power_w", "cadence_rpm"):
            with self.subTest(field=field):
                self.assert_raises_value_error(
                    lambda **kw: RiderInput(
                        power_w=kw.get("power_w", 250.0),
                        cadence_rpm=kw.get("cadence_rpm", 90.0),
                    ),
                    field,
                    negative,
                )

        for field in ("speed_mps", "distance_m", "elapsed_time_s"):
            with self.subTest(field=field):
                self.assert_raises_value_error(
                    lambda **kw: SimulationState(
                        speed_mps=kw.get("speed_mps", 10.0),
                        distance_m=kw.get("distance_m", 1200.0),
                        elapsed_time_s=kw.get("elapsed_time_s", 120.0),
                    ),
                    field,
                    negative,
                )

    def test_drivetrain_efficiency_must_be_in_open_unit_interval(self):
        for value in (0.0, -0.1, -1.0, 1.0001, 2.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RiderParameters(75.0, 8.5, 0.32, 0.004, value)

    def test_efficiency_boundary_of_one_is_accepted(self):
        rider = RiderParameters(75.0, 8.5, 0.32, 0.004, 1.0)
        self.assertEqual(rider.drivetrain_efficiency, 1.0)

    def test_non_finite_values_are_rejected(self):
        records = (
            ("RiderParameters", lambda **kw: RiderParameters(
                rider_mass_kg=kw.get("rider_mass_kg", 75.0),
                bike_mass_kg=kw.get("bike_mass_kg", 8.5),
                cda_m2=kw.get("cda_m2", 0.32),
                rolling_resistance_coefficient=kw.get("rolling_resistance_coefficient", 0.004),
                drivetrain_efficiency=kw.get("drivetrain_efficiency", 0.97),
            ), ("rider_mass_kg", "bike_mass_kg", "cda_m2", "rolling_resistance_coefficient", "drivetrain_efficiency")),
            ("Environment", lambda **kw: Environment(
                grade_decimal=kw.get("grade_decimal", 0.05),
                wind_speed_mps=kw.get("wind_speed_mps", 0.0),
                air_density_kg_m3=kw.get("air_density_kg_m3", 1.225),
            ), ("grade_decimal", "wind_speed_mps", "air_density_kg_m3")),
            ("RiderInput", lambda **kw: RiderInput(
                power_w=kw.get("power_w", 250.0),
                cadence_rpm=kw.get("cadence_rpm", 90.0),
            ), ("power_w", "cadence_rpm")),
            ("SimulationState", lambda **kw: SimulationState(
                speed_mps=kw.get("speed_mps", 10.0),
                distance_m=kw.get("distance_m", 1200.0),
                elapsed_time_s=kw.get("elapsed_time_s", 120.0),
            ), ("speed_mps", "distance_m", "elapsed_time_s")),
        )

        for name, factory, fields in records:
            for field in fields:
                for value in (math.inf, -math.inf, math.nan):
                    with self.subTest(record=name, field=field, value=value):
                        with self.assertRaises(ValueError):
                            factory(**{field: value})

    def test_non_numeric_values_are_rejected(self):
        for value in (None, True, "75.0"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RiderParameters(value, 8.5, 0.32, 0.004, 0.97)


class TestRecordProperties(unittest.TestCase):
    def test_records_are_immutable(self):
        rider = _valid_rider()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rider.rider_mass_kg = 80.0

    def test_records_use_slots(self):
        rider = _valid_rider()
        env = _valid_environment()
        rider_input = _valid_rider_input()
        state = _valid_simulation_state()
        for record in (rider, env, rider_input, state):
            with self.subTest(record=type(record).__name__):
                self.assertFalse(hasattr(record, "__dict__"))


if __name__ == "__main__":
    unittest.main()
