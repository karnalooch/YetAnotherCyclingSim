"""Unit tests for the reference cycling physics data contracts."""

import dataclasses
import math
import unittest

from cycling_physics import (
    STANDARD_GRAVITY_MPS2,
    Environment,
    RiderInput,
    RiderParameters,
    SimulationState,
    aerodynamic_force_n,
    gravitational_force_n,
    road_angle_rad,
    rolling_resistance_force_n,
    step_simulation,
    total_resistance_force_n,
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


class TestForces(unittest.TestCase):
    def test_standard_gravity_constant(self):
        self.assertEqual(STANDARD_GRAVITY_MPS2, 9.80665)

    def test_total_mass_is_sum_of_rider_and_bike(self):
        rider = _valid_rider()
        self.assertEqual(rider.total_mass_kg, 75.0 + 8.5)

    def test_road_angle_flat(self):
        self.assertEqual(road_angle_rad(0.0), 0.0)

    def test_road_angle_climb_and_descent(self):
        self.assertEqual(road_angle_rad(0.1), math.atan(0.1))
        self.assertEqual(road_angle_rad(-0.1), math.atan(-0.1))

    def test_gravitational_force_on_flat_road_is_zero(self):
        env = Environment(grade_decimal=0.0, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        self.assertEqual(gravitational_force_n(_valid_rider(), env), 0.0)

    def test_gravitational_force_resists_motion_on_climb(self):
        rider = _valid_rider()
        env = Environment(grade_decimal=0.1, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        expected = rider.total_mass_kg * STANDARD_GRAVITY_MPS2 * math.sin(road_angle_rad(0.1))
        force = gravitational_force_n(rider, env)
        self.assertGreater(force, 0.0)
        self.assertAlmostEqual(force, expected, places=9)

    def test_gravitational_force_assists_motion_on_descent(self):
        rider = _valid_rider()
        env = Environment(grade_decimal=-0.1, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        expected = rider.total_mass_kg * STANDARD_GRAVITY_MPS2 * math.sin(road_angle_rad(-0.1))
        force = gravitational_force_n(rider, env)
        self.assertLess(force, 0.0)
        self.assertAlmostEqual(force, expected, places=9)

    def test_rolling_resistance_on_flat_road(self):
        rider = _valid_rider()
        env = Environment(grade_decimal=0.0, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        expected = rider.rolling_resistance_coefficient * rider.total_mass_kg * STANDARD_GRAVITY_MPS2
        force = rolling_resistance_force_n(rider, env)
        self.assertGreater(force, 0.0)
        self.assertAlmostEqual(force, expected, places=9)

    def test_rolling_resistance_is_non_negative_on_climb_and_descent(self):
        for grade in (0.1, -0.1):
            with self.subTest(grade=grade):
                env = Environment(grade_decimal=grade, wind_speed_mps=0.0, air_density_kg_m3=1.225)
                expected = (
                    0.004
                    * 83.5
                    * STANDARD_GRAVITY_MPS2
                    * math.cos(road_angle_rad(grade))
                )
                force = rolling_resistance_force_n(_valid_rider(), env)
                self.assertGreaterEqual(force, 0.0)
                self.assertAlmostEqual(force, expected, places=9)

    def test_aerodynamic_force_reference_value_zero_wind(self):
        rider = RiderParameters(75.0, 8.5, 0.32, 0.004, 0.97)
        env = Environment(grade_decimal=0.0, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        force = aerodynamic_force_n(rider, env, 10.0)
        self.assertAlmostEqual(force, 19.6, places=9)

    def test_aerodynamic_force_zero_speed_and_zero_wind_is_zero(self):
        force = aerodynamic_force_n(_valid_rider(), _valid_environment(), 0.0)
        self.assertEqual(force, 0.0)

    def test_aerodynamic_force_with_headwind(self):
        env = Environment(grade_decimal=0.0, wind_speed_mps=5.0, air_density_kg_m3=1.225)
        expected = 0.5 * 1.225 * 0.32 * (10.0 + 5.0) ** 2
        force = aerodynamic_force_n(_valid_rider(), env, 10.0)
        self.assertGreater(force, 19.6)
        self.assertAlmostEqual(force, expected, places=9)

    def test_aerodynamic_force_with_weak_tailwind(self):
        env = Environment(grade_decimal=0.0, wind_speed_mps=-4.0, air_density_kg_m3=1.225)
        expected = 0.5 * 1.225 * 0.32 * (10.0 - 4.0) ** 2
        force = aerodynamic_force_n(_valid_rider(), env, 10.0)
        self.assertGreater(force, 0.0)
        self.assertAlmostEqual(force, expected, places=9)

    def test_aerodynamic_force_with_strong_tailwind_is_negative(self):
        env = Environment(grade_decimal=0.0, wind_speed_mps=-15.0, air_density_kg_m3=1.225)
        relative = 10.0 - 15.0
        expected = 0.5 * 1.225 * 0.32 * relative * abs(relative)
        force = aerodynamic_force_n(_valid_rider(), env, 10.0)
        self.assertLess(force, 0.0)
        self.assertAlmostEqual(force, expected, places=9)

    def test_aerodynamic_force_rejects_invalid_speed(self):
        for speed in (-1.0, math.inf, -math.inf, math.nan, None):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    aerodynamic_force_n(_valid_rider(), _valid_environment(), speed)


class TestTotalResistanceForce(unittest.TestCase):
    def _flat_environment(self, wind_speed_mps=0.0):
        return Environment(
            grade_decimal=0.0,
            wind_speed_mps=wind_speed_mps,
            air_density_kg_m3=1.225,
        )

    def test_flat_road_no_wind_equals_rolling_plus_aerodynamic(self):
        rider = _valid_rider()
        env = self._flat_environment()
        expected = rolling_resistance_force_n(rider, env) + aerodynamic_force_n(rider, env, 10.0)
        force = total_resistance_force_n(rider, env, 10.0)
        self.assertGreater(force, 0.0)
        self.assertAlmostEqual(force, expected, places=9)

    def test_total_equals_sum_of_individually_computed_components(self):
        rider = _valid_rider()
        env = _valid_environment()
        expected = (
            gravitational_force_n(rider, env)
            + rolling_resistance_force_n(rider, env)
            + aerodynamic_force_n(rider, env, 10.0)
        )
        self.assertAlmostEqual(
            total_resistance_force_n(rider, env, 10.0),
            expected,
            places=9,
        )

    def test_climb_has_greater_total_resistance_than_flat_road(self):
        rider = _valid_rider()
        flat = self._flat_environment()
        climb = Environment(grade_decimal=0.1, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        flat_force = total_resistance_force_n(rider, flat, 10.0)
        climb_force = total_resistance_force_n(rider, climb, 10.0)
        self.assertGreater(climb_force, flat_force)

    def test_steep_descent_can_give_negative_result(self):
        rider = _valid_rider()
        descent = Environment(grade_decimal=-0.15, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        force = total_resistance_force_n(rider, descent, 5.0)
        self.assertLess(force, 0.0)

    def test_strong_tailwind_reduces_total_resistance(self):
        rider = _valid_rider()
        calm = self._flat_environment(wind_speed_mps=0.0)
        tailwind = self._flat_environment(wind_speed_mps=-20.0)
        calm_force = total_resistance_force_n(rider, calm, 10.0)
        tailwind_force = total_resistance_force_n(rider, tailwind, 10.0)
        self.assertLess(tailwind_force, calm_force)
        self.assertLess(tailwind_force, 0.0)

    def test_invalid_speed_raises_value_error(self):
        rider = _valid_rider()
        env = _valid_environment()
        for speed in (-1.0, math.inf, -math.inf, math.nan):
            with self.subTest(speed=speed):
                with self.assertRaises(ValueError):
                    total_resistance_force_n(rider, env, speed)


class TestStepSimulation(unittest.TestCase):
    def _flat_environment(self):
        return Environment(grade_decimal=0.0, wind_speed_mps=0.0, air_density_kg_m3=1.225)

    def _environment(self, grade_decimal):
        return Environment(grade_decimal=grade_decimal, wind_speed_mps=0.0, air_density_kg_m3=1.225)

    def _input(self, power_w):
        return RiderInput(power_w=power_w, cadence_rpm=90.0)

    def _state(self, speed_mps, distance_m=0.0, elapsed_time_s=0.0):
        return SimulationState(
            speed_mps=speed_mps,
            distance_m=distance_m,
            elapsed_time_s=elapsed_time_s,
        )

    def test_stopped_bike_on_flat_moves_with_positive_power(self):
        result = step_simulation(
            _valid_rider(),
            self._flat_environment(),
            self._input(250.0),
            self._state(0.0),
            1.0,
        )
        self.assertGreater(result.speed_mps, 0.0)
        self.assertGreater(result.distance_m, 0.0)

    def test_more_power_gives_more_speed_after_same_time(self):
        low = step_simulation(
            _valid_rider(),
            self._flat_environment(),
            self._input(100.0),
            self._state(0.0),
            5.0,
        )
        high = step_simulation(
            _valid_rider(),
            self._flat_environment(),
            self._input(500.0),
            self._state(0.0),
            5.0,
        )
        self.assertGreater(high.speed_mps, low.speed_mps)

    def test_no_power_on_flat_decelerates(self):
        result = step_simulation(
            _valid_rider(),
            self._flat_environment(),
            self._input(0.0),
            self._state(10.0),
            1.0,
        )
        self.assertLess(result.speed_mps, 10.0)
        self.assertGreaterEqual(result.speed_mps, 0.0)

    def test_no_power_on_descent_accelerates(self):
        result = step_simulation(
            _valid_rider(),
            self._environment(-0.1),
            self._input(0.0),
            self._state(10.0),
            1.0,
        )
        self.assertGreater(result.speed_mps, 10.0)

    def test_climb_gives_less_speed_than_flat_with_same_power(self):
        start = self._state(5.0)
        flat = step_simulation(
            _valid_rider(),
            self._flat_environment(),
            self._input(250.0),
            start,
            1.0,
        )
        climb = step_simulation(
            _valid_rider(),
            self._environment(0.1),
            self._input(250.0),
            start,
            1.0,
        )
        self.assertLess(climb.speed_mps, flat.speed_mps)

    def test_speed_is_never_negative(self):
        cases = (
            (_valid_rider(), self._flat_environment(), self._input(0.0), self._state(1.0), 20.0),
            (_valid_rider(), self._environment(-0.2), self._input(0.0), self._state(0.0), 5.0),
            (_valid_rider(), self._flat_environment(), self._input(0.0), self._state(0.0), 1.0),
            (_valid_rider(), self._flat_environment(), self._input(250.0), self._state(0.0), 1.0),
        )
        for rider, env, rider_input, state, dt in cases:
            with self.subTest(state=state):
                result = step_simulation(rider, env, rider_input, state, dt)
                self.assertGreaterEqual(result.speed_mps, 0.0)

    def test_distance_and_time_increase(self):
        start = self._state(10.0, distance_m=100.0, elapsed_time_s=50.0)
        result = step_simulation(_valid_rider(), self._flat_environment(), self._input(0.0), start, 2.0)
        self.assertGreater(result.distance_m, start.distance_m)
        self.assertAlmostEqual(result.elapsed_time_s, start.elapsed_time_s + 2.0, places=12)

    def test_input_state_is_not_mutated(self):
        start = self._state(10.0, distance_m=100.0, elapsed_time_s=50.0)
        step_simulation(_valid_rider(), self._flat_environment(), self._input(250.0), start, 1.0)
        self.assertEqual(start, self._state(10.0, distance_m=100.0, elapsed_time_s=50.0))

    def test_identical_inputs_give_identical_results(self):
        args = (_valid_rider(), self._flat_environment(), self._input(250.0), self._state(5.0), 1.0)
        first = step_simulation(*args)
        second = step_simulation(*args)
        self.assertEqual(first, second)

    def test_invalid_dt_raises_value_error(self):
        for dt in (0.0, -1.0, math.nan, math.inf, -math.inf, True, None):
            with self.subTest(dt=dt):
                with self.assertRaises(ValueError):
                    step_simulation(
                        _valid_rider(),
                        self._flat_environment(),
                        self._input(250.0),
                        self._state(5.0),
                        dt,
                    )

    def test_all_result_fields_are_finite(self):
        result = step_simulation(
            _valid_rider(),
            self._environment(0.05),
            self._input(250.0),
            self._state(5.0),
            1.0,
        )
        for field in dataclasses.fields(result):
            self.assertTrue(math.isfinite(getattr(result, field.name)))


class TestEnvironmentSurfaceAndGrip(unittest.TestCase):
    def _environment(self, **overrides):
        values = dict(
            grade_decimal=0.0,
            wind_speed_mps=0.0,
            air_density_kg_m3=1.225,
            surface_wetness=0.0,
            rolling_resistance_multiplier=1.0,
            grip_multiplier=1.0,
        )
        values.update(overrides)
        return Environment(**values)

    def test_three_argument_environment_gets_defaults(self):
        env = Environment(grade_decimal=0.0, wind_speed_mps=0.0, air_density_kg_m3=1.225)
        self.assertEqual(env.surface_wetness, 0.0)
        self.assertEqual(env.rolling_resistance_multiplier, 1.0)
        self.assertEqual(env.grip_multiplier, 1.0)

    def test_wetness_boundaries_allowed(self):
        dry = self._environment(surface_wetness=0.0)
        wet = self._environment(surface_wetness=1.0)
        self.assertEqual(dry.surface_wetness, 0.0)
        self.assertEqual(wet.surface_wetness, 1.0)

    def test_wetness_out_of_range_rejected(self):
        for wetness in (-0.001, 1.001, 2.0, -1.0):
            with self.subTest(wetness=wetness):
                with self.assertRaises(ValueError):
                    self._environment(surface_wetness=wetness)

    def test_rolling_resistance_multiplier_non_positive_rejected(self):
        for multiplier in (0.0, -1.0, -0.5):
            with self.subTest(multiplier=multiplier):
                with self.assertRaises(ValueError):
                    self._environment(rolling_resistance_multiplier=multiplier)

    def test_grip_out_of_range_rejected(self):
        for grip in (0.0, -1.0, 1.0001, 2.0):
            with self.subTest(grip=grip):
                with self.assertRaises(ValueError):
                    self._environment(grip_multiplier=grip)

    def test_non_numeric_surface_values_rejected(self):
        for value in (math.nan, math.inf, -math.inf, True, False, "0.5", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self._environment(surface_wetness=value)
                with self.assertRaises(ValueError):
                    self._environment(rolling_resistance_multiplier=value)
                with self.assertRaises(ValueError):
                    self._environment(grip_multiplier=value)

    def test_multiplier_1_25_increases_rolling_resistance_by_25_percent(self):
        rider = _valid_rider()
        base = rolling_resistance_force_n(rider, self._environment())
        scaled = rolling_resistance_force_n(
            rider,
            self._environment(rolling_resistance_multiplier=1.25),
        )
        self.assertAlmostEqual(scaled, base * 1.25, places=12)

    def test_surface_wetness_alone_does_not_change_rolling_resistance(self):
        rider = _valid_rider()
        dry = rolling_resistance_force_n(rider, self._environment(surface_wetness=0.0))
        wet = rolling_resistance_force_n(rider, self._environment(surface_wetness=1.0))
        self.assertEqual(dry, wet)

    def test_grip_multiplier_does_not_change_step_simulation(self):
        base = self._environment(grip_multiplier=1.0)
        limited = self._environment(grip_multiplier=0.5)
        start = SimulationState(speed_mps=5.0, distance_m=0.0, elapsed_time_s=0.0)
        rider = _valid_rider()
        rider_input = RiderInput(power_w=250.0, cadence_rpm=90.0)

        state = start
        for _ in range(200):
            state = step_simulation(rider, base, rider_input, state, 0.05)

        other_state = start
        for _ in range(200):
            other_state = step_simulation(rider, limited, rider_input, other_state, 0.05)

        self.assertEqual(state, other_state)


if __name__ == "__main__":
    unittest.main()
