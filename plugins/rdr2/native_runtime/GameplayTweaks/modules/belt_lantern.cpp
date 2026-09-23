// GitHub #5 - radial-controlled belt lantern.
//
// Primary-source contract:
//   - defaultcarriablesdata.meta maps lantern01/02/03 to the normal, Davy and
//     electric lantern weapons and names the carried grip ID_GUN_GRIPR.
//   - player_zero__boneNames.lua resolves PH_Belt_Thrower to player bone 2656.
//     Vanilla weapons.ymt maps WEAPON_ATTACH_POINT_LANTERN to that exact bone;
//     CP_R_Belt overlaps the right holster/knife/leg in Lexer's runtime test.
//   - beat_treasure_hunter.c:1000 uses named object and owner bones with
//     ATTACH_ENTITY_TO_ENTITY_PHYSICALLY. Its final RDR2 arguments are copied
//     here. No guessed numeric bone ID remains.
//   - act_camp_fff_light.c:3004-3005 returns a held light to WEAPON_UNARMED.
//
// updateBeltLantern runs every frame. Weapon state is sampled at 20 Hz,
// attachment/gate health at 4 Hz, and the idle heartbeat every 3 seconds. When
// lit, entity existence/position and DRAW_LIGHT_WITH_RANGE remain per-frame:
// the light is frame-scoped and its origin must follow the physical prop.

static Object g_beltLanternProp = 0;
static Ped g_beltLanternOwner = 0;
static Hash g_beltLanternModel = 0;
static bool g_beltLanternLit = false;
static bool g_beltLanternWasSelected = false;
static bool g_beltLanternPendingStow = false;
static bool g_beltLanternStowDeferredLogged = false;
static bool g_beltLanternVerifyStow = false;
static DWORD g_beltLanternPollAt = 0;
static DWORD g_beltLanternHealthAt = 0;
static DWORD g_beltLanternHeartbeatAt = 0;
static DWORD g_beltLanternSpawnTryAt = 0;
static DWORD g_beltLanternSelectionAt = 0;
static DWORD g_beltLanternVerifyAt = 0;
static DWORD g_beltLanternConditionAt = 0;
static int g_beltLanternConditionGate = 0;
static int g_beltLanternGate = -1;
static int g_beltLanternSpawnFailure = 0;
static bool g_beltLanternCalibrating = false;
static int g_beltLanternPropBone = -1;
static int g_beltLanternPedBone = -1;
static int g_beltLanternCalibrationPose = 0;
static int g_beltLanternBestPose = -1;
static float g_beltLanternBestScore = -2.0f;
static DWORD g_beltLanternCalibrationAt = 0;
static Vector3 g_beltLanternModelCenter = {};
static float g_beltLanternAppliedScale = -1.0f;
static float g_beltLanternScaleAttempted = -1.0f;

static const DWORD kBeltLanternPollMs = 50;
static const DWORD kBeltLanternHealthMs = 250;
static const DWORD kBeltLanternHeartbeatMs = 3000;
static const DWORD kBeltLanternSelectionDebounceMs = 750;
static const Hash kBeltLanternSwapTaskHash = 716706914;
static const DWORD kBeltLanternCalibrationSettleMs = 150;

struct BeltLanternPose {
	float x;
	float y;
	float z;
	const char* name;
	bool rejectedByRuntime;
};

// This is a bounded basis calibration, not a list of claimed-good poses. Zero
// was visible but rearward. +90 X is retained only as the explicitly rejected
// control from Lexer's next test; it can be measured but can never win. The
// remaining quarter-turns span the unresolved constraint axes without shipping
// another visual guess as fact.
static const BeltLanternPose kBeltLanternPoses[] = {
	{ 0.0f, 0.0f, 0.0f, "zero", false },
	{ 90.0f, 0.0f, 0.0f, "plus-x-runtime-rejected", true },
	{ -90.0f, 0.0f, 0.0f, "minus-x", false },
	{ 0.0f, 90.0f, 0.0f, "plus-y", false },
	{ 0.0f, -90.0f, 0.0f, "minus-y", false },
	{ 0.0f, 0.0f, 90.0f, "plus-z", false },
	{ 0.0f, 0.0f, -90.0f, "minus-z", false },
};

static void beltLanternLog(GtLogLevel level, const std::string& event) {
	gtLog("belt-lantern", level, event);
}

static void beltLanternLogSpawnFailure(int failure, const char* event) {
	if (failure == g_beltLanternSpawnFailure) return;
	g_beltLanternSpawnFailure = failure;
	beltLanternLog(GT_ERROR, event);
}

static const char* beltLanternGateName(int gate) {
	switch (gate) {
		case 1: return "disabled";
		case 2: return "mission";
		case 3: return "dead";
		case 4: return "swimming";
		case 5: return "ragdoll";
		default: return "active";
	}
}

static void setBeltLanternGate(int gate) {
	if (gate == g_beltLanternGate) return;
	g_beltLanternGate = gate;
	beltLanternLog(GT_INFO, std::string("gate=") + beltLanternGateName(gate));
}

static bool isBeltLanternWeapon(Hash weapon) {
	return weapon == joaat("WEAPON_MELEE_LANTERN") ||
		weapon == joaat("WEAPON_MELEE_DAVY_LANTERN") ||
		weapon == joaat("WEAPON_MELEE_LANTERN_ELECTRIC");
}

static Hash beltLanternModelForWeapon(Hash weapon) {
	if (weapon == joaat("WEAPON_MELEE_DAVY_LANTERN"))
		return joaat("s_interact_lantern02x");
	if (weapon == joaat("WEAPON_MELEE_LANTERN_ELECTRIC"))
		return joaat("s_interact_lantern03x");
	return joaat("s_interact_lantern01x");
}

static Hash beltLanternWeaponForModel(Hash model) {
	if (model == joaat("s_interact_lantern02x"))
		return joaat("WEAPON_MELEE_DAVY_LANTERN");
	if (model == joaat("s_interact_lantern03x"))
		return joaat("WEAPON_MELEE_LANTERN_ELECTRIC");
	return joaat("WEAPON_MELEE_LANTERN");
}

static Hash selectedBeltLanternWeapon(Ped ped) {
	Hash weapon = 0;
	if (!WEAPON::GET_CURRENT_PED_WEAPON(ped, &weapon, TRUE, 0, FALSE)) return 0;
	return isBeltLanternWeapon(weapon) ? weapon : 0;
}

static void removeBeltLantern(const char* reason) {
	if (g_beltLanternProp && ENTITY::DOES_ENTITY_EXIST(g_beltLanternProp)) {
		ENTITY::SET_ENTITY_AS_MISSION_ENTITY(g_beltLanternProp, TRUE, TRUE);
		Object handle = g_beltLanternProp;
		OBJECT::DELETE_OBJECT(&handle);
		beltLanternLog(GT_INFO, std::string("prop removed reason=") + reason);
	}
	g_beltLanternProp = 0;
	g_beltLanternOwner = 0;
	g_beltLanternCalibrating = false;
	g_beltLanternPropBone = -1;
	g_beltLanternPedBone = -1;
	g_beltLanternCalibrationPose = 0;
	g_beltLanternBestPose = -1;
	g_beltLanternBestScore = -2.0f;
	g_beltLanternCalibrationAt = 0;
	g_beltLanternHealthAt = 0;
	g_beltLanternAppliedScale = -1.0f;
	g_beltLanternScaleAttempted = -1.0f;
	g_beltLanternSpawnTryAt = 0;
}

// natives.json names 0xB6CBD40F8EA69E8A CREATE_OBJECT_SKELETON(Object).
// campfire_gang.c:53661 calls it immediately before a physical attachment.
static bool createBeltLanternSkeleton(Object object) {
	return invoke<BOOL>(0xB6CBD40F8EA69E8A, object) != FALSE;
}

// natives.json resolves the full 22-argument RDR2 signature. The constraint
// tail (FALSE, TRUE, FALSE, TRUE, 2, TRUE, 1.0, 1.0) is copied from
// beat_treasure_hunter.c:1000. Collision between prop and player is disabled;
// world collision remains enabled on the prop.
static void physicallyAttachBeltLantern(Object prop, Ped ped,
	int propBone, int pedBone, const BeltLanternPose& pose) {
	invoke<Void>(0xB629A43CA1643481,
		prop, ped, propBone, pedBone,
		0.0f, 0.0f, 0.0f,
		0.0f, 0.0f, 0.0f,
		pose.x, pose.y, pose.z, -1.0f,
		FALSE, TRUE, FALSE, TRUE, 2, TRUE, 1.0f, 1.0f);
}

static void attachBeltLanternCalibrationPose(DWORD now) {
	const BeltLanternPose& pose = kBeltLanternPoses[g_beltLanternCalibrationPose];
	physicallyAttachBeltLantern(g_beltLanternProp, g_beltLanternOwner,
		g_beltLanternPropBone, g_beltLanternPedBone, pose);
	g_beltLanternCalibrationAt = now;
}

static void updateBeltLanternCalibration(DWORD now) {
	if (!g_beltLanternCalibrating || !g_beltLanternProp ||
		now - g_beltLanternCalibrationAt < kBeltLanternCalibrationSettleMs) return;
	const BeltLanternPose& pose = kBeltLanternPoses[g_beltLanternCalibrationPose];
	const Vector3 grip = ENTITY::GET_WORLD_POSITION_OF_ENTITY_BONE(
		g_beltLanternProp, g_beltLanternPropBone);
	const Vector3 center = ENTITY::GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(
		g_beltLanternProp, g_beltLanternModelCenter.x,
		g_beltLanternModelCenter.y, g_beltLanternModelCenter.z);
	const float dx = center.x - grip.x;
	const float dy = center.y - grip.y;
	const float dz = center.z - grip.z;
	const float length = std::sqrt(dx * dx + dy * dy + dz * dz);
	const float downScore = length > 0.001f ? -dz / length : -2.0f;
	{
		char line[256] = {};
		sprintf_s(line,
			"pose calibration sample=%d name=%s rotation=%.0f,%.0f,%.0f "
			"gripToCenter=%.3f,%.3f,%.3f length=%.3f downScore=%.3f rejected=%d",
			g_beltLanternCalibrationPose, pose.name, pose.x, pose.y, pose.z,
			dx, dy, dz, length, downScore, pose.rejectedByRuntime ? 1 : 0);
		beltLanternLog(GT_INFO, line);
	}
	if (!pose.rejectedByRuntime && length > 0.001f && downScore > g_beltLanternBestScore) {
		g_beltLanternBestScore = downScore;
		g_beltLanternBestPose = g_beltLanternCalibrationPose;
	}
	ENTITY::DETACH_ENTITY(g_beltLanternProp, TRUE, FALSE);
	++g_beltLanternCalibrationPose;
	if (g_beltLanternCalibrationPose < (int)_countof(kBeltLanternPoses)) {
		attachBeltLanternCalibrationPose(now);
		return;
	}
	if (g_beltLanternBestPose < 0) {
		beltLanternLog(GT_ERROR,
			"pose calibration failed no valid grip-to-center vector; prop removed");
		removeBeltLantern("pose calibration failed");
		return;
	}
	const BeltLanternPose& selected = kBeltLanternPoses[g_beltLanternBestPose];
	physicallyAttachBeltLantern(g_beltLanternProp, g_beltLanternOwner,
		g_beltLanternPropBone, g_beltLanternPedBone, selected);
	if (!ENTITY::IS_ENTITY_ATTACHED_TO_ENTITY(
		g_beltLanternProp, g_beltLanternOwner)) {
		beltLanternLog(GT_ERROR,
			"pose calibration final attach readback=not-attached; prop removed");
		removeBeltLantern("pose calibration final attach failed");
		return;
	}
	ENTITY::SET_ENTITY_COLLISION(g_beltLanternProp, TRUE, TRUE);
	ENTITY::SET_ENTITY_NO_COLLISION_ENTITY(
		g_beltLanternProp, g_beltLanternOwner, FALSE);
	ENTITY::SET_ENTITY_VISIBLE(g_beltLanternProp, TRUE);
	g_beltLanternCalibrating = false;
	g_beltLanternHealthAt = now;
	{
		char line[224] = {};
		sprintf_s(line,
			"pose calibration selected=%d name=%s rotation=%.0f,%.0f,%.0f "
			"downScore=%.3f anchor=PH_Belt_Thrower vanillaAttachPoint=WEAPON_ATTACH_POINT_LANTERN",
			g_beltLanternBestPose, selected.name, selected.x, selected.y, selected.z,
			g_beltLanternBestScore);
		beltLanternLog(GT_INFO, line);
	}
}

static bool spawnBeltLantern(Ped ped, DWORD now) {
	if (now - g_beltLanternSpawnTryAt < 250) return false;
	g_beltLanternSpawnTryAt = now;
	if (!g_beltLanternModel)
		g_beltLanternModel = joaat("s_interact_lantern01x");

	if (!STREAMING::HAS_MODEL_LOADED(g_beltLanternModel)) {
		STREAMING::REQUEST_MODEL(g_beltLanternModel, FALSE);
		return false;
	}

	// Vanilla weapons.ymt maps every Story lantern's HolsterAttachPoint to
	// WEAPON_ATTACH_POINT_LANTERN, whose AttachPointInfos entry names
	// ID_PH_BELT_THROWER. The extracted player skeleton resolves its runtime name
	// as PH_Belt_Thrower (bone 2656). This replaces CP_R_Belt because Lexer's live
	// test proved that generic right-belt point overlaps the holster/knife/leg.
	const int pedBone = ENTITY::GET_ENTITY_BONE_INDEX_BY_NAME(ped, "PH_Belt_Thrower");
	if (pedBone < 0) {
		beltLanternLogSpawnFailure(1,
			"spawn rejected missing player bone=PH_Belt_Thrower; no prop created");
		return false;
	}
	const Vector3 hip = ENTITY::GET_WORLD_POSITION_OF_ENTITY_BONE(ped, pedBone);
	const Hash weapon = beltLanternWeaponForModel(g_beltLanternModel);
	Object prop = WEAPON::_CREATE_WEAPON_OBJECT(weapon, 0,
		hip.x, hip.y, hip.z, TRUE, g_beltLanternScale);
	if (!prop) {
		beltLanternLogSpawnFailure(2,
			"spawn failed CREATE_WEAPON_OBJECT returned 0");
		return false;
	}

	ENTITY::SET_ENTITY_AS_MISSION_ENTITY(prop, TRUE, TRUE);
	const float appliedScale = invoke<float>(0x22084CA699219624, prop);
	g_beltLanternAppliedScale = appliedScale;
	g_beltLanternScaleAttempted = g_beltLanternScale;
	if (!createBeltLanternSkeleton(prop)) {
		Object handle = prop;
		OBJECT::DELETE_OBJECT(&handle);
		beltLanternLogSpawnFailure(3,
			"spawn rejected CREATE_OBJECT_SKELETON failed; created prop deleted");
		return false;
	}

	const int propBone = ENTITY::GET_ENTITY_BONE_INDEX_BY_NAME(prop, "Gun_GripR");
	if (propBone < 0) {
		Object handle = prop;
		OBJECT::DELETE_OBJECT(&handle);
		beltLanternLogSpawnFailure(4,
			"spawn rejected missing lantern bone=Gun_GripR; created prop deleted");
		return false;
	}
	Vector3 modelMin = {}, modelMax = {};
	MISC::GET_MODEL_DIMENSIONS(g_beltLanternModel, &modelMin, &modelMax);
	g_beltLanternModelCenter = {
		(modelMin.x + modelMax.x) * 0.5f,
		(modelMin.y + modelMax.y) * 0.5f,
		(modelMin.z + modelMax.z) * 0.5f
	};
	ENTITY::SET_ENTITY_VISIBLE(prop, FALSE);
	ENTITY::SET_ENTITY_COLLISION(prop, FALSE, FALSE);
	ENTITY::SET_ENTITY_NO_COLLISION_ENTITY(prop, ped, FALSE);
	g_beltLanternProp = prop;
	g_beltLanternOwner = ped;
	g_beltLanternPropBone = propBone;
	g_beltLanternPedBone = pedBone;
	g_beltLanternCalibrationPose = 0;
	g_beltLanternBestPose = -1;
	g_beltLanternBestScore = -2.0f;
	g_beltLanternCalibrating = true;
	attachBeltLanternCalibrationPose(now);

	if (!ENTITY::IS_ENTITY_ATTACHED_TO_ENTITY(prop, ped)) {
		beltLanternLogSpawnFailure(5,
			"attach failed readback=not-attached; created prop deleted");
		removeBeltLantern("initial calibration attach failed");
		return false;
	}

	g_beltLanternSpawnFailure = 0;
	STREAMING::SET_MODEL_AS_NO_LONGER_NEEDED(g_beltLanternModel);
	beltLanternLog(GT_INFO, "prop calibration spawned attachment=physical playerBone=PH_Belt_Thrower "
		"vanillaAttachPoint=WEAPON_ATTACH_POINT_LANTERN "
		"propBone=Gun_GripR weapon=" + std::to_string(weapon) +
		" model=" + std::to_string(g_beltLanternModel) +
		" requestedScale=" + std::to_string(g_beltLanternScale) +
		" appliedScale=" + std::to_string(appliedScale) +
		" candidates=7 rejectedControl=plus-x-runtime-rejected visible=0 collision=0");
	return true;
}

static bool beltLanternSwapTaskBusy(Ped ped) {
	const int status = TASK::GET_SCRIPT_TASK_STATUS(
		ped, kBeltLanternSwapTaskHash, TRUE);
	return status == 0 || status == 1;
}

static void issueBeltLanternStow(Ped ped, DWORD now) {
	if (!g_beltLanternPendingStow) return;
	if (beltLanternSwapTaskBusy(ped)) {
		if (!g_beltLanternStowDeferredLogged) {
			g_beltLanternStowDeferredLogged = true;
			beltLanternLog(GT_INFO, "stow deferred weapon-swap task busy");
		}
		return;
	}
	const Hash current = selectedBeltLanternWeapon(ped);
	if (!current) {
		g_beltLanternPendingStow = false;
		g_beltLanternStowDeferredLogged = false;
		beltLanternLog(GT_INFO, "stow cleared current weapon already not lantern");
		return;
	}

	// Complete Story Mode stow sequence. It is issued once, only after the
	// shared weapon-swap task becomes idle.
	HIDE_PED_WEAPONS(ped, 2, false);
	WEAPON::SET_CURRENT_PED_WEAPON(ped, joaat("WEAPON_UNARMED"),
		FALSE, 0, FALSE, FALSE);
	TASK::TASK_SWAP_WEAPON(ped, 0, 0, 0, 0);
	g_beltLanternPendingStow = false;
	g_beltLanternStowDeferredLogged = false;
	g_beltLanternVerifyStow = true;
	g_beltLanternVerifyAt = now;
	beltLanternLog(GT_INFO, "stow issued weapon=" + std::to_string(current));
}

static void verifyBeltLanternStow(Ped ped, DWORD now) {
	if (!g_beltLanternVerifyStow || now - g_beltLanternVerifyAt < 2000) return;
	g_beltLanternVerifyStow = false;
	const Hash current = selectedBeltLanternWeapon(ped);
	if (current) {
		beltLanternLog(GT_ERROR, "stow readback failed lantern still current weapon=" +
			std::to_string(current));
	} else {
		beltLanternLog(GT_INFO, "stow readback passed current weapon is not lantern");
	}
}

static void pollBeltLanternRadial(Ped ped, DWORD now) {
	if (now - g_beltLanternPollAt < kBeltLanternPollMs) return;
	g_beltLanternPollAt = now;
	const Hash weapon = selectedBeltLanternWeapon(ped);
	const bool selected = weapon != 0;
	const bool rising = selected && !g_beltLanternWasSelected;
	g_beltLanternWasSelected = selected;

	if (rising) {
		if (now - g_beltLanternSelectionAt < kBeltLanternSelectionDebounceMs) {
			beltLanternLog(GT_WARN, "radial edge rejected debounce weapon=" +
				std::to_string(weapon));
		} else {
			g_beltLanternSelectionAt = now;
			g_beltLanternLit = !g_beltLanternLit;
			const Hash model = beltLanternModelForWeapon(weapon);
			if (model != g_beltLanternModel) {
				g_beltLanternModel = model;
				removeBeltLantern("selected model changed");
			}
			g_beltLanternPendingStow = true;
			g_beltLanternStowDeferredLogged = false;
			beltLanternLog(GT_INFO, "radial toggle lit=" +
				std::to_string(g_beltLanternLit ? 1 : 0) +
				" weapon=" + std::to_string(weapon) +
				" model=" + std::to_string(g_beltLanternModel));
		}
	}

	issueBeltLanternStow(ped, now);
	verifyBeltLanternStow(ped, now);
}

static void checkBeltLanternAttachment(Ped ped, DWORD now) {
	if (!g_beltLanternProp ||
		g_beltLanternCalibrating ||
		now - g_beltLanternHealthAt < kBeltLanternHealthMs) return;
	g_beltLanternHealthAt = now;
	if (!ENTITY::DOES_ENTITY_EXIST(g_beltLanternProp)) {
		g_beltLanternProp = 0;
		g_beltLanternOwner = 0;
		beltLanternLog(GT_ERROR, "health failed prop no longer exists");
		return;
	}
	if (!ENTITY::IS_ENTITY_ATTACHED_TO_ENTITY(g_beltLanternProp, ped)) {
		removeBeltLantern("health failed detached");
		return;
	}
	if (std::fabs(g_beltLanternScaleAttempted - g_beltLanternScale) > 0.0001f) {
		g_beltLanternScaleAttempted = g_beltLanternScale;
		invoke<Void>(0xC3544AD0522E69B4,
			g_beltLanternProp, g_beltLanternScale);
		g_beltLanternAppliedScale = invoke<float>(
			0x22084CA699219624, g_beltLanternProp);
		beltLanternLog(GT_INFO, "scale changed requested=" +
			std::to_string(g_beltLanternScale) + " applied=" +
			std::to_string(g_beltLanternAppliedScale));
	}
	const int hipBone = ENTITY::GET_ENTITY_BONE_INDEX_BY_NAME(ped, "PH_Belt_Thrower");
	if (hipBone < 0) {
		removeBeltLantern("health failed missing PH_Belt_Thrower");
		return;
	}
	const Vector3 hip = ENTITY::GET_WORLD_POSITION_OF_ENTITY_BONE(ped, hipBone);
	const Vector3 prop = ENTITY_COORDS(g_beltLanternProp);
	const float dx = prop.x - hip.x;
	const float dy = prop.y - hip.y;
	const float dz = prop.z - hip.z;
	const float distanceSquared = dx * dx + dy * dy + dz * dz;
	if (distanceSquared > 1.5625f) {
		beltLanternLog(GT_ERROR, "health failed displacementSquared=" +
			std::to_string(distanceSquared) + " limitSquared=1.5625");
		removeBeltLantern("displacement failsafe");
	}
}

static void beltLanternHeartbeat(Ped ped, DWORD now) {
	if (now - g_beltLanternHeartbeatAt < kBeltLanternHeartbeatMs) return;
	g_beltLanternHeartbeatAt = now;
	beltLanternLog(GT_INFO, std::string("heartbeat gate=") +
		beltLanternGateName(g_beltLanternGate) +
		" ped=" + std::to_string(ped) +
		" prop=" + std::to_string(g_beltLanternProp) +
		" scale=" + std::to_string(g_beltLanternAppliedScale) +
		" calibrating=" + std::to_string(g_beltLanternCalibrating ? 1 : 0) +
		" lit=" + std::to_string(g_beltLanternLit ? 1 : 0) +
		" pendingStow=" + std::to_string(g_beltLanternPendingStow ? 1 : 0) +
		" spawnFailure=" + std::to_string(g_beltLanternSpawnFailure));
}

static void updateBeltLantern(Ped ped, bool mission) {
	const DWORD now = GetTickCount();

	int gate = 0;
	if (!g_beltLanternEnabled || !ped) gate = 1;
	else if (mission) gate = 2;
	else {
		if (!g_beltLanternConditionAt ||
			now - g_beltLanternConditionAt >= kBeltLanternHealthMs) {
			g_beltLanternConditionAt = now;
			g_beltLanternConditionGate =
				PED::IS_PED_DEAD_OR_DYING(ped, TRUE) ? 3 :
				PED::IS_PED_SWIMMING(ped) ? 4 :
				PED::IS_PED_RAGDOLL(ped) ? 5 : 0;
		}
		gate = g_beltLanternConditionGate;
	}
	setBeltLanternGate(gate);
	beltLanternHeartbeat(ped, now);
	if (gate) {
		removeBeltLantern(beltLanternGateName(gate));
		g_beltLanternWasSelected = true;
		g_beltLanternPendingStow = false;
		g_beltLanternStowDeferredLogged = false;
		g_beltLanternVerifyStow = false;
		return;
	}

	if (g_beltLanternOwner && g_beltLanternOwner != ped)
		removeBeltLantern("player ped changed");
	pollBeltLanternRadial(ped, now);
	if (!g_beltLanternProp) spawnBeltLantern(ped, now);
	updateBeltLanternCalibration(now);
	checkBeltLanternAttachment(ped, now);

	if (g_beltLanternLit && g_beltLanternBrightness > 0.0f &&
		!g_beltLanternCalibrating && g_beltLanternProp &&
		ENTITY::DOES_ENTITY_EXIST(g_beltLanternProp)) {
		const Vector3 lit = ENTITY_COORDS(g_beltLanternProp);
		GRAPHICS::DRAW_LIGHT_WITH_RANGE(lit.x, lit.y, lit.z - 0.12f,
			255, 176, 92, g_beltLanternRange, g_beltLanternBrightness);
	}
}
