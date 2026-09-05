"""Contract for Lexeditor-owned low-to-high FF8 Hext application."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
HEXT_SOURCE = ROOT / "_scratch" / "issue51-ffnx-build-c056db2" / "src" / "hext.cpp"


def verify_source(source: str) -> None:
    match = re.search(
        r"void Hext::applyAll\(std::string checkpoint\)\s*\{(?P<body>.*)\n\}",
        source,
        re.DOTALL,
    )
    assert match, "Hext::applyAll is missing"
    body = match.group("body")
    assert "std::vector<std::filesystem::directory_entry> entries;" in body
    assert "std::sort(entries.begin(), entries.end()" in body
    assert "left.path().filename().generic_string() < right.path().filename().generic_string()" in body
    assert body.count("for (const auto& entry : entries)") == 2
    # One directory walk may collect the files. Applying patches directly from
    # a directory_iterator would restore nondeterministic Windows ordering.
    assert body.count("std::filesystem::directory_iterator(hext_patching_path)") == 1
    assert body.index("std::sort(entries.begin(), entries.end()") < body.index(
        "for (const auto& entry : entries)")


def main() -> int:
    source = HEXT_SOURCE.read_text(encoding="utf-8")
    verify_source(source)

    without_sort = re.sub(
        r"\s*std::sort\(entries\.begin\(\), entries\.end\(\), \[\]\(const auto& left, const auto& right\) \{.*?\n\s*\}\);",
        "",
        source,
        count=1,
        flags=re.DOTALL,
    )
    try:
        verify_source(without_sort)
    except AssertionError:
        pass
    else:
        raise AssertionError("contract accepted Hext application without sorting")

    direct_apply = source.replace(
        "for (const auto& entry : entries)",
        "for (const auto& entry : std::filesystem::directory_iterator(hext_patching_path))",
        1,
    )
    try:
        verify_source(direct_apply)
    except AssertionError:
        pass
    else:
        raise AssertionError("contract accepted direct directory-order patch application")

    print("FF8 Hext deterministic low-to-high source contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
