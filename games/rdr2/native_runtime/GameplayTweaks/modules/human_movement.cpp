// GitHub #144: two-speed on-foot movement for the human player.
//
// Rockstar's locomotion graph owns the actual walk/sprint animation transition.
// This controller only narrows the allowed blend ceiling and applies the
// configured rate scalar. It must never force a motion state or collapse
// min/max/desired blend every update: the first live build did exactly that for
// 2,867 frames and produced catastrophic graph stutter/acceleration.

enum class HumanMovementGait {
	Unavailable,
	Idle,
	Walk,
	Sneak,
	Sprint,
};

static bool g_humanMovementEnabled = true;
static constexpr float kHumanMovementRateMinimum = 0.10f;
static constexpr float kHumanMovementRateMaximum = 1.15f;
static float g_humanMovementRequestedWalkRate = 1.0f;
static float g_humanMovementRequestedSneakRate = 0.70f;
static float g_humanMovementRequestedSprintRate = 1.0f;
static float g_humanMovementWalkRate = 1.0f;
static float g_humanMovementSneakRate = 0.70f;
static float g_humanMovementSprintRate = 1.0f;
static DWORD g_humanMovementConfigAt = 0;
static DWORD g_humanMovementHeartbeatAt = 0;
static Ped g_humanMovementOwner = 0;
static HumanMovementGait g_humanMovementGait = HumanMovementGait::Unavailable;
static unsigned g_humanMovementAppliedFrames = 0;
static bool g_humanMovementReleasePending = false;
static unsigned g_humanMovementReleaseWalkFrames = 0;
static DWORD g_humanMovementReleaseAt = 0;
static DWORD g_humanMovementReleaseReadbackAt = 0;
static bool g_humanMovementReleaseFirstFramePending = false;
static unsigned g_humanMovementSneakWalkFrames = 0;
static DWORD g_humanMovementSneakReadbackAt = 0;

static float humanMovementClamp(float value, float minimum, float maximum) {
	return (std::max)(minimum, (std::min)(maximum, value));
}

static const char* humanMovementGaitName(HumanMovementGait gait) {
	switch (gait) {
	case HumanMovementGait::Idle: return "idle";
	case HumanMovementGait::Walk: return "walk";
	case HumanMovementGait::Sneak: return "sneak";
	case HumanMovementGait::Sprint: return "sprint";
	default: return "unavailable";
	}
}

static void loadHumanMovementSettings(DWORD now) {
	if (g_humanMovementConfigAt && now - g_humanMovementConfigAt < 2000) return;
	g_humanMovementConfigAt = now;
	g_humanMovementEnabled = readB("HumanMovement", "Enabled", true);
	// The RDR2 SDK and natives.json both document 0.0..1.15 for hash
	// 0x085BF80FA50A39D1. This user-facing controller keeps 0.10 as its practical
	// floor and never treats the scalar as metres per second.
	g_humanMovementRequestedWalkRate =
		readF("HumanMovement", "WalkRateScalar", 1.0f);
	g_humanMovementRequestedSneakRate =
		readF("HumanMovement", "SneakRateScalar", 0.70f);
	g_humanMovementRequestedSprintRate =
		readF("HumanMovement", "SprintRateScalar", 1.00f);
	g_humanMovementWalkRate = humanMovementClamp(
		g_humanMovementRequestedWalkRate,
		kHumanMovementRateMinimum, kHumanMovementRateMaximum);
	g_humanMovementSneakRate = humanMovementClamp(
		g_humanMovementRequestedSneakRate,
		kHumanMovementRateMinimum, kHumanMovementRateMaximum);
	g_humanMovementSprintRate = humanMovementClamp(
		g_humanMovementRequestedSprintRate,
		kHumanMovementRateMinimum, kHumanMovementRateMaximum);
}

static bool humanMovementSprintHeld() {
	const Hash sprint = joaat("INPUT_SPRINT");
	return (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0 ||
		PAD::IS_CONTROL_PRESSED(0, sprint) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, sprint) ||
		PAD::IS_CONTROL_PRESSED(2, sprint) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, sprint);
}

static void humanMovementBlockSprintControl() {
	// A walk frame (or any crouched frame) consumes Rockstar's Sprint action so
	// its run-toggle/cycle cannot survive Shift release. While Shift is held and
	// Arthur is standing, the action remains enabled and Rockstar starts its own
	// sanctioned sprint transition.
	const Hash sprint = joaat("INPUT_SPRINT");
	PAD::DISABLE_CONTROL_ACTION(0, sprint, TRUE);
	PAD::DISABLE_CONTROL_ACTION(2, sprint, TRUE);
}

static bool humanMovementHasInput() {
	const float lateral = CONTROL_AXIS(0, joaat("INPUT_MOVE_LR"));
	const float forward = CONTROL_AXIS(0, joaat("INPUT_MOVE_UD"));
	return lateral * lateral + forward * forward >= 0.01f;
}

static void restoreHumanMovementDefaults(Ped ped) {
	if (!ped || !ENTITY::DOES_ENTITY_EXIST(ped)) return;
	PED::SET_PED_MOVE_RATE_OVERRIDE(ped, 1.0f);
	PED::SET_PED_MIN_MOVE_BLEND_RATIO(ped, 0.0f);
	PED::SET_PED_MAX_MOVE_BLEND_RATIO(ped, 3.0f);
}

// `callerUnavailable` is only a hint. The first installed #144 runtime produced
// `unavailable=1 frames=0` for the entire 8.5-minute session even while Arthur
// visibly ran. Trusting that collapsed boolean meant none of the gait natives
// executed. Corroborate it with authoritative live ownership below, and report
// every term separately so another false gate can never be mistaken for a
// movement-native failure.
static void updateHumanMovementRework(Player player, Ped ped, DWORD now,
	bool callerUnavailable) {
	loadHumanMovementSettings(now);
	if (ped != g_humanMovementOwner) {
		restoreHumanMovementDefaults(g_humanMovementOwner);
		g_humanMovementOwner = ped;
		g_humanMovementGait = HumanMovementGait::Unavailable;
		g_humanMovementReleasePending = false;
		g_humanMovementReleaseWalkFrames = 0;
		g_humanMovementReleaseFirstFramePending = false;
		g_humanMovementSneakWalkFrames = 0;
	}

	// Player is an index, not an entity handle: Story's valid local player is 0.
	// The previous null-style player test therefore made this true every frame.
	const bool invalidPed = !ped || !ENTITY::DOES_ENTITY_EXIST(ped);
	const bool dead = !invalidPed && ENTITY::IS_ENTITY_DEAD(ped);
	const bool faded = SCREEN_FADED_OUT();
	const bool controlOff = !PLAYER_CONTROL_ON(player);
	const bool customProne = customProneActive();
	const bool customClimb = g_climbState != ClimbState::Grounded;
	const bool customDodge = g_dodgeRollStage != DodgeRollStage::Idle;
	const bool customMenu = g_customCraftingMenuOpen || g_settingsMenuOpen;
	const bool callerCorroborated = callerUnavailable &&
		(faded || controlOff || customMenu || customProne || customClimb || customDodge);
	const bool mount = !invalidPed && IS_PED_ON_MOUNT(ped);
	const bool swimming = !invalidPed && IS_PED_SWIMMING(ped);
	const bool climbing = !invalidPed && (PED::IS_PED_CLIMBING(ped) ||
		PED::_IS_PED_CLIMBING_LADDER(ped));
	const bool falling = !invalidPed && IS_PED_FALLING(ped);
	const bool ragdoll = !invalidPed && IS_PED_RAGDOLL(ped);
	const bool gettingUp = !invalidPed && TASK::IS_PED_GETTING_UP(ped);
	const bool nativeProne = !invalidPed && PED::IS_PED_PRONE(ped);
	const bool nonLocomotion = invalidPed || dead || faded || controlOff ||
		customMenu || customProne || customClimb || customDodge || mount ||
		swimming || climbing || falling || ragdoll || gettingUp || nativeProne;
	if (!g_humanMovementEnabled || nonLocomotion) {
		if (g_humanMovementGait != HumanMovementGait::Unavailable)
			restoreHumanMovementDefaults(ped);
		g_humanMovementGait = HumanMovementGait::Unavailable;
		g_humanMovementReleasePending = false;
		g_humanMovementReleaseWalkFrames = 0;
		g_humanMovementReleaseFirstFramePending = false;
		g_humanMovementSneakWalkFrames = 0;
		if (now - g_humanMovementHeartbeatAt >= 5000) {
			g_humanMovementHeartbeatAt = now;
			GtLogStream("human-movement", GT_INFO)
				<< "idle enabled=" << (g_humanMovementEnabled ? 1 : 0)
				<< " caller=" << (callerUnavailable ? 1 : 0)
				<< " corroborated=" << (callerCorroborated ? 1 : 0)
				<< " invalid=" << (invalidPed ? 1 : 0)
				<< " dead=" << (dead ? 1 : 0)
				<< " fade=" << (faded ? 1 : 0)
				<< " controlOff=" << (controlOff ? 1 : 0)
				<< " menu=" << (customMenu ? 1 : 0)
				<< " prone=" << (customProne ? 1 : 0)
				<< " climb=" << (customClimb ? 1 : 0)
				<< " dodge=" << (customDodge ? 1 : 0)
				<< " mount=" << (mount ? 1 : 0)
				<< " swim=" << (swimming ? 1 : 0)
				<< " nativeClimb=" << (climbing ? 1 : 0)
				<< " fall=" << (falling ? 1 : 0)
				<< " ragdoll=" << (ragdoll ? 1 : 0)
				<< " getUp=" << (gettingUp ? 1 : 0)
				<< " nativeProne=" << (nativeProne ? 1 : 0)
				<< " frames=" << g_humanMovementAppliedFrames << "\n";
		}
		return;
	}

	const bool moving = humanMovementHasInput();
	const bool sneaking = PED::GET_PED_STEALTH_MOVEMENT(ped) ||
		GET_PED_CROUCH_MOVEMENT(ped);
	const bool sprintHeld = humanMovementSprintHeld();
	const bool sprintReleased = g_humanMovementGait == HumanMovementGait::Sprint &&
		!sprintHeld;
	if (sprintReleased) {
		g_humanMovementReleasePending = true;
		g_humanMovementReleaseWalkFrames = 0;
		g_humanMovementReleaseAt = now;
		g_humanMovementReleaseFirstFramePending = true;
		GtLogStream("human-movement", GT_INFO)
			<< "sprint release edge; walk ceiling applied\n";
	}
	// A release owns the short walk-confirmation window. This prevents Rockstar's
	// run toggle from surviving the key-up edge. A new sprint can start after
	// three consecutive live readbacks show that the previous sprint ended.
	const bool sprintAllowed = sprintHeld && !sneaking &&
		!g_humanMovementReleasePending;
	const bool sprintBlocked = !sprintAllowed;
	if (sprintBlocked) humanMovementBlockSprintControl();
	HumanMovementGait next = HumanMovementGait::Idle;
	float maximumBlend = 1.0f;
	float requestedRate = g_humanMovementRequestedWalkRate;
	float moveRate = g_humanMovementWalkRate;

	// Sneak owns this branch even while Shift is held. Sprint input stays blocked
	// and the walk ceiling prevents the crouched locomotion graph entering run.
	if (moving && sneaking) {
		next = HumanMovementGait::Sneak;
		requestedRate = g_humanMovementRequestedSneakRate;
		moveRate = g_humanMovementSneakRate;
	} else if (moving && sprintAllowed) {
		next = HumanMovementGait::Sprint;
		maximumBlend = 3.0f;
		requestedRate = g_humanMovementRequestedSprintRate;
		moveRate = g_humanMovementSprintRate;
	} else if (moving) {
		next = HumanMovementGait::Walk;
	}
	const bool nativeRangeClamped =
		g_humanMovementRequestedWalkRate != g_humanMovementWalkRate ||
		g_humanMovementRequestedSneakRate != g_humanMovementSneakRate ||
		g_humanMovementRequestedSprintRate != g_humanMovementSprintRate ||
		requestedRate < kHumanMovementRateMinimum ||
		requestedRate > kHumanMovementRateMaximum;

	// Both setters are frame-scoped controller inputs. SET_PED_MAX_MOVE_BLEND_RATIO
	// remains a ceiling with the untouched engine-default minimum of zero; it is
	// not paired with desired-blend or FORCE_PED_MOTION_STATE. MOVE_RATE is a
	// relative scalar for the graph-selected gait, not an absolute world speed.
	// These are the only per-frame locomotion writes.
	PED::SET_PED_MOVE_RATE_OVERRIDE(ped, moveRate);
	PED::SET_PED_MAX_MOVE_BLEND_RATIO(ped, maximumBlend);
	++g_humanMovementAppliedFrames;

	const bool readbackRunning = IS_PED_RUNNING(ped);
	const bool readbackSprinting = IS_PED_SPRINTING(ped);
	const float readbackBlend = GET_DESIRED_MOVE_BLEND(ped);
	const float readbackSpeed = ENTITY_SPEED(ped);
	if (g_humanMovementReleaseFirstFramePending) {
		g_humanMovementReleaseFirstFramePending = false;
		GtLogStream("human-movement",
			(!readbackRunning && !readbackSprinting && readbackBlend <= 1.05f)
				? GT_INFO : GT_WARN)
			<< "release first owned frame sprintBlocked="
			<< (sprintBlocked ? 1 : 0)
			<< " maximumBlend=" << maximumBlend
			<< " running=" << (readbackRunning ? 1 : 0)
			<< " sprinting=" << (readbackSprinting ? 1 : 0)
			<< " desiredBlend=" << readbackBlend
			<< " speed=" << readbackSpeed << "\n";
	}
	if (g_humanMovementReleasePending && moving) {
		const bool walkReadback = !readbackRunning && !readbackSprinting &&
			readbackBlend <= 1.05f;
		g_humanMovementReleaseWalkFrames = walkReadback ?
			g_humanMovementReleaseWalkFrames + 1 : 0;
		if (!walkReadback && now - g_humanMovementReleaseReadbackAt >= 250) {
			g_humanMovementReleaseReadbackAt = now;
			GtLogStream("human-movement", GT_WARN)
				<< "engine release transition still active running="
				<< (readbackRunning ? 1 : 0)
				<< " sprinting=" << (readbackSprinting ? 1 : 0)
				<< " desiredBlend=" << readbackBlend
				<< " ageMs=" << (now - g_humanMovementReleaseAt) << "\n";
		}
		if (g_humanMovementReleaseWalkFrames >= 3) {
			GtLogStream("human-movement", GT_INFO)
				<< "release confirmed walk running=0 sprinting=0 desiredBlend="
				<< readbackBlend << " ageMs=" << (now - g_humanMovementReleaseAt)
				<< "\n";
			g_humanMovementReleasePending = false;
			g_humanMovementReleaseWalkFrames = 0;
		}
	}
	if (moving && sneaking) {
		const bool sneakWalkReadback = !readbackRunning && !readbackSprinting &&
			readbackBlend <= 1.05f;
		g_humanMovementSneakWalkFrames = sneakWalkReadback ?
			g_humanMovementSneakWalkFrames + 1 : 0;
		if (!sneakWalkReadback && now - g_humanMovementSneakReadbackAt >= 250) {
			g_humanMovementSneakReadbackAt = now;
			GtLogStream("human-movement", GT_WARN)
				<< "crouch-walk rejected sprintBlocked="
				<< (sprintBlocked ? 1 : 0)
				<< " shift=" << (sprintHeld ? 1 : 0)
				<< " running=" << (readbackRunning ? 1 : 0)
				<< " sprinting=" << (readbackSprinting ? 1 : 0)
				<< " desiredBlend=" << readbackBlend
				<< " speed=" << readbackSpeed << "\n";
		}
	} else {
		g_humanMovementSneakWalkFrames = 0;
	}

	if (next != g_humanMovementGait) {
		GtLogStream("human-movement", GT_INFO)
			<< humanMovementGaitName(g_humanMovementGait) << " -> "
			<< humanMovementGaitName(next)
			<< " shift=" << (sprintHeld ? 1 : 0)
			<< " sprintBlocked=" << (sprintBlocked ? 1 : 0)
			<< " sneak=" << (sneaking ? 1 : 0)
			<< " maximumBlend=" << maximumBlend
			<< " requestedRate=" << requestedRate
			<< " rate=" << moveRate
			<< " nativeRangeClamped=" << (nativeRangeClamped ? 1 : 0) << "\n";
		g_humanMovementGait = next;
	}
	if (now - g_humanMovementHeartbeatAt >= 5000) {
		g_humanMovementHeartbeatAt = now;
		GtLogStream("human-movement", GT_INFO)
			<< "heartbeat gait=" << humanMovementGaitName(g_humanMovementGait)
			<< " moving=" << (moving ? 1 : 0)
			<< " shift=" << (sprintHeld ? 1 : 0)
			<< " sneak=" << (sneaking ? 1 : 0)
			<< " maximumBlend=" << maximumBlend
			<< " requestedRate=" << requestedRate
			<< " rate=" << moveRate
			<< " nativeRangeClamped=" << (nativeRangeClamped ? 1 : 0)
			<< " actualRun=" << (readbackRunning ? 1 : 0)
			<< " actualSprint=" << (readbackSprinting ? 1 : 0)
			<< " desiredBlend=" << readbackBlend
			<< " sneakWalkFrames=" << g_humanMovementSneakWalkFrames
			<< " releasePending=" << (g_humanMovementReleasePending ? 1 : 0)
			<< " speed=" << readbackSpeed
			<< " frames=" << g_humanMovementAppliedFrames << "\n";
	}
}
