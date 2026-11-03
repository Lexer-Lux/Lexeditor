"""Saving scalar/vector numbers must preserve their binary64 values on reopen."""
import ast
import pytest

from plugins.warband.module_records import SCHEMAS, dataset_data
from tests.warband.test_warband_dataset_creation import record_service
from tests.warband.test_warband_module_records import FIXTURES

NUMERIC_KINDS = {"number", "vec2", "vec3", "vec4"}
DATASETS = [name for name, schema in SCHEMAS.items() if any(spec["kind"] in NUMERIC_KINDS for spec in schema["fields"])]
VALUES = [0.12345678901234566, 0.30000000000000004, 0.5000000000000001, 1.0000000000000001e-16, 5e-324, -0.0]


@pytest.mark.parametrize("dataset", DATASETS)
def test_scalar_and_vector_http_roundtrip_preserves_float_bits(tmp_path, record_service, dataset):
    schema = SCHEMAS[dataset]
    source = tmp_path / schema["filename"]
    source.write_text(FIXTURES[source.name], encoding="utf-8")
    before = dataset_data(tmp_path, dataset)
    original_fields = before["rows"][0]["fields"]
    specs = [spec for spec in schema["fields"] if spec["kind"] in NUMERIC_KINDS
             and spec["key"] in before["rows"][0]["presentFields"]
             and spec["key"] not in before["rows"][0].get("fieldProblems", {})]
    assert specs
    for sample, number in enumerate(VALUES):
        fields = {spec["key"]: (number if spec["kind"] == "number" else
                  [VALUES[(sample + component) % len(VALUES)] for component in range(int(spec["kind"][-1]))])
                  for spec in specs}
        previous_bytes = source.read_bytes()
        status, result = record_service("/save", {"dataset": dataset, "sha256": before["sha256"],
            "edits": [{"recordIndex": 0, "originalId": before["rows"][0]["id"], "fields": fields}]})
        assert status == 200 and result["saved"] == 1, result
        status, reopened = record_service("?dataset=" + dataset)
        assert status == 200
        actual = reopened["rows"][0]["fields"]
        for key, value in fields.items():
            expected_values = value if isinstance(value, list) else [value]
            actual_values = actual[key] if isinstance(value, list) else [actual[key]]
            assert [float(value).hex() for value in actual_values] == [value.hex() for value in expected_values], (dataset, key, value, actual[key])
        for key, value in original_fields.items():
            if key not in fields:
                assert actual[key] == value
        assert source.with_name(source.name + ".lexeditor.bak").read_bytes() == previous_bytes
        module = ast.parse(source.read_text(encoding="utf-8"))
        records = next(node.value for node in module.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == schema["variable"] for target in node.targets))
        for spec in specs:
            if spec["kind"].startswith("vec"):
                node = records.elts[0].elts[schema["fields"].index(spec)]
                assert isinstance(node, ast.Tuple if spec.get("container") == "tuple" else ast.List)
        before = reopened
