// GitHub #62: exact Story honor-event bit controls and shared tier remapping.
// Included by the integration dispatcher after common wrappers are defined.

struct HonorActionTier { int vanilla; int amount; bool enabled; };

static const int kHonorEventBits[] = {
	1, 2, 4, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384,
	32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304
};
static const char* kHonorEventIds[] = {
	"HONOR_EVENT_LOOT_INNOCENT", "HONOR_EVENT_AMBIENT_KILL", "HONOR_EVENT_AMBIENT_KO",
	"HONOR_EVENT_SCARE", "HONOR_EVENT_KILL_VERMIN", "HONOR_EVENT_KILL_FARM_ANIMAL",
	"HONOR_EVENT_KILL_HORSE", "HONOR_EVENT_STEAL_HORSE", "HONOR_EVENT_STEAL_DONKEY",
	"HONOR_EVENT_STEAL_MULE", "HONOR_EVENT_TRAMPLED_INNOCENT", "HONOR_EVENT_STEAL_WAGON",
	"HONOR_EVENT_ABANDON_ANIMALS", "HONOR_EVENT_ANIMAL_BLEEDOUT", "HONOR_EVENT_ANTAGONIZE",
	"HONOR_EVENT_THEFT", "HONOR_EVENT_INTERVENED", "HONOR_EVENT_WANTED_IN_CAMP",
	"HONOR_EVENT_DONATED_GAME", "HONOR_EVENT_ITEM_REQUEST", "HONOR_EVENT_LONG_ABSENCE"
};
static const int kHonorVanillaTiers[] = {
	-640, -480, -320, -160, -40, -20, -10, -5, -2, -1,
	0, 1, 2, 5, 10, 20, 40, 160, 640
};
static HonorActionTier g_honorActionTiers[19];
static int g_honorActionDisabledBits = 0;
static bool g_honorActionsLoaded = false;
static DWORD g_honorActionsNextReloadAt = 0;
static int g_honorActionsLastValue = 0;
static bool g_honorActionsHaveValue = false;

static bool honorActionBool(const std::string& text, bool* value) {
	if (text == "1" || text == "true") { *value = true; return true; }
	if (text == "0" || text == "false") { *value = false; return true; }
	return false;
}

static void honorActionsReload(DWORD now) {
	if (now < g_honorActionsNextReloadAt) return;
	g_honorActionsNextReloadAt = now + 2000;
	std::ifstream input(g_moduleDir + "\\honor_actions.csv");
	if (!input) { g_honorActionsLoaded = false; return; }
	std::string line;
	if (!std::getline(input, line) || line != "kind,id,enabled,amount") return;
	int disabled = 0, eventCount = 0, tierCount = 0;
	HonorActionTier replacement[19];
	while (std::getline(input, line)) {
		std::vector<std::string> fields; std::istringstream row(line); std::string field;
		while (std::getline(row, field, ',')) fields.push_back(field);
		if (fields.size() < 3 || fields.size() > 4) return;
		bool enabled = true; if (!honorActionBool(fields[2], &enabled)) return;
		if (fields[0] == "event") {
			if (eventCount >= 21 || fields[1] != kHonorEventIds[eventCount]) return;
			if (!enabled) disabled |= kHonorEventBits[eventCount];
			++eventCount;
		} else if (fields[0] == "tier") {
			if (tierCount >= 19 || fields.size() != 4) return;
			const std::string expected = "tier_" + std::string(kHonorVanillaTiers[tierCount] >= 0 ? "+" : "") + std::to_string(kHonorVanillaTiers[tierCount]);
			if (fields[1] != expected) return;
			char* end = nullptr; const long amount = std::strtol(fields[3].c_str(), &end, 10);
			if (!end || *end || amount < -10000 || amount > 10000) return;
			replacement[tierCount] = { kHonorVanillaTiers[tierCount], (int)amount, enabled };
			++tierCount;
		} else return;
	}
	if (eventCount != 21 || tierCount != 19) return;
	for (int i = 0; i < 19; ++i) g_honorActionTiers[i] = replacement[i];
	g_honorActionDisabledBits = disabled; g_honorActionsLoaded = true;
}

static void updateHonorActions(DWORD now) {
	honorActionsReload(now);
	if (!g_honorActionsLoaded) { g_honorActionsHaveValue = false; return; }
	constexpr int managedMask = 0x7FFFE7; // exact 21 audited bits; gaps remain Rockstar-owned
	UINT64* flags = getGlobalPtr(36616);
	*flags = (*flags & ~(UINT64)managedMask) | (UINT64)g_honorActionDisabledBits;
	int current = 0; if (!STAT_GET(joaat("HONOR_CURRENT"), &current)) return;
	if (!g_honorActionsHaveValue) { g_honorActionsLastValue = current; g_honorActionsHaveValue = true; return; }
	const int delta = current - g_honorActionsLastValue;
	for (int i = 0; i < 19; ++i) if (delta == g_honorActionTiers[i].vanilla) {
		const int replacement = g_honorActionTiers[i].enabled ? g_honorActionTiers[i].amount : 0;
		current = (std::max)(-320, (std::min)(320, g_honorActionsLastValue + replacement));
		if (current != g_honorActionsLastValue + delta) STAT_SET(joaat("HONOR_CURRENT"), current);
		break;
	}
	g_honorActionsLastValue = current;
}
