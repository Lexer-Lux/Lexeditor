"""Run every pinned linked-runtime assertion and mutation with export-only PE parsing.

The upstream verifier reads only PE headers, exports, and raw section offsets.
Avoid decoding unrelated imports/resources twelve times for large static DLLs.
The shipping-package verifier separately validates the Windows XML manifest.
No verification assertion, required export, or negative control is removed.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def verify(verifier: Path, driver: Path) -> int:
    spec = importlib.util.spec_from_file_location('ff8_pinned_linked_verifier', verifier)
    if spec is None or spec.loader is None:
        raise ValueError(f'Cannot load linked artifact verifier: {verifier}')
    linked = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(linked)
    pe = linked.pefile
    original_pe = pe.PE

    def exports_only(*args, **kwargs):
        kwargs['fast_load'] = True
        image = original_pe(*args, **kwargs)
        image.parse_data_directories(directories=[
            pe.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
        return image

    # Replace only this verifier's module binding. Pefile's own PE class
    # must remain intact because its constructor refers to class constants.
    facade = SimpleNamespace(PE=exports_only, PEFormatError=pe.PEFormatError)
    with patch.object(linked, 'pefile', facade):
        runtime = linked.verify(driver)
        rejected = linked.mutation_test(driver, runtime)
    if rejected != 11:
        raise AssertionError(f'Expected all eleven pinned mutation controls, got {rejected}')
    print(f'PASS linked runtime: all original assertions; {rejected} binary mutations rejected.')
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--driver', type=Path, required=True)
    args = parser.parse_args()
    verify(args.verifier.resolve(), args.driver.resolve())
