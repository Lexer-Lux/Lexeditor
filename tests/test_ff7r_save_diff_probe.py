from games.ff7r.save_diff_probe import SavePair, analyze_save_pairs


def _pair(*, noise_offset: int, noise_value: int) -> SavePair:
    before = bytearray(64)
    after = bytearray(before)
    after[10] = 0x01
    after[20] = 0x80
    after[noise_offset] = noise_value
    return SavePair(bytes(before), bytes(after), f"noise-{noise_offset}")


def test_repeated_save_pairs_separate_stable_changes_from_pair_specific_noise():
    result = analyze_save_pairs([
        _pair(noise_offset=30, noise_value=5),
        _pair(noise_offset=31, noise_value=7),
        _pair(noise_offset=32, noise_value=9),
    ])

    assert result["pairCount"] == 3
    assert result["stableChangedOffsets"] == [10, 20]
    assert result["variableChangedOffsets"] == [30, 31, 32]
    assert result["stableChangedRuns"] == [
        {"start": 10, "end": 11, "length": 1},
        {"start": 20, "end": 21, "length": 1},
    ]
    assert result["sameBeforeAfterTransformCount"] == 2
    assert result["sameXorMaskCount"] == 2

    transforms = {row["offset"]: row for row in result["stableTransforms"]}
    assert transforms[10]["beforeValue"] == 0
    assert transforms[10]["afterValue"] == 1
    assert transforms[10]["xorMask"] == 1
    assert transforms[20]["afterValue"] == 0x80


def test_integer_candidates_report_stable_little_endian_transitions():
    before1 = bytearray(32)
    after1 = bytearray(before1)
    before2 = bytearray(32)
    after2 = bytearray(before2)

    before1[8:12] = (10).to_bytes(4, "little")
    after1[8:12] = (11).to_bytes(4, "little")
    before2[8:12] = (20).to_bytes(4, "little")
    after2[8:12] = (21).to_bytes(4, "little")

    result = analyze_save_pairs([
        SavePair(bytes(before1), bytes(after1), "one"),
        SavePair(bytes(before2), bytes(after2), "two"),
    ])

    # Only byte 8 changes for these values, so width-1 is the supported stable
    # candidate. The probe must not invent unchanged bytes as part of a 4-byte
    # field merely because a 32-bit interpretation would be convenient.
    candidate = next(row for row in result["integerCandidates"] if row["offset"] == 8 and row["width"] == 1)
    assert candidate["sameDelta"] is True
    assert candidate["delta"] == 1
    assert not any(row["offset"] == 8 and row["width"] == 4 for row in result["integerCandidates"])


def test_transform_consistency_distinguishes_same_xor_from_same_values():
    before1 = bytearray(16)
    after1 = bytearray(before1)
    before2 = bytearray(16)
    after2 = bytearray(before2)
    before1[5] = 0b0001
    after1[5] = 0b0011
    before2[5] = 0b0101
    after2[5] = 0b0111

    result = analyze_save_pairs([
        SavePair(bytes(before1), bytes(after1)),
        SavePair(bytes(before2), bytes(after2)),
    ])
    row = result["stableTransforms"][0]
    assert row["offset"] == 5
    assert row["sameXorMask"] is True
    assert row["xorMask"] == 0b0010
    assert row["sameBeforeValue"] is False
    assert row["sameAfterValue"] is False
    assert result["sameBeforeAfterTransformCount"] == 0
    assert result["sameXorMaskCount"] == 1


def test_empty_pair_list_is_rejected():
    try:
        analyze_save_pairs([])
    except ValueError as error:
        assert "at least one" in str(error)
    else:
        raise AssertionError("expected ValueError")
