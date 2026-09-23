// GitHub #82: one Tab press requests one ordinary animated weapon stow.
//
// Integration handoff: this issue-local module replaces the older
// updateAlwaysHolster() embedded in world_economy.cpp.  It is deliberately not
// registered here because script.cpp is integration-owned.
//
// ---------------------------------------------------------------------------
// WHY THE PREVIOUS REVISIONS FAILED, AND WHY THE FAILURE WAS NON-DETERMINISTIC
// ---------------------------------------------------------------------------
//
// DEFECT A - the physical Tab edge was BANKED, not drained.
//   GetAsyncKeyState()'s low bit is a latch: it is set when the key goes down
//   and it is cleared only by a call to GetAsyncKeyState for that key. The
//   previous revision called it at the very END of the function, after seven
//   early returns (feature off, no ped, mission, vehicle, mount, NO WEAPON IN
//   HAND, control already disabled). Every Tab press made in any of those
//   states therefore stayed latched until the first frame that reached the
//   call, and was then harvested as if it had just happened.
//
//   A weapon is drawn by pressing Tab WITH EMPTY HANDS - which is exactly the
//   `!weaponInHand` early return. So every single Tab-draw banked an edge, and
//   the first frame on which the drawn weapon appeared at attach point 0
//   harvested that stale edge and immediately issued a stow INTO THE RUNNING
//   DRAW. That is the "time period after I pull out my weapon during which I
//   can't put it away": the press that was supposed to put it away had already
//   been spent, invisibly, by the draw itself.
//
// DEFECT B - the stow was issued on top of an in-flight weapon-swap task.
//   Draw and stow are the SAME script task, 716706914. Rockstar never issues
//   the stow sequence while that task is live; every shipped call site tests it
//   first:
//     _downloads/RDR2-Decompiled-Scripts/script_rel/act_bankrobbery01.c:22038
//       `if (!func_226(iParam0, 716706914)) { _HIDE_PED_WEAPONS; ... }`
//     act_bankrobbery01.c:10854-10866 - func_226 returns TRUE (busy) when
//       `GET_SCRIPT_TASK_STATUS(ped, iParam1, true)` is 1 or 0.
//     act_caunc_rustling.c:13561 - same 716706914 test before TASK_SWAP_WEAPON.
//   The draw itself goes through that task too:
//     act_caunc_rustling.c:26060-26062 - SET_CURRENT_PED_WEAPON(best) then
//       `TASK_SWAP_WEAPON(ped, 1, 0, 0, 0)`   (arg1 = 1 -> draw)
//     abigail2_1.c:81135 - `TASK_SWAP_WEAPON(Global_35, 0, 1, 0, 0)`
//   The previous revision had no such test, so the stale edge from Defect A
//   fired the three-call sequence at an arbitrary point inside the draw. WHERE
//   in the draw it landed decided what the player saw, which is the entire
//   source of the reported tri-state:
//     - landed early  -> SET_CURRENT_PED_WEAPON(UNARMED) applied, then the draw
//                        task finished and re-attached: weapon appears on the
//                        back with no animation ("teleporting onto my back");
//     - landed mid    -> the draw task won outright: weapon ends up in the hand
//                        ("he put it into his hand like in vanilla");
//     - landed after  -> clean run, the authored stow plays ("it once went away
//                        the way I want").
//   Tapping Tab ~50 times eventually placed one tap in the idle window after a
//   draw had fully retired, which is why brute force appeared to help.
//
// THE FIX IS NOT A TIMEOUT. There is no ms constant, no retry, no completion
// poll driving a second attempt, and no held-key repetition anywhere below.
//   1. The physical edge is drained UNCONDITIONALLY on the first line of the
//      function, before any gate, so it can never bank across a state change.
//   2. A press is latched as one pending intent. If the swap-task slot is busy
//      the intent WAITS for the slot instead of being rejected or repeated, and
//      is issued on the first frame the slot is free. From the player's side
//      the post-draw dead window disappears: Tab pressed during a draw stows as
//      soon as the draw retires, from that one press.
//   3. The sequence is issued exactly once per latched press.
// ---------------------------------------------------------------------------

// Rockstar's weapon-swap script task. Both draw and stow run through it.
// Status values per act_bankrobbery01.c:10864 (0 = assigned/pending,
// 1 = running) and :22057 (8 = finished/none).
static const Hash kHolsterSwapTaskHash = 716706914;

static bool  g_holsterPending = false;   // one accepted press awaiting the slot
static bool  g_holsterVerify = false;    // log survival on the following frame
static bool  g_holsterDeferLogged = false;
static DWORD g_holsterHeartbeatAt = 0;

// #126: routed to the unified GameplayTweaks.log under subsystem "holster".
// Bounding and once-per-launch truncation are handled there.
static void alwaysHolsterLog(GtLogLevel level, const std::string& line) {
	if (!g_alwaysHolsterLog) return;
	gtLog("holster", level, line);
}

static bool alwaysHolsterWeaponInHand(Ped ped) {
	const Hash inHand = GET_WEAPON_AT_ATTACH_POINT(ped, 0);
	return inHand && inHand != joaat("WEAPON_UNARMED");
}

static int alwaysHolsterSwapTaskStatus(Ped ped) {
	return TASK::GET_SCRIPT_TASK_STATUS(ped, kHolsterSwapTaskHash, TRUE);
}

// act_bankrobbery01.c:10864 - busy means status 1 (running) or 0 (assigned).
static bool alwaysHolsterSwapTaskBusy(Ped ped) {
	const int status = alwaysHolsterSwapTaskStatus(ped);
	return status == 0 || status == 1;
}

// Name the gate that ate a press, and clear any latched intent, so a dropped
// press is never silent and can never be mistaken for a missing input.
static void alwaysHolsterReject(const char* why, bool sawPress) {
	if (sawPress) alwaysHolsterLog(GT_WARN, std::string("press rejected gate=") + why);
	if (!g_holsterPending) return;
	g_holsterPending = false;
	g_holsterDeferLogged = false;
	alwaysHolsterLog(GT_INFO, std::string("cancel pending reason=") + why);
}

static void requestAlwaysHolster(Ped ped) {
	const Hash inHand = GET_WEAPON_AT_ATTACH_POINT(ped, 0);
	// Rockstar's complete ordinary put-away sequence, verbatim from
	// act_bankrobbery01.c:22040-22042 (func_586). Issued exactly once for the
	// latched edge, and only with the swap-task slot free. There is no timeout,
	// completion poll, second attempt, or held-key repetition.
	HIDE_PED_WEAPONS(ped, 2, false);
	WEAPON::SET_CURRENT_PED_WEAPON(ped, joaat("WEAPON_UNARMED"),
		FALSE, 0, FALSE, FALSE);
	TASK::TASK_SWAP_WEAPON(ped, 0, 0, 0, 0);
	alwaysHolsterLog(GT_INFO, "issue stow inHand=" + std::to_string(inHand) +
		" taskStatusAfter=" + std::to_string(alwaysHolsterSwapTaskStatus(ped)));
}

static void updateAlwaysHolster(Ped ped, DWORD now, bool mission) {
	static const Hash kToggleHolster = joaat("INPUT_TOGGLE_HOLSTER");

	// ---- (1) DRAIN THE PHYSICAL EDGE UNCONDITIONALLY --------------------
	// This MUST be the first thing the function does and it must run on every
	// frame regardless of every gate below. GetAsyncKeyState's low bit is only
	// cleared by reading it; leaving it unread behind an early return is what
	// let a draw press resurface later as a phantom stow press (Defect A).
	// Kept out of a && expression on purpose - short-circuiting would skip the
	// read and reintroduce the bank.
	const bool tabBit = (GetAsyncKeyState(VK_TAB) & 1) != 0;
	DWORD foregroundPid = 0;
	const HWND foreground = GetForegroundWindow();
	if (foreground) GetWindowThreadProcessId(foreground, &foregroundPid);
	const bool physicalTab = tabBit && foregroundPid == GetCurrentProcessId();

	// ---- (2) SURVIVAL READBACK FOR THE PREVIOUS FRAME'S ISSUE -----------
	if (g_holsterVerify) {
		g_holsterVerify = false;
		if (ped) alwaysHolsterLog(GT_INFO, "survived taskStatus=" +
			std::to_string(alwaysHolsterSwapTaskStatus(ped)) +
			" inHand=" + std::to_string(GET_WEAPON_AT_ATTACH_POINT(ped, 0)));
	}

	// ---- (3) IDLE HEARTBEAT ---------------------------------------------
	// A silent log must mean "not running", never "nothing happened".
	if (now - g_holsterHeartbeatAt > 3000) {
		g_holsterHeartbeatAt = now;
		alwaysHolsterLog(GT_INFO, "heartbeat armed=" +
			std::to_string(ped && alwaysHolsterWeaponInHand(ped) ? 1 : 0) +
			" pending=" + std::to_string(g_holsterPending ? 1 : 0) +
			" taskStatus=" +
			std::to_string(ped ? alwaysHolsterSwapTaskStatus(ped) : -1));
	}

	// ---- (4) GATES -------------------------------------------------------
	// Every gate names itself in the log when it eats a real press, so a
	// rejection can never be mistaken for a missing input.
	const char* reject = nullptr;
	if (!g_alwaysHolster || !ped)                    reject = "disabled";
	else if (mission)                                reject = "mission";
	else if (PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE)) reject = "vehicle";
	else if (PED::IS_PED_ON_MOUNT(ped))              reject = "mount";
	if (reject) return alwaysHolsterReject(reject, physicalTab);

	// Empty-hand Tab remains vanilla draw. Kept as its own explicit return so
	// the draw path can never be swallowed by this module.
	const bool weaponInHand = alwaysHolsterWeaponInHand(ped);
	if (!weaponInHand) return alwaysHolsterReject("emptyHand", physicalTab);

	// Respect prone/binocular/other feature locks established earlier in frame
	// (movement.cpp:1081 and combat_inventory.cpp:706 both disable this control).
	if (!PAD::IS_CONTROL_ENABLED(0, kToggleHolster))
		return alwaysHolsterReject("controlLocked", physicalTab);

	// ---- (5) ACCEPT ONE PRESS -------------------------------------------
	// Suppress Rockstar's instant toggle first, every armed frame. The physical
	// VK_TAB edge was already captured above, so disabling cannot erase it and
	// Rockstar cannot win the same input cycle. The disabled-control edge keeps
	// remapped/controller bindings working through the normal action as well.
	PAD::DISABLE_CONTROL_ACTION(0, kToggleHolster, TRUE);
	const bool pressed = physicalTab ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, kToggleHolster) != 0;
	if (pressed) {
		if (g_holsterPending) {
			// Already own an unissued intent. Swallow the extra tap rather than
			// queue or reissue it - this is what stops repeated taps from
			// interrupting the transition they are waiting for.
			alwaysHolsterLog(GT_TRACE, "press coalesced (intent already pending)");
		} else {
			g_holsterPending = true;
			g_holsterDeferLogged = false;
			alwaysHolsterLog(GT_INFO, "press accepted physical=" +
				std::to_string(physicalTab ? 1 : 0) +
				" taskStatus=" + std::to_string(alwaysHolsterSwapTaskStatus(ped)));
		}
	}
	if (!g_holsterPending) return;

	// ---- (6) ISSUE WHEN THE SWAP-TASK SLOT IS FREE ----------------------
	// This is the deferral that replaces the old "press is dropped mid-draw"
	// behaviour. It is driven by task state, never by elapsed time, and it ends
	// the moment the slot frees - so the post-draw dead window the player
	// reported is gone without the sequence ever fighting a live transition.
	if (alwaysHolsterSwapTaskBusy(ped)) {
		if (!g_holsterDeferLogged) {
			g_holsterDeferLogged = true;
			alwaysHolsterLog(GT_INFO, "defer: swap task busy status=" +
				std::to_string(alwaysHolsterSwapTaskStatus(ped)));
		}
		return;
	}

	g_holsterPending = false;
	g_holsterDeferLogged = false;
	requestAlwaysHolster(ped);
	g_holsterVerify = true;
}
