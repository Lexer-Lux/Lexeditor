// GitHub #89: authored water-pump drinking and reusable-canteen refill.
//
// This module never plays a loose animation. It derives alignment from the
// pump's Rockstar-authored PROP_HUMAN_PUMP_WATER scenario point, creates the
// dedicated WORLD_PLAYER_CHORES_PUMP_WATER point at that exact transform, and
// associates the actual pump prop so its handle participates in the scenario.

struct WaterPumpCanteenApi {
	bool (*owned)() = nullptr;
	int (*charges)() = nullptr;
	int (*capacity)() = nullptr;
	bool (*refillToCapacity)() = nullptr;
	int (*staminaCorePerDrink)() = nullptr;
};

static WaterPumpCanteenApi g_waterPumpCanteenApi;

// Integration calls this once after #88 is included. Keeping the dependency in
// five callbacks prevents either issue from reaching into the other's state.
static void configureWaterPumpCanteenApi(const WaterPumpCanteenApi& api) {
	g_waterPumpCanteenApi = api;
}

enum class WaterPumpAction { None, Drink, Refill };

struct WaterPumpRuntime {
	Object pump = 0;
	int sourcePoint = 0;
	int playerPoint = 0;
	WaterPumpAction action = WaterPumpAction::None;
	DWORD issuedAt = 0;
	DWORD enteredAt = 0;
	DWORD exitRequestedAt = 0;
	DWORD nextScanAt = 0;
	bool rewardApplied = false;
	bool blockInputsUntilRelease = false;
};

static WaterPumpRuntime g_waterPumpRuntime;
static Prompt g_waterPumpDrinkPrompt = 0;
static Prompt g_waterPumpRefillPrompt = 0;

// The map layer is sourced from Rockstar's scenario registry, not from nearby
// streamed props. GET_SCENARIO_POINTS_IN_AREA returns scenario-point handles;
// a bounded world-grid sweep filters those handles by the exact authored pump
// type and retains their coordinates. Repeating the sweep also picks up
// chapter/interior points that are registered after the first pass.
struct WaterPumpMapMarker {
	Vector3 position;
	Blip blip = 0;
};

static std::vector<WaterPumpMapMarker> g_waterPumpMapMarkers;
static Any g_waterPumpScenarioBuffer[8192] = {};
static int g_waterPumpMapScanCell = 0;
static DWORD g_waterPumpNextMapScanAt = 0;
static bool g_waterPumpTextureProbeLogged = false;

static constexpr uint64_t kGetScenarioPointsInAreaHash = 0x345EC3B7EBDE1CB5ULL;
static constexpr uint64_t kGetScenarioPointTypeHash = 0xA92450B5AE687AAFULL;
static constexpr int kWaterPumpGridWidth = 20;
static constexpr float kWaterPumpGridFirst = -7600.0f;
static constexpr float kWaterPumpGridStep = 800.0f;
static constexpr float kWaterPumpGridCenterZ = 200.0f;
static constexpr float kWaterPumpGridRadius = 1000.0f;
static constexpr int kWaterPumpScenarioCapacity =
	static_cast<int>(sizeof(g_waterPumpScenarioBuffer) /
		sizeof(g_waterPumpScenarioBuffer[0]));

static float waterPumpDistanceSquared(Vector3 a, Vector3 b);

static constexpr uint64_t kCreateScenarioPointHash = 0x94B745CE41DB58A1ULL;
static constexpr uint64_t kAssociateScenarioPropHash = 0x8360C47380B6F351ULL;
static constexpr uint64_t kDeleteScenarioPointHash = 0x81948DFE4F5A0283ULL;
static constexpr uint64_t kRequestScenarioExitHash = 0xFDECCA06E8B81346ULL;

static int waterPumpPromptBegin() { return invoke<int>(0x04F97DE45A519419); }
static void waterPumpPromptEnd(int prompt) { invoke<Void>(0xF7AA2696A22AD8B9, prompt); }
static void waterPumpPromptControl(int prompt, Hash control) {
	invoke<Any>(0xB5352B7494A08258, prompt, control);
}
static void waterPumpPromptText(int prompt, const char* text) {
	invoke<Void>(0x5DD02A8318420DD7, prompt,
		invoke<const char*>(0xFA925AC00EB830B9, 10, "LITERAL_STRING", text));
}
static void waterPumpPromptHold(int prompt) {
	invoke<Void>(0x74C7D7B72ED0D3CF, prompt, joaat("MEDIUM_TIMED_EVENT"));
}
static void waterPumpPromptVisible(int prompt, bool visible) {
	invoke<Void>(0x71215ACCFDE075EE, prompt, visible ? TRUE : FALSE);
	invoke<Void>(0x8A0FB4D03A630D21, prompt, visible ? TRUE : FALSE);
}
static void waterPumpPromptState(int prompt, bool visible, bool enabled) {
	invoke<Void>(0x71215ACCFDE075EE, prompt, visible ? TRUE : FALSE);
	invoke<Void>(0x8A0FB4D03A630D21, prompt, enabled ? TRUE : FALSE);
}
static bool waterPumpPromptDone(int prompt) {
	return invoke<BOOL>(0xE0F65F0640EF0617, prompt) != FALSE;
}
static void waterPumpPromptRestart(int prompt) {
	invoke<Void>(0xDC6C55DFA2C24EE5, prompt);
}

static void waterPumpLog(GtLogLevel level, const std::string& text) {
	gtLog("water-pumps", level, text);
}

static void ensureWaterPumpMapTexture() {
	const char* dictionary = "INVENTORY_ITEMS_MP";
	const bool loaded = invoke<BOOL>(0x54D6900929CCF162, dictionary) != FALSE;
	if (!loaded) invoke<Void>(0xC1BA29DF5631B0F8, dictionary, FALSE);
	if (g_waterPumpTextureProbeLogged) return;
	g_waterPumpTextureProbeLogged = true;
	const bool exists = invoke<BOOL>(0x7332461FC59EB7EC, dictionary) != FALSE;
	waterPumpLog(GT_INFO, std::string("map-texture INVENTORY_ITEMS_MP exists=") +
		(exists ? "1" : "0") + " loaded-before-request=" +
		(loaded ? "1" : "0"));
}

static bool waterPumpMapPositionKnown(Vector3 position) {
	for (const WaterPumpMapMarker& marker : g_waterPumpMapMarkers) {
		if (waterPumpDistanceSquared(marker.position, position) < 2.25f)
			return true;
	}
	return false;
}

static void refreshWaterPumpMapBlips() {
	ensureWaterPumpMapTexture();
	for (WaterPumpMapMarker& marker : g_waterPumpMapMarkers) {
		if (marker.blip && !MAP::DOES_BLIP_EXIST(marker.blip)) marker.blip = 0;
		if (marker.blip) continue;
		marker.blip = ADD_COORD_BLIP((Hash)-1337945352, marker.position);
		if (!marker.blip) continue;
		SET_BLIP_ICON(marker.blip, joaat("LEX_BLIP_WATER_PUMP"));
		SET_BLIP_NAME(marker.blip, "Water Pump");
	}
}

static void scanWaterPumpMapCell(DWORD now) {
	if (now < g_waterPumpNextMapScanAt) {
		refreshWaterPumpMapBlips();
		return;
	}
	g_waterPumpNextMapScanAt = now + 50;

	const int cell = g_waterPumpMapScanCell;
	const int column = cell % kWaterPumpGridWidth;
	const int row = cell / kWaterPumpGridWidth;
	const float x = kWaterPumpGridFirst + column * kWaterPumpGridStep;
	const float y = kWaterPumpGridFirst + row * kWaterPumpGridStep;
	const int reported = invoke<int>(kGetScenarioPointsInAreaHash,
		x, y, kWaterPumpGridCenterZ, kWaterPumpGridRadius,
		g_waterPumpScenarioBuffer, kWaterPumpScenarioCapacity);
	const int count = (std::max)(0,
		(std::min)(reported, kWaterPumpScenarioCapacity));
	const Hash pumpScenario = joaat("PROP_HUMAN_PUMP_WATER");
	int added = 0;
	for (int index = 0; index < count; ++index) {
		const int scenarioPoint =
			static_cast<int>(g_waterPumpScenarioBuffer[index]);
		if (!scenarioPoint ||
			!TASK::_DOES_SCENARIO_POINT_EXIST(scenarioPoint) ||
			invoke<Hash>(kGetScenarioPointTypeHash, scenarioPoint) != pumpScenario)
			continue;
		const Vector3 position =
			TASK::_GET_SCENARIO_POINT_COORDS(scenarioPoint, TRUE);
		if (position.x < -9000.0f || position.x > 9000.0f ||
			position.y < -9000.0f || position.y > 9000.0f ||
			waterPumpMapPositionKnown(position))
			continue;
		g_waterPumpMapMarkers.push_back({ position, 0 });
		++added;
	}
	if (reported >= kWaterPumpScenarioCapacity)
		waterPumpLog(GT_WARN, "map-scan saturated cell=" + std::to_string(cell));
	if (added)
		waterPumpLog(GT_INFO, "map-scan cell=" + std::to_string(cell) +
			" added=" + std::to_string(added) +
			" total=" + std::to_string(g_waterPumpMapMarkers.size()));

	g_waterPumpMapScanCell =
		(g_waterPumpMapScanCell + 1) %
		(kWaterPumpGridWidth * kWaterPumpGridWidth);
	refreshWaterPumpMapBlips();
}

static float waterPumpDistanceSquared(Vector3 a, Vector3 b) {
	const float x = a.x - b.x, y = a.y - b.y, z = a.z - b.z;
	return x * x + y * y + z * z;
}

static bool waterPumpApiReady() {
	return g_waterPumpCanteenApi.owned && g_waterPumpCanteenApi.charges &&
		g_waterPumpCanteenApi.capacity &&
		g_waterPumpCanteenApi.refillToCapacity &&
		g_waterPumpCanteenApi.staminaCorePerDrink;
}

static void ensureWaterPumpPrompts() {
	if (!g_waterPumpDrinkPrompt) {
		g_waterPumpDrinkPrompt = waterPumpPromptBegin();
		waterPumpPromptControl(g_waterPumpDrinkPrompt, joaat("INPUT_CONTEXT_X"));
		waterPumpPromptText(g_waterPumpDrinkPrompt, "Drink");
		waterPumpPromptHold(g_waterPumpDrinkPrompt);
		waterPumpPromptEnd(g_waterPumpDrinkPrompt);
		waterPumpPromptVisible(g_waterPumpDrinkPrompt, false);
	}
	if (!g_waterPumpRefillPrompt) {
		g_waterPumpRefillPrompt = waterPumpPromptBegin();
		waterPumpPromptControl(g_waterPumpRefillPrompt, joaat("INPUT_RELOAD"));
		waterPumpPromptText(g_waterPumpRefillPrompt, "Refill Canteen");
		waterPumpPromptHold(g_waterPumpRefillPrompt);
		waterPumpPromptEnd(g_waterPumpRefillPrompt);
		waterPumpPromptVisible(g_waterPumpRefillPrompt, false);
	}
}

static void hideWaterPumpPrompts() {
	if (g_waterPumpDrinkPrompt) waterPumpPromptVisible(g_waterPumpDrinkPrompt, false);
	if (g_waterPumpRefillPrompt) waterPumpPromptVisible(g_waterPumpRefillPrompt, false);
}

static void deleteWaterPumpPlayerPoint() {
	if (g_waterPumpRuntime.playerPoint) {
		invoke<Void>(kDeleteScenarioPointHash, g_waterPumpRuntime.playerPoint);
		g_waterPumpRuntime.playerPoint = 0;
	}
}

static void resetWaterPumpAction(const char* reason) {
	waterPumpLog(GT_INFO, std::string("action-end reason=") + reason +
		" reward=" + (g_waterPumpRuntime.rewardApplied ? "1" : "0"));
	deleteWaterPumpPlayerPoint();
	g_waterPumpRuntime.action = WaterPumpAction::None;
	g_waterPumpRuntime.issuedAt = 0;
	g_waterPumpRuntime.enteredAt = 0;
	g_waterPumpRuntime.exitRequestedAt = 0;
	g_waterPumpRuntime.rewardApplied = false;
	waterPumpPromptRestart(g_waterPumpDrinkPrompt);
	waterPumpPromptRestart(g_waterPumpRefillPrompt);
}

static bool waterPumpInterrupted(Ped ped, bool locked, bool mission) {
	return locked || mission || !ped || ENTITY::IS_ENTITY_DEAD(ped) ||
		PED::IS_PED_RAGDOLL(ped) || PED::IS_PED_IN_COMBAT(ped, 0) ||
		PED::IS_PED_ON_MOUNT(ped) || ENTITY::IS_ENTITY_IN_AIR(ped, 0) ||
		!g_waterPumpRuntime.pump ||
		!ENTITY::DOES_ENTITY_EXIST(g_waterPumpRuntime.pump);
}

static void requestWaterPumpExit(Ped ped, DWORD now, const char* reason) {
	if (g_waterPumpRuntime.exitRequestedAt) return;
	g_waterPumpRuntime.exitRequestedAt = now;
	waterPumpLog(GT_INFO, std::string("exit-request reason=") + reason);
	if (ped && PED::IS_PED_USING_ANY_SCENARIO(ped))
		invoke<Any>(kRequestScenarioExitHash, ped);
	else if (ped)
		TASK::CLEAR_PED_TASKS(ped, true, false);
}

static Object findEligibleWaterPump(Ped ped, int& scenarioPoint) {
	scenarioPoint = 0;
	const Vector3 playerPosition = ENTITY::GET_ENTITY_COORDS(ped, TRUE, FALSE);
	const Hash pumpModel = joaat("p_waterpump01x");
	Object pump = OBJECT::GET_CLOSEST_OBJECT_OF_TYPE(playerPosition.x,
		playerPosition.y, playerPosition.z, 4.0f, pumpModel,
		FALSE, FALSE, FALSE);
	if (!pump || !ENTITY::DOES_ENTITY_EXIST(pump) ||
		ENTITY::GET_ENTITY_MODEL(pump) != pumpModel ||
		!ENTITY::IS_ENTITY_VISIBLE(pump)) return 0;
	const Vector3 pumpPosition = ENTITY::GET_ENTITY_COORDS(pump, TRUE, FALSE);
	if (waterPumpDistanceSquared(playerPosition, pumpPosition) > 12.25f ||
		!ENTITY::HAS_ENTITY_CLEAR_LOS_TO_ENTITY(ped, pump, 17)) return 0;

	// propscenarios.meta attaches this exact authored point to p_waterpump01x.
	// Reusing its transform is what makes the hands and moving handle align.
	const Hash ambientScenario = joaat("PROP_HUMAN_PUMP_WATER");
	const int point = TASK::_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE(
		pumpPosition.x, pumpPosition.y, pumpPosition.z, ambientScenario,
		3.0f, 0, FALSE);
	if (!point || !TASK::_DOES_SCENARIO_POINT_EXIST(point) ||
		!TASK::_IS_SCENARIO_POINT_ACTIVE(point)) return 0;
	const Vector3 pointPosition = TASK::_GET_SCENARIO_POINT_COORDS(point, TRUE);
	if (waterPumpDistanceSquared(pointPosition, pumpPosition) > 9.0f) return 0;
	const Ped user = TASK::_GET_PED_USING_SCENARIO_POINT(point);
	if (user && user != ped) return 0;
	scenarioPoint = point;
	return pump;
}

static bool beginWaterPumpAction(Ped ped, WaterPumpAction action, DWORD now) {
	if (!g_waterPumpRuntime.pump || !g_waterPumpRuntime.sourcePoint) return false;
	const Vector3 point = TASK::_GET_SCENARIO_POINT_COORDS(
		g_waterPumpRuntime.sourcePoint, TRUE);
	const float heading = TASK::_GET_SCENARIO_POINT_HEADING(
		g_waterPumpRuntime.sourcePoint, TRUE);
	const int playerPoint = invoke<int>(kCreateScenarioPointHash,
		joaat("WORLD_PLAYER_CHORES_PUMP_WATER"), point.x, point.y, point.z,
		heading, 0, -1.0f, FALSE);
	if (!playerPoint || !TASK::_DOES_SCENARIO_POINT_EXIST(playerPoint)) {
		waterPumpLog(GT_ERROR, "start-failed create-player-point");
		return false;
	}
	if (!invoke<BOOL>(kAssociateScenarioPropHash, playerPoint,
		g_waterPumpRuntime.pump, "p_waterpump01x_PH_L_HAND", TRUE)) {
		invoke<Void>(kDeleteScenarioPointHash, playerPoint);
		waterPumpLog(GT_ERROR, "start-failed associate-pump-prop");
		return false;
	}

	const char* conditional = action == WaterPumpAction::Drink
		? "PROP_HUMAN_PUMP_WATER_PLAYER"
		: "PROP_HUMAN_PUMP_WATER_BUCKET_PLAYER";
	TASK::_TASK_USE_SCENARIO_POINT(ped, playerPoint, conditional, -1,
		TRUE, FALSE, 0, FALSE, -1.0f, FALSE);
	g_waterPumpRuntime.playerPoint = playerPoint;
	g_waterPumpRuntime.action = action;
	g_waterPumpRuntime.issuedAt = now;
	g_waterPumpRuntime.enteredAt = 0;
	g_waterPumpRuntime.exitRequestedAt = 0;
	g_waterPumpRuntime.rewardApplied = false;
	g_waterPumpRuntime.blockInputsUntilRelease = true;
	hideWaterPumpPrompts();
	waterPumpLog(GT_INFO, std::string("action-start kind=") +
		(action == WaterPumpAction::Drink ? "drink" : "refill") +
		" source-point=" + std::to_string(g_waterPumpRuntime.sourcePoint) +
		" player-point=" + std::to_string(playerPoint));
	return true;
}

static bool waterPumpRewardEvent(Ped ped, WaterPumpAction action) {
	if (action == WaterPumpAction::Drink)
		return ENTITY::HAS_ANIM_EVENT_FIRED(ped,
			joaat("ENT_ANIM_PED_WATER_DRINK_PUMP")) != FALSE;
	return ENTITY::HAS_ANIM_EVENT_FIRED(ped,
		joaat("ENT_ANIM_WATER_BUCKET_FILL")) != FALSE ||
		ENTITY::HAS_ANIM_EVENT_FIRED(ped,
			joaat("ENT_ANIM_BUCKET_FILL_SPLASH")) != FALSE;
}

static void applyWaterPumpReward(Ped ped, int* managedStaminaCore) {
	if (g_waterPumpRuntime.rewardApplied || !waterPumpApiReady()) return;
	g_waterPumpRuntime.rewardApplied = true;
	if (g_waterPumpRuntime.action == WaterPumpAction::Drink) {
		const int before = GET_CORE(ped, 1);
		const int amount = (std::max)(0, (std::min)(100,
			g_waterPumpCanteenApi.staminaCorePerDrink()));
		const int after = (std::min)(100, before + amount);
		SET_CORE(ped, 1, after);
		if (managedStaminaCore) *managedStaminaCore = after;
		waterPumpLog(GT_INFO, "drink-reward before=" + std::to_string(before) +
			" amount=" + std::to_string(amount) +
			" after=" + std::to_string(after));
	} else {
		const bool refilled = g_waterPumpCanteenApi.refillToCapacity();
		waterPumpLog(GT_INFO, std::string("refill-reward changed=") +
			(refilled ? "1" : "0"));
	}
}

static void updateWaterPumps(Player player, Ped ped, DWORD now, bool locked,
	bool mission, int* managedStaminaCore) {
	scanWaterPumpMapCell(now);
	ensureWaterPumpPrompts();

	if (g_waterPumpRuntime.blockInputsUntilRelease) {
		const Hash controls[] = { joaat("INPUT_CONTEXT_X"),
			joaat("INPUT_RELOAD"), joaat("INPUT_DYNAMIC_SCENARIO") };
		bool stillDown = false;
		for (Hash control : controls) {
			stillDown = stillDown || PAD::IS_DISABLED_CONTROL_PRESSED(0, control) ||
				PAD::IS_CONTROL_PRESSED(0, control);
			PAD::DISABLE_CONTROL_ACTION(0, control, FALSE);
		}
		if (!stillDown) g_waterPumpRuntime.blockInputsUntilRelease = false;
	}

	if (g_waterPumpRuntime.action != WaterPumpAction::None) {
		hideWaterPumpPrompts();
		if (waterPumpInterrupted(ped, locked, mission))
			requestWaterPumpExit(ped, now, "interrupted");

		const bool usingOurScenario = ped && PED::IS_PED_USING_ANY_SCENARIO(ped) &&
			TASK::_GET_SCENARIO_POINT_PED_IS_USING(ped, FALSE) ==
			g_waterPumpRuntime.playerPoint;
		if (!g_waterPumpRuntime.enteredAt) {
			if (usingOurScenario) {
				g_waterPumpRuntime.enteredAt = now;
				waterPumpLog(GT_INFO, "authored-scenario-entered");
			} else if (now - g_waterPumpRuntime.issuedAt > 10000) {
				requestWaterPumpExit(ped, now, "approach-timeout");
			}
		} else if (!usingOurScenario && !g_waterPumpRuntime.exitRequestedAt) {
			requestWaterPumpExit(ped, now, "scenario-ended-before-event");
		}

		if (usingOurScenario && !g_waterPumpRuntime.exitRequestedAt &&
			waterPumpRewardEvent(ped, g_waterPumpRuntime.action)) {
			applyWaterPumpReward(ped, managedStaminaCore);
			requestWaterPumpExit(ped, now, "authored-water-event");
		}
		if (g_waterPumpRuntime.enteredAt &&
			!g_waterPumpRuntime.exitRequestedAt &&
			now - g_waterPumpRuntime.enteredAt > 20000)
			requestWaterPumpExit(ped, now, "water-event-timeout");

		if (g_waterPumpRuntime.exitRequestedAt) {
			if (!usingOurScenario)
				resetWaterPumpAction(g_waterPumpRuntime.rewardApplied
					? "authored-exit-complete" : "cancelled-no-reward");
			else if (now - g_waterPumpRuntime.exitRequestedAt > 5000) {
				TASK::CLEAR_PED_TASKS(ped, true, false);
				resetWaterPumpAction("exit-timeout");
			}
		}
		return;
	}

	const bool baseEligible = waterPumpApiReady() && ped && !locked && !mission &&
		!ENTITY::IS_ENTITY_DEAD(ped) && !PED::IS_PED_RAGDOLL(ped) &&
		!PED::IS_PED_IN_COMBAT(ped, 0) && !PED::IS_PED_ON_MOUNT(ped) &&
		!PED::IS_PED_USING_ANY_SCENARIO(ped) && PLAYER_CONTROL_ON(player);
	if (!baseEligible) {
		hideWaterPumpPrompts();
		g_waterPumpRuntime.pump = 0;
		g_waterPumpRuntime.sourcePoint = 0;
		return;
	}

	if (!g_waterPumpRuntime.nextScanAt || now >= g_waterPumpRuntime.nextScanAt) {
		g_waterPumpRuntime.nextScanAt = now + 250;
		g_waterPumpRuntime.pump = findEligibleWaterPump(ped,
			g_waterPumpRuntime.sourcePoint);
	}
	if (!g_waterPumpRuntime.pump) {
		hideWaterPumpPrompts();
		return;
	}

	const bool owned = g_waterPumpCanteenApi.owned();
	const int charges = g_waterPumpCanteenApi.charges();
	const int capacity = (std::max)(1, g_waterPumpCanteenApi.capacity());
	const bool canRefill = owned && charges < capacity;
	waterPumpPromptText(g_waterPumpDrinkPrompt, "Drink");
	waterPumpPromptText(g_waterPumpRefillPrompt,
		!owned ? "No Canteen" : (canRefill ? "Refill Canteen" : "Canteen Full"));
	waterPumpPromptVisible(g_waterPumpDrinkPrompt, true);
	// Keep the unavailable state visible so "full" and "not owned" are clear,
	// but disable its hold mode so R cannot replay a meaningless interaction.
	waterPumpPromptState(g_waterPumpRefillPrompt, true, canRefill);

	if (waterPumpPromptDone(g_waterPumpDrinkPrompt))
		beginWaterPumpAction(ped, WaterPumpAction::Drink, now);
	else if (canRefill && waterPumpPromptDone(g_waterPumpRefillPrompt))
		beginWaterPumpAction(ped, WaterPumpAction::Refill, now);
}
