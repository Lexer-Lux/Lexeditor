// GameplayTweaks feature module: Collectible map markers, native collectible state, and train map tracking.
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


// #10 CUSTOM MINIMAP ZOOM
//
// RDR2's native database inherited the GTA name SET_RADAR_ZOOM for
// 0xCAF6489DA2C8DD9E, but Story Mode passes that native a BLIP HANDLE when it
// removes a focused blip. It is not the live minimap's numeric scale control.
// Story Mode changes the actual scale with _SET_RADAR_CONFIG_TYPE and the
// RADAR_CONFIG_* records below. Those records are discrete engine-authored
// presets, so choose the closest real preset instead of pretending an arbitrary
// integer is a continuous zoom value.
//
// OWNERSHIP (the reason the first shipped attempt throbbed):
// medium_update.c func_330 runs every frame and re-selects a radar config from
// wanted/mounted/speed/interior state, so a per-frame native call from here was
// simply the loser of a two-writer race. But that function opens with
//
//     if (Global_1911667 == 0) { ...all the auto-selection... }
//     else                     { iVar1 = Global_1911667; }
//     if (iVar1 == iLocal_39) return;      // only fires the native on CHANGE
//     iLocal_39 = iVar1;
//     MAP::_0x9C113883487FD53C(iLocal_39, 0);
//
// Global_1911667 is Rockstar's own sanctioned radar-config override: mission
// scripts write a RADAR_CONFIG_* hash into it to force a zoom and write 0 to
// release (mudtown3b.c func_1533, winter1.c, winter4.c, saint_denis1.c, mob5.c).
// While it is non-zero the game does not select a config at all, and because of
// the `iVar1 == iLocal_39` guard the native is invoked exactly once per change.
// So we write the state the game reads instead of fighting its writes, and the
// game itself applies our config. Every literal in func_330 joaats back to a
// RADAR_CONFIG_* name below, which is what confirms the record set.
//
// Read the string directly: GetPrivateProfileIntA overflows on the deliberately
// huge values used to expose #10. Polling here also makes this setting genuinely
// hot-reloadable without depending on the old int global.
struct MinimapZoomPreset {
	float scale;
	const char* config;
};

static const MinimapZoomPreset kMinimapZoomPresets[] = {
	{ 1.1f, "RADAR_CONFIG_WANTED" },
	{ 2.2f, "RADAR_CONFIG_WANTED_WITNESSED" },
	{ 2.5f, "RADAR_CONFIG_RIDE_FAST_WILDERNESS" },
	{ 3.0f, "RADAR_CONFIG_FOOT_FAST_WILDERNESS" },
	{ 3.5f, "RADAR_CONFIG_FOOT_FAST_TOWN" },
	{ 4.0f, "RADAR_CONFIG_RIDE_SLOW_TOWN" },
	{ 5.0f, "RADAR_CONFIG_FOOT_SLOW_WILDERNESS" },
	{ 7.0f, "RADAR_CONFIG_CARAVAN" },
	{ 10.0f, "RADAR_CONFIG_INDOOR" },
};

static bool g_customMinimapZoomEnabled = true;
static bool g_customMinimapExpanded = false;
static float g_customMinimapZoomRequested = 5.0f;
static const MinimapZoomPreset* g_customMinimapZoomPreset = nullptr;

// Runtime gate retained for isolated diagnostics. The crash bisect reached the
// plant learner before this update path and reproduced with this gate disabled,
// so the minimap override was not the ERROR:FFFFFFFF source.
// Re-enabled once the override moved off the per-frame native and onto
// Global_1911667, the game's own radar-config override slot (see header note).
static constexpr bool kCustomMinimapZoomRuntimeEnabled = true;

// Script global Global_1911667 — Story Mode's radar-config override slot.
static constexpr int kRadarConfigOverrideGlobal = 1911667;

// Every radar-config literal that appears in medium_update.c func_330, so the
// diagnostic log names the config a mission forced instead of printing a hash.
static const struct { INT32 hash; const char* name; } kRadarConfigNames[] = {
	{  2080113112, "RADAR_CONFIG_WANTED" },
	{ -1986542417, "RADAR_CONFIG_WANTED_WITNESSED" },
	{ -1943724816, "RADAR_CONFIG_RIDE_FAST_WILDERNESS" },
	{   347777538, "RADAR_CONFIG_FOOT_FAST_WILDERNESS" },
	{ -2024960240, "RADAR_CONFIG_FOOT_FAST_TOWN" },
	{  -280612398, "RADAR_CONFIG_RIDE_SLOW_TOWN" },
	{  -189036996, "RADAR_CONFIG_FOOT_SLOW_WILDERNESS" },
	{   455950385, "RADAR_CONFIG_RIDE_SLOW_WILDERNESS" },
	{  -117986897, "RADAR_CONFIG_FOOT_SLOW_TOWN" },
	{   642254004, "RADAR_CONFIG_RIDE_FAST_TOWN" },
	{  -789269373, "RADAR_CONFIG_CARAVAN" },
	{  -547506804, "RADAR_CONFIG_INDOOR" },
};

static const char* radarConfigName(INT32 hash) {
	if (hash == 0) return "<game auto-select>";
	for (const auto& entry : kRadarConfigNames)
		if (entry.hash == hash) return entry.name;
	return "<unknown>";
}

// What we last wrote into the slot, so a later foreign value is distinguishable
// from our own, and a back-off deadline so a mission that keeps reclaiming the
// slot can never turn into a per-frame tug of war.
static INT32 g_minimapZoomOwnedConfig = 0;
static DWORD g_minimapZoomBackoffUntil = 0;
static INT32 g_minimapZoomLastLoggedForeign = 0;

// Change-triggered only: one line per ownership transition, never per frame, so
// any oscillation would be visible as a repeating pair in a single file.
static void logMinimapZoomEvent(const char* event, INT32 previous, INT32 applied) {
	GtLogStream log("minimap", GT_INFO);
	if (!log) return;
	log << event
		<< " slot_was=" << previous << " (" << radarConfigName(previous) << ")"
		<< " slot_now=" << applied << " (" << radarConfigName(applied) << ")\n";
}

// Runtime gate retained for isolated diagnostics. Failed blip handles are
// guarded below; a zero-collectible-blip build still reproduced the crash, so
// this renderer was not the ERROR:FFFFFFFF source.
static constexpr bool kCollectibleBlipRuntimeEnabled = true;

static void readCustomMinimapZoom() {
	g_customMinimapZoomEnabled =
		GetPrivateProfileIntA("Minimap", "Enabled", 1, g_iniPath.c_str()) != 0;
	g_customMinimapExpanded =
		GetPrivateProfileIntA("Minimap", "Expanded", 0, g_iniPath.c_str()) != 0;

	char text[96] = {};
	GetPrivateProfileStringA("Minimap", "ZoomLevel", "5.0", text,
		sizeof(text), g_iniPath.c_str());
	char* end = nullptr;
	double requested = strtod(text, &end);
	if (end == text || !std::isfinite(requested)) requested = 5.0;
	requested = (std::max)(1.1, (std::min)(10.0, requested));
	g_customMinimapZoomRequested = static_cast<float>(requested);

	g_customMinimapZoomPreset = &kMinimapZoomPresets[0];
	float closest = std::fabs(g_customMinimapZoomRequested -
		g_customMinimapZoomPreset->scale);
	for (const MinimapZoomPreset& candidate : kMinimapZoomPresets) {
		const float distance = std::fabs(g_customMinimapZoomRequested - candidate.scale);
		if (distance < closest) {
			closest = distance;
			g_customMinimapZoomPreset = &candidate;
		}
	}

	// Log the settings only when they actually change. This poll runs every two
	// seconds; an unconditional line here would bury the ownership transitions
	// that the log exists to make visible.
	static bool loggedOnce = false;
	static bool lastEnabled = false;
	static bool lastExpanded = false;
	static const MinimapZoomPreset* lastPreset = nullptr;
	if (!loggedOnce || lastEnabled != g_customMinimapZoomEnabled ||
		lastExpanded != g_customMinimapExpanded ||
		lastPreset != g_customMinimapZoomPreset) {
		loggedOnce = true;
		lastEnabled = g_customMinimapZoomEnabled;
		lastExpanded = g_customMinimapExpanded;
		lastPreset = g_customMinimapZoomPreset;
		GtLogStream log("minimap", GT_INFO);
		if (log) {
			log << "settings"
				<< " enabled=" << (g_customMinimapZoomEnabled ? 1 : 0)
				<< " expanded=" << (g_customMinimapExpanded ? 1 : 0)
				<< " requested=" << text
				<< " clamped=" << g_customMinimapZoomRequested;
			if (g_customMinimapZoomPreset)
				log << " preset=" << g_customMinimapZoomPreset->scale
					<< " config=" << g_customMinimapZoomPreset->config;
			log << "\n";
		}
	}
}

// Integration calls this every frame in place of SET_RADAR_ZOOM(g_minimapZoom).
// This never calls the radar native. It only publishes the chosen config into
// Global_1911667, medium_update's own override slot, and the game applies it.
// Settings are reparsed on a separate two-second cadence.
//
// Why this cannot oscillate:
//  1. We never invoke _SET_RADAR_CONFIG_TYPE, so there is no second writer of
//     the live radar state — medium_update remains the only caller.
//  2. While the slot holds our hash, medium_update skips its own selection
//     entirely and its `iVar1 == iLocal_39` guard returns before the native, so
//     the applied config is written once and then left alone.
//  3. We only write when the slot differs from what we want, so a steady state
//     produces zero writes per frame.
//  4. If a mission script claims the slot (a value that is neither ours nor 0)
//     we yield completely and refuse to write for kMinimapZoomBackoffMs. Even a
//     hypothetical script that cleared the slot every frame could therefore
//     produce at most one change every three seconds, not a per-frame throb —
//     and no such script exists: the shipped writers (mudtown3b.c func_1533,
//     mob5.c, winter1.c, winter4.c, saint_denis1.c) either write once on a
//     state transition or, like func_1533, guard their reset with
//     `else if (Global_1911667 == RADAR_CONFIG_INDOOR)`, which does not match
//     while we own the slot.
static constexpr DWORD kMinimapZoomBackoffMs = 3000;

static void updateCustomMinimapZoom(DWORD now) {
	if (!kCustomMinimapZoomRuntimeEnabled) return;

	static DWORD lastRead = 0;
	if (!lastRead || now - lastRead >= 2000) {
		lastRead = now;
		readCustomMinimapZoom();
	}

	UINT64* slot = getGlobalPtr(kRadarConfigOverrideGlobal);
	if (!slot) return;
	const INT32 current = static_cast<INT32>(*slot & 0xFFFFFFFFull);

	// Turned off (or hot-disabled through the INI): hand the slot back so Story
	// Mode resumes its own selection, and touch nothing we do not own.
	if (!g_customMinimapZoomEnabled || !g_customMinimapZoomPreset) {
		if (g_minimapZoomOwnedConfig != 0 && current == g_minimapZoomOwnedConfig) {
			*slot = 0;
			logMinimapZoomEvent("released", current, 0);
		}
		g_minimapZoomOwnedConfig = 0;
		return;
	}

	const INT32 desired = static_cast<INT32>(joaat(g_customMinimapZoomPreset->config));

	// Steady state — the overwhelmingly common path, and it writes nothing.
	if (current == desired) {
		g_minimapZoomOwnedConfig = desired;
		g_minimapZoomLastLoggedForeign = 0;
		// Lexer correctly observed that holding the vanilla radar control shows
		// more area than the widest RADAR_CONFIG record. It is a separate binary
		// input state, not another numeric preset. Drive that exact engine action
		// when requested; SET_CONTROL_VALUE_NEXT_FRAME is the native used to
		// synthesize an input without stealing the user's real key binding.
		if (g_customMinimapExpanded)
			invoke<BOOL>(0xE8A25867FBA3B05E, 0,
				joaat("INPUT_EXPAND_RADAR"), 1.0f);
		return;
	}

	// A mission script owns the slot. Yield; do not fight it.
	if (current != 0 && current != g_minimapZoomOwnedConfig) {
		g_minimapZoomBackoffUntil = now + kMinimapZoomBackoffMs;
		g_minimapZoomOwnedConfig = 0;
		if (g_minimapZoomLastLoggedForeign != current) {
			g_minimapZoomLastLoggedForeign = current;
			logMinimapZoomEvent("yielded to script", current, current);
		}
		return;
	}

	if (g_minimapZoomBackoffUntil != 0 && now < g_minimapZoomBackoffUntil) return;
	g_minimapZoomBackoffUntil = 0;

	// Slot is free (0) or still holds our previous choice after an INI edit.
	*slot = static_cast<UINT64>(static_cast<INT64>(desired));
	g_minimapZoomOwnedConfig = desired;
	g_minimapZoomLastLoggedForeign = 0;
	logMinimapZoomEvent("applied", current, desired);
}

static bool readCsvField(std::stringstream& row, std::string& out) {
	out.clear();
	if (row.peek() == '"') {
		row.get(); char c;
		while (row.get(c)) {
			if (c == '"') { if (row.peek() == '"') { row.get(); out += '"'; } else break; }
			else out += c;
		}
		if (row.peek() == ',') row.get();
		return true;
	}
	return static_cast<bool>(std::getline(row, out, ','));
}

// Retired markers persist here (one "category|name" per line) so collecting is
// remembered across game sessions instead of every blip returning on reload.
static std::string collectedStatePath() { return g_moduleDir + "\\collectibles_collected.txt"; }
static std::string collectibleKey(const CollectibleMarker& m) {
	char idx[16]; sprintf_s(idx, "|%d", m.index);
	return m.category + "|" + m.name + idx;
}
// Lines written before #147b had no index. They can only be honoured for the
// first occurrence, because "exotic|Gator Eggs" genuinely does not say WHICH of
// the twenty gator-egg nests you took.
static std::string legacyCollectibleKey(const CollectibleMarker& m) { return m.category + "|" + m.name; }

static std::unordered_set<std::string> loadCollectedKeys() {
	std::unordered_set<std::string> keys;
	std::ifstream in(collectedStatePath());
	std::string line;
	while (std::getline(in, line)) {
		if (!line.empty() && line.back() == '\r') line.pop_back();
		if (!line.empty()) keys.insert(line);
	}
	return keys;
}

// #147 step 1: safe, read-only reverse-engineering probe. Only the value-return,
// no-pointer compendium calls — no output-pointer natives yet (those can crash if
// the arg shape is wrong). Toggle [CollectibleProbe] Enabled=1 and press F10
// in-game; results append to GameplayTweaks.probe.log for us to decode.
// Log which candidate controls are currently held. Used to capture real control
// hashes from the player's own inputs instead of guessing names.
static const char* kProbeControlNames[] = {
	"INPUT_LOOK_BEHIND","INPUT_VEH_LOOK_BEHIND","INPUT_MELEE_ATTACK","INPUT_ATTACK",
	"INPUT_ATTACK2","INPUT_AIM","INPUT_RELOAD","INPUT_TOGGLE_HOLSTER",
	"INPUT_INTERACT_LOCKON","INPUT_CONTEXT","INPUT_CONTEXT_A","INPUT_CONTEXT_B",
	"INPUT_CONTEXT_X","INPUT_CONTEXT_Y","INPUT_CONTEXT_LT","INPUT_CONTEXT_RT",
	"INPUT_OPEN_SATCHEL_MENU","INPUT_OPEN_WHEEL_MENU","INPUT_OPEN_JOURNAL",
	"INPUT_SELECT_WEAPON","INPUT_SELECT_NEXT_WEAPON","INPUT_SELECT_PREV_WEAPON",
	"INPUT_HUD_SPECIAL","INPUT_WHISTLE","INPUT_GREET_POSITIVE","INPUT_GREET_NEGATIVE",
	"INPUT_JUMP","INPUT_SPRINT","INPUT_ENTER","INPUT_DUCK","INPUT_COVER",
	"INPUT_MAP","INPUT_PLAYER_MENU","INPUT_DYNAMIC_SCENARIO","INPUT_PICKUP",
	"INPUT_FRONTEND_LB","INPUT_FRONTEND_RB","INPUT_FRONTEND_LT","INPUT_FRONTEND_RT",
	"INPUT_FRONTEND_LEFT","INPUT_FRONTEND_RIGHT","INPUT_FRONTEND_UP","INPUT_FRONTEND_DOWN",
	"INPUT_WEAPON_SPECIAL","INPUT_WEAPON_SPECIAL_TWO","INPUT_SPECIAL_ABILITY",
	"INPUT_OPEN_CRAFTING","INPUT_QUICK_USE_ITEM","INPUT_SELECT_RADAR_MODE",
};

static bool probeControlActive(Hash h) {
	return PAD::IS_CONTROL_PRESSED(0, h) || PAD::IS_DISABLED_CONTROL_PRESSED(0, h) ||
		PAD::IS_CONTROL_PRESSED(2, h) || PAD::IS_DISABLED_CONTROL_PRESSED(2, h);
}

static void probeActiveControls(GtLogStream& log) {
	for (const char* n : kProbeControlNames)
		if (probeControlActive(joaat(n)))
			log << "CONTROL HELD: " << n << " (0x" << std::hex << joaat(n) << std::dec << ")\n";
}

// Continuously catch momentary taps (e.g. flipping the wheel to the item page):
// logs each candidate the first time it fires since the last reset, so you don't
// have to hold it while pressing F10.
static void probeContinuousTap() {
	static std::unordered_set<std::string> seen;
	for (const char* n : kProbeControlNames) {
		if (seen.count(n)) continue;
		if (probeControlActive(joaat(n))) {
			seen.insert(n);
			GtLogStream log("map-probe", GT_INFO);
			log << "TAP: " << n << " (0x" << std::hex << joaat(n) << std::dec << ")\n";
		}
	}
}

// The game's own COLLECTABLE system exposes exact placement coordinates AND
// found-state per item — everything the scraped CSV lacks (#147). Probe which
// categories are populated in story mode, then dump each item's coords/state.
static void probeCollectableSystem(GtLogStream& log) {
	static const char* kCats[] = {
		"CIGARETTE_CARDS","DINOSAUR_BONES","ROCK_CARVINGS","DREAMCATCHERS","EXOTICS",
		"LEGENDARY_FISH","GRAVES","POINTS_OF_INTEREST","SHACKS","TREASURE_MAPS",
		"WEEKLY_COLLECTABLES","ANTIQUE_BOTTLES","BIRD_EGGS","ARROWHEADS","FAMILY_HEIRLOOMS",
		"WILD_FLOWERS","COINS","LOST_JEWELRY_RINGS","TAROT_CARDS_CUPS","FOSSILS_COMMON",
		"COLLECTABLE","COLLECTABLES","SP_COLLECTABLES","CARDS","BONES","CARVINGS","ORCHIDS",
		// second sweep: remaining SP families and plausible aliases
		"DINO_BONES","POINT_OF_INTEREST","POI","GRAVE","SHACK","TREASURE","TREASURE_MAP",
		"DREAMCATCHER","EXOTIC","EXOTICS_STAGE_1","LEGENDARY_ANIMALS","LEGENDARY_FISHES",
		"HIDDEN_GRAVES","SHACKS_SP","CIGARETTE_CARD","CARD_SETS","BOUNTY_POSTERS",
	};
	for (const char* cn : kCats) {
		Hash cat = joaat(cn);
		for (int sub = 0; sub < 6; ++sub) {
			Hash subHash = (sub == 0) ? (Hash)0 : (Hash)sub;
			int n = invoke<int>(0x62CAB7DB62EAD434, cat, subHash); // CATEGORY_GET_NUM_COLLECTABLES
			if (n <= 0 || n > 5000) continue;
			int found = invoke<int>(0x5461C821D00FE15A, cat, subHash); // CATEGORY_GET_NUM_FOUND
			log << "CATEGORY " << cn << " sub=" << sub << " -> num=" << n << " found=" << found << "\n";
			for (int i = 0; i < n; ++i) {   // dump EVERY item: one run must be enough
				Hash item = invoke<Hash>(0x126CBEBBA46693CF, i, cat, subHash); // GET_COLLECTABLE_ITEM_HASH
				if (!item) continue;
				Vector3 pos = invoke<Vector3>(0x1F1DD794908C2BFA, item);      // GET_PLACEMENT_LOCATION
				int nf = invoke<int>(0xF83D3DDA4D3C8169, item);               // GET_NUM_FOUND
				log << "   item[" << i << "] hash=0x" << std::hex << item << std::dec
					<< " pos=" << pos.x << "," << pos.y << "," << pos.z
					<< " found=" << nf << "\n";
			}
		}
	}
}

// #147e: which story missions does this save consider done? Needed to replace
// the blanket FINALE3 gate on the graves with a per-character chapter gate.
// The ids are the short codes the scripts pass to MISSIONDATA_WAS_COMPLETED;
// unknown ids simply answer 0, so a wrong guess costs nothing but a log line.
static void probeMissionCompletion(GtLogStream& log) {
	static const char* kMissions[] = {
		"MUD1","MUD2","MUD3","MUD4","MUD5","MUD6",
		"WINTER1","WINTER2","WINTER3","WINTER4","WINTER5",
		"MUDTOWN1","MUDTOWN2","MUDTOWN3","MUDTOWN4","MUDTOWN5",
		"GRAYS1","GRAYS2","GRAYS3","BRAITHWAITES1","BRAITHWAITES2","BRAITHWAITES3",
		"SMUGGLER2","SAINTDENIS","BANK","BANK1","INDUSTRY1","INDUSTRY3",
		"GUAMA1","GUAMA2","GUAMA3","UTOPIA1","UTOPIA2","TRELAWNY1",
		"GANG01","GANG02","GANG1","GANG2","GANG3","MOB1","MOB2","MOB3","MOB4","MOB5",
		"SAD2","SAD3","SAD4","SAD5","SADIE1","SADIE4","MARY01","MARY02","MARY31",
		"FINALE1","FINALE2","FINALE3",
		"MAR1","MAR2","MAR4","MAR5","MAR6","MAR7","MAR8",
	};
	for (const char* m : kMissions)
		log << "MISSION " << m << " completed="
			<< (invoke<int>(0xE54DC27571D5EDC4, joaat(m)) != 0 ? 1 : 0) << "\n";
}

static void probeCollectibleNatives() {
	GtLogStream log("map-probe", GT_INFO);
	log << "=== probe ===\n";
	Ped ped = PLAYER::PLAYER_PED_ID();
	if (ped) { Vector3 p = ENTITY_COORDS(ped); log << "player x=" << p.x << " y=" << p.y << " z=" << p.z << "\n"; }
	probeActiveControls(log);
	probeMissionCompletion(log);
	probeCollectableSystem(log);
	log << "--- done ---\n";
}

static void loadCollectibles() {
	g_collectibles.clear();
	std::unordered_set<std::string> collected = loadCollectedKeys();
	std::ifstream input(g_moduleDir + "\\collectibles.csv");
	std::string line; std::getline(input, line);
	std::unordered_map<std::string, int> seen;   // (category|name) -> next occurrence index
	while (std::getline(input, line)) {
		if (!line.empty() && line.back() == '\r') line.pop_back();
		std::stringstream row(line); std::string category, name, x, y, require;
		if (!readCsvField(row, category) || !readCsvField(row, name) ||
			!readCsvField(row, x) || !readCsvField(row, y)) continue;
		readCsvField(row, require);   // optional 5th column, blank on most rows
		CollectibleMarker marker = {};
		marker.category = category; marker.name = name; marker.require = require;
		marker.index = seen[category + "|" + name]++;
		marker.position.x = (float)atof(x.c_str()); marker.position.y = (float)atof(y.c_str()); marker.position.z = 0.0f;
		marker.collected = collected.count(collectibleKey(marker)) > 0 ||
			(marker.index == 0 && collected.count(legacyCollectibleKey(marker)) > 0);
		g_collectibles.push_back(marker);
	}
}

// Forward declarations: these are defined later in the file.
static bool categoryEnabled(const std::string& category);
static void CASING_FEED(const char* text, const char* textureDict, Hash texture);

// F2: move the NEAREST marker to where the player is standing and persist it.
// The community maps these came from were pinned by hand, so the residual error
// is not systematic and no formula removes it — manual correction is the only
// way to reach exact placement. Corrections live in collectibles_fixups.csv and
// are re-applied over the base csv on load, so the base file stays pristine.
static std::string fixupPath() { return g_moduleDir + "\\collectibles_fixups.csv"; }

static void applyCollectibleFixups() {
	std::ifstream in(fixupPath());
	if (!in) return;
	std::string line;
	while (std::getline(in, line)) {
		if (!line.empty() && line.back() == '\r') line.pop_back();
		// Two layouts. New: category,name,index,x,y. Legacy (pre-#147b):
		// category,name,x,y - no index, so it can only be applied to the first
		// occurrence instead of to every marker sharing the name.
		std::stringstream row(line); std::string cat, name, a, b, c;
		if (!readCsvField(row, cat) || !readCsvField(row, name) ||
			!readCsvField(row, a) || !readCsvField(row, b)) continue;
		const bool hasIndex = readCsvField(row, c);
		const int index = hasIndex ? atoi(a.c_str()) : 0;
		const float fx = (float)atof((hasIndex ? b : a).c_str());
		const float fy = (float)atof((hasIndex ? c : b).c_str());
		for (CollectibleMarker& m : g_collectibles)
			if (m.category == cat && m.name == name && m.index == index) {
				m.position.x = fx;
				m.position.y = fy;
				if (m.blip) { REMOVE_MAP_BLIP(&m.blip); }
			}
	}
	g_collectiblesDirty = true;
}

static void relocateNearestCollectible(Ped ped) {
	if (!ped || g_collectibles.empty()) return;
	Vector3 p = ENTITY_COORDS(ped);
	CollectibleMarker* best = nullptr; float bestD2 = 1e18f;
	for (CollectibleMarker& m : g_collectibles) {
		if (m.collected || !categoryEnabled(m.category)) continue;
		float dx = p.x - m.position.x, dy = p.y - m.position.y;
		float d2 = dx*dx + dy*dy;
		if (d2 < bestD2) { bestD2 = d2; best = &m; }
	}
	if (!best) return;
	const float moved = sqrtf(bestD2);
	if (moved > g_collectMoveMaxDistance) {
		char buf[256];
		sprintf_s(buf, "F2 refused: nearest marker is %.1fm away (maximum %.1fm)",
			moved, g_collectMoveMaxDistance);
		CASING_FEED(buf, "toast_bg", joaat("toast_bg"));
		GtLogStream log("collectfix", GT_INFO);
		log << buf << "\n";
		return;
	}
	best->position.x = p.x; best->position.y = p.y;
	if (best->blip) REMOVE_MAP_BLIP(&best->blip);
	g_collectiblesDirty = true;
	{   // append the correction so it survives restarts
		std::ofstream out(fixupPath(), std::ios::app);
		out << best->category << "," << best->name << "," << best->index << ","
			<< std::fixed << std::setprecision(3) << p.x << "," << p.y << "\n";
	}
	char buf[256];
	sprintf_s(buf, "Moved \"%s\" (%s) %.1fm to you", best->name.c_str(), best->category.c_str(), moved);
	CASING_FEED(buf, "toast_bg", joaat("toast_bg"));
	GtLogStream log("collectfix", GT_INFO);
	log << buf << " -> " << p.x << "," << p.y << "\n";
}

// Mark one marker collected: retire its blip now and append it to the state
// file so it does not reappear when the game (or this ASI) reloads.
static void retireCollectible(CollectibleMarker& marker) {
	marker.collected = true;
	if (marker.blip) REMOVE_MAP_BLIP(&marker.blip);
	std::ofstream out(collectedStatePath(), std::ios::app);
	out << collectibleKey(marker) << "\n";
}

// #80: POIs are not ordinary pickups.  Reaching the coordinate only makes the
// game's INSPECT prompt available; the discoverable script sets bit 4 in
// Global_40.f_8863[discoverableIndex] after the journal sketch completes.
// The old proximity fallback therefore erased a POI before the player had
// actually inspected it.  These indices are Rockstar's func_99 mapping in
// discoverable_generic_location.c, keyed here by the names in our CSV.
struct PoiDiscoverableState {
	const char* name;
	int index;
};

static const PoiDiscoverableState kPoiDiscoverableStates[] = {
	{ "Abandoned Church", 49 }, { "Abandoned Trading Post", 52 },
	{ "Barrel Rider", 2 }, { "Bolger Glade", 133 },
	{ "Braithwaites' Secret", 62 }, { "Brush Fire", 65 },
	{ "Circus Wagons", 70 }, { "Crashed Airship", 72 },
	{ "Defaced Grave", 8 }, { "Devil's Cave", 136 },
	{ "Donkey Lady", 10 }, { "Face in Cliff", 34 },
	{ "Faces in Trees", 81 }, { "Flying Machine", 84 },
	{ "Fossilized Man", 13 }, { "Frozen Settler", 14 },
	{ "Giant Remains", 16 }, { "Gray's Secret", 89 },
	{ "Hermit Woman", 90 }, { "Jesuit Missionary", 93 },
	{ "Mammoth Skeleton", 97 }, { "Manmade Mutant", 85 },
	{ "Meditating Monk", 98 }, { "Meteor House", 99 },
	{ "Meteorite", 20 }, { "Mysterious Hill Home", 125 },
	{ "Native Burial Site", 92 }, { "Obelisk", 103 },
	{ "Oil Derrick", 51 }, { "Old Tomb", 29 },
	{ "Old World Scripts", 21 }, { "Pagan Ritual", 110 },
	{ "Painting in Cabin", 33 }, { "Phonograph", 48 },
	{ "Pleasance", 15 }, { "Register Rock", 115 },
	{ "Serpent Mound", 118 }, { "Sperm Whale Bones", 119 },
	{ "Strange Statues - Painting", 120 }, { "Strange Statues Cave", 120 },
	{ "Tiny Church", 108 }, { "Trading Post", 135 },
	{ "Trail Trees (I)", 139 }, { "Trail Trees (II)", 139 },
	{ "Trail Trees (III)", 139 }, { "Trail Trees (IV)", 139 },
	{ "Warped Tree", 31 }, { "Whale Bones", 25 },
	{ "Wickiup", 124 }, { "Withered Arm", 42 },
};

static bool poiDiscovered(const CollectibleMarker& marker) {
	if (marker.category != "poi") return false;

	// Town-secret Aztec writings share one discoverable record but retain their
	// six individual completion bits in f_154.  Keep each marker independently
	// truthful instead of hiding the entire set after the first writing.
	static const int kAztecBits[] = { 65536, 131072, 262144, 524288, 1048576, 2097152 };
	static const char* kAztecNames[] = {
		"Mysterious Aztec Writing #1", "Mysterious Aztec Writing #2",
		"Mysterious Aztec Writing #3", "Mysterious Aztec Writing #4",
		"Mysterious Aztec Writing #5", "Mysterious Aztec Writing #6",
	};
	for (int i = 0; i < 6; ++i)
		if (marker.name == kAztecNames[i])
			return (*getGlobalPtr(40 + 8863 + 154) & kAztecBits[i]) != 0;

	// Trail trees likewise have per-tree flags in f_152.  The common record's
	// bit 4 means the whole group is complete and is too coarse for four blips.
	static const int kTrailBits[] = { 262144, 524288, 1048576, 2097152 };
	static const char* kTrailNames[] = {
		"Trail Trees (I)", "Trail Trees (II)", "Trail Trees (III)", "Trail Trees (IV)"
	};
	for (int i = 0; i < 4; ++i)
		if (marker.name == kTrailNames[i])
			return (*getGlobalPtr(40 + 8863 + 152) & kTrailBits[i]) != 0;

	for (const PoiDiscoverableState& state : kPoiDiscoverableStates)
		if (marker.name == state.name)
			return (*getGlobalPtr(40 + 8863 + state.index) & 4) != 0;

	// Coal Mine Writing is a cheat inscription, not a journal discoverable. It
	// has no completion bit, so it deliberately remains until manually hidden.
	return false;
}

// Clear any nearby (2D) not-yet-collected markers once the player is basically
// on top of them — you must physically reach a collectible to pick it up.
static void clearReachedCollectibles(Ped ped) {
	if (!g_collectAutoClear || !ped) return;
	Vector3 p = ENTITY_COORDS(ped);
	const float r2 = g_collectClearRadius * g_collectClearRadius;
	for (CollectibleMarker& marker : g_collectibles) {
		if (marker.collected) continue;
		// Entering a hideout area does not prove the game awarded completion, and
		// standing at a POI does not prove its journal inspection completed.
		if (marker.category == "gang_hideout" || marker.category == "poi") continue;
		float dx = p.x - marker.position.x, dy = p.y - marker.position.y;
		if (dx * dx + dy * dy <= r2) retireCollectible(marker);
	}
}

static bool hasItem(const char* item) { return INVENTORY_ITEM_COUNT(joaat(item)) > 0; }
static bool hasOrUnlocked(const char* item) { Hash key = joaat(item); return INVENTORY_ITEM_COUNT(key) > 0 || UNLOCKED(key); }
// #147a: THE ONE-OFF DOCUMENT WAS THE WRONG SIGNAL FOR AN EXISTING SAVE.
// The gate only ever asked "is the quest-starting note in your satchel", and on
// a save that started the hunt long ago it is not - you read it, it left the
// inventory, and UNLOCKED() does not cover documents. Nothing about it was
// one-time-trigger-driven (the whole set is already re-read once a second), so
// "check at startup" was already true; the check itself was just blind.
// The game's own collectable ledger answers it properly and works on any save:
// if it says you have already found one of a category, the quest is plainly
// underway. Your probe log proves it - DINO_BONES reports num=30 found=2 while
// the document check returned nothing, which is precisely the missing icons.
// Either signal is now enough.
static bool collectableCategoryStarted(const char* categoryName) {
	// CATEGORY_GET_NUM_FOUND. Value-return, no output pointers - safe to poll.
	return invoke<int>(0x5461C821D00FE15A, joaat(categoryName), (Hash)0) > 0;
}

static unsigned collectibleUnlocks() {
	unsigned bits = 0;
	if (hasOrUnlocked("DOCUMENT_BUSINESS_CARD_CIG_CARDS") || collectableCategoryStarted("CIGARETTE_CARDS")) bits |= 1u << 0;
	if (hasOrUnlocked("DOCUMENT_NOTE_DINO_BONES") || collectableCategoryStarted("DINO_BONES")) bits |= 1u << 1;
	if (hasOrUnlocked("DOCUMENT_NOTE_ROCK_CARVINGS") || collectableCategoryStarted("ROCK_CARVINGS")) bits |= 1u << 2;
	if (hasOrUnlocked("DOCUMENT_NOTE_RARE_FISH") || collectableCategoryStarted("LEGENDARY_FISH")) bits |= 1u << 3;
	for (int i = 1; i <= 5; ++i) { char key[48]; sprintf_s(key, "DOCUMENT_NOTE_EXOTICS_STAGE_%02d", i); if (hasOrUnlocked(key)) bits |= 1u << (3 + i); }
	return bits;
}

static int exoticStage(const std::string& name) {
	if (name.find("Egret") != std::string::npos || name == "Lady of the Night Orchid") return 1;
	if (name == "Heron Plumes" || name == "Lady Slipper Orchid" || name == "Moccasin Flower Orchid") return 2;
	if (name == "Gator Eggs" || name == "Acuna's Star Orchid" || name == "Cigar Orchid" || name == "Ghost Orchid") return 3;
	if (name == "Spoonbill Plumes" || name == "Night Scented Orchid" || name == "Rat Tail Orchid" || name == "Spider Orchid") return 4;
	return 5;
}

static bool categoryEnabled(const std::string& category) {
	if (category == "card") return g_collectCards;
	if (category == "bone") return g_collectBones;
	if (category == "carving") return g_collectCarvings;
	if (category == "dreamcatcher") return g_collectDreamcatchers;
	if (category == "grave") return g_collectGraves;
	if (category == "exotic") return g_collectExotics;
	if (category == "legendary_fish") return g_collectLegendaryFish;
	if (category == "shack") return g_collectShacks;
	if (category == "treasure_clue") return g_collectTreasureClues;
	if (category == "poi") return g_collectPois;
	if (category == "gang_hideout") return g_collectGangHideouts;
	return false;
}

static Hash categoryIcon(const std::string& category) {
	// THE BLACK SQUARES WERE A REGISTRATION BUG, NOT AN ART BUG.
	// blipdata.ymt gives every blip its own <TextureDictionary>. Our six custom
	// entries were pointing at `blips` - Rockstar's RESIDENT dictionary, which
	// obviously does not contain our textures - so the blip record resolved but
	// its texture did not, and the map drew an empty square. Trying to override
	// the resident `blips` dictionary wholesale was the wrong fix and displaced
	// ordinary icons.
	// Superseded by #153 below: the separate `lex_blips` dictionary rendered as
	// black quads, so custom art now lives in the resident INVENTORY_ITEMS_MP
	// replacement (see ensureLexBlipTextures). History kept: the earlier black
	// squares were a registration bug (entries pointed at resident `blips`,
	// which lacks our textures), not an art bug.
	if (category == "card") return joaat("LEX_BLIP_CARD");
	if (category == "bone") return joaat("LEX_BLIP_BONE");
	if (category == "carving") return joaat("LEX_BLIP_CARVING");
	if (category == "dreamcatcher") return joaat("LEX_BLIP_DREAMCATCHER");
	if (category == "treasure_clue") return joaat("LEX_BLIP_TREASURE");
	// #147g: the custom grave art is dropped in favour of BLIP_AMBIENT_DEATH -
	// the shipped outline cross. It is the icon #50 used for the lost-money
	// bloodstain before that switched to a money bag, and a cross is what a
	// grave should be anyway. LEX_BLIP_GRAVE is no longer referenced by code;
	// its entry in blipdata.ymt and its texture in lex_blips.ytd are now dead
	// weight and can be stripped next time that pair is rebuilt.
	if (category == "grave") return joaat("BLIP_AMBIENT_DEATH");
	// Categories with no custom art keep their shipped Rockstar glyphs.
	if (category == "exotic") return joaat("BLIP_RC_COLLECTABLE_EXOTICS");
	if (category == "legendary_fish") return joaat("BLIP_RC_COLLECTABLE_RAREFISH");
	if (category == "shack") return joaat("BLIP_PROC_HOME");
	if (category == "poi") return joaat("BLIP_POI");
	if (category == "gang_hideout") return joaat("BLIP_REGION_HIDEOUT");
	return joaat("BLIP_AMBIENT_SECRET");
}

// #147e: WE WERE ROUTING YOU TO THE GRAVES OF PEOPLE WHO ARE STILL ALIVE.
// Every one of the eight graves belongs to a gang member who dies during the
// story, and nothing gated them, so a Chapter 2 save got a map full of who is
// about to be buried. A marker can now name a story mission in the CSV's
// `require` column and stays hidden until the game says that mission is done.
// MISSIONDATA_WAS_COMPLETED takes a single mission-id hash and returns a value,
// so it is safe to poll; the ids are the short codes the scripts use
// (medium_update.c calls it with joaat("MUD1")).
// The shipped gate is FINALE3 on all eight - the last Arthur mission - because
// that is the one point where all eight are provably dead, so it can never
// spoil anything. Per-grave chapter gates are a CSV edit away once the mission
// ids are confirmed in game; the probe dumps them and the map-icons log prints
// each gate's current state, so no rebuild is needed to loosen them.
static bool missionCompleted(const std::string& missionId) {
	if (missionId.empty()) return true;
	return invoke<int>(0xE54DC27571D5EDC4, joaat(missionId.c_str())) != 0;
}

// #44: Levin gives all four photographs at the end of RCAL11, but vanilla
// waits for each photograph to be inspected before it exposes that branch's
// map blip.  Keep the quest data untouched and fill only that presentation
// gap: four ASI-owned blips appear as soon as the introductory mission is
// complete.  Each entry uses the exact coordinate/icon registered by
// init_all_sp for the corresponding stranger mission.
//
// The document fallback covers saves made during the hand-off frame, before
// MISSIONDATA has committed RCAL11. Requiring all four photographs avoids
// treating one independently granted/test item as a started quest.
struct GunslingerReveal {
	const char* name;
	const char* missionId;
	const char* scriptName;
	const char* photograph;
	int storyRecord;
	Vector3 position;
	Hash icon;
	Blip blip;
};

static GunslingerReveal g_gunslingerReveals[] = {
	{ "Emmet Granger",  "RGUN11", "rcm_gunslinger1_1", "DOCUMENT_GUNSLINGER_1_NOTE", 84, { -62.69012f, -404.3738f, 69.91233f }, joaat("BLIP_RC_GUNSLINGER_1"), 0 },
	{ "Flaco Hernandez", "RGUN2",  "rcm_gunslinger2_1", "DOCUMENT_GUNSLINGER_2_NOTE", 86, { -967.5845f, 2181.624f, 339.4473f }, joaat("BLIP_RC_GUNSLINGER_2"), 0 },
	{ "Billy Midnight",  "RGUN3",  "rcm_gunslinger3_1", "DOCUMENT_GUNSLINGER_3_NOTE", 87, { 1231.35f, -1299.684f, 75.9034f }, joaat("BLIP_RC_GUNSLINGER_3"), 0 },
	{ "Black Belle",     "RGUN5",  "rcm_gunslinger5_1", "DOCUMENT_GUNSLINGER_5_NOTE", 88, { 2492.992f, -420.529f, 43.78334f }, joaat("BLIP_RC_GUNSLINGER_5"), 0 },
};

static bool gunslingerQuestStarted() {
	if (missionCompleted("RCAL11")) return true;
	for (const GunslingerReveal& entry : g_gunslingerReveals)
		if (!hasItem(entry.photograph)) return false;
	return true;
}

static Blip vanillaGunslingerBlip(const GunslingerReveal& entry) {
	// Global_1347702 is the stranger-mission registry initialized by
	// init_all_sp; records are 49 slots wide and f_37 is Rockstar's blip.
	// Read-only: never replace, remove, or otherwise mutate vanilla state.
	return static_cast<Blip>(*getGlobalPtr(1347702 + entry.storyRecord * 49 + 37));
}

static void retireGunslingerReveal(GunslingerReveal& entry) {
	if (entry.blip) REMOVE_MAP_BLIP(&entry.blip);
	entry.blip = 0;
}

static void refreshGunslingerMapBlips() {
	const bool started = gunslingerQuestStarted();
	for (GunslingerReveal& entry : g_gunslingerReveals) {
		if (entry.blip && !MAP::DOES_BLIP_EXIST(entry.blip)) entry.blip = 0;

		// Finished branches never regain an ASI marker. If Rockstar currently
		// owns a live marker, defer to it so inspecting a photograph cannot
		// produce a doubled icon.
		const Blip vanilla = vanillaGunslingerBlip(entry);
		const bool vanillaVisible = vanilla && MAP::DOES_BLIP_EXIST(vanilla);
		const bool branchRunning = scriptRunning(entry.scriptName);
		if (!started || missionCompleted(entry.missionId) || vanillaVisible || branchRunning) {
			retireGunslingerReveal(entry);
			continue;
		}

		if (!entry.blip) {
			entry.blip = ADD_COORD_BLIP((Hash)-1337945352, entry.position);
			if (entry.blip) {
				SET_BLIP_ICON(entry.blip, entry.icon);
				SET_BLIP_NAME(entry.blip, entry.name);
			}
		}
	}
}

static const char* categoryLabel(const std::string& category) {
	if (category == "card") return "Cigarette Card";
	if (category == "bone") return "Dinosaur Bone";
	if (category == "carving") return "Rock Carving";
	if (category == "dreamcatcher") return "Dreamcatcher";
	if (category == "grave") return "Grave";
	if (category == "exotic") return "Exotic";
	if (category == "legendary_fish") return "Legendary Fish";
	if (category == "shack") return "Shack";
	if (category == "treasure_clue") return "Treasure Map";
	if (category == "poi") return "Point of Interest";
	if (category == "gang_hideout") return "Gang Hideout";
	return "Collectible";
}

// ---- Native collectable layer (#147) --------------------------------------
// For categories the game's COLLECTABLE system exposes with real coordinates,
// we ignore the scraped CSV entirely: positions come from
// _COLLECTABLE_GET_PLACEMENT_LOCATION and a marker disappears when the GAME says
// it is found (_COLLECTABLE_GET_NUM_FOUND) — no proximity guessing, no manual
// state file. Verified populated in story mode: ROCK_CARVINGS (10/10 exact).
// CIGARETTE_CARDS / DINO_BONES / LEGENDARY_FISH report found-state but return
// 0,0,0 for position, so they stay on the CSV path until coords are sourced.
struct NativeCollectible { Hash item; Vector3 pos; Blip blip; bool found; };
static std::vector<NativeCollectible> g_nativeCollectibles;
static bool g_nativeCarvingsLoaded = false;

static void loadNativeCollectibles() {
	g_nativeCollectibles.clear();
	const Hash cat = joaat("ROCK_CARVINGS");
	const int n = invoke<int>(0x62CAB7DB62EAD434, cat, (Hash)0);
	if (n <= 0 || n > 5000) return;
	for (int i = 0; i < n; ++i) {
		Hash item = invoke<Hash>(0x126CBEBBA46693CF, i, cat, (Hash)0);
		if (!item) continue;
		Vector3 p = invoke<Vector3>(0x1F1DD794908C2BFA, item);
		if (p.x == 0.0f && p.y == 0.0f) continue;   // no placement data
		NativeCollectible nc = {};
		nc.item = item; nc.pos = p; nc.blip = 0; nc.found = false;
		g_nativeCollectibles.push_back(nc);
	}
	g_nativeCarvingsLoaded = !g_nativeCollectibles.empty();
}

// #153: all custom map art is now appended to the complete resident
// INVENTORY_ITEMS_MP replacement. The separate lex_blips resource repeatedly
// rendered as black quads and must not be requested or republished again.
static bool g_lexBlipsProbed = false;
static void ensureLexBlipTextures() {
	const char* dict = "INVENTORY_ITEMS_MP";
	const bool loaded = invoke<BOOL>(0x54D6900929CCF162, dict) != 0;
	if (!loaded) invoke<Void>(0xC1BA29DF5631B0F8, dict, FALSE);
	if (!g_lexBlipsProbed) {
		// One line, once: does the game even SEE the file we ship? This
		// separates "not requested" from "not reachable by the mod loader",
		// which is the one thing guesswork could never settle.
		g_lexBlipsProbed = true;
		const bool exists = invoke<BOOL>(0x7332461FC59EB7EC, dict) != 0;
		GtLogStream log("map-icons", GT_INFO);
		if (log) log << "custom map icons dictionary exists=" << (exists ? 1 : 0)
			<< " loaded_before_request=" << (loaded ? 1 : 0) << "\n";
	}
}

static void refreshNativeCollectibleBlips() {
	// This function is already polled every two seconds independently of the
	// collectible toggle, making it the module's safe periodic map hook.
	refreshGunslingerMapBlips();
	ensureLexBlipTextures();
	if (!g_nativeCarvingsLoaded) return;
	for (NativeCollectible& nc : g_nativeCollectibles) {
		if (!kCollectibleBlipRuntimeEnabled) {
			if (nc.blip) REMOVE_MAP_BLIP(&nc.blip);
			continue;
		}
		const bool found = invoke<int>(0xF83D3DDA4D3C8169, nc.item) > 0;
		nc.found = found;
		const bool show = g_collectiblesEnabled && g_collectCarvings && !found;
		if (!show) { if (nc.blip) REMOVE_MAP_BLIP(&nc.blip); continue; }
		if (!nc.blip) {
			nc.blip = ADD_COORD_BLIP((Hash)-1337945352, nc.pos);
			if (!nc.blip) continue;
			SET_BLIP_ICON(nc.blip, categoryIcon("carving"));
			SET_BLIP_NAME(nc.blip, "Rock Carving");
		}
	}
}

// One line per distinct `require` id, re-logged whenever its answer flips, so a
// wrong mission id shows up as "never completes" instead of as silence (#147e).
static void logRequireGates() {
	static std::unordered_map<std::string, int> lastState;
	for (const CollectibleMarker& m : g_collectibles) {
		if (m.require.empty()) continue;
		const int now = missionCompleted(m.require) ? 1 : 0;
		auto it = lastState.find(m.require);
		if (it != lastState.end() && it->second == now) continue;
		lastState[m.require] = now;
		GtLogStream log("map-icons", GT_INFO);
		if (log) log << "require " << m.require << " completed=" << now << "\n";
	}
}

static void refreshCollectibleBlips() {
	ensureLexBlipTextures();
	logRequireGates();
	for (CollectibleMarker& marker : g_collectibles) {
		if (!kCollectibleBlipRuntimeEnabled) {
			if (marker.blip) REMOVE_MAP_BLIP(&marker.blip);
			continue;
		}
		if (marker.collected) { if (marker.blip) REMOVE_MAP_BLIP(&marker.blip); continue; }
		if (poiDiscovered(marker)) {
			if (marker.blip) REMOVE_MAP_BLIP(&marker.blip);
			continue;
		}
		// The native layer owns carvings once loaded — never draw both.
		if (g_nativeCarvingsLoaded && marker.category == "carving") {
			if (marker.blip) REMOVE_MAP_BLIP(&marker.blip);
			continue;
		}
		bool visible = g_collectiblesEnabled && categoryEnabled(marker.category);
		if (marker.category == "card") visible = visible && (g_collectibleUnlocks & (1u << 0));
		else if (marker.category == "bone") visible = visible && (g_collectibleUnlocks & (1u << 1));
		else if (marker.category == "carving") visible = visible && (g_collectibleUnlocks & (1u << 2));
		else if (marker.category == "legendary_fish") visible = visible && (g_collectibleUnlocks & (1u << 3));
		else if (marker.category == "exotic") visible = visible && (g_collectibleUnlocks & (1u << (3 + exoticStage(marker.name))));
		if (visible && !marker.require.empty()) visible = missionCompleted(marker.require);
		if (!visible) { if (marker.blip) REMOVE_MAP_BLIP(&marker.blip); continue; }
		if (!marker.blip) {
			// This is the ordinary coordinate style used by vanilla map points.
			marker.blip = ADD_COORD_BLIP((Hash)-1337945352, marker.position);
			if (!marker.blip) continue;
			SET_BLIP_ICON(marker.blip, categoryIcon(marker.category));
			// Matching labels group the locations into one Index entry with 1-of-N cycling.
			SET_BLIP_NAME(marker.blip, categoryLabel(marker.category));
		}
	}
	g_collectiblesDirty = false;
}

// #14 PAUSE-MAP CENTERING
//
// WHAT WORKS, AND WHY THE OTHER HALF NEVER COULD
// ----------------------------------------------
// Auto-centering works and is confirmed in game ("map does seem to open to my
// location"). It works because it is done while the map is CLOSED: the unnamed
// native 0xE0884C184728C75B (natives.h:2898, MAP namespace, no Rockstar name in
// the SDK - do not call it _SET_PAUSEMAP_COORDS_WITH_RADIUS, that name is
// nowhere in natives.h) supplies the focus that the MAP UIApp consumes at
// launch. Rockstar's own order is focus-then-launch, e.g. doc_newspaper.c:3425
// MAP::_0xE0884C184728C75B(...) immediately followed by :3427
// UIAPPS::_LAUNCH_APP_BY_HASH(joaat("MAP")). The only three scripts in
// script_rel/ that touch this native (doc_newspaper.c,
// doc_coach_robbery_note.c, generic_document_inspection.c) all do exactly that,
// and none of them ever moves a map that is already open.
//
// The on-demand Recenter half - a bottom-right prompt plus MMB / R3 while the
// map is up - is NOT REACHABLE FROM AN ASI SCRIPT. Not "unreliable": the code
// does not execute at all, because the SP script thread is suspended for the
// entire time the pause map is open.
//
// Proof, from the installed #117 instrumented build's own log
// (GameplayTweaks.map-zoom.log in the game root, one process launch,
// truncate-once-per-launch, 1454 hook heartbeats + 468 script heartbeats):
//   * The now-removed #117 diagnostic module emitted an unconditional 1 Hz
//     `hb script` line from the ScriptHook script thread and an unconditional
//     1 Hz `hb hook` line from an independent WH_MOUSE_LL worker thread.
//   * Across the window 631539328 -> 631609328 ms the hook thread logged 69
//     heartbeats with no gap over 1.1 s, while the script thread logged ZERO.
//     Seventy seconds of pause map with not one script frame. The same log has
//     script gaps of 203 s, 156 s and 125 s with the hook thread never missing
//     a beat.
//   * In all 468 `hb script` samples, mapApp (UIAPP_ACTIVE(joaat("MAP"))),
//     pauseMenu (IS_PAUSE_MENU_ACTIVE, natives.h:2242) and spPause
//     (_UI_IS_SINGLEPLAYER_PAUSE_MENU_ACTIVE, natives.h:3274) are ALL ZERO.
//     Not once does any of the three read true on a sampled frame.
//
// So the gate is not the wrong hash. There are no frames to evaluate it on.
// A UiPrompt only renders while something calls _UIPROMPT_SET_VISIBLE on it
// every frame, so the Recenter prompt could never appear; PAD:: reads and
// GetAsyncKeyState polls placed on the script thread could never observe a
// press. The single `requested middleMouse=1` line ever written to
// GameplayTweaks.map-recenter.log landed at 631525000, in a sub-second sliver
// between two script heartbeats that both read mapApp=0 - a launch/teardown
// transition frame, not a real in-map press. Its relaunch reported result=0.
//
// The previous close-and-relaunch state machine is therefore removed rather
// than retried. It was not merely dead: _CLOSE_APP_BY_HASH_IMMEDIATE
// (natives.h:7771) fired on that same spurious transition frame would eject the
// player from the frontend they had just opened.
//
// Recentering an already-open pause map is left UNFEASIBLE from script, on
// evidence. Auto-centering below covers every case except panning within one
// map session, and it is kept exactly as-is because it is the path that works.
//
// This function must still be serviced every frame by the integration
// dispatcher so the focus stays fresh as the player moves.
static bool g_pauseMapWasActive = false;
static DWORD g_pauseMapNextHeartbeat = 0;
static long g_pauseMapLogLines = 0;
static unsigned long g_pauseMapFrames = 0;
static unsigned long g_pauseMapFocusWrites = 0;

// gtLogInit truncates once per launch, so the log already describes this
// session only. The 20000-line cap is kept: it bounds this subsystem's own
// share of the shared file so a 1 Hz heartbeat cannot crowd everything else out.
static void logMapRecenter(const std::string& text) {
	if (g_pauseMapLogLines++ >= 20000) return;
	gtLog("map-recenter", GT_INFO, text);
}

static void setPauseMapFocusToPlayer(Ped ped) {
	if (!ped || !ENTITY::DOES_ENTITY_EXIST(ped)) return;
	const Vector3 p = ENTITY_COORDS(ped);
	// A zero radius requests a point focus without inventing a replacement zoom
	// radius. Confirmed in game: the map opens on the player at ordinary zoom.
	invoke<Void>(0xE0884C184728C75B, p.x, p.y, p.z, 0.0f);
	++g_pauseMapFocusWrites;
}

static void updatePauseMapRecenter(Ped ped) {
	const bool mapActive = UIAPP_ACTIVE(joaat("MAP")) != 0;
	++g_pauseMapFrames;

	// Log every edge unconditionally. A transition frame can fall between two
	// 1 Hz samples - that is exactly how the old build's one and only event line
	// was produced - so edges must not depend on the heartbeat cadence.
	if (mapActive != g_pauseMapWasActive) {
		logMapRecenter(std::string("mapApp edge active=") + (mapActive ? "1" : "0") +
			" frames=" + std::to_string(g_pauseMapFrames));
		g_pauseMapWasActive = mapActive;
	}

	// Idle heartbeat. This is the whole diagnostic contract: while the script
	// thread runs, this line appears once a second no matter what the feature
	// does. A silent stretch in the log is therefore positive evidence that the
	// script thread was not running, not evidence that nothing happened.
	const DWORD now = GetTickCount();
	if (now >= g_pauseMapNextHeartbeat) {
		g_pauseMapNextHeartbeat = now + 1000;
		logMapRecenter("hb mapApp=" + std::string(mapActive ? "1" : "0") +
			" frames=" + std::to_string(g_pauseMapFrames) +
			" focusWrites=" + std::to_string(g_pauseMapFocusWrites));
	}

	// The old implementation still wrote this native four times every second
	// while the map was closed. The startup-crash run ended after eight such
	// writes with the same asynchronous WAIT-stage abort previously caused by
	// the original per-frame implementation. Rate limiting was not ownership.
	//
	// Rockstar writes the focus ONCE immediately before launching MAP
	// (doc_newspaper.c:3425 then :3427). Mirror that transaction boundary: set
	// focus only on the physical opening edge for the direct map action or either
	// pause-menu action. Selecting MAP from the pause frontend consumes the focus
	// already written on that pause edge; direct INPUT_MAP consumes it immediately.
	const bool openingRequested =
		CONTROL_JUST_PRESSED(0, joaat("INPUT_MAP")) ||
		CONTROL_JUST_PRESSED(2, joaat("INPUT_MAP")) ||
		CONTROL_JUST_PRESSED(0, joaat("INPUT_FRONTEND_PAUSE")) ||
		CONTROL_JUST_PRESSED(2, joaat("INPUT_FRONTEND_PAUSE")) ||
		CONTROL_JUST_PRESSED(0, joaat("INPUT_FRONTEND_PAUSE_ALTERNATE")) ||
		CONTROL_JUST_PRESSED(2, joaat("INPUT_FRONTEND_PAUSE_ALTERNATE"));
	if (!mapActive && openingRequested) {
		setPauseMapFocusToPlayer(ped);
		logMapRecenter("opening focus write input-edge=1 focusWrites=" +
			std::to_string(g_pauseMapFocusWrites));
	}
}

// #35 TRAIN MAP MARKERS
//
// The old implementation treated `_DOES_TRAIN_EXIST_ON_TRACK` as proof that a
// train existed and then placed a coordinate blip at the track manager's cached
// position.  A route/track can remain active after its vehicle has streamed out
// or a mission has deleted it, which is exactly how orphaned markers survived
// despawn, cleanup and fast travel.
//
// Only streamed vehicle-pool entities may own a marker now.  These hashes are
// the three ordinary vanilla models whose vehicles.meta type is
// VEHICLE_TYPE_TRAIN_ENGINE.  Deliberately excluded are trolley01x,
// steamerDummy and the discoverable GhostTrainSteamer: none is an ordinary
// live railway train the map should reveal.
static bool isMapTrainEngine(Vehicle vehicle) {
	if (!vehicle || !ENTITY::DOES_ENTITY_EXIST(vehicle) ||
		!VEHICLE::IS_THIS_MODEL_A_TRAIN(ENTITY::GET_ENTITY_MODEL(vehicle)))
		return false;
	// Train carriages also satisfy IS_THIS_MODEL_A_TRAIN. Only the controlled
	// locomotive has a driver-seat occupant; this admits live engine variants
	// without placing a marker on every carriage in the consist.
	return VEHICLE::GET_PED_IN_VEHICLE_SEAT(vehicle, -1) != 0;
}

static Vehicle g_trainBlipEntities[32] = {};

static void retireTrainBlip(int slot) {
	if (g_trainBlips[slot]) REMOVE_MAP_BLIP(&g_trainBlips[slot]);
	g_trainBlips[slot] = 0;
	g_trainBlipEntities[slot] = 0;
}

static bool vehiclePoolContains(const int* vehicles, int count, Vehicle target) {
	for (int i = 0; i < count; ++i)
		if (vehicles[i] == target) return true;
	return false;
}

static int trainBlipSlotFor(Vehicle train) {
	for (int slot = 0; slot < 32; ++slot)
		if (g_trainBlipEntities[slot] == train) return slot;
	return -1;
}

static int freeTrainBlipSlot() {
	for (int slot = 0; slot < 32; ++slot)
		if (!g_trainBlipEntities[slot]) return slot;
	return -1;
}

static void updateTrainBlips() {
	int vehicles[512] = {};
	const int vehicleCount = g_trainTracking ? worldGetAllVehicles(vehicles, 512) : 0;

	// Retire first.  Absence from the current pool is streaming loss; a missing
	// entity is despawn/mission cleanup; a model mismatch also protects against
	// the engine reusing an old handle after fast travel.
	for (int slot = 0; slot < 32; ++slot) {
		const Vehicle train = g_trainBlipEntities[slot];
		if (!g_trainTracking || !train ||
			!vehiclePoolContains(vehicles, vehicleCount, train) ||
			!ENTITY::DOES_ENTITY_EXIST(train) ||
			!isMapTrainEngine(train)) {
			retireTrainBlip(slot);
			continue;
		}

		if (g_trainBlips[slot] && !MAP::DOES_BLIP_EXIST(g_trainBlips[slot]))
			g_trainBlips[slot] = 0;
	}

	if (!g_trainTracking) return;

	for (int i = 0; i < vehicleCount; ++i) {
		const Vehicle train = vehicles[i];
		if (!train || !ENTITY::DOES_ENTITY_EXIST(train) ||
			!isMapTrainEngine(train)) continue;

		int slot = trainBlipSlotFor(train);
		if (slot < 0) {
			slot = freeTrainBlipSlot();
			if (slot < 0) break;
			g_trainBlipEntities[slot] = train;
		}

		if (!g_trainBlips[slot]) {
			// BLIP_STYLE_TRAIN is Rockstar's own train presentation: ambient-train
			// art plus an Arrow heading.  The mission modifier makes a live train
			// visible across the pause map instead of only at the current zoom.
			g_trainBlips[slot] = MAP::_BLIP_ADD_FOR_ENTITY(joaat("BLIP_STYLE_TRAIN"), train);
			if (g_trainBlips[slot])
				ADD_BLIP_MODIFIER(g_trainBlips[slot], joaat("BLIP_MODIFIER_TRAIN_MISSION"));
		}

		// Entity blips follow position automatically.  Explicit rotation mirrors
		// Story Mode's feud1 train logic and keeps the arrow tied to travel heading.
		if (g_trainBlips[slot])
			MAP::SET_BLIP_ROTATION(g_trainBlips[slot],
				(int)std::lround(ENTITY::GET_ENTITY_HEADING(train)));
	}
}
