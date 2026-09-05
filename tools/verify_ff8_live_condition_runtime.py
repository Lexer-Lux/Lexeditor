"""Verify the guarded FFNx evaluator for precomposed FF8 live variants."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
FFNX = ROOT / "_scratch" / "issue51-ffnx-build-c056db2"


def failures(evaluator: str, direct: str, audio: str, cmake: str) -> list[str]:
    errors: list[str] = []

    def need(value: bool, message: str) -> None:
        if not value:
            errors.append(message)

    # Memory input is checked before it is copied. A failed read makes the
    # condition invalid instead of dereferencing the supplied address.
    query = evaluator.find("VirtualQuery(")
    read = evaluator.find("ReadProcessMemory(")
    need(0 <= query < read, "guarded reads do not validate memory before copying")
    need("region.State != MEM_COMMIT" in evaluator and
         "!readable_protection(region.Protect)" in evaluator,
         "guarded reads do not reject unreadable memory")

    for input_type in ("byte", "short", "int", "ffstring", "sys", "counter",
                       "counteradv", "counterrnd", "random", "randomvaronce",
                       "randomvar"):
        need(f'kind == "{input_type}"' in evaluator,
             f"the {input_type} runtime input is not evaluated")

    # Only a contained, content-addressed final output can become a selected
    # target. Raw package candidates never appear in this evaluator.
    need("path_below(candidate, allowed)" in evaluator and
         "weakly_canonical(direct_root / relative)" in evaluator,
         "final assets are not contained under the runtime variant root")
    need("sha256(candidate) != digest" in evaluator and
         "digest.substr(0, 24)" in evaluator,
         "final assets are not verified by content and filename identity")
    need('kAssetPrefix[] = "lexeditor/conditional-variants/"' in evaluator and
         '"candidates"' not in evaluator,
         "the evaluator can consume something other than final variants")

    # Invalid evaluation starts from the composed fallback. Pass-through lets
    # the original FFNx lookup continue.
    fallback = evaluator.find("const Target *target = &route.fallback")
    variant = evaluator.find("target = &variant->second", fallback)
    passthrough = evaluator.find("if (target->pass_through) return false", variant)
    need(0 <= fallback < variant < passthrough,
         "invalid conditions do not fail closed through the composed fallback")
    need("catch (...)" in evaluator and "A malformed route is inert" in evaluator,
         "a malformed route is not isolated")

    # These caps bound every manifest dimension and the exponential outcome
    # table. The producer has the same 12-condition and 4096-output caps.
    for declaration in (
        "kMaxManifestBytes = 16U * 1024U * 1024U",
        "kMaxJsonDepth = 32",
        "kMaxJsonNodes = 300000",
        "kMaxRoutes = 4096",
        "kMaxConditionsPerRoute = 12",
        "kMaxTokensPerCondition = 256",
        "kMaxVariantsPerRoute = 4096",
        "kMaxVariantsTotal = 65536",
        "kMaxStringRead = 4096",
    ):
        need(declaration in evaluator, f"runtime bound changed or disappeared: {declaration}")
    need("variant_values.array.size() != expected" in evaluator and
         "route.variants.size() != expected" in evaluator,
         "the evaluator accepts an incomplete outcome table")

    # The evaluator runs before the existing lookup at the proven Direct and
    # external SFX/voice/ambient seams. Music and movies remain untouched.
    need(direct.count("live_conditions::resolve(") == 2,
         "both FF8 Direct path forms are not condition-aware")
    direct_resolve = direct.find("live_conditions::resolve(")
    direct_exists = direct.find("fileExists(output)", direct_resolve)
    need(0 <= direct_resolve < direct_exists,
         "Direct variants are not selected before normal FFNx lookup")
    for root in ('lexeditor_root = "sfx"', 'lexeditor_root = "voice"',
                 'lexeditor_root = "ambient"'):
        need(root in audio, f"external audio root is missing: {root}")
    audio_resolve = audio.find("live_conditions::resolve(")
    audio_exists = audio.find("fileExists(_out)", audio_resolve)
    need(0 <= audio_resolve < audio_exists,
         "external variants are not selected before normal FFNx lookup")
    need('lexeditor_root = "music"' not in audio and
         'lexeditor_root = "movie"' not in audio,
         "unsupported external audio roots entered live routing")

    need("option(FFNX_LEXEDITOR_LIVE_CONDITIONS" in cmake and
         "FFNX_LEXEDITOR_LIVE_CONDITIONS=$<BOOL:${FFNX_LEXEDITOR_LIVE_CONDITIONS}>" in cmake,
         "the derivative has no explicit live-condition compile gate")
    need("#define FFNX_LEXEDITOR_LIVE_CONDITIONS 0" in direct and
         "#define FFNX_LEXEDITOR_LIVE_CONDITIONS 0" in audio,
         "an upstream/default build could enable Lexeditor routing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiled", action="store_true",
                        help="also run the CMake-built behavior harness")
    arguments = parser.parse_args()

    evaluator = (FFNX / "src" / "ff8" / "lexeditor_live_conditions.cpp").read_text(encoding="utf-8")
    direct = (FFNX / "src" / "ff8" / "file.cpp").read_text(encoding="utf-8")
    audio = (FFNX / "src" / "audio.cpp").read_text(encoding="utf-8")
    cmake = (FFNX / "CMakeLists.txt").read_text(encoding="utf-8")
    current = failures(evaluator, direct, audio, cmake)
    if current:
        raise AssertionError("; ".join(current))

    # Prove that the static contract detects the prior dangerous forms. This
    # prevents a passing verifier from silently requiring the defect.
    mutations = (
        (evaluator.replace("VirtualQuery(", "UncheckedQuery(", 1), direct, audio, cmake),
        (evaluator.replace("sha256(candidate) != digest", "false", 1), direct, audio, cmake),
        (evaluator.replace("const Target *target = &route.fallback", "const Target *target = nullptr", 1), direct, audio, cmake),
        (evaluator.replace("kMaxConditionsPerRoute = 12", "kMaxConditionsPerRoute = 64", 1), direct, audio, cmake),
        (evaluator, direct.replace("live_conditions::resolve(", "disabled_resolve("), audio, cmake),
        (evaluator, direct, audio.replace('lexeditor_root = "voice"', 'lexeditor_root = "music"', 1), cmake),
    )
    for index, mutation in enumerate(mutations, 1):
        if not failures(*mutation):
            raise AssertionError(f"runtime verifier accepted dangerous mutation {index}")

    if arguments.compiled:
        executable = FFNX / ".build" / "lexeditor_live_conditions_test.exe"
        if not executable.is_file():
            raise AssertionError("the CMake-built live-condition behavior harness is missing")
        completed = subprocess.run([executable], cwd=FFNX, check=False)
        if completed.returncode:
            raise AssertionError(
                f"compiled live-condition behavior harness failed with {completed.returncode}")

    print("FF8 guarded live-condition runtime and mutation contracts passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
