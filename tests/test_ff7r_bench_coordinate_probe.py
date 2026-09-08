import struct

from games.ff7r.bench_coordinate_probe import (
    analyze_actor_root_coordinate_space,
    compare_actor_root_coordinate_spaces,
    correlate_layout_with_coordinate_evidence,
    decode_object_property_ref,
)
from games.ff7r.package_probe import NameRef, PackageExport, PackageObjectTable


def _export(index: int, name: str, *, outer: int = 0) -> PackageExport:
    return PackageExport(
        index=index,
        class_index=0,
        super_index=0,
        template_index=0,
        outer_index=outer,
        object_name=NameRef(name),
        object_flags=0,
        serial_size=0,
        serial_offset=0,
    )


def _table() -> PackageObjectTable:
    # Positive FPackageIndex values are one-based export indices.
    return PackageObjectTable(
        names=(
            "BenchActor", "BenchRoot", "VendingActor", "VendingRoot",
            "SharedParent", "OtherParent",
        ),
        imports=(),
        exports=(
            _export(0, "BenchActor"),
            _export(1, "BenchRoot", outer=1),
            _export(2, "VendingActor"),
            _export(3, "VendingRoot", outer=3),
            _export(4, "SharedParent"),
            _export(5, "OtherParent"),
        ),
        import_stride=0,
        export_stride=104,
        total_header_size=100,
        file_version=522,
        licensee_version=0,
    )


def _object_ref(export_index: int, name: str, package_index: int, *, size: int = 4):
    raw = struct.pack("<i", package_index)
    return {
        "exportIndex": export_index,
        "name": name,
        "propertyType": "ObjectProperty",
        "propertyTagLayoutPlausible": True,
        "declaredValueSize": size,
        "valueHex": raw.hex(),
    }


def _vector_ref(export_index: int, xyz):
    return {
        "exportIndex": export_index,
        "name": "RelativeLocation",
        "propertyType": "StructProperty",
        "propertyTagLayoutPlausible": True,
        "declaredValueSize": 12,
        "typeMetadata": {"structName": "Vector"},
        "vectorValuePlausible": True,
        "vectorValue": {"x": xyz[0], "y": xyz[1], "z": xyz[2]},
    }


def _base_refs(*, bench_parent=5, vending_parent=5, include_parents=True):
    refs = [
        _object_ref(0, "RootComponent", 2),  # BenchRoot export index 1.
        _object_ref(2, "RootComponent", 4),  # VendingRoot export index 3.
        _vector_ref(1, (0.0, 0.0, 0.0)),
        _vector_ref(3, (3.0, 4.0, 0.0)),
    ]
    if include_parents:
        refs.extend([
            _object_ref(1, "AttachParent", bench_parent),
            _object_ref(3, "AttachParent", vending_parent),
        ])
    return refs


def test_exact_four_byte_object_property_decodes_export_and_null_package_indices():
    table = _table()
    root = decode_object_property_ref(_object_ref(0, "RootComponent", 2), table)
    assert root == {
        "valid": True,
        "packageIndex": 2,
        "targetKind": "export",
        "targetPath": "BenchActor.BenchRoot",
        "targetExportIndex": 1,
        "targetImportIndex": None,
        "reason": "resolved-export-package-index",
    }

    null = decode_object_property_ref(_object_ref(1, "AttachParent", 0), table)
    assert null["valid"] is True
    assert null["packageIndex"] == 0
    assert null["targetKind"] == "null"
    assert null["targetPath"] is None


def test_object_property_requires_layout_proof_exact_type_and_four_byte_value():
    table = _table()
    wrong_size = decode_object_property_ref(
        _object_ref(0, "RootComponent", 2, size=8), table
    )
    assert wrong_size["valid"] is False
    assert wrong_size["reason"] == "object-property-size-is-not-four"

    wrong_type = _object_ref(0, "RootComponent", 2)
    wrong_type["propertyType"] = "IntProperty"
    assert decode_object_property_ref(wrong_type, table)["valid"] is False

    no_layout = _object_ref(0, "RootComponent", 2)
    no_layout["propertyTagLayoutPlausible"] = False
    assert decode_object_property_ref(no_layout, table)["valid"] is False


def test_actor_chain_requires_root_component_location_and_explicit_attach_parent():
    result = analyze_actor_root_coordinate_space(_table(), _base_refs(), 0)

    assert result["resolved"] is True
    assert result["actorObjectName"] == "BenchActor"
    assert result["rootComponentExportIndex"] == 1
    assert result["rootComponentObjectPath"] == "BenchActor.BenchRoot"
    assert result["relativeLocation"]["status"] == "unique-decoded-vector"
    assert result["relativeLocation"]["vector"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert result["attachParent"]["status"] == "unique-decoded-property"
    assert result["explicitAttachParentResolved"] is True
    assert result["attachParent"]["unique"]["targetPath"] == "SharedParent"


def test_same_explicit_parent_validates_common_relative_frame_and_distance_only():
    result = compare_actor_root_coordinate_spaces(_table(), _base_refs(), 0, 2)

    assert result["status"] == "shared-explicit-relative-coordinate-parent"
    assert result["sharedExplicitAttachParent"] is True
    assert result["sharedAttachParentPackageIndex"] == 5
    assert result["sharedAttachParentPath"] == "SharedParent"
    assert result["relativeCoordinateDistanceValidated"] is True
    assert result["relativeCoordinateDistance"] == 5.0
    assert result["worldSpaceDistanceValidated"] is False
    assert result["worldSpaceAdjacencyValidated"] is False
    assert result["suppressionAuthorized"] is False
    assert result["implementationReady"] is False


def test_explicit_null_parent_on_both_roots_is_comparable_but_still_not_world_proof():
    result = compare_actor_root_coordinate_spaces(
        _table(), _base_refs(bench_parent=0, vending_parent=0), 0, 2
    )

    assert result["sharedExplicitAttachParent"] is True
    assert result["sharedAttachParentPackageIndex"] == 0
    assert result["sharedAttachParentPath"] is None
    assert result["relativeCoordinateDistance"] == 5.0
    assert result["worldSpaceAdjacencyValidated"] is False


def test_missing_attach_parent_is_unknown_not_implicit_null():
    result = compare_actor_root_coordinate_spaces(
        _table(), _base_refs(include_parents=False), 0, 2
    )

    assert result["status"] == "attach-parent-not-explicitly-serialized"
    assert result["bothAttachParentsExplicitlyDecoded"] is False
    assert result["sharedExplicitAttachParent"] is False
    assert result["relativeCoordinateDistanceValidated"] is False
    assert result["relativeCoordinateDistance"] is None


def test_different_explicit_parents_block_relative_distance_comparison():
    result = compare_actor_root_coordinate_spaces(
        _table(), _base_refs(bench_parent=5, vending_parent=6), 0, 2
    )

    assert result["status"] == "different-explicit-attach-parents"
    assert result["bothAttachParentsExplicitlyDecoded"] is True
    assert result["sharedExplicitAttachParent"] is False
    assert result["relativeCoordinateDistance"] is None


def test_duplicate_root_component_property_fails_closed():
    refs = _base_refs()
    refs.append(_object_ref(0, "RootComponent", 2))
    result = analyze_actor_root_coordinate_space(_table(), refs, 0)

    assert result["resolved"] is False
    assert result["rootComponent"]["status"] == "ambiguous-property-tag"
    assert result["reason"] == "unique-export-root-component-unresolved"


def test_objectlayout_join_requires_exact_path_and_export_pair():
    coordinate = compare_actor_root_coordinate_spaces(_table(), _base_refs(), 0, 2)
    coordinate_pairs = [{
        "path": "End/Content/Game/slum7/LevelA.umap",
        "benchExportIndex": 0,
        "vendingExportIndex": 2,
        "coordinateSpace": coordinate,
    }]
    layout_rows = [{
        "path": "End/Content/Game/slum7/LevelA.umap",
        "benchExportIndex": 0,
        "vendingExportIndex": 2,
        "exactActorIdentityCorrelation": True,
        "worldSpaceAdjacencyValidated": False,
        "suppressionAuthorized": False,
    }]

    joined = correlate_layout_with_coordinate_evidence(layout_rows, coordinate_pairs)
    assert joined[0]["coordinateEvidenceMatchCount"] == 1
    assert joined[0]["relativeCoordinateDistanceValidated"] is True
    assert joined[0]["relativeCoordinateDistance"] == 5.0
    assert joined[0]["worldSpaceAdjacencyValidated"] is False
    assert joined[0]["suppressionAuthorized"] is False
