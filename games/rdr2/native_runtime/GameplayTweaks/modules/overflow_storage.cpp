// GitHub #26: DS3-style overflow storage transaction prototype.
//
// The catalog patch raises only the engine-facing base satchel contribution.
// This module subtracts that exact lift from Rockstar's live role-max readback,
// so Arthur's authored active cap and current satchel upgrade still apply.
// It moves only a verified amount above that cap and persists only that amount.

struct OverflowPrototypeItem {
	std::string name;
	Hash hash = 0;
	int authoredBase = 0;
	int liftedBase = 0;
	int reserve = 0;
	int lastCount = 0;
	int lastEngineCap = 0;
	int lastActiveCap = 0;
	bool capReadbackReady = false;
	bool primed = false;
};

static OverflowPrototypeItem g_overflowPrototype;
static bool g_overflowLoaded = false;
static bool g_overflowEnabled = false;
static std::string g_overflowStoragePath;
static DWORD g_overflowNextPollAt = 0;
static DWORD g_overflowLastHeartbeatAt = 0;
static bool g_overflowUiOpen = false;
static bool g_overflowUiThreadsPaused = false;
static bool g_overflowUiInputArmed = false;
static bool g_overflowUiClosePending = false;
static bool g_overflowUiF7WasDown = false;
static int g_overflowUiSelection = 0; // 0 withdraw, 1 deposit
static DWORD g_overflowUiNextInputAt = 0;
static std::string g_overflowUiNotice;
static DWORD g_overflowUiNoticeUntil = 0;
static int g_overflowLastCatalogBaseReadback = INT_MIN;

static std::string overflowTrim(const std::string& input) {
	size_t first = 0;
	while (first < input.size() && isspace(static_cast<unsigned char>(input[first]))) ++first;
	size_t last = input.size();
	while (last > first && isspace(static_cast<unsigned char>(input[last - 1]))) --last;
	return input.substr(first, last - first);
}

static bool overflowParsePositive(const std::string& text, int& output) {
	char* end = nullptr;
	const long value = strtol(text.c_str(), &end, 10);
	if (end == text.c_str() || *end != '\0' || value <= 0 || value > 9999) return false;
	output = static_cast<int>(value);
	return true;
}

static bool overflowLoadPrototypeData() {
	std::ifstream input(g_moduleDir + "\\overflow_storage_items.csv");
	if (!input) {
		gtLog("overflow-storage", GT_ERROR, "data-open-failed");
		return false;
	}
	std::string line;
	int rows = 0;
	while (std::getline(input, line)) {
		line = overflowTrim(line);
		if (line.empty() || line[0] == '#') continue;
		std::stringstream stream(line);
		std::string item;
		std::string authored;
		std::string lifted;
		std::string extra;
		if (!std::getline(stream, item, ',') || !std::getline(stream, authored, ',') ||
			!std::getline(stream, lifted, ',') || std::getline(stream, extra, ',')) {
			gtLog("overflow-storage", GT_ERROR, "data-row-invalid");
			return false;
		}
		item = overflowTrim(item);
		authored = overflowTrim(authored);
		lifted = overflowTrim(lifted);
		int authoredBase = 0;
		int liftedBase = 0;
		if (item.empty() || !overflowParsePositive(authored, authoredBase) ||
			!overflowParsePositive(lifted, liftedBase) || liftedBase <= authoredBase) {
			gtLog("overflow-storage", GT_ERROR, "data-values-invalid");
			return false;
		}
		if (++rows != 1) {
			gtLog("overflow-storage", GT_ERROR, "prototype-row-count-invalid");
			return false;
		}
		g_overflowPrototype.name = item;
		g_overflowPrototype.hash = joaat(item.c_str());
		g_overflowPrototype.authoredBase = authoredBase;
		g_overflowPrototype.liftedBase = liftedBase;
	}
	return rows == 1;
}

static int overflowReadReserve(const OverflowPrototypeItem& item) {
	return (std::max)(0, (int)GetPrivateProfileIntA("Reserve",
		item.name.c_str(), 0, g_overflowStoragePath.c_str()));
}

static bool overflowWriteReserve(const OverflowPrototypeItem& item, int value) {
	char text[32];
	sprintf_s(text, "%d", (std::max)(0, value));
	return WritePrivateProfileStringA("Reserve", item.name.c_str(), text,
		g_overflowStoragePath.c_str()) != 0;
}

static int overflowEngineBase(const OverflowPrototypeItem& item) {
	// _GET_ITEM_SLOT_MAX_COUNT(item, SLOTID_SATCHEL). This readback proves that
	// the issue #26 catalog lift is actually active before any inventory write.
	return invoke<int>(0xE80E50BEE276A54A, item.hash, joaat("SLOTID_SATCHEL"));
}

static int overflowEngineCap(const OverflowPrototypeItem& item) {
	// Story inventory 1 and _GET_ITEM_ROLE_MAX_LEVEL_COUNT match
	// simple_crafting.c func_147/func_192.
	return invoke<int>(0xADDD1E7C0ECF7D95, 1, item.hash);
}

static bool overflowCaps(OverflowPrototypeItem& item, int& engineCap, int& activeCap) {
	const int engineBase = overflowEngineBase(item);
	engineCap = overflowEngineCap(item);
	if (engineBase != item.liftedBase) {
		if (engineBase != g_overflowLastCatalogBaseReadback)
			GtLogStream("overflow-storage", GT_WARN)
				<< "catalog-lift-not-active item=" << item.name
				<< " baseReadback=" << engineBase
				<< " expected=" << item.liftedBase << "\n";
		g_overflowLastCatalogBaseReadback = engineBase;
		return false;
	}
	g_overflowLastCatalogBaseReadback = engineBase;
	const int lift = item.liftedBase - item.authoredBase;
	activeCap = engineCap - lift;
	if (engineCap < item.liftedBase || activeCap < item.authoredBase) {
		GtLogStream("overflow-storage", GT_ERROR)
			<< "cap-readback-invalid item=" << item.name
			<< " engineCap=" << engineCap << " activeCap=" << activeCap
			<< " lift=" << lift << "\n";
		return false;
	}
	return true;
}

static void overflowLogTransaction(const char* direction,
	const OverflowPrototypeItem& item,
	int engineCap, int activeCap, int before, int requested, int after,
	int moved, int reserveBefore, int reserveAfter, const char* result) {
	GtLogStream("overflow-storage", moved == requested ? GT_INFO : GT_WARN)
		<< direction << "-result item=" << item.name
		<< " result=" << result
		<< " engineCap=" << engineCap
		<< " activeCap=" << activeCap
		<< " before=" << before
		<< " requested=" << requested
		<< " after=" << after
		<< " moved=" << moved
		<< " reserveBefore=" << reserveBefore
		<< " reserveAfter=" << reserveAfter << "\n";
}

static int overflowDeposit(OverflowPrototypeItem& item, int engineCap,
	int activeCap, int before, int requested, bool showFeed) {
	requested = (std::min)(before, (std::max)(0, requested));
	if (requested <= 0) return 0;
	const int reserveBefore = item.reserve;
	INVENTORY_REMOVE_WITH_REASON(item.hash, requested, joaat("REMOVE_REASON_DUPLICATE"));
	const int after = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
	const int moved = (std::min)(requested, (std::max)(0, before - after));
	if (moved <= 0) {
		overflowLogTransaction("deposit", item, engineCap, activeCap, before, requested, after,
			0, reserveBefore, reserveBefore, "remove-no-postcondition");
		return 0;
	}
	const int reserveAfter = reserveBefore + moved;
	if (!overflowWriteReserve(item, reserveAfter)) {
		// The inventory change is real but storage did not persist. Restore the
		// verified amount through the still-lifted engine cap instead of claiming it.
		const int rollbackBefore = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		INVENTORY_ADD(item.hash, moved);
		const int rollbackAfter = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		const int restored = (std::min)(moved,
			(std::max)(0, rollbackAfter - rollbackBefore));
		overflowLogTransaction("deposit", item, engineCap, activeCap, before, requested,
			rollbackAfter, moved, reserveBefore, reserveBefore,
			restored == moved ? "persist-failed-rolled-back" : "persist-failed-partial-rollback");
		g_overflowEnabled = false;
		return 0;
	}
	item.reserve = reserveAfter;
	overflowLogTransaction("deposit", item, engineCap, activeCap, before, requested, after,
		moved, reserveBefore, reserveAfter,
		moved == requested ? "stored" : "stored-partial");
	if (showFeed) {
		char message[160];
		sprintf_s(message, "%s sent to overflow storage (+%d; %d stored).",
			item.name == "CONSUMABLE_BAKED_BEANS_CAN" ? "Baked Beans" : item.name.c_str(),
			moved, reserveAfter);
		CASING_FEED(message, "INVENTORY_ITEMS", item.hash);
	}
	return moved;
}

static int overflowWithdraw(OverflowPrototypeItem& item, int engineCap,
	int activeCap, int requested) {
	const int before = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
	const int reserveBefore = item.reserve;
	requested = (std::min)(requested,
		(std::min)(reserveBefore, (std::max)(0, activeCap - before)));
	if (requested <= 0) return 0;
	INVENTORY_ADD(item.hash, requested);
	const int after = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
	const int moved = (std::min)(requested, (std::max)(0, after - before));
	if (moved <= 0) {
		overflowLogTransaction("withdraw", item, engineCap, activeCap, before,
			requested, after, 0, reserveBefore, reserveBefore,
			"add-no-postcondition");
		return 0;
	}
	const int reserveAfter = reserveBefore - moved;
	if (!overflowWriteReserve(item, reserveAfter)) {
		const int rollbackBefore = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		INVENTORY_REMOVE_WITH_REASON(item.hash, moved, joaat("REMOVE_REASON_DUPLICATE"));
		const int rollbackAfter = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		const int restored = (std::min)(moved,
			(std::max)(0, rollbackBefore - rollbackAfter));
		overflowLogTransaction("withdraw", item, engineCap, activeCap, before,
			requested, rollbackAfter, moved, reserveBefore, reserveBefore,
			restored == moved ? "persist-failed-rolled-back" :
			"persist-failed-partial-rollback");
		g_overflowEnabled = false;
		return 0;
	}
	item.reserve = reserveAfter;
	overflowLogTransaction("withdraw", item, engineCap, activeCap, before,
		requested, after, moved, reserveBefore, reserveAfter,
		moved == requested ? "withdrawn" : "withdrawn-partial");
	return moved;
}

static bool overflowAtCamp() {
	return scriptRunning("player_camp") || scriptRunning("interactive_campfire") ||
		scriptRunning("campfire_gang") || scriptRunning("campfire_gang_es");
}

static void overflowUiText(const std::string& text, float x, float y, float scale,
	int r = 245, int g = 245, int b = 245, int a = 255) {
	HUD::SET_TEXT_SCALE(scale, scale);
	HUD::_SET_TEXT_COLOR(r, g, b, a);
	HUD::SET_TEXT_CENTRE(FALSE);
	HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, 220);
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", text.c_str()), x, y);
}

static void overflowUiDisableControls() {
	// Raw keyboard input belongs to this page. Disable all game control groups;
	// the integration dispatcher must also stop later mod hotkey handlers while
	// updateOverflowStorage returns true.
	for (int group = 0; group < 3; ++group)
		invoke<Void>(0x5F4B6931816E599B, group); // DISABLE_ALL_CONTROL_ACTIONS
}

static bool overflowUiOwnedInputDown() {
	static const int keys[] = { VK_F7, VK_ESCAPE, VK_BACK, VK_RETURN, VK_UP, VK_DOWN };
	for (int key : keys) if ((GetAsyncKeyState(key) & 0x8000) != 0) return true;
	static const char* controls[] = {
		"INPUT_FRONTEND_UP", "INPUT_FRONTEND_DOWN", "INPUT_FRONTEND_ACCEPT",
		"INPUT_FRONTEND_CANCEL", "INPUT_GAME_MENU_UP", "INPUT_GAME_MENU_DOWN",
		"INPUT_GAME_MENU_ACCEPT", "INPUT_GAME_MENU_CANCEL"
	};
	for (const char* name : controls) for (int group = 0; group < 3; ++group) {
		const Hash control = joaat(name);
		if (PAD::IS_CONTROL_PRESSED(group, control) ||
			PAD::IS_DISABLED_CONTROL_PRESSED(group, control)) return true;
	}
	return false;
}

static void overflowUiClearKeyEdges() {
	static const int keys[] = { VK_F7, VK_ESCAPE, VK_BACK, VK_RETURN, VK_UP, VK_DOWN };
	for (int key : keys) (void)GetAsyncKeyState(key);
}

static void overflowUiAcquire(DWORD now) {
	ANIMSCENE::_PAUSE_SCRIPT_THREADS(TRUE);
	g_overflowUiThreadsPaused = true;
	invoke<Void>(0xEC3D8C228FE553D7, FALSE);
	g_overflowUiOpen = true;
	g_overflowUiInputArmed = false;
	g_overflowUiClosePending = false;
	g_overflowUiSelection = 0;
	g_overflowUiNextInputAt = now + 150u;
	gtLog("overflow-storage", GT_INFO,
		"ui-open camp=1 threadsPaused=1 inputArmed=0 drawOrder=7");
}

static void overflowUiRelease(const char* reason) {
	if (g_overflowUiThreadsPaused) {
		ANIMSCENE::_PAUSE_SCRIPT_THREADS(FALSE);
		invoke<Void>(0x41AFA5F228B0B6B0); // _REQUEST_PHOTO_MODE_DEFREEZE
		invoke<Void>(0xEC3D8C228FE553D7, TRUE);
	}
	g_overflowUiThreadsPaused = false;
	g_overflowUiOpen = false;
	g_overflowUiInputArmed = false;
	g_overflowUiClosePending = false;
	gtLog("overflow-storage", GT_INFO,
		std::string("ui-close reason=") + reason + " threadsPaused=0");
}

static void overflowUiDrawHint() {
	overflowUiText("F7  OVERFLOW STORAGE", 0.790f, 0.900f, 0.235f,
		225, 205, 170, 235);
}

static void overflowUiDraw(DWORD now, const OverflowPrototypeItem& item,
	int activeCap, bool capsReady) {
	invoke<Void>(0xCFCC78391C8B3814, 7); // SET_SCRIPT_GFX_DRAW_ORDER
	GRAPHICS::DRAW_RECT(0.5f, 0.5f, 0.70f, 0.72f, 14, 12, 10, 248, FALSE, FALSE);
	GRAPHICS::DRAW_RECT(0.5f, 0.18f, 0.70f, 0.10f, 76, 17, 12, 255, FALSE, FALSE);
	overflowUiText("OVERFLOW STORAGE", 0.185f, 0.145f, 0.50f);
	overflowUiText("CAMP STORAGE", 0.185f, 0.200f, 0.22f, 215, 192, 154);
	const int active = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
	overflowUiText("Baked Beans", 0.245f, 0.300f, 0.34f);
	overflowUiText("Active  " + std::to_string(active) + " / " +
		(capsReady ? std::to_string(activeCap) : "?"), 0.245f, 0.355f, 0.26f,
		220, 205, 180);
	overflowUiText("Stored  " + std::to_string(item.reserve), 0.245f, 0.400f,
		0.26f, 220, 205, 180);
	static const char* actions[] = { "WITHDRAW ONE", "DEPOSIT ONE" };
	for (int row = 0; row < 2; ++row) {
		const float y = 0.515f + row * 0.090f;
		const bool available = row == 0 ?
			(capsReady && item.reserve > 0 && active < activeCap) : active > 0;
		GRAPHICS::DRAW_RECT(0.5f, y, 0.48f, 0.064f,
			row == g_overflowUiSelection ? 112 : 50,
			row == g_overflowUiSelection ? 25 : 45,
			row == g_overflowUiSelection ? 17 : 40, 220, FALSE, FALSE);
		overflowUiText(actions[row], 0.300f, y - 0.018f, 0.285f,
			available ? 245 : 120, available ? 245 : 120, available ? 245 : 120);
	}
	overflowUiText("UP/DOWN select   ENTER/A transfer   ESC/F7/B close",
		0.245f, 0.735f, 0.235f, 225, 205, 170);
	if (now < g_overflowUiNoticeUntil)
		overflowUiText(g_overflowUiNotice, 0.245f, 0.680f, 0.235f,
			235, 190, 115);
}

static bool overflowUiUpdate(DWORD now, OverflowPrototypeItem& item,
	int engineCap, int activeCap, bool capsReady) {
	const bool f7Down = (GetAsyncKeyState(VK_F7) & 0x8000) != 0;
	const bool f7Pressed = f7Down && !g_overflowUiF7WasDown;
	g_overflowUiF7WasDown = f7Down;
	if (!g_overflowUiOpen) {
		if (!overflowAtCamp()) return false;
		overflowUiDrawHint();
		// Never cover an active Rockstar page. The mod-owned page opens only from
		// the normal camp state and uses its own keyboard key.
		const bool rockstarPage = UIAPP_ACTIVE(joaat("CRAFTING")) ||
			UIAPP_ACTIVE(joaat("SATCHEL")) || HUD::IS_PAUSE_MENU_ACTIVE();
		if (f7Pressed && !rockstarPage && capsReady) overflowUiAcquire(now);
		else if (f7Pressed && !capsReady) {
			g_overflowUiNotice = "Catalog lift is not active";
			g_overflowUiNoticeUntil = now + 2500u;
		}
		return g_overflowUiOpen;
	}

	overflowUiDisableControls();
	invoke<Void>(0x06565032897BA861, 6); // _UI_PROMPT_ENABLE_PROMPT_TYPE_THIS_FRAME
	overflowUiDraw(now, item, activeCap, capsReady);
	if (!g_overflowUiInputArmed) {
		if (overflowUiOwnedInputDown()) return true;
		overflowUiClearKeyEdges();
		g_overflowUiInputArmed = true;
		g_overflowUiNextInputAt = now + 100u;
		gtLog("overflow-storage", GT_INFO,
			"ui-input-armed threadsPaused=1 allOwnedKeysReleased=1");
		return true;
	}
	if (g_overflowUiClosePending) {
		if (overflowUiOwnedInputDown()) return true;
		overflowUiRelease("release-gated-cancel");
		return false;
	}
	const bool padCancel = PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0,
		joaat("INPUT_FRONTEND_CANCEL")) || PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2,
		joaat("INPUT_FRONTEND_CANCEL")) || PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0,
		joaat("INPUT_GAME_MENU_CANCEL")) || PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2,
		joaat("INPUT_GAME_MENU_CANCEL"));
	if (f7Pressed || padCancel || (GetAsyncKeyState(VK_ESCAPE) & 1) ||
		(GetAsyncKeyState(VK_BACK) & 1)) {
		g_overflowUiClosePending = true;
		g_overflowUiNotice = "Release the key to return to camp";
		g_overflowUiNoticeUntil = now + 2500u;
		return true;
	}
	if (now < g_overflowUiNextInputAt) return true;
	const bool up = (GetAsyncKeyState(VK_UP) & 1) != 0 ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, joaat("INPUT_FRONTEND_UP")) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, joaat("INPUT_GAME_MENU_UP"));
	const bool down = (GetAsyncKeyState(VK_DOWN) & 1) != 0 ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, joaat("INPUT_FRONTEND_DOWN")) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, joaat("INPUT_GAME_MENU_DOWN"));
	const bool accept = (GetAsyncKeyState(VK_RETURN) & 1) != 0 ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, joaat("INPUT_FRONTEND_ACCEPT")) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, joaat("INPUT_GAME_MENU_ACCEPT"));
	if (up || down) {
		g_overflowUiSelection = 1 - g_overflowUiSelection;
		g_overflowUiNextInputAt = now + 110u;
	}
	if (accept && capsReady) {
		const int before = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		int moved = 0;
		if (g_overflowUiSelection == 0)
			moved = overflowWithdraw(item, engineCap, activeCap, 1);
		else moved = overflowDeposit(item, engineCap, activeCap, before, 1, false);
		item.lastCount = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		g_overflowUiNotice = moved > 0 ?
			(g_overflowUiSelection == 0 ? "Withdrew one Baked Beans" :
			 "Deposited one Baked Beans") :
			(g_overflowUiSelection == 0 ? "Active inventory is full or storage is empty" :
			 "No Baked Beans to deposit");
		g_overflowUiNoticeUntil = now + 2200u;
		g_overflowUiNextInputAt = now + 180u;
	}
	return true;
}

static void loadOverflowStorage() {
	if (g_overflowLoaded) return;
	g_overflowLoaded = true;
	if (!overflowLoadPrototypeData()) return;
	g_overflowStoragePath = g_moduleDir + "\\GameplayTweaks.overflow-storage.ini";
	g_overflowPrototype.reserve = overflowReadReserve(g_overflowPrototype);
	if (!overflowWriteReserve(g_overflowPrototype, g_overflowPrototype.reserve)) {
		gtLog("overflow-storage", GT_ERROR, "persistence-preflight-failed");
		return;
	}
	g_overflowPrototype.lastCount = (std::max)(0,
		INVENTORY_ITEM_COUNT(g_overflowPrototype.hash));
	g_overflowEnabled = true;
	// The first dispatcher call must establish the catalog/cap readback before
	// F7 can open the page. Invalid startup reads are retried at the normal rate.
	g_overflowNextPollAt = GetTickCount();
	GtLogStream("overflow-storage", GT_INFO)
		<< "registered prototype=1 item=" << g_overflowPrototype.name
		<< " authoredBase=" << g_overflowPrototype.authoredBase
		<< " liftedBase=" << g_overflowPrototype.liftedBase
		<< " count=" << g_overflowPrototype.lastCount
		<< " reserve=" << g_overflowPrototype.reserve << "\n";
}

// Called by the integration dispatcher. The return value is true while this
// page owns input; the dispatcher must skip later mod hotkey handlers then.
// Background inventory mutation remains transition-only.
static bool updateOverflowStorage(DWORD now) {
	loadOverflowStorage();
	if (!g_overflowEnabled) {
		if (g_overflowUiOpen || g_overflowUiThreadsPaused)
			overflowUiRelease("feature-disabled");
		return false;
	}
	OverflowPrototypeItem& item = g_overflowPrototype;
	if (now >= g_overflowNextPollAt) {
		g_overflowNextPollAt = now + 250u;
		int engineCap = 0;
		int activeCap = 0;
		item.capReadbackReady = overflowCaps(item, engineCap, activeCap);
		item.lastEngineCap = engineCap;
		item.lastActiveCap = activeCap;
		const int count = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		const bool countTransition = !item.primed || count != item.lastCount;
		if (item.capReadbackReady && countTransition && count > activeCap)
			overflowDeposit(item, engineCap, activeCap, count, count - activeCap, true);
		item.lastCount = (std::max)(0, INVENTORY_ITEM_COUNT(item.hash));
		item.primed = true;
	}
	const bool ownsInput = overflowUiUpdate(now, item, item.lastEngineCap,
		item.lastActiveCap, item.capReadbackReady);
	if (!g_overflowLastHeartbeatAt || now - g_overflowLastHeartbeatAt >= 10000u) {
		g_overflowLastHeartbeatAt = now;
		GtLogStream("overflow-storage", GT_INFO)
			<< "heartbeat item=" << item.name
			<< " count=" << item.lastCount
			<< " engineCap=" << item.lastEngineCap
			<< " activeCap=" << item.lastActiveCap
			<< " reserve=" << item.reserve
			<< " ui=" << (g_overflowUiOpen ? 1 : 0)
			<< " threadsPaused=" << (g_overflowUiThreadsPaused ? 1 : 0)
			<< " catalogLift=" << (item.capReadbackReady ? 1 : 0) << "\n";
	}
	return ownsInput;
}
