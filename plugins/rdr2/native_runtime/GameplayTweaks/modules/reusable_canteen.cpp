// GitHub #88: make LEX_WATER_BOTTLE a persistent, multi-use canteen.
//
// This module is intentionally unregistered. The integration owner includes it
// after world_economy.cpp (for CASING_FEED) and calls updateReusableCanteen()
// once per frame. The catalog's authored consumable interaction remains in
// charge of the drink animation; this module replaces its fixed core effect
// with the configured exact result and restores the consumed inventory shell.

static const int kReusableCanteenCapacity = 5;

struct ReusableCanteenState {
	bool loaded = false;
	bool owned = false;
	bool interaction = false;
	bool consumptionHandled = false;
	bool restoreShellPending = false;
	int charges = 0;
	int beforeCount = 0;
	int beforeStaminaCore = 0;
	int lastCount = -1;
	int restorePerDrink = 25;
	DWORD interactionEndedAt = 0;
	DWORD nextConfigReadAt = 0;
	DWORD nextShellRetryAt = 0;
	DWORD acquisitionHintAt = 0;
	bool acquisitionHintShown = false;
};

static ReusableCanteenState g_reusableCanteen;

static std::string reusableCanteenStatePath() {
	return g_moduleDir + "\\GameplayTweaks.canteen.ini";
}

static void reusableCanteenLog(GtLogLevel level, const std::string& text) {
	gtLog("canteen", level, text);
}

static void saveReusableCanteenState() {
	const std::string path = reusableCanteenStatePath();
	char charges[16];
	sprintf_s(charges, "%d", (std::max)(0,
		(std::min)(kReusableCanteenCapacity, g_reusableCanteen.charges)));
	WritePrivateProfileStringA("State", "Charges", charges, path.c_str());
}

static void loadReusableCanteenState() {
	if (g_reusableCanteen.loaded) return;
	g_reusableCanteen.loaded = true;
	const Hash canteen = joaat("LEX_WATER_BOTTLE");
	const int count = INVENTORY_ITEM_COUNT(canteen);
	g_reusableCanteen.lastCount = count;
	g_reusableCanteen.owned = count > 0;

	const std::string path = reusableCanteenStatePath();
	const bool stateExists = GetFileAttributesA(path.c_str()) != INVALID_FILE_ATTRIBUTES;
	if (stateExists) {
		g_reusableCanteen.charges = (std::max)(0, (std::min)(
			kReusableCanteenCapacity,
			(int)GetPrivateProfileIntA("State", "Charges", kReusableCanteenCapacity,
				path.c_str())));
	} else {
		// Existing owners migrate full. A player without the item receives
		// nothing; their first real 0 -> 1 acquisition is initialized below.
		g_reusableCanteen.charges = count > 0 ? kReusableCanteenCapacity : 0;
		saveReusableCanteenState();
	}
	reusableCanteenLog(GT_INFO, "loaded count=" + std::to_string(count) +
		" charges=" + std::to_string(g_reusableCanteen.charges));
}

static void reloadReusableCanteenConfig(DWORD now) {
	if (now < g_reusableCanteen.nextConfigReadAt) return;
	g_reusableCanteen.nextConfigReadAt = now + 2000;
	g_reusableCanteen.restorePerDrink = (std::max)(0, (std::min)(100,
		(int)GetPrivateProfileIntA("CanteenDeveloper", "StaminaCorePerDrink", 25,
			g_iniPath.c_str())));
}

static void reusableCanteenFeed() {
	char text[96];
	if (g_reusableCanteen.charges > 0)
		sprintf_s(text, "Canteen: %d/%d drinks", g_reusableCanteen.charges,
			kReusableCanteenCapacity);
	else
		sprintf_s(text, "Canteen empty - refill at a water pump");
	// Keep the proven vanilla inventory icon. #88 must not reintroduce the
	// broken ersatz bottle icon that was previously removed.
	CASING_FEED(text, "INVENTORY_ITEMS", joaat("CONSUMABLE_WHISKEY_USED"));
}

static void reusableCanteenAcquisitionHint(DWORD now) {
	if (g_reusableCanteen.owned || g_reusableCanteen.acquisitionHintShown) return;
	if (!g_reusableCanteen.acquisitionHintAt) {
		// Wait until the save and HUD have settled; this is a one-shot tutorial,
		// not a repeated reminder or automated-comment-style spam loop.
		g_reusableCanteen.acquisitionHintAt = now + 5000;
		return;
	}
	if (now < g_reusableCanteen.acquisitionHintAt) return;
	g_reusableCanteen.acquisitionHintShown = true;
	CASING_FEED("Reusable Canteen: craft at any campfire with 1 Empty Bottle",
		"INVENTORY_ITEMS", joaat("CONSUMABLE_WHISKEY_USED"));
	reusableCanteenLog(GT_INFO, "acquisition-hint campfire empty-bottle=1");
}

static void handleReusableCanteenConsumption(Ped ped, int* managedStaminaCore) {
	if (g_reusableCanteen.consumptionHandled) return;
	g_reusableCanteen.consumptionHandled = true;
	const bool hadWater = g_reusableCanteen.charges > 0;
	if (hadWater) --g_reusableCanteen.charges;
	saveReusableCanteenState();

	const int target = hadWater
		? (std::min)(100, g_reusableCanteen.beforeStaminaCore +
			g_reusableCanteen.restorePerDrink)
		: g_reusableCanteen.beforeStaminaCore;
	SET_CORE(ped, 1, target);
	// CoreClock normally rejects a one-point native change. Synchronizing its
	// owner cache makes every configured value, including 0 and 1, exact.
	if (managedStaminaCore) *managedStaminaCore = target;

	const Hash canteen = joaat("LEX_WATER_BOTTLE");
	const int countBeforeRestore = INVENTORY_ITEM_COUNT(canteen);
	if (countBeforeRestore <= 0) {
		INVENTORY_ADD(canteen, 1);
		g_reusableCanteen.restoreShellPending = INVENTORY_ITEM_COUNT(canteen) <= 0;
		g_reusableCanteen.nextShellRetryAt = GetTickCount() + 250;
	}
	g_reusableCanteen.owned = true;
	g_reusableCanteen.lastCount = INVENTORY_ITEM_COUNT(canteen);
	reusableCanteenFeed();
	reusableCanteenLog(GT_INFO, std::string("drink water=") + (hadWater ? "1" : "0") +
		" coreBefore=" + std::to_string(g_reusableCanteen.beforeStaminaCore) +
		" coreAfter=" + std::to_string(target) +
		" charges=" + std::to_string(g_reusableCanteen.charges) +
		" shellCount=" + std::to_string(g_reusableCanteen.lastCount));
}

// Issue #89 calls this only after its pump refill scenario has completed.
// It changes canteen state only; drinking from the pump separately uses
// reusableCanteenStaminaCorePerDrink() and therefore shares the same setting.
static bool refillReusableCanteen() {
	loadReusableCanteenState();
	const int count = INVENTORY_ITEM_COUNT(joaat("LEX_WATER_BOTTLE"));
	if (count <= 0 || g_reusableCanteen.charges >= kReusableCanteenCapacity)
		return false;
	g_reusableCanteen.owned = true;
	g_reusableCanteen.charges = kReusableCanteenCapacity;
	saveReusableCanteenState();
	CASING_FEED("Canteen refilled: 5/5 drinks", "INVENTORY_ITEMS",
		joaat("CONSUMABLE_WHISKEY_USED"));
	reusableCanteenLog(GT_INFO, "refilled charges=5");
	return true;
}

static int reusableCanteenCharges() {
	loadReusableCanteenState();
	return g_reusableCanteen.charges;
}

static bool reusableCanteenOwned() {
	loadReusableCanteenState();
	return g_reusableCanteen.owned &&
		INVENTORY_ITEM_COUNT(joaat("LEX_WATER_BOTTLE")) > 0;
}

static int reusableCanteenCapacity() { return kReusableCanteenCapacity; }

static int reusableCanteenStaminaCorePerDrink() {
	loadReusableCanteenState();
	reloadReusableCanteenConfig(GetTickCount());
	return g_reusableCanteen.restorePerDrink;
}

static void updateReusableCanteen(Ped ped, DWORD now, bool blocked,
	int* managedStaminaCore) {
	loadReusableCanteenState();
	reloadReusableCanteenConfig(now);
	if (!ped || blocked) return;
	reusableCanteenAcquisitionHint(now);

	const Hash canteen = joaat("LEX_WATER_BOTTLE");
	int count = INVENTORY_ITEM_COUNT(canteen);
	const bool running = ITEM_INTERACTION_RUNNING(ped);
	const Hash item = running ? ITEM_INTERACTION_ITEM(ped) : 0;
	// Resolve a real inventory acquisition before interaction capture, so using
	// a freshly crafted canteen immediately cannot be mistaken for an empty one.
	if (!g_reusableCanteen.interaction && !g_reusableCanteen.restoreShellPending &&
		!g_reusableCanteen.owned && g_reusableCanteen.lastCount == 0 && count > 0) {
		g_reusableCanteen.owned = true;
		g_reusableCanteen.charges = kReusableCanteenCapacity;
		saveReusableCanteenState();
		CASING_FEED("Canteen filled: 5/5 - refill at any water pump", "INVENTORY_ITEMS",
			joaat("CONSUMABLE_WHISKEY_USED"));
		reusableCanteenLog(GT_INFO, "acquired charges=5");
	}

	if (!g_reusableCanteen.interaction && running && item == canteen) {
		g_reusableCanteen.interaction = true;
		g_reusableCanteen.consumptionHandled = false;
		g_reusableCanteen.beforeCount = count;
		g_reusableCanteen.beforeStaminaCore = GET_CORE(ped, 1);
		g_reusableCanteen.interactionEndedAt = 0;
		reusableCanteenLog(GT_INFO, "interaction-start count=" + std::to_string(count) +
			" core=" + std::to_string(g_reusableCanteen.beforeStaminaCore) +
			" charges=" + std::to_string(g_reusableCanteen.charges));
	}

	if (g_reusableCanteen.interaction) {
		if (!g_reusableCanteen.consumptionHandled &&
			count < g_reusableCanteen.beforeCount) {
			handleReusableCanteenConsumption(ped, managedStaminaCore);
			count = INVENTORY_ITEM_COUNT(canteen);
		}
		if (running && item == canteen) {
			g_reusableCanteen.interactionEndedAt = 0;
		} else if (!g_reusableCanteen.interactionEndedAt) {
			g_reusableCanteen.interactionEndedAt = now;
		} else if (now - g_reusableCanteen.interactionEndedAt >= 1200) {
			if (!g_reusableCanteen.consumptionHandled)
				reusableCanteenLog(GT_WARN, "interaction-ended-without-consumption");
			g_reusableCanteen.interaction = false;
			g_reusableCanteen.consumptionHandled = false;
			g_reusableCanteen.interactionEndedAt = 0;
		}
	}

	// Retry only a shell lost during a consumption observed in this process.
	// Never infer ownership from the INI and grant an item into another save.
	if (g_reusableCanteen.restoreShellPending && now >= g_reusableCanteen.nextShellRetryAt) {
		g_reusableCanteen.nextShellRetryAt = now + 500;
		if (INVENTORY_ITEM_COUNT(canteen) > 0 || INVENTORY_ADD(canteen, 1))
			g_reusableCanteen.restoreShellPending = INVENTORY_ITEM_COUNT(canteen) <= 0;
	}

	count = INVENTORY_ITEM_COUNT(canteen);
	if (!g_reusableCanteen.interaction && !g_reusableCanteen.restoreShellPending) {
		if (g_reusableCanteen.owned && count <= 0) {
			// Sold/discarded outside the drink interaction: do not resurrect it.
			g_reusableCanteen.owned = false;
		}
	}
	g_reusableCanteen.lastCount = count;
}
