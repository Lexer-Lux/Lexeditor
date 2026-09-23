// GameplayTweaks feature module: #19 stealth/detection direction indicators.
// Included by script.cpp into the single ScriptHook translation unit.
//
// RDR2 does not expose a universal detection percentage. This module therefore
// renders only discrete, engine-observable states: an enemy is focused on and
// can see the player, a ped has targeted suspicion/is responding to that threat,
// or a ped is already fighting the player. The brief fade is presentation only;
// it is not represented as AI awareness.

enum class StealthIndicatorLevel : unsigned char {
	Focused = 1,
	Suspicious = 2,
	Alert = 3
};

struct StealthIndicatorState {
	Ped ped = 0;
	StealthIndicatorLevel level = StealthIndicatorLevel::Focused;
	DWORD observedAt = 0;
};

static std::vector<StealthIndicatorState> g_stealthIndicators;
static DWORD g_stealthIndicatorLastScan = 0;

static bool stealthIndicatorPerception(Ped observer, Ped playerPed) {
	// IS_TARGET_PED_IN_PERCEPTION_AREA means focused and looking at the target.
	// CAN_PED_SEE_ENTITY returns 1 for can-target, 2 for not-sure-yet; only the
	// affirmative result is suitable for a player-facing indicator.
	return invoke<BOOL>(0x06087579E7AA85A9, observer, playerPed,
		-1.0f, -1.0f, -1.0f, -1.0f) != 0 &&
		invoke<int>(0x7F9B9791D4CB71F6, observer, playerPed, FALSE, TRUE) == 1 &&
		ENTITY::HAS_ENTITY_CLEAR_LOS_TO_ENTITY(observer, playerPed, 17) != 0;
}

static float stealthIndicatorMotivation(Ped observer, int state, Ped playerPed) {
	// eMotivationState 3 = agitation, 9 = suspicion. Supplying playerPed keeps
	// unrelated ambient agitation from lighting an indicator.
	const float value = invoke<float>(0x42688E94E96FD9B4, observer, state, playerPed);
	return std::isfinite(value) ? (std::max)(0.0f, value) : 0.0f;
}

static StealthIndicatorLevel stealthIndicatorLevel(Ped observer, Ped playerPed,
	bool focused, bool* targetedThreatOut) {
	if (PED::IS_PED_IN_COMBAT(observer, playerPed))
		return StealthIndicatorLevel::Alert;
	const float suspicion = stealthIndicatorMotivation(observer, 9, playerPed);
	const float agitation = stealthIndicatorMotivation(observer, 3, playerPed);
	const bool responding = invoke<BOOL>(0x77525BBF433F2CD6, observer) != 0;
	const Player player = PLAYER::PLAYER_ID();
	const bool playerThreatening =
		PLAYER::IS_PLAYER_TARGETTING_ENTITY(player, observer, FALSE) ||
		PLAYER::IS_PLAYER_FREE_AIMING_AT_ENTITY(player, observer);
	const bool targetedThreat = playerThreatening && PED::IS_PED_FLEEING(observer);
	*targetedThreatOut = targetedThreat;
	if (suspicion > 0.01f || agitation >= 0.35f || targetedThreat ||
		(focused && responding))
		return StealthIndicatorLevel::Suspicious;
	return StealthIndicatorLevel::Focused;
}

static bool stealthIndicatorRelevant(Ped observer, Ped playerPed,
	bool* focusedOut, StealthIndicatorLevel* levelOut) {
	if (!observer || observer == playerPed ||
		!ENTITY::DOES_ENTITY_EXIST(observer) ||
		PED::IS_PED_DEAD_OR_DYING(observer, TRUE) ||
		!PED::IS_PED_HUMAN(observer)) return false;

	const Vector3 playerPos = ENTITY_COORDS(playerPed);
	const Vector3 observerPos = ENTITY_COORDS(observer);
	const float dx = observerPos.x - playerPos.x;
	const float dy = observerPos.y - playerPos.y;
	const float dz = observerPos.z - playerPos.z;
	if (dx * dx + dy * dy + dz * dz > 4225.0f) return false; // 65 m

	const bool focused = stealthIndicatorPerception(observer, playerPed);
	bool targetedThreat = false;
	const StealthIndicatorLevel level = stealthIndicatorLevel(observer, playerPed,
		focused, &targetedThreat);
	const int relation = PED::GET_RELATIONSHIP_BETWEEN_PEDS(observer, playerPed);
	const bool hostile = relation >= 4;

	// Stance and locomotion already feed the engine's perception/noise system.
	// They must not independently switch the HUD off. A focused warning remains
	// hostile-only so ordinary civilians glancing at Arthur do not create clutter;
	// neutrals appear only after player-targeted awareness or threat becomes real.
	if (level == StealthIndicatorLevel::Focused && (!hostile || !focused))
		return false;
	if (level == StealthIndicatorLevel::Suspicious && !focused &&
		stealthIndicatorMotivation(observer, 9, playerPed) <= 0.01f &&
		!targetedThreat)
		return false;

	*focusedOut = focused;
	*levelOut = level;
	return true;
}

static void scanStealthIndicators(Ped playerPed, DWORD now) {
	if (now - g_stealthIndicatorLastScan < 100) return;
	g_stealthIndicatorLastScan = now;

	int peds[160] = {};
	const int count = sharedWorldPedSnapshot(peds, 160);
	for (int i = 0; i < count; ++i) {
		Ped observer = peds[i];
		bool focused = false;
		StealthIndicatorLevel level = StealthIndicatorLevel::Focused;
		if (!stealthIndicatorRelevant(observer, playerPed, &focused, &level))
			continue;

		auto found = std::find_if(g_stealthIndicators.begin(), g_stealthIndicators.end(),
			[observer](const StealthIndicatorState& state) { return state.ped == observer; });
		if (found == g_stealthIndicators.end()) {
			StealthIndicatorState state;
			state.ped = observer;
			state.level = level;
			state.observedAt = now;
			g_stealthIndicators.push_back(state);
		} else {
			found->level = level;
			found->observedAt = now;
		}
	}

	for (size_t i = 0; i < g_stealthIndicators.size();) {
		const StealthIndicatorState& state = g_stealthIndicators[i];
		if (!ENTITY::DOES_ENTITY_EXIST(state.ped) ||
			PED::IS_PED_DEAD_OR_DYING(state.ped, TRUE) ||
			now - state.observedAt > 850) {
			g_stealthIndicators.erase(g_stealthIndicators.begin() + i);
		} else {
			++i;
		}
	}
}

static void drawStealthIndicator(const StealthIndicatorState& state, Ped playerPed,
	DWORD now) {
	const Vector3 playerPos = ENTITY_COORDS(playerPed);
	const Vector3 observerPos = ENTITY_COORDS(state.ped);
	const float bearing = std::atan2(-(observerPos.x - playerPos.x),
		observerPos.y - playerPos.y) * 57.2957795f;
	float relative = bearing - CAM::GET_GAMEPLAY_CAM_ROT(2).z;
	while (relative > 180.0f) relative -= 360.0f;
	while (relative < -180.0f) relative += 360.0f;
	const float radians = relative * 0.0174532925f;

	// A shallow ring around the aiming area conveys direction without becoming
	// a screen-edge HUD frame. The shipped blip ring keeps the visual language
	// consistent with Rockstar's minimap and this mod's recon markers.
	const float x = 0.5f - std::sin(radians) * 0.135f;
	const float y = 0.445f - std::cos(radians) * 0.072f;
	int r = 236, g = 230, b = 211;
	if (state.level == StealthIndicatorLevel::Suspicious) {
		r = 230; g = 177; b = 63;
	} else if (state.level == StealthIndicatorLevel::Alert) {
		r = 194; g = 45; b = 38;
	}
	const DWORD age = now - state.observedAt;
	const int alpha = age <= 350 ? 235 :
		(std::max)(0, 235 - (int)((age - 350) * 235 / 500));
	const float pulse = state.level == StealthIndicatorLevel::Alert ?
		1.0f + 0.10f * std::sin(now * 0.012f) : 1.0f;
	GRAPHICS::DRAW_SPRITE("blips", "blip_overlay_ring", x, y,
		0.024f * pulse, 0.043f * pulse, 0.0f, r, g, b, alpha, FALSE);
}

static void updateStealthDetectionIndicators(Ped playerPed, DWORD now, bool unavailable) {
	if (unavailable || !playerPed || HUD::IS_PAUSE_MENU_ACTIVE() ||
		scriptRunning("satchel_ui_event_handler") || scriptRunning("satchel")) {
		g_stealthIndicators.clear();
		return;
	}
	if (!invoke<BOOL>(0x54D6900929CCF162, "blips")) {
		invoke<Void>(0xC1BA29DF5631B0F8, "blips", FALSE);
		return;
	}
	scanStealthIndicators(playerPed, now);

	// Highest-confidence states draw first, then nearest peds. Cap the display to
	// four so a camp never turns into an arcade-style halo.
	std::vector<StealthIndicatorState> visible = g_stealthIndicators;
	std::sort(visible.begin(), visible.end(), [playerPed](const StealthIndicatorState& a,
		const StealthIndicatorState& b) {
		if (a.level != b.level) return (int)a.level > (int)b.level;
		const Vector3 origin = ENTITY_COORDS(playerPed);
		const Vector3 pa = ENTITY_COORDS(a.ped), pb = ENTITY_COORDS(b.ped);
		const float adx = pa.x - origin.x, ady = pa.y - origin.y;
		const float bdx = pb.x - origin.x, bdy = pb.y - origin.y;
		return adx * adx + ady * ady < bdx * bdx + bdy * bdy;
	});
	const size_t shown = (std::min)((size_t)4, visible.size());
	for (size_t i = 0; i < shown; ++i)
		drawStealthIndicator(visible[i], playerPed, now);
}
