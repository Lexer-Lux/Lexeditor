"""The distribution string blocks external transports and preserves local editing."""
import importlib.util
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import urllib.request

import pytest
import disable_networking
from core import network_policy
from tools.configure_nexus_networking import configure

ROOT = Path(__file__).resolve().parents[2]


def test_staged_distribution_literal_and_any_edit(tmp_path):
    shutil.copy2(ROOT/'disable_networking.py',tmp_path)
    configure(tmp_path, True)
    spec = importlib.util.spec_from_file_location('staged_networking',tmp_path/'disable_networking.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.disabled()
    name = 'DO_NOT_EDIT_ANY_PART_OF_THIS_STRING_AND_THEN_PRESS_SAVE_OR_NETWORK_FEATURES_WILL_BE_RE_ENABLED'
    setattr(module, name, getattr(module,name)+' ')
    assert not module.disabled()
    configure(tmp_path,False)
    spec.loader.exec_module(module)
    assert not module.disabled()


def test_disabled_network_blocks_dns_connections_and_remote_commands(monkeypatch):
    monkeypatch.setattr(network_policy, 'disabled', lambda:True)
    network_policy.install()
    with pytest.raises(OSError,match='External networking'):
        socket.getaddrinfo('example.com',443)
    with pytest.raises(OSError,match='External networking'):
        urllib.request.urlopen('https://example.com', timeout=0.1)
    with socket.socket() as connection:
        with pytest.raises(OSError,match='External networking'):
            connection.connect(('192.0.2.1',443))
    for command in [['git','fetch','origin'],['curl','https://example.com'],
                    ['git','clone','https://example.com/repo']]:
        with pytest.raises(OSError,match='External networking'):
            subprocess.run(command,check=True)
    with socket.socket() as server, socket.socket() as client:
        server.bind(('127.0.0.1',0));server.listen()
        client.connect(server.getsockname())
        peer,_ = server.accept()
        peer.close()
    assert socket.getaddrinfo('localhost',80)


def test_github_default_and_local_notice_actions():
    assert not disable_networking.disabled()
    assert not network_policy.notice()['disabled']
    network_policy.require_network()


def test_windows_editor_uses_text_association_and_safe_argument_list(tmp_path,monkeypatch):
    import ctypes
    from core import runtime_bootstrap
    if runtime_bootstrap.os.name != 'nt':
        pytest.skip('Windows text-editor association')
    target=tmp_path/'source with spaces.py'
    target.write_text('print("do not execute")')
    queries=[];launches=[]
    class Query:
        def __call__(self,flags,kind,extension,verb,buffer,size):
            queries.append((extension,verb))
            buffer.value=r'C:\Text Editor\editor.exe'
            return 0
    class Library:
        AssocQueryStringW=Query()
    monkeypatch.setattr(ctypes,'WinDLL',lambda *_:Library())
    monkeypatch.setattr(runtime_bootstrap.subprocess,'Popen',lambda args:launches.append(args))
    runtime_bootstrap.open_text_file(target)
    assert queries==[('.txt','open')]
    assert launches==[[r'C:\Text Editor\editor.exe',str(target.resolve())]]


def test_child_service_core_import_installs_distribution_policy(tmp_path):
    shutil.copy2(ROOT/'disable_networking.py',tmp_path)
    configure(tmp_path,True)
    probe=tmp_path/'child.py'
    probe.write_text(f'import sys\nsys.path.append({str(ROOT)!r})\n'
        'import core\nimport socket\n'
        'try:\n socket.getaddrinfo("example.com",443)\n'
        'except OSError as error:\n assert "External networking" in str(error)\n'
        'else:\n raise AssertionError("child networking was enabled")\n')
    subprocess.run([sys.executable,str(probe)],cwd=tmp_path,check=True,capture_output=True)


def test_startup_notice_renders_and_actions_only_request_a_draft(tmp_path):
    import functools
    import json
    import threading
    from http.server import ThreadingHTTPServer
    from playwright.sync_api import sync_playwright
    from test_chooser_renders import Handler, BASE
    server = ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    payload = dict(network_policy.notice(),disabled=True,show=True)
    settings = dict(BASE,defaultValues=dict(BASE),viewPreferences={},loadingTransitionMinimumSeconds=0)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={'width':1440,'height':900})
                page.add_init_script(f'''window.actions=[];window.pywebview={{api:new Proxy({{
                  lexeditor_settings:async()=>({json.dumps(settings)}),plugins:async()=>[],
                  loading_quote:async()=>({{quote:''}}),window_state:async()=>({{maximized:false}}),
                  networking_notice:async()=>({json.dumps(payload)}),
                  open_networking_notice_action:async action=>{{actions.push(action);return {{opened:true}};}}
                }},{{get:(t,k)=>t[k]||(async()=>false)}})}};''')
                page.goto(f'http://127.0.0.1:{server.server_port}/ui/chooser.html')
                page.evaluate("dispatchEvent(new Event('pywebviewready'))")
                page.get_by_text('Internet features disabled',exact=True).wait_for()
                page.get_by_role('button',name='OPEN IN TEXT EDITOR',exact=True).click()
                page.get_by_role('button',name='DRAFT EMAIL TO NEXUS SUPPORT',exact=True).click()
                assert page.evaluate('actions')==['edit','support']
                page.screenshot(path=str(tmp_path/'network-notice.png'))
                page.get_by_role('button',name='CONTINUE',exact=True).click()
                assert not page.get_by_text('Internet features disabled',exact=True).is_visible()
            finally:
                browser.close()
    finally:
        server.shutdown();server.server_close()
