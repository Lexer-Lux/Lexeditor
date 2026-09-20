// GitHub #99: recoverable lost money carried by the player's actual last hat.
// Integration replaces the superseded BloodstainState block in world_economy.cpp
// with this file; the existing load/place/update call sites remain unchanged.

struct BloodstainState {
	bool active = false;
	int cash = 0;
	Vector3 position = {};
	Hash hatModel = 0;
	Blip blip = 0;
	Object prop = 0;
	DWORD captureUntil = 0;
	bool notificationShown = false;
	bool playerWasNearHat = false;
};

static const char* kBloodstainNotification =
	"Find your hat where near where you died and collect it to reclaim your money. If you die before then, it will be gone forever.";
static float g_bloodstainBlipScale = 1.4f;
static float g_bloodstainMarkerScale = 1.0f;
static BloodstainState g_bloodstain;
static int g_bloodstainPickupPrompt = 0;
static bool g_bloodstainPickupPromptRegistered = false;

static float bloodstainDistanceSquared(const Vector3& a, const Vector3& b) {
	const float dx = a.x - b.x;
	const float dy = a.y - b.y;
	const float dz = a.z - b.z;
	return dx * dx + dy * dy + dz * dz;
}

static void bloodstainLog(const char* event, Object hat = 0, Hash model = 0) {
	std::ostringstream log;
	log << event << " cash=" << g_bloodstain.cash
		<< " hat=" << hat << " model=0x" << std::hex << std::uppercase << model
		<< std::dec << " x=" << g_bloodstain.position.x
		<< " y=" << g_bloodstain.position.y << " z=" << g_bloodstain.position.z;
	gtLog("bloodstain", GT_INFO, log.str());
}

static void loadBloodstainSettings() {
	g_bloodstainBlipScale = readF("LostMoney", "MapIconScale", 1.4f);
	if (g_bloodstainBlipScale < 0.5f) g_bloodstainBlipScale = 0.5f;
	if (g_bloodstainBlipScale > 3.0f) g_bloodstainBlipScale = 3.0f;
	g_bloodstainMarkerScale = readF("LostMoney", "WorldMarkerScale", 1.0f);
	if (g_bloodstainMarkerScale < 0.25f) g_bloodstainMarkerScale = 0.25f;
	if (g_bloodstainMarkerScale > 4.0f) g_bloodstainMarkerScale = 4.0f;
}

static std::string bloodstainPath() {
	return g_moduleDir + "\\GameplayTweaks.bloodstain.dat";
}

static void saveBloodstain() {
	std::ofstream out(bloodstainPath(), std::ios::trunc);
	out << "hat-v2 " << (g_bloodstain.active ? 1 : 0) << ' ' << g_bloodstain.cash << ' '
		<< g_bloodstain.position.x << ' ' << g_bloodstain.position.y << ' '
		<< g_bloodstain.position.z << ' ' << g_bloodstain.hatModel << ' '
		<< (g_bloodstain.notificationShown ? 1 : 0) << '\n';
}

static void loadBloodstain() {
	std::ifstream in(bloodstainPath());
	std::string version;
	int active = 0, notificationShown = 0;
	if (!(in >> version) || version != "hat-v2" ||
		!(in >> active >> g_bloodstain.cash >> g_bloodstain.position.x >>
			g_bloodstain.position.y >> g_bloodstain.position.z >> g_bloodstain.hatModel >>
			notificationShown)) {
		// The old unversioned record represented a cash bag and cannot identify the
		// requested last-worn hat. Never resurrect that superseded presentation.
		g_bloodstain = {};
		saveBloodstain();
		return;
	}
	g_bloodstain.active = active != 0 && g_bloodstain.cash > 0;
	g_bloodstain.notificationShown = notificationShown != 0;
	if (g_bloodstain.active && !g_bloodstain.hatModel)
		g_bloodstain.captureUntil = GetTickCount() + 3000;
}

static void removeBloodstainBlip() {
	if (g_bloodstain.blip) REMOVE_MAP_BLIP(&g_bloodstain.blip);
}

static void hideBloodstainPickupPrompt() {
	if (!g_bloodstainPickupPromptRegistered) return;
	CASING_PROMPT_VISIBLE(g_bloodstainPickupPrompt, FALSE);
	CASING_PROMPT_ENABLED(g_bloodstainPickupPrompt, FALSE);
}

static void removeBloodstainProp() {
	if (g_bloodstain.prop && ENTITY::DOES_ENTITY_EXIST(g_bloodstain.prop)) {
		ENTITY::SET_ENTITY_AS_MISSION_ENTITY(g_bloodstain.prop, TRUE, TRUE);
		Object handle = g_bloodstain.prop;
		OBJECT::DELETE_OBJECT(&handle);
	}
	g_bloodstain.prop = 0;
}

static void abandonBloodstain(const char* reason) {
	if (g_bloodstain.active) bloodstainLog(reason, g_bloodstain.prop, g_bloodstain.hatModel);
	hideBloodstainPickupPrompt();
	removeBloodstainBlip();
	removeBloodstainProp();
	g_bloodstain = {};
	saveBloodstain();
}

static Object getLastDroppedHat(Ped ped) {
	return ped ? invoke<Object>(0x1F714E7A9DADFC42, ped) : 0;
}

static void moveCapturedHatToBloodstain(Object hat) {
	ENTITY::SET_ENTITY_AS_MISSION_ENTITY(hat, TRUE, TRUE);
	invoke<Void>(0x06843DA7060A026B, hat,
		g_bloodstain.position.x, g_bloodstain.position.y,
		g_bloodstain.position.z + 0.08f, FALSE, FALSE, FALSE, TRUE);
	OBJECT::PLACE_OBJECT_ON_GROUND_PROPERLY(hat, TRUE);
	ENTITY::FREEZE_ENTITY_POSITION(hat, FALSE);
	ENTITY::SET_ENTITY_COLLISION(hat, TRUE, TRUE);
	g_bloodstain.prop = hat;
	g_bloodstain.hatModel = ENTITY::GET_ENTITY_MODEL(hat);
	g_bloodstain.captureUntil = 0;
	g_bloodstain.playerWasNearHat = false;
	const bool showNotification = !g_bloodstain.notificationShown;
	g_bloodstain.notificationShown = true;
	saveBloodstain();
	if (showNotification) {
		CASING_FEED(kBloodstainNotification, "", 0);
	}
	bloodstainLog("captured-last-dropped-hat", hat, g_bloodstain.hatModel);
}

static bool captureLastWornHat(Ped ped, bool knockOff) {
	Object before = getLastDroppedHat(ped);
	if (knockOff && ped)
		invoke<Void>(0x6FD7816A36615F48, ped, FALSE, TRUE, FALSE, TRUE);
	Object after = getLastDroppedHat(ped);
	Object hat = after && ENTITY::DOES_ENTITY_EXIST(after) ? after : before;
	if (!hat || !ENTITY::DOES_ENTITY_EXIST(hat)) return false;
	moveCapturedHatToBloodstain(hat);
	return true;
}

static void ensureBloodstainProp(Ped ped) {
	if (!g_bloodstain.active || g_bloodstain.prop) return;
	if (!g_bloodstain.hatModel) {
		if (captureLastWornHat(ped, false)) return;
		if (g_bloodstain.captureUntil && GetTickCount() >= g_bloodstain.captureUntil) {
			// Cash was removed before placeBloodstain() was called. If no current or
			// recent hat can be captured, restore it instead of silently losing money
			// to a bloodstain the player can never recover.
			const int refund = g_bloodstain.cash;
			if (refund > 0 && ADD_CASH(refund)) abandonBloodstain("no-hat-captured-cash-refunded");
		}
		return;
	}
	const Vector3 playerPosition = ENTITY_COORDS(ped);
	if (bloodstainDistanceSquared(playerPosition, g_bloodstain.position) > 120.0f * 120.0f) return;
	if (!STREAMING::HAS_MODEL_LOADED(g_bloodstain.hatModel)) {
		STREAMING::REQUEST_MODEL(g_bloodstain.hatModel, FALSE);
		return;
	}
	Object hat = OBJECT::CREATE_OBJECT(g_bloodstain.hatModel,
		g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 0.08f,
		FALSE, FALSE, FALSE, FALSE, TRUE);
	if (!hat) return;
	moveCapturedHatToBloodstain(hat);
	bloodstainLog("recreated-persisted-hat", hat, g_bloodstain.hatModel);
}

static void createBloodstainBlip() {
	if (!g_bloodstain.active || !g_bloodstain.hatModel || g_bloodstain.blip) return;
	g_bloodstain.blip = ADD_COORD_BLIP((Hash)-1337945352, g_bloodstain.position);
	SET_BLIP_ICON(g_bloodstain.blip, joaat("LEX_BLIP_HAT_BLOODSTAIN"));
	ADD_BLIP_MODIFIER(g_bloodstain.blip, joaat("BLIP_MODIFIER_RADAR_EDGE_ALWAYS"));
	SET_BLIP_SCALE(g_bloodstain.blip, g_bloodstainBlipScale);
	SET_BLIP_NAME(g_bloodstain.blip, "Lost Hat");
}

static void placeBloodstain(Vector3 death, int cash) {
	// This ordering is the one-bloodstain guarantee: the previous prop, markers,
	// and unrecovered cash are destroyed before the new death captures anything.
	abandonBloodstain("superseded-by-second-death");
	Vector3 safe = death;
	if (!SAFE_PED_COORD(death, &safe)) {
		float z = death.z;
		if (GROUND_Z(death, &z)) safe.z = z;
	}
	g_bloodstain.active = cash > 0;
	g_bloodstain.cash = cash;
	g_bloodstain.position = safe;
	g_bloodstain.captureUntil = GetTickCount() + 3000;
	saveBloodstain();
	if (g_bloodstain.active) captureLastWornHat(PLAYER::PLAYER_PED_ID(), true);
	createBloodstainBlip();
}

static void registerBloodstainPickupPrompt() {
	if (g_bloodstainPickupPromptRegistered) return;
	g_bloodstainPickupPrompt = CASING_PROMPT_BEGIN();
	CASING_PROMPT_CONTROL(g_bloodstainPickupPrompt, joaat("INPUT_CONTEXT_X"));
	CASING_PROMPT_TEXT(g_bloodstainPickupPrompt, CASING_LITERAL("Pick Up Hat"));
	CASING_PROMPT_HOLD(g_bloodstainPickupPrompt, joaat("SHORT_TIMED_EVENT"));
	CASING_PROMPT_END(g_bloodstainPickupPrompt);
	CASING_PROMPT_VISIBLE(g_bloodstainPickupPrompt, FALSE);
	CASING_PROMPT_ENABLED(g_bloodstainPickupPrompt, FALSE);
	g_bloodstainPickupPromptRegistered = true;
}

static bool recoverBloodstain() {
	const int amount = g_bloodstain.cash;
	if (amount <= 0 || !ADD_CASH(amount)) return false;
	bloodstainLog("hat-picked-up-cash-restored", g_bloodstain.prop, g_bloodstain.hatModel);
	hideBloodstainPickupPrompt();
	removeBloodstainBlip();
	removeBloodstainProp();
	g_bloodstain = {};
	saveBloodstain();
	if (g_bloodstainPickupPromptRegistered) CASING_PROMPT_RESTART(g_bloodstainPickupPrompt);
	return true;
}

static void updateBloodstain(Ped ped) {
	if (!g_bloodstain.active) {
		hideBloodstainPickupPrompt();
		return;
	}
	registerBloodstainPickupPrompt();
	createBloodstainBlip();
	ensureBloodstainProp(ped);
	if (!g_bloodstain.active) return;

	const Vector3 playerPosition = ENTITY_COORDS(ped);
	bool hatExists = g_bloodstain.prop && ENTITY::DOES_ENTITY_EXIST(g_bloodstain.prop);
	bool nearHat = bloodstainDistanceSquared(playerPosition, g_bloodstain.position) <= 2.25f * 2.25f;
	if (hatExists) {
		const Vector3 hatPosition = ENTITY_COORDS(g_bloodstain.prop);
		g_bloodstain.position = hatPosition;
		if (g_bloodstain.blip) SET_BLIP_POS(g_bloodstain.blip, hatPosition);
		nearHat = bloodstainDistanceSquared(playerPosition, hatPosition) <= 2.25f * 2.25f;
		// Vanilla hat pickup either consumes the dropped object or briefly attaches
		// it to the player. An attachment near the player is therefore recovery,
		// not a radius-only auto-award.
		if (nearHat && ENTITY::IS_ENTITY_ATTACHED(g_bloodstain.prop)) {
			recoverBloodstain();
			return;
		}
	} else if (g_bloodstain.playerWasNearHat && nearHat) {
		// The engine consumed the dropped-hat object during its native pickup.
		if (recoverBloodstain()) return;
	}
	if (!hatExists && !(g_bloodstain.playerWasNearHat && nearHat))
		g_bloodstain.prop = 0;

	CASING_PROMPT_VISIBLE(g_bloodstainPickupPrompt, nearHat ? TRUE : FALSE);
	CASING_PROMPT_ENABLED(g_bloodstainPickupPrompt, nearHat ? TRUE : FALSE);
	if (nearHat && CASING_PROMPT_DONE(g_bloodstainPickupPrompt)) {
		recoverBloodstain();
		return;
	}
	g_bloodstain.playerWasNearHat = nearHat && hatExists;

	// A subdued blood-red pool/column identifies the physical hat without
	// reviving the superseded gold cash-bag presentation.
	const float s = g_bloodstainMarkerScale;
	const float pulse = 0.85f + 0.15f * sinf(GetTickCount() * 0.004f);
	GRAPHICS::_DRAW_MARKER(kMarkerVerticalCylinder,
		g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 0.03f,
		0, 0, 0, 0, 0, 0, 1.15f * s, 1.15f * s, 0.045f,
		120, 8, 12, 175, FALSE, FALSE, 0, FALSE, nullptr, nullptr, FALSE);
	GRAPHICS::_DRAW_MARKER(kMarkerVerticalCylinder,
		g_bloodstain.position.x, g_bloodstain.position.y, g_bloodstain.position.z + 1.15f,
		0, 0, 0, 0, 0, 0, 0.14f * s * pulse, 0.14f * s * pulse, 2.3f,
		150, 12, 16, 105, FALSE, FALSE, 0, FALSE, nullptr, nullptr, FALSE);
}
