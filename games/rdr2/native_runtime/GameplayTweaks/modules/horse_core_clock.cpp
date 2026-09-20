// GameplayTweaks feature module: independent owned/current-horse core clock
// settings (GitHub #145).
//
// Included by script.cpp into the one ScriptHook translation unit. The module
// deliberately owns its config refresh so CoreClock's shared loadConfig body
// needs no horse-specific globals or parsing.

struct HorseCoreClockState {
	Ped horse = 0;
	Hash model = 0;
	int managedCore[2] = { 100, 100 };
	double drainBank[2] = {};
	DWORD lastSeenAt = 0;
	bool initialized = false;
};

static HorseCoreClockState g_horseCoreClockStates[2];
static bool g_horseCoreClockEnabled = true;
static float g_horseHealthDrainHours = 24.0f;
static float g_horseStaminaDrainHours = 24.0f;
static DWORD g_horseCoreClockNextConfigAt = 0;
static DWORD g_horseCoreClockNextUpdateAt = 0;
static DWORD g_horseCoreClockNextHeartbeatAt = 0;
static DWORD g_horseCoreClockNextReadbackWarningAt = 0;
static int g_horseCoreClockLastMinute = -1;
static int g_horseCoreClockLastJump = 0;

static float horseCoreClockReadHours(const char* key, float fallback) {
	// Same validation floor as the existing Arthur/John CoreClock durations.
	return (std::max)(0.01f, readF("CoreClock", key, fallback));
}

static void resetHorseCoreClockStates() {
	for (HorseCoreClockState& state : g_horseCoreClockStates)
		state = HorseCoreClockState{};
}

static void refreshHorseCoreClockConfig(DWORD now) {
	if (g_horseCoreClockNextConfigAt && now < g_horseCoreClockNextConfigAt) return;
	g_horseCoreClockNextConfigAt = now + 2000;
	const bool enabled = GetPrivateProfileIntA("CoreClock", "Enabled", 1,
		g_iniPath.c_str()) != 0;
	const float health = horseCoreClockReadHours("HorseHealthDrainHours", 24.0f);
	const float stamina = horseCoreClockReadHours("HorseStaminaDrainHours", 24.0f);
	const bool healthChanged = std::fabs(health - g_horseHealthDrainHours) > 0.0001f;
	const bool staminaChanged = std::fabs(stamina - g_horseStaminaDrainHours) > 0.0001f;
	const bool changed = enabled != g_horseCoreClockEnabled || healthChanged || staminaChanged;
	g_horseCoreClockEnabled = enabled;
	g_horseHealthDrainHours = health;
	g_horseStaminaDrainHours = stamina;
	if (changed) {
		// A hot reload applies only to future in-game minutes. Discard fractional
		// points accumulated under the old rates instead of charging them later.
		for (HorseCoreClockState& state : g_horseCoreClockStates) {
			if (healthChanged) state.drainBank[0] = 0.0;
			if (staminaChanged) state.drainBank[1] = 0.0;
		}
		char line[192] = {};
		sprintf_s(line, "config reloaded enabled=%d healthHours=%.3f staminaHours=%.3f futureMinutesOnly=1",
			g_horseCoreClockEnabled ? 1 : 0, g_horseHealthDrainHours,
			g_horseStaminaDrainHours);
		gtLog("horse-core-clock", GT_INFO, line);
	}
}

static HorseCoreClockState* horseCoreClockStateFor(Ped horse, DWORD now) {
	const Hash model = ENTITY_MODEL(horse);
	HorseCoreClockState* slot = nullptr;
	for (HorseCoreClockState& state : g_horseCoreClockStates) {
		if (state.horse == horse) {
			if (state.model == model) {
				state.lastSeenAt = now;
				return &state;
			}
			// Entity handles may be reused after streaming. A model mismatch is a
			// replacement horse and must never inherit the former horse's banks.
			state = HorseCoreClockState{};
			slot = &state;
			break;
		}
	}
	if (!slot) {
		for (HorseCoreClockState& state : g_horseCoreClockStates) {
			if (!state.horse || now - state.lastSeenAt > 5000) {
				slot = &state;
				break;
			}
		}
	}
	if (!slot) slot = &g_horseCoreClockStates[0];
	*slot = HorseCoreClockState{};
	slot->horse = horse;
	slot->model = model;
	slot->lastSeenAt = now;
	return slot;
}

static void horseCoreClockWrite(HorseCoreClockState& state, int core, int value,
	DWORD now) {
	SET_HORSE_CORE(state.horse, core, value);
	const int readback = GET_CORE(state.horse, core);
	if (readback != value && now >= g_horseCoreClockNextReadbackWarningAt) {
		g_horseCoreClockNextReadbackWarningAt = now + 5000;
		char line[160] = {};
		sprintf_s(line, "write readback mismatch horse=%d core=%d requested=%d readback=%d",
			(int)state.horse, core, value, readback);
		gtLog("horse-core-clock", GT_WARN, line);
	}
}

static void horseCoreClockDrain(HorseCoreClockState& state, int core,
	int minutes, float drainHours, DWORD now) {
	if (minutes <= 0) return;
	state.drainBank[core] += (double)minutes * 100.0 /
		((double)drainHours * 60.0);
	const int points = (int)(state.drainBank[core] + 0.000001);
	if (points <= 0) return;
	state.drainBank[core] -= points;
	state.managedCore[core] = (std::max)(0, state.managedCore[core] - points);
	horseCoreClockWrite(state, core, state.managedCore[core], now);
}

static void updateOneHorseCoreClock(Ped horse, DWORD now, int jump) {
	if (!horse || !ENTITY::DOES_ENTITY_EXIST(horse) ||
		PED::IS_PED_DEAD_OR_DYING(horse, TRUE)) return;
	HorseCoreClockState& state = *horseCoreClockStateFor(horse, now);
	if (!state.initialized) {
		state.managedCore[0] = GET_CORE(horse, 0);
		state.managedCore[1] = GET_CORE(horse, 1);
		state.initialized = true;
		return; // Never back-charge minutes that elapsed before this horse resolved.
	}

	// Four-Hz reconciliation replaces Rockstar's ordinary one-point background
	// metabolism without placing core natives on a per-frame path. Substantial
	// food/tonic/script changes remain authoritative, matching player CoreClock.
	for (int core = 0; core < 2; ++core) {
		const int live = GET_CORE(horse, core);
		if (live > state.managedCore[core] + 1 || live < state.managedCore[core] - 1)
			state.managedCore[core] = live;
		else if (live != state.managedCore[core])
			horseCoreClockWrite(state, core, state.managedCore[core], now);
	}
	horseCoreClockDrain(state, 0, jump, g_horseHealthDrainHours, now);
	horseCoreClockDrain(state, 1, jump, g_horseStaminaDrainHours, now);
}

// Integration-owned script.cpp calls this once per frame. The function itself
// bounds entity/core reads to four Hz and configuration reads to once per two
// real seconds. In-game clock jumps up to twenty hours include sleep/fast travel,
// matching the existing player CoreClock window.
static void updateHorseCoreClock(Player player, Ped playerPed, DWORD now) {
	refreshHorseCoreClockConfig(now);
	if (now < g_horseCoreClockNextUpdateAt) return;
	g_horseCoreClockNextUpdateAt = now + 250;

	const int minute = clockMinute();
	if (!g_horseCoreClockEnabled || !playerPed ||
		!ENTITY::DOES_ENTITY_EXIST(playerPed)) {
		g_horseCoreClockLastMinute = minute;
		g_horseCoreClockLastJump = 0;
		resetHorseCoreClockStates();
		if (now >= g_horseCoreClockNextHeartbeatAt) {
			g_horseCoreClockNextHeartbeatAt = now + 30000;
			char line[160] = {};
			sprintf_s(line,
				"heartbeat executed=1 enabled=%d targets=0 playerAvailable=%d",
				g_horseCoreClockEnabled ? 1 : 0,
				playerPed && ENTITY::DOES_ENTITY_EXIST(playerPed) ? 1 : 0);
			gtLog("horse-core-clock", GT_INFO, line);
		}
		return;
	}
	if (g_horseCoreClockLastMinute < 0) g_horseCoreClockLastMinute = minute;
	const int jump = forwardMinutes(g_horseCoreClockLastMinute, minute);
	g_horseCoreClockLastMinute = minute;
	g_horseCoreClockLastJump = jump > 0 && jump <= 1200 ? jump : 0;

	const Ped ownedHorse = GET_OWNED_MOUNT(player);
	const Ped currentHorse = GET_MOUNT(playerPed);
	for (HorseCoreClockState& state : g_horseCoreClockStates)
		if (state.horse && state.horse != ownedHorse && state.horse != currentHorse)
			state = HorseCoreClockState{};
	updateOneHorseCoreClock(ownedHorse, now, g_horseCoreClockLastJump);
	if (currentHorse != ownedHorse)
		updateOneHorseCoreClock(currentHorse, now, g_horseCoreClockLastJump);

	if (now >= g_horseCoreClockNextHeartbeatAt) {
		g_horseCoreClockNextHeartbeatAt = now + 30000;
		int targets = 0;
		for (const HorseCoreClockState& state : g_horseCoreClockStates)
			if (state.horse && now - state.lastSeenAt <= 5000) ++targets;
		char line[224] = {};
		sprintf_s(line,
			"heartbeat executed=1 enabled=1 targets=%d owned=%d current=%d jumpMinutes=%d healthHours=%.3f staminaHours=%.3f",
			targets, (int)ownedHorse, (int)currentHorse,
			g_horseCoreClockLastJump, g_horseHealthDrainHours,
			g_horseStaminaDrainHours);
		gtLog("horse-core-clock", GT_INFO, line);
	}
}
