from pathlib import Path

p = Path('games/rdr/server.py')
s = p.read_text(encoding='utf-8')
# Constants beside other project-owned files.
s = s.replace('''CAMERA_GENERATED_ROOT = PROJECT / ".lexeditor-generated" / "camera"\n''', '''CAMERA_GENERATED_ROOT = PROJECT / ".lexeditor-generated" / "camera"\nMISSION_TEST_STATE = PROJECT / ".lexeditor-mission-test.json"\nMISSION_TEST_ID = 2\nMISSION_TEST_REWARDS = {"cash": 123, "fame": 321, "honor": 222}\n''', 1)
marker = '\n\ndef redhook_payload() -> dict:\n'
assert marker in s
insert = r'''

def _mission_override_document() -> dict:
    base = mission_rewards.load_generated()
    if mission_rewards.OVERRIDE_FILE.is_file():
        return mission_rewards.validate_override(json.loads(
            mission_rewards.OVERRIDE_FILE.read_text(encoding="utf-8-sig")), base)
    return {"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": []}


def _mission_row(document: dict, mission_id: int) -> dict | None:
    return next((row for row in document.get("overrides", []) if row.get("id") == mission_id), None)


def _mission_test_manifest() -> dict | None:
    if not MISSION_TEST_STATE.is_file():
        return None
    try:
        document = json.loads(MISSION_TEST_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"Mission test state is unreadable: {error}") from error
    if (not isinstance(document, dict) or document.get("version") != 1 or
            document.get("missionId") != MISSION_TEST_ID or
            document.get("testOverride") != {"id": MISSION_TEST_ID, "rewards": MISSION_TEST_REWARDS}):
        raise ValueError("Mission test state does not match the current deterministic test")
    previous = document.get("previousOverride")
    if previous is not None:
        mission_rewards.validate_override({
            "schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": [previous]
        })
    return document


def mission_test_plan() -> dict:
    base = mission_rewards.load_generated()
    mission = next(row for row in base["missions"] if row["id"] == MISSION_TEST_ID)
    current_document = _mission_override_document()
    current = _mission_row(current_document, MISSION_TEST_ID)
    test_row = {"id": MISSION_TEST_ID, "rewards": dict(MISSION_TEST_REWARDS)}
    try:
        manifest = _mission_test_manifest()
        problem = ""
    except ValueError as error:
        manifest = None
        problem = str(error)
    if problem:
        status = "conflict"
    elif manifest is not None:
        status = "staged" if current == test_row else "conflict"
        if status == "conflict":
            problem = "Mission 2 changed after the deterministic test was staged; restore is locked to avoid overwriting it."
    else:
        status = "custom" if current else "baseline"
    return {
        "available": not bool(problem),
        "missionId": MISSION_TEST_ID,
        "mission": mission["name"],
        "storyTitle": "New Friends, Old Problems",
        "scriptName": mission["scriptName"],
        "vanillaRewards": dict(mission["rewards"]),
        "testRewards": dict(MISSION_TEST_REWARDS),
        "currentOverride": current,
        "status": status,
        "problem": problem,
        "stageAllowed": not bool(problem) and manifest is None,
        "restoreAllowed": not bool(problem) and manifest is not None and current == test_row,
        "stateFile": str(MISSION_TEST_STATE),
        "overrideFile": str(mission_rewards.OVERRIDE_FILE),
        "route": "Use a normal-difficulty New Game: complete Intro 01, then complete Ranch 01. Mission Replay is intentionally rejected by the runtime.",
        "expected": "At Ranch 01 completion the configured reward deltas are +$123 cash, +321 fame, and +222 honor instead of the vanilla 0/0/+50.",
        "instruction": "Stage this test before starting the New Game route. The native runtime reloads LexerRDR.missions.json from the workspace; Deploy Project is not required for this JSON override.",
    }


def stage_mission_test() -> dict:
    plan = mission_test_plan()
    if not plan.get("available"):
        raise RuntimeError(plan.get("problem") or "Mission test is unavailable")
    if not plan.get("stageAllowed"):
        raise ValueError("Mission reward test is already staged")
    current = _mission_override_document()
    previous = _mission_row(current, MISSION_TEST_ID)
    rows = [row for row in current["overrides"] if row["id"] != MISSION_TEST_ID]
    rows.append({"id": MISSION_TEST_ID, "rewards": dict(MISSION_TEST_REWARDS)})
    candidate = {"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": rows}
    save_missions(candidate)
    try:
        manifest = {
            "version": 1,
            "missionId": MISSION_TEST_ID,
            "previousOverride": previous,
            "testOverride": {"id": MISSION_TEST_ID, "rewards": dict(MISSION_TEST_REWARDS)},
        }
        atomic_bytes(MISSION_TEST_STATE, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    except Exception:
        rollback_rows = [row for row in _mission_override_document()["overrides"] if row["id"] != MISSION_TEST_ID]
        if previous is not None:
            rollback_rows.append(previous)
        save_missions({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": rollback_rows})
        raise
    refreshed = mission_test_plan()
    if refreshed["status"] != "staged":
        raise RuntimeError("Mission reward test did not read back as staged")
    return {"saved": 1, "test": refreshed,
            "message": "Mission 2 reward test staged. Install/run the current LexerRDR native candidate; no RPF deployment is needed for mission JSON."}


def restore_mission_test() -> dict:
    plan = mission_test_plan()
    if not plan.get("available"):
        raise RuntimeError(plan.get("problem") or "Mission test is unavailable")
    if not plan.get("restoreAllowed"):
        raise ValueError("Mission reward test is not safely restorable")
    manifest = _mission_test_manifest()
    current = _mission_override_document()
    test_row = manifest["testOverride"]
    if _mission_row(current, MISSION_TEST_ID) != test_row:
        raise ValueError("Mission 2 changed after staging; refusing to overwrite it")
    rows = [row for row in current["overrides"] if row["id"] != MISSION_TEST_ID]
    if manifest.get("previousOverride") is not None:
        rows.append(manifest["previousOverride"])
    save_missions({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": rows})
    MISSION_TEST_STATE.unlink(missing_ok=True)
    refreshed = mission_test_plan()
    expected_status = "custom" if manifest.get("previousOverride") is not None else "baseline"
    if refreshed["status"] != expected_status:
        raise RuntimeError("Mission reward test did not restore the previous mission 2 state")
    return {"saved": 1, "test": refreshed,
            "message": "Mission 2 reward test restored to the exact pre-test override state."}
'''
s = s.replace(marker, insert + marker, 1)
s = s.replace('''        "shopTest": shop_test_plan(),\n        "problems": paths.check()\n''', '''        "shopTest": shop_test_plan(),\n        "missionTest": mission_test_plan(),\n        "problems": paths.check()\n''', 1)
s = s.replace('''            elif path == "/api/shop-test/restore":\n                self.json_response(restore_shop_test())\n''', '''            elif path == "/api/shop-test/restore":\n                self.json_response(restore_shop_test())\n            elif path == "/api/mission-test/stage":\n                self.json_response(stage_mission_test())\n            elif path == "/api/mission-test/restore":\n                self.json_response(restore_mission_test())\n''', 1)
p.write_text(s, encoding='utf-8')

p = Path('games/rdr/editor.html')
s = p.read_text(encoding='utf-8')
marker = '''    const deliveryCard=el("section",{class:"card"},el("h2",{},"Saved files and game delivery"),\n'''
assert marker in s
card = r'''    const missionTest=state.dashboard.missionTest||{available:false,problem:"Mission reward test is unavailable."};
    const missionTestCard=el("section",{class:"card"},el("h2",{},"Mission reward test"),
      !missionTest.available?el("div",{class:"error"},missionTest.problem):[
        el("p",{},"Lexeditor uses a fixed early Story mission and preserves the exact mission-2 override that existed before staging."),
        el("div",{class:"path-row"},el("b",{},"Mission"),el("code",{},`${missionTest.storyTitle} · ${missionTest.mission} · ID ${missionTest.missionId}`)),
        el("div",{class:"path-row"},el("b",{},"Vanilla rewards"),el("code",{},`cash ${missionTest.vanillaRewards.cash} · fame ${missionTest.vanillaRewards.fame} · honor ${missionTest.vanillaRewards.honor}`)),
        el("div",{class:"path-row"},el("b",{},"Test rewards"),el("code",{},`cash ${missionTest.testRewards.cash} · fame ${missionTest.testRewards.fame} · honor ${missionTest.testRewards.honor}`)),
        el("div",{class:missionTest.status==="staged"?"ok":"source-note"},missionTest.status==="staged"?"Mission test is staged in LexerRDR.missions.json.":missionTest.status==="custom"?"A pre-existing mission-2 override exists; Stage will snapshot it and Restore will put it back exactly.":"Mission 2 is at vanilla override state and ready to stage."),
        el("p",{},missionTest.route),el("p",{},missionTest.expected),el("p",{},missionTest.instruction),
        el("div",{class:"redhook-actions"},
          el("button",{type:"button",onclick:()=>stageMissionTest(),disabled:!missionTest.stageAllowed},"Stage Mission Test"),
          el("button",{type:"button",class:"secondary",onclick:()=>restoreMissionTest(),disabled:!missionTest.restoreAllowed},"Restore Mission Test"),
          el("button",{type:"button",class:"secondary",onclick:()=>openMissionTest()},"Open in Missions"))
      ]);
'''
s = s.replace(marker, card + marker, 1)
s = s.replace('''    $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard,shopTestCard,deliveryCard));shell.refresh();\n''', '''    $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard,shopTestCard,missionTestCard,deliveryCard));shell.refresh();\n''', 1)
marker = '''  async function deployProject(){\n'''
assert marker in s
functions = r'''  async function stageMissionTest(){
    try{setStatus("Staging deterministic mission reward test…");const result=await api("/api/mission-test/stage",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.missions=await api("/api/missions");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Mission test staged");renderProject();}
    catch(error){setStatus("Mission test staging failed");showAlert({title:"Mission test staging failed",items:[{item:"Mission 2",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  async function restoreMissionTest(){
    try{setStatus("Restoring pre-test mission reward state…");const result=await api("/api/mission-test/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.missions=await api("/api/missions");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Mission test restored");renderProject();}
    catch(error){setStatus("Mission test restore failed");showAlert({title:"Mission test restore failed",items:[{item:"Mission 2",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  function openMissionTest(){const test=state.dashboard.missionTest;if(!test?.missionId)return;state.missionQuery=test.mission;state.missionRegion="";state.missionSelected=test.missionId;navigate("missions");}
'''
s = s.replace(marker, functions + marker, 1)
p.write_text(s, encoding='utf-8')

p = Path('tools/verify_rdr_editing.py')
s = p.read_text(encoding='utf-8')
needle = '''    def test_mission_save_and_reset_leave_generated_table_unchanged(self):\n'''
assert needle in s
addition = '''    def test_mission_handoff_preserves_and_restores_exact_pretest_override(self):\n        base = server.mission_test_plan()\n        self.assertEqual(base["missionId"], 2)\n        self.assertEqual(base["status"], "baseline")\n        server.save_missions({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards",\n            "overrides": [{"id": 5, "rewards": {"cash": 777}}, {"id": 2, "rewards": {"honor": 7}}]})\n        custom = server.mission_test_plan()\n        self.assertEqual(custom["status"], "custom")\n        staged = server.stage_mission_test()["test"]\n        self.assertEqual(staged["status"], "staged")\n        self.assertEqual(staged["currentOverride"], {"id": 2, "rewards": {"cash": 123, "fame": 321, "honor": 222}})\n        document = server._mission_override_document()\n        self.assertIn({"id": 5, "rewards": {"cash": 777}}, document["overrides"])\n        restored = server.restore_mission_test()["test"]\n        self.assertEqual(restored["status"], "custom")\n        document = server._mission_override_document()\n        self.assertIn({"id": 5, "rewards": {"cash": 777}}, document["overrides"])\n        self.assertIn({"id": 2, "rewards": {"honor": 7}}, document["overrides"])\n        self.assertFalse(server.MISSION_TEST_STATE.exists())\n\n    def test_mission_handoff_refuses_restore_after_mission2_changes(self):\n        server.stage_mission_test()\n        document = server._mission_override_document()\n        rows = [row for row in document["overrides"] if row["id"] != 2]\n        rows.append({"id": 2, "rewards": {"honor": 999}})\n        server.save_missions({"schemaVersion": 1, "contract": "LexerRDR.mission-rewards", "overrides": rows})\n        plan = server.mission_test_plan()\n        self.assertEqual(plan["status"], "conflict")\n        with self.assertRaisesRegex(RuntimeError, "changed after"):\n            server.restore_mission_test()\n        self.assertEqual(server._mission_row(server._mission_override_document(), 2), {"id": 2, "rewards": {"honor": 999}})\n\n'''
s = s.replace(needle, addition + needle, 1)
p.write_text(s, encoding='utf-8')

p = Path('tools/verify_rdr_editing_browser.py')
s = p.read_text(encoding='utf-8')
needle = '''                    delivery_text = page.locator('#main').inner_text()\n'''
assert needle in s
addition = '''                    assert page.get_by_text('Mission reward test', exact=True).count()\n                    mission_plan = server.mission_test_plan()\n                    assert mission_plan['missionId'] == 2 and mission_plan['status'] == 'baseline'\n                    page.get_by_role('button', name='Stage Mission Test').click()\n                    page.wait_for_function('state.dashboard.missionTest.status === "staged"')\n                    staged_mission = server.mission_test_plan()\n                    assert staged_mission['testRewards'] == {'cash': 123, 'fame': 321, 'honor': 222}\n                    page.get_by_role('button', name='Restore Mission Test').click()\n                    page.wait_for_function('state.dashboard.missionTest.status === "baseline"')\n                    assert server._mission_row(server._mission_override_document(), 2) is None\n'''
s = s.replace(needle, addition + needle, 1)
p.write_text(s, encoding='utf-8')
