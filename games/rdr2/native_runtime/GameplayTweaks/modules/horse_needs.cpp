// GameplayTweaks feature module: autonomous owned-horse feeding and drinking (#91).
//
// Trough drinking follows the exact task/animation sequence recovered from
// Thirsty Horse 1.6: approach, face the source, then play Rockstar's authored
// trough ENTER/BASE pair. Hay uses Rockstar's domestic grazing scenario at a
// validated dry, level point.

enum class HorseNeedAction { None, Drink, Eat };
enum class HorseDrinkStage { None, Approaching, Aligning, Entering, Drinking };

struct HorseNeedSource {
	HorseNeedAction action = HorseNeedAction::None;
	Hash model = 0;
	Hash scenario = 0;
	float radius = 0.0f;
};

struct HorseNeedRuntime {
	Ped horse = 0;
	HorseNeedAction action = HorseNeedAction::None;
	Entity source = 0;
	Hash scenario = 0;
	int scenarioPoint = 0;
	bool ownsScenarioPoint = false;
	HorseDrinkStage drinkStage = HorseDrinkStage::None;
	Vector3 drinkTarget = {};
	float drinkHeading = 0.0f;
	DWORD drinkStageAt = 0;
	bool drinkEnterIssued = false;
	DWORD idleSince = 0;
	DWORD issuedAt = 0;
	DWORD enteredAt = 0;
	DWORD lastRestoreAt = 0;
	DWORD cooldownUntil = 0;
	DWORD nextSourceScanAt = 0;
};

static HorseNeedRuntime g_horseNeedRuntime;
static std::vector<HorseNeedSource> g_horseNeedSources;
static bool g_horseNeedSourcesLoaded = false;
static bool g_horseNeedsEnabled = true;
static bool g_horseNeedsTrace = false;
static int g_horseNeedsIdleMs = 15000;
static int g_horseNeedsApproachTimeoutMs = 20000;
static int g_horseNeedsMinimumUseMs = 4000;
static int g_horseNeedsMaximumUseMs = 24000;
static int g_horseNeedsCooldownMs = 300000;
static int g_horseNeedsRestoreIntervalMs = 1000;
static int g_horseNeedsRestorePoints = 5;
static int g_horseNeedsTriggerCore = 75;
static float g_horseNeedsMinimumPlayerDistance = 6.0f;
static float g_horseNeedsMaximumPlayerDistance = 80.0f;
static DWORD g_horseNeedsNextConfigRead = 0;
static DWORD g_horseNeedsNextHeartbeatAt = 0;
static std::string g_horseNeedsLastStartResult = "not_attempted";
static std::string g_horseNeedsLastConfigSummary;

struct HorseDrinkMapMarker {
	Object object = 0;
	Blip blip = 0;
	DWORD seenAt = 0;
};

static std::vector<HorseDrinkMapMarker> g_horseDrinkMapMarkers;
static DWORD g_horseDrinkNextMapScanAt = 0;
static bool g_horseDrinkTextureProbeLogged = false;

static constexpr uint64_t kHorseNeedsDeleteScenarioPointHash =
	0x81948DFE4F5A0283ULL; // TASK::DELETE_SCENARIO_POINT
static constexpr uint64_t kIsPedLeadingHorseHash =
	0xEFC4303DDC6E60D3ULL; // PED::_IS_PED_LEADING_HORSE
static constexpr uint64_t kGetLedHorseFromPedHash =
	0xED1F514AF4732258ULL; // PED::_GET_LED_HORSE_FROM_PED
static constexpr uint64_t kGetActiveHorseForPlayerHash =
	0x46FA0AE18F4C7FA9ULL; // PLAYER::_GET_ACTIVE_HORSE_FOR_PLAYER
static constexpr uint64_t kGetSaddleHorseForPlayerHash =
	0xB48050D326E9A2F3ULL; // PLAYER::_GET_SADDLE_HORSE_FOR_PLAYER

static constexpr const char* kHorseDrinkEnterDict =
	"AMB_CREATURE_MAMMAL@PROP_HORSE_DRINK_TROUGH@STAND_ENTER";
static constexpr const char* kHorseDrinkEnterClip = "ENTER";
static constexpr const char* kHorseDrinkBaseDict =
	"AMB_CREATURE_MAMMAL@PROP_HORSE_DRINK_TROUGH@BASE";
static constexpr const char* kHorseDrinkBaseClip = "BASE";

struct HorseNeedResolvedHorse {
	Ped selected = 0;
	const char* source = "none";
	Ped mount = 0;
	Ped led = 0;
	Ped active = 0;
	Ped saddle = 0;
	Ped owned = 0;
};

static bool validHorseNeedHorse(Ped horse) {
	return horse && ENTITY::DOES_ENTITY_EXIST(horse) &&
		!PED::IS_PED_HUMAN(horse) && !PED::IS_PED_DEAD_OR_DYING(horse, TRUE);
}

static HorseNeedResolvedHorse resolveHorseNeedHorse(Player player, Ped playerPed) {
	HorseNeedResolvedHorse result;
	result.mount = playerPed ? GET_MOUNT(playerPed) : 0;
	result.led = playerPed && invoke<BOOL>(kIsPedLeadingHorseHash, playerPed) ?
		invoke<Ped>(kGetLedHorseFromPedHash, playerPed) : 0;
	result.active = invoke<Ped>(kGetActiveHorseForPlayerHash, player);
	result.saddle = invoke<Ped>(kGetSaddleHorseForPlayerHash, player);
	result.owned = GET_OWNED_MOUNT(player);
	const struct { Ped horse; const char* source; } candidates[] = {
		{ result.mount, "current_mount" }, { result.led, "led_horse" },
		{ result.active, "active_horse" }, { result.saddle, "saddle_horse" },
		{ result.owned, "owned_mount" }
	};
	for (const auto& candidate : candidates) {
		if (!validHorseNeedHorse(candidate.horse)) continue;
		result.selected = candidate.horse;
		result.source = candidate.source;
		break;
	}
	return result;
}

static float horseNeedsDistanceSquared(Vector3 a, Vector3 b) {
	const float dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
	return dx * dx + dy * dy + dz * dz;
}

// Lifecycle, rejection, and heartbeat lines are always retained. DevelopmentTrace
// adds only high-cadence restoration detail; a failed release run must never be
// indistinguishable from a module that did not execute.
static void horseNeedsLog(GtLogLevel level, const std::string& message) {
	if (level == GT_TRACE && !g_horseNeedsTrace) return;
	gtLog("horse-needs", level, message);
}

static void loadHorseNeedSources() {
	g_horseNeedSources.clear();
	std::ifstream input(g_moduleDir + "\\horse_need_sources.csv");
	std::string line;
	while (std::getline(input, line)) {
		if (line.empty() || line[0] == '#') continue;
		std::stringstream row(line);
		std::string kind, model, scenario, radiusText;
		if (!std::getline(row, kind, ',') || !std::getline(row, model, ',') ||
			!std::getline(row, scenario, ',') || !std::getline(row, radiusText)) continue;
		if (kind == "kind") continue;
		HorseNeedSource source;
		source.action = kind == "water" ? HorseNeedAction::Drink :
			(kind == "hay" ? HorseNeedAction::Eat : HorseNeedAction::None);
		source.model = joaat(model.c_str());
		source.scenario = joaat(scenario.c_str());
		source.radius = (float)atof(radiusText.c_str());
		if (source.action != HorseNeedAction::None && source.model &&
			source.scenario && source.radius >= 1.0f)
			g_horseNeedSources.push_back(source);
	}
	g_horseNeedSourcesLoaded = true;
	horseNeedsLog(GT_INFO, "sources loaded=" +
		std::to_string(g_horseNeedSources.size()) +
		" source-registry-reload=restart-required");
}

static void refreshHorseNeedsConfig(DWORD now) {
	if (g_horseNeedsNextConfigRead && now < g_horseNeedsNextConfigRead) return;
	g_horseNeedsNextConfigRead = now + 2000;
	g_horseNeedsEnabled = GetPrivateProfileIntA("HorseNeeds", "Enabled", 1,
		g_iniPath.c_str()) != 0;
	g_horseNeedsTrace = developmentModeActive() &&
		GetPrivateProfileIntA("HorseNeeds", "DevelopmentTrace", 0,
			g_iniPath.c_str()) != 0;
	g_horseNeedsIdleMs = (std::max)(0, (std::min)(120000,
		(int)GetPrivateProfileIntA("HorseNeeds", "IdleSeconds", 15,
			g_iniPath.c_str()) * 1000));
	g_horseNeedsApproachTimeoutMs = (std::max)(5000, (std::min)(60000,
		(int)GetPrivateProfileIntA("HorseNeeds", "ApproachTimeoutSeconds", 20,
			g_iniPath.c_str()) * 1000));
	g_horseNeedsMinimumUseMs = (std::max)(2000, (std::min)(15000,
		(int)GetPrivateProfileIntA("HorseNeeds", "MinimumUseSeconds", 4,
			g_iniPath.c_str()) * 1000));
	g_horseNeedsMaximumUseMs = (std::max)(g_horseNeedsMinimumUseMs + 1000,
		(std::min)(60000, (int)GetPrivateProfileIntA("HorseNeeds",
			"MaximumUseSeconds", 24, g_iniPath.c_str()) * 1000));
	g_horseNeedsCooldownMs = (std::max)(0, (std::min)(3600000,
		(int)GetPrivateProfileIntA("HorseNeeds", "CooldownSeconds", 300,
			g_iniPath.c_str()) * 1000));
	g_horseNeedsRestoreIntervalMs = (std::max)(250, (std::min)(5000,
		(int)GetPrivateProfileIntA("HorseNeeds", "RestoreIntervalMs", 1000,
			g_iniPath.c_str())));
	g_horseNeedsRestorePoints = (std::max)(1, (std::min)(25,
		(int)GetPrivateProfileIntA("HorseNeeds", "RestorePointsPerTick", 5,
			g_iniPath.c_str())));
	g_horseNeedsTriggerCore = (std::max)(1, (std::min)(99,
		(int)GetPrivateProfileIntA("HorseNeeds", "TriggerBelowCorePercent", 75,
			g_iniPath.c_str())));
	g_horseNeedsMinimumPlayerDistance = (std::max)(0.0f, (std::min)(20.0f,
		readF("HorseNeeds", "MinimumPlayerDistance", 6.0f)));
	g_horseNeedsMaximumPlayerDistance = (std::max)(20.0f, (std::min)(200.0f,
		readF("HorseNeeds", "MaximumPlayerDistance", 80.0f)));
	const std::string summary = std::string("enabled=") +
		(g_horseNeedsEnabled ? "1" : "0") +
		" idle-ms=" + std::to_string(g_horseNeedsIdleMs) +
		" trigger-core=" + std::to_string(g_horseNeedsTriggerCore) +
		" player-distance=" + std::to_string(g_horseNeedsMinimumPlayerDistance) +
		".." + std::to_string(g_horseNeedsMaximumPlayerDistance) +
		" cooldown-ms=" + std::to_string(g_horseNeedsCooldownMs) +
		" trace=" + (g_horseNeedsTrace ? "1" : "0");
	if (summary != g_horseNeedsLastConfigSummary) {
		g_horseNeedsLastConfigSummary = summary;
		horseNeedsLog(GT_INFO, "config-applied hot-reload<=2s " + summary);
	}
}

static bool horseNeedsWhistlePressed() {
	static const Hash kWhistle = 0x24978A28; // INPUT_WHISTLE
	static const Hash kWhistleHorseback = 0xE7EB9185; // INPUT_WHISTLE_HORSEBACK
	return PAD::IS_CONTROL_JUST_PRESSED(0, kWhistle) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, kWhistle) ||
		PAD::IS_CONTROL_JUST_PRESSED(0, kWhistleHorseback) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, kWhistleHorseback);
}

static bool horseNeedsDangerOrInterruption(Ped playerPed, Ped horse, bool locked) {
	if (locked || !playerPed || !horse || !ENTITY::DOES_ENTITY_EXIST(horse) ||
		PED::IS_PED_DEAD_OR_DYING(horse, TRUE) || PED::IS_PED_RAGDOLL(horse) ||
		PED::IS_PED_FALLING(horse) || PED::IS_PED_SWIMMING(horse) ||
		PED::IS_PED_FLEEING(horse) || PED::IS_PED_IN_COMBAT(horse, 0) ||
		PED::IS_PED_IN_COMBAT(playerPed, 0) || PED::IS_PED_ON_MOUNT(playerPed) ||
		GET_MOUNT(playerPed) == horse || ENTITY::IS_ENTITY_ATTACHED(horse) ||
		invoke<BOOL>(kIsPedLeadingHorseHash, playerPed) ||
		horseNeedsWhistlePressed()) return true;
	// Walking back to the horse is an implicit request to retake control. Clear
	// our scenario before it can fight the mount/lead interaction prompt.
	const Vector3 playerPosition = ENTITY::GET_ENTITY_COORDS(playerPed, TRUE, FALSE);
	const Vector3 horsePosition = ENTITY::GET_ENTITY_COORDS(horse, TRUE, FALSE);
	if (horseNeedsDistanceSquared(playerPosition, horsePosition) <
		g_horseNeedsMinimumPlayerDistance * g_horseNeedsMinimumPlayerDistance)
		return true;
	const int health = ENTITY::GET_ENTITY_HEALTH(horse);
	const int maximum = ENTITY::GET_ENTITY_MAX_HEALTH(horse, TRUE);
	return maximum > 0 && health * 100 < maximum * 60;
}

static void stopHorseNeedAction(DWORD now, bool applyCooldown, const char* reason) {
	HorseNeedRuntime& state = g_horseNeedRuntime;
	if (state.action != HorseNeedAction::None && state.horse &&
		ENTITY::DOES_ENTITY_EXIST(state.horse)) {
		if (state.action == HorseNeedAction::Drink) {
			TASK::STOP_ANIM_TASK(state.horse, kHorseDrinkEnterDict,
				kHorseDrinkEnterClip, -2.0f);
			TASK::STOP_ANIM_TASK(state.horse, kHorseDrinkBaseDict,
				kHorseDrinkBaseClip, -2.0f);
			TASK::CLEAR_PED_TASKS(state.horse, true, false);
		}
		else {
			// A whistle or player approach can replace our scenario before this update.
			// Clear only our exact active scenario, never a newer Rockstar task.
			const bool usingScenario = PED::IS_PED_USING_ANY_SCENARIO(state.horse);
			const Hash activeScenario = usingScenario ?
				TASK::_GET_SCENARIO_POINT_TYPE_PED_IS_USING(state.horse) : 0;
			if (!usingScenario || activeScenario == state.scenario)
				TASK::CLEAR_PED_TASKS(state.horse, true, false);
		}
	}
	if (state.ownsScenarioPoint && state.scenarioPoint) {
		invoke<Void>(kHorseNeedsDeleteScenarioPointHash, state.scenarioPoint);
		state.scenarioPoint = 0;
		state.ownsScenarioPoint = false;
	}
	horseNeedsLog(GT_INFO, std::string("stop reason=") + reason);
	const Ped horse = state.horse;
	const DWORD cooldown = applyCooldown ? now + g_horseNeedsCooldownMs :
		state.cooldownUntil;
	state = {};
	state.horse = horse;
	state.cooldownUntil = cooldown;
	state.idleSince = now;
}

static Object closestHorseNeedObject(Vector3 horsePosition,
	const HorseNeedSource& source) {
	Object object = OBJECT::GET_CLOSEST_OBJECT_OF_TYPE(horsePosition.x,
		horsePosition.y, horsePosition.z, source.radius, source.model,
		FALSE, FALSE, FALSE);
	if (!object || !ENTITY::DOES_ENTITY_EXIST(object) ||
		ENTITY::GET_ENTITY_MODEL(object) != source.model ||
		!ENTITY::IS_ENTITY_VISIBLE(object) || ENTITY::IS_ENTITY_ATTACHED(object) ||
		ENTITY_SPEED(object) > 0.02f) return 0;
	return object;
}

static void clearHorseDrinkMapMarkers() {
	for (HorseDrinkMapMarker& marker : g_horseDrinkMapMarkers) {
		if (marker.blip && MAP::DOES_BLIP_EXIST(marker.blip))
			MAP::REMOVE_BLIP(&marker.blip);
	}
	g_horseDrinkMapMarkers.clear();
}

static void ensureHorseDrinkMapTexture() {
	const char* dictionary = "INVENTORY_ITEMS_MP";
	const bool loaded = invoke<BOOL>(0x54D6900929CCF162, dictionary) != FALSE;
	if (!loaded) invoke<Void>(0xC1BA29DF5631B0F8, dictionary, FALSE);
	if (g_horseDrinkTextureProbeLogged) return;
	g_horseDrinkTextureProbeLogged = true;
	const bool exists = invoke<BOOL>(0x7332461FC59EB7EC, dictionary) != FALSE;
	horseNeedsLog(GT_INFO, std::string("map-texture INVENTORY_ITEMS_MP exists=") +
		(exists ? "1" : "0") + " loaded-before-request=" +
		(loaded ? "1" : "0"));
}

static HorseDrinkMapMarker* horseDrinkMarkerFor(Object object) {
	for (HorseDrinkMapMarker& marker : g_horseDrinkMapMarkers)
		if (marker.object == object) return &marker;
	return nullptr;
}

static bool playerIsLeadingOwnedHorse(Ped playerPed, Ped ownedHorse) {
	if (!playerPed || !ownedHorse ||
		!invoke<BOOL>(kIsPedLeadingHorseHash, playerPed)) return false;
	return invoke<Ped>(kGetLedHorseFromPedHash, playerPed) == ownedHorse;
}

// While the player is actively leading the owned horse, scan only streamed,
// validated water-source models within 100 m. The scan runs at 2 Hz, not per
// frame, and every blip is removed immediately when leading stops.
static void updateHorseDrinkMapMarkers(Ped playerPed, Ped ownedHorse, DWORD now,
	bool locked) {
	if (locked || !g_horseNeedsEnabled ||
		!playerIsLeadingOwnedHorse(playerPed, ownedHorse)) {
		if (!g_horseDrinkMapMarkers.empty()) clearHorseDrinkMapMarkers();
		return;
	}
	if (now < g_horseDrinkNextMapScanAt) return;
	g_horseDrinkNextMapScanAt = now + 500;
	if (!g_horseNeedSourcesLoaded) loadHorseNeedSources();
	ensureHorseDrinkMapTexture();
	const Vector3 playerPosition = ENTITY::GET_ENTITY_COORDS(playerPed, TRUE, FALSE);
	static Object objects[4096];
	const int objectCount = worldGetAllObjects(objects, (int)_countof(objects));
	for (int objectIndex = 0; objectIndex < objectCount; ++objectIndex) {
		const Object object = objects[objectIndex];
		if (!object || !ENTITY::DOES_ENTITY_EXIST(object) ||
			!ENTITY::IS_ENTITY_VISIBLE(object) || ENTITY::IS_ENTITY_ATTACHED(object) ||
			ENTITY_SPEED(object) > 0.02f) continue;
		const Hash model = ENTITY::GET_ENTITY_MODEL(object);
		bool registeredWater = false;
		for (const HorseNeedSource& source : g_horseNeedSources) {
			if (source.action == HorseNeedAction::Drink && source.model == model) {
				registeredWater = true;
				break;
			}
		}
		if (!registeredWater) continue;
		const Vector3 position = ENTITY::GET_ENTITY_COORDS(object, TRUE, FALSE);
		if (horseNeedsDistanceSquared(position, playerPosition) > 10000.0f) continue;
		HorseDrinkMapMarker* marker = horseDrinkMarkerFor(object);
		if (!marker) {
			g_horseDrinkMapMarkers.push_back({ object, 0, now });
			marker = &g_horseDrinkMapMarkers.back();
		}
		marker->seenAt = now;
		if (!marker->blip || !MAP::DOES_BLIP_EXIST(marker->blip)) {
			marker->blip = ADD_COORD_BLIP((Hash)-1337945352, position);
			if (marker->blip) {
				SET_BLIP_ICON(marker->blip, joaat("LEX_BLIP_HORSE_DRINK"));
				SET_BLIP_NAME(marker->blip, "Horse Drinking Water");
			}
		}
	}
	for (size_t index = 0; index < g_horseDrinkMapMarkers.size();) {
		HorseDrinkMapMarker& marker = g_horseDrinkMapMarkers[index];
		if (marker.seenAt == now) { ++index; continue; }
		if (marker.blip && MAP::DOES_BLIP_EXIST(marker.blip))
			MAP::REMOVE_BLIP(&marker.blip);
		g_horseDrinkMapMarkers.erase(g_horseDrinkMapMarkers.begin() + index);
	}
}

static bool validHayScenarioPosition(Ped horse, Object hay, Vector3& out,
	float& heading) {
	const Vector3 hayPosition = ENTITY::GET_ENTITY_COORDS(hay, TRUE, FALSE);
	const Vector3 horsePosition = ENTITY::GET_ENTITY_COORDS(horse, TRUE, FALSE);
	float bestDistance = 1e30f;
	for (int i = 0; i < 8; ++i) {
		const float angle = (float)i * 0.78539816339f;
		Vector3 candidate = { hayPosition.x + sinf(angle) * 1.55f,
			hayPosition.y + cosf(angle) * 1.55f, hayPosition.z + 1.0f };
		float ground = 0.0f;
		Vector3 normal = {};
		if (!GROUND_Z_NORMAL(candidate, &ground, &normal) || normal.z < 0.92f)
			continue;
		candidate.z = ground;
		// Rockstar uses flags 12 when asking GET_SAFE_COORD_FOR_PED for outdoor
		// placement. Requiring the navmesh result to remain very close rejects
		// blocked/stacked props instead of letting the task warp to a remote point.
		Vector3 safe = {};
		if (!PATHFIND::GET_SAFE_COORD_FOR_PED(candidate.x, candidate.y,
			candidate.z, FALSE, &safe, 12) ||
			horseNeedsDistanceSquared(candidate, safe) > 0.1225f)
			continue;
		float safeGround = 0.0f;
		Vector3 safeNormal = {};
		if (!GROUND_Z_NORMAL(safe, &safeGround, &safeNormal) || safeNormal.z < 0.92f)
			continue;
		candidate = safe;
		candidate.z = safeGround;
		float water = 0.0f;
		if (WATER_HEIGHT(candidate, &water) && water > safeGround + 0.10f) continue;
		const float distance = horseNeedsDistanceSquared(candidate, horsePosition);
		if (distance >= bestDistance) continue;
		bestDistance = distance;
		out = candidate;
		heading = atan2f(hayPosition.x - candidate.x,
			hayPosition.y - candidate.y) * 57.2957795131f;
	}
	return bestDistance < 1e29f &&
		ENTITY::HAS_ENTITY_CLEAR_LOS_TO_ENTITY(horse, hay, 17);
}

static bool validHorseDrinkPosition(Ped horse, Object object, Vector3& out,
	float& heading, const char*& sideName) {
	Vector3 minimum = {}, maximum = {};
	MISC::GET_MODEL_DIMENSIONS(ENTITY::GET_ENTITY_MODEL(object), &minimum, &maximum);
	const float halfX = (std::max)(0.25f, (maximum.x - minimum.x) * 0.5f);
	const float halfY = (std::max)(0.25f, (maximum.y - minimum.y) * 0.5f);
	// A horse drinks from the long side of a trough: offset along the model's
	// shorter horizontal axis. Both sides are tested and the nearest safe one is
	// selected. Barrels are approximately symmetric and use the same bounded test.
	const bool useX = halfX <= halfY;
	const float clearance = (useX ? halfX : halfY) + 0.95f;
	const float localOffsets[2] = { -clearance, clearance };
	const char* namesX[2] = { "local-x-negative", "local-x-positive" };
	const char* namesY[2] = { "local-y-negative", "local-y-positive" };
	const Vector3 objectPosition = ENTITY::GET_ENTITY_COORDS(object, TRUE, FALSE);
	const Vector3 horsePosition = ENTITY::GET_ENTITY_COORDS(horse, TRUE, FALSE);
	float bestDistance = 1e30f;
	for (int i = 0; i < 2; ++i) {
		Vector3 candidate = ENTITY::GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(object,
			useX ? localOffsets[i] : 0.0f,
			useX ? 0.0f : localOffsets[i], 1.0f);
		float ground = 0.0f;
		Vector3 normal = {};
		if (!GROUND_Z_NORMAL(candidate, &ground, &normal) || normal.z < 0.90f)
			continue;
		candidate.z = ground;
		Vector3 safe = {};
		if (!PATHFIND::GET_SAFE_COORD_FOR_PED(candidate.x, candidate.y, candidate.z,
			FALSE, &safe, 12) ||
			horseNeedsDistanceSquared(candidate, safe) > 0.25f)
			continue;
		float safeGround = 0.0f;
		Vector3 safeNormal = {};
		if (!GROUND_Z_NORMAL(safe, &safeGround, &safeNormal) || safeNormal.z < 0.90f)
			continue;
		safe.z = safeGround;
		float water = 0.0f;
		if (WATER_HEIGHT(safe, &water) && water > safeGround + 0.10f) continue;
		const float distance = horseNeedsDistanceSquared(safe, horsePosition);
		if (distance >= bestDistance) continue;
		bestDistance = distance;
		out = safe;
		heading = atan2f(objectPosition.x - safe.x,
			objectPosition.y - safe.y) * 57.2957795131f;
		sideName = useX ? namesX[i] : namesY[i];
	}
	return bestDistance < 1e29f &&
		ENTITY::HAS_ENTITY_CLEAR_LOS_TO_ENTITY(horse, object, 17);
}

static bool beginHorseNeedAction(Ped horse, const HorseNeedSource& source,
	Object object, DWORD now) {
	const Vector3 sourcePosition = ENTITY::GET_ENTITY_COORDS(object, TRUE, FALSE);
	HorseNeedRuntime& state = g_horseNeedRuntime;
	if (source.action == HorseNeedAction::Drink) {
		Vector3 target = {};
		float heading = 0.0f;
		const char* side = "none";
		if (!validHorseDrinkPosition(horse, object, target, heading, side)) {
			g_horseNeedsLastStartResult = "drink_no_safe_approach";
			return false;
		}
		invoke<Void>(0xD76B57B44F1E6F8BULL, horse, target.x, target.y,
			target.z, 1.0f, g_horseNeedsApproachTimeoutMs, heading, 0.55f, 0);
		state.drinkStage = HorseDrinkStage::Approaching;
		state.drinkTarget = target;
		state.drinkHeading = heading;
		state.drinkStageAt = now;
		state.drinkEnterIssued = false;
		horseNeedsLog(GT_INFO, std::string("drink approach issued side=") + side +
			" target=" + std::to_string(target.x) + "," +
			std::to_string(target.y) + "," + std::to_string(target.z) +
			" heading=" + std::to_string(heading));
	}
	else {
		Vector3 position = {};
		float heading = 0.0f;
		if (!validHayScenarioPosition(horse, object, position, heading)) return false;
		TASK::TASK_START_SCENARIO_AT_POSITION(horse, source.scenario,
			position.x, position.y, position.z, heading, -1, FALSE, FALSE,
			nullptr, -1.0f, FALSE);
	}
	state.action = source.action;
	state.source = object;
	state.scenario = source.scenario;
	state.issuedAt = now;
	state.enteredAt = 0;
	state.lastRestoreAt = 0;
	g_horseNeedsLastStartResult = "issued";
	horseNeedsLog(GT_INFO, std::string("action-issued call-only action=") +
		(source.action == HorseNeedAction::Drink ? "drink" : "eat") +
		" scenario=" + std::to_string(source.scenario) +
		" point=" + std::to_string(state.scenarioPoint) +
		" owns-point=" + (state.ownsScenarioPoint ? "1" : "0") +
		" model=" + std::to_string(source.model));
	return true;
}

static bool tryStartHorseNeed(Ped horse, DWORD now) {
	if (!g_horseNeedSourcesLoaded) loadHorseNeedSources();
	if (g_horseNeedSources.empty()) {
		g_horseNeedsLastStartResult = "no_configured_sources";
		return false;
	}
	const int hunger = GET_CORE(horse, 0);
	const int thirst = GET_CORE(horse, 1);
	const bool needsFood = hunger <= g_horseNeedsTriggerCore;
	const bool needsWater = thirst <= g_horseNeedsTriggerCore;
	if (!needsFood && !needsWater) {
		g_horseNeedsLastStartResult = "cores_above_trigger";
		return false;
	}
	const Vector3 position = ENTITY::GET_ENTITY_COORDS(horse, TRUE, FALSE);
	// Prefer the greater need. If no valid source exists for it, try the other.
	for (int pass = 0; pass < 2; ++pass) {
		const HorseNeedAction wanted = ((thirst <= hunger) == (pass == 0)) ?
			HorseNeedAction::Drink : HorseNeedAction::Eat;
		if ((wanted == HorseNeedAction::Drink && !needsWater) ||
			(wanted == HorseNeedAction::Eat && !needsFood)) continue;
		for (const HorseNeedSource& source : g_horseNeedSources) {
			if (source.action != wanted) continue;
			const Object object = closestHorseNeedObject(position, source);
			if (!object) continue;
			g_horseNeedsLastStartResult = "source_found_task_not_issued";
			if (beginHorseNeedAction(horse, source, object, now)) return true;
		}
	}
	if (g_horseNeedsLastStartResult == "not_attempted" ||
		g_horseNeedsLastStartResult == "issued")
		g_horseNeedsLastStartResult = "no_streamed_source_in_range";
	return false;
}

static float horseNeedsHeadingDelta(float a, float b) {
	float delta = fmodf(a - b, 360.0f);
	if (delta > 180.0f) delta -= 360.0f;
	if (delta < -180.0f) delta += 360.0f;
	return fabsf(delta);
}

static bool horseDrinkAnimationPlaying(Ped horse, const char*& stateName) {
	if (ENTITY::IS_ENTITY_PLAYING_ANIM(horse, kHorseDrinkBaseDict,
		kHorseDrinkBaseClip, 3)) {
		stateName = "base";
		return true;
	}
	if (ENTITY::IS_ENTITY_PLAYING_ANIM(horse, kHorseDrinkEnterDict,
		kHorseDrinkEnterClip, 3)) {
		stateName = "enter";
		return true;
	}
	stateName = "none";
	return false;
}

static bool updateHorseDrinkAction(Ped horse, DWORD now) {
	HorseNeedRuntime& state = g_horseNeedRuntime;
	const char* animation = "none";
	const bool playing = horseDrinkAnimationPlaying(horse, animation);
	if (playing && !state.enteredAt) {
		state.enteredAt = now;
		state.lastRestoreAt = now;
		state.drinkStage = HorseDrinkStage::Drinking;
		state.drinkStageAt = now;
		horseNeedsLog(GT_INFO, std::string("drink-animation-confirmed state=") +
			animation + " visual-alignment=pending");
	}
	if (state.drinkStage == HorseDrinkStage::Approaching) {
		const Vector3 position = ENTITY::GET_ENTITY_COORDS(horse, TRUE, FALSE);
		const float distanceSq = horseNeedsDistanceSquared(position, state.drinkTarget);
		if (distanceSq <= 0.7225f) {
			invoke<Void>(0x93B93A37987F1F3DULL, horse, state.drinkHeading, 2500);
			state.drinkStage = HorseDrinkStage::Aligning;
			state.drinkStageAt = now;
			horseNeedsLog(GT_INFO, "drink approach confirmed; heading task issued");
		}
		else if (now - state.issuedAt > (DWORD)g_horseNeedsApproachTimeoutMs) {
			stopHorseNeedAction(now, false, "drink_approach_timeout");
			return false;
		}
		return true;
	}
	if (state.drinkStage == HorseDrinkStage::Aligning) {
		const float actual = ENTITY::GET_ENTITY_HEADING(horse);
		const float delta = horseNeedsHeadingDelta(actual, state.drinkHeading);
		if (delta <= 12.0f) {
			TASK::CLEAR_PED_TASKS(horse, true, false);
			STREAMING::REQUEST_ANIM_DICT(kHorseDrinkEnterDict);
			STREAMING::REQUEST_ANIM_DICT(kHorseDrinkBaseDict);
			state.drinkStage = HorseDrinkStage::Entering;
			state.drinkStageAt = now;
			horseNeedsLog(GT_INFO, "drink heading confirmed delta=" +
				std::to_string(delta));
		}
		else if (now - state.drinkStageAt > 2500) {
			stopHorseNeedAction(now, false, "drink_heading_timeout");
			return false;
		}
		return true;
	}
	if (state.drinkStage == HorseDrinkStage::Entering) {
		if (!STREAMING::HAS_ANIM_DICT_LOADED(kHorseDrinkEnterDict))
			STREAMING::REQUEST_ANIM_DICT(kHorseDrinkEnterDict);
		if (!STREAMING::HAS_ANIM_DICT_LOADED(kHorseDrinkBaseDict))
			STREAMING::REQUEST_ANIM_DICT(kHorseDrinkBaseDict);
		if (!state.drinkEnterIssued &&
			STREAMING::HAS_ANIM_DICT_LOADED(kHorseDrinkEnterDict) &&
			STREAMING::HAS_ANIM_DICT_LOADED(kHorseDrinkBaseDict)) {
			TASK::TASK_PLAY_ANIM(horse, kHorseDrinkEnterDict, kHorseDrinkEnterClip,
				8.0f, -8.0f, 10000, 2, 0.0f, FALSE, 0, FALSE, "", FALSE);
			state.drinkEnterIssued = true;
			state.drinkStageAt = now;
			horseNeedsLog(GT_INFO, "drink ENTER task issued; awaiting live readback");
		}
		if (state.drinkEnterIssued && !playing && now - state.drinkStageAt > 1500) {
			stopHorseNeedAction(now, false, "drink_animation_not_observed");
			return false;
		}
		return true;
	}
	if (state.drinkStage != HorseDrinkStage::Drinking || !state.enteredAt)
		return true;
	if (!playing) {
		stopHorseNeedAction(now, true, "drink_animation_exited");
		return false;
	}
	const DWORD usedFor = now - state.enteredAt;
	if (usedFor >= (DWORD)g_horseNeedsMinimumUseMs &&
		now - state.lastRestoreAt >= (DWORD)g_horseNeedsRestoreIntervalMs) {
		const int before = GET_CORE(horse, 1);
		const int after = (std::min)(100, before + g_horseNeedsRestorePoints);
		if (after > before) SET_HORSE_CORE(horse, 1, after);
		state.lastRestoreAt = now;
		horseNeedsLog(GT_TRACE, "restore core=1 from=" + std::to_string(before) +
			" to=" + std::to_string(after));
		if (after >= 100) {
			stopHorseNeedAction(now, true, "core_full");
			return false;
		}
	}
	if (usedFor >= (DWORD)g_horseNeedsMaximumUseMs) {
		stopHorseNeedAction(now, true, "maximum_use_time");
		return false;
	}
	return true;
}

static void horseNeedsHeartbeat(const HorseNeedResolvedHorse& resolved,
	DWORD now, const char* gate) {
	if (now < g_horseNeedsNextHeartbeatAt) return;
	g_horseNeedsNextHeartbeatAt = now + 5000;
	const Ped horse = resolved.selected;
	const int hunger = horse && ENTITY::DOES_ENTITY_EXIST(horse) ?
		GET_CORE(horse, 0) : -1;
	const int thirst = horse && ENTITY::DOES_ENTITY_EXIST(horse) ?
		GET_CORE(horse, 1) : -1;
	const bool usingScenario = horse && ENTITY::DOES_ENTITY_EXIST(horse) &&
		PED::IS_PED_USING_ANY_SCENARIO(horse);
	const Hash activeScenario = usingScenario ?
		TASK::_GET_SCENARIO_POINT_TYPE_PED_IS_USING(horse) : 0;
	const bool pointExists = g_horseNeedRuntime.scenarioPoint &&
		TASK::_DOES_SCENARIO_POINT_EXIST(g_horseNeedRuntime.scenarioPoint);
	const Ped pointUser = pointExists ?
		TASK::_GET_PED_USING_SCENARIO_POINT(g_horseNeedRuntime.scenarioPoint) : 0;
	const bool modScenarioConfirmed = g_horseNeedRuntime.action !=
		HorseNeedAction::None && activeScenario == g_horseNeedRuntime.scenario;
	horseNeedsLog(GT_INFO, std::string("heartbeat gate=") + gate +
		" horse=" + std::to_string(horse) +
		" horse-source=" + resolved.source +
		" candidates[mount,led,active,saddle,owned]=" +
		std::to_string(resolved.mount) + "," + std::to_string(resolved.led) +
		"," + std::to_string(resolved.active) + "," +
		std::to_string(resolved.saddle) + "," + std::to_string(resolved.owned) +
		" hunger=" + std::to_string(hunger) +
		" thirst=" + std::to_string(thirst) +
		" action=" + std::to_string((int)g_horseNeedRuntime.action) +
		" using-scenario=" + (usingScenario ? "1" : "0") +
		" active-scenario=" + std::to_string(activeScenario) +
		" expected-scenario=" + std::to_string(g_horseNeedRuntime.scenario) +
		" mod-scenario-confirmed=" + (modScenarioConfirmed ? "1" : "0") +
		" point=" + std::to_string(g_horseNeedRuntime.scenarioPoint) +
		" point-user=" + std::to_string(pointUser) +
		" drink-stage=" + std::to_string((int)g_horseNeedRuntime.drinkStage) +
		" last-start=" + g_horseNeedsLastStartResult);
}

static void updateAutonomousHorseNeeds(Player player, Ped playerPed, DWORD now,
	bool locked) {
	refreshHorseNeedsConfig(now);
	HorseNeedRuntime& state = g_horseNeedRuntime;
	const HorseNeedResolvedHorse resolved = resolveHorseNeedHorse(player, playerPed);
	const Ped horse = resolved.selected;
	updateHorseDrinkMapMarkers(playerPed, horse, now, locked);
	if (horse != state.horse) {
		if (state.action != HorseNeedAction::None) stopHorseNeedAction(now, false,
			"owned_horse_changed");
		state = {};
		state.horse = horse;
		state.idleSince = now;
	}
	if (!g_horseNeedsEnabled) {
		if (state.action != HorseNeedAction::None)
			stopHorseNeedAction(now, false, "disabled");
		horseNeedsHeartbeat(resolved, now, "disabled");
		return;
	}
	if (!horse || !ENTITY::DOES_ENTITY_EXIST(horse)) {
		horseNeedsHeartbeat(resolved, now, "no_owned_horse");
		return;
	}

	if (state.action != HorseNeedAction::None) {
		horseNeedsHeartbeat(resolved, now, state.enteredAt ? "using" : "approaching");
		if (horseNeedsDangerOrInterruption(playerPed, horse, locked)) {
			stopHorseNeedAction(now, state.enteredAt != 0, "interrupted");
			return;
		}
		if (!state.source || !ENTITY::DOES_ENTITY_EXIST(state.source)) {
			stopHorseNeedAction(now, false, "source_unloaded");
			return;
		}
		if (state.action == HorseNeedAction::Drink) {
			updateHorseDrinkAction(horse, now);
			return;
		}
		const Hash activeScenario = PED::IS_PED_USING_ANY_SCENARIO(horse) ?
			TASK::_GET_SCENARIO_POINT_TYPE_PED_IS_USING(horse) : 0;
		if (!state.enteredAt) {
			if (activeScenario == state.scenario) {
				state.enteredAt = now;
				state.lastRestoreAt = now;
				horseNeedsLog(GT_INFO,
					"mod-scenario-confirmed active-scenario=" +
					std::to_string(activeScenario) +
					" point=" + std::to_string(state.scenarioPoint) +
					" pose=authored-conditional visual-acceptance=pending");
			}
			else if (now - state.issuedAt > (DWORD)g_horseNeedsApproachTimeoutMs) {
				stopHorseNeedAction(now, false, "approach_timeout");
			}
			return;
		}
		if (activeScenario != state.scenario) {
			stopHorseNeedAction(now, true, "scenario_exited");
			return;
		}
		const DWORD usedFor = now - state.enteredAt;
		const int core = state.action == HorseNeedAction::Drink ? 1 : 0;
		if (usedFor >= (DWORD)g_horseNeedsMinimumUseMs &&
			now - state.lastRestoreAt >= (DWORD)g_horseNeedsRestoreIntervalMs) {
			const int before = GET_CORE(horse, core);
			const int after = (std::min)(100, before + g_horseNeedsRestorePoints);
			if (after > before) SET_HORSE_CORE(horse, core, after);
			state.lastRestoreAt = now;
			horseNeedsLog(GT_TRACE, "restore core=" + std::to_string(core) +
				" from=" + std::to_string(before) + " to=" + std::to_string(after));
			if (after >= 100) {
				stopHorseNeedAction(now, true, "core_full");
				return;
			}
		}
		if (usedFor >= (DWORD)g_horseNeedsMaximumUseMs)
			stopHorseNeedAction(now, true, "maximum_use_time");
		return;
	}

	if (locked || now < state.cooldownUntil ||
		horseNeedsDangerOrInterruption(playerPed, horse, locked) ||
		PED::IS_PED_USING_ANY_SCENARIO(horse) || ENTITY_SPEED(horse) > 0.12f)
	{
		state.idleSince = now;
		horseNeedsHeartbeat(resolved, now, "busy_or_interrupted");
		return;
	}
	const Vector3 horsePosition = ENTITY::GET_ENTITY_COORDS(horse, TRUE, FALSE);
	const Vector3 playerPosition = ENTITY::GET_ENTITY_COORDS(playerPed, TRUE, FALSE);
	const float playerDistanceSq = horseNeedsDistanceSquared(horsePosition,
		playerPosition);
	if (playerDistanceSq < g_horseNeedsMinimumPlayerDistance *
		g_horseNeedsMinimumPlayerDistance ||
		playerDistanceSq > g_horseNeedsMaximumPlayerDistance *
		g_horseNeedsMaximumPlayerDistance) {
		state.idleSince = now;
		horseNeedsHeartbeat(resolved, now, "player_distance");
		return;
	}
	if (!state.idleSince) state.idleSince = now;
	if (now - state.idleSince < (DWORD)g_horseNeedsIdleMs ||
		now < state.nextSourceScanAt) {
		horseNeedsHeartbeat(resolved, now, "idle_wait");
		return;
	}
	state.nextSourceScanAt = now + 2000;
	g_horseNeedsLastStartResult = "not_attempted";
	if (tryStartHorseNeed(horse, now)) state.idleSince = 0;
	horseNeedsHeartbeat(resolved, now, "source_scan");
}
