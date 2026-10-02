"""Ammunition payload, deployment and settings checks without retail assets."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plugins.ds1 import ammunition_controls as patch
from plugins.ds1 import ammunition_tweak as tweak


class PayloadChecks(unittest.TestCase):
    def test_pinned_payload_and_exported_functions(self):
        spec, raw = patch._payload()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), spec["payloadSha256"])
        self.assertEqual(set(spec["entrypoints"]), {h[3] for h in patch.HOOKS} | {"ammo_route"})
        self.assertLess(len(raw), 8192)
        self.assertEqual(len(spec["functions"]), 8)

    def test_unwind_records_are_bounded(self):
        spec, raw = patch._payload()
        for start, end, unwind in spec["functions"]:
            with self.subTest(start=start):
                off = unwind - patch.PAYLOAD_RVA
                version, prolog, count, frame = raw[off:off+4]
                self.assertEqual(version, 1)  # no handler/chain flags
                self.assertLessEqual(off + 4 + count*2, len(raw))
                cursor, previous = 0, prolog
                while cursor < count:
                    code, info = raw[off+4+2*cursor:off+6+2*cursor]
                    self.assertLessEqual(code, previous)
                    previous = code
                    opcode, operand = info & 15, info >> 4
                    extra = {0:0, 2:0, 3:0, 4:1, 5:2, 8:1, 9:2, 10:0}
                    if opcode == 1:
                        self.assertIn(operand, (0,1))
                        n = 1 if operand == 0 else 2
                    else:
                        self.assertIn(opcode, extra)
                        n = extra[opcode]
                    cursor += 1+n
                    self.assertLessEqual(cursor, count)
                self.assertLess(start, end)
                self.assertLessEqual(prolog, end-start)

    def test_rel32_relocations_and_no_site_overlap(self):
        spec, _ = patch._payload()
        seen = set()
        for offset, rva, raw in patch.code_writes()[1:]:
            opcode = next(h[1] for h in patch.HOOKS if h[0] == rva)
            name = next(h[3] for h in patch.HOOKS if h[0] == rva)
            self.assertEqual(raw[0], opcode)
            self.assertEqual(rva+5+struct.unpack("<i",raw[1:])[0], spec["entrypoints"][name])
            self.assertEqual(offset, rva-0xc00)
            addresses = set(range(offset,offset+len(raw)))
            self.assertFalse(seen & addresses)
            seen |= addresses
        with self.assertRaises(patch.UnsupportedBuild):
            patch.branch(0,0xe8,1<<40)

    def test_hext_is_explicitly_prepared_image_only(self):
        self.assertEqual(patch.build_hext(False), "")
        text = patch.build_hext(True)
        self.assertIn("not a standalone live patch",text)
        self.assertIn(patch.ORIGINAL_SHA256,text)
        self.assertIn(f"{patch.IMAGE_BASE+patch.PAYLOAD_RVA:X} = ",text)

    def test_flags_are_strict_booleans(self):
        for value in (0,1,"true",None,[],{}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                patch.transform(b"",value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                patch.build_hext(value)

    def test_unknown_executable_unchanged(self):
        data=b"MZ"+bytes(1024)
        before=data[:]
        with self.assertRaises(patch.UnsupportedBuild):
            patch.transform(data,True)
        self.assertEqual(data,before)

    def test_payload_corruption_and_source_drift_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)
            for name in ("ammunition_controls.py","ammunition_native.c","ammunition_bridge.S",
                         "ammunition_payload.json"):
                shutil.copyfile(ROOT/"plugins/ds1"/name,target/name)
            spec=importlib.util.spec_from_file_location("private_ammo_fixture",target/"ammunition_controls.py")
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            original=(target/"ammunition_payload.json").read_text()
            data=json.loads(original)
            data["payloadSha256"]="0"*64
            (target/"ammunition_payload.json").write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                module._payload()
            (target/"ammunition_payload.json").write_text(original)
            (target/"ammunition_native.c").write_text("changed")
            with self.assertRaises(ValueError):
                module._payload()

    def test_source_hashes_accept_windows_line_endings(self):
        spec,_=patch._payload()
        for name,expected in spec["sourceHashes"].items():
            source=(ROOT/"plugins/ds1"/name).read_text()
            self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),expected)

    def test_shipped_native_machine_code(self):
        if platform.machine().lower() not in ("x86_64","amd64"):
            self.skipTest("Windows x64 payload requires an x64 test host")
        if os.name != "nt" and not (shutil.which("cc") or shutil.which("clang")):
            self.skipTest("The Linux ABI test adapter needs a C compiler")
        result=subprocess.run([sys.executable,"-S",str(Path(__file__).with_name("ammunition_native_harness.py"))],
                              cwd=ROOT,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stdout+"\n"+result.stderr)
        self.assertIn("67 assertions passed",result.stdout)


ORIGINAL=b"original executable fixture"+bytes(100)
ENABLED=b"enabled executable fixture"+bytes(200)


def fake_patch():
    def identify(data):
        if data==ORIGINAL: return "vanilla"
        if data==ENABLED: return "enabled"
        raise patch.UnsupportedBuild("unrecognized fixture")
    def transform(data,enabled):
        identify(data)
        return ENABLED if enabled else ORIGINAL
    return types.SimpleNamespace(
        ORIGINAL_SIZE=len(ORIGINAL),patched_size=lambda:len(ENABLED),
        identify=identify,transform=transform,UnsupportedBuild=patch.UnsupportedBuild,
        EXECUTABLE=patch.EXECUTABLE,TWEAK_ID=patch.TWEAK_ID,LABEL=patch.LABEL,
        HELP=patch.HELP,DEFAULT_ENABLED=False,_payload=lambda:None)


class DeploymentChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="ds1-ammunition-test-")
        self.base=Path(self.temp.name)
        self.game=self.base/"game"
        self.project=self.base/"project"
        self.game.mkdir();self.project.mkdir()
        (self.project/tweak.PROJECT_MARKER).write_text("fixture")
        self.live=self.game/patch.EXECUTABLE
        self.backup=self.game/tweak.BACKUP_FILE
        self.live.write_bytes(ORIGINAL)
        self.fake=fake_patch()
        self.mocks=[mock.patch.object(tweak,"patch",self.fake),
                    mock.patch.object(tweak,"ensure_game_closed")]
        for item in self.mocks: item.start()

    def tearDown(self):
        for item in reversed(self.mocks): item.stop()
        self.temp.cleanup()

    def store(self,readonly=False,project=True):
        return tweak.TweakStore(self.game,self.project if project else None,readonly)

    def test_roundtrip_and_bounded_backup(self):
        tweak.deploy(self.game,True)
        self.assertEqual(self.live.read_bytes(),ENABLED)
        self.assertEqual(self.backup.read_bytes(),ORIGINAL)
        for enabled in (True,False,False,True,False):
            tweak.deploy(self.game,enabled)
            self.assertEqual(self.live.read_bytes(),ENABLED if enabled else ORIGINAL)
        self.assertEqual(set(p.name for p in self.game.iterdir()),
                         {patch.EXECUTABLE,tweak.BACKUP_FILE})

    def test_disabled_vanilla_has_no_backup_side_effect(self):
        tweak.deploy(self.game,False)
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.live.read_bytes(),ORIGINAL)

    def test_unknown_live_file_never_overwritten(self):
        self.live.write_bytes(b"unknown")
        with self.assertRaises(ValueError): tweak.deploy(self.game,True)
        self.assertEqual(self.live.read_bytes(),b"unknown")
        self.assertFalse(self.backup.exists())

    def test_unknown_or_patched_backup_refused(self):
        for data in (b"unknown",ENABLED):
            self.backup.write_bytes(data)
            with self.subTest(data=data[:8]),self.assertRaises(ValueError):
                tweak.deploy(self.game,True)
            self.assertEqual(self.live.read_bytes(),ORIGINAL)
            self.assertEqual(self.backup.read_bytes(),data)

    def test_missing_backup_after_apply_refused(self):
        self.live.write_bytes(ENABLED)
        for enabled in (True,False):
            with self.subTest(enabled=enabled),self.assertRaises(ValueError):
                tweak.deploy(self.game,enabled)
        self.assertEqual(self.live.read_bytes(),ENABLED)

    def test_atomic_replace_failure_keeps_original(self):
        with mock.patch.object(tweak,"atomic_write",side_effect=PermissionError("image in use")):
            with self.assertRaises(PermissionError): tweak.deploy(self.game,True)
        self.assertEqual(self.live.read_bytes(),ORIGINAL)
        self.assertEqual(self.backup.read_bytes(),ORIGINAL)

    def test_external_change_during_prepare_refused(self):
        transform=self.fake.transform
        def changed(data,enabled):
            self.live.write_bytes(b"changed externally")
            return transform(data,enabled)
        self.fake.transform=changed
        with self.assertRaises(ValueError): tweak.deploy(self.game,True)
        self.assertEqual(self.live.read_bytes(),b"changed externally")
        self.assertEqual(self.backup.read_bytes(),ORIGINAL)

    def test_running_guard_precedes_any_write(self):
        with mock.patch.object(tweak,"ensure_game_closed",side_effect=ValueError("running")):
            with self.assertRaisesRegex(ValueError,"running"): tweak.deploy(self.game,True)
        self.assertEqual(self.live.read_bytes(),ORIGINAL)
        self.assertFalse(self.backup.exists())

    def test_invalid_enabled_refused(self):
        for value in (1,0,"yes",None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                tweak.deploy(self.game,value)
        self.assertFalse(self.backup.exists())

    def test_symlink_and_hardlink_refused(self):
        linked=self.base/"link"
        try: linked.symlink_to(self.game,target_is_directory=True)
        except OSError: pass  # unprivileged Windows may prohibit creating this fixture
        else:
            with self.assertRaises(ValueError): tweak.deploy(linked,True)
        hard=self.base/"hard.exe"
        try: os.link(self.live,hard)
        except OSError: self.skipTest("Filesystem does not support hardlink fixtures")
        with self.assertRaises(ValueError): tweak.deploy(self.game,True)
        self.assertEqual(self.live.read_bytes(),ORIGINAL)

    def test_setting_default_and_strict_edit(self):
        store=self.store()
        self.assertFalse(store.enabled)
        self.assertEqual(store.dirty_count,0)
        for value in (1,"true",None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                store.edit(value)
        self.assertFalse((self.project/tweak.SETTING_FILE).exists())

    def test_save_only_writes_project_and_discard_reloads(self):
        store=self.store()
        store.edit(True)
        self.assertEqual(store.dirty_count,1)
        self.assertEqual(self.live.read_bytes(),ORIGINAL)
        store.save()
        self.assertFalse(self.backup.exists())
        self.assertTrue(self.store().enabled)
        store.edit(False)
        store.discard()
        self.assertTrue(store.enabled)
        self.assertEqual(store.dirty_count,0)
        self.assertEqual(set(p.name for p in self.project.iterdir()),
                         {tweak.PROJECT_MARKER,tweak.SETTING_FILE})

    def test_vanilla_and_references_are_readonly(self):
        for store in (self.store(readonly=True),self.store(project=False)):
            with self.assertRaises(PermissionError): store.edit(True)
            with self.assertRaises(PermissionError): store.apply()
            store.save()
        self.assertFalse((self.project/tweak.SETTING_FILE).exists())

    def test_unsaved_and_stale_apply_refused(self):
        store=self.store()
        store.edit(True)
        with self.assertRaises(ValueError): store.apply()
        store.save()
        other=self.store()
        other.edit(False);other.save()
        with self.assertRaises(ValueError): store.apply()
        self.assertEqual(self.live.read_bytes(),ORIGINAL)

    def test_external_settings_edit_not_overwritten(self):
        store=self.store()
        store.edit(True)
        path=self.project/tweak.SETTING_FILE
        path.write_text(json.dumps({"schema":1,patch.TWEAK_ID:True}))
        with self.assertRaises(ValueError): store.save()
        self.assertTrue(json.loads(path.read_text())[patch.TWEAK_ID])

    def test_corrupt_settings_refused_and_preserved(self):
        path=self.project/tweak.SETTING_FILE
        for raw in (b"not json",b"x"*4097,b"{}",b'{"schema":2}',b'{"schema":1,"other":true}'):
            path.write_bytes(raw)
            with self.subTest(raw=raw[:20]),self.assertRaises(ValueError): self.store()
            self.assertEqual(path.read_bytes(),raw)

    def test_project_paths_are_validated(self):
        for path in (self.game,self.game/"inside",self.base):
            with self.subTest(path=path),self.assertRaises(ValueError):
                tweak.TweakStore(self.game,path,False)
        (self.project/tweak.PROJECT_MARKER).unlink()
        with self.assertRaises(ValueError): self.store()

    def test_apply_restore_and_status_are_independent_of_project_setting(self):
        store=self.store()
        store.edit(True);store.save()
        self.assertTrue(store.apply()["applied"])
        setting=(self.project/tweak.SETTING_FILE).read_bytes()
        self.assertTrue(store.snapshot(refresh=True)["backupOk"])
        self.assertFalse(self.store(project=False).restore()["applied"])
        self.assertEqual((self.project/tweak.SETTING_FILE).read_bytes(),setting)
        self.assertTrue(store.enabled)

    def test_status_reports_unknown_and_missing_original(self):
        store=self.store()
        self.live.write_bytes(ENABLED)
        result=store.snapshot(refresh=True)
        self.assertFalse(result["available"])
        self.assertTrue(result["applied"])
        self.live.write_bytes(b"unknown")
        result=store.snapshot(refresh=True)
        self.assertIsNone(result["applied"])
        self.assertFalse(result["available"])


class PrivateExecutableChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        location=os.environ.get("LEXEDITOR_DS1_AMMO_EXE") or os.environ.get("LEXEDITOR_DS1_PROBE_EXE")
        if not location: raise unittest.SkipTest("No explicit private executable; public CI has no retail assets")
        cls.path=Path(location)
        cls.original=cls.path.read_bytes()
        cls.candidate=patch.transform(cls.original,True)

    def test_exact_fingerprints_and_roundtrip(self):
        self.assertEqual(patch.identify(self.original),"vanilla")
        self.assertEqual(patch.identify(self.candidate),"enabled")
        self.assertEqual(patch.transform(self.candidate,False),self.original)
        self.assertEqual(patch.transform(self.candidate,True),self.candidate)
        self.assertEqual(patch.transform(self.original,False),self.original)
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_no_unrelated_original_bytes_changed(self):
        allowed=set()
        for off in patch.HEADER_ORIGINAL: allowed.update(range(off,off+4))
        for rva,_,_,_ in patch.HOOKS: allowed.update(range(rva-0xc00,rva-0xc00+5))
        different={i for i,(a,b) in enumerate(zip(self.original,self.candidate)) if a!=b}
        self.assertLessEqual(different,allowed)
        self.assertGreater(patch.PAYLOAD_OFFSET,len(self.original))

    def test_prepared_pe_protections_bss_and_function_table(self):
        spec,raw,table_rva,table_off,table_size,size,image=patch._layout()
        self.assertEqual(len(self.candidate),size)
        self.assertEqual(struct.unpack_from("<II",self.candidate,0x220),(table_rva,table_size))
        self.assertEqual(self.candidate[table_off:table_off+patch.TABLE_SIZE],
                         self.original[patch.TABLE_OFFSET:patch.TABLE_OFFSET+patch.TABLE_SIZE])
        functions=list(struct.iter_unpack("<III",self.candidate[table_off:table_off+table_size]))
        self.assertEqual(functions[-len(spec["functions"]):],[tuple(r) for r in spec["functions"]])
        self.assertTrue(all(a[0]<b[0] for a,b in zip(functions,functions[1:])))
        self.assertEqual(struct.unpack_from("<I",self.candidate,0x2e0)[0]+0x1a25000,0x1d0b000)
        self.assertLessEqual(patch.SCRATCH_RVA+patch.SCRATCH_SIZE,0x1d0b000)
        self.assertEqual(struct.unpack_from("<I",self.candidate,0x3ec)[0]&0xe0000000,0x60000000)
        self.assertEqual(struct.unpack_from("<II",self.candidate,0x228),(0,0))
        self.assertEqual(self.candidate[patch.PAYLOAD_OFFSET:patch.PAYLOAD_OFFSET+len(raw)],raw)

    def test_modified_candidate_refused(self):
        candidate=bytearray(self.candidate)
        candidate[patch.PAYLOAD_OFFSET]^=1
        with self.assertRaises(patch.UnsupportedBuild): patch.transform(bytes(candidate),False)

    def test_real_file_deployment_and_restoration(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory)
            live=game/patch.EXECUTABLE
            live.write_bytes(self.original)
            with mock.patch.object(tweak,"ensure_game_closed"):
                tweak.deploy(game,True)
                self.assertEqual(live.read_bytes(),self.candidate)
                tweak.deploy(game,False)
                self.assertEqual(live.read_bytes(),self.original)
            self.assertEqual((game/tweak.BACKUP_FILE).read_bytes(),self.original)


if __name__ == "__main__":
    unittest.main()
