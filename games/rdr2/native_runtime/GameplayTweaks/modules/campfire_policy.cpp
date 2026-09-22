// GameplayTweaks feature module: persistent campsite and camp-kit policy (#1).
//
// Disabling KIT_CAMP merely leaves a grey radial entry.  The requested result
// is absence, so outside missions we bank the player's two camp-kit records in
// a small persistent sidecar and remove them from the live inventory.  They are
// restored on mission entry and Story owns them until the mission ends.

struct CampKitPolicyState {
	bool loaded = false;
	bool wasMission = false;
	int bankedFull = 0;
	int bankedSimple = 0;
	DWORD nextEnforcement = 0;
	DWORD nextFailureLog = 0;
};

static CampKitPolicyState g_campKitPolicy;

static std::string campKitPolicyStatePath() {
	return g_moduleDir + "\\camp-kit-policy.state";
}

static void saveCampKitPolicyState() {
	std::ofstream out(campKitPolicyStatePath(), std::ios::trunc);
	if (out) out << g_campKitPolicy.bankedFull << ","
		<< g_campKitPolicy.bankedSimple << "\n";
}

static void campKitPolicyLog(GtLogLevel level, const char* action, Hash item,
	int before, int after, int banked, bool nativeResult) {
	std::ostringstream out;
	out << action << " item=0x" << std::hex
		<< (unsigned)item << std::dec << " before=" << before
		<< " after=" << after << " banked=" << banked
		<< " native=" << (nativeResult ? 1 : 0);
	gtLog("campfire", level, out.str());
}

static void loadCampKitPolicyState() {
	if (g_campKitPolicy.loaded) return;
	g_campKitPolicy.loaded = true;
	std::ifstream in(campKitPolicyStatePath());
	char comma = 0;
	int full = 0, simple = 0;
	if (in >> full >> comma >> simple && comma == ',') {
		g_campKitPolicy.bankedFull = (std::max)(0, full);
		g_campKitPolicy.bankedSimple = (std::max)(0, simple);
	}
	gtLog("campfire", GT_INFO, "session-start bankedFull=" +
		std::to_string(g_campKitPolicy.bankedFull) + " bankedSimple=" +
		std::to_string(g_campKitPolicy.bankedSimple));
}

static void bankCampKit(Hash item, int* banked) {
	const int before = (std::max)(0, INVENTORY_ITEM_COUNT(item));
	if (before <= 0) return;
	*banked = (std::max)(*banked, before);
	const bool removed = INVENTORY_REMOVE_WITH_REASON(item, before,
		joaat("REMOVE_REASON_DUPLICATE"));
	const int after = (std::max)(0, INVENTORY_ITEM_COUNT(item));
	if (after == 0) saveCampKitPolicyState();
	campKitPolicyLog(after == 0 ? GT_INFO : GT_WARN,
		after == 0 ? "banked" : "bank-failed", item,
		before, after, *banked, removed);
}

static void restoreCampKit(Hash item, int* banked) {
	if (*banked <= 0) return;
	// This is the only path that clears an old disabled state. It is called only
	// while entering/being in a mission with a genuinely banked record, never as
	// a free-roam heartbeat. Unconditionally enabling both hashes every 500 ms
	// kept mutating Rockstar's shared inventory layer after the kits were already
	// absent and interfered with shop-script ownership (#114).
	INVENTORY_ENABLE_ITEM(item);
	const int before = (std::max)(0, INVENTORY_ITEM_COUNT(item));
	const int missing = (std::max)(0, *banked - before);
	const bool added = missing == 0 || INVENTORY_ADD(item, missing);
	const int after = (std::max)(0, INVENTORY_ITEM_COUNT(item));
	if (after >= *banked) {
		*banked = 0;
		saveCampKitPolicyState();
	}
	campKitPolicyLog(*banked == 0 ? GT_INFO : GT_WARN,
		*banked == 0 ? "restored" : "restore-failed",
		item, before, after, *banked, added);
}

static void updateCampfirePolicy(bool mission) {
	loadCampKitPolicyState();
	const DWORD now = GetTickCount();
	const Hash fullCamp = joaat("KIT_CAMP");
	const Hash simpleCamp = joaat("KIT_CAMP_SIMPLE");

	if (mission) {
		// Restore only records that are genuinely banked. Retry failures at the
		// bounded cadence instead of writing availability every frame.
		if (!g_campKitPolicy.wasMission || now >= g_campKitPolicy.nextEnforcement) {
			restoreCampKit(fullCamp, &g_campKitPolicy.bankedFull);
			restoreCampKit(simpleCamp, &g_campKitPolicy.bankedSimple);
			g_campKitPolicy.nextEnforcement = now + 500;
		}
	} else if (g_campKitPolicy.wasMission || now >= g_campKitPolicy.nextEnforcement) {
		// Removal, not INVENTORY_DISABLE_ITEM, makes the camp item absent from the
		// radial. The count checks are read-only when both records are already
		// absent; periodic enforcement mutates only if progression actually grants
		// a full/simple variant while free-roaming.
		bankCampKit(fullCamp, &g_campKitPolicy.bankedFull);
		bankCampKit(simpleCamp, &g_campKitPolicy.bankedSimple);
		g_campKitPolicy.nextEnforcement = now + 500;
	}

	g_campKitPolicy.wasMission = mission;
}

static void protectAuthoredCampTeardown(bool ownedCampActive, DWORD now) {
	static DWORD nextPromptReadback = 0;
	static DWORD nextPromptHeartbeat = 0;
	static int ambientSlot = -1;
	static int ambientPrompt = 0;
	static int ambientOwnerThread = 0;
	static int seatedSlot = -1;
	static int seatedPrompt = 0;
	static int seatedOwnerThread = 0;
	const Hash contextBack = joaat("INPUT_CONTEXT_B");
	if (!ownedCampActive) {
		nextPromptReadback = 0;
		nextPromptHeartbeat = 0;
		ambientSlot = -1;
		ambientPrompt = 0;
		ambientOwnerThread = 0;
		seatedSlot = -1;
		seatedPrompt = 0;
		seatedOwnerThread = 0;
		return;
	}

	// The exact ambient teardown constructor is player_camp.c:1342. Through
	// func_158 -> func_395 it produces a registry record with f_0=0, f_2=1,
	// f_4=INPUT_CONTEXT_B, and f_16 owned by the player_camp thread. Matching all
	// four primary-source fields avoids hiding the other B prompts in that script.
	// Globals are scanned each frame only until the prompt is acquired, so a newly
	// created prompt cannot render first. Story may rewrite prompt visibility and
	// enabled state on its own update, so the exact cached handle must be enforced
	// every protected frame. Only the readback/log is rate-limited to 4 Hz.
	// A prompt handle can remain valid after Rockstar frees and reuses its
	// registry slot. Revalidate every cached handle against the exact record
	// before writing to it. This prevents a stale campsite cache from hiding an
	// unrelated prompt that later receives the same native handle.
	const auto cacheStillOwnsExactPrompt = [&](int slot, int prompt,
		int ownerThread, int priority, int transport) {
		if (slot < 1 || slot >= 48 || !prompt || !ownerThread)
			return false;
		const int record = 1945938 + slot * 18;
		return (static_cast<int>(*getGlobalPtr(record + 1)) & 2) != 0 &&
			static_cast<int>(*getGlobalPtr(record)) == priority &&
			static_cast<int>(*getGlobalPtr(record + 2)) == transport &&
			static_cast<int>(*getGlobalPtr(record + 3)) == prompt &&
			static_cast<Hash>(*getGlobalPtr(record + 4)) == contextBack &&
			static_cast<int>(*getGlobalPtr(record + 16)) == ownerThread &&
			HUD::_UIPROMPT_IS_VALID(prompt);
	};
	const auto invalidateStaleCache = [&](int& slot, int& prompt,
		int& ownerThread, int priority, int transport, const char* kind) {
		if (slot < 0 && !prompt && !ownerThread) return;
		if (cacheStillOwnsExactPrompt(slot, prompt, ownerThread,
			priority, transport)) return;
		gtLog("campfire", GT_INFO, std::string(kind) +
			" teardown prompt cache released slot=" + std::to_string(slot) +
			" handle=" + std::to_string(prompt));
		slot = -1;
		prompt = 0;
		ownerThread = 0;
	};
	invalidateStaleCache(ambientSlot, ambientPrompt, ambientOwnerThread,
		0, 1, "ambient");
	invalidateStaleCache(seatedSlot, seatedPrompt, seatedOwnerThread,
		2, 0, "seated-hold");

		if (ambientSlot < 0 || ambientPrompt == 0 || seatedSlot < 0 ||
		seatedPrompt == 0) for (int i = 1; i < 48; ++i) {
		const int record = 1945938 + i * 18;
		const int flags = static_cast<int>(*getGlobalPtr(record + 1));
		const int priority = static_cast<int>(*getGlobalPtr(record));
		const int transport = static_cast<int>(*getGlobalPtr(record + 2));
		const bool ambientTeardown = priority == 0 && transport == 1;
		const bool seatedHoldTeardown = priority == 2 && transport == 0;
		if ((flags & 2) == 0 || (!ambientTeardown && !seatedHoldTeardown) ||
			static_cast<Hash>(*getGlobalPtr(record + 4)) != contextBack)
			continue;
		// Validate the prompt first: an invalid handle means this registry slot
		// is stale, and its thread id is not worth asking the engine about.
		const int prompt = static_cast<int>(*getGlobalPtr(record + 3));
		if (!prompt || !HUD::_UIPROMPT_IS_VALID(prompt) ||
			!HUD::_UIPROMPT_HAS_HOLD_MODE(prompt))
			continue;
		const int ownerThread = static_cast<int>(*getGlobalPtr(record + 16));
		if (!ownerThread ||
			invoke<Hash>(0x724CB89D35B283D0, ownerThread) != joaat("player_camp"))
			continue;
		int* slot = ambientTeardown ? &ambientSlot : &seatedSlot;
		int* handle = ambientTeardown ? &ambientPrompt : &seatedPrompt;
		int* owner = ambientTeardown ? &ambientOwnerThread : &seatedOwnerThread;
		if (*slot >= 0 && *handle != 0) continue;
		*slot = i;
		*handle = prompt;
		*owner = ownerThread;
		gtLog("campfire", GT_INFO, std::string(ambientTeardown ?
			"ambient" : "seated-hold") + " teardown prompt acquired slot=" +
			std::to_string(i) + " handle=" + std::to_string(prompt) +
			" ownerThread=" + std::to_string(ownerThread));
	}
	const auto suppressExactPrompt = [&](int prompt, const char* kind) {
		if (!prompt) return;
		// Cache ownership was checked above in this same update. There is no
		// second registry/native scan between validation and these two writes.
		HUD::_UIPROMPT_SET_VISIBLE(prompt, FALSE);
		HUD::_UIPROMPT_SET_ENABLED(prompt, FALSE);
		if ((!nextPromptReadback || now >= nextPromptReadback) &&
			HUD::_UIPROMPT_IS_ENABLED(prompt))
			gtLog("campfire", GT_ERROR,
				std::string(kind) + " teardown prompt disable readback=enabled");
	};
	// #114. These two calls disable cached prompt HANDLES every frame. RDR2
	// recycles prompt handles, so once a cached handle is reused by another
	// prompt - a shopkeeper's, for instance - this silently disables that
	// prompt instead, forever, which matches the reported "no prompts at all"
	// and the greyed RMB glyph. Default OFF until the ownership check is proven
	// to survive handle recycling.
	if (readB("CampfirePolicy", "SuppressTeardownPrompts", false)) {
		suppressExactPrompt(ambientPrompt, "ambient");
		suppressExactPrompt(seatedPrompt, "seated-hold");
	}
	if (!nextPromptReadback || now >= nextPromptReadback)
		nextPromptReadback = now + 250;
	if (!nextPromptHeartbeat || now >= nextPromptHeartbeat) {
		const auto promptState = [](int slot, int prompt) {
			if (slot < 0 || !prompt) return std::string("missing");
			return std::string("slot=") + std::to_string(slot) +
				" handle=" + std::to_string(prompt) +
				" valid=" + std::to_string(HUD::_UIPROMPT_IS_VALID(prompt) ? 1 : 0) +
				" enabled=" + std::to_string(HUD::_UIPROMPT_IS_ENABLED(prompt) ? 1 : 0) +
				" active=" + std::to_string(HUD::_UIPROMPT_IS_ACTIVE(prompt) ? 1 : 0);
		};
		gtLog("campfire", GT_INFO,
			"teardown guard heartbeat ambient={" +
			promptState(ambientSlot, ambientPrompt) +
			"} seated-hold={" + promptState(seatedSlot, seatedPrompt) + "}");
		nextPromptHeartbeat = now + 2000;
	}

	// Never suppress INPUT_CONTEXT_B itself. Rockstar deliberately shares that
	// action with the short Leave prompt. Hide the two exact long-hold handles;
	// the short Leave record has priority=1 and is never acquired here.
}
