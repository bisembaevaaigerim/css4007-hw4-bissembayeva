import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import calculate, lookup


# calculate

def test_calculate_multiplication():
    result = calculate("48317 * 1.0947")
    assert "error" not in result
    assert abs(result["result"] - 52892.6199) < 0.0001


def test_calculate_q09_difference():
    result = calculate("37203 / 758.6 - 44675 / 921.4")
    assert round(result["result"], 1) == 0.6


def test_calculate_refuses_import():
    result = calculate("__import__('os').system('echo hi')")
    assert "error" in result
    assert "not allowed" in result["error"]


def test_calculate_refuses_class():
    result = calculate("(1).__class__")
    assert "error" in result
    assert "not allowed" in result["error"]


def test_calculate_refuses_huge_power_fast():
    start = time.time()
    result = calculate("9**9**9")
    seconds = time.time() - start
    assert "error" in result
    assert seconds < 1    


def test_calculate_refuses_other_huge_powers():
    for expression in ["8**8**8", "10**10**10", "2**100"]:
        assert "error" in calculate(expression)


def test_calculate_division_by_zero():
    assert calculate("5 / (3 - 3)") == {"error": "division by zero"}


def test_calculate_refuses_functions_and_text():
    for expression in ["abs(-1)", "'hi'", "True + 1", "x + 1", "1 % 2"]:
        assert "error" in calculate(expression)


def test_calculate_bad_input_does_not_crash():
    for expression in ["", "   ", "1 +* 2", "x" * 201, None, 123]:
        assert "error" in calculate(expression)


# lookup 

def test_lookup_finds_2025_population():
    result = lookup("Millbrook", "population_2025")
    assert result["value"] == 37203
    assert result["source"] == "NR-11"


def test_lookup_takes_2025_not_2020():
    # NR-05 has "39,902 in 2020 and 44,675 in 2025" in one sentence
    assert lookup("Brightwater", "population_2025")["value"] == 44675
    assert lookup("Brightwater", "population_2020")["value"] == 39902


def test_lookup_uses_correction():
    result = lookup("Brightwater", "area_km2")
    assert result["value"] == 921.4       # not 912.4 from NR-05
    assert result["corrected_by"] == "NR-16"


def test_lookup_skips_archived_profile():
    # Tarnvale has NR-03 (2025) and NR-13 (ARCHIVED 2019)
    result = lookup("Tarnvale", "population_2025")
    assert result["source"] == "NR-03"
    assert result["value"] == 71388       # not 65030 from NR-13
    assert lookup("Kelmarsh", "schools")["source"] == "NR-04"    # not NR-14


def test_lookup_misspelled_name():
    result = lookup("Ossbrige", "area_km2")
    assert "error" in result
    assert "Ossbridge" in result["error"]


def test_lookup_similar_names_are_different():
    ossbridge = lookup("Ossbridge", "area_km2")
    ossford = lookup("Ossford", "area_km2")
    assert ossbridge["value"] == 1284.6
    assert ossford["value"] == 846.2
    assert ossbridge["source"] != ossford["source"]


def test_lookup_part_of_name_is_not_guessed():
    result = lookup("Oss", "area_km2")
    assert "error" in result
    assert "Ossbridge" in result["error"] and "Ossford" in result["error"]


def test_lookup_converts_cubic_metres():
    result = lookup("Lindenmoor", "water_use_2025_megalitres")
    assert result["value"] == 2151.4      # 2151400 cubic metres / 1000
    assert result["unit"] == "megalitres"


def test_lookup_water_tariff():
    result = lookup("Region", "water_tariff_2025")
    assert result["value"] == 142.35
    assert result["source"] == "NR-15"


def test_lookup_bad_input_does_not_crash():
    assert "error" in lookup("Brightwater", "density")
    assert "error" in lookup("Atlantis", "area_km2")
    assert "error" in lookup("", "area_km2")
    assert "error" in lookup(None, "area_km2")
    assert "error" in lookup("Region", "area_km2")