// GameplayTweaks feature module: live third-person camera calibration (#8).
//
// RDR2's public native surface provides two continuous position controls for
// the gameplay camera: signed horizontal offset and orbit distance.  It also
// provides one real, binary low/ground-level framing state.  There is no
// continuous vertical-position argument, so this module deliberately exposes
// LOW/NORMAL instead of a slider that could not affect the shipped camera.

// #177: the on-foot follow camera is not one rig. Unholstering swaps Rockstar's
// own base third-person camera even though our submitted horizontal offset and
// distance are unchanged, which is exactly what Lexer observed ("camera mode is
// standing ... yet unholstering a gun clearly moves the camera a bit"). ARMED
// and CROUCHED ARMED are appended so that rig gets its own tunable profile
// instead of inheriting the holstered numbers. New entries are appended, never
// inserted, so existing INI keys keep their meaning.
enum class GameplayCameraMode : int {
	Standing = 0,
	Crouched,
	Prone,
	Horseback,
	Vehicle,
	Aim,
	CrouchedAim,
	Armed,
	CrouchedArmed,
	Count
};

struct GameplayCameraProfile {
	const char* label;
	const char* keyPrefix;
	float horizontal;
	float distance;
	bool low;
};

static GameplayCameraProfile g_cameraProfiles[(int)GameplayCameraMode::Count] = {
	{ "STANDING",   "Standing",   0.42f, 2.10f, false },
	{ "CROUCHED",   "Crouched",   0.42f, 1.85f, false },
	{ "PRONE",      "Prone",      0.55f, 1.60f, true  },
	{ "HORSEBACK",  "Horseback",  0.42f, 2.40f, false },
	{ "VEHICLE",    "Vehicle",    0.42f, 2.80f, false },
	{ "AIM",        "Aim",        0.55f, 1.35f, false },
	{ "CROUCHED AIM", "CrouchedAim", 0.55f, 1.35f, true },
	// #177: seeded from the holstered profiles so behaviour is unchanged until
	// Lexer actually tunes them. The point of the split is that he now CAN.
	{ "ARMED",         "Armed",         0.42f, 2.10f, false },
	{ "CROUCHED ARMED", "CrouchedArmed", 0.42f, 1.85f, false },
};

static bool g_gameplayCameraConfigLoaded = false;
static bool g_gameplayCameraEnabled = true;
static bool g_gameplayCameraLockZoom = true;
// #128: the on-foot zoom lock was deliberately not applied to the mounted
// camera in #8, so horseback kept Rockstar's full four-view cycle (three
// third-person zoom steps plus first person) while on foot had two.  These two
// settings extend the same lock to the mounted follow camera.
static bool g_gameplayCameraLockZoomMounted = true;
static int g_gameplayCameraMountedZoomLevel = 0;
static float g_gameplayCameraBlendSpeed = 1.0f;
static bool g_gameplayCameraLowApplied = false;
// #178: the applied profile only follows the observed stance after it has been
// stable for this long. A stance predicate that flickers for one or two frames
// (crouch gait, holster transition) would otherwise alternate two different
// submitted distances at gait frequency, which is what a "constant, almost
// sinusoidal bumping" looks like. 0 restores the old immediate behaviour.
static int g_gameplayCameraModeDwellMs = 100;
// #178: bounded camera telemetry cadence. This module previously logged only a
// 3 s heartbeat that named no camera state at all, so the answer to "what does
// the log say" about #177 and #178 was literally nothing.
static int g_gameplayCameraSampleMs = 500;
static GameplayCameraMode g_gameplayCameraAppliedMode = GameplayCameraMode::Standing;
static bool g_gameplayCameraAppliedModeKnown = false;
static unsigned int g_gameplayCameraRawModeFlips = 0;
static unsigned int g_gameplayCameraAppliedModeFlips = 0;
// #8 follows the one shared runtime developer-mode boundary. Tilde is owned by
// the integration dispatcher; this module only observes developmentModeActive()
// and therefore cannot create a camera-only mode or toggle the global state a
// second time. Compiling authoring code into a normal build does not make its
// inputs live: calibration and keypad ownership remain gated below.

// #8/#23: Numpad 0 swaps the one shared keypad between the camera editor and
// the fortification editor.  The fortification updater normally flips this
// flag first, but it can return before reading the key while the HUD/reference
// canvas/texture dictionary is unavailable.  Observe its result here and only
// perform the flip when its updater did not, so ownership can never get stuck
// on an editor that is not currently able to draw or accept input.
static void updateGameplayCameraNumpadOwnership() {
	static bool numpadZeroLatch = false;
	static bool previousFortificationOwner = false;
	const bool numpadZeroDown =
		(GetAsyncKeyState(VK_NUMPAD0) & 0x8000) != 0;
	if (numpadZeroDown && !numpadZeroLatch &&
		g_fortificationCalibrationOwnsNumpad == previousFortificationOwner) {
		g_fortificationCalibrationOwnsNumpad =
			!g_fortificationCalibrationOwnsNumpad;
		gtLog("camera-editor", GT_INFO,
			g_fortificationCalibrationOwnsNumpad
				? "Numpad0 owner=fortification source=camera-fallback"
				: "Numpad0 owner=camera source=camera-fallback");
	}
	if (numpadZeroDown && !numpadZeroLatch &&
		g_fortificationCalibrationOwnsNumpad != previousFortificationOwner) {
		gtLog("camera-editor", GT_INFO,
			g_fortificationCalibrationOwnsNumpad
				? "Numpad0 owner=fortification source=fortification"
				: "Numpad0 owner=camera source=fortification");
	}
	numpadZeroLatch = numpadZeroDown;
	previousFortificationOwner = g_fortificationCalibrationOwnsNumpad;
}

static bool gameplayCameraReadBool(const char* key, bool fallback) {
	return GetPrivateProfileIntA("Camera", key, fallback ? 1 : 0,
		g_iniPath.c_str()) != 0;
}

static float gameplayCameraReadFloat(const char* key, float fallback) {
	char def[32] = {};
	char value[64] = {};
	sprintf_s(def, "%.3f", fallback);
	GetPrivateProfileStringA("Camera", key, def, value, sizeof(value),
		g_iniPath.c_str());
	return (float)atof(value);
}

static void loadGameplayCameraConfig() {
	g_gameplayCameraEnabled = gameplayCameraReadBool("Enabled", true);
	g_gameplayCameraLockZoom = gameplayCameraReadBool("LockToOneThirdPersonZoom", true);
	g_gameplayCameraLockZoomMounted =
		gameplayCameraReadBool("LockToOneThirdPersonZoomMounted", true);
	g_gameplayCameraMountedZoomLevel = (int)GetPrivateProfileIntA("Camera",
		"MountedThirdPersonLevel", 0, g_iniPath.c_str());
	g_gameplayCameraMountedZoomLevel =
		(std::max)(0, (std::min)(2, g_gameplayCameraMountedZoomLevel));
	g_gameplayCameraBlendSpeed = gameplayCameraReadFloat("BlendSpeed", 1.0f);
	if (!std::isfinite(g_gameplayCameraBlendSpeed) ||
		g_gameplayCameraBlendSpeed <= 0.0f)
		g_gameplayCameraBlendSpeed = 1.0f;
	g_gameplayCameraModeDwellMs = (int)GetPrivateProfileIntA("Camera",
		"ModeDwellMs", 100, g_iniPath.c_str());
	if (g_gameplayCameraModeDwellMs < 0) g_gameplayCameraModeDwellMs = 0;
	g_gameplayCameraSampleMs = (int)GetPrivateProfileIntA("Camera",
		"SampleIntervalMs", 500, g_iniPath.c_str());
	if (g_gameplayCameraSampleMs < 0) g_gameplayCameraSampleMs = 0;
	for (int i = 0; i < (int)GameplayCameraMode::Count; ++i) {
		GameplayCameraProfile& p = g_cameraProfiles[i];
		char key[64] = {};
		sprintf_s(key, "%sShoulderOffset", p.keyPrefix);
		p.horizontal = gameplayCameraReadFloat(key, p.horizontal);
		sprintf_s(key, "%sDistance", p.keyPrefix);
		p.distance = gameplayCameraReadFloat(key, p.distance);
		sprintf_s(key, "%sLowCamera", p.keyPrefix);
		p.low = gameplayCameraReadBool(key, p.low);
		// The old +/-2 and replacement +/-20 limits were both project-invented.
		// Keep only finite/nonnegative validation. The native owns its real range.
		if (!std::isfinite(p.horizontal)) p.horizontal = 0.0f;
		p.horizontal = fabsf(p.horizontal);
		// Distance is nonnegative by definition. The old 8.0 upper limit had no
		// source basis and stopped the live editor while the camera was still
		// moving. Reject invalid/negative input, but let the camera native own its
		// usable upper range.
		if (!std::isfinite(p.distance) || p.distance < 0.0f) p.distance = 0.0f;
	}
	g_gameplayCameraConfigLoaded = true;
}

static bool gameplayCameraFirstPerson() {
	// natives.json names this exact zero-argument native
	// _IS_IN_FULL_FIRST_PERSON_MODE and documents it as true whenever the player
	// is in first person. The old three-argument 0xA24... predicate did not cover
	// the vehicle first-person rig and let our third-person profile pull it out.
	return invoke<BOOL>(0xD1BA66940E94C547) != 0 ||
		CAM::IS_FIRST_PERSON_AIM_CAM_ACTIVE();
}

static bool gameplayCameraAimHeld() {
	const Hash aim = joaat("INPUT_AIM");
	return PAD::IS_CONTROL_PRESSED(0, aim) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, aim) ||
		PAD::IS_CONTROL_PRESSED(2, aim) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, aim);
}

enum class GameplayCameraShoulderInput {
	None = 0,
	MappedAction,
	KeyboardX
};

// #154/#175 root cause, and the reason every previous input-debounce attempt was
// working on the wrong layer.
//
// 1. RDR2's public native surface has NO shoulder-side setter. A full dump of
//    the CAMERA namespace in _downloads/natives.json contains no SHOULDER
//    entry; the only continuous horizontal control is
//    _SET_GAMEPLAY_CAM_PARAMS_THIS_UPDATE (0x066167C63111D8CF, natives.json
//    params: speed, respectHorizontalOffset, horizontalOffset,
//    respectDistance, distance). The side therefore belongs to the engine.
//
// 2. horizontalOffset does not mirror when negated. Two independent live
//    observations rule out the alternatives:
//      - #175 worklog: submitted +2.95 rendered "camera on Arthur's left",
//        submitted -2.95 rendered "him centered".
//      - #154 comment: submitted +0.42 put Arthur ~25% across the screen,
//        submitted -0.42 put him ~55% (centre) instead of the mirrored ~75%.
//    An additive engine base B would need B~=2.95 in the first case and
//    B~=0.42 in the second, which cannot both be true, so "additive base" is
//    refuted. A plain abs() would have produced the SAME picture for +h and
//    -h, so "unsigned magnitude, sign ignored" is refuted too. What survives
//    both data points is that a negative horizontalOffset collapses the offset
//    toward zero: the parameter is a nonnegative magnitude applied on
//    whichever shoulder the engine currently owns. This is inferred from two
//    live results, not read from a primary source - no decompiled Story call
//    site for this native exists (grep of
//    _downloads/RDR2-Decompiled-Scripts/script_rel returns zero hits) and
//    cameras.ymt is not in the project extraction. The 2 Hz sample line logs
//    submitted horizontal next to the measured rendered lateral so the next
//    test either confirms or kills this model outright.
//
// 3. The previous build actively suppressed Rockstar's own shoulder action in
//    exactly the state #154 is about. PAD::DISABLE_CONTROL_ACTION's signature
//    is (control, action, disableRelatedActions) - natives.json 0xFE99B66D079CF6BC.
//    The third argument is NOT a disable flag; the native always disables, and
//    FALSE only means "leave related actions alone". Rockstar uses that exact
//    idiom to BLOCK the shoulder swap while a scope is up: binoculars.c:406,
//    camera_item.c:966, camera_photomode.c:1345. So
//    A per-frame disable of the resolved shoulder action outside
//    aim switched Rockstar's holstered shoulder handling off.
//
// Consequence: the module must not own a side at all. It submits a nonnegative
// magnitude, never disables INPUT_SWITCH_SHOULDER, and only OBSERVES the press
// so the log can prove whether the engine's side actually changed. With no
// module-owned side variable there is no double-flip to debounce, which is why
// all of the previous cross-source suppression is gone rather than retuned.
static GameplayCameraShoulderInput gameplayCameraShoulderInput(DWORD now) {
	const Hash switchShoulder = joaat("INPUT_SWITCH_SHOULDER");

	const bool mappedEdge =
		PAD::IS_CONTROL_JUST_PRESSED(0, switchShoulder) ||
		PAD::IS_CONTROL_JUST_PRESSED(2, switchShoulder) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, switchShoulder) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, switchShoulder);

	// Lexer's physical shoulder key is keyboard X. Observing it directly means
	// the log records his press even in a context where Rockstar never raises
	// the semantic action, which is the difference between "the module never
	// saw the press" and "the module saw it and the engine did not move".
	static bool keyboardXLatch = false;
	static DWORD lastObservedEdge = 0;
	const bool keyboardXDown = (GetAsyncKeyState('X') & 0x8000) != 0;
	const bool keyboardXEdge = keyboardXDown && !keyboardXLatch;
	keyboardXLatch = keyboardXDown;

	// Do not turn a key typed into a pause/menu state into a camera log event.
	if (!PLAYER::IS_PLAYER_CONTROL_ON(PLAYER::PLAYER_ID()))
		return GameplayCameraShoulderInput::None;

	// One physical press can surface both as the raw key and as Rockstar's
	// mapped action a frame later. That no longer flips any module state, so
	// the only remaining reason to collapse them is to keep one press to one
	// log record.
	if (now - lastObservedEdge < 250) return GameplayCameraShoulderInput::None;
	if (keyboardXEdge) {
		lastObservedEdge = now;
		return GameplayCameraShoulderInput::KeyboardX;
	}
	if (mappedEdge) {
		lastObservedEdge = now;
		return GameplayCameraShoulderInput::MappedAction;
	}
	return GameplayCameraShoulderInput::None;
}

// #177: Rockstar's own scripts answer "is this ped's weapon put away" with
// WEAPON::_0xBDD9C235D8D1052E(ped), negated next to IS_PED_SHOOTING at
// mary3.c:73776, mudtown4.c:65346, train_robbery2.c:35367, sadie2.c:56138 and
// mary3_intro.c:3389. natives.json names it _IS_PED_CURRENT_WEAPON_HOLSTERED.
static bool gameplayCameraWeaponDrawn(Ped ped) {
	return invoke<BOOL>(0xBDD9C235D8D1052E, ped) == 0;
}

// Measured, not requested. The engine yaw convention is taken from the same
// GET_FINAL_RENDERED_CAM_ROT(2) the previous #175 readback used; only the extra
// planar-distance and vertical terms are new. These are pure reads.
static void gameplayCameraRenderedFrame(Ped ped, float* lateral, float* orbit,
	float* vertical) {
	const Vector3 camera = CAM::GET_FINAL_RENDERED_CAM_COORD();
	const Vector3 origin = ENTITY_COORDS(ped);
	const float yaw = CAM::GET_FINAL_RENDERED_CAM_ROT(2).z * 0.0174532925f;
	const Vector3 right = { std::cos(yaw), std::sin(yaw), 0.0f };
	const Vector3 delta = { camera.x - origin.x, camera.y - origin.y, 0.0f };
	if (lateral) *lateral = delta.x * right.x + delta.y * right.y;
	if (orbit) *orbit = std::sqrt(delta.x * delta.x + delta.y * delta.y);
	if (vertical) *vertical = camera.z - origin.z;
}

static float gameplayCameraRenderedLateral(Ped ped) {
	float lateral = 0.0f;
	gameplayCameraRenderedFrame(ped, &lateral, nullptr, nullptr);
	return lateral;
}

// #269: automatic, non-invasive weapon-draw transition recorder. It owns no
// camera state and calls no camera setter. Eight read-only pre-trigger frames
// are kept in memory so the capture always contains a genuine frame from before
// the weapon-out edge, even if Rockstar starts moving its rig slightly before
// the Armed predicate flips. The first normal draw per process is enough for a
// diagnosis; after a 1.5 s bounded post-edge window the recorder disarms.
struct GameplayCameraTransitionSample {
	bool valid = false;
	DWORD at = 0;
	bool drawn = false;
	bool aimHeld = false;
	bool holsterTransition = false;
	GameplayCameraMode rawMode = GameplayCameraMode::Standing;
	GameplayCameraMode appliedMode = GameplayCameraMode::Standing;
	bool appliedKnown = false;
	Vector3 camera = {};
	Vector3 rotation = {};
	Vector3 ped = {};
	float fov = 0.0f;
	float lateral = 0.0f;
	float orbit = 0.0f;
	float vertical = 0.0f;
};
static GameplayCameraTransitionSample g_cameraTransitionHistory[8];
static int g_cameraTransitionHistoryHead = 0;
static int g_cameraTransitionHistoryCount = 0;
static bool g_cameraTransitionWeaponStateKnown = false;
static bool g_cameraTransitionLastDrawn = false;
static bool g_cameraTransitionRecording = false;
static bool g_cameraTransitionCompleted = false;
static DWORD g_cameraTransitionEdgeAt = 0;
static DWORD g_cameraTransitionUntil = 0;
static DWORD g_cameraTransitionNextSample = 0;

static GameplayCameraTransitionSample gameplayCameraTransitionCapture(Ped ped,
	DWORD now, bool drawn, GameplayCameraMode rawMode) {
	GameplayCameraTransitionSample sample;
	sample.valid = ped && ENTITY::DOES_ENTITY_EXIST(ped);
	sample.at = now;
	sample.drawn = drawn;
	sample.aimHeld = gameplayCameraAimHeld();
	sample.holsterTransition = invoke<BOOL>(0x2387D6E9C6B478AA, ped) != 0;
	sample.rawMode = rawMode;
	sample.appliedKnown = g_gameplayCameraAppliedModeKnown;
	sample.appliedMode = g_gameplayCameraAppliedModeKnown
		? g_gameplayCameraAppliedMode : rawMode;
	sample.camera = CAM::GET_FINAL_RENDERED_CAM_COORD();
	sample.rotation = CAM::GET_FINAL_RENDERED_CAM_ROT(2);
	sample.ped = ENTITY_COORDS(ped);
	sample.fov = CAM::GET_GAMEPLAY_CAM_FOV();
	gameplayCameraRenderedFrame(ped, &sample.lateral, &sample.orbit,
		&sample.vertical);
	return sample;
}

static void gameplayCameraTransitionLog(const char* phase,
	const GameplayCameraTransitionSample& sample, DWORD edgeAt) {
	if (!sample.valid) return;
	const long long offsetMs = (long long)sample.at - (long long)edgeAt;
	std::ostringstream line;
	line << "capture phase=" << phase
		<< " offsetMs=" << offsetMs
		<< " drawn=" << (sample.drawn ? 1 : 0)
		<< " aimHeld=" << (sample.aimHeld ? 1 : 0)
		<< " holsterTransition=" << (sample.holsterTransition ? 1 : 0)
		<< " raw=" << g_cameraProfiles[(int)sample.rawMode].label
		<< " applied=" << (sample.appliedKnown
			? g_cameraProfiles[(int)sample.appliedMode].label : "unknown")
		<< " camPos=" << sample.camera.x << "," << sample.camera.y << "," << sample.camera.z
		<< " camRot=" << sample.rotation.x << "," << sample.rotation.y << "," << sample.rotation.z
		<< " fov=" << sample.fov
		<< " pedPos=" << sample.ped.x << "," << sample.ped.y << "," << sample.ped.z
		<< " measLateral=" << sample.lateral
		<< " measOrbit=" << sample.orbit
		<< " measVertical=" << sample.vertical;
	gtLog("camera-transition", GT_INFO, line.str());
}

static void gameplayCameraTransitionPushHistory(
	const GameplayCameraTransitionSample& sample) {
	g_cameraTransitionHistory[g_cameraTransitionHistoryHead] = sample;
	g_cameraTransitionHistoryHead = (g_cameraTransitionHistoryHead + 1) % 8;
	if (g_cameraTransitionHistoryCount < 8) ++g_cameraTransitionHistoryCount;
}

static void gameplayCameraTransitionRecorderBeforeMutation(Ped ped, DWORD now,
	bool drawn, GameplayCameraMode rawMode) {
	if (g_cameraTransitionCompleted) return;
	const GameplayCameraTransitionSample current =
		gameplayCameraTransitionCapture(ped, now, drawn, rawMode);
	if (!g_cameraTransitionWeaponStateKnown) {
		g_cameraTransitionWeaponStateKnown = true;
		g_cameraTransitionLastDrawn = drawn;
		gameplayCameraTransitionPushHistory(current);
		return;
	}

	const bool drawEdge = !g_cameraTransitionLastDrawn && drawn;
	if (!g_cameraTransitionRecording && drawEdge) {
		g_cameraTransitionRecording = true;
		g_cameraTransitionEdgeAt = now;
		g_cameraTransitionUntil = now + 1500;
		g_cameraTransitionNextSample = now + 50;
		gtLog("camera-transition", GT_INFO,
			"capture begin source=automatic-weapon-draw preFrames<=8 postMs=1500 sampleMs=50 invasive=0");
		for (int i = 0; i < g_cameraTransitionHistoryCount; ++i) {
			const int first = (g_cameraTransitionHistoryHead -
				g_cameraTransitionHistoryCount + 8) % 8;
			const int index = (first + i) % 8;
			gameplayCameraTransitionLog(
				i == g_cameraTransitionHistoryCount - 1 ? "prechange" : "history",
				g_cameraTransitionHistory[index], g_cameraTransitionEdgeAt);
		}
		gameplayCameraTransitionLog("edge", current, g_cameraTransitionEdgeAt);
		g_cameraTransitionHistoryCount = 0;
	} else if (g_cameraTransitionRecording && now >= g_cameraTransitionNextSample) {
		gameplayCameraTransitionLog("frame", current, g_cameraTransitionEdgeAt);
		g_cameraTransitionNextSample = now + 50;
	}

	if (g_cameraTransitionRecording && now >= g_cameraTransitionUntil) {
		gameplayCameraTransitionLog("final", current, g_cameraTransitionEdgeAt);
		gtLog("camera-transition", GT_INFO,
			"capture complete source=automatic-weapon-draw invasive=0");
		g_cameraTransitionRecording = false;
		g_cameraTransitionCompleted = true;
	} else if (!g_cameraTransitionRecording) {
		gameplayCameraTransitionPushHistory(current);
	}
	g_cameraTransitionLastDrawn = drawn;
}

static GameplayCameraMode gameplayCameraMode(Ped ped) {
	// Aim deliberately wins over mount/vehicle so one aim profile has identical
	// meaning everywhere.  Outside aim, mounted and vehicle follow cameras get
	// independent profiles before the on-foot stance split.
	// Use the physical aim action as well as the camera readback so the profile
	// is selected from the first held frame and cannot oscillate during the
	// camera's transition. Crouched aim has its own low-framing profile.
	const bool crouched = GET_PED_CROUCH_MOVEMENT(ped) || customProneActive();
	if (CAM::IS_AIM_CAM_ACTIVE() || gameplayCameraAimHeld())
		return crouched ? GameplayCameraMode::CrouchedAim : GameplayCameraMode::Aim;
	if (PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE)) return GameplayCameraMode::Vehicle;
	if (PED::IS_PED_ON_MOUNT(ped)) return GameplayCameraMode::Horseback;
	if (customProneActive()) return GameplayCameraMode::Prone;
	// #177: on foot, holstered and weapon-drawn are different Rockstar follow
	// cameras. Classify them apart so each one has its own tunable profile and
	// so the HUD/log stop claiming "STANDING" for a rig that has visibly moved.
	if (gameplayCameraWeaponDrawn(ped))
		return crouched ? GameplayCameraMode::CrouchedArmed
			: GameplayCameraMode::Armed;
	if (crouched) return GameplayCameraMode::Crouched;
	return GameplayCameraMode::Standing;
}

// #178: hold the applied profile until the observed stance has been stable for
// ModeDwellMs. Two profiles with different distances alternating at gait
// frequency is a sinusoidal in/out bump, and the raw-versus-applied flip
// counters below make that diagnosable instead of guessable: a high rawFlips
// with appliedFlips near zero proves stance flicker was the source and that the
// dwell absorbed it, while rawFlips ~= 0 proves the bob is engine-side and this
// module is not the cause.
static GameplayCameraMode gameplayCameraStableMode(GameplayCameraMode raw,
	DWORD now) {
	static GameplayCameraMode candidate = GameplayCameraMode::Standing;
	static GameplayCameraMode lastRaw = GameplayCameraMode::Standing;
	static DWORD candidateSince = 0;
	if (!g_gameplayCameraAppliedModeKnown) {
		g_gameplayCameraAppliedModeKnown = true;
		g_gameplayCameraAppliedMode = raw;
		candidate = raw;
		lastRaw = raw;
		candidateSince = now;
		return raw;
	}
	if (raw != lastRaw) {
		++g_gameplayCameraRawModeFlips;
		lastRaw = raw;
	}
	if (raw != candidate) {
		candidate = raw;
		candidateSince = now;
	}
	if (candidate != g_gameplayCameraAppliedMode &&
		(int)(now - candidateSince) >= g_gameplayCameraModeDwellMs) {
		const GameplayCameraProfile& from =
			g_cameraProfiles[(int)g_gameplayCameraAppliedMode];
		const GameplayCameraProfile& to = g_cameraProfiles[(int)candidate];
		g_gameplayCameraAppliedMode = candidate;
		++g_gameplayCameraAppliedModeFlips;
		std::ostringstream line;
		line << "mode transition from=" << from.label << " to=" << to.label
			<< " dwellMs=" << g_gameplayCameraModeDwellMs
			<< " fromDistance=" << from.distance
			<< " toDistance=" << to.distance
			<< " rawFlips=" << g_gameplayCameraRawModeFlips
			<< " appliedFlips=" << g_gameplayCameraAppliedModeFlips;
		gtLog("camera-editor", GT_INFO, line.str());
	}
	return g_gameplayCameraAppliedMode;
}

static void gameplayCameraSetLow(bool low) {
	// 0x71D... is the only proven live vertical/framing control: Rockstar calls
	// it every frame to move third-person framing closer to ground level.  It is
	// a BOOL, not a scalar, hence the honest LOW/NORMAL UI.
	invoke<Void>(0x71D71E08A7ED5BD7, low ? TRUE : FALSE);
	g_gameplayCameraLowApplied = low;
}

// The three documented third-person framing steps the engine exposes, ordered
// here as closest, second-furthest and furthest. All three are declared in the
// local native header
// (_downloads/RDR2_SDK/SDK/inc/natives.h:717, :718, :719) and named in
// _downloads/natives.json:9147, :9154, :9161 as
// _FORCE_THIRD_PERSON_CLOSE_THIS_FRAME, _FORCE_THIRD_PERSON_CAM_THIS_FRAME and
// _FORCE_THIRD_PERSON_CAM_FAR_THIS_FRAME.  Each is a per-frame force, which is
// how Rockstar's own scripts pin a framing step rather than driving the orbit.
static void gameplayCameraForceThirdPersonLevel(int level) {
	switch (level) {
	case 1:  invoke<Void>(0x8370D34BD2E60B73); break;
	case 2:  invoke<Void>(0x1CFB749AD4317BDE); break;
	default: invoke<Void>(0x718C6ECF5E8CBDD4); break;
	}
}

static bool gameplayCameraViewTransition(DWORD now) {
	static DWORD releaseUntil = 0;
	const Hash nextCamera = joaat("INPUT_NEXT_CAMERA");
	const bool edge =
		PAD::IS_CONTROL_JUST_PRESSED(0, nextCamera) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, nextCamera) ||
		PAD::IS_CONTROL_JUST_PRESSED(2, nextCamera) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, nextCamera);
	if (edge) {
		releaseUntil = now + 500;
		gtLog("camera-editor", GT_INFO,
			"view edge: third-person pin released for Rockstar transition");
	}
	return now < releaseUntil;
}

static void saveGameplayCameraProfiles() {
	for (int i = 0; i < (int)GameplayCameraMode::Count; ++i) {
		const GameplayCameraProfile& p = g_cameraProfiles[i];
		char key[64] = {};
		char value[32] = {};
		sprintf_s(value, "%.3f", p.horizontal);
		sprintf_s(key, "%sShoulderOffset", p.keyPrefix);
		WritePrivateProfileStringA("Camera", key, value, g_iniPath.c_str());
		sprintf_s(value, "%.3f", p.distance);
		sprintf_s(key, "%sDistance", p.keyPrefix);
		WritePrivateProfileStringA("Camera", key, value, g_iniPath.c_str());
		sprintf_s(key, "%sLowCamera", p.keyPrefix);
		WritePrivateProfileStringA("Camera", key, p.low ? "1" : "0",
			g_iniPath.c_str());
	}
}

static void calibrateGameplayCamera(GameplayCameraProfile& p, DWORD now) {
	static DWORD lastNudge = 0;
	if (now - lastNudge >= 16) {
		// Update at frame cadence. The old 0.02-per-60ms repeat was roughly
		// 0.33 units/second and felt glacial while a key was held.
		const float step = (GetAsyncKeyState(VK_SHIFT) & 0x8000) ? 0.005f : 0.05f;
		bool changed = false;
		if (GetAsyncKeyState(VK_NUMPAD4) & 0x8000) { p.horizontal -= step; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD6) & 0x8000) { p.horizontal += step; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD8) & 0x8000) { p.distance -= step; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD2) & 0x8000) { p.distance += step; changed = true; }
		if (changed) {
			lastNudge = now;
			// Live #154/#175 results show that a negative value does not create the
			// opposite shoulder. Do not let the editor enter that inert range.
			if (!std::isfinite(p.horizontal) || p.horizontal < 0.0f)
				p.horizontal = 0.0f;
			if (!std::isfinite(p.distance) || p.distance < 0.0f)
				p.distance = 0.0f;
		}
	}

	static bool lowLatch = false;
	const bool lowDown = (GetAsyncKeyState(VK_NUMPAD7) & 0x8000) != 0;
	if (lowDown && !lowLatch) p.low = !p.low;
	lowLatch = lowDown;

	static bool saveLatch = false;
	const bool saveDown = (GetAsyncKeyState(VK_NUMPAD5) & 0x8000) != 0;
	if (saveDown && !saveLatch) {
		saveGameplayCameraProfiles();
		drawReconText("all camera mode values saved", 0.5f, 0.78f);
	}
	saveLatch = saveDown;

	char hud[256] = {};
	// #177: the label is now the resolved rig, so ARMED and CROUCHED ARMED read
	// differently from STANDING and CROUCHED instead of all claiming "standing".
	sprintf_s(hud,
		"CAMERA CALIBRATION  %s   horizontal %.3f   distance %.3f   height %s   side: game-owned",
		p.label, p.horizontal, p.distance, p.low ? "LOW" : "NORMAL");
	drawReconText(hud, 0.5f, 0.83f);
	drawReconText("numpad 4/6 horizontal   8/2 distance   7 LOW/NORMAL   shift fine   5 save",
		0.5f, 0.86f);
}

static void updateGameplayCameraEditor(Ped ped, DWORD now, bool mission) {
	if (!g_gameplayCameraConfigLoaded) loadGameplayCameraConfig();
	static bool bootLogged = false;
	static DWORD nextHeartbeat = 0;
	static bool developmentStateKnown = false;
	static bool lastDevelopmentState = false;
	const bool editorActive = developmentModeActive();
	if (!bootLogged) {
		bootLogged = true;
		std::ostringstream line;
		line << "session build="
			<< (GameplayTweaksBuild::Development ? "development" : "release")
			<< " runtimeDev=" << (editorActive ? 1 : 0)
			<< " enabled=" << (g_gameplayCameraEnabled ? 1 : 0)
			<< " defaultOwner="
			<< (g_fortificationCalibrationOwnsNumpad ? "fortification" : "camera");
		gtLog("camera-editor", GT_INFO, line.str());
	}
	if (!developmentStateKnown || editorActive != lastDevelopmentState) {
		std::ostringstream line;
		line << "developer mode observed enabled=" << (editorActive ? 1 : 0)
			<< " owner="
			<< (g_fortificationCalibrationOwnsNumpad ? "fortification" : "camera");
		gtLog("camera-editor", GT_INFO, line.str());
		developmentStateKnown = true;
		lastDevelopmentState = editorActive;
	}
	if (editorActive) updateGameplayCameraNumpadOwnership();
	if (!nextHeartbeat || now >= nextHeartbeat) {
		nextHeartbeat = now + 3000;
		std::ostringstream line;
		line << "heartbeat build="
			<< (GameplayTweaksBuild::Development ? "development" : "release")
			<< " runtimeDev=" << (developmentModeActive() ? 1 : 0)
			<< " owner="
			<< (g_fortificationCalibrationOwnsNumpad ? "fortification" : "camera")
			<< " enabled=" << (g_gameplayCameraEnabled ? 1 : 0)
			<< " ped=" << (ped ? 1 : 0)
			<< " mission=" << (mission ? 1 : 0)
			<< " cinematic=" << (CAM::IS_CINEMATIC_CAM_RENDERING() ? 1 : 0)
			<< " gameplay=" << (CAM::IS_GAMEPLAY_CAM_RENDERING() ? 1 : 0)
			<< " firstPerson=" << (gameplayCameraFirstPerson() ? 1 : 0)
			// #178: the old heartbeat named no camera state at all, so a silent
			// log could not distinguish "module idle" from "module running and
			// fighting the stance predicate". These two counters are the cheap
			// pairing that makes the difference visible on one line.
			<< " rawFlips=" << g_gameplayCameraRawModeFlips
			<< " appliedFlips=" << g_gameplayCameraAppliedModeFlips
			<< " mode=" << (g_gameplayCameraAppliedModeKnown
				? g_cameraProfiles[(int)g_gameplayCameraAppliedMode].label
				: "unknown")
			<< " editor=" << ((editorActive &&
				!g_fortificationCalibrationOwnsNumpad) ? "active" : "inactive");
		gtLog("camera-editor", GT_INFO, line.str());
	}
	if (!g_gameplayCameraEnabled || !ped || mission ||
		CAM::IS_CINEMATIC_CAM_RENDERING() || !CAM::IS_GAMEPLAY_CAM_RENDERING() ||
		gameplayCameraFirstPerson()) {
		if (g_gameplayCameraLowApplied) gameplayCameraSetLow(false);
		return;
	}

	const bool weaponDrawn = gameplayCameraWeaponDrawn(ped);
	const GameplayCameraMode rawMode = gameplayCameraMode(ped);
	// #269: this call is deliberately before stable-mode bookkeeping, editor
	// calibration, LOW framing, profile submission, or zoom forcing. The cached
	// prior frame and edge sample therefore cannot be contaminated by this
	// frame's camera writes.
	gameplayCameraTransitionRecorderBeforeMutation(ped, now, weaponDrawn, rawMode);
	const GameplayCameraMode mode = gameplayCameraStableMode(rawMode, now);
	GameplayCameraProfile& profile = g_cameraProfiles[(int)mode];
	// While the shared developer mode is on, camera calibration is the default
	// keypad owner; Numpad 0 swaps to the gold-core editor and the next Numpad 0
	// swaps straight back. With developer mode off, no camera authoring input is
	// read and no profile can be persisted.
	if (editorActive && !g_fortificationCalibrationOwnsNumpad)
		calibrateGameplayCamera(profile, now);

	// The side belongs to Rockstar. The module submits a nonnegative magnitude
	// and never negates it, because a negative horizontalOffset does not mirror
	// the camera - see the long note on gameplayCameraShoulderInput. The press
	// is observed only so the log can prove whether the engine's side moved.
	const GameplayCameraShoulderInput shoulderInput =
		gameplayCameraShoulderInput(now);
	static DWORD nativeShoulderReadbackAt = 0;
	static float nativeShoulderBefore = 0.0f;
	static bool nativeShoulderReadbackPending = false;
	const float submittedHorizontal = profile.horizontal;
	if (shoulderInput != GameplayCameraShoulderInput::None) {
		nativeShoulderBefore = gameplayCameraRenderedLateral(ped);
		nativeShoulderReadbackAt = now + 650;
		nativeShoulderReadbackPending = true;
		Hash currentWeapon = 0;
		WEAPON::GET_CURRENT_PED_WEAPON(ped, &currentWeapon, TRUE, 0, FALSE);
		std::ostringstream line;
		line << "shoulder edge source="
			<< (shoulderInput == GameplayCameraShoulderInput::KeyboardX
				? "keyboard-x" : "mapped-action")
			<< " profile=" << profile.label
			<< " aimHeld=" << (gameplayCameraAimHeld() ? 1 : 0)
			<< " weapon=0x" << std::hex << (unsigned int)currentWeapon << std::dec
			<< " drawn=" << (weaponDrawn ? 1 : 0)
			<< " holsterTransition="
			<< (invoke<BOOL>(0x2387D6E9C6B478AA, ped) ? 1 : 0)
			<< " sideOwner=rockstar"
			<< " beforeLateral=" << nativeShoulderBefore
			<< " appliedHorizontal=" << submittedHorizontal;
		gtLog("camera-editor", GT_INFO, line.str());
	}
	if (nativeShoulderReadbackPending && now >= nativeShoulderReadbackAt) {
		// Distinguishes the three outcomes that previous attempts could not tell
		// apart: the engine crossed sides (working), the engine stayed put
		// (Rockstar has no shoulder side in this state), or the camera settled
		// near centre (the offset collapsed).
		const float after = gameplayCameraRenderedLateral(ped);
		const bool crossed = nativeShoulderBefore * after < 0.0f;
		const bool centered = fabsf(after) < 0.12f;
		const bool unmoved = !crossed &&
			fabsf(after - nativeShoulderBefore) < 0.05f;
		std::ostringstream line;
		line << "shoulder settle beforeLateral=" << nativeShoulderBefore
			<< " afterLateral=" << after
			<< " crossed=" << (crossed ? 1 : 0)
			<< " centered=" << (centered ? 1 : 0)
			<< " unmoved=" << (unmoved ? 1 : 0)
			<< " verdict="
			<< (crossed ? "engine-side-changed"
				: (centered ? "collapsed-to-centre"
					: (unmoved ? "engine-ignored-press" : "partial")));
		gtLog("camera-editor", crossed ? GT_INFO : GT_WARN, line.str());
		nativeShoulderReadbackPending = false;
	}

	// #178 / #177 telemetry. Reads only, bounded cadence, and it names the raw
	// stance as well as the applied one so a disagreement is visible rather
	// than inferred. Crouched and prone sample faster because that is the exact
	// state whose oscillation is under investigation.
	static DWORD nextSample = 0;
	const bool crouchFamily = mode == GameplayCameraMode::Crouched ||
		mode == GameplayCameraMode::CrouchedArmed ||
		mode == GameplayCameraMode::CrouchedAim ||
		mode == GameplayCameraMode::Prone;
	const int sampleMs = crouchFamily
		? (std::min)(g_gameplayCameraSampleMs, 100)
		: g_gameplayCameraSampleMs;
	// SampleIntervalMs=0 means off, never "every frame".
	if (g_gameplayCameraSampleMs > 0 &&
		(!nextSample || (int)(now - nextSample) >= 0)) {
		nextSample = now + (DWORD)(std::max)(1, sampleMs);
		float lateral = 0.0f, orbit = 0.0f, vertical = 0.0f;
		gameplayCameraRenderedFrame(ped, &lateral, &orbit, &vertical);
		std::ostringstream line;
		line << "sample mode=" << profile.label
			<< " raw=" << g_cameraProfiles[(int)rawMode].label
			<< " crouch=" << (GET_PED_CROUCH_MOVEMENT(ped) ? 1 : 0)
			<< " drawn=" << (weaponDrawn ? 1 : 0)
			<< " aimCam=" << (CAM::IS_AIM_CAM_ACTIVE() ? 1 : 0)
			<< " cfgHorizontal=" << profile.horizontal
			<< " sentHorizontal=" << submittedHorizontal
			<< " sentDistance=" << profile.distance
			<< " low=" << (profile.low ? 1 : 0)
			<< " measLateral=" << lateral
			<< " measOrbit=" << orbit
			<< " measVertical=" << vertical
			<< " rawFlips=" << g_gameplayCameraRawModeFlips
			<< " appliedFlips=" << g_gameplayCameraAppliedModeFlips;
		gtLog("camera-editor", GT_INFO, line.str());
	}

	gameplayCameraSetLow(profile.low);
	// These are the exact named arguments in the local native database:
	// speed, respectHorizontalOffset, horizontalOffset,
	// respectDistance, distance.
	//
	// #175: the 500 ms "release" window that used to pass FALSE for
	// respectHorizontalOffset during an aim shoulder swap is gone. Dropping the
	// override mid-blend and then re-asserting it is itself a discontinuity, and
	// re-asserting at the end of Rockstar's transition matches the reported
	// "after it's almost done moving there's this noticeable jump". The offset
	// is now asserted continuously at one constant magnitude, so the only thing
	// moving during a swap is Rockstar's own side blend.
	invoke<Void>(0x066167C63111D8CF, g_gameplayCameraBlendSpeed,
		TRUE, submittedHorizontal,
		TRUE, profile.distance);

	// Optional close/first-person-only view-cycle policy.  On foot it collapses
	// the three third-person steps onto the closest one, so the view key only
	// ever picks between that framing and first person.
	if (g_gameplayCameraLockZoom &&
		(mode == GameplayCameraMode::Standing ||
		 mode == GameplayCameraMode::Crouched ||
		 mode == GameplayCameraMode::Armed ||
		 mode == GameplayCameraMode::CrouchedArmed ||
		 mode == GameplayCameraMode::Prone ||
		 mode == GameplayCameraMode::Aim ||
		 mode == GameplayCameraMode::CrouchedAim))
		gameplayCameraForceThirdPersonLevel(0);

	// #128: same policy for mounted and vehicle follow cameras, which #8 left on the
	// stock four-view cycle.  The mounted rig sits further out than the on-foot
	// one, so which of the three steps gets pinned is configurable rather than
	// hard-coded to "closest"; the default matches the on-foot behaviour Lexer
	// reported as working.
	//
	// No opened Story call site proves these framing natives on a horse.
	// natives.json documents all three as frame-scoped third-person camera
	// positions with no on-foot-only qualifier; that supports this bounded
	// mounted runtime candidate, not a claim that horseback behavior is proven.
	// Lexer's visible view-cycle test remains the required postcondition.
	//
	// Aim still wins over Horseback in gameplayCameraMode(), so mounted aiming
	// keeps the shared aim profile exactly as it does on foot.
	if (g_gameplayCameraLockZoomMounted &&
		(mode == GameplayCameraMode::Horseback || mode == GameplayCameraMode::Vehicle) &&
		!gameplayCameraViewTransition(now))
		gameplayCameraForceThirdPersonLevel(g_gameplayCameraMountedZoomLevel);
}
