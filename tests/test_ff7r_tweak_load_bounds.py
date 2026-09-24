"""FF7R Tweaks loads stay bounded: pooled groups, cached scans (F12).

Opening Tweaks fired all seventeen group loads at once, and each slow group
re-scanned the installed game from scratch. The concurrent full-game scans
peaked past 5GB and starved the host until the whole program froze. The loader
runs at most two groups at a time now, and installed-input scans are cached.
"""
import json
import re
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plugins.ff7r import scan_cache  # noqa: E402
from test_shared_ui_feedback import ROOT, page  # noqa: E402,F401  (pytest fixture)


@pytest.fixture(autouse=True)
def clean_scan_cache():
    scan_cache.clear()
    yield
    scan_cache.clear()


def test_concurrent_scans_compute_once():
    import time

    calls = []
    barrier = threading.Barrier(8)

    def compute():
        calls.append(1)
        time.sleep(0.2)
        return {"nested": [1, 2]}

    def race(results):
        barrier.wait(timeout=10)
        results.append(scan_cache.cached(("k",), compute))

    results = []
    threads = [threading.Thread(target=race, args=(results,)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert calls == [1]
    assert results == [{"nested": [1, 2]}] * 8
    # Callers get private copies: mutating one must not poison the cache.
    results[0]["nested"].append(3)
    assert scan_cache.cached(("k",), compute) == {"nested": [1, 2]}


def test_failed_scans_are_not_cached():
    attempts = []

    def compute():
        attempts.append(1)
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        scan_cache.cached(("k",), compute)
    with pytest.raises(RuntimeError):
        scan_cache.cached(("k",), compute)
    assert attempts == [1, 1]


def test_list_pak_caches_per_install_identity(tmp_path, monkeypatch):
    from plugins.ff7r import tooling

    pak = tmp_path / "End" / "Content" / "Paks" / "pakchunk0-Windows.pak"
    pak.parent.mkdir(parents=True)
    pak.write_bytes(b"fake")
    calls = []

    class FakeResult:
        stdout = "a.uasset\nb.uexp\n"

    monkeypatch.setattr(tooling, "_command",
                        lambda *args, **kwargs: (calls.append(1), FakeResult())[1])
    assert tooling.list_pak(pak) == ["a.uasset", "b.uexp"]
    assert tooling.list_pak(pak) == ["a.uasset", "b.uexp"]
    assert len(calls) == 1
    pak.write_bytes(b"changed")
    assert tooling.list_pak(pak) == ["a.uasset", "b.uexp"]
    assert len(calls) == 2


def test_probe_installed_exe_caches_per_needles(tmp_path, monkeypatch):
    from plugins.ff7r import native_probe

    exe = tmp_path / "End" / "Binaries" / "Win64" / "ff7remake_.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"fake-exe")
    calls = []
    monkeypatch.setattr(native_probe, "probe_bytes",
                        lambda data, needles: (calls.append(tuple(needles)),
                                               {"needles": list(needles)})[1])
    first = native_probe.probe_installed_exe(tmp_path, needles=("a",))
    assert native_probe.probe_installed_exe(tmp_path, needles=("a",)) == first
    assert len(calls) == 1
    native_probe.probe_installed_exe(tmp_path, needles=("b",))
    assert len(calls) == 2


def test_collect_report_caches_on_index_signature(monkeypatch):
    import plugins.ff7r.archive as archive
    import plugins.ff7r.text_storage as text_storage
    from plugins.ff7r import no_more_cheats_tweaks as module

    calls = {"text": 0, "data": 0, "scan": 0}

    class FakeTextPackage:
        entries = ()

    def fake_text(*args, **kwargs):
        calls["text"] += 1
        return FakeTextPackage(), "", "", False

    def fake_pair(*args, **kwargs):
        calls["data"] += 1
        return ("uasset", "uexp")

    def fake_scan(*args, **kwargs):
        calls["scan"] += 1
        return {"targets": [], "notes": []}

    monkeypatch.setattr(text_storage, "load_text_package", fake_text)
    monkeypatch.setattr(archive, "extract_pair", fake_pair)
    monkeypatch.setattr(module, "DataObjectPackage", lambda *a, **k: object())
    monkeypatch.setattr(module, "scan_installed_menu_candidates", fake_scan)
    index = {"signatureId": "sig-1",
             "textAssets": [{"asset": "T1", "language": "US"}],
             "assets": [{"asset": "D1"}]}
    first = module.collect_report("game", "data", "project", index, language="US")
    assert module.collect_report("game", "data", "project", index,
                                 language="US") == first
    assert calls == {"text": 1, "data": 1, "scan": 1}
    # Without an install identity there is nothing safe to key on.
    module.collect_report("game", "data", "project",
                          {"textAssets": [], "assets": []}, language="US")
    module.collect_report("game", "data", "project",
                          {"textAssets": [], "assets": []}, language="US")
    assert calls["scan"] == 3


def _tweaks_document(groups: int, delay_ms: int) -> str:
    assets = [{"asset": f"Lexeditor/Group{i:02}", "name": f"Group {i}",
               "group": f"Lexeditor T{i}"} for i in range(groups)]
    data = {asset["asset"]: {"asset": asset["asset"], "records": [
        {"id": 0, "tag": "R0", "values": {}}], "properties": []}
        for asset in assets}
    fixture = {"catalog": {"assets": assets, "textAssets": []},
               "data": data, "datamap": {"rows": []}, "info": {}}
    stub = r"""
window.__fixture = FIXTURE;
history.replaceState = () => {};
history.pushState = () => {};
window.__inflight = 0;
window.__maxInflight = 0;
const delay = ms => new Promise(done => setTimeout(done, ms));
window.fetch = async function(input, options={}) {
  const url = new URL(String(input), document.baseURI);
  const path = url.pathname;
  let data = null, status = 200;
  if(path === "/api/catalog") data = window.__fixture.catalog;
  else if(path === "/api/datamap") data = window.__fixture.datamap;
  else if(path === "/api/info") data = window.__fixture.info;
  else if(path === "/api/data") {
    window.__inflight++;
    window.__maxInflight = Math.max(window.__maxInflight, window.__inflight);
    try {
      await delay(DELAY);
      data = window.__fixture.data[url.searchParams.get("asset")];
      if(!data){data={error:"Synthetic DataObject not found"};status=404;}
    } finally { window.__inflight--; }
  }
  else {data={error:"Unexpected synthetic request: "+path};status=404;}
  return new Response(JSON.stringify(data), {
    status, headers:{"Content-Type":"application/json"}
  });
};
""".replace("FIXTURE", json.dumps(fixture)).replace("DELAY", str(delay_ms))
    html = (ROOT / "plugins/ff7r/editor.html").read_text(encoding="utf-8")
    html = html.replace("<head>", '<head><base href="https://lexeditor.test/">', 1)
    html = html.replace(
        '<link rel="stylesheet" href="/shared/framework.css">',
        "<style>" + (ROOT / "ui/framework.css").read_text(encoding="utf-8") + "</style>",
    )
    html = html.replace(
        '<script src="/shared/framework.js"></script>',
        "<script>" + stub + "</script><script>"
        + (ROOT / "ui/framework.js").read_text(encoding="utf-8") + "</script>",
    )
    html = html.replace(
        '<script src="/shared/unreal-config.js"></script>',
        "<script>"
        + (ROOT / "ui/unreal-config.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
        + "</script>",
    )
    folder = ROOT / "plugins" / "ff7r"
    html = re.sub(
        r'<script src="(?!/shared/)/?([A-Za-z0-9_./-]+\.js)"></script>',
        lambda match: "<script>"
        + (folder / Path(match[1]).name).read_text(encoding="utf-8").replace("</script", "<\\/script")
        + "</script>",
        html,
    )
    return html


def test_tweak_groups_load_bounded_and_settle(page):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content(_tweaks_document(groups=17, delay_ms=150))
    page.wait_for_function("state.catalog && state.data && !state.busy",
                           timeout=30000)
    page.evaluate("void navigate('tweaks')")
    # Seventeen groups at 150ms each with a pool of two settles in seconds;
    # firing them all at once used to exhaust the host instead.
    page.wait_for_function("!state.tweaksPending && state.tweaks",
                           timeout=30000)
    assert page.evaluate("Object.keys(state.tweaks).length") == 17
    assert page.evaluate("window.__maxInflight") <= 2
    assert page.evaluate("document.querySelector('#main').innerText").strip()
    assert errors == []
