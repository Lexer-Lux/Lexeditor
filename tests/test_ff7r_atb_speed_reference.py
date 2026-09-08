from games.ff7r.atb_speed_reference import analyze_speed_measurement_reference


def test_speed_reference_preserves_measured_points_without_claiming_exact_formula():
    result = analyze_speed_measurement_reference()

    assert result["exactSpeedFormulaValidated"] is False
    assert result["descriptiveFitOnly"] is True
    assert result["internalUnitsPerDisplayedBar"] == 1000.0
    assert [(row["speed"], row["oneBarSeconds"]) for row in result["passiveSamples"]] == [
        (45, 13.850),
        (50, 13.745),
        (55, 13.660),
        (65, 13.525),
        (80, 13.365),
    ]


def test_descriptive_linear_rate_fit_is_close_but_explicitly_not_promoted_as_formula():
    result = analyze_speed_measurement_reference()
    fit = result["descriptiveLinearRateFit"]

    assert 69.0 < fit["interceptInternalUnitsPerSecond"] < 69.1
    assert 0.073 < fit["slopeInternalUnitsPerSecondPerSpeed"] < 0.074
    # The empirical points are approximately linear in units/sec, but residuals
    # remain much larger than the source's +/-0.005 s measurement precision.
    assert 0.02 < fit["maxAbsoluteTimeResidualSeconds"] < 0.04
    assert result["measurementToleranceSeconds"] == 0.005
    assert result["descriptiveFitOnly"] is True


def test_haste_measurements_independently_reproduce_approximately_one_point_four_x_rate():
    result = analyze_speed_measurement_reference()
    haste = result["hasteReference"]

    assert haste["documentedMultiplier"] == 1.4
    assert 1.399 < haste["meanObservedMultiplier"] < 1.400
    assert [row["speed"] for row in haste["samples"]] == [50, 55, 65, 80]
    assert all(abs(row["errorFromDocumented1_4x"]) < 0.002 for row in haste["samples"])


def test_speed_reference_notes_forbid_using_fit_as_runtime_implementation():
    result = analyze_speed_measurement_reference()

    assert any("must never be used as the gameplay implementation" in note for note in result["notes"])
    assert any("No ResidentParameter row" in note for note in result["notes"])
