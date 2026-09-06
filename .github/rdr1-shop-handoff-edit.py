from pathlib import Path

p = Path('games/rdr/server.py')
s = p.read_text(encoding='utf-8')
marker = '\n\ndef save_shop(source: str, root_hash: str, item_index: int,\n'
assert marker in s
insert = r'''

def shop_test_plan() -> dict:
    """Choose one stable real prepared shop record for a reversible price test.

    Identity always comes from vanilla prepared data, so staging the test cannot
    silently move the handoff to another item.  If that exact price is already
    customized by the project, the helper refuses to overwrite it.
    """
    vanilla_rows = shops_payload(True)["rows"]
    if not vanilla_rows:
        return {"available": False, "reason": "No prepared ShopInventory records are available."}
    candidates = sorted(
        (row for row in vanilla_rows
         if row.get("name") and row.get("shop") and math.isfinite(row.get("priceModifier", float("nan")))
         and row.get("quantityPerPurchase", 0) > 0 and row.get("totalAvailableQuantity", 0) != 0),
        key=lambda row: (row["shop"].casefold(), row["name"].casefold(), row["source"],
                         row["rootHash"], row["itemIndex"]),
    )
    if not candidates:
        return {"available": False, "reason": "Prepared shops contain no usable priced stock record."}
    baseline = candidates[0]
    active = {row["id"]: row for row in shops_payload()["rows"]}.get(baseline["id"])
    if active is None:
        return {"available": False, "reason": "The selected prepared shop record is missing from the active project."}
    original = float(baseline["priceModifier"])
    # Use a conspicuous but bounded multiplier. The alternative keeps a vanilla
    # 2.0 record equally obvious rather than turning the test into a no-op.
    test_value = 2.0 if original != 2.0 else 0.5
    test_value = struct.unpack("<f", struct.pack("<f", test_value))[0]
    current = float(active["priceModifier"])
    if current == original:
        status = "baseline"
    elif current == test_value:
        status = "staged"
    else:
        status = "custom"
    return {
        "available": True,
        "id": baseline["id"],
        "shop": baseline["shop"],
        "item": baseline["name"],
        "category": baseline["category"],
        "source": baseline["source"],
        "rootHash": baseline["rootHash"],
        "itemIndex": baseline["itemIndex"],
        "baselinePriceModifier": original,
        "testPriceModifier": test_value,
        "currentPriceModifier": current,
        "status": status,
        "stageAllowed": status in {"baseline", "staged"},
        "restoreAllowed": status in {"baseline", "staged"},
        "projectPath": active["projectPath"],
        "instruction": (
            "Stage changes only this item's PriceModifier. Deploy Project, visit this exact shop/item, "
            "then Restore Shop Test and redeploy to return the field to its vanilla multiplier."
        ),
    }


def _save_shop_test(target: str) -> dict:
    plan = shop_test_plan()
    if not plan.get("available"):
        raise RuntimeError(plan.get("reason") or "No shop test candidate is available")
    if plan["status"] == "custom":
        raise ValueError(
            "The shop test candidate already has a non-test custom price. Reload Shops and preserve that edit; "
            "Lexeditor will not overwrite it for a test."
        )
    if target == "test":
        value = plan["testPriceModifier"]
    elif target == "baseline":
        value = plan["baselinePriceModifier"]
    else:
        raise ValueError("Unknown shop-test target")
    result = save_shop(
        plan["source"], plan["rootHash"], plan["itemIndex"], plan["item"],
        [{"field": "PriceModifier", "value": value}],
    )
    refreshed = shop_test_plan()
    expected = "staged" if target == "test" else "baseline"
    if refreshed.get("status") != expected:
        raise RuntimeError(f"Shop test did not read back as {expected}")
    return {**result, "test": refreshed,
            "message": ("Shop test price staged; Deploy Project before launching RDR1."
                        if target == "test" else
                        "Shop test price restored; redeploy the project to restore the game copy.")}


def stage_shop_test() -> dict:
    return _save_shop_test("test")


def restore_shop_test() -> dict:
    return _save_shop_test("baseline")
'''
s = s.replace(marker, insert + marker, 1)
s = s.replace('''        "deployment": _deployment_payload(),\n        "problems": paths.check()\n''', '''        "deployment": _deployment_payload(),\n        "shopTest": shop_test_plan(),\n        "problems": paths.check()\n''', 1)
s = s.replace('''            elif path == "/api/deployment/revert":\n                self.json_response(revert_archives(GAME_ROOT, ARCHIVE_SPECS))\n''', '''            elif path == "/api/deployment/revert":\n                self.json_response(revert_archives(GAME_ROOT, ARCHIVE_SPECS))\n            elif path == "/api/shop-test/stage":\n                self.json_response(stage_shop_test())\n            elif path == "/api/shop-test/restore":\n                self.json_response(restore_shop_test())\n''', 1)
p.write_text(s, encoding='utf-8')

p = Path('games/rdr/editor.html')
s = p.read_text(encoding='utf-8')
old = '''    const deliveryCard=el("section",{class:"card"},el("h2",{},"Saved files and game delivery"),\n'''
assert old in s
# Insert a separate, inspectable handoff card before the general delivery card.
insert = r'''    const shopTest=state.dashboard.shopTest||{available:false,reason:"No shop test candidate is available."};
    const shopTestCard=el("section",{class:"card"},el("h2",{},"Shop edit test"),
      !shopTest.available?el("div",{class:"error"},shopTest.reason):[
        el("p",{},"Lexeditor selected one stable prepared record so the in-game check does not require you to invent a shop, item, or value."),
        el("div",{class:"path-row"},el("b",{},"Shop"),el("code",{},shopTest.shop)),
        el("div",{class:"path-row"},el("b",{},"Item"),el("code",{},shopTest.item)),
        el("div",{class:"path-row"},el("b",{},"Price multiplier"),el("code",{},`vanilla ${shopTest.baselinePriceModifier} · current ${shopTest.currentPriceModifier} · test ${shopTest.testPriceModifier}`)),
        el("div",{class:shopTest.status==="staged"?"ok":shopTest.status==="custom"?"error":"source-note"},shopTest.status==="staged"?"Test value is staged. Deploy Project before launching RDR1.":shopTest.status==="custom"?"This candidate already has a different custom price; the test helper will not overwrite it.":"Candidate is at its vanilla price and ready to stage."),
        el("p",{},shopTest.instruction),
        el("div",{class:"redhook-actions"},
          el("button",{type:"button",onclick:()=>stageShopTest(),disabled:!shopTest.stageAllowed||shopTest.status==="staged"},"Stage Shop Test"),
          el("button",{type:"button",class:"secondary",onclick:()=>restoreShopTest(),disabled:!shopTest.restoreAllowed||shopTest.status!=="staged"},"Restore Shop Test"),
          el("button",{type:"button",class:"secondary",onclick:()=>openShopTest(),disabled:!shopTest.available},"Open in Shops"))
      ]);
'''
s = s.replace(old, insert + old, 1)
s = s.replace('''    $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard,deliveryCard));shell.refresh();\n''', '''    $("#main").replaceChildren(el("div",{class:"cards"},statusCard,redHookCard,shopTestCard,deliveryCard));shell.refresh();\n''', 1)
marker = '''  async function deployProject(){\n'''
assert marker in s
functions = r'''  async function stageShopTest(){
    try{setStatus("Staging deterministic shop price test…");const result=await api("/api/shop-test/stage",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.shops=await api("/api/shops");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Shop test staged");renderProject();}
    catch(error){setStatus("Shop test staging failed");showAlert({title:"Shop test staging failed",items:[{item:"Price test",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  async function restoreShopTest(){
    try{setStatus("Restoring deterministic shop test price…");const result=await api("/api/shop-test/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});state.shops=await api("/api/shops");state.dashboard=await api("/api/dashboard");setStatus(result.message||"Shop test restored");renderProject();}
    catch(error){setStatus("Shop test restore failed");showAlert({title:"Shop test restore failed",items:[{item:"Price test",issue:error.message||String(error)}],closeLabel:"Confirm and Close"});}
  }
  function openShopTest(){const test=state.dashboard.shopTest;if(!test?.available)return;state.shopQuery=test.item;state.shopName=test.shop;state.shopCategory="";state.shopSelected=test.id;navigate("shops");}
'''
s = s.replace(marker, functions + marker, 1)
p.write_text(s, encoding='utf-8')

p = Path('tools/verify_rdr_editing.py')
s = p.read_text(encoding='utf-8')
needle = '''    def test_shop_stock_bounds_and_unlimited(self):\n        self.assertEqual(self.shop_save(-1, "TotalAvailableQuantity")["saved"], 1)\n        self.assertEqual(self.shop_save(0, "QuantityPerPurchase")["saved"], 1)\n        self.assertEqual(server.shops_payload()["rows"][0]["totalAvailableQuantity"], -1)\n\n'''
assert needle in s
addition = '''    def test_shop_handoff_is_deterministic_reversible_and_does_not_clobber_custom_price(self):\n        plan = server.shop_test_plan()\n        self.assertTrue(plan["available"])\n        self.assertEqual(plan["status"], "baseline")\n        identity = plan["id"]\n        source_bytes = Path(next(row for row in server.shops_payload(True)["rows"] if row["id"] == identity)["sourcePath"]).read_bytes()\n        staged = server.stage_shop_test()\n        self.assertEqual(staged["test"]["id"], identity)\n        self.assertEqual(staged["test"]["status"], "staged")\n        self.assertEqual(staged["test"]["currentPriceModifier"], plan["testPriceModifier"])\n        self.assertEqual(server.shop_test_plan()["id"], identity)\n        restored = server.restore_shop_test()\n        self.assertEqual(restored["test"]["status"], "baseline")\n        self.assertEqual(restored["test"]["currentPriceModifier"], plan["baselinePriceModifier"])\n        active = next(row for row in server.shops_payload()["rows"] if row["id"] == identity)\n        server.save_shop(active["source"], active["rootHash"], active["itemIndex"], active["name"],\n                         [{"field": "PriceModifier", "value": 3.0}])\n        self.assertEqual(server.shop_test_plan()["status"], "custom")\n        with self.assertRaisesRegex(ValueError, "will not overwrite"):\n            server.stage_shop_test()\n        self.assertEqual(Path(active["sourcePath"]).read_bytes(), source_bytes)\n\n'''
s = s.replace(needle, needle + addition, 1)
p.write_text(s, encoding='utf-8')

p = Path('tools/verify_rdr_editing_browser.py')
s = p.read_text(encoding='utf-8')
needle = '''                    assert page.get_by_role('button', name='Deploy Project').count()\n                    assert page.get_by_role('button', name='Revert Deployment').count()\n'''
assert needle in s
addition = '''                    assert page.get_by_text('Shop edit test', exact=True).count()\n                    assert page.get_by_role('button', name='Stage Shop Test').count()\n                    plan = server.shop_test_plan()\n                    assert plan['available'] and plan['status'] == 'baseline'\n                    page.get_by_role('button', name='Stage Shop Test').click()\n                    page.wait_for_function('state.dashboard.shopTest.status === "staged"')\n                    assert server.shop_test_plan()['id'] == plan['id']\n                    assert server.shop_test_plan()['currentPriceModifier'] == plan['testPriceModifier']\n                    page.get_by_role('button', name='Restore Shop Test').click()\n                    page.wait_for_function('state.dashboard.shopTest.status === "baseline"')\n                    assert server.shop_test_plan()['currentPriceModifier'] == plan['baselinePriceModifier']\n'''
s = s.replace(needle, needle + addition, 1)
p.write_text(s, encoding='utf-8')
