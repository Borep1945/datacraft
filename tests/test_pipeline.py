import json

import pytest

from datacraft import PipelineError, run


def test_decimal_grouping_and_filters(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("team,cost\na,0.1\na,0.2\nb,2\nb,-1\n")
    out = tmp_path / "out.json"
    result = run(
        source,
        out,
        {
            "schema": {"cost": {"type": "decimal", "required": True}},
            "filters": [{"field": "cost", "op": "ge", "value": 0}],
            "aggregate": {"group_by": ["team"], "sum": ["cost"]},
        },
    )
    assert json.loads(out.read_text()) == [
        {"team": "a", "count": 2, "cost": "0.3"},
        {"team": "b", "count": 1, "cost": "2"},
    ]
    assert result == {"read": 4, "accepted": 3, "rejected": 0, "filtered": 1, "written": 2}


def test_failure_preserves_output_and_cleans_temporary(tmp_path):
    src, dst = tmp_path / "i.csv", tmp_path / "o.jsonl"
    src.write_text("n\n1\nnot-a-number\n")
    dst.write_text("original")
    with pytest.raises(PipelineError, match="Row 2"):
        run(src, dst, {"schema": {"n": {"type": "int"}}})
    assert dst.read_text() == "original"
    assert not list(tmp_path.glob(".datacraft-*"))


def test_skip_invalid_values_and_required(tmp_path):
    src, dst = tmp_path / "i.csv", tmp_path / "o.jsonl"
    src.write_text("n\n2\n2.5\nNaN\n,\n")
    # Extra CSV fields represent malformed source structure and always fail.
    src.write_text("n,x\n2,a\n2.5,b\nNaN,c\n,d\n")
    stats = run(src, dst, {"on_error": "skip", "schema": {"n": {"type": "int", "required": True}}})
    assert stats["rejected"] == 3
    assert json.loads(dst.read_text())["n"] == 2


@pytest.mark.parametrize(
    "config",
    [
        [],
        {"on_error": "ignore"},
        {"schema": {"n": {"type": "bad"}}},
        {"filters": [{"field": "n", "op": "execute", "value": 0}]},
        {"aggregate": {"group_by": ["n"], "sum": ["n"]}},
        {"aggregate": {"group_by": "n", "sum": []}},
    ],
)
def test_bad_config(config, tmp_path):
    with pytest.raises(PipelineError):
        run(tmp_path / "i.csv", tmp_path / "o.csv", config)


def test_jsonl_malformed_is_not_silently_skipped(tmp_path):
    src, dst = tmp_path / "i.jsonl", tmp_path / "o.json"
    src.write_text('{"n": 1}\nnot-json\n')
    with pytest.raises(PipelineError, match="line 2"):
        run(src, dst, {"on_error": "skip"})
    assert not dst.exists()


def test_csv_formula_escaping(tmp_path):
    src, dst = tmp_path / "i.jsonl", tmp_path / "o.csv"
    src.write_text('{"name":"=1+1"}\n')
    run(src, dst)
    assert "'=1+1" in dst.read_text()


def test_different_row_keys_cannot_drop_data(tmp_path):
    src, dst = tmp_path / "i.json", tmp_path / "o.csv"
    src.write_text('[{"a": 1}, {"b": 2}]')
    with pytest.raises(PipelineError, match="consistent schema"):
        run(src, dst)
    assert not dst.exists()


def test_xlsx_read_only_adapter(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active.append(["team", "n"])
    workbook.active.append(["a", 3])
    src, dst = tmp_path / "input.xlsx", tmp_path / "out.json"
    workbook.save(src)
    workbook.close()
    run(src, dst)
    assert json.loads(dst.read_text()) == [{"team": "a", "n": 3}]


def test_duplicate_csv_headers(tmp_path):
    src = tmp_path / "i.csv"
    src.write_text("n,n\n1,2\n")
    with pytest.raises(PipelineError, match="unique"):
        run(src, tmp_path / "o.json")


def test_same_source_rejected(tmp_path):
    src = tmp_path / "i.csv"
    src.write_text("n\n1\n")
    with pytest.raises(PipelineError, match="differ"):
        run(src, src)


def test_aggregation_missing_field_atomic(tmp_path):
    src, dst = tmp_path / "i.csv", tmp_path / "o.json"
    src.write_text("a\n1\n")
    with pytest.raises(PipelineError, match="present"):
        run(src, dst, {"aggregate": {"group_by": ["missing"], "sum": []}})
    assert not dst.exists()


def test_exact_sum_above_default_decimal_precision(tmp_path):
    src, dst = tmp_path / "i.csv", tmp_path / "o.json"
    src.write_text("team,n\na,123456789012345678901234567890.1\na,0.2\n")
    run(src, dst, {"aggregate": {"group_by": ["team"], "sum": ["n"]}})
    assert json.loads(dst.read_text())[0]["n"] == "123456789012345678901234567890.3"


@pytest.mark.parametrize("suffix", [".json", ".jsonl"])
def test_json_fractional_sum_keeps_source_digits(tmp_path, suffix):
    src, dst = tmp_path / ("i" + suffix), tmp_path / "o.json"
    rows = ['{"n": 12345678901234567890.123456789}', '{"n": 0.000000001}']
    src.write_text("[" + ",".join(rows) + "]" if suffix == ".json" else "\n".join(rows))
    run(src, dst, {"aggregate": {"group_by": [], "sum": ["n"]}})
    assert json.loads(dst.read_text())[0]["n"] == "12345678901234567890.123456790"


@pytest.mark.parametrize(
    "config",
    [
        {"on_error": []},
        {"schema": {"n": {"type": []}}},
        {"filters": [{"field": [], "op": "eq", "value": 1}]},
        {"filters": [{"field": "n", "op": [], "value": 1}]},
        {"filters": [{"field": "n", "op": "gt", "value": "not numeric"}]},
        {"schema": {"n": {"type": "str", "min": 1}}},
        {"schema": {"n": {"type": "int", "min": 3, "max": 1}}},
    ],
)
def test_invalid_config_types_and_ranges_fail_before_io(tmp_path, config):
    dst = tmp_path / "o.json"
    dst.write_text("original")
    with pytest.raises(PipelineError):
        run(tmp_path / "missing.json", dst, config)
    assert dst.read_text() == "original"
    assert not list(tmp_path.glob(".datacraft-*"))


def test_decimal_group_keys_distinguish_text_and_merge_equivalent_numbers(tmp_path):
    src, dst = tmp_path / "i.json", tmp_path / "o.json"
    src.write_text('[{"g": 0.10}, {"g": "0.1"}, {"g": 0.100}]')
    run(src, dst, {"aggregate": {"group_by": ["g"], "sum": []}})
    assert sorted(row["count"] for row in json.loads(dst.read_text())) == [1, 2]


def test_cli_invalid_config_has_structured_error_without_traceback(tmp_path):
    import os
    import subprocess
    import sys

    config = tmp_path / "bad.json"
    config.write_text('{"on_error": []}')
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "datacraft.cli",
            str(tmp_path / "i.csv"),
            str(tmp_path / "o.json"),
            "--config",
            str(config),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr)["event"] == "pipeline_failed"
    assert "Traceback" not in result.stderr
