"""CLI end-to-end tests (simulate / analyze / compare / report)."""

import json
import os

import pytest

from traffic_flow.cli import main


def _write_scenario(tmp_path, duration=60.0, name="cli_test"):
    cfg = {
        "name": name,
        "description": "CLI test scenario",
        "road": {"length_m": 2000, "n_lanes": 2, "speed_limit": 33.3},
        "demand": {"intervals": [
            {"t_start": 0, "t_end": duration, "rate_veh_per_h": 900}
        ]},
        "duration": duration,
        "dt": 0.1,
        "seed": 5,
        "detectors": [1000.0],
    }
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(cfg))
    return str(path)


def test_cli_simulate_writes_all_artifacts(tmp_path):
    scenario = _write_scenario(tmp_path)
    out = str(tmp_path / "out")
    assert main(["simulate", "--scenario", scenario, "--out", out]) == 0
    for name in ("trajectory.csv", "events.json", "metrics.json",
                 "scenario.json", "space_time.png", "fundamental.png",
                 "speed_time.png", "queues.png", "report.md",
                 "dashboard.html"):
        assert os.path.exists(os.path.join(out, name)), name
    with open(os.path.join(out, "metrics.json")) as fh:
        metrics = json.load(fh)
    assert metrics["vehicles_entered"] > 0
    assert metrics["level_of_service"] in "ABCDEF"


def test_cli_analyze_recomputes_metrics(tmp_path):
    scenario = _write_scenario(tmp_path)
    out = str(tmp_path / "out")
    main(["simulate", "--scenario", scenario, "--out", out])
    assert main(["analyze", "--input", out]) == 0
    with open(os.path.join(out, "metrics.json")) as fh:
        metrics = json.load(fh)
    assert metrics["vehicles_completed"] >= 0


def test_cli_compare_writes_table(tmp_path):
    s1 = _write_scenario(tmp_path, duration=60.0, name="run_a")
    out_a = str(tmp_path / "a")
    out_b = str(tmp_path / "b")
    main(["simulate", "--scenario", s1, "--out", out_a])
    s2 = _write_scenario(tmp_path, duration=60.0, name="run_b")
    main(["simulate", "--scenario", s2, "--out", out_b])
    cmp_dir = str(tmp_path / "cmp")
    assert main(["compare", "--a", out_a, "--b", out_b,
                 "--out", cmp_dir]) == 0
    assert os.path.exists(os.path.join(cmp_dir, "comparison.md"))
    assert os.path.exists(os.path.join(cmp_dir, "comparison.json"))
    text = open(os.path.join(cmp_dir, "comparison.md")).read()
    assert "run_a" in text and "run_b" in text


def test_cli_report_regenerates(tmp_path):
    scenario = _write_scenario(tmp_path)
    out = str(tmp_path / "out")
    main(["simulate", "--scenario", scenario, "--out", out])
    os.remove(os.path.join(out, "report.md"))
    os.remove(os.path.join(out, "dashboard.html"))
    assert main(["report", "--input", out]) == 0
    assert os.path.exists(os.path.join(out, "report.md"))
    assert os.path.exists(os.path.join(out, "dashboard.html"))


def test_cli_unknown_subcommand_fails():
    with pytest.raises(SystemExit):
        main(["frobnicate"])
