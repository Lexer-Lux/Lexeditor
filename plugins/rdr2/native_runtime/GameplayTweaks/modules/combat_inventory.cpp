// GameplayTweaks feature module: Input bridges, combat roll, shared carry pools, radial ammo, binocular access, and projectile visibility.
// Included by script.cpp into the single ScriptHook translation unit.

static void binoLog(const char* msg) {
	gtLog("binoculars", GT_INFO, std::string(msg ? msg : ""));
}

// Trigger = hold RDR2's remappable cover control. This deliberately follows the
// game's binding rather than hard-coding Q/RB: tap still covers, hold raises
// binoculars after HoldMs.
static Hash coverControl() {
	// INPUT_COVER is the game's bindable cover action (Q on Lexer's keyboard
	// profile).  Reading the action, rather than a raw virtual key, follows any
	// future keyboard/controller rebind.
	return joaat("INPUT_COVER");
}

static bool coverBindingDown() {
	const Hash cover = coverControl();
	return PAD::IS_CONTROL_PRESSED(0, cover) || PAD::IS_DISABLED_CONTROL_PRESSED(0, cover) ||
		PAD::IS_CONTROL_PRESSED(2, cover) || PAD::IS_DISABLED_CONTROL_PRESSED(2, cover);
}

// Read the physical bindings independently from Rockstar's PAD action state.
// Q and controller RB are both Cover in Lexer's profile. This lets the native
// action pass through untouched for a tap and avoids disabled/synthetic PAD
// state feeding back into our hold detector.
static bool coverHoldInputDown() {
	const bool keyboardQ = (GetAsyncKeyState('Q') & 0x8000) != 0;
	return keyboardQ || padButtonDown(XINPUT_GAMEPAD_RIGHT_SHOULDER);
}

static void suppressCoverBinding() {
	const Hash cover = coverControl();
	DISABLE_CONTROL(0, cover);
	DISABLE_CONTROL(2, cover);
}

static void replayCoverTap() {
	const Hash cover = coverControl();
	SET_CONTROL_NORMAL(0, cover, 1.0f);
	SET_CONTROL_NORMAL(2, cover, 1.0f);
}

// Deprecated direct-input helpers retained temporarily for INI compatibility.
// The active binocular path uses coverBindingDown() above.
static bool holdKeyFDown() {
	return (GetAsyncKeyState(g_binocularsKey) & 0x8000) != 0;
}

static bool padBinocularButtonDown() {
	// Default D-pad Up: it does NOT move the camera. (RS/R3 recentres the camera,
	// which snapped the player ~180° before raising binos.) Configurable via
	// [Binoculars] PadButton.
	return padButtonDown((WORD)g_binocularPadMask);
}

static bool binocularHoldInputDown() {
	const bool key = (g_binocularsHoldMode != 1) && holdKeyFDown();
	const bool pad = (g_binocularsHoldMode != 0) && padBinocularButtonDown();
	return key || pad;
}

// Never yank the player out of an active aim into binoculars (that was the whole
// bug). Only blocks *starting* a raise; once we're already glassing, forced-aim
// reads as aiming, so the caller bypasses this while active/pressing.
static bool aimingAGun(Player player) {
	const Hash aim = joaat("INPUT_AIM");
	const bool aimInput =
		PAD::IS_CONTROL_PRESSED(0, aim) || PAD::IS_DISABLED_CONTROL_PRESSED(0, aim) ||
		PAD::IS_CONTROL_PRESSED(2, aim) || PAD::IS_DISABLED_CONTROL_PRESSED(2, aim) ||
		(GetAsyncKeyState(VK_RBUTTON) & 0x8000) != 0;
	// Camera state is not an input gate. The installed trace caught physical Q
	// holds that never became `held` after extended play even though RMB was up;
	// IS_AIM_CAM_ACTIVE can remain latched by Rockstar camera contexts just like
	// the broader target predicate did. Starting quick access is blocked only
	// while the player is physically holding Aim. Once started, the active path
	// owns its own forced-aim state.
	(void)player;
	return aimInput;
}

static bool controlJustPressedOrDisabled(Hash control) {
	return PAD::IS_CONTROL_JUST_PRESSED(0, control) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, control);
}

// STREAMING::DOES_ANIM_DICT_EXIST answers for a dictionary name WITHOUT
// streaming it. GET_PED_IS_DOING_COMBAT_ROLL is not in the SDK header - it comes
// from the native database (`python _downloads/grep_natives.py ROLL`) and is the
// engine's own CTaskCombatRoll predicate: proof the task exists at runtime, and
// the only way to see whether anything vanilla ever enters it.
static bool PED_IS_DOING_COMBAT_ROLL(Ped ped) {
	return invoke<BOOL>(0xC48A9EB0D499B3E5, ped) != 0;
}

static void combatRollLog(const std::string& line) {
	if (!g_combatRollTrace) return;
	gtLog("roll", GT_INFO, line);
}

#if 0 // Superseded by movement.cpp's confirmed authored #6 implementation.
// Every clip name the shipped strings contain, plus the mirrored (right-hand)
// spellings. Rockstar's dumps hold "COMBATROLL_FWD_P1_" as a bare prefix, so the
// signed variants are built by the engine at runtime and cannot be confirmed
// statically - they are probed like everything else and simply dropped if the
// dictionary has no such clip.
struct CombatRollClip { const char* name; float degrees; };
static const CombatRollClip kCombatRollClips[] = {
	{ "combatroll_fwd_p1_00",    0.0f },
	{ "combatroll_fwd_p1_45",   45.0f },
	{ "combatroll_fwd_p1_-45",  -45.0f },
	{ "combatroll_fwd_p1_90",   90.0f },
	{ "combatroll_fwd_p1_-90",  -90.0f },
	{ "combatroll_fwd_p1_135",  135.0f },
	{ "combatroll_fwd_p1_-135",-135.0f },
	{ "combatroll_bwd_p1_135",  135.0f },
	{ "combatroll_bwd_p1_-135",-135.0f },
	{ "combatroll_bwd_p1_180",  180.0f },
	{ "combatroll_bwd_p1_-90",  -90.0f },
	{ "combatroll_bwd_p1_90",   90.0f },
};
static std::vector<CombatRollClip> g_combatRollAvailable;

// Candidate dictionaries. STREAMING::DOES_ANIM_DICT_EXIST answers for a name
// without streaming anything, so the list is deliberately wide and the whole
// table is logged in one pass - per project rule, a probe should not need a
// relaunch per guess. `mech_weapons_core@base@` leads because that is where the
// dive sequence being replaced actually lives
// (mech_weapons_core@base@dive@{pistol,rifle,unarmed}@{launch,prone,getup}).
static const char* kCombatRollDictCandidates[] = {
	"mech_weapons_core@base@combat_roll",
	"mech_weapons_core@base@combatroll",
	"mech_weapons_core@base@roll",
	"mech_weapons_core@base@dive@roll",
	"mech_weapons_core@base@dive@pistol@roll",
	"mech_strafe@generic@roll@base",
	"mech_strafe@generic@roll",
	"mech_strafe@generic@combat_roll",
	"mech_strafe@generic@combatroll",
	"mech_strafe@generic@base",
	"mech_loco_m@generic@roll@base",
	"mech_loco_m@generic@combat_roll",
	"mech_jump@generic@roll",
	"mech_fall@generic@roll",
	"combat@roll",
	"combatroll",
};

// True once a dictionary is streamed in AND at least one combat-roll clip in it
// reports a duration. Called at most every 500 ms so a failed resolve does not
// spin the streamer every frame.
static bool combatRollResolve(DWORD now) {
	if (g_combatRollResolved) return true;
	if (g_combatRollResolveFailed) return false;
	if (now < g_combatRollNextProbeAt) return false;
	g_combatRollNextProbeAt = now + 500;

	std::vector<std::string> candidates;
	if (!g_combatRollDictOverride.empty()) candidates.push_back(g_combatRollDictOverride);
	for (const char* c : kCombatRollDictCandidates) candidates.push_back(c);

	// One pass: request everything, then accept the first that has streamed in
	// and contains a clip. Streaming takes a few frames, so this runs again on
	// the next probe tick until something lands or the attempts run out.
	static int attempts = 0;
	// One-off existence table for the whole list, so a failed resolve says which
	// names the game recognises at all rather than only that nothing worked.
	static bool loggedTable = false;
	if (!loggedTable) {
		loggedTable = true;
		std::string table;
		for (const std::string& d : candidates) {
			table += "\n    ";
			table += STREAMING::DOES_ANIM_DICT_EXIST(d.c_str()) ? "EXISTS  " : "missing ";
			table += d;
		}
		combatRollLog("candidate dictionary existence:" + table);
	}

	bool anyLoaded = false;
	for (const std::string& dict : candidates) {
		// Skip names the game does not know; requesting them only wastes probes.
		if (!STREAMING::DOES_ANIM_DICT_EXIST(dict.c_str())) continue;
		if (!STREAMING::HAS_ANIM_DICT_LOADED(dict.c_str())) {
			STREAMING::REQUEST_ANIM_DICT(dict.c_str());
			continue;
		}
		anyLoaded = true;
		std::vector<CombatRollClip> found;
		for (const CombatRollClip& clip : kCombatRollClips) {
			const float seconds = ENTITY::GET_ANIM_DURATION(dict.c_str(), clip.name);
			if (std::isfinite(seconds) && seconds > 0.05f) found.push_back(clip);
		}
		if (found.empty()) {
			combatRollLog("dict streamed but holds no combatroll clip: " + dict);
			continue;
		}
		g_combatRollDict = dict;
		g_combatRollAvailable = found;
		g_combatRollResolved = true;
		std::string names;
		for (const CombatRollClip& c : found) { names += " "; names += c.name; }
		combatRollLog("RESOLVED dict=" + dict + " clips:" + names);
		return true;
	}
	if (++attempts >= 40) {
		g_combatRollResolveFailed = true;
		std::string tried;
		for (const std::string& d : candidates) tried += "\n    " + d;
		combatRollLog(std::string("GAVE UP after 40 probes. anyDictStreamed=") +
			(anyLoaded ? "yes" : "no") + ". Tried:" + tried +
			"\n    Vanilla dive left intact. Set [CombatRoll] AnimDict= to a"
			" dictionary name to retry without restarting.");
	}
	return false;
}

// Nearest existing clip to the requested direction, in degrees where 0 is
// straight ahead, positive is left and 180 is straight back.
static const char* combatRollClipFor(float degrees) {
	const CombatRollClip* best = nullptr;
	float bestDelta = 1e9f;
	for (const CombatRollClip& clip : g_combatRollAvailable) {
		float delta = std::fabs(clip.degrees - degrees);
		if (delta > 180.0f) delta = 360.0f - delta;
		if (delta < bestDelta) { bestDelta = delta; best = &clip; }
	}
	return best ? best->name : nullptr;
}

static void updateCombatRoll(Player player, Ped ped, DWORD now, bool blocked) {
	// Carry an in-progress roll even while the trigger conditions no longer
	// hold, otherwise the roll stops travelling the moment aim is released.
	if (g_combatRollDriveUntil && ped) {
		if (now < g_combatRollDriveUntil) {
			const Vector3 v = ENTITY_VELOCITY(ped);
			SET_ENTITY_VELOCITY(ped, { g_combatRollDriveX, g_combatRollDriveY, v.z });
		} else {
			g_combatRollDriveUntil = 0;
		}
	}

	// Free evidence: if the engine ever puts Arthur into CTaskCombatRoll on its
	// own, the log says so and the dictionary hunt below becomes unnecessary -
	// the trigger that did it is what we should be feeding instead.
	if (ped && g_combatRollTrace) {
		static bool wasRolling = false;
		const bool rolling = PED_IS_DOING_COMBAT_ROLL(ped);
		if (rolling && !wasRolling) {
			combatRollLog(std::string("engine reports COMBAT ROLL active"
				" (ours=") + (g_combatRollDriveUntil ? "yes" : "NO") + ")");
		}
		wasRolling = rolling;
	}

	if (!g_combatRollEnabled || blocked || !ped || now < g_nextCombatRollAt) return;
	if (PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE) || PED::IS_PED_ON_MOUNT(ped) ||
		PED::IS_PED_FALLING(ped) || PED::IS_PED_RAGDOLL(ped) ||
		PED::IS_PED_CLIMBING(ped) || PED::IS_PED_SWIMMING(ped)) return;
	if (ENTITY::IS_ENTITY_IN_AIR(ped, 0)) return;
	if (!g_combatRollFirstPerson && CAM::IS_FIRST_PERSON_AIM_CAM_ACTIVE()) return;
	const Hash weapon = GET_CURRENT_WEAPON(ped);
	if (!weapon || weapon == joaat("WEAPON_UNARMED")) return;
	// The vanilla dive this replaces only happens with a gun up. Requiring aim
	// is also what keeps the roll clear of #169 climbing, which is driven by
	// direction + Jump and is never performed down the sights. Turning this off
	// is the only way the two inputs can ever contend.
	if (g_combatRollRequireAiming && !aimingAGun(player)) return;

	// Only take the Dive control away once a real roll can be played. Until
	// then Rockstar's dive stays available, so a failed resolve degrades to
	// vanilla behaviour instead of removing the move altogether.
	if (!combatRollResolve(now)) return;

	const Hash dive = joaat("INPUT_DIVE");
	PAD::DISABLE_CONTROL_ACTION(0, dive, TRUE);
	if (!controlJustPressedOrDisabled(dive)) return;

	// Direction comes from the movement axes, resolved against the camera the
	// same way ordinary movement is, then expressed relative to where Arthur is
	// facing so the chosen clip rolls the way the stick is pushed.
	const float moveX = CONTROL_AXIS(0, joaat("INPUT_MOVE_LR"));
	const float moveY = CONTROL_AXIS(0, joaat("INPUT_MOVE_UD"));
	float degrees = 0.0f;
	if (std::sqrt(moveX * moveX + moveY * moveY) > 0.25f) {
		// INPUT_MOVE_UD is negative when pushed forward. The camera's relative
		// heading converts a camera-space stick push into Arthur-space, which is
		// what the clip names are expressed in.
		const float stick = std::atan2(-moveX, -moveY) * 57.2957795f;
		degrees = stick + CAM::GET_GAMEPLAY_CAM_RELATIVE_HEADING();
		while (degrees > 180.0f) degrees -= 360.0f;
		while (degrees < -180.0f) degrees += 360.0f;
	}
	const char* clip = combatRollClipFor(degrees);
	if (!clip) return;

	const DWORD durationMs = (std::max)((DWORD)350, (std::min)((DWORD)1400,
		(DWORD)(ENTITY::GET_ANIM_DURATION(g_combatRollDict.c_str(), clip) * 1000.0f)));
	TASK::TASK_PLAY_ANIM(ped, g_combatRollDict.c_str(), clip,
		8.0f, -8.0f, (int)durationMs, 0x4000010, 0.0f, FALSE, 0, FALSE, "", FALSE);

	if (g_combatRollAssistSpeed > 0.01f) {
		const float rad = (ENTITY_HEADING(ped) + degrees) * 0.0174532925f;
		g_combatRollDriveX = -std::sin(rad) * g_combatRollAssistSpeed;
		g_combatRollDriveY = std::cos(rad) * g_combatRollAssistSpeed;
		g_combatRollDriveUntil = now + durationMs;
	}
	g_nextCombatRollAt = now + (DWORD)g_combatRollCooldownMs;
	{
		std::ostringstream s;
		s << "roll dir=" << degrees << "deg clip=" << clip
			<< " dur=" << durationMs << "ms assist=" << g_combatRollAssistSpeed;
		combatRollLog(s.str());
	}
}

#endif

static bool pedHasBinoKit(Ped ped, Hash kit) {
	if (!kit) return false;
	if (HAS_WEAPON(ped, kit)) return true;
	if (INVENTORY_ITEM_COUNT(kit) > 0) return true;
	return false;
}

static Hash resolveBinocularWeapon(Ped ped) {
	const Hash regular = joaat("WEAPON_KIT_BINOCULARS");
	if (pedHasBinoKit(ped, regular)) return regular;
	// Story free-roam kit wheel always has base binos; HAS_PED_GOT is often false
	// until first equip. Equip path GIVE_s then SET_CURRENT; timeout if refused.
	return regular;
}

static void equipBinoculars(Ped ped, Hash kit) {
	if (!ped || !kit) return;
	if (!HAS_WEAPON(ped, kit))
		GIVE_WEAPON(ped, kit);
	// #4: selecting a weapon non-immediately does not itself start the authored
	// presentation. Rockstar's shipped scripts pair that selection with
	// TASK_SWAP_WEAPON; omitting the task left the kit free to jump directly to
	// the hand. Request the same task once, and never clear/restart it while the
	// satchel retrieve is running.
	WEAPON::SET_CURRENT_PED_WEAPON(ped, kit, g_binocularsInstantEquip,
		0, FALSE, FALSE);
	if (!g_binocularsInstantEquip) {
		// Rockstar uses the second option enabled for swaps that coexist with
		// locomotion. The old 1,0 task froze Arthur throughout the retrieve.
		TASK::TASK_SWAP_WEAPON(ped, 1, 1, 0, 0);
		char taskBuf[96];
		sprintf_s(taskBuf, "satchel retrieve task requested status=%d",
			TASK::GET_SCRIPT_TASK_STATUS(ped, 716706914, TRUE));
		binoLog(taskBuf);
	}
}

// Rockstar's binocular thread registers BINO_PUT_AWAY in the shared prompt
// registry against INPUT_CAMERA_PUT_AWAY.  Disabling INPUT_FRONTEND_CANCEL did
// not affect that prompt because it is a different action.  Hide only the
// matching live registry entry while quick access owns the binoculars; do not
// touch other prompts or delete a prompt owned by Rockstar's thread.
static bool suppressNativeBinocularPutAwayPrompt() {
	CRASH_TRACE_STAGE("binocular: put-away prompt registry");
	// #176: never use _UIPROMPT_DISABLE_PROMPTS_THIS_FRAME here. The installed
	// log contained zero positive put-away handle observations, so the alleged
	// one-frame fallback ran for the complete binocular session and suppressed
	// Rockstar's animal Study/Info prompts too. Own only the exact registered
	// INPUT_CAMERA_PUT_AWAY handle when it exists, plus that one control action.
	const Hash putAway = joaat("INPUT_CAMERA_PUT_AWAY");
	static int lastSuppressedPrompt = 0;
	bool foundPutAwayPrompt = false;
	for (int i = 0; i < 48; ++i) {
		const int record = 1945938 + i * 18;
		// binoculars.c's shared prompt constructor stores its active/allocation
		// flags in f_1. f_0 is presentation context, so reading the base record
		// made this scan a no-op and allowed the newly registered prompt to flash.
		const auto* flagsSlot = getGlobalPtr(record + 1);
		if (!flagsSlot || (static_cast<int>(*flagsSlot) & 2) == 0) continue;
		const auto* actionSlot = getGlobalPtr(record + 4);
		if (!actionSlot || static_cast<Hash>(*actionSlot) != putAway) continue;
		const auto* promptSlot = getGlobalPtr(record + 3);
		if (!promptSlot) continue;
		const int prompt = static_cast<int>(*promptSlot);
		if (!HUD::_UIPROMPT_IS_VALID(prompt)) continue;
		foundPutAwayPrompt = true;
		const bool activeBefore = HUD::_UIPROMPT_IS_ACTIVE(prompt) != 0;
		HUD::_UIPROMPT_SET_VISIBLE(prompt, FALSE);
		HUD::_UIPROMPT_SET_ENABLED(prompt, FALSE);
		if (prompt != lastSuppressedPrompt) {
			lastSuppressedPrompt = prompt;
			char line[160] = {};
			sprintf_s(line,
				"put-away prompt suppressed handle=%d validAfter=%d activeBefore=%d activeAfter=%d",
				prompt, HUD::_UIPROMPT_IS_VALID(prompt) ? 1 : 0,
				activeBefore ? 1 : 0,
				HUD::_UIPROMPT_IS_ACTIVE(prompt) ? 1 : 0);
			binoLog(line);
		}
	}
	for (int group = 0; group < 3; ++group)
		PAD::DISABLE_CONTROL_ACTION(group, putAway, TRUE);
	return foundPutAwayPrompt;
}

// The looking-glass control context consumes ordinary locomotion even though
// the physical movement axes remain readable.  Restore only those two axes and
// replay their current values into the gameplay groups.  This leaves look,
// aim, zoom, retrieve/stow and every unrelated action under native ownership.
static void bridgeBinocularLocomotion(Player player) {
	if (!PLAYER_CONTROL_ON(player))
		PLAYER::SET_PLAYER_CONTROL(player, TRUE, 2048, FALSE);
	const Hash moveLR = joaat("INPUT_MOVE_LR");
	const Hash moveUD = joaat("INPUT_MOVE_UD");
	const float lr = CONTROL_AXIS(0, moveLR);
	const float ud = CONTROL_AXIS(0, moveUD);
	for (int group : { 0, 2 }) {
		PAD::ENABLE_CONTROL_ACTION(group, moveLR, TRUE);
		PAD::ENABLE_CONTROL_ACTION(group, moveUD, TRUE);
		SET_CONTROL_NORMAL(group, moveLR, lr);
		SET_CONTROL_NORMAL(group, moveUD, ud);
	}
}

// #4: hold past HoldMs → retrieve binos from the satchel and look; release
// returns them to the satchel and restores the previous weapon.
// ---- #70 Shared ammo-family caps -------------------------------------------
// Vanilla gives every ammo VARIANT its own capacity, so a "family" (all .307,
// say) can total far more than any one cap. Here each family gets ONE combined
// limit: we raise every variant's own ceiling to the shared number (so a single
// variant may fill the whole pool), then each tick sum the family and trim any
// overflow — taking it from whatever variant just went up, so the round you
// picked up last is the one that doesn't stick.
static void SET_MAX_AMMO_OVERRIDE(Player p, Hash ammoType, int amount) {
	invoke<Void>(0xE133C1EC5300F740, p, ammoType, amount);
}

struct AmmoFamily {
	const char* name;
	const int*  cap;              // ini-configured shared capacity (0 = leave vanilla)
	const char* types[12];        // ammo TYPE names (not the _AMMOBOX shop items)
};
static const AmmoFamily kAmmoFamilies[] = {
	// The overhaul has three cartridge calibres, not vanilla's weapon-class
	// buckets: pistols + varmint are .225, revolvers are .307, and repeaters +
	// rifles/snipers are .444. Shotgun shells and arrows remain separate pools.
	{ ".225", &g_ammoCap225, { "AMMO_PISTOL", "AMMO_PISTOL_HIGH_VELOCITY", "AMMO_PISTOL_EXPRESS",
		"AMMO_PISTOL_EXPRESS_EXPLOSIVE", "AMMO_PISTOL_SPLIT_POINT", "AMMO_22", nullptr } },
	{ ".307", &g_ammoCap307, { "AMMO_REVOLVER", "AMMO_REVOLVER_HIGH_VELOCITY", "AMMO_REVOLVER_EXPRESS",
		"AMMO_REVOLVER_EXPRESS_EXPLOSIVE", "AMMO_REVOLVER_SPLIT_POINT", nullptr } },
	{ ".444", &g_ammoCap444, { "AMMO_REPEATER", "AMMO_REPEATER_HIGH_VELOCITY", "AMMO_REPEATER_EXPRESS",
		"AMMO_REPEATER_EXPRESS_EXPLOSIVE", "AMMO_REPEATER_SPLIT_POINT",
		"AMMO_RIFLE", "AMMO_RIFLE_HIGH_VELOCITY", "AMMO_RIFLE_EXPRESS",
		"AMMO_RIFLE_EXPRESS_EXPLOSIVE", "AMMO_RIFLE_SPLIT_POINT", nullptr } },
	{ "Shotgun",  &g_ammoCapShotgun,  { "AMMO_SHOTGUN", "AMMO_SHOTGUN_SLUG", "AMMO_SHOTGUN_SLUG_EXPLOSIVE",
	                                    "AMMO_SHOTGUN_BUCKSHOT_INCENDIARY", nullptr } },
	{ "Arrow",    &g_ammoCapArrow,    { "AMMO_ARROW", "AMMO_ARROW_IMPROVED", "AMMO_ARROW_FIRE", "AMMO_ARROW_POISON",
	                                    "AMMO_ARROW_DYNAMITE", "AMMO_ARROW_SMALL_GAME", nullptr } },
};

// Shared ITEM pools (#2 herbs / food+drink). Membership from shared_item_caps.csv.
static void loadSharedItemPools() {
	g_sharedItemPools.clear();
	std::ifstream in(g_moduleDir + "\\shared_item_caps.csv");
	std::string line;
	while (std::getline(in, line)) {
		if (!line.empty() && line.back() == '\r') line.pop_back();
		if (line.empty() || line[0] == '#') continue;
		std::stringstream row(line); std::string pool, item;
		if (!readCsvField(row, pool) || !readCsvField(row, item)) continue;
		SharedItemPool* p = nullptr;
		for (SharedItemPool& e : g_sharedItemPools) if (e.pool == pool) { p = &e; break; }
		if (!p) { g_sharedItemPools.push_back({ pool, {} }); p = &g_sharedItemPools.back(); }
		p->items.push_back(item);
	}
}

static void updateSharedItemCaps(Ped ped) {
	if (!g_sharedItemCapsEnabled || !ped || g_sharedItemPools.empty()) return;
	// Remembered counts so we can take the overflow from whatever just increased —
	// the pickup that broke the cap is the one that does not stick.
	static std::vector<std::vector<int>> prev;
	static bool primed = false;
	if (prev.size() != g_sharedItemPools.size()) {
		prev.assign(g_sharedItemPools.size(), {}); primed = false;
	}
	for (size_t pi = 0; pi < g_sharedItemPools.size(); ++pi) {
		const SharedItemPool& pool = g_sharedItemPools[pi];
		int cap = 0;
		if (pool.pool == "Herbs") cap = g_itemCapHerbs;
		else if (pool.pool == "Food") cap = g_itemCapFood;
		if (cap <= 0) continue;                       // pool not configured: vanilla

		const size_t n = pool.items.size();
		std::vector<int> count(n, 0);
		int total = 0;
		for (size_t i = 0; i < n; ++i) {
			count[i] = INVENTORY_ITEM_COUNT(joaat(pool.items[i].c_str()));
			if (count[i] < 0) count[i] = 0;
			total += count[i];
		}
		if (prev[pi].size() != n) { prev[pi].assign(n, 0); primed = false; }

		int overflow = total - cap;
		if (overflow > 0 && primed) {
			for (int pass = 0; pass < 2 && overflow > 0; ++pass) {
				while (overflow > 0) {
					int pick = -1, best = 0;
					for (size_t i = 0; i < n; ++i) {
						if (count[i] <= 0) continue;
						int score = (pass == 0) ? (count[i] - prev[pi][i]) : count[i];
						if (score > best) { best = score; pick = (int)i; }
					}
					if (pick < 0) break;
					int take = count[pick] < overflow ? count[pick] : overflow;
					if (pass == 0 && take > best) take = best;
					if (take <= 0) break;
					// 1 = player inventory; REMOVE_REASON_DEFAULT is the ordinary path.
					invoke<BOOL>(0xB4158C8C9A3B5DCE, 1, joaat(pool.items[pick].c_str()),
						take, joaat("REMOVE_REASON_DEFAULT"));
					count[pick] -= take; overflow -= take;
				}
			}
		}
		prev[pi] = count;
	}
	primed = true;
}

static void updateSharedAmmoCaps(Player player, Ped ped) {
	if (!g_sharedAmmoEnabled || !ped) return;
	// Previous counts per family/variant, so we can tell what just increased.
	static int prev[_countof(kAmmoFamilies)][12] = {};
	static bool primed = false;

	for (size_t f = 0; f < _countof(kAmmoFamilies); ++f) {
		const AmmoFamily& fam = kAmmoFamilies[f];
		const int cap = *fam.cap;
		if (cap <= 0) continue;                      // family not configured: vanilla behaviour

		int count[12] = {}, total = 0, n = 0;
		for (; fam.types[n] && n < 12; ++n) {
			Hash t = joaat(fam.types[n]);
			// Let any single variant hold the whole shared pool.
			SET_MAX_AMMO_OVERRIDE(player, t, cap);
			count[n] = GET_PED_AMMO_BY_TYPE(ped, t);
			if (count[n] < 0) count[n] = 0;
			total += count[n];
		}

		int overflow = total - cap;
		if (overflow > 0 && primed) {
			// Trim what just went up first (the pickup/purchase that broke the cap),
			// largest gain first; then fall back to the biggest stacks.
			for (int pass = 0; pass < 2 && overflow > 0; ++pass) {
				while (overflow > 0) {
					int pick = -1, best = 0;
					for (int i = 0; i < n; ++i) {
						if (count[i] <= 0) continue;
						int score = (pass == 0) ? (count[i] - prev[f][i]) : count[i];
						if (score > best) { best = score; pick = i; }
					}
					if (pick < 0) break;
					int take = count[pick] < overflow ? count[pick] : overflow;
					if (pass == 0 && take > best) take = best;   // only claw back the gain
					if (take <= 0) break;
					count[pick] -= take; overflow -= take;
					SET_PED_AMMO_BY_TYPE(ped, joaat(fam.types[pick]), count[pick]);
				}
			}
		}
		for (int i = 0; i < n; ++i) prev[f][i] = count[i];
	}
	primed = true;
}

static void updateBinocularAccess(Player player, Ped ped, DWORD now, bool fadedOrDead) {
	static bool pressing = false;
	static bool active = false;
	static bool forcedAim = false;
	static bool loggedHold = false;
	static bool replayingTap = false;
	static DWORD pressStart = 0;
	static DWORD enterAt = 0;
	static DWORD stowUntil = 0;
	static bool stowing = false;
	// #116 RELEASE MID-DRAW. The authored satchel draw takes about a second, and
	// the old code stowed the moment the button came up - so a normal-length hold
	// equipped the binoculars and put them away again without them ever reaching
	// his eyes ("holding Q does nothing at all"). Once the raise is committed it
	// now always completes: releasing before the scope is up LATCHES the view up,
	// and the next press of the same button lowers it.
	static bool latched = false;
	static bool scopeWasUp = false;
	// The press that dismisses a latched view must not immediately count as the
	// start of a fresh raise. Ignore the button until it is physically released.
	static bool ignoreUntilRelease = false;
	static DWORD lastPulse = 0;
	static Hash previousWeapon = 0;
	static Hash binoWeapon = 0;
	// Lexeditor #181: native draw/stow timing remains engine-owned. The
	// ineffective animation-rate observer and its misleading control are retired.

	auto exitBinoMode = [&](const char* reason) {
		if (active || pressing)
			binoLog((std::string("exit ") + reason).c_str());
		if (forcedAim) {
			PLAYER::SET_PLAYER_FORCED_AIM(player, false, 0, -1, false);
			forcedAim = false;
		}
		if (active && ped) {
			Hash restore = previousWeapon;
			if (!restore || WEAPON::_IS_WEAPON_BINOCULARS(restore))
				restore = joaat("WEAPON_UNARMED");
			WEAPON::SET_CURRENT_PED_WEAPON(ped, restore, true, 0, false, false);
			// Never leave a weapon hidden, whatever path we exited through.
			SET_PED_CURRENT_WEAPON_VISIBLE(ped, TRUE, FALSE, FALSE, FALSE);
			if (!deadeyeOuterEmpty(player))
				SET_DEADEYE_DISABLED(player, false);
		}
		active = false;
		stowing = false;
		stowUntil = 0;
		latched = false;
		scopeWasUp = false;
		g_binocularsActive = false;
		g_binocularsModeEngaged = false;
		pressing = false;
		loggedHold = false;
		pressStart = 0;
		enterAt = 0;
		previousWeapon = 0;
		binoWeapon = 0;
	};

	static bool booted = false;
	if (!booted) {
		booted = true;
		// The unified log is truncated once per launch by gtLogInit, so this
		// subsystem no longer manages its own file lifetime.
		binoLog("session start");
		char buf[320];
		sprintf_s(buf, "ready enabled=%d holdMs=%d requireOwned=%d holdMode=%d key=0x%02X('%c') padMask=0x%04X",
			g_binocularsEnabled ? 1 : 0, g_binocularsHoldMs, g_binocularsRequireOwned ? 1 : 0,
			g_binocularsHoldMode, g_binocularsKey,
			(g_binocularsKey >= 32 && g_binocularsKey < 127) ? (char)g_binocularsKey : '?',
			(unsigned)g_binocularPadMask);
		binoLog(buf);
	}

	if (!g_binocularsEnabled) {
		if (active || pressing) exitBinoMode("disabled");
		g_binocularsActive = false;
		g_binocularsModeEngaged = false;
		return;
	}
	// Hard lock only: dead / fade. Do NOT gate on PLAYER_CONTROL_ON — that was
	// blocking free-roam detection with zero log lines past boot.
	if (!ped || fadedOrDead) {
		if (active || pressing) exitBinoMode("dead_or_faded");
		g_binocularsActive = false;
		g_binocularsModeEngaged = false;
		return;
	}

	// Read physical Q/RB and own Cover from the first down-frame. Letting the
	// native action run during the threshold window made Arthur start sprinting
	// toward cover before the binocular raise won. A short press is replayed to
	// Rockstar only on release; a hold is consumed entirely by binoculars.
	const bool bindingCover = coverBindingDown();
	const bool rawCoverFallback = coverHoldInputDown();
	bool input = bindingCover || rawCoverFallback;
	static bool previousPhysicalCover = false;
	if (input != previousPhysicalCover) {
		const Hash cover = coverControl();
		const bool enabled0 = PAD::IS_CONTROL_PRESSED(0, cover) != FALSE;
		const bool disabled0 = PAD::IS_DISABLED_CONTROL_PRESSED(0, cover) != FALSE;
		const bool enabled2 = PAD::IS_CONTROL_PRESSED(2, cover) != FALSE;
		const bool disabled2 = PAD::IS_DISABLED_CONTROL_PRESSED(2, cover) != FALSE;
		char edge[224];
		sprintf_s(edge,
			"cover input %s group0(enabled=%d disabled=%d) group2(enabled=%d disabled=%d) rawFallback=%d",
			input ? "down" : "up", enabled0 ? 1 : 0, disabled0 ? 1 : 0,
			enabled2 ? 1 : 0, disabled2 ? 1 : 0, rawCoverFallback ? 1 : 0);
		binoLog(edge);
		previousPhysicalCover = input;
	}
	if (replayingTap) {
		// SET_CONTROL_NORMAL is visible to the disabled-control reader on the
		// next tick. Ignore that synthetic edge or it recursively becomes a new
		// tap every frame.
		input = false;
		replayingTap = false;
	}
	// The weapon/item wheel is held-open via INPUT_OPEN_WHEEL_MENU, and RB (a
	// common bino PadButton) is ALSO the wheel's page-flip. If we ran the bino
	// logic while the wheel is open, our suppression would kill the wheel-open
	// control and slam the wheel shut. So: binos never engage while the wheel is
	// open — RB (or any button) keeps its in-wheel job.
	static const Hash kWheelMenu = joaat("INPUT_OPEN_WHEEL_MENU");
	const bool wheelOpen =
		PAD::IS_CONTROL_PRESSED(0, kWheelMenu) || PAD::IS_DISABLED_CONTROL_PRESSED(0, kWheelMenu) ||
		PAD::IS_CONTROL_PRESSED(2, kWheelMenu) || PAD::IS_DISABLED_CONTROL_PRESSED(2, kWheelMenu);
	if (ignoreUntilRelease) {
		if (!input && !stowing) ignoreUntilRelease = false;
		input = false;
	}
	// Block a fresh raise while aiming a gun; never re-gate once we're glassing
	// (forced-aim would read as aiming and immediately kick us out).
	const bool held = input && !wheelOpen && (active || pressing || !aimingAGun(player));
	if (held) suppressCoverBinding();

	// Whichever button raises binoculars, it ALSO has a native action (RS=Look
	// Behind, RB=Cover, LB=weapon wheel, F=melee/interact...). While binos are
	// being raised we swallow that whole set so the button can't fire its normal
	// action too. DISABLE_CONTROL on a hash that isn't bound is a no-op, so we can
	// safely cover every candidate. (Nothing LS/aim/zoom is touched.)
	auto suppressBinocularActions = []() {
		static const Hash kSuppress[] = {
			joaat("INPUT_LOOK_BEHIND"), joaat("INPUT_VEH_LOOK_BEHIND"),
			joaat("INPUT_COVER"), joaat("INPUT_COVER_TRANSITION"),
			joaat("INPUT_SELECT_WEAPON"), joaat("INPUT_OPEN_WHEEL_MENU"),
			joaat("INPUT_MELEE_ATTACK"), joaat("INPUT_ATTACK"), joaat("INPUT_MELEE_GRAPPLE"),
			joaat("INPUT_MELEE_GRAPPLE_CHOKE"), joaat("INPUT_RELOAD"),
			joaat("INPUT_INTERACT_LOCKON"), joaat("INPUT_CONTEXT"), joaat("INPUT_CONTEXT_SECONDARY"),
			joaat("INPUT_PICKUP"), // keyboard F = pickup; its reach anim floats the binos (probe-confirmed)
			joaat("INPUT_DYNAMIC_SCENARIO"), joaat("INPUT_WHISTLE"),
			joaat("INPUT_SPECIAL_ABILITY"), joaat("INPUT_TOGGLE_HOLSTER"),
			joaat("INPUT_OPEN_SATCHEL_MENU"), joaat("INPUT_OPEN_JOURNAL"),
			joaat("INPUT_SELECT_RADAR_MODE"), joaat("INPUT_MAP"),
			joaat("INPUT_CAMERA_PUT_AWAY"),
		};
		for (Hash h : kSuppress) { DISABLE_CONTROL(0, h); DISABLE_CONTROL(2, h); }
	};
	const bool controlOn = PLAYER_CONTROL_ON(player);

	if (stowing) {
		suppressBinocularActions();
		suppressNativeBinocularPutAwayPrompt();
		if (now < stowUntil) return;
		// The release branch already selected the destination and started the
		// swap task. Do not issue another weapon selection here: doing so at the
		// end of the window was the old instant-disappear regression.
		SET_PED_CURRENT_WEAPON_VISIBLE(ped, TRUE, FALSE, FALSE, FALSE);
		binoLog("native satchel stow window complete");
		stowing = false;
		stowUntil = 0;
		latched = false;
		scopeWasUp = false;
		pressing = false;
		loggedHold = false;
		pressStart = 0;
		enterAt = 0;
		previousWeapon = 0;
		binoWeapon = 0;
		return;
	}

	// Heartbeat every 3s so we know the tick is alive even when idle.
	if (now - lastPulse > 3000) {
		lastPulse = now;
		char buf[192];
		sprintf_s(buf, "pulse held=%d cover=%d binding=%d rawFallback=%d controlOn=%d active=%d pressing=%d deBar=%.1f",
			held ? 1 : 0, input ? 1 : 0, bindingCover ? 1 : 0, rawCoverFallback ? 1 : 0,
			controlOn ? 1 : 0, active ? 1 : 0, pressing ? 1 : 0,
			GET_DEADEYE_BAR(player));
		binoLog(buf);
	}

	if (active) {
		// #116 THE LATCH. While the raise is still playing, a release does not
		// cancel it - it converts the interaction to a latched view. From then on
		// the binoculars behave as a toggle: they stay up (and keep swallowing the
		// button's native action) until the button is pressed again. Once the
		// scope has actually been up, plain hold-to-look is restored.
		static bool latchRearmed = false;
		bool dismissed = false;
		if (!latched && !scopeWasUp && !held) {
			latched = true;
			latchRearmed = false;
			binoLog("released mid-draw; completing raise and latching view");
		}
		if (latched) {
			if (!held) latchRearmed = true;      // wait for the button to come up
			else if (latchRearmed) {             // ...then treat the next press as "lower"
				latched = false;
				dismissed = true;
				ignoreUntilRelease = true;
				binoLog("latched view dismissed by second press");
			}
		}
		const bool holding = (held || latched) && !dismissed;

		suppressBinocularActions();
		// Keep prompt ownership narrow. A missing registry handle means there is
		// nothing to mutate; it never authorizes a blanket prompt kill.
		suppressNativeBinocularPutAwayPrompt();
		bridgeBinocularLocomotion(player);
		if (invoke<BOOL>(0xB16223CB7DA965F0, player) != 0)
			SET_DEADEYE_DISABLED(player, true);

		if (!holding) {
			// Releasing aim lowers the binoculars. Then immediately select the
			// destination non-forced and start Rockstar's swap task: that task owns
			// the visible hand-to-satchel return. The old path waited first and only
			// changed weapon after the alleged animation window, so no stow task
			// existed during the wait and the prop could only blink away afterward.
			if (forcedAim) {
				// #116 THE CROUCHED 360 SPIN. Forced aim lets the CAMERA turn freely
				// while crouching pins his legs, so by the time you let go his body can
				// be pointing a long way from where he is looking. Releasing forced aim
				// makes the upper body unwind that gap on its own - and when the gap is
				// large it takes the long way round, which is the whole-torso spin over
				// a motionless lower half. Close the gap BEFORE releasing so there is
				// nothing left to unwind. Standing, the body already tracks the camera,
				// so the delta is tiny and this does nothing.
				// #116 AND IT FLIPPED HIM WHILE STANDING TOO. The realign below is a
				// hard SET_ENTITY_HEADING snap, which IS a flip if it ever fires with a
				// meaningful delta. Standing, there is no pinned lower half to unwind,
				// so the snap only ever creates the problem it was written to prevent.
				// Restrict it to the crouched/prone case it was actually diagnosed on.
				const bool lowerBodyPinned =
					PED::GET_PED_STEALTH_MOVEMENT(ped) != FALSE || customProneActive();
				const float camRelative = CAM::GET_GAMEPLAY_CAM_RELATIVE_HEADING();
				float delta = camRelative;
				while (delta > 180.0f) delta -= 360.0f;
				while (delta < -180.0f) delta += 360.0f;
				if (lowerBodyPinned && fabsf(delta) > 25.0f) {
					float aligned = ENTITY::GET_ENTITY_HEADING(ped) + delta;
					while (aligned < 0.0f) aligned += 360.0f;
					while (aligned >= 360.0f) aligned -= 360.0f;
					ENTITY::SET_ENTITY_HEADING(ped, aligned);
					CAM::SET_GAMEPLAY_CAM_RELATIVE_HEADING(0.0f, 1.0f);
					char spinBuf[96];
					sprintf_s(spinBuf, "stow heading realigned delta=%.1f", delta);
					binoLog(spinBuf);
				}
				PLAYER::SET_PLAYER_FORCED_AIM(player, false, 0, -1, false);
				forcedAim = false;
			}
			Hash restore = previousWeapon;
			if (!restore || WEAPON::_IS_WEAPON_BINOCULARS(restore))
				restore = joaat("WEAPON_UNARMED");
			if (g_binocularsInstantEquip) {
				WEAPON::SET_CURRENT_PED_WEAPON(ped, restore, TRUE, 0, FALSE, FALSE);
			} else {
				HIDE_PED_WEAPONS(ped, 2, false);
				WEAPON::SET_CURRENT_PED_WEAPON(ped, restore, FALSE, 0, FALSE, FALSE);
				TASK::TASK_SWAP_WEAPON(ped, 0, 1, 0, 0);
			}
			active = false;
			g_binocularsActive = false;
			g_binocularsModeEngaged = false;
			stowing = true;
			stowUntil = now + (DWORD)g_binocularsStowMs;
			binoLog("release; native satchel stow task requested");
			return;
		}

		// Do not clear tasks or hide the weapon here. Clearing the secondary task
		// cancels both Rockstar's satchel transition and the binocular scope task;
		// hiding the current weapon also hides the binoculars themselves.

		Hash current = GET_CURRENT_WEAPON(ped);
		const bool isBino = binoWeapon && (current == binoWeapon || WEAPON::_IS_WEAPON_BINOCULARS(current));
		if (!isBino) {
			if (now - enterAt > 2000) {
				char buf[128];
				sprintf_s(buf, "equip timeout current=0x%08X want=0x%08X", (unsigned)current, (unsigned)binoWeapon);
				binoLog(buf);
				exitBinoMode("equip_timeout");
				return;
			}
		} else {
			// Let the native satchel draw play before entering the scope. Forcing aim
			// on the equip frame was what made the prop teleport into Arthur's hands.
			// Status 0/1 is Rockstar's queued/running task test in shipped scripts;
			// the timer is only a minimum and may not cut the swap task short.
			CRASH_TRACE_STAGE("binocular: draw task status");
			const int swapStatus =
				TASK::GET_SCRIPT_TASK_STATUS(ped, 716706914, TRUE);
			const bool swapRunning = swapStatus == 0 || swapStatus == 1;
			// One camera readback per owned frame. A forced-aim request issued below
			// cannot become ready until a later frame confirms this predicate.
			CRASH_TRACE_STAGE("binocular: optics readiness");
			const bool opticsReady = CAM::IS_FIRST_PERSON_AIM_CAM_ACTIVE();
			if (!swapRunning && !opticsReady) {
				CRASH_TRACE_STAGE("binocular: request forced aim");
				PLAYER::SET_PLAYER_FORCED_AIM(player, true, 0, -1, false);
				forcedAim = true;
			}
			CRASH_TRACE_STAGE("binocular: draw postcondition");
			// binoculars.c func_21 is the authoritative state-4 -> state-5 gate:
			// setter intent is not optics readiness.
			g_binocularsActive = isBino && forcedAim && opticsReady;
		}
		// #113(b) THE STUDY METER FILLED WHILE HE WAS STILL PULLING THEM OUT.
		// This armed the recon scanner the instant the binocular KIT became the
		// equipped weapon - which happens on the first frame of the satchel draw,
		// long before he is looking through anything. So the scan ran, picked a
		// target and started filling Study during the draw animation. Require the
		// draw to have finished and the scope to actually be up.
		if (!isBino) g_binocularsActive = false;
		// Once the scope has genuinely been up, hold-to-look is back in charge:
		// a release from here stows, it does not latch.
		if (g_binocularsActive) {
			scopeWasUp = true;
		}
		return;
	}

	if (held) {
		if (!pressing) {
			pressing = true;
			pressStart = now;
			loggedHold = false;
			return;
		}
		const DWORD heldMs = now - pressStart;
		if (!loggedHold && heldMs >= 40) {
			loggedHold = true;
			Hash kit = resolveBinocularWeapon(ped);
			char buf[256];
			sprintf_s(buf, "HOLD cover=1 controlOn=%d kit=0x%08X hasWpn=%d inv=%d heldMs=%u",
				controlOn ? 1 : 0, (unsigned)kit,
				HAS_WEAPON(ped, kit) ? 1 : 0, INVENTORY_ITEM_COUNT(kit), (unsigned)heldMs);
			binoLog(buf);
		}
		if (heldMs < (DWORD)g_binocularsHoldMs) {
			return;
		}
		// THIS is why holding Q while prone put him into binoculars STANDING: the
		// clear below ran the moment the hold threshold passed, dropping the crawl
		// task and snapping him to his feet before the prone system ever saw the
		// request. Ask prone to stand him up through its own authored transition
		// first, and only engage once it reports he is off the ground.
		if (proneRequestStandForNativeAction(ped, "binoculars")) return;
		g_binocularsModeEngaged = true;
		// Own prompt presentation on the very frame that equips the kit. The
		// Rockstar binocular thread may register its put-away prompt later in
		// this same frame, before a registry handle exists for us to scan.
		suppressNativeBinocularPutAwayPrompt();
		if (g_proneTaskOwnsSkeleton) {
			TASK::CLEAR_PED_TASKS(ped, true, false);
			g_proneTaskOwnsSkeleton = false;
		}

		// A quick Q tap has already remained fully native. Once the configured
		// hold threshold is crossed, swallow the continuing cover input and equip
		// binos. Clear only an actual cover transition at that point.
		suppressBinocularActions();

		if (!controlOn) {
			// Menus / cinematic: don't equip; keep waiting for control or release.
			return;
		}

		Hash kit = resolveBinocularWeapon(ped);
		previousWeapon = GET_CURRENT_WEAPON(ped);
		if (!previousWeapon || WEAPON::_IS_WEAPON_BINOCULARS(previousWeapon))
			previousWeapon = joaat("WEAPON_UNARMED");
		binoWeapon = kit;

		if (invoke<BOOL>(0xB16223CB7DA965F0, player) != 0)
			SET_DEADEYE_DISABLED(player, true);

		// The first physical frame may already have begun a cover transition
		// before this script's control suppression runs. Cancel that task once;
		// per-frame task clearing would also destroy the binocular scope task.
		if (PED::IS_PED_IN_COVER(ped, false, false) || PED::IS_PED_GOING_INTO_COVER(ped))
			TASK::CLEAR_PED_TASKS(ped, true, false);
		equipBinoculars(ped, binoWeapon);
		// Forced aim begins after the native draw in the active branch above.
		forcedAim = false;
		active = true;
		latched = false;
		scopeWasUp = false;
		g_binocularsActive = false; // waits for the actual scope camera above
		enterAt = now;
		{
			char buf[160];
			sprintf_s(buf, "enter binos kit=0x%08X prev=0x%08X via held cover",
				(unsigned)binoWeapon, (unsigned)previousWeapon);
			binoLog(buf);
		}
		return;
	}

	if (pressing && !active) {
		const DWORD heldMs = now - pressStart;
		if (heldMs >= (DWORD)g_binocularsHoldMs && loggedHold) {
			binoLog("released before binocular equip");
		} else if (heldMs < (DWORD)g_binocularsHoldMs) {
			// The physical press was suppressed from its first frame, so this is the
			// only native Cover pulse. It cannot start a cover run before we know the
			// press was actually a tap.
			replayCoverTap();
			replayingTap = true;
			binoLog("short cover tap replayed on release");
		}
	}
	pressing = false;
	loggedHold = false;
	pressStart = 0;
	g_binocularsActive = false;
	g_binocularsModeEngaged = false;
}
