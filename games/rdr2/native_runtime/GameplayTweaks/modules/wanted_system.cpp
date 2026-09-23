// GitHub #50: runtime evidence for the post-search "dark-red lawmen" phase.
//
// The editable radius and escape-duration fields are already handled by
// LEXEDITOR.  ParoleDuration's unit and exact state transition are engine-owned
// and cannot be established from its name alone.  This trace is deliberately
// observational: it does not report a fake crime, alter wanted score, or keep
// an incident alive.  One normal crime/escape run records all exposed law
// states around the transition so the persistent multi-area layer can re-arm
// the state the game actually uses.

struct WantedTraceCrimeRecord {
	Any crimeType;
	Any fields[9];
	Any reported;
};

static_assert(sizeof(WantedTraceCrimeRecord) == sizeof(Any) * 11,
	"registered crime record must match Rockstar's 11-slot script struct");

static bool g_wantedTraceEnabled = true;
static DWORD g_wantedTraceIntervalMs = 250;
static DWORD g_wantedTraceTailMs = 180000;
static int g_wantedTraceVisualMarkerKey = VK_F8;
static DWORD g_wantedTraceNextSample = 0;
static DWORD g_wantedTraceStartedAt = 0;
static DWORD g_wantedTraceLastRelevantAt = 0;
static bool g_wantedTraceWasRelevant = false;
static bool g_wantedTraceMarkerWasDown = false;
static bool g_wantedTraceVisibleDarkRed = false;
static Vector3 g_wantedTraceOrigin = {};
static std::string g_wantedTraceLastState;

static void loadWantedSystemSettings() {
	g_wantedTraceEnabled = GetPrivateProfileIntA(
		"WantedSystem", "TraceEnabled", 1, g_iniPath.c_str()) != 0;
	const int interval = GetPrivateProfileIntA(
		"WantedSystem", "TraceIntervalMs", 250, g_iniPath.c_str());
	const int tailSeconds = GetPrivateProfileIntA(
		"WantedSystem", "TraceTailSeconds", 180, g_iniPath.c_str());
	g_wantedTraceVisualMarkerKey = GetPrivateProfileIntA(
		"WantedSystem", "VisualMarkerKey", VK_F8, g_iniPath.c_str());
	g_wantedTraceIntervalMs = (DWORD)(std::max)(50, (std::min)(2000, interval));
	g_wantedTraceTailMs = (DWORD)(std::max)(30, (std::min)(900, tailSeconds)) * 1000u;
}

static std::string wantedTraceNearbyLawSummary(Ped playerPed) {
	int peds[160] = {};
	const int count = sharedWorldPedSnapshot(peds, 160);
	int candidates = 0;
	int withBlip = 0;
	int onMinimap = 0;
	int onScreen = 0;
	std::ostringstream details;
	for (int index = 0; index < count; ++index) {
		const Ped other = peds[index];
		if (!other || other == playerPed || !ENTITY::DOES_ENTITY_EXIST(other) ||
			!PED::IS_PED_HUMAN(other) || PED::IS_PED_DEAD_OR_DYING(other, TRUE)) continue;
		const int relationship = invoke<int>(0xEBA5AD3A0EAF7121, other, playerPed);
		const bool combat = invoke<BOOL>(0x4859F1FC66A6278E, other, playerPed) != 0;
		const Blip blip = invoke<Blip>(0x6D2C41A8BD6D6FD0, other);
		const bool blipExists = blip && invoke<BOOL>(0xCD82FA174080B3B1, blip) != 0;
		if (relationship < 4 && !combat && !blipExists) continue;

		++candidates;
		const bool minimap = blipExists && invoke<BOOL>(0x46534526B9CD2D17, blip) != 0;
		const bool screen = invoke<BOOL>(0x613C15D5D8DB781F, other) != 0;
		if (blipExists) ++withBlip;
		if (minimap) ++onMinimap;
		if (screen) ++onScreen;
		if (candidates <= 12) {
			const Vector3 playerPos = ENTITY_COORDS(playerPed);
			const Vector3 otherPos = ENTITY_COORDS(other);
			const float dx = otherPos.x - playerPos.x;
			const float dy = otherPos.y - playerPos.y;
			const float dz = otherPos.z - playerPos.z;
			if (candidates > 1) details << ',';
			details << (int)other
				<< ":model=0x" << std::hex << (unsigned int)invoke<Hash>(0xDA76A9F39210D365, other)
				<< ":group=0x" << (unsigned int)invoke<Hash>(0x7DBDD04862D95F04, other)
				<< std::dec << ":rel=" << relationship
				<< ":combat=" << (combat ? 1 : 0)
				<< ":blip=" << (blipExists ? 1 : 0)
				<< ":minimap=" << (minimap ? 1 : 0)
				<< ":screen=" << (screen ? 1 : 0)
				<< ":distance=" << std::fixed << std::setprecision(1)
				<< sqrtf(dx * dx + dy * dy + dz * dz);
		}
	}
	std::ostringstream result;
	result << "candidates=" << candidates << ":blips=" << withBlip
		<< ":minimap=" << onMinimap << ":onscreen=" << onScreen
		<< ":details=" << (candidates ? details.str() : "none");
	return result.str();
}

static std::string wantedTraceCrimeSummary(Player player) {
	std::ostringstream out;
	int count = 0;
	for (int index = 0; index < 24; ++index) {
		WantedTraceCrimeRecord record = {};
		if (!invoke<BOOL>(0x532C5FDDB986EE5C, player, index, &record)) continue;
		if (count++) out << ',';
		out << index << ":0x" << std::hex << (unsigned int)(Hash)record.crimeType
			<< std::dec << ":reported=" << (record.reported ? 1 : 0)
			<< ":bounty=" << (int)record.fields[0]
			<< ":pair7=" << (int)record.fields[6];
	}
	if (!count) out << "none";
	return out.str();
}

// #126: routed to the unified GameplayTweaks.log under subsystem "wanted".
// The per-sample state line stays TRACE (very high volume, [Logging] Verbose=1
// gates it); the session markers stay INFO. The leading number remains the
// elapsed_ms SINCE THE TRACE STARTED, which is not the same clock as the
// facility's own session-elapsed column.
static void wantedTraceWrite(GtLogLevel level, const std::string& line) {
	gtLog("wanted", level, line);
}

static void initializeWantedSystemTrace() {
	g_wantedTraceNextSample = 0;
	g_wantedTraceStartedAt = 0;
	g_wantedTraceLastRelevantAt = 0;
	g_wantedTraceWasRelevant = false;
	g_wantedTraceMarkerWasDown = false;
	g_wantedTraceVisibleDarkRed = false;
	g_wantedTraceOrigin = {};
	g_wantedTraceLastState.clear();
	wantedTraceWrite(GT_INFO, "# GitHub #50 wanted/parole transition trace");
	wantedTraceWrite(GT_INFO,
		"# elapsed_ms pos law_incident wanted_score wanted_level hud_crime dispatch "
		"witnesses pending_witnesses investigators any_law_investigating "
		"seconds_since_seen radius origin_distance visual_dark_red nearby_law crimes");
	wantedTraceWrite(GT_INFO,
		"# Press F8 when the visible dark-red law-dot phase begins and again when it ends.");
}

static void updateWantedSystemTrace(Player player, Ped ped, DWORD now, bool blocked) {
	if (!g_wantedTraceEnabled || !ped || ENTITY::IS_ENTITY_DEAD(ped) || blocked) return;

	const bool lawIncident = invoke<BOOL>(0xAD401C63158ACBAA, player) != 0;
	const int wantedScore = invoke<int>(0xDD5FD601481F648B, player);
	const int wantedLevel = invoke<int>(0xABC532F9098BFD9D, player);
	const Hash hudCrime = invoke<Hash>(0x259CE340A8738814, player);
	const Hash dispatch = invoke<Hash>(0x148E7AC8141C9E64, player);
	const bool witnesses = invoke<BOOL>(0x69E181772886F48B, player) != 0;
	const bool pendingWitnesses = invoke<BOOL>(0x0BB6DE7D23C60626, player) != 0;
	const bool investigators = invoke<BOOL>(0xF0FBFB9AB15F7734, player, TRUE, 0) != 0;
	const bool anyLawInvestigating = invoke<BOOL>(0xECE3C34B270428D5) != 0;
	const float sinceSeen = invoke<float>(0x717DA2281DF90855, player);
	const bool relevant = lawIncident || wantedScore > 0 || wantedLevel > 0 ||
		hudCrime != 0 || dispatch != 0 || witnesses || pendingWitnesses ||
		investigators || anyLawInvestigating;

	if (relevant) g_wantedTraceLastRelevantAt = now;
	const bool tail = g_wantedTraceLastRelevantAt &&
		(now - g_wantedTraceLastRelevantAt <= g_wantedTraceTailMs);
	if (!relevant && !tail) {
		g_wantedTraceWasRelevant = false;
		g_wantedTraceStartedAt = 0;
		g_wantedTraceMarkerWasDown = false;
		g_wantedTraceVisibleDarkRed = false;
		g_wantedTraceLastState.clear();
		return;
	}
	if (!g_wantedTraceStartedAt) {
		g_wantedTraceStartedAt = now;
		g_wantedTraceOrigin = ENTITY_COORDS(ped);
		CASING_FEED("Wanted trace started - press F8 when dark-red law dots begin/end.", "", 0);
		wantedTraceWrite(GT_INFO, "BEGIN");
	}
	const bool markerDown = g_wantedTraceVisualMarkerKey > 0 &&
		(GetAsyncKeyState(g_wantedTraceVisualMarkerKey) & 0x8000) != 0;
	if (markerDown && !g_wantedTraceMarkerWasDown) {
		g_wantedTraceVisibleDarkRed = !g_wantedTraceVisibleDarkRed;
		std::ostringstream marker;
		marker << (now - g_wantedTraceStartedAt) << " VISUAL_MARK dark_red="
			<< (g_wantedTraceVisibleDarkRed ? 1 : 0);
		wantedTraceWrite(GT_INFO, marker.str());
		CASING_FEED(g_wantedTraceVisibleDarkRed ?
			"Wanted trace marked: dark-red dots visible." :
			"Wanted trace marked: dark-red dots ended.", "", 0);
	}
	g_wantedTraceMarkerWasDown = markerDown;

	std::ostringstream state;
	state << (lawIncident ? 1 : 0) << ' ' << wantedScore << ' ' << wantedLevel
		<< " 0x" << std::hex << (unsigned int)hudCrime
		<< " 0x" << (unsigned int)dispatch << std::dec
		<< ' ' << (witnesses ? 1 : 0) << ' ' << (pendingWitnesses ? 1 : 0)
		<< ' ' << (investigators ? 1 : 0) << ' ' << (anyLawInvestigating ? 1 : 0);
	const std::string compactState = state.str();
	const bool wasRelevant = g_wantedTraceWasRelevant;
	const bool transition = compactState != g_wantedTraceLastState ||
		relevant != g_wantedTraceWasRelevant;
	if (!transition && now < g_wantedTraceNextSample) return;
	g_wantedTraceNextSample = now + g_wantedTraceIntervalMs;
	g_wantedTraceLastState = compactState;
	g_wantedTraceWasRelevant = relevant;

	const Vector3 pos = ENTITY_COORDS(ped);
	const float originDx = pos.x - g_wantedTraceOrigin.x;
	const float originDy = pos.y - g_wantedTraceOrigin.y;
	const float originDz = pos.z - g_wantedTraceOrigin.z;
	const float wantedRadius = invoke<float>(0x80B00EB26D9521C7, wantedLevel);
	std::ostringstream line;
	line << (now - g_wantedTraceStartedAt) << " pos=" << std::fixed
		<< std::setprecision(2) << pos.x << ',' << pos.y << ',' << pos.z
		<< " law_incident=" << (lawIncident ? 1 : 0)
		<< " wanted_score=" << wantedScore << " wanted_level=" << wantedLevel
		<< " hud_crime=0x" << std::hex << (unsigned int)hudCrime
		<< " dispatch=0x" << (unsigned int)dispatch << std::dec
		<< " witnesses=" << (witnesses ? 1 : 0)
		<< " pending_witnesses=" << (pendingWitnesses ? 1 : 0)
		<< " investigators=" << (investigators ? 1 : 0)
		<< " any_law_investigating=" << (anyLawInvestigating ? 1 : 0)
		<< " seconds_since_seen=" << std::setprecision(3) << sinceSeen
		<< " radius=" << wantedRadius
		<< " origin_distance=" << sqrtf(originDx * originDx + originDy * originDy + originDz * originDz)
		<< " visual_dark_red=" << (g_wantedTraceVisibleDarkRed ? 1 : 0)
		<< " nearby_law=" << wantedTraceNearbyLawSummary(ped)
		<< " crimes=" << wantedTraceCrimeSummary(player);
	wantedTraceWrite(GT_TRACE, line.str());

	if (!relevant && tail && wasRelevant)
		CASING_FEED("Wanted trace entered the post-search tail.", "", 0);
}
