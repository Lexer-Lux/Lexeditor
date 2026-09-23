// GameplayTweaks feature module: Configuration reload, merchants, unique items, economy, camera, bounty, bloodstain, and campsites.
// Included by script.cpp into the single ScriptHook translation unit.

// #126: adapter so existing `log << "field=" << value` code writes to the one
// unified log without a single field being restated or renamed. Each '\n' in
// the stream ends one record, which is emitted immediately via gtLog(), so
// ordering against other subsystems stays exact. Guarded because several
// modules carry this same block into the one translation unit.
#ifndef GT_LOG_STREAM_DEFINED
#define GT_LOG_STREAM_DEFINED
struct GtLogStream {
	GtLogStream(const char* subsystem, GtLogLevel level)
		: subsystem_(subsystem), level_(level) {}
	~GtLogStream() { drain(true); }
	template <class T> GtLogStream& operator<<(const T& value) {
		buffer_ << value; drain(false); return *this;
	}
	GtLogStream& operator<<(std::ostream& (*manip)(std::ostream&)) {
		buffer_ << manip; drain(false); return *this;
	}
	GtLogStream& operator<<(std::ios_base& (*manip)(std::ios_base&)) {
		buffer_ << manip; drain(false); return *this;
	}
	// Contextual conversion only, so the legacy `if (log)` guards still compile
	// and no built-in operator<< can hijack an insertion.
	explicit operator bool() const { return true; }
private:
	void drain(bool final) {
		pending_ += buffer_.str();
		buffer_.str(std::string()); // clears the buffer, keeps hex/dec/precision
		size_t nl;
		while ((nl = pending_.find('\n')) != std::string::npos) {
			std::string line = pending_.substr(0, nl);
			pending_.erase(0, nl + 1);
			if (!line.empty() && line[line.size() - 1] == '\r') line.erase(line.size() - 1);
			if (!line.empty()) gtLog(subsystem_, level_, line);
		}
		if (final && !pending_.empty()) {
			gtLog(subsystem_, level_, pending_);
			pending_.clear();
		}
	}
	const char* subsystem_;
	GtLogLevel level_;
	std::ostringstream buffer_;
	std::string pending_;
};
#endif


static void initIniPath() {
	char path[MAX_PATH] = {};
	HMODULE self = nullptr;
	GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
		(LPCSTR)&initIniPath, &self);
	GetModuleFileNameA(self, path, MAX_PATH);
	g_moduleDir = path;
	g_moduleDir = g_moduleDir.substr(0, g_moduleDir.find_last_of("\\/"));
	g_iniPath = path;
	g_iniPath = g_iniPath.substr(0, g_iniPath.find_last_of('.')) + ".ini";
}

static UINT64 merchantOverrideKey(Hash shop, Hash item) {
	return (static_cast<UINT64>(shop) << 32) | static_cast<UINT64>(item);
}

static void loadMerchantBuyOverrides() {
	g_merchantBuyOverrides.clear();
	std::ifstream input(g_moduleDir + "\\merchant_buy_overrides.csv");
	std::string line;
	std::getline(input, line);
	while (std::getline(input, line)) {
		const size_t first = line.find(',');
		const size_t second = first == std::string::npos ? std::string::npos : line.find(',', first + 1);
		if (first == std::string::npos || second == std::string::npos) continue;
		const std::string shop = line.substr(0, first);
		const std::string item = line.substr(first + 1, second - first - 1);
		const std::string mode = line.substr(second + 1);
		if (shop.empty() || item.empty()) continue;
		if (mode == "accept") g_merchantBuyOverrides[merchantOverrideKey(joaat(shop.c_str()), joaat(item.c_str()))] = 1;
		else if (mode == "reject") g_merchantBuyOverrides[merchantOverrideKey(joaat(shop.c_str()), joaat(item.c_str()))] = -1;
	}
	GtLogStream("merchant-buy", GT_INFO)
		<< "loaded overrides=" << g_merchantBuyOverrides.size() << "\n";
}

static void reloadIfChanged() {
	WIN32_FILE_ATTRIBUTE_DATA fad;
	if (!GetFileAttributesExA(g_iniPath.c_str(), GetFileExInfoStandard, &fad)) return;
	if (CompareFileTime(&fad.ftLastWriteTime, &g_lastWrite) != 0) {
		g_lastWrite = fad.ftLastWriteTime;
		loadConfig();
	}
	WIN32_FILE_ATTRIBUTE_DATA alcohol;
	std::string path = g_moduleDir + "\\alcohol_strengths.csv";
	if (GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &alcohol) &&
		CompareFileTime(&alcohol.ftLastWriteTime, &g_alcoholLastWrite) != 0) {
		g_alcoholLastWrite = alcohol.ftLastWriteTime;
		loadAlcoholStrengths();
	}
	WIN32_FILE_ATTRIBUTE_DATA buyers;
	path = g_moduleDir + "\\merchant_buy_overrides.csv";
	if (GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &buyers) &&
		CompareFileTime(&buyers.ftLastWriteTime, &g_buyerOverrideLastWrite) != 0) {
		g_buyerOverrideLastWrite = buyers.ftLastWriteTime;
		loadMerchantBuyOverrides();
	}
}

static bool dumpVanillaShopBuyers() {
	const char* shops[] = {
		"ST_BAIT", "ST_BARBER", "ST_BUTCHER", "ST_CLOTHING", "ST_DOCTOR",
		"ST_EXOTIC", "ST_FENCE", "ST_FRENCH_MARKET", "ST_GENERAL", "ST_GUNSMITH",
		"ST_HAIR", "ST_HORSE_SHOP", "ST_HORSE_TRAINER", "ST_MARKET",
		"ST_NEWSPAPER_BOY", "ST_PEARSON", "ST_QUARTERMASTER", "ST_TAILOR",
		"ST_TRAIN_STATION", "ST_TRAPPER"
	};
	std::string output = g_moduleDir + "\\vanilla_shop_buyers.csv";
	if (GetFileAttributesA(output.c_str()) != INVALID_FILE_ATTRIBUTES) return true;
	// This CRC-mounted parsed-data resource loads by its literal resource hash,
	// not joaat("PDATA_SHOP_INVENTORIES").
	int file = PARSEDDATA_LOAD(0x0BA63B3D);
	for (int tries = 0; tries < 1000 && !PARSEDDATA_LOADED(file); ++tries) WAIT(10);
	GtLogStream log("shop-buyers", GT_INFO);
	if (!PARSEDDATA_LOADED(file)) { log << "PDATA_SHOP_INVENTORIES (0x0BA63B3D) failed to load; retrying in Story Mode\n"; return false; }
	PARSEDDATA_REGISTER(file, 0, "SHOPINVENTORIES/SHOPSELLABLEITEMS(SHOPTYPE=%X)/INVITEM(%i):ITEMID");
	std::ofstream csv(output, std::ios::trunc);
	csv << "shop,item_hash\n";
	for (const char* shop : shops) {
		int found = 0, misses = 0;
		for (int index = 0; index < 10000 && misses < 4; ++index) {
			Any query[5] = { file, 0, 0, (Any)joaat(shop), index };
			Hash item = 0;
			if (PARSEDDATA_HASH(&item, query) && item) {
				csv << shop << ",0x" << std::hex << std::uppercase << item << std::dec << "\n";
				++found; misses = 0;
			} else ++misses;
		}
		log << shop << ": " << found << " items\n";
	}
	PARSEDDATA_UNLOAD(file);
	return true;
}

struct RecoverableUnique {
	const char* id;
	const char* model;
	const char* label;
	Hash weapon = 0;
	Hash modelHash = 0;
	bool acquired = false;
	bool pendingAtLocker = false;
	DWORD missingSince = 0;
};

// weapon_locker.c stores a weapon by clearing field 21 in the weapon's full
// inventory data and committing that data with _INVENTORY_UPDATE_INVENTORY_ITEM
// (its func_73).  This is the actual locker state; there is no separate locker
// container.  Enumerating ALL WEAPONS also finds entries which have no attach
// point, unlike GET_PED_WEAPON_GUID_AT_ATTACH_POINT.
struct WeaponCollectionEntry { Any field[10]; };
struct WeaponInventoryData { Any field[22]; };
static_assert(sizeof(WeaponCollectionEntry) == sizeof(Any) * 10, "weapon collection entry layout");
static_assert(sizeof(WeaponInventoryData) == sizeof(Any) * 22, "weapon inventory data layout");

// Prompt helpers are implemented below with the rest of the module's native
// UIPrompt wrappers.  The recovery prompt is intentionally visible only while
// Rockstar's weapon_locker script owns the screen.
static int  CASING_PROMPT_BEGIN();
static void CASING_PROMPT_END(int p);
static void CASING_PROMPT_CONTROL(int p, Hash action);
static void CASING_PROMPT_TEXT(int p, const char* t);
static void CASING_PROMPT_HOLD(int p, Hash type);
static void CASING_PROMPT_VISIBLE(int p, BOOL v);
static void CASING_PROMPT_ENABLED(int p, BOOL v);
static bool CASING_PROMPT_DONE(int p);
static void CASING_PROMPT_RESTART(int p);
static const char* CASING_LITERAL(const char* t);

static int g_uniqueLockerPrompt = 0;
static bool g_uniqueLockerPromptRegistered = false;

// Returns -1 when the weapon has no inventory entry, 0 when field 21 places it
// in the locker, and 1 when it is available to the player/horse.  Rockstar's
// locker UI uses the same classification, but filters melee and throwables out
// before it ever evaluates this field.
static int uniqueWeaponLockerState(Hash weapon) {
	int count = 0;
	const int collection = invoke<int>(0x80D78BDC9D88EF07, 1, "ALL WEAPONS", (Hash)-1591664384, &count);
	if (collection < 0) return -1;
	int state = -1;
	for (int index = 0; index < count; ++index) {
		WeaponCollectionEntry entry = {};
		entry.field[9] = (Any)-1591664384;
		if (!invoke<BOOL>(0x82FA24C3D3FCD9B7, collection, index, &entry)) continue;
		if ((Hash)entry.field[4] != weapon) continue;
		InventoryGuid guid = {};
		for (int i = 0; i < 4; ++i) guid.data[i] = entry.field[i];
		WeaponInventoryData data = {};
		data.field[9] = (Any)-1591664384;
		if (invoke<BOOL>(0x025A1B1FB03FBF61, 1, &guid, &data, 22, 1))
			state = data.field[21] ? 1 : 0;
		break;
	}
	invoke<BOOL>(0x42A2F33A1942E865, collection);
	return state;
}

static bool setUniqueWeaponLockerState(Hash weapon, bool stored) {
	int count = 0;
	const int collection = invoke<int>(0x80D78BDC9D88EF07, 1, "ALL WEAPONS", (Hash)-1591664384, &count);
	if (collection < 0) return false;
	bool changed = false;
	for (int index = 0; index < count; ++index) {
		WeaponCollectionEntry entry = {};
		entry.field[9] = (Any)-1591664384;
		if (!invoke<BOOL>(0x82FA24C3D3FCD9B7, collection, index, &entry)) continue;
		if ((Hash)entry.field[4] != weapon) continue;
		InventoryGuid guid = {};
		for (int i = 0; i < 4; ++i) guid.data[i] = entry.field[i];
		WeaponInventoryData data = {};
		data.field[9] = (Any)-1591664384;
		if (!invoke<BOOL>(0x025A1B1FB03FBF61, 1, &guid, &data, 22, 1)) break;
		data.field[21] = stored ? 0 : 1;
		if (!invoke<BOOL>(0xD80A8854DB5CFBA5, 1, &guid, &data, 22)) break;
		WeaponInventoryData check = {};
		check.field[9] = (Any)-1591664384;
		changed = invoke<BOOL>(0x025A1B1FB03FBF61, 1, &guid, &check, 22, 1) &&
			(check.field[21] != 0) == !stored;
		break;
	}
	invoke<BOOL>(0x42A2F33A1942E865, collection);
	return changed;
}

static bool stageUniqueAtLocker(Ped playerPed, Hash weapon) {
	// The live test proved that inserting a field-21 melee entry can prevent the
	// vanilla locker from opening. Stage only our persistent pending record. The
	// weapon is created, unequipped, only after an explicit recovery action in a
	// successfully opened WEAPON_LOCKER app.
	return !HAS_WEAPON(playerPed, weapon) && INVENTORY_ITEM_COUNT(weapon) <= 0 &&
		uniqueWeaponLockerState(weapon) < 0;
}
static RecoverableUnique g_recoverableUniques[] = {
	{"WEAPON_MELEE_HATCHET_VIKING", "W_MELEE_HATCHET04", "Viking Hatchet"},
	{"WEAPON_MELEE_HATCHET_HEWING", "W_MELEE_HATCHET05", "Hewing Hatchet"},
	{"WEAPON_MELEE_HATCHET_DOUBLE_BIT", "W_MELEE_HATCHET05", "Double Bit Hatchet"},
	{"WEAPON_MELEE_HATCHET_DOUBLE_BIT_RUSTED", "W_MELEE_HATCHET06", "Rusted Double Bit Hatchet"},
	{"WEAPON_MELEE_HATCHET_HUNTER", "W_MELEE_HATCHET07", "Hunter Hatchet"},
	{"WEAPON_MELEE_HATCHET_HUNTER_RUSTED", "W_MELEE_HATCHET07", "Rusted Hunter Hatchet"},
};

static void initializeRecoverableUniques() {
	std::string path = statePath("recoverable_unique_weapons.ini");
	for (RecoverableUnique& unique : g_recoverableUniques) {
		unique.weapon = joaat(unique.id); unique.modelHash = joaat(unique.model);
		unique.acquired = GetPrivateProfileIntA("Acquired", unique.id, 0, path.c_str()) != 0;
		unique.pendingAtLocker = GetPrivateProfileIntA("PendingAtLocker", unique.id, 0, path.c_str()) != 0;
		// Record previous hidden entries as pending. updateRecoverableUniques removes
		// those unsafe field-21 melee entries once a live player ped is available.
		if (unique.acquired && uniqueWeaponLockerState(unique.weapon) == 0) {
			unique.pendingAtLocker = true;
			WritePrivateProfileStringA("PendingAtLocker", unique.id, "1", path.c_str());
		}
	}
}

static bool liveUniquePickup(Hash model) {
	int pickups[512] = {}; int count = worldGetAllPickups(pickups, 512);
	for (int i = 0; i < count; ++i) {
		Object object = PICKUP_OBJECT(pickups[i]);
		if (object && ENTITY_MODEL(object) == model) return true;
	}
	return false;
}

static void updateRecoverableUniques(Ped playerPed, DWORD now, bool mission) {
	if (!g_recoverUniqueWeapons || mission) {
		return;
	}
	std::string path = statePath("recoverable_unique_weapons.ini");
	for (RecoverableUnique& unique : g_recoverableUniques) {
		int lockerState = uniqueWeaponLockerState(unique.weapon);
		if (lockerState == 0 && unique.acquired) {
			// Roll back the build that made the locker inaccessible. First restore the
			// entry to ordinary inventory state so the inverse field transition is
			// committed, then remove that temporary entry. The persistent pending flag
			// remains the only staged representation until explicit locker recovery.
			const bool activated = setUniqueWeaponLockerState(unique.weapon, false);
			WEAPON::REMOVE_WEAPON_FROM_PED(playerPed, unique.weapon, FALSE,
				joaat("REMOVE_REASON_DEBUG"));
			lockerState = uniqueWeaponLockerState(unique.weapon);
			unique.pendingAtLocker = true;
			WritePrivateProfileStringA("PendingAtLocker", unique.id, "1", path.c_str());
			GtLogStream("uniques", lockerState < 0 ? GT_INFO : GT_WARN)
				<< "legacy hidden rollback " << unique.id
				<< " activated=" << (activated ? 1 : 0)
				<< " finalState=" << lockerState << "\n";
		}
		const bool stored = lockerState == 0;
		const bool owned = !stored &&
			(HAS_WEAPON(playerPed, unique.weapon) || INVENTORY_ITEM_COUNT(unique.weapon) > 0);
		if (owned && !unique.acquired) {
			unique.acquired = true;
			WritePrivateProfileStringA("Acquired", unique.id, "1", path.c_str());
		}
		if (stored && unique.acquired && !unique.pendingAtLocker) {
			unique.pendingAtLocker = true;
			WritePrivateProfileStringA("PendingAtLocker", unique.id, "1", path.c_str());
		}
		if (unique.pendingAtLocker && owned) {
			// Manual world retrieval still wins if it becomes available before the
			// player takes the staged copy from camp.
			unique.pendingAtLocker = false;
			WritePrivateProfileStringA("PendingAtLocker", unique.id, "0", path.c_str());
		}
		if (unique.pendingAtLocker || !unique.acquired || owned || liveUniquePickup(unique.modelHash)) {
			unique.missingSince = 0;
			continue;
		}
		if (!unique.missingSince) unique.missingSince = now;
		else if (now - unique.missingSince >= 30000) {
			if (stageUniqueAtLocker(playerPed, unique.weapon)) {
				unique.pendingAtLocker = true;
				unique.missingSince = 0;
				WritePrivateProfileStringA("PendingAtLocker", unique.id, "1", path.c_str());
				GtLogStream("uniques", GT_INFO)
					<< "staged " << unique.id << " at locker\n";
			}
		}
	}

}

// Run every frame while the slow inventory/world scan above remains throttled.
// Menu presses are edges and must not be sampled only once per second.
static void updateRecoverableUniqueLocker(Ped playerPed, DWORD now,
	bool unavailable, bool mission) {
	RecoverableUnique* pending = nullptr;
	for (RecoverableUnique& unique : g_recoverableUniques) {
		if (unique.pendingAtLocker) { pending = &unique; break; }
	}
	// Never register or enable our prompt during the world interaction that opens
	// the locker. The supplied failure showed that script lifetime is broader than
	// the actual frontend. Wait until Rockstar confirms the app is active.
	const bool lockerOpen = g_recoverUniqueWeapons && !unavailable && !mission &&
		playerPed && pending &&
		UIAPPS::_IS_APP_ACTIVE_BY_HASH(joaat("WEAPON_LOCKER"));
	if (!g_uniqueLockerPromptRegistered && lockerOpen) {
		g_uniqueLockerPrompt = CASING_PROMPT_BEGIN();
		CASING_PROMPT_CONTROL(g_uniqueLockerPrompt, joaat("INPUT_GAME_MENU_EXTRA_OPTION"));
		CASING_PROMPT_TEXT(g_uniqueLockerPrompt, CASING_LITERAL("Recover unique weapon"));
		CASING_PROMPT_HOLD(g_uniqueLockerPrompt, joaat("SHORT_TIMED_EVENT"));
		CASING_PROMPT_END(g_uniqueLockerPrompt);
		g_uniqueLockerPromptRegistered = true;
	}
	if (g_uniqueLockerPromptRegistered) {
		if (lockerOpen) {
			std::string text = "Recover " + std::string(pending->label);
			CASING_PROMPT_TEXT(g_uniqueLockerPrompt, CASING_LITERAL(text.c_str()));
		}
		CASING_PROMPT_VISIBLE(g_uniqueLockerPrompt, lockerOpen ? TRUE : FALSE);
		CASING_PROMPT_ENABLED(g_uniqueLockerPrompt, lockerOpen ? TRUE : FALSE);
	}
	if (lockerOpen && CASING_PROMPT_DONE(g_uniqueLockerPrompt)) {
		std::string path = statePath("recoverable_unique_weapons.ini");
		const bool absent = uniqueWeaponLockerState(pending->weapon) < 0 &&
			!HAS_WEAPON(playerPed, pending->weapon) &&
			INVENTORY_ITEM_COUNT(pending->weapon) <= 0 &&
			!liveUniquePickup(pending->modelHash);
		if (absent) GIVE_WEAPON(playerPed, pending->weapon);
		const bool retrieved = absent && HAS_WEAPON(playerPed, pending->weapon);
		GtLogStream("uniques", GT_INFO)
			<< "retrieve " << pending->id
			<< " absent=" << (absent ? 1 : 0)
			<< " result=" << (retrieved ? 1 : 0) << "\n";
		if (retrieved) {
			pending->pendingAtLocker = false;
			WritePrivateProfileStringA("PendingAtLocker", pending->id, "0", path.c_str());
		}
		CASING_PROMPT_RESTART(g_uniqueLockerPrompt);
	}
}

static int gamblerRank() {
	static const char* goals[][3] = {
		{"ACW_GAMB_Rank_01_Poker"}, {"ACW_GAMB_Rank_02_Blackjack"}, {"ACW_GAMB_Rank_03_FiveFingerFillet"},
		{"ACW_GAMB_Rank_04_Poker_FNS", "ACW_GAMB_Rank_04_Poker_SDN", "ACW_GAMB_Rank_04_Poker_VAL"},
		{"ACW_GAMB_Rank_05_Dominoes"}, {"ACW_GAMB_Rank_06_Blackjack_RHO", "ACW_GAMB_Rank_06_Blackjack_VAN"},
		{"ACW_GAMB_Rank_07_FiveFinger_STR", "ACW_GAMB_Rank_07_FiveFinger_VAL", "ACW_GAMB_Rank_07_FiveFinger_VAN"},
		{"ACW_GAMB_Rank_08_Blackjack"}, {"ACW_GAMB_Rank_09_Dominoes"}, {"ACW_GAMB_Rank_10_PokerHands"}
	};
	Hash challenge = joaat("SP_CHAL_GAMB_ROOT");
	for (int rank = 0; rank < 10; ++rank)
		for (int j = 0; j < 3 && goals[rank][j]; ++j)
			if (GOAL_ACTIVE(challenge, joaat(goals[rank][j]))) return rank;
	return UNLOCKED(joaat("CHAL_GAMBLER_TREE_COMPLETED")) ? 10 : 0;
}

static void CASING_FEED(const char* text, const char* textureDict, Hash texture);

// #112. The Banking mod has no public API. This bridge is deliberately pinned
// to the one installed build we inspected: a different PE is never written to.
// Banking.asi stores cents at RVA 0x53A48 and periodically persists that value
// as the first integer in Banking.dat.
static volatile int* walletBankBalance(DWORD now) {
	static volatile int* balance = nullptr;
	static DWORD nextProbe = 0;
	static bool mismatchLogged = false;
	if (balance) return balance;
	if (now < nextProbe) return nullptr;
	nextProbe = now + 5000;
	HMODULE module = GetModuleHandleA("Banking.asi");
	if (!module) return nullptr;
	const BYTE* base = reinterpret_cast<const BYTE*>(module);
	const IMAGE_DOS_HEADER* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
	if (dos->e_magic != IMAGE_DOS_SIGNATURE) return nullptr;
	const IMAGE_NT_HEADERS64* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
	if (nt->Signature != IMAGE_NT_SIGNATURE ||
		nt->FileHeader.TimeDateStamp != 0x63A0E7D4 ||
		nt->OptionalHeader.SizeOfImage != 0x5A000) {
		if (!mismatchLogged) {
			mismatchLogged = true;
			GtLogStream("wallet", GT_INFO)
				<< "Banking.asi version mismatch; Auto-Bank disabled safely\n";
		}
		return nullptr;
	}
	balance = reinterpret_cast<volatile int*>(const_cast<BYTE*>(base) + 0x53A48);
	return balance;
}

static bool walletAutoBank() {
	return GetPrivateProfileIntA("Misc", "Auto-Bank", 1, g_iniPath.c_str()) != 0;
}

static int walletActiveCap(int* rankOut = nullptr) {
	const int rank = (std::max)(0, (std::min)(10, gamblerRank()));
	if (rankOut) *rankOut = rank;
	return g_walletCapEnabled ? g_walletCapCents[rank] : 0;
}

static int enforceWalletCap() {
	const int cash = CASH_BALANCE();
	if (!g_walletCapEnabled) return cash;
	int rank = 0;
	const int cap = walletActiveCap(&rank);
	if (cap <= 0 || cash <= cap) return cash;
	const DWORD now = GetTickCount();
	const int excess = cash - cap;
	volatile int* bank = walletAutoBank() ? walletBankBalance(now) : nullptr;
	if (walletAutoBank() && !bank) {
		static DWORD lastWarning = 0;
		if (now - lastWarning >= 5000) {
			lastWarning = now;
			CASING_FEED("Wallet full: Auto-Bank is unavailable", "", 0);
		}
		return cash; // Never destroy earnings when the requested bank cannot receive them.
	}
	if (bank && static_cast<long long>(*bank) + excess > 2147483647LL) {
		CASING_FEED("Wallet full: bank account cannot hold more", "", 0);
		return cash;
	}
	if (!REMOVE_CASH(excess)) return CASH_BALANCE();
	if (bank) *bank += excess;
	char message[112];
	if (bank)
		sprintf_s(message, "$%d.%02d sent to your bank", excess / 100, excess % 100);
	else
		sprintf_s(message, "Wallet full at rank %d: $%d.%02d", rank, cap / 100, cap % 100);
	CASING_FEED(message, "", 0);
	GtLogStream("wallet", GT_INFO)
		<< "cash=" << cash << " cap=" << cap << " excess=" << excess
		<< " autoBank=" << (bank ? 1 : 0)
		<< " cashAfter=" << CASH_BALANCE()
		<< " bankAfter=" << (bank ? *bank : -1) << "\n";
	return CASH_BALANCE();
}

#if 0 // Superseded by issue-owned modules/bloodstain_hat.cpp (#99).
struct BloodstainState { bool active = false; int cash = 0; Vector3 position = {}; Blip blip = 0; Object prop = 0; };
// #50: the drawn pool and beam were not readable on the ground, so there was
// nothing to walk up to. Spawn a real world object as well. A money bag is the
// obvious choice - it IS the lost cash, it is a shipped asset, and it reads at
// a glance without looking like a grave marker for a death you recovered from.
// #50 round two. Three complaints, three separate causes:
//  - MAP ICON. It was BLIP_AMBIENT_DEATH, which is the small outline CROSS -
//    a grave marker, for a death you walked away from, and it says nothing
//    about money. There is NO skull anywhere in the 321 vanilla blip textures
//    (all of them are extracted at icons/vanilla/png/blips/ - checked every
//    one), so a skull would have to be drawn and shipped through lex_blips.ytd
//    as new art. BLIP_CASH_BAG is a shipped money bag with a $ on it, which is
//    literally what the marker is, so that is the default now.
//  - ICON SIZE. Nothing ever set a scale, so it drew at the same size as every
//    ambient blip on the map. It is now scaled up.
//  - THE WORLD MARKER. The pool was dark red at 190 alpha and the beam was
//    10 cm wide, dark red, 1.5 m tall - i.e. deliberately dim, on ground that
//    is often already dark. It is gold now, wider, twice as tall, and carries
//    a real light so it reads at night, which was the actual problem.
// All four of these plus the prop are ini-driven so alternatives can be tried
// without a rebuild. Prop alternatives that exist in the game if the bag still
// reads too small: p_moneybag05x, p_satchel01x, p_strongbox01x, p_chest01x.
static std::string g_bloodstainProp = "p_moneybag01x";
static std::string g_bloodstainIcon = "BLIP_CASH_BAG";
static float g_bloodstainBlipScale = 1.4f;
static float g_bloodstainMarkerScale = 1.0f;
static BloodstainState g_bloodstain;

static void loadBloodstainSettings() {
	char buf[96] = {};
	GetPrivateProfileStringA("LostMoney", "PropModel", "p_moneybag01x", buf, sizeof(buf), g_iniPath.c_str());
	if (buf[0]) g_bloodstainProp = buf;
	GetPrivateProfileStringA("LostMoney", "MapIcon", "BLIP_CASH_BAG", buf, sizeof(buf), g_iniPath.c_str());
	if (buf[0]) g_bloodstainIcon = buf;
	g_bloodstainBlipScale = readF("LostMoney", "MapIconScale", 1.4f);
	if (g_bloodstainBlipScale < 0.5f) g_bloodstainBlipScale = 0.5f;
	if (g_bloodstainBlipScale > 3.0f) g_bloodstainBlipScale = 3.0f;
	g_bloodstainMarkerScale = readF("LostMoney", "WorldMarkerScale", 1.0f);
	if (g_bloodstainMarkerScale < 0.25f) g_bloodstainMarkerScale = 0.25f;
	if (g_bloodstainMarkerScale > 4.0f) g_bloodstainMarkerScale = 4.0f;
}

static std::string bloodstainPath() { return g_moduleDir + "\\GameplayTweaks.bloodstain.dat"; }
static void saveBloodstain() {
	std::ofstream out(bloodstainPath(), std::ios::trunc);
	out << (g_bloodstain.active ? 1 : 0) << ' ' << g_bloodstain.cash << ' '
		<< g_bloodstain.position.x << ' ' << g_bloodstain.position.y << ' ' << g_bloodstain.position.z << '\n';
}
static void loadBloodstain() {
	std::ifstream in(bloodstainPath()); int active = 0;
	if (in >> active >> g_bloodstain.cash >> g_bloodstain.position.x >> g_bloodstain.position.y >> g_bloodstain.position.z)
		g_bloodstain.active = active != 0 && g_bloodstain.cash > 0;
}
static void removeBloodstainBlip() { if (g_bloodstain.blip) REMOVE_MAP_BLIP(&g_bloodstain.blip); }
static void removeBloodstainProp() {
	if (!g_bloodstain.prop) return;
	if (ENTITY::DOES_ENTITY_EXIST(g_bloodstain.prop)) {
		ENTITY::SET_ENTITY_AS_MISSION_ENTITY(g_bloodstain.prop, TRUE, TRUE);
		Object handle = g_bloodstain.prop;
		OBJECT::DELETE_OBJECT(&handle);
	}
	g_bloodstain.prop = 0;
}
// Spawn (or respawn after streaming) the physical marker. Cheap to call every
// tick: it returns immediately once a live object exists.
static void ensureBloodstainProp(Ped ped) {
	if (!g_bloodstain.active) { removeBloodstainProp(); return; }
	if (g_bloodstain.prop && ENTITY::DOES_ENTITY_EXIST(g_bloodstain.prop)) return;
	g_bloodstain.prop = 0;
	const Vector3 here = ENTITY_COORDS(ped);
	const float dx = here.x - g_bloodstain.position.x;
	const float dy = here.y - g_bloodstain.position.y;
	if (dx * dx + dy * dy > 120.0f * 120.0f) return;   // out of streaming range
	const Hash model = joaat(g_bloodstainProp.c_str());
	if (!STREAMING::HAS_MODEL_LOADED(model)) { STREAMING::REQUEST_MODEL(model, FALSE); return; }
	g_bloodstain.prop = OBJECT::CREATE_OBJECT(model,
		g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 0.02f,
		FALSE, FALSE, FALSE, FALSE, TRUE);
	if (!g_bloodstain.prop) return;
	ENTITY::SET_ENTITY_AS_MISSION_ENTITY(g_bloodstain.prop, TRUE, TRUE);
	OBJECT::PLACE_OBJECT_ON_GROUND_PROPERLY(g_bloodstain.prop, TRUE);
	ENTITY::FREEZE_ENTITY_POSITION(g_bloodstain.prop, TRUE);
	ENTITY::SET_ENTITY_COLLISION(g_bloodstain.prop, FALSE, FALSE);
}
static void createBloodstainBlip() {
	if (!g_bloodstain.active || g_bloodstain.blip) return;
	g_bloodstain.blip = ADD_COORD_BLIP((Hash)-1337945352, g_bloodstain.position);
	SET_BLIP_ICON(g_bloodstain.blip, joaat(g_bloodstainIcon.c_str()));
	ADD_BLIP_MODIFIER(g_bloodstain.blip, joaat("BLIP_MODIFIER_RADAR_EDGE_ALWAYS"));
	if (g_bloodstainBlipScale > 0.0f) SET_BLIP_SCALE(g_bloodstain.blip, g_bloodstainBlipScale);
	SET_BLIP_NAME(g_bloodstain.blip, "Lost Money");
}
static void placeBloodstain(Vector3 death, int cash) {
	removeBloodstainBlip(); Vector3 safe = death;
	if (!SAFE_PED_COORD(death, &safe)) { float z = death.z; if (GROUND_Z(death, &z)) safe.z = z; }
	removeBloodstainProp();
	g_bloodstain.active = cash > 0; g_bloodstain.cash = cash; g_bloodstain.position = safe;
	saveBloodstain(); createBloodstainBlip();
}
#if 0 // Superseded by modules/always_holster.cpp after the failed repeated-tap test.
// #82: hitting the holster key sometimes just changes his pose and leaves the
// gun in his hands. Selecting fists in the weapon wheel gives the wanted stow
// animation, so the fallback below asks for that same non-forced transition.
static void holsterLog(const std::string& line) {
	if (!g_alwaysHolsterLog) return;
	GtLogStream log("holster", GT_INFO);
	if (log) log << line << "\n";
}

static void updateAlwaysHolster(Ped ped, DWORD now, bool mission) {
	(void)now;
	// EVERY GATE NOW REPORTS ITSELF. Two rounds of this were spent asserting a
	// cause from the script corpus and being wrong, so nothing below is assumed.
	// The first line the log emits on a press names the exact gate that stopped
	// it - and if pressing the key writes NO line at all, the control itself is
	// not what we think it is, which is the one thing that has never been tested.
	if (g_alwaysHolsterLog) {
		static const Hash kProbe = joaat("INPUT_TOGGLE_HOLSTER");
		for (int group = 0; group < 3; ++group) {
			const bool on = PAD::IS_CONTROL_JUST_PRESSED(group, kProbe) != 0;
			const bool off = PAD::IS_DISABLED_CONTROL_JUST_PRESSED(group, kProbe) != 0;
			if (on || off) holsterLog("press group=" + std::to_string(group) +
				(on ? " enabled" : "") + (off ? " disabled" : "") +
				" mission=" + std::to_string(mission ? 1 : 0) +
				" ped=" + std::to_string(ped ? 1 : 0) +
				" featureOn=" + std::to_string(g_alwaysHolster ? 1 : 0));
		}
	}
	if (!g_alwaysHolster || !ped || mission) return;

	// THE CONTROL NAME WAS WRONG AND THAT IS WHY NOTHING EVER HAPPENED.
	// This listened for "INPUT_HOLSTER_WEAPON", which does not exist: it appears
	// nowhere in the whole decompiled script corpus, so joaat() hashed a name the
	// game has never heard of and IS_CONTROL_PRESSED was false on every single
	// frame. The feature has never run once. The real control is
	// INPUT_TOGGLE_HOLSTER, used by Rockstar's own scripts.
	static const Hash kToggleHolster = joaat("INPUT_TOGGLE_HOLSTER");
	if (PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE) || PED::IS_PED_ON_MOUNT(ped)) {
		if (PAD::IS_CONTROL_JUST_PRESSED(0, kToggleHolster))
			holsterLog("stop: mounted or in vehicle");
		return;
	}

	// WHY THE LAST ATTEMPT STILL DID NOTHING. It compared his CURRENT weapon
	// against whatever sat on back slots 9 and 10. A longarm that is in his hands
	// is not on slot 9 or 10 - it is on slot 0, the in-use point - so the two
	// never matched and the function returned on every single press. The slot
	// reads were broken on top of that (wrong p3, see the wrapper above), so both
	// halves of the test were wrong at once.
	//
	// The question worth asking is simply "is anything in his hands right now".
	// Slot 0 answers it directly. If his hands are empty the key is being used to
	// DRAW, and we must stay out of the way; if anything is in them, the key means
	// put it away, so put it away. No longarm special case, no timing window.
	const Hash unarmed = joaat("WEAPON_UNARMED");
	const Hash inHand = GET_WEAPON_AT_ATTACH_POINT(ped, 0);

	if (!inHand || inHand == unarmed) {
		if (PAD::IS_CONTROL_JUST_PRESSED(0, kToggleHolster))
			holsterLog("stop: point 0 reads empty, leaving DRAW to vanilla");
		return;
	}

	// The previous attempt asked for an animated task but left the original Tab
	// action enabled in the same frame. The log proved our request initially left
	// the rifle in point 0; Rockstar's still-running control action then won and
	// attached it to the back instantly. Intercept that action every frame while
	// a weapon is actually in hand, then detect the press through the disabled-
	// control API. Empty-hand Tab returned above and therefore keeps its vanilla
	// draw behavior.
	//
	// Respect another feature's lock (prone/binoculars): if the control was
	// already disabled before this module reached it, do not turn that locked
	// press into a holster request.
	if (!PAD::IS_CONTROL_ENABLED(0, kToggleHolster)) {
		if (PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, kToggleHolster))
			holsterLog("stop: holster control already disabled by another state");
		return;
	}
	PAD::DISABLE_CONTROL_ACTION(0, kToggleHolster, TRUE);
	if (!PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, kToggleHolster)) return;

	// Dump what every point actually holds at the moment of the intercepted
	// press, so the slot map itself can be checked against reality.
	if (g_alwaysHolsterLog) {
		std::string s = "before current=" + std::to_string(GET_CURRENT_WEAPON(ped));
		for (int point : {0, 1, 2, 3, 4, 7, 8, 9, 10})
			s += " p" + std::to_string(point) + "=" +
				std::to_string(GET_WEAPON_AT_ATTACH_POINT(ped, point));
		holsterLog(s);
	}

	// Rockstar's own animated put-away sequence uses all three calls in this
	// order: hide with immediately=false, select WEAPON_UNARMED with the
	// force-in-hand flag false, then start TASK_SWAP_WEAPON in stow mode (0).
	// The old fallback passed true to both immediate/force arguments and omitted
	// the swap task, which explained the instant teleport onto the back.
	HIDE_PED_WEAPONS(ped, 2, false);
	WEAPON::SET_CURRENT_PED_WEAPON(ped, unarmed, FALSE, 0, FALSE, FALSE);
	TASK::TASK_SWAP_WEAPON(ped, 0, 0, 0, 0);

	holsterLog("requested animated stow inHand=" + std::to_string(inHand) +
		" currentNow=" + std::to_string(GET_CURRENT_WEAPON(ped)) +
		" p0Now=" + std::to_string(GET_WEAPON_AT_ATTACH_POINT(ped, 0)) +
		" taskStatus=" + std::to_string(
			TASK::GET_SCRIPT_TASK_STATUS(ped, 716706914, TRUE)));
}
#endif

static void updateBloodstain(Ped ped) {
	if (!g_bloodstain.active) return; createBloodstainBlip(); ensureBloodstainProp(ped);
	Vector3 p = ENTITY_COORDS(ped); float dx=p.x-g_bloodstain.position.x, dy=p.y-g_bloodstain.position.y, dz=p.z-g_bloodstain.position.z;
	if (dx*dx + dy*dy + dz*dz <= 0.42f) {
		int amount = g_bloodstain.cash;
		if (amount > 0 && ADD_CASH(amount)) { g_bloodstain.active = false; g_bloodstain.cash = 0; removeBloodstainBlip(); removeBloodstainProp(); saveBloodstain(); }
	}
	else {
		// #50: gold, wider and taller than the old dark-red version, plus a
		// light so it is findable after dark. The beam still uses 0x94FDAE17,
		// which is world-vertical - that is a defect for tracers (#112) and
		// exactly what is wanted for a fixed ground marker.
		const float s = g_bloodstainMarkerScale;
		const float pulse = 0.85f + 0.15f * sinf(GetTickCount() * 0.004f);
		GRAPHICS::_DRAW_MARKER(kMarkerVerticalCylinder, g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 0.04f,
			0,0,0, 0,0,0, 1.6f*s,1.6f*s,0.06f, 245,190,70,220, FALSE,FALSE,0,FALSE,nullptr,nullptr,FALSE);
		GRAPHICS::_DRAW_MARKER(kMarkerVerticalCylinder, g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 1.60f,
			0,0,0, 0,0,0, 0.26f*s*pulse,0.26f*s*pulse,3.2f, 250,205,105,150, FALSE,FALSE,0,FALSE,nullptr,nullptr,FALSE);
		GRAPHICS::DRAW_LIGHT_WITH_RANGE(g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 0.60f,
			255, 198, 90, 7.0f * s, 3.0f * pulse);
	}
}
#endif

struct VikingVictim { Ped ped = 0; bool looting = false; int cashBefore = 0; };
static std::vector<VikingVictim> g_vikingVictims;
static bool updateVikingVictims(Ped playerPed, bool mission) {
	bool cashChanged = false;
	int nearby[65] = {}; nearby[0] = 32; int count = NEARBY_PEDS(playerPed, nearby);
	if (!mission) for (int i = 0; i < count && i < 32; ++i) {
		Ped victim = nearby[i+1]; if (!victim || !PED::IS_PED_DEAD_OR_DYING(victim, TRUE)) continue;
		if (PED_DEATH_SOURCE(victim) != playerPed || PED_DEATH_CAUSE(victim) != joaat("WEAPON_MELEE_HATCHET_VIKING")) continue;
		if (std::find_if(g_vikingVictims.begin(), g_vikingVictims.end(), [victim](const VikingVictim& v){ return v.ped == victim; }) == g_vikingVictims.end())
			g_vikingVictims.push_back({ victim, false, 0 });
	}
	for (auto it = g_vikingVictims.begin(); it != g_vikingVictims.end();) {
		if (!ENTITY::DOES_ENTITY_EXIST(it->ped)) { it = g_vikingVictims.erase(it); continue; }
		bool looting = PED_LOOTER(it->ped) == playerPed;
		if (looting && !it->looting) { it->looting = true; it->cashBefore = CASH_BALANCE(); }
		else if (!looting && it->looting) {
			int gained = CASH_BALANCE() - it->cashBefore;
			if (gained > 0 && !mission) {
				// #203: the bonus top-up is 4x the rolled loot on top of it.
				// Whether the spec means 4x total is settled by the controlled
				// test, not by editing this line blind. The log below reports
				// rolled and bonus separately so the ratio is measurable.
				const int bonus = gained * 4;
				const bool added = ADD_CASH(bonus);
				cashChanged = added;
				GtLogStream log("viking", GT_INFO);
				log << "hatchet victim=" << (int)it->ped
					<< " rolled=" << gained << " bonus=" << bonus
					<< " added=" << (added ? 1 : 0) << "\n";
			}
			it = g_vikingVictims.erase(it); continue;
		}
		++it;
	}
	return cashChanged;
}

struct SpentCasing {
	Pickup pickup = 0;
	Object object = 0;
	Hash item = 0;
	Hash model = 0;
	DWORD createdAt = 0;
	Vector3 lastPosition = {};
	int fxHandle = 0;         // looped glint ptfx attached to the casing
	DWORD glintStartedAt = 0; // #32 current pulse envelope origin
	DWORD nextGlintAt = 0;    // #32 independently randomized next pulse
	bool isPickup = false;    // spawned through the engine's pickup system
	bool collecting = false;  // reach animation has started; grant at its pickup point
	DWORD collectAt = 0;
};

// a fired round whose casing has not physically ejected yet
struct PendingEject {
	Hash weapon = 0;
	Hash item = 0;
	DWORD firedAt = 0;
	DWORD spawnAt = 0;       // timed ejection (pistols); 0 when waitForCycle
	bool waitForCycle = false; // lever/bolt/pump weapons: eject on re-ready
};

static std::vector<SpentCasing> g_spentCasings;
static std::vector<PendingEject> g_pendingEjects;
static int  g_revolverOwed = 0;      // casings held in the cylinder until reload
static Hash g_revolverOwedItem = 0;
static unsigned g_casingRng = 0xC451A65Eu;
static int  g_casingPrompt = 0;
static bool g_casingPromptRegistered = false;
// #85 THE HOLD BLEEDS INTO VANILLA'S OWN HOLD-E. Our prompt completes on
// SHORT_TIMED_EVENT, which is shorter than the ambient rest hold, so the key is
// usually still down when we grant the casing — and the vanilla rest prompt,
// which watches the same INPUT_LOOT family, keeps counting and fires right
// after. Once a pickup starts, the loot inputs stay suppressed until the key is
// physically released, so the leftover hold cannot reach anything else.
// Suppression deliberately starts at the pickup, never during our own hold:
// DISABLE_CONTROL_ACTION on INPUT_LOOT would otherwise be able to starve our
// prompt too. saloon_dining/theatre_ticket_taker do the same three-input
// disable when they own the loot key.
static bool g_casingLootBlocked = false;

// UIPrompt natives (hashes from the alloc8or db) — this is the game's own
// prompt system; every vanilla loot prompt is one of these.
static int  CASING_PROMPT_BEGIN() { return invoke<int>(0x04F97DE45A519419); }
static void CASING_PROMPT_END(int p) { invoke<Void>(0xF7AA2696A22AD8B9, p); }
static void CASING_PROMPT_CONTROL(int p, Hash action) { invoke<Any>(0xB5352B7494A08258, p, action); }
static void CASING_PROMPT_TEXT(int p, const char* t) { invoke<Void>(0x5DD02A8318420DD7, p, t); }
static void CASING_PROMPT_HOLD(int p, Hash type) { invoke<Void>(0x74C7D7B72ED0D3CF, p, type); }
static void CASING_PROMPT_VISIBLE(int p, BOOL v) { invoke<Void>(0x71215ACCFDE075EE, p, v); }
static void CASING_PROMPT_ENABLED(int p, BOOL v) { invoke<Void>(0x8A0FB4D03A630D21, p, v); }
static bool CASING_PROMPT_DONE(int p) { return invoke<BOOL>(0xE0F65F0640EF0617, p) != 0; }
static void CASING_PROMPT_RESTART(int p) { invoke<Void>(0xDC6C55DFA2C24EE5, p); }
static const char* CASING_LITERAL(const char* t) { return invoke<const char*>(0xFA925AC00EB830B9, 10, "LITERAL_STRING", t); }
static void CASING_SOUND(const char* name, const char* set) { invoke<Void>(0x67C540AA08E4A6F5, name, set, TRUE, 0); }
static void CASING_FEED(const char* text, const char* textureDict, Hash texture);

// #93. shop_post_office exposes its live UI item list through
// Global_1914319.f_16855.f_31. Nested DataBinding containers cannot be fetched
// by passing a slash-delimited string to GET_DATA_CONTAINER_FROM_PATH; retrieve
// each visible row from the real UI list and identify bounty rows by the exact
// uiItemType/uiItemID fields authored by func_1682.
static void updatePartialBounty(Player player, DWORD now) {
	static bool logBooted = false;
	static DWORD lastDiagnostic = 0;
	static DWORD lastPaymentAt = 0;
	static Any armedRowContext = 0;
	static int armedState = -1;
	static bool rowWasArmed = false;
	static const int kBountyRowType = -698448975;
	if (!logBooted) {
		logBooted = true;
		GtLogStream("bounty", GT_INFO)
			<< "session start enabled=" << (g_partialBountyEnabled ? 1 : 0) << "\n";
	}
	Any stateRows[6] = {};
	int validBountyRows = 0;
	const Any genericShop = DATABINDING_CONTAINER("GenericShop");
	const Any itemList = (Any)*getGlobalPtr(1914319 + 16855 + 31);
	const int itemListCount = DATABINDING_VALID(itemList)
		? DATABINDING_ARRAY_COUNT(itemList) : 0;
	for (int index = 0; index < itemListCount && index < 256; ++index) {
		const Any row = DATABINDING_ITEM_CONTEXT(itemList, index);
		if (!DATABINDING_VALID(row) ||
			DATABINDING_READ_INT(row, "uiItemType") != kBountyRowType)
			continue;
		const int state = DATABINDING_READ_INT(row, "uiItemID");
		if (state < 0 || state >= 6) continue;
		stateRows[state] = row;
		validBountyRows++;
	}
	const int selectedIndex = DATABINDING_VALID(genericShop)
		? DATABINDING_READ_INT(genericShop, "ItemListEntryIndex") : -1;
	const Any selectedRow = selectedIndex >= 0 && selectedIndex < itemListCount
		? DATABINDING_ITEM_CONTEXT(itemList, selectedIndex) : 0;
	const bool selectedBountyRow = DATABINDING_VALID(selectedRow) &&
		DATABINDING_READ_INT(selectedRow, "uiItemType") == kBountyRowType;
	const int selectedState = selectedBountyRow
		? DATABINDING_READ_INT(selectedRow, "uiItemID") : -1;
	const bool validState = selectedState >= 0 && selectedState < 6;
	const bool bountyPage = UIAPP_ACTIVE(joaat("SHOP_MENU")) &&
		validBountyRows > 0 &&
		selectedBountyRow && validState;
	const int bounty = validState ?
		(int)*getGlobalPtr(40 + 359 + selectedState * 12) : 0;
	const int cash = CASH_BALANCE();
	const int payment = (std::min)(cash, bounty);
	const bool available = g_partialBountyEnabled && bountyPage &&
		validState && cash < bounty && payment >= g_partialBountyMinPayment;
	const bool selectedEnabledBefore = DATABINDING_VALID(selectedRow) &&
		DATABINDING_READ_BOOL(selectedRow, "itemEnabled");
	// The shop UI disables a row immediately after dispatching its action. That
	// transition is a reliable fallback for mouse activation, but only while the
	// exact same row context that we armed remains selected (pause/rebuilds create
	// a new context and must never be mistaken for a payment).
	const bool rowActivation = available && rowWasArmed &&
		armedRowContext == selectedRow && armedState == selectedState &&
		!selectedEnabledBefore && now - lastPaymentAt >= 350;
	if (UIAPP_ACTIVE(joaat("SHOP_MENU")) && g_partialBountyEnabled) {
		for (int state = 0; state < 6; ++state) {
			if (!DATABINDING_VALID(stateRows[state])) continue;
			const int stateBounty = (int)*getGlobalPtr(40 + 359 + state * 12);
			DATABINDING_WRITE_BOOL(stateRows[state], "itemEnabled",
				stateBounty > 0 && (cash >= stateBounty ||
					cash >= g_partialBountyMinPayment));
		}
	}
	if (now - lastDiagnostic >= 1000) {
		lastDiagnostic = now;
		GtLogStream log("bounty", GT_INFO);
		log << "refs shop_post_office=" << SCRIPT_REFS(joaat("shop_post_office"))
			<< " shop_controller=" << SCRIPT_REFS(joaat("shop_controller"))
			<< " uiShop=" << UIAPP_ACTIVE(joaat("SHOP_MENU"))
			<< " itemList=0x" << std::hex << itemList << std::dec
			<< " listCount=" << itemListCount
			<< " bountyRows=" << validBountyRows << " selectedIndex=" << selectedIndex
			<< " selectedState=" << selectedState
			<< " bounty=" << bounty << " cash=" << cash
			<< " available=" << available << " ledger=";
		for (int state = 0; state < 6; ++state)
			log << (state ? "," : "") << (int)*getGlobalPtr(40 + 359 + state * 12);
		log << "\n";
	}
	auto pressed = [](Hash control) {
		return CONTROL_JUST_PRESSED(0, control) ||
			DISABLED_CONTROL_JUST_PRESSED(0, control) ||
			CONTROL_JUST_PRESSED(2, control) ||
			DISABLED_CONTROL_JUST_PRESSED(2, control);
	};
	const bool shopBuy = pressed(joaat("INPUT_SHOP_BUY"));
	const bool shopBounty = pressed(joaat("INPUT_SHOP_BOUNTY"));
	const bool frontendAccept = pressed(joaat("INPUT_FRONTEND_ACCEPT"));
	const bool accepted = shopBuy || shopBounty || frontendAccept || rowActivation;
	if (available) {
		armedRowContext = selectedRow;
		armedState = selectedState;
		rowWasArmed = true;
	} else {
		armedRowContext = 0;
		armedState = -1;
		rowWasArmed = false;
	}
	if (!available || !accepted) return;

	const int newBounty = bounty - payment;
	lastPaymentAt = now;
	const bool removeReturned = REMOVE_CASH(payment);
	const int cashAfter = CASH_BALANCE();
	const bool cashDebited = cashAfter <= cash - payment;
	{
		GtLogStream log("bounty", GT_INFO);
		log << "pay-activation state=" << selectedState
			<< " buy=" << shopBuy << " bountyControl=" << shopBounty
			<< " frontend=" << frontendAccept << " rowTransition=" << rowActivation
			<< " removeReturned=" << removeReturned
			<< " cashBefore=" << cash << " cashAfter=" << cashAfter << "\n";
	}
	if (cashDebited) {
		*getGlobalPtr(40 + 359 + selectedState * 12) = newBounty;
		const int currentLawState = (int)*getGlobalPtr(1934266 + 4);
		if (currentLawState == selectedState) SET_BOUNTY_VALUE(player, newBounty);
		if (DATABINDING_VALID(stateRows[selectedState])) {
			DATABINDING_WRITE_INT(stateRows[selectedState], "price", newBounty);
			DATABINDING_WRITE_BOOL(stateRows[selectedState], "itemEnabled",
				newBounty > 0 && CASH_BALANCE() >= g_partialBountyMinPayment);
		}
		char text[120];
		sprintf_s(text, "Paid $%d.%02d; bounty remaining $%d.%02d",
			payment / 100, payment % 100, newBounty / 100, newBounty % 100);
		CASING_FEED(text, "", 0);
		GtLogStream("bounty", GT_INFO)
			<< "state=" << selectedState << " old=" << bounty
			<< " paid=" << payment << " new=" << newBounty
			<< " cashAfter=" << cashAfter << "\n";
	} else {
		GtLogStream("bounty", GT_INFO)
			<< "transaction-aborted cash was not debited\n";
	}
}

static int selectedItemCashSellPrice(Hash item) {
	Any price[32] = {};
	price[4] = 10; // capacity used by Rockstar's own satchel script
	if (!invoke<BOOL>(0x7A62A2EEDE1C3766, item, joaat("SELL_SHOP_DEFAULT"), price))
		return -1;
	const int count = (std::max)(0, (std::min)(10, static_cast<int>(price[3])));
	for (int i = 0; i < count; ++i)
		if (static_cast<Hash>(price[4 + i * 2]) == joaat("CURRENCY_CASH"))
			return static_cast<int>(price[5 + i * 2]);
	return -1;
}

// #146/#112. Rockstar's shop script opens the SATCHEL app for merchant purchases
// from the player. PDATA controls which exceptional items enter that satchel;
// an explicit Reject is enforced against the selected catalog item here. The
// direct PromptSelectEnabled DataBinding ID is authored by
// satchel_ui_event_handler and gives the player an honestly greyed-out Sell
// action instead of accepting input and undoing a transaction afterward. The
// same pre-transaction gate prevents a sale that would exceed the wallet cap
// when Auto-Bank is off (or its version-pinned Banking bridge is unavailable).
static void updateMerchantBuyOverrides(DWORD now) {
	static DWORD lastLog = 0;
	static DWORD lastWalletFeed = 0;
	if (SCRIPT_REFS(joaat("satchel")) <= 0) return;
	const Hash shop = static_cast<Hash>(*getGlobalPtr(1914319 + 16855 + 34));
	const Hash item = static_cast<Hash>(*getGlobalPtr(1935689 + 10190));
	if (!shop || !item) return;
	const auto found = g_merchantBuyOverrides.find(merchantOverrideKey(shop, item));
	const bool explicitReject = found != g_merchantBuyOverrides.end() && found->second < 0;
	const int cap = walletActiveCap();
	const int cash = CASH_BALANCE();
	const int price = cap > 0 ? selectedItemCashSellPrice(item) : -1;
	const bool bankReady = walletAutoBank() && walletBankBalance(now) != nullptr;
	const bool walletReject = cap > 0 && !bankReady &&
		((price >= 0 && static_cast<long long>(cash) + price > cap) ||
		 (price < 0 && cash >= cap));
	if (!explicitReject && !walletReject) return;
	const Hash sellControl = joaat("INPUT_SHOP_SELL");
	const bool attempted = CONTROL_JUST_PRESSED(0, sellControl) ||
		DISABLED_CONTROL_JUST_PRESSED(0, sellControl) ||
		CONTROL_JUST_PRESSED(2, sellControl) ||
		DISABLED_CONTROL_JUST_PRESSED(2, sellControl);
	const Any promptSelectEnabled = *getGlobalPtr(1935689 + 10214);
	if (DATABINDING_VALID(promptSelectEnabled))
		DATABINDING_WRITE_BOOL_ID(promptSelectEnabled, false);
	DISABLE_CONTROL(0, sellControl);
	DISABLE_CONTROL(2, sellControl);
	if (walletReject && attempted && now - lastWalletFeed >= 500) {
		lastWalletFeed = now;
		char message[96];
		sprintf_s(message, "Wallet full: limit is $%d.%02d", cap / 100, cap % 100);
		CASING_FEED(message, "", 0);
	}
	if (now - lastLog >= 1000) {
		lastLog = now;
		GtLogStream("merchant-buy", GT_INFO)
			<< "rejected shop=0x" << std::hex << shop
			<< " item=0x" << item << std::dec
			<< " explicit=" << explicitReject << " wallet=" << walletReject
			<< " cash=" << cash << " price=" << price << " cap=" << cap
			<< " autoBankReady=" << bankReady << "\n";
	}
}

// The vanilla item-card feed. Struct layout taken from the GAME'S OWN
// wrapper (abigail2_1.c func_701), not community pastebins:
//   arg1 = { 450, soundSet, soundName, 0 }
//   arg2 = { 0, text, textureDictString, textureHash, 0, colorHash, 0 }
// Arrays are deliberately larger than the script structs: if the native
// reads or writes fields past the documented ones, it hits our zeroed
// slack instead of the stack frame (collect-crash suspect #1).
static void CASING_FEED(const char* text, const char* textureDict, Hash texture) {
	UINT64 a[8] = { 450, 0, 0, 0, 0, 0, 0, 0 };
	UINT64 b[16] = { 0 };
	b[1] = (UINT64)text; b[2] = (UINT64)textureDict; b[3] = (UINT64)texture;
	b[5] = (UINT64)joaat("COLOR_PURE_WHITE");
	invoke<int>(0xB249EBCB30DD88E0, a, b, 1); // _UI_FEED_POST_SAMPLE_TOAST_RIGHT
}

// ---- Persistent authored campsites (#59) ---------------------------------
// The campsite key records the player's current valid outdoor ground position.
// Only the nearest site is materialized. An inactive site uses Rockstar's exact
// burnt-out campfire model. Activation replaces it with Rockstar's player_camp
// script, which owns the complete vanilla sleep/cook/craft/fast-travel set.
// DEFAULT KEY IS F3 (#59): F4 is a vanilla binding and reading it raw left the
// game's own F4 action firing underneath ours.
struct Campsite {
	Vector3 pos;
	float heading;
	bool activated;
	Blip blip;
	Object inactiveFire;
	// #272: one script-owned smoke loop per saved site. The handle lives on the
	// campsite record so vector reload/removal and activation changes cannot
	// accidentally orphan a second plume at the same coordinates.
	int smokeFx;
	bool smokeFxActivated;
};
static std::vector<Campsite> g_campsites;
static bool g_campKeyWasDown = false;
static DWORD g_campKeyPressedAt = 0;
static bool g_campKeyHoldHandled = false;
static bool g_campScriptRequested = false;
static int g_materializedCamp = -1;
static int g_campThread = 0;
static int g_requestedCamp = -1;
static bool g_campCleanupPending = false;
static DWORD g_campCleanupRequestedAt = 0;
static unsigned g_campCleanupAttempts = 0;
static int g_campInactiveOwnerSite = -1;
static DWORD g_campInactiveOwnerSince = 0;
// A rejected/short-lived player_camp launch used to be retried every frame.
// The installed log captured thousands of consecutive thread IDs. Keep retries
// available for streaming failures, but never turn one bad launch into a script
// storm; switching to a different saved site still gets one immediate attempt.
static int g_campLaunchTarget = -1;
static DWORD g_campNextLaunchAt = 0;
static unsigned g_campLaunchAttempts = 0;
static int g_pendingCampRespawn = -1;
static int g_campActivationPrompt = 0;
static bool g_campActivationPromptRegistered = false;
static bool g_campsiteIconDictReady = false;
// The move starts only after Rockstar has returned the live, controllable ped.
// It is issued exactly once behind a black frame; repeating a world-space move
// while collision settles makes the gameplay camera fly between streaming
// origins for the entire retry window.
static bool  g_campRespawnActive = false;
static bool  g_campRespawnTeleported = false;
static Vector3 g_campRespawnTarget = {};
static DWORD g_campRespawnUntil = 0;
// #244: preserve Rockstar's completed death-respawn result before our one-shot
// campsite relocation. If campsite validation later fails, restore this exact
// position/heading so "fallback to vanilla" is literally true.
static Vector3 g_campRespawnVanillaOrigin = {};
static float g_campRespawnVanillaHeading = 0.0f;
static bool g_campRespawnVanillaCaptured = false;
// Failure notices are deferred until the death sequence has returned control;
// a toast emitted on the death screen is easy to miss and does not satisfy the
// player-facing warning contract. String literals have process lifetime.
static const char* g_campRespawnFallbackMessage = nullptr;
static constexpr float kCampsiteFootprintRadius = 30.0f;
// #149: a persisted activation bit is not evidence that player_camp actually
// created its fire. Track absence only while the site is streamed/nearby; far
// camps deliberately have no physical entities and must retain their saved
// activation state until they can be verified locally.
static int g_campPresenceSite = -1;
static DWORD g_campPresenceMissingSince = 0;
static DWORD g_campPresenceHeartbeatAt = 0;
static bool g_campPresenceVerified = false;
static constexpr DWORD kCampsitePresenceGraceMs = 15000;
// #272: smoke is presentation, not physical camp materialization. Keep every
// saved site in the same local streaming neighborhood eligible for its own
// plume instead of limiting smoke to the single nearest materialized camp.
static constexpr float kCampsiteSmokeRangeMeters = 120.0f;
static constexpr DWORD kCampsiteSmokeUpdateMs = 100;
static DWORD g_campsiteSmokeNextUpdate = 0;

static void requestPlayerCampCleanup(const char* reason) {
	// The two reproduced #163 failures occurred immediately after the
	// thread-id cleanup native was called for the ScriptHook-started
	// player_camp thread. Rockstar's own scripts provide a separate,
	// name-addressed cleanup path for externally owned scripts. There can be
	// only one player_camp here: materialization refuses to start while any
	// player_camp reference exists. Address that exact owner by name so its
	// authored HAS_FORCE_CLEANUP_OCCURRED(555) branch still runs, without
	// passing ScriptHook's returned thread id back into the crashing native.
	const int refsBefore = SCRIPT_REFS(joaat("player_camp"));
	const DWORD now = GetTickCount();
	if (refsBefore <= 0 || g_campCleanupPending || g_campCleanupAttempts >= 2)
		return;
	GtLogStream("campsites", GT_INFO)
		<< "cleanup request path=name reason=" << (reason ? reason : "unknown")
		<< " trackedThread=" << g_campThread
		<< " active=" << (SCRIPT_THREAD_ACTIVE(g_campThread) ? 1 : 0)
		<< " refsBefore=" << refsBefore
		<< " attempt=" << (g_campCleanupAttempts + 1) << "\n";
	invoke<Void>(0xDAACAF8B687F2353, "player_camp", 555);
	g_campCleanupPending = true;
	g_campCleanupRequestedAt = now;
	++g_campCleanupAttempts;
}

static void updatePlayerCampCleanupReadback(DWORD now) {
	const int refs = SCRIPT_REFS(joaat("player_camp"));
	const bool trackedActive = SCRIPT_THREAD_ACTIVE(g_campThread);
	if (refs <= 0 && !trackedActive) {
		if (g_campCleanupPending || g_campCleanupAttempts) {
			GtLogStream("campsites", GT_INFO)
				<< "cleanup accepted refs=0 trackedActive=0 attempts="
				<< g_campCleanupAttempts << "\n";
		}
		g_campCleanupPending = false;
		g_campCleanupRequestedAt = 0;
		g_campCleanupAttempts = 0;
		g_campThread = 0;
		g_materializedCamp = -1;
		return;
	}
	if (g_campCleanupPending && now - g_campCleanupRequestedAt >= 15000) {
		GtLogStream("campsites", GT_WARN)
			<< "cleanup unconfirmed refs=" << refs
			<< " trackedActive=" << (trackedActive ? 1 : 0)
			<< " attempt=" << g_campCleanupAttempts << "\n";
		g_campCleanupPending = false;
		g_campCleanupRequestedAt = 0;
	}
}

static Any campFloatArg(float value) {
	unsigned bits = 0;
	memcpy(&bits, &value, sizeof(bits));
	return (Any)bits;
}

static float campDistanceSq(Vector3 a, Vector3 b) {
	const float x = a.x - b.x, y = a.y - b.y, z = a.z - b.z;
	return x * x + y * y + z * z;
}

static Object campsitePhysicalFire(const Campsite& campsite) {
	// player_camp.c func_107 creates P_CAMPFIRE02X_COMBO with NO_OFFSET at
	// uParam0->f_4, the explicit coordinate supplied from this saved row.
	const Object fire = OBJECT::GET_CLOSEST_OBJECT_OF_TYPE(
		campsite.pos.x, campsite.pos.y, campsite.pos.z, 1.5f,
		joaat("P_CAMPFIRE02X_COMBO"), false, false, true);
	return fire && ENTITY::DOES_ENTITY_EXIST(fire) ? fire : 0;
}

static Object campsitePhysicalFireNear(Vector3 position, float radius) {
	const Object fire = OBJECT::GET_CLOSEST_OBJECT_OF_TYPE(
		position.x, position.y, position.z, radius,
		joaat("P_CAMPFIRE02X_COMBO"), false, false, true);
	return fire && ENTITY::DOES_ENTITY_EXIST(fire) ? fire : 0;
}

// player_camp.c func_69 names P_CAMPFIREBURNTOUT02X as its unlit model, and
// func_107 creates and freezes that model at the camp origin before it creates
// the lit P_CAMPFIRE02X_COMBO. An inactive authored site owns only this exact
// unlit model. Starting player_camp would create a complete usable camp and
// would therefore make an inactive saved row disagree with the world.
static void removeInactiveCampsiteFire(Campsite& campsite) {
	if (campsite.inactiveFire && ENTITY::DOES_ENTITY_EXIST(campsite.inactiveFire)) {
		ENTITY::SET_ENTITY_AS_MISSION_ENTITY(campsite.inactiveFire, TRUE, TRUE);
		Object handle = campsite.inactiveFire;
		OBJECT::DELETE_OBJECT(&handle);
	}
	campsite.inactiveFire = 0;
}

static Object ensureInactiveCampsiteFire(Campsite& campsite, int index) {
	if (campsite.activated) {
		removeInactiveCampsiteFire(campsite);
		return 0;
	}
	if (campsite.inactiveFire && ENTITY::DOES_ENTITY_EXIST(campsite.inactiveFire))
		return campsite.inactiveFire;
	campsite.inactiveFire = 0;
	const Hash model = joaat("P_CAMPFIREBURNTOUT02X");
	if (!STREAMING::HAS_MODEL_LOADED(model)) {
		STREAMING::REQUEST_MODEL(model, FALSE);
		return 0;
	}
	Object fire = OBJECT::CREATE_OBJECT(model,
		campsite.pos.x, campsite.pos.y, campsite.pos.z,
		TRUE, TRUE, FALSE, FALSE, TRUE);
	if (!fire || !ENTITY::DOES_ENTITY_EXIST(fire)) {
		GtLogStream("campsites", GT_WARN)
			<< "inactive fire create failed site=" << index << "\n";
		return 0;
	}
	ENTITY::SET_ENTITY_AS_MISSION_ENTITY(fire, TRUE, TRUE);
	ENTITY::FREEZE_ENTITY_POSITION(fire, TRUE);
	campsite.inactiveFire = fire;
	STREAMING::SET_MODEL_AS_NO_LONGER_NEEDED(model);
	GtLogStream("campsites", GT_INFO)
		<< "inactive fire verified site=" << index << " fire=" << fire << "\n";
	return fire;
}

// #272: a persistent coordinate particle is intentionally separate from the
// active/inactive fire object. Active camps are owned by player_camp while
// inactive sites own only P_CAMPFIREBURNTOUT02X; tying smoke to either entity
// would make the plume disappear during that ownership handoff.
static void stopCampsiteSmoke(Campsite& campsite) {
	if (campsite.smokeFx) {
		if (GRAPHICS::DOES_PARTICLE_FX_LOOPED_EXIST(campsite.smokeFx))
			GRAPHICS::STOP_PARTICLE_FX_LOOPED(campsite.smokeFx, FALSE);
		campsite.smokeFx = 0;
	}
	campsite.smokeFxActivated = false;
}

static void stopAllCampsiteSmoke() {
	for (Campsite& campsite : g_campsites) stopCampsiteSmoke(campsite);
	g_campsiteSmokeNextUpdate = 0;
}

static void updateCampsiteSmoke(Ped ped, DWORD now, bool enabled) {
	if (!enabled || !ped || !ENTITY::DOES_ENTITY_EXIST(ped)) {
		stopAllCampsiteSmoke();
		return;
	}

	// Request immediately and retry every frame until resident. Do not arm the
	// 100 ms maintenance cadence until the asset is actually available: that
	// removes the old one-second first-plume delay completely.
	const Hash asset = joaat("core");
	if (!invoke<BOOL>(0x65BB72F29138F5D6, asset)) {
		STREAMING::REQUEST_NAMED_PTFX_ASSET(asset);
		g_campsiteSmokeNextUpdate = 0;
		return;
	}
	if (g_campsiteSmokeNextUpdate && now < g_campsiteSmokeNextUpdate) return;
	g_campsiteSmokeNextUpdate = now + kCampsiteSmokeUpdateMs;

	const Vector3 playerPos = ENTITY_COORDS(ped);
	const float rangeSq = kCampsiteSmokeRangeMeters * kCampsiteSmokeRangeMeters;
	for (int i = 0; i < (int)g_campsites.size(); ++i) {
		Campsite& campsite = g_campsites[i];
		const bool wanted = campDistanceSq(playerPos, campsite.pos) <= rangeSq;
		if (!wanted) {
			stopCampsiteSmoke(campsite);
			continue;
		}

		if (campsite.smokeFx &&
			!GRAPHICS::DOES_PARTICLE_FX_LOOPED_EXIST(campsite.smokeFx)) {
			campsite.smokeFx = 0;
			campsite.smokeFxActivated = false;
		}
		// The color is fixed by activation state. Replace the existing handle on
		// the first <=100 ms maintenance pass after activation/deactivation rather
		// than layering another plume over it.
		if (campsite.smokeFx && campsite.smokeFxActivated != campsite.activated)
			stopCampsiteSmoke(campsite);
		if (campsite.smokeFx) continue;

		GRAPHICS::USE_PARTICLE_FX_ASSET("core");
		const int handle = invoke<int>(0xBA32867E86125D3A,
			"core_smoke", campsite.pos.x, campsite.pos.y, campsite.pos.z + 0.15f,
			0.0f, 0.0f, 0.0f, 0.75f, FALSE, FALSE, FALSE, FALSE);
		if (!handle) {
			GtLogStream("campsites", GT_WARN)
				<< "smoke start failed site=" << i
				<< " activated=" << (campsite.activated ? 1 : 0) << "\n";
			continue;
		}
		campsite.smokeFx = handle;
		campsite.smokeFxActivated = campsite.activated;
		const float shade = campsite.activated ? 1.0f : 0.02f;
		GRAPHICS::SET_PARTICLE_FX_LOOPED_COLOUR(handle,
			shade, shade, shade, FALSE);
		GRAPHICS::SET_PARTICLE_FX_LOOPED_ALPHA(handle, 0.82f);
		GtLogStream("campsites", GT_INFO)
			<< "smoke started site=" << i << " handle=" << handle
			<< " activated=" << (campsite.activated ? 1 : 0)
			<< " shade=" << shade << "\n";
	}
}

static void campMessage(const char* text) {
	// The retained F3 crash trace names campMessage.showTooltip at the exact
	// RDR2 access violation. Both a raw literal and _CREATE_VAR_STRING crashed
	// inside that undocumented feed ABI. Never call it again from ScriptHook.
	// Status remains in the unified log; gameplay state changes above/below this
	// helper do not depend on presentation and continue to receive readbacks.
	GtLogStream("campsites", GT_INFO)
		<< "status ui=omitted reason=unsafe-show-tooltip text="
		<< (text ? text : "") << "\n";
}

// #244: death-respawn warnings use the already-proven sample-toast feed rather
// than campMessage(), whose old tooltip ABI is intentionally disabled. This is
// called only on terminal fallback edges, never per frame.
static void campRespawnNotify(const char* text) {
	if (!text || !text[0]) return;
	CASING_FEED(text, "", 0);
	GtLogStream("campsites", GT_INFO)
		<< "respawn notification text=" << text << "\n";
}

static void saveCampsites() {
	std::ofstream out(g_moduleDir + "\\campsites.csv", std::ios::trunc);
	out << "# x,y,z,heading,activated\n";
	out << std::fixed << std::setprecision(3);
	for (const Campsite& c : g_campsites)
		out << c.pos.x << "," << c.pos.y << "," << c.pos.z << ","
			<< c.heading << "," << (c.activated ? 1 : 0) << "\n";
}

static void refreshCampsiteBlip(Campsite& c) {
	if (!c.blip) c.blip = ADD_COORD_BLIP((Hash)-1337945352, c.pos);
	SET_BLIP_ICON(c.blip, campsiteStateBlipIcon(c.activated));
	SET_BLIP_NAME(c.blip, c.activated ? "Activated Campsite" : "Campsite");
}

static void updateCampsiteIconStreaming() {
	const bool ready = campsiteIconTexturesReady();
	if (ready && !g_campsiteIconDictReady) {
		// A request issued while a blip is first created does not make the custom
		// texture synchronously available. Reassign every inactive marker on the
		// first loaded frame (and again after any unexpected eviction/reload).
		for (Campsite& c : g_campsites)
			if (!c.activated && c.blip)
				SET_BLIP_ICON(c.blip, joaat("LEX_BLIP_CAMPFIRE_INACTIVE"));
		GtLogStream log("campsites", GT_INFO);
		if (log) log << "inactive-icon dictionary-ready refreshed\n";
	}
	g_campsiteIconDictReady = ready;
}

static void loadCampsites() {
	for (Campsite& c : g_campsites) {
		if (c.blip) REMOVE_MAP_BLIP(&c.blip);
		stopCampsiteSmoke(c);
		removeInactiveCampsiteFire(c);
	}
	g_campsiteSmokeNextUpdate = 0;
	g_campsites.clear();
	std::ifstream in(g_moduleDir + "\\campsites.csv");
	std::string line;
	while (std::getline(in, line)) {
		if (line.empty() || line[0] == '#') continue;
		std::replace(line.begin(), line.end(), ',', ' ');
		std::istringstream row(line);
		Campsite c = {};
		int active = 0;
		if (!(row >> c.pos.x >> c.pos.y >> c.pos.z >> c.heading >> active)) continue;
		c.activated = active != 0;
		g_campsites.push_back(c);
	}
	for (Campsite& c : g_campsites) refreshCampsiteBlip(c);
	GtLogStream("campsites", GT_INFO)
		<< "session-start loaded-sites=" << g_campsites.size()
		<< "\n";
}

static bool validCampsite(Ped ped, Vector3* placed) {
	if (!ped || ENTITY_INTERIOR(ped)) return false;
	Vector3 p = ENTITY_COORDS(ped), normal = {};
	float ground = 0.0f;
	if (!GROUND_Z_NORMAL(p, &ground, &normal) || normal.z < 0.82f) return false;
	float water = 0.0f;
	if (WATER_HEIGHT(p, &water) && water > ground + 0.15f) return false;
	p.z = ground;
	// Prevent overlap, but do not reject an otherwise valid campsite merely
	// because another authored site exists somewhere in the same neighborhood.
	// The physical camp's rest/tent positions can sit well away from its saved
	// fire origin. Use the same authored-camp radius as removal so tapping F3
	// while resting there cannot place a duplicate camp on top of it.
	for (const Campsite& c : g_campsites)
		if (campDistanceSq(p, c.pos) <
			kCampsiteFootprintRadius * kCampsiteFootprintRadius) return false;
	*placed = p;
	return true;
}

static void materializeCampsite(int index) {
	if (index < 0 || index >= (int)g_campsites.size()) return;
	Campsite& c = g_campsites[index];
	const DWORD now = GetTickCount();
	if (g_campLaunchTarget != index) {
		g_campLaunchTarget = index;
		g_campNextLaunchAt = 0;
		g_campLaunchAttempts = 0;
	}
	if (g_materializedCamp == index && SCRIPT_THREAD_ACTIVE(g_campThread)) {
		if (c.activated) {
			g_campLaunchAttempts = 0;
			return;
		}
	}
	// player_camp owns exactly one physical camp. The old code saw any running
	// instance, relabelled it as the new site, and returned—leaving the new map
	// marker with no campsite. Ask our previous instance to run its authored
	// cleanup, then start the requested location after it exits.
	if (SCRIPT_THREAD_ACTIVE(g_campThread)) {
		// Cleanup is asynchronous. Do not request it again every frame while the
		// same switch is already pending.
		if (!g_campScriptRequested || g_requestedCamp != index) {
			g_requestedCamp = index;
			g_campScriptRequested = true;
			requestPlayerCampCleanup("switch-site");
		}
		return;
	}
	if (g_campThread && !SCRIPT_THREAD_ACTIVE(g_campThread)) {
		g_campThread = 0;
		g_materializedCamp = -1;
	}
	if (SCRIPT_REFS(joaat("player_camp")) > 0) return;
	if (!c.activated) {
		g_requestedCamp = -1;
		g_campScriptRequested = false;
		g_materializedCamp = -1;
		ensureInactiveCampsiteFire(c, index);
		return;
	}
	removeInactiveCampsiteFire(c);
	if (g_campNextLaunchAt && now < g_campNextLaunchAt) return;
	REQUEST_SCRIPT("player_camp");
	g_campScriptRequested = true;
	g_requestedCamp = index;
	if (!SCRIPT_LOADED("player_camp")) return;
	Any args[10] = {};
	args[0] = 2048; // explicit-position path used by respawn_persistence.c
	args[6] = campFloatArg(c.pos.x);
	args[7] = campFloatArg(c.pos.y);
	args[8] = campFloatArg(c.pos.z);
	args[9] = campFloatArg(c.heading);
	const int thread = START_SCRIPT_ARGS("player_camp", args, 10, 6096);
	if (thread) {
		g_campCleanupPending = false;
		g_campCleanupRequestedAt = 0;
		g_campCleanupAttempts = 0;
		++g_campLaunchAttempts;
		g_campNextLaunchAt = now + 5000;
		g_campThread = thread;
		g_materializedCamp = index;
		g_requestedCamp = -1;
		g_campScriptRequested = false;
		GtLogStream log("campsites", GT_INFO);
		log << "started player_camp thread=" << thread << " site="
			<< index << " attempt=" << g_campLaunchAttempts << "\n";
	} else {
		g_campNextLaunchAt = now + 1000;
		GtLogStream("campsites", GT_INFO)
			<< "player_camp start returned 0 site=" << index << "\n";
	}
}

static void ensureCampActivationPrompt() {
	if (g_campActivationPromptRegistered) return;
	g_campActivationPrompt = CASING_PROMPT_BEGIN();
	CASING_PROMPT_CONTROL(g_campActivationPrompt, joaat("INPUT_CONTEXT_X"));
	CASING_PROMPT_TEXT(g_campActivationPrompt, CASING_LITERAL("Activate Campsite"));
	CASING_PROMPT_HOLD(g_campActivationPrompt, joaat("SHORT_TIMED_EVENT"));
	CASING_PROMPT_END(g_campActivationPrompt);
	CASING_PROMPT_VISIBLE(g_campActivationPrompt, FALSE);
	CASING_PROMPT_ENABLED(g_campActivationPrompt, FALSE);
	g_campActivationPromptRegistered = true;
}

static void updateCampsites(Player player, Ped ped, DWORD now, bool dead, bool mission) {
	updateCampsiteIconStreaming();
	updatePlayerCampCleanupReadback(now);
	// Smoke presentation owns no gameplay state, so maintain/clean it before any
	// of the authoring/materialization early returns below.
	updateCampsiteSmoke(ped, now, ped && !dead && !mission);
	bool ownedCampActive = false;
	if (!mission && ped) {
		const Vector3 p = ENTITY_COORDS(ped);
		for (const Campsite& c : g_campsites) {
			if (campDistanceSq(p, c.pos) <
				kCampsiteFootprintRadius * kCampsiteFootprintRadius) {
				ownedCampActive = true;
				break;
			}
		}
		// A running player_camp can survive without a recoverable saved-row or
		// transient launcher association. The F3 recovery path already uses this
		// exact authoritative pair: Rockstar's player-camp fire model near Arthur
		// plus a live player_camp script reference. Free-roam kits are banked, so a
		// live owner here is also part of the authored-camp policy.
		if (!ownedCampActive && campsitePhysicalFireNear(p, 10.0f) &&
			SCRIPT_REFS(joaat("player_camp")) > 0)
			ownedCampActive = true;
	}
	protectAuthoredCampTeardown(ownedCampActive, now);

	const bool campKey = (GetAsyncKeyState(g_campKey) & 0x8000) != 0;
	// The key is read raw from the keyboard, so whatever RDR2 also has bound to
	// it still fires. On the old F4 default that opened the item/satchel wheel on
	// top of placing a campsite. F3 is unbound in vanilla, so this only matters
	// if the key is pointed back at a bound one — swallow the menu controls
	// while it is physically down either way.
	if (campKey) {
		static const Hash kCampBlocked[] = {
			joaat("INPUT_OPEN_WHEEL_MENU"), joaat("INPUT_OPEN_SATCHEL_MENU"),
			joaat("INPUT_OPEN_JOURNAL"), joaat("INPUT_SELECT_WEAPON"),
		};
		for (int group = 0; group < 3; ++group)
			for (Hash control : kCampBlocked) DISABLE_CONTROL(group, control);
	}
	const bool canAuthor = ped && !dead && !mission && PLAYER_CONTROL_ON(player);
	if (campKey && !g_campKeyWasDown) {
		g_campKeyPressedAt = now;
		g_campKeyHoldHandled = false;
	}
	if (campKey && g_campKeyWasDown && !g_campKeyHoldHandled && canAuthor &&
		now - g_campKeyPressedAt >= 800) {
		const Vector3 p = ENTITY_COORDS(ped);
		int nearestRemove = -1;
		// Saved coordinates are the campfire origin, while Arthur can be resting
		// at the tent/bed on the edge of the authored layout. Eight metres rejected
		// a real active campsite; thirty still requires an intentional long hold
		// in that campsite's immediate footprint.
		float nearestRemoveD2 =
			kCampsiteFootprintRadius * kCampsiteFootprintRadius;
		for (int i = 0; i < (int)g_campsites.size(); ++i) {
			const float d2 = campDistanceSq(p, g_campsites[i].pos);
			if (d2 < nearestRemoveD2) {
				nearestRemoveD2 = d2;
				nearestRemove = i;
			}
		}
		// A live player_camp can survive a process restart without this module's
		// transient g_materializedCamp index. It can also be physically near the
		// player while no saved origin is inside the 30 m authoring footprint.
		// Accept only Rockstar's exact player-camp fire model near Arthur plus a
		// live player_camp script reference; this cannot target an arbitrary world
		// campfire. If our transient index still exists, associate that exact row.
		const Object nearbyPlayerCampFire = campsitePhysicalFireNear(p, 10.0f);
		const int playerCampRefs = SCRIPT_REFS(joaat("player_camp"));
		if (nearestRemove < 0 && nearbyPlayerCampFire && playerCampRefs > 0 &&
			g_materializedCamp >= 0 &&
			g_materializedCamp < (int)g_campsites.size()) {
			nearestRemove = g_materializedCamp;
			nearestRemoveD2 = campDistanceSq(p, g_campsites[nearestRemove].pos);
		}
		{
			GtLogStream log("campsites", GT_INFO);
			log << "removal-hold player=" << p.x << "," << p.y << ","
				<< p.z << " sites=" << g_campsites.size() << " nearest=" << nearestRemove
				<< " nearbyPhysicalFire=" << nearbyPlayerCampFire
				<< " playerCampRefs=" << playerCampRefs
				<< " materialized=" << g_materializedCamp;
			if (nearestRemove >= 0) log << " distance=" << sqrtf(nearestRemoveD2);
			log << "\n";
		}
		if (nearestRemove >= 0) {
			const bool removingMaterialized = g_materializedCamp == nearestRemove;
			stopCampsiteSmoke(g_campsites[nearestRemove]);
			removeInactiveCampsiteFire(g_campsites[nearestRemove]);
			if (removingMaterialized && SCRIPT_THREAD_ACTIVE(g_campThread))
				requestPlayerCampCleanup("remove-site");
			if (g_campsites[nearestRemove].blip)
				REMOVE_MAP_BLIP(&g_campsites[nearestRemove].blip);
			g_campsites.erase(g_campsites.begin() + nearestRemove);
			if (removingMaterialized) g_materializedCamp = -1;
			else if (g_materializedCamp > nearestRemove) --g_materializedCamp;
			if (g_requestedCamp == nearestRemove) {
				g_requestedCamp = -1;
				g_campScriptRequested = false;
			} else if (g_requestedCamp > nearestRemove) --g_requestedCamp;
			if (g_campLaunchTarget == nearestRemove) {
				g_campLaunchTarget = -1;
				g_campNextLaunchAt = 0;
				g_campLaunchAttempts = 0;
			} else if (g_campLaunchTarget > nearestRemove) --g_campLaunchTarget;
			if (g_pendingCampRespawn == nearestRemove) g_pendingCampRespawn = -1;
			else if (g_pendingCampRespawn > nearestRemove) --g_pendingCampRespawn;
			saveCampsites();
			campMessage("Campsite removed.");
		} else if (nearbyPlayerCampFire && playerCampRefs > 0) {
			// The physical camp is authoritative even when its persisted row cannot
			// be recovered. Clean up only the exact player_camp owner; do not guess
			// which unrelated saved coordinate should be erased.
			requestPlayerCampCleanup("remove-orphan-physical");
			GtLogStream("campsites", GT_WARN)
				<< "removed orphan physical player_camp fire=" << nearbyPlayerCampFire
				<< " refs=" << playerCampRefs << " savedRow=unchanged\n";
			campMessage("Campsite removed; no matching saved marker was found.");
		} else campMessage("Stand at an authored campsite to remove it.");
		g_campKeyHoldHandled = true;
	}
	if (!campKey && g_campKeyWasDown && !g_campKeyHoldHandled && canAuthor) {
		Vector3 p = {};
		if (validCampsite(ped, &p)) {
			Campsite c = {};
			c.pos = p;
			c.heading = ENTITY_HEADING(ped);
			g_campsites.push_back(c);
			refreshCampsiteBlip(g_campsites.back());
			saveCampsites();
			materializeCampsite((int)g_campsites.size() - 1);
			campMessage("Inactive campsite placed. Activate it to use the full camp.");
		} else campMessage("This is not a valid camping area.");
	}
	g_campKeyWasDown = campKey;
	if (!ped || dead || mission) return;

	const Vector3 playerPos = ENTITY_COORDS(ped);
	int nearest = -1;
	float nearestD2 = 120.0f * 120.0f;
	for (int i = 0; i < (int)g_campsites.size(); ++i) {
		const float d2 = campDistanceSq(playerPos, g_campsites[i].pos);
		if (d2 < nearestD2) { nearestD2 = d2; nearest = i; }
	}
	for (int i = 0; i < (int)g_campsites.size(); ++i)
		if (i != nearest) removeInactiveCampsiteFire(g_campsites[i]);
	if (nearest < 0 &&
		(g_materializedCamp >= 0 || g_campThread || g_campScriptRequested)) {
		requestPlayerCampCleanup("left-materialization-range");
	}
	if (nearest >= 0 && (g_materializedCamp != nearest ||
		SCRIPT_REFS(joaat("player_camp")) == 0 || g_campScriptRequested))
		materializeCampsite(g_requestedCamp >= 0 ? g_requestedCamp : nearest);

	// Same thirty-metre streamed footprint as the authored camp, written as its
	// square here so #116's three ownership/removal/placement uses stay distinct.
	const bool presenceRange = nearest >= 0 && nearestD2 < 900.0f;
	const Object activeFire = presenceRange ?
		campsitePhysicalFire(g_campsites[nearest]) : 0;
	const Object inactiveFire = presenceRange && !g_campsites[nearest].activated &&
		SCRIPT_REFS(joaat("player_camp")) == 0 ?
		ensureInactiveCampsiteFire(g_campsites[nearest], nearest) : 0;
	const Object physicalFire = presenceRange ?
		(g_campsites[nearest].activated ? activeFire : inactiveFire) : 0;
	const int playerCampRefs = SCRIPT_REFS(joaat("player_camp"));
	if (presenceRange && g_campsites[nearest].activated && activeFire &&
		playerCampRefs > 0 && g_materializedCamp < 0 && !g_campThread) {
		g_materializedCamp = nearest;
		GtLogStream("campsites", GT_INFO)
			<< "recovered player_camp ownership site=" << nearest
			<< " fire=" << activeFire << " refs=" << playerCampRefs << "\n";
	}
	if (presenceRange && !g_campsites[nearest].activated && playerCampRefs > 0) {
		if (g_campInactiveOwnerSite != nearest) {
			g_campInactiveOwnerSite = nearest;
			g_campInactiveOwnerSince = now;
			GtLogStream("campsites", GT_WARN)
				<< "inactive site has player_camp owner site=" << nearest
				<< " refs=" << playerCampRefs << " cleanupDelayMs=2000\n";
		} else if (now - g_campInactiveOwnerSince >= 2000) {
			requestPlayerCampCleanup("inactive-site-orphan-owner");
		}
	} else {
		g_campInactiveOwnerSite = -1;
		g_campInactiveOwnerSince = 0;
	}
	if (!presenceRange) {
		g_campPresenceSite = -1;
		g_campPresenceMissingSince = 0;
		g_campPresenceVerified = false;
	} else {
		if (g_campPresenceSite != nearest) {
			g_campPresenceSite = nearest;
			g_campPresenceMissingSince = physicalFire ? 0 : now;
			g_campPresenceVerified = physicalFire != 0;
			GtLogStream("campsites", GT_INFO)
				<< "presence begin site=" << nearest
				<< " activated=" << (g_campsites[nearest].activated ? 1 : 0)
				<< " physical=" << (physicalFire ? 1 : 0)
				<< " trackedThread=" << (SCRIPT_THREAD_ACTIVE(g_campThread) ? 1 : 0)
				<< " refs=" << SCRIPT_REFS(joaat("player_camp")) << "\n";
		}
		if (physicalFire) {
			if (!g_campPresenceVerified) {
				GtLogStream("campsites", GT_INFO)
					<< "physical camp verified site=" << nearest
					<< " fire=" << physicalFire << "\n";
			}
			g_campPresenceVerified = true;
			g_campPresenceMissingSince = 0;
		} else {
			if (!g_campPresenceMissingSince) g_campPresenceMissingSince = now;
			const DWORD missingMs = now - g_campPresenceMissingSince;
			if (now - g_campPresenceHeartbeatAt >= 1000) {
				g_campPresenceHeartbeatAt = now;
				GtLogStream("campsites", GT_INFO)
					<< "physical camp missing site=" << nearest
					<< " activated=" << (g_campsites[nearest].activated ? 1 : 0)
					<< " missingMs=" << missingMs
					<< " tracked=" << g_materializedCamp
					<< " threadActive=" << (SCRIPT_THREAD_ACTIVE(g_campThread) ? 1 : 0)
					<< " refs=" << SCRIPT_REFS(joaat("player_camp")) << "\n";
			}
			// Do not destroy the authored row: it is still a recoverable campsite
			// location. Remove only the false activation after a full local
			// streaming/materialization window; the inactive marker can become
			// activatable again only after a real campfire is observed.
			if (g_campsites[nearest].activated &&
				missingMs >= kCampsitePresenceGraceMs) {
				g_campsites[nearest].activated = false;
				refreshCampsiteBlip(g_campsites[nearest]);
				saveCampsites();
				GtLogStream("campsites", GT_WARN)
					<< "demoted false activation site=" << nearest
					<< " reason=no-physical-camp missingMs=" << missingMs << "\n";
				campMessage("Campsite activation cleared: no physical camp loaded here.");
			}
		}
	}

	ensureCampActivationPrompt();
	const bool canActivate = nearest >= 0 && nearestD2 < 5.0f * 5.0f &&
		physicalFire && !g_campsites[nearest].activated && PLAYER_CONTROL_ON(player);
	CASING_PROMPT_VISIBLE(g_campActivationPrompt, canActivate);
	CASING_PROMPT_ENABLED(g_campActivationPrompt, canActivate);
	if (canActivate && CASING_PROMPT_DONE(g_campActivationPrompt)) {
		removeInactiveCampsiteFire(g_campsites[nearest]);
		g_campsites[nearest].activated = true;
		refreshCampsiteBlip(g_campsites[nearest]);
		saveCampsites();
		GtLogStream("campsites", GT_INFO)
			<< "activated verified physical camp site=" << nearest
			<< " source=inactive-fire"
			<< " fire=" << physicalFire << "\n";
		CASING_PROMPT_RESTART(g_campActivationPrompt);
		campMessage("Campsite activated. You can now respawn here.");
		g_campPresenceSite = -1;
		g_campPresenceMissingSince = 0;
		g_campPresenceVerified = false;
		materializeCampsite(nearest);
	}
}

static int nearestActivatedCampsite(Vector3 p) {
	int best = -1;
	float bestD2 = 1.0e30f;
	for (int i = 0; i < (int)g_campsites.size(); ++i) {
		if (!g_campsites[i].activated) continue;
		const float d2 = campDistanceSq(p, g_campsites[i].pos);
		if (d2 < bestD2) { bestD2 = d2; best = i; }
	}
	return best;
}

// GitHub #73: c.pos is the fire itself. player_camp creates
// P_CAMPFIRE02X_COMBO at that exact coordinate, so using c.pos as the death
// destination necessarily respawned Arthur in the flames. Choose a heading-
// relative point outside the campfire instead, and validate the actual terrain
// before moving him. There is deliberately no c.pos fallback: timing out at the
// vanilla respawn is safer than ever putting the player on the fire again.
static bool campsiteRespawnPosition(const Campsite& c, Vector3* out) {
	static const float offsets[][2] = {
		{ 4.0f,  0.0f }, { -4.0f,  0.0f },
		{ 0.0f, -4.0f }, {  0.0f,  4.0f },
		{ 3.5f, -3.5f }, { -3.5f, -3.5f },
		{ 3.5f,  3.5f }, { -3.5f,  3.5f },
	};
	for (const auto& offset : offsets) {
		Vector3 candidate = OFFSET_FROM_COORDS(c.pos, c.heading, offset[0], offset[1], 0.0f);
		float ground = 0.0f;
		Vector3 normal = {};
		if (!GROUND_Z_NORMAL(candidate, &ground, &normal) || normal.z < 0.82f)
			continue;
		if (std::fabs(ground - c.pos.z) > 2.5f) continue;
		float water = 0.0f;
		if (WATER_HEIGHT(candidate, &water) && water > ground + 0.15f) continue;
		candidate.z = ground + 0.05f;

		Vector3 safe = {};
		if (SAFE_PED_COORD(candidate, &safe) &&
			campDistanceSq(safe, c.pos) >= 3.0f * 3.0f &&
			campDistanceSq(safe, candidate) <= 2.0f * 2.0f) {
			float safeGround = 0.0f;
			Vector3 safeNormal = {};
			if (GROUND_Z_NORMAL(safe, &safeGround, &safeNormal) && safeNormal.z >= 0.82f) {
				safe.z = safeGround + 0.05f;
				*out = safe;
				return true;
			}
		}

		// Campsites themselves require flat, dry outdoor ground. If navmesh safe-
		// coord discovery is temporarily unavailable during streaming, the same
		// terrain checks still make this offset safe; retain the three-metre fire
		// exclusion above all else.
		if (campDistanceSq(candidate, c.pos) >= 3.0f * 3.0f) {
			*out = candidate;
			return true;
		}
	}
	return false;
}
