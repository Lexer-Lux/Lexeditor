// GameplayTweaks feature module: Reusable stamina drain, prone locomotion, free climbing, and core-XP enforcement.
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


// ---- Reusable net stamina drain -----------------------------------------
// The game continuously refills the outer stamina bar from the stamina core,
// so a plain "subtract N per second" call loses the race and the bar never
// moves (the core just thumps). Hold a target that only ever decreases and pull
// the bar down to it each frame; the regen is cancelled as a side effect and
// the configured per-second value becomes a true NET rate.
//
// Any future stamina-draining activity should use this rather than re-deriving
// it:  begin() when the activity starts, tick() every frame, reset() on exit.
struct StaminaDrain {
	float target = -1.0f;
	void begin(Player player) { target = GET_STAMINA_BAR(player); }
	void reset() { target = -1.0f; }
	float tick(Player player, Ped ped, float perSecond, float dt) {
		if (target < 0.0f) begin(player);
		target = (std::max)(0.0f, target - perSecond * dt);
		const float current = GET_STAMINA_BAR(player);
		// _CHANGE_PED_STAMINA accepts negatives; RESTORE_PLAYER_STAMINA does not.
		if (current > target) invoke<BOOL>(0xC3D4B754C0E86B9E, ped, target - current);
		return target;
	}
};

// Owns a net stamina rate instead of multiplying Rockstar's simultaneous
// drain/recovery. Moving the target first and correcting the live meter every
// frame prevents the two systems from cancelling each other.
struct StaminaRateController {
	Ped owner = 0;
	float target = -1.0f;
	void reset() { owner = 0; target = -1.0f; }
	void tick(Ped ped, float rate, float dt) {
		if (!ped) { reset(); return; }
		const float maxStamina = GET_PED_MAX_STAMINA(ped);
		const float current = GET_PED_STAMINA(ped);
		if (maxStamina <= 0.0f) { reset(); return; }
		if (owner != ped || target < 0.0f || fabsf(current - target) > maxStamina * 0.35f) {
			owner = ped;
			target = current;
		}
		target = (std::max)(0.0f, (std::min)(maxStamina, target + rate * dt));
		const float delta = target - GET_PED_STAMINA(ped);
		if (fabsf(delta) > 0.005f)
			invoke<BOOL>(0xC3D4B754C0E86B9E, ped, delta);
	}
	// One-off spends (a dodge roll, a climbing leap) MUST go through here while
	// this controller owns the ped. tick() drives the live bar back onto `target`
	// every frame, so a bare _CHANGE_PED_STAMINA(-cost) leaves target untouched
	// and the very next tick computes delta = target - current = +cost and hands
	// the whole payment straight back. Same-frame readback still shows the drop,
	// so that failure is indistinguishable from a charge that worked - which is
	// exactly the #173 report. Moving the target with the spend makes this
	// controller the single owner of the net result.
	float spend(Ped ped, float amount, BOOL* accepted = nullptr) {
		if (accepted) *accepted = FALSE;
		if (!ped || !(amount > 0.0f)) return 0.0f;
		const float before = GET_PED_STAMINA(ped);
		const float applied = (std::min)(amount, (std::max)(0.0f, before));
		if (!(applied > 0.0f)) return 0.0f;
		const BOOL ok = invoke<BOOL>(0xC3D4B754C0E86B9E, ped, -applied);
		if (accepted) *accepted = ok;
		if (owner == ped && target >= 0.0f)
			target = (std::max)(0.0f, target - applied);
		return applied;
	}
};

static StaminaRateController g_playerStaminaRate;
static StaminaRateController g_horseStaminaRate;

// #71: one exact-road sample feeds player and horse stamina drain. Polling the path
// network once per actor every 100 ms is prompt at a road edge without making
// an expensive native query every frame. Two consecutive changed samples must
// agree before the stable state flips, so one noisy boundary result cannot
// alternate the locomotion scalar or stamina rate.
struct MovementRoadSample {
	Ped owner = 0;
	bool initialized = false;
	bool raw = false;
	bool stable = false;
	bool candidate = false;
	unsigned candidateCount = 0;
	DWORD sampleAt = 0;
	DWORD heartbeatAt = 0;
};

static MovementRoadSample g_playerRoadSample;
static MovementRoadSample g_horseRoadSample;

static bool movementRoadOnRoad(Ped ped, DWORD now,
	MovementRoadSample& sample, const char* actor) {
	if (!ped || !ENTITY::DOES_ENTITY_EXIST(ped)) {
		sample = {};
		return false;
	}
	if (sample.owner != ped) {
		sample = {};
		sample.owner = ped;
	}
	if (!sample.initialized || now - sample.sampleAt >= 100) {
		sample.sampleAt = now;
		const Vector3 position = ENTITY_COORDS(ped);
		const bool raw = invoke<BOOL>(0x125BF4ABFC536B09,
			position.x, position.y, position.z, 0) != FALSE; // IS_POINT_ON_ROAD
		sample.raw = raw;
		if (!sample.initialized) {
			sample.initialized = true;
			sample.stable = raw;
			sample.candidate = raw;
			sample.candidateCount = 0;
			GtLogStream("road-travel", GT_INFO)
				<< actor << " initial raw=" << (raw ? 1 : 0)
				<< " stable=" << (sample.stable ? 1 : 0) << "\n";
		} else if (raw == sample.stable) {
			sample.candidate = raw;
			sample.candidateCount = 0;
		} else {
			if (sample.candidate != raw) {
				sample.candidate = raw;
				sample.candidateCount = 1;
			} else {
				++sample.candidateCount;
			}
			if (sample.candidateCount >= 2) {
				sample.stable = raw;
				sample.candidateCount = 0;
				GtLogStream("road-travel", GT_INFO)
					<< actor << " transition raw=" << (raw ? 1 : 0)
					<< " stable=" << (sample.stable ? 1 : 0) << "\n";
			}
		}
	}
	if (now - sample.heartbeatAt >= 5000) {
		sample.heartbeatAt = now;
		GtLogStream("road-travel", GT_INFO)
			<< actor << " heartbeat raw=" << (sample.raw ? 1 : 0)
			<< " stable=" << (sample.stable ? 1 : 0)
			<< " pendingSamples=" << sample.candidateCount << "\n";
	}
	return sample.stable;
}

static bool movementPlayerOnRoad(Ped ped, DWORD now) {
	return movementRoadOnRoad(ped, now, g_playerRoadSample, "human");
}

static bool movementHorseOnRoad(Ped horse, DWORD now) {
	return movementRoadOnRoad(horse, now, g_horseRoadSample, "horse");
}

static float movementStaminaRoadAdjusted(Ped ped, float rate,
	float roadDrainMultiplier, bool horse) {
	// Swimming and every non-draining mode retain their exact configured rate.
	// The integrator clamps the hot-reloaded setting to [0, 1]. Clamp here too
	// so this module remains safe if another config path ever supplies it.
	if (rate >= 0.0f || IS_PED_SWIMMING(ped))
		return rate;
	const DWORD now = GetTickCount();
	const bool onRoad = horse ? movementHorseOnRoad(ped, now) :
		movementPlayerOnRoad(ped, now);
	if (!onRoad)
		return rate;
	const float multiplier = (std::max)(0.0f,
		(std::min)(1.0f, roadDrainMultiplier));
	return rate * multiplier;
}

// #11: the mode NAME as well as the rate, so the on-screen readout and the rate
// can never disagree about which band you are in.
static const char* playerMovementStaminaMode(Ped ped) {
	if (IS_PED_SWIMMING(ped)) return "Swimming";
	if (IS_PED_SPRINTING(ped)) return "Sprinting";
	if (IS_PED_RUNNING(ped) || GET_DESIRED_MOVE_BLEND(ped) >= 1.6f) return "Jogging";
	if (ENTITY_SPEED(ped) >= 0.12f || PED::GET_PED_STEALTH_MOVEMENT(ped)) return "Walking/Sneaking";
	return "Standing";
}

static float playerMovementStaminaRate(Ped ped) {
	if (IS_PED_SWIMMING(ped)) return g_humanSwimRate;
	if (IS_PED_SPRINTING(ped))
		return movementStaminaRoadAdjusted(ped, g_humanSprintRate,
			g_humanRoadDrainMultiplier, false);
	if (IS_PED_RUNNING(ped) || GET_DESIRED_MOVE_BLEND(ped) >= 1.6f)
		return movementStaminaRoadAdjusted(ped, g_humanJogRate,
			g_humanRoadDrainMultiplier, false);
	if (ENTITY_SPEED(ped) >= 0.12f || PED::GET_PED_STEALTH_MOVEMENT(ped))
		return movementStaminaRoadAdjusted(ped, g_humanWalkRate,
			g_humanRoadDrainMultiplier, false);
	return g_humanIdleRate;
}

// Horse gaits are read from GROUND SPEED, not from a gait state — the engine
// exposes no "this horse is cantering" flag. The bands below are where each gait
// actually sits in metres per second. This is honest but not perfect: a trotting
// horse running downhill can cross into the canter band on speed alone.
static const char* horseMovementStaminaMode(Ped horse) {
	if (IS_PED_SWIMMING(horse)) return "Swimming";
	const float speed = ENTITY_SPEED(horse);
	if (speed < 0.15f) return "Standing";
	if (speed < 2.4f) return "Walking";
	if (speed < 5.0f) return "Trotting";
	if (speed < 8.0f) return "Cantering";
	return "Galloping";
}

static float horseMovementStaminaRate(Ped horse) {
	if (IS_PED_SWIMMING(horse)) return g_horseSwimRate;
	const float speed = ENTITY_SPEED(horse);
	if (speed < 0.15f) return g_horseIdleRate;
	if (speed < 2.4f)
		return movementStaminaRoadAdjusted(horse, g_horseWalkRate,
			g_horseRoadDrainMultiplier, true);
	if (speed < 5.0f)
		return movementStaminaRoadAdjusted(horse, g_horseTrotRate,
			g_horseRoadDrainMultiplier, true);
	if (speed < 8.0f)
		return movementStaminaRoadAdjusted(horse, g_horseCanterRate,
			g_horseRoadDrainMultiplier, true);
	return movementStaminaRoadAdjusted(horse, g_horseGallopRate,
		g_horseRoadDrainMultiplier, true);
}

// ---- Surface-conforming free climbing (#169) -----------------------------
enum class ClimbState { Grounded, Grabbing, Climbing, ToppingOut, Dismounting, Airborne };
enum class ClimbMotion { Idle, Up, Down, Left, Right, Settling };
struct ClimbProbe {
	int handle = 0;
	bool hit = false;
	Vector3 point = {};
	Vector3 normal = {};
	Entity entity = 0;
	float bodyHeight = 0.0f;
};
static ClimbState g_climbState = ClimbState::Grounded;
// Four vertical body contacts plus left/right flank contacts for corner wrap.
static ClimbProbe g_climbProbes[6];
static Vector3 g_climbNormal = { 0.0f, -1.0f, 0.0f };
static Vector3 g_climbPoint = {};
static float g_climbContactHeight = 0.995f;
static DWORD g_climbStateAt = 0;
static DWORD g_climbLastTrace = 0;
static DWORD g_climbHeartbeatAt = 0;
static DWORD g_climbLastAnim = 0;
static int g_climbProtectedCore = -1;
static bool g_climbManualPending = false;
static DWORD g_climbManualAt = 0;
static DWORD g_climbSlipAt = 0;
static DWORD g_climbNativeTraversalAt = 0;
static DWORD g_climbGroundTraceAt = 0;
static DWORD g_climbLastContactAt = 0;
static DWORD g_climbProbeAt = 0;
static DWORD g_climbLeapAt = 0;
static DWORD g_climbTopOutAt = 0;
static bool g_climbNativeTopOutStarted = false;
static bool g_climbNativeTopOutObserved = false;
static DWORD g_climbNativeTopOutTraceAt = 0;
static bool g_climbTopOutBlockedUntilRelease = false;
static DWORD g_climbSlideStartedAt = 0;
static DWORD g_climbSlideLastSeenAt = 0;
static bool g_climbSlidePrequalified = false;
static StaminaDrain g_climbStamina;
static Vector3 g_climbLeapFrom = {};
static Vector3 g_climbTopOutFrom = {};
// The lean he is carrying when the mantle begins, so it can be unwound as he
// comes over the lip instead of him arcing onto flat ground still tilted.
static float g_climbTopOutPitch = 0.0f;
static Vector3 g_climbTopOutTarget = {};
// Asynchronous shape tests only resolve on roughly every second frame, so a
// single missed batch must never read as "the wall disappeared". Every steep
// batch is cached and the attached state is driven from the cache, not from
// whichever batch happens to land on the current frame.
struct ClimbContact {
	bool valid = false;
	Vector3 point = {};
	Vector3 normal = {};
	float height = 0.995f;
	DWORD at = 0;
};
static ClimbContact g_climbCache;
// A native slide may flicker off for one frame. Keep one pre-slide contact for
// the full physical slide episode, so a later probe cannot turn a slide that is
// already visible into a coordinate-owning climb on a different surface.
static ClimbContact g_climbSlideContact;
// Position we own while attached. Gravity used to drag Arthur off the face in
// the frames between probe batches; he is frozen and driven from this anchor.
static Vector3 g_climbAnchor = {};
static Vector3 g_climbAttachFrom = {};
static bool g_climbPhysicsOwned = false;
static bool g_climbReverseGrab = false;
static bool g_climbReverseAnimStarted = false;
static DWORD g_climbReverseDurationMs = 0;
static bool g_climbScanCamera = false;
static bool g_climbIdleLeftHand = false;
static ClimbMotion g_climbMotion = ClimbMotion::Idle;
static ClimbMotion g_climbSettleFrom = ClimbMotion::Idle;
static DWORD g_climbMotionAt = 0;
static bool g_climbReleaseAuditPending = false;
static int g_climbReleaseRetryCount = 0;
static DWORD g_climbReleaseAuditAt = 0;
static const char* g_climbReleaseDict = nullptr;
static const char* g_climbReleaseClip = nullptr;
static DWORD g_climbLateralAttemptAt = 0;
static ClimbMotion g_climbLateralDirection = ClimbMotion::Idle;
static DWORD g_climbLateralReadbackAt = 0;
static Vector3 g_climbLateralStartAnchor = {};
static Vector3 g_climbLateralStartActual = {};
// mech_ladders@base is the game's full vertical-traversal clip set (verified
// against the shipped animation table). The previous build played exactly one
// clip, `base_right_hand_up`, at playback rate 0 — a frozen pose, which is why
// Arthur appeared to float across the rock face without animating.
static const char* kClimbAnimDict = "mech_ladders@base";
static const char* kClimbIdleLeft = "base_left_hand_up";
static const char* kClimbIdleRight = "base_right_hand_up";
static const char* kClimbUp = "climb_up";
static const char* kClimbDown = "climb_down";
static const char* kClimbUpStartLeft = "climb_up_start_left_hand";
static const char* kClimbUpStartRight = "climb_up_start_right_hand";
static const char* kClimbDownStartLeft = "climb_down_start_left_hand";
static const char* kClimbDownStartRight = "climb_down_start_right_hand";
static const char* kClimbUpSettleLeft = "climb_up_settle_left_hand";
static const char* kClimbUpSettleRight = "climb_up_settle_right_hand";
static const char* kClimbDownSettleLeft = "climb_down_settle_left_hand";
static const char* kClimbDownSettleRight = "climb_down_settle_right_hand";
static const char* kClimbExitTop = "get_on_top_front";
static const char* kClimbExitBottom = "get_off_bottom_front_stand";
static const char* kClimbEnter = "get_on_bottom_front_run";
// The shipped animation inventory identifies `walk_left` as a DICTIONARY, not
// a clip in its parent `narrow_ledge` dictionary. Its playable traversal clip
// is `move`. The rejected Story-scene sidle must never be substituted when
// this authored asset is still streaming or fails a runtime readback.
static const char* kClimbLedgeDict =
	"mech_loco_m@character@arthur@terrain@unarmed@narrow_ledge_cliff@walk_left";
static const char* kClimbLedgeClip = "move";
// Rockstar-authored top-to-below-ledge transition. Unlike the rejected Story
// horse-leading scene, this belongs to the generic vertical-climb system.
static const char* kClimbReverseDict = "mech_climb@base@vertical@clamber_exits";
static const char* kClimbReverseClip = "vault_down";
static const char* g_climbAnimClip = nullptr;
// Track the dictionary each clip was ISSUED from instead of inferring it.
static const char* g_climbAnimDictInUse = nullptr;

static Vector3 cvAdd(Vector3 a, Vector3 b) { return { a.x + b.x, a.y + b.y, a.z + b.z }; }
static Vector3 cvSub(Vector3 a, Vector3 b) { return { a.x - b.x, a.y - b.y, a.z - b.z }; }
static Vector3 cvMul(Vector3 a, float s) { return { a.x * s, a.y * s, a.z * s }; }
static float cvDot(Vector3 a, Vector3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static float cvLen(Vector3 a) { return std::sqrt(cvDot(a, a)); }
static Vector3 cvNorm(Vector3 a) {
	const float length = cvLen(a);
	return length > 0.0001f ? cvMul(a, 1.0f / length) : Vector3{ 0.0f, 0.0f, 0.0f };
}
static Vector3 cvCross(Vector3 a, Vector3 b) {
	return { a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x };
}
static Vector3 cvLerp(Vector3 a, Vector3 b, float t) { return cvAdd(a, cvMul(cvSub(b, a), t)); }

// The direction "up the face" - the body's own up-axis while climbing. On a
// vertical wall this is world up; on a slope it leans back with the rock.
static Vector3 climbSurfaceUp(Vector3 normal) {
	Vector3 right = cvCross(Vector3{ 0.0f, 0.0f, 1.0f }, normal);
	if (cvLen(right) < 1e-3f) return Vector3{ 0.0f, 0.0f, 1.0f };
	Vector3 up = cvNorm(cvCross(normal, cvNorm(right)));
	if (up.z < 0.0f) up = cvMul(up, -1.0f);
	return up;
}

// WHY HIS LOWER BODY IS INSIDE THE ROCK, and why it only ever looked right on a
// vertical wall. A probe contact sits ON the surface at roughly chest height.
// To get from there to the root at his feet, this dropped STRAIGHT DOWN by that
// height - a world-space (0,0,-h) - and then stood off along the normal.
// Dropping straight down from a point on a sloped face does not travel along
// the face, it travels INTO it: the move buries the root by h * normal.z. On the
// 45-degree slope in Lexer's screenshot that is 1.0 * 0.707 = about 0.7 m of
// burial, against a standoff of 0.30 - so his legs and hips are a third of a
// metre inside solid rock before a single animation plays. On a vertical wall
// normal.z is 0, straight down IS along the face, and the error vanishes. That
// is exactly why every flat-wall test passed and every slope failed.
// Walk down the SURFACE instead of down the world, and the root lands on the
// face at precisely the requested standoff, at any angle.
static Vector3 climbRootFromContact(Vector3 point, Vector3 normal, float height,
	float standoff) {
	return cvAdd(cvSub(point, cvMul(climbSurfaceUp(normal), height)),
		cvMul(normal, standoff));
}

// ---- Camera-relative prone locomotion (#170) -----------------------------
// Every dictionary and clip named here was verified against the game's shipped
// animation table (`_downloads/rdr3_discoveries/animations/ingameanims`).
// TASK_PLAY_ANIM with a clip that is not in its dictionary, or with a
// dictionary that has not finished streaming, plays nothing at all and leaves
// the ped in its default stance. That silent no-op is what produced every
// rejected result: "stands up first and is then forced into crouch" is simply
// CLEAR_PED_TASKS followed by an animation that never started.
static const char* kProneCrawlDict = "mech_crawl@base";
static const char* kProneIdleClip = "idle";
static const char* kProneWalkClip = "walk";
static const char* kProneWalkLeftClip = "walk_turn_l4";
static const char* kProneWalkRightClip = "walk_turn_r4";
static const char* kProneWalkBackwardClip = "onfront_bwd";
// FUN_18000f280 gives the crawl clips exclusive mover ownership. 0x30001C01
// belongs to moving clips; 0x30000401 belongs to idle. Do not add coordinate,
// velocity or root-rotation writers on top of these tasks.
static const int kProneMoveFlags = 0x30001C01;
static const int kProneIdleFlags = 0x30000401;
// Standing/crouched -> prone. The decompiled Crawl N' Gun persistent-prone
// handler (FUN_180014d60) uses mech_crawl@base/idle2stealth with the
// keyboard/controller flag split below. Its dive_launch_* assets belong to the
// separate combat-dive handler (FUN_180015400); using dive_launch_fwd here made
// Arthur dive into the ground and hand control to ragdoll physics.
static const char* kProneEnterClip = "idle2stealth";
// Prone -> kneeling. This dictionary contains exactly one clip, "front".
// `prone_to_seated@crawl` contains only "back" and is a face-up recovery, so
// playing it from the face-down crawl pose could never look right.
static const char* kProneKneesDict = "ai_getup@directional@transition@prone_to_knees@crawl";
static const char* kProneKneesClip = "front";
static const char* kProneExitReferenceDict =
	"ai_getup@directional_sweep@combat@cop@rifle@front";
static const char* kProneExitReferenceClip = "get_up_0";
// Retained weapon-specific get-up assets belong to the combat-dive path. They
// are not the persistent-prone exit used by FUN_18000f280.
static const char* kProneGetupUnarmed = "mech_weapons_core@base@dive@unarmed@getup";
static const char* kProneGetupPistol = "mech_weapons_core@base@dive@pistol@getup";
static const char* kProneGetupRifle = "mech_weapons_core@base@dive@rifle@getup";
static const char* kProneGetupClip = "dive_getup_fwd";
// Crawl N' Gun's authored face-down one-handed aim rig. Unlike a native
// standing aim task, these clips can own the full skeleton without lifting the
// ped out of prone. The reference uses aim_med_0 with flags 0x10000410.
static const char* kProneAim1hDict =
	"ai_combat@aim_sweeps@cowboy@grounded@base@1h";
static const char* kProneAim1hIntro = "aim_med_0_intro";
static const char* kProneAim1hLoop = "aim_med_0";
static const char* kProneAim1hOutro = "aim_med_0_outro";
static const char* kProneRollBackDict =
	"ai_getup@directional@transition@prone_to_faceup";
static const char* kProneRollBackClip = "back";
static const char* kProneRollFrontDict =
	"ai_getup@directional@transition@prone_to_facedown";
static const char* kProneRollFrontClip = "front";
static const char* kProneAimBackRifleDict =
	"ai_getup@aim_from_ground@cop@rifle@on_back";
static const char* kProneAimBackPistolDict =
	"ai_getup@aim_from_ground@cop@pistol@on_back";
static const char* kProneAimBackIntro = "intro_0";
static const char* kProneAimBackLoop = "sweep_med";
static const char* kProneAimBackOutro = "outro_0";
static const char* kProneEquipDict = "script_common@other@unapproved";
static const char* kProneEquipClip = "prone_michael";
// RDR2's shipped scripts use 0 for one-shots and 1 for looping locomotion here.
static const int kProneAnimOnce = 0;
static const int kProneAnimLoop = 1;
static const int kProneAnimHold = 1;

enum class ProneState {
	Standing, Crouched, Entering, Prone, ExitingCrouch, ExitingStanding,
	SettlingStanding
};
enum class ProneLocoState { Idle, Starting, Moving, Stopping };
enum class ProneActionState {
	None, AimIntro, Aiming, AimOutro,
	RollingBack, BackAimIntro, BackAiming, BackAimOutro, RollingFront
};
static ProneState g_proneState = ProneState::Standing;
static ProneLocoState g_proneLocoState = ProneLocoState::Idle;
static Ped g_pronePed = 0;
static Hash g_proneModel = 0;
static bool g_proneSavedStealth = false;
static bool g_pronePressing = false;
static bool g_proneHoldHandled = false;
static bool g_proneLocoFoot = false;
static bool g_proneStartedCrouched = false;
static int g_proneEntryStage = 0;
static bool g_proneRequireDuckRelease = false;
static bool g_proneEntryFrozen = false;
static DWORD g_pronePressedAt = 0;
static DWORD g_proneStateAt = 0;
static DWORD g_proneLastAnim = 0;
static DWORD g_proneLastTrace = 0;
static Vector3 g_proneTracePosition = {};
static DWORD g_proneLocoAt = 0;
static DWORD g_proneStreamAt = 0;
static DWORD g_proneGateTrace = 0;
static DWORD g_proneStandAfterCrouchAt = 0;
static DWORD g_proneStandRequestedAt = 0;
static float g_pronePitch = 0.0f;
static float g_proneRoll = 0.0f;
static const char* g_proneExitDict = nullptr;
static const char* g_proneExitClip = nullptr;
static const char* g_proneLocoClip = nullptr;
static Vector3 g_proneLastPosition = {};
static float g_proneEntryHeading = 0.0f;
static bool g_proneActionSuspended = false;
static DWORD g_proneActionResumeAt = 0;
static ProneActionState g_proneActionState = ProneActionState::None;
static DWORD g_proneActionAt = 0;
static Hash g_proneActionWeapon = 0;
static bool g_proneBackRigBino = false;
static bool g_proneWheelWasOpen = false;
static DWORD g_proneWheelSeenAt = 0;
static DWORD g_proneEquipUntil = 0;
static Hash g_proneEquipWeapon = 0;

static const char* proneStateName(ProneState state) {
	switch (state) {
	case ProneState::Standing: return "standing";
	case ProneState::Crouched: return "crouched";
	case ProneState::Entering: return "entering";
	case ProneState::Prone: return "prone";
	case ProneState::ExitingCrouch: return "exiting_crouch";
	case ProneState::ExitingStanding: return "exiting_standing";
	case ProneState::SettlingStanding: return "settling_standing";
	default: return "unknown";
	}
}

static void proneLog(const std::string& text) {
	// State transitions and bounded heartbeats must survive release builds. The
	// old development-only gate produced an empty log for a wholly failed test.
	gtLog("prone", GT_INFO, text);
}

static void setProneState(ProneState next, const char* reason) {
	if (next == g_proneState) return;
	std::ostringstream line;
	line << proneStateName(g_proneState) << " -> " << proneStateName(next)
		<< " reason=" << reason;
	proneLog(line.str());
	g_proneState = next;
	g_proneStateAt = GetTickCount();
}

static bool customProneActive() {
	return g_proneState == ProneState::Entering || g_proneState == ProneState::Prone ||
		g_proneState == ProneState::ExitingCrouch ||
		g_proneState == ProneState::ExitingStanding ||
		g_proneState == ProneState::SettlingStanding;
}

struct ProneDict { const char* name; bool checked; bool exists; };
static ProneDict g_proneDicts[] = {
	{ kProneCrawlDict, false, false },
	{ kProneKneesDict, false, false },
	{ kProneExitReferenceDict, false, false },
	{ kProneGetupUnarmed, false, false },
	{ kProneGetupPistol, false, false },
	{ kProneGetupRifle, false, false },
	{ kProneAim1hDict, false, false },
	{ kProneRollBackDict, false, false },
	{ kProneRollFrontDict, false, false },
	{ kProneAimBackRifleDict, false, false },
	{ kProneAimBackPistolDict, false, false },
	{ kProneEquipDict, false, false },
};

// The previous build called REQUEST_ANIM_DICT for three dictionaries on every
// single frame for as long as prone was enabled, including before any of them
// could be needed. Hammering the streamer that way is the most plausible source
// of the launch crash that forced Enabled=0, and it does nothing once a
// dictionary is resident. Ask at most four times a second, never for a name the
// game does not have, and only while a Duck press or prone itself is live.
static void proneEnsureDicts(DWORD now) {
	if (now - g_proneStreamAt < 250) return;
	g_proneStreamAt = now;
	for (ProneDict& dict : g_proneDicts) {
		if (!dict.checked) {
			dict.checked = true;
			dict.exists = STREAMING::DOES_ANIM_DICT_EXIST(dict.name) != FALSE;
			if (!dict.exists) proneLog(std::string("anim dict missing: ") + dict.name);
		}
		if (!dict.exists) continue;
		if (!STREAMING::HAS_ANIM_DICT_LOADED(dict.name))
			STREAMING::REQUEST_ANIM_DICT(dict.name);
	}
}

static bool proneHoldInputDown(Hash duck) {
	// Keep ordinary Duck taps native. PAD covers remapped actions when Rockstar
	// exposes them; physical Ctrl/L3 are the confirmed default keyboard/gamepad
	// bindings and remain readable independently once we suppress a held action.
	const bool padAction = PAD::IS_CONTROL_PRESSED(0, duck) ||
		PAD::IS_CONTROL_PRESSED(2, duck) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, duck) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, duck);
	const bool keyboardCtrl = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
	return padAction || keyboardCtrl || padButtonDown(XINPUT_GAMEPAD_LEFT_THUMB);
}

static bool proneDictReady(const char* dict) {
	return STREAMING::HAS_ANIM_DICT_LOADED(dict) != FALSE;
}

// Returns the clip's normalised phase, or -1 when it is not the ped's current
// task animation. Phase replaces the guessed millisecond timers: a transition
// is finished when its own clip says so, not when a stopwatch expires.
static float proneAnimPhase(Ped ped, const char* dict, const char* clip) {
	if (!dict || !clip) return -1.0f;
	// Do NOT gate on IS_ENTITY_PLAYING_ANIM. That predicate is unreliable here
	// (it is what pinned the climbing pose at frame 0), and gating on it made
	// this return -1 permanently, silently demoting every transition to its
	// fallback stopwatch.
	return ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(ped, dict, clip);
}

static DWORD proneAnimDurationMs(const char* dict, const char* clip,
	DWORD minimum, DWORD maximum) {
	if (!dict || !clip || !proneDictReady(dict)) return maximum;
	const float seconds = ENTITY::GET_ANIM_DURATION(dict, clip);
	if (!std::isfinite(seconds) || seconds <= 0.0f) return maximum;
	const DWORD duration = (DWORD)(seconds * 1000.0f);
	return (std::max)(minimum, (std::min)(maximum, duration));
}

static void playProneAnimation(Ped ped, const char* dict, const char* clip,
	float blend, int duration, int flags, float rate) {
	if (!proneDictReady(dict)) return;
	// Crawl N' Gun's wrapper does not use the SDK's ordinary argument tail.
	// It passes 0, false, 0x02000000, false, empty-string, false after flags.
	// The 0x02000000 task filter is part of every crawl clip invocation.
	TASK::TASK_PLAY_ANIM(ped, dict, clip, blend, -blend, duration, flags, 0.0f,
		FALSE, 0x02000000, FALSE, "", FALSE);
	g_proneTaskOwnsSkeleton = true;
	g_proneLastAnim = GetTickCount();
}

static void playReferenceCrawlAnimation(Ped ped, const char* clip, int flags) {
	if (!proneDictReady(kProneCrawlDict) || !clip) return;
	TASK::TASK_PLAY_ANIM(ped, kProneCrawlDict, clip,
		1.0f, 1.0f, -1, flags, 0.0f,
		FALSE, 0x02000000, FALSE, "", FALSE);
	g_proneTaskOwnsSkeleton = true;
	g_proneLastAnim = GetTickCount();
}

static void applyCrouchStance(Ped ped, bool crouched, bool immediate) {
	// immediately=FALSE lets Rockstar animate its own crouch, which is right for
	// an ordinary Duck tap. It is WRONG coming out of prone: the request is
	// simply dropped while the ped is still on the ground, so Arthur stood up
	// instead of ending in a crouch. Force it on that path and re-assert below
	// until the engine actually reports crouched.
	SET_PED_CROUCH_MOVEMENT(ped, crouched, immediate);
	SET_PED_STEALTH_MOVEMENT(ped, crouched);
}

static const char* proneWeaponRig(Ped ped, const char* unarmed,
	const char* pistol, const char* rifle) {
	const Hash weapon = GET_CURRENT_WEAPON(ped);
	if (!weapon || weapon == joaat("WEAPON_UNARMED")) return unarmed;
	const Hash group = WEAPON::GET_WEAPONTYPE_GROUP(weapon);
	if (group == joaat("GROUP_PISTOL") || group == joaat("GROUP_REVOLVER"))
		return pistol;
	if (group == joaat("GROUP_REPEATER") || group == joaat("GROUP_RIFLE") ||
		group == joaat("GROUP_SNIPER") || group == joaat("GROUP_SHOTGUN") ||
		group == joaat("GROUP_BOW"))
		return rifle;
	return unarmed;
}

static const char* proneGetupDict(Ped ped) {
	return proneWeaponRig(ped, kProneGetupUnarmed,
		kProneGetupPistol, kProneGetupRifle);
}

// Returns false when the transition could not be started. The caller must then
// leave the hold unresolved and retry, rather than clearing tasks and stranding
// the ped in a default stance while the dictionary is still streaming.
static bool beginProne(Ped ped, const char* reason) {
	if (!ped || customProneActive()) return false;
	if (!proneDictReady(kProneCrawlDict)) return false;
	g_pronePed = ped;
	g_proneModel = ENTITY_MODEL(ped);
	g_proneSavedStealth = PED::GET_PED_STEALTH_MOVEMENT(ped) != FALSE;
	g_proneLastPosition = ENTITY_COORDS(ped);
	g_proneEntryHeading = ENTITY_HEADING(ped);
	g_proneLocoState = ProneLocoState::Idle;
	g_proneLocoClip = nullptr;
	g_proneEntryStage = 2;
	g_proneRequireDuckRelease = true;
	// Entering prone cancels any stand-settle still pending from a previous
	// exit. Otherwise that timer lands mid-crawl and desyncs the state machine.
	g_proneStandAfterCrouchAt = 0;
	g_proneStandRequestedAt = 0;
	// Exact ordinary Ctrl path. Both keyboard and controller visibly settle into
	// Rockstar crouch first; the authored prone transition is not issued until
	// the Entering stage observes crouch (or its bounded fallback expires).
	g_proneEntryFrozen = false;
	// Weapons are refused while prone (#195), so going prone holding one left it
	// stuck in his hands in a pose the crawl clips were never authored for. Put
	// it away on the way down. Nothing prone can use it anyway.
	// #195: a ONE-HANDED weapon is the exception — Rockstar authored a complete
	// face-down one-handed aim set and it is wired up below, so a pistol,
	// revolver or throwable can come down with him. Longarms have no authored
	// face-down set at all and still get put away.
	{
		const Hash held = GET_CURRENT_WEAPON(ped);
		const bool holdable = g_proneOneHandedWeapons && held &&
			(WEAPON::_IS_WEAPON_PISTOL(held) || WEAPON::_IS_WEAPON_REVOLVER(held) ||
			 WEAPON::_IS_WEAPON_THROWABLE(held));
		if ((g_proneBlockWeaponActions || g_proneOneHandedWeapons) && !holdable &&
			held && held != joaat("WEAPON_UNARMED"))
			WEAPON::SET_CURRENT_PED_WEAPON(ped, joaat("WEAPON_UNARMED"), true, 0, false, false);
	}
	// FUN_180014d60 performs these two calls back-to-back, then waits 900 ms
	// before entering its crawl loop. The former staged delay was not reference
	// behavior and let Rockstar's crouch graph compete before the authored task.
	SET_PED_CROUCH_MOVEMENT(ped, true, false);
	const bool keyboard = invoke<BOOL>(0xA571D46727E2B718, 0) != FALSE;
	const int flags = keyboard ? 0x00010C00 : 0x20010C00;
	TASK::TASK_PLAY_ANIM(ped, kProneCrawlDict, kProneEnterClip,
		1.0f, 1.0f, -1, flags, 0.0f,
		FALSE, 0x02000000, FALSE, "", FALSE);
	g_proneTaskOwnsSkeleton = true;
	g_proneLastAnim = GetTickCount();
	setProneState(ProneState::Entering, reason);
	proneLog(std::string("reference entry issued clip=idle2stealth flags=") +
		(keyboard ? "0x00010C00" : "0x20010C00"));
	return true;
}

static void finishProneExit(Ped ped, bool toCrouch, const char* reason,
	bool immediate = false) {
	if (ped) {
		// The supplied reference standing exit establishes native crouch first,
		// with p2=1 and immediately=true, then clears its crawl tasks. The old
		// order cleared the full-body task first and exposed the standing base
		// pose before crouch existed.
		if (!toCrouch && !immediate)
			invoke<Void>(0x7DE9692C6F64CFE8, ped, TRUE, 1, TRUE);
		else
			applyCrouchStance(ped, toCrouch, true);
		TASK::CLEAR_PED_SECONDARY_TASK(ped);
		TASK::CLEAR_PED_TASKS(ped, true, true);
		g_proneTaskOwnsSkeleton = false;
	}
	if (!toCrouch && immediate) {
		g_proneStandAfterCrouchAt = 0;
		g_proneStandRequestedAt = 0;
		g_proneRequireDuckRelease = true;
		g_pronePressing = false;
		g_proneHoldHandled = false;
		setProneState(ProneState::Standing, reason);
	} else if (!toCrouch) {
		// Arm the visible hold only after native crouch readback. Clearing ped/model
		// ownership here used to make the next frame treat SettlingStanding as a
		// ped mismatch and hard-exit immediately, so this state never rendered.
		g_proneStandAfterCrouchAt = 0;
		g_proneStandRequestedAt = 0;
		setProneState(ProneState::SettlingStanding, reason);
	} else {
		g_proneStandAfterCrouchAt = 0;
		g_proneStandRequestedAt = 0;
		setProneState(ProneState::Crouched, reason);
	}
	if (g_proneState != ProneState::SettlingStanding) {
		g_pronePed = 0;
		g_proneModel = 0;
	}
	g_proneExitDict = nullptr;
	g_proneExitClip = nullptr;
	g_proneLocoClip = nullptr;
	g_proneLocoState = ProneLocoState::Idle;
	g_proneActionSuspended = false;
	g_proneActionResumeAt = 0;
	g_proneActionState = ProneActionState::None;
	g_proneActionWeapon = 0;
	g_proneEquipWeapon = 0;
	g_proneEquipUntil = 0;
	g_proneBackRigBino = false;
	if (g_proneEntryFrozen && ped) {
		ENTITY::FREEZE_ENTITY_POSITION(ped, FALSE);
		g_proneEntryFrozen = false;
	}
}

static bool beginProneExit(Ped ped, bool toCrouch, const char* reason) {
	if (!ped || g_proneState != ProneState::Prone) return false;
	// Tap-to-crouch retains the shipped prone-to-knees clip. Standing uses the
	// supplied working mod's exact persistent-prone exit: rifle/front get_up_0,
	// flags 0x20002C10, then its 600 ms boundary and native crouch handoff.
	const char* dict = toCrouch ? kProneKneesDict : kProneExitReferenceDict;
	const char* clip = toCrouch ? kProneKneesClip : kProneExitReferenceClip;
	if (!proneDictReady(dict)) {
		proneLog(std::string("exit deferred: dictionary not streamed: ") + dict);
		return false;
	}
	g_proneExitDict = dict;
	g_proneExitClip = clip;
	// DO NOT CLEAR_PED_TASKS HERE, AND DO NOT DROP THE CROUCH STANCE HERE.
	// Clearing released the crawl skeleton, so the ped snapped to its standing
	// base pose for the frames before the exit clip bound, and only THEN did the
	// get-up play. That is the "jumps directly into standing, then does an
	// on-all-fours animation, then gets up again" report - two separate causes
	// stacked. TASK_PLAY_ANIM already replaces the running crawl task: the
	// idle<->walk switcher below relies on exactly that every time it changes
	// clip and never clears. Blend out of the live prone pose instead.
	// finishProneExit already calls applyCrouchStance(ped, toCrouch, true) at the
	// end of the clip, so clearing crouch up front only let the engine stand him
	// up underneath the animation.
	const int exitFlags = toCrouch ? 0x10000410 : 0x20002C10;
	playProneAnimation(ped, dict, clip, 1.0f, -1, exitFlags, 0.0f);
	proneLog(std::string("exit clip ") + dict + "/" + clip +
		(toCrouch ? " (to crouch) flags=0x10000410" :
		" (to standing) flags=0x20002C10 referenceWaitMs=600"));
	setProneState(toCrouch ? ProneState::ExitingCrouch :
		ProneState::ExitingStanding, reason);
	return true;
}

static void leaveProneImmediate(Ped ped, bool toCrouch, const char* reason) {
	finishProneExit(ped, toCrouch, reason, true);
}

// A native STANDING full-body task (binoculars today) has no authored face-down
// form: RDR2 ships no prone binocular animation, and the only ground option is
// the roll-onto-the-back rig, which was already rejected in-game for rolling
// Arthur through terrain when driven from timers. So do not fake it. Returns
// TRUE while the caller must wait or give up:
//   BinocularMode=0 -> refuse outright, he stays prone.
//   BinocularMode=1 -> run the authored prone->knees exit, then allow it, so the
//                      stand-up is a real transition instead of a teleport.
// Returns FALSE once he is off the ground and the caller may proceed.
static bool proneRequestStandForNativeAction(Ped ped, const char* reason) {
	if (!ped || !customProneActive()) return false;
	if (g_proneState == ProneState::Prone) {
		if (g_proneBinocularMode == 0) {
			proneLog(std::string("refused ") + reason +
				" while prone (Prone/BinocularMode=0)");
			return true;
		}
		if (beginProneExit(ped, true, reason))
			proneLog(std::string(reason) + ": authored prone exit first");
		return true;
	}
	// Entering or already transitioning: let that finish before handing the
	// skeleton to anything else.
	return true;
}

static void leaveProneToCrouchDirect(Ped ped, const char* reason) {
	if (!ped || g_proneState != ProneState::Prone) return;
	// An immediate clear exposes the standing base pose for a frame. Retain the
	// crawl skeleton until the authored prone-to-knees transition is ready.
	beginProneExit(ped, true, reason);
}

static float shortestHeadingDelta(float from, float to) {
	float delta = std::fmod(to - from + 540.0f, 360.0f) - 180.0f;
	return delta;
}

static const char* proneStartClip() { return g_proneLocoFoot ? "wstart_r_0" : "wstart_l_0"; }
static const char* proneStopClip() { return g_proneLocoFoot ? "wstop_r_0" : "wstop_l_0"; }

// #170: IS_PED_SWIMMING only becomes true once he is actually swimming, so it
// never stopped him lying face-down in water shallow enough to stand in — which
// is precisely where his head goes under. Compare the water surface against the
// ground he would be lying on: prone puts his head barely above the ground
// plane, so any water deeper than that clearance drowns him.
static bool proneHeadWouldSubmerge(Ped ped) {
	if (!ped || g_proneWaterHeadClearance <= 0.0f) return false;
	const Vector3 position = ENTITY_COORDS(ped);
	float waterZ = 0.0f;
	if (!WATER_HEIGHT(position, &waterZ)) return false;   // no water here at all
	float groundZ = position.z;
	if (!GROUND_Z(position, &groundZ)) groundZ = position.z;
	return waterZ > groundZ + g_proneWaterHeadClearance;
}

static bool proneUnavailable(Player player, Ped ped, bool unavailable, bool mission) {
	// Weapon/satchel wheels temporarily clear PLAYER_CONTROL_ON. Treating that
	// transient UI state as a hard interruption ran finishProneExit immediately,
	// which is why merely equipping anything stood Arthur up. The caller now
	// supplies only true hard locks (death/fade); mission and physical-state
	// exclusions remain explicit here.
	return !ped || unavailable || mission ||
		g_climbState != ClimbState::Grounded ||
		PED::IS_PED_DEAD_OR_DYING(ped, TRUE) || PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE) ||
		PED::IS_PED_ON_MOUNT(ped) || PED::IS_PED_RAGDOLL(ped) ||
		PED::IS_PED_FALLING(ped) || ENTITY::IS_ENTITY_IN_AIR(ped, 0) ||
		PED::IS_PED_SWIMMING(ped) || PED::IS_PED_CLIMBING(ped) ||
		PED::_IS_PED_CLIMBING_LADDER(ped) || PED::IS_PED_USING_ANY_SCENARIO(ped);
}

static void updateProne(Player player, Ped ped, DWORD now, bool unavailable, bool mission) {
	static DWORD previous = now;
	float dt = (now - previous) * 0.001f;
	previous = now;
	if (dt <= 0.0f || dt > 0.10f) dt = 0.016f;

	// The 2026-07-28 session produced ZERO prone log lines, which means this gate
	// rejected every frame before any input was even read. The old trace only ran
	// after the gate, so it could never say why. Report each term once a second.
	if (now - g_proneGateTrace >= (g_proneTrace ? 1000u : 5000u)) {
		g_proneGateTrace = now;
		std::ostringstream gate;
		gate << "gate enabled=" << (g_proneEnabled ? 1 : 0)
			<< " ped=" << (ped ? 1 : 0)
			<< " unavailable=" << (unavailable ? 1 : 0)
			<< " mission=" << (mission ? 1 : 0)
			<< " control=" << (PLAYER_CONTROL_ON(player) ? 1 : 0)
			<< " climbState=" << (int)g_climbState
			<< " dying=" << (PED::IS_PED_DEAD_OR_DYING(ped, TRUE) ? 1 : 0)
			<< " vehicle=" << (PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE) ? 1 : 0)
			<< " mount=" << (PED::IS_PED_ON_MOUNT(ped) ? 1 : 0)
			<< " ragdoll=" << (PED::IS_PED_RAGDOLL(ped) ? 1 : 0)
			<< " falling=" << (PED::IS_PED_FALLING(ped) ? 1 : 0)
			<< " inAir=" << (ENTITY::IS_ENTITY_IN_AIR(ped, 0) ? 1 : 0)
			<< " swim=" << (PED::IS_PED_SWIMMING(ped) ? 1 : 0)
			<< " climbing=" << (PED::IS_PED_CLIMBING(ped) ? 1 : 0)
			<< " ladder=" << (PED::_IS_PED_CLIMBING_LADDER(ped) ? 1 : 0)
			<< " scenario=" << (PED::IS_PED_USING_ANY_SCENARIO(ped) ? 1 : 0)
			<< " ctrlKey=" << ((GetAsyncKeyState(VK_CONTROL) & 0x8000) ? 1 : 0)
			<< " padDuck=" << (PAD::IS_CONTROL_PRESSED(0, joaat("INPUT_DUCK")) ? 1 : 0);
		proneLog(gate.str());
	}

	if (!g_proneEnabled || proneUnavailable(player, ped, unavailable, mission) ||
		(customProneActive() && (ped != g_pronePed || ENTITY_MODEL(ped) != g_proneModel))) {
		if (customProneActive()) leaveProneImmediate(ped, g_proneSavedStealth,
			mission ? "mission" : "interrupted");
		g_pronePressing = false;
		g_proneHoldHandled = false;
		g_proneActionState = ProneActionState::None;
		g_proneActionWeapon = 0;
		g_proneEquipWeapon = 0;
		g_proneEquipUntil = 0;
		g_proneBackRigBino = false;
		return;
	}

	const Hash duck = joaat("INPUT_DUCK");
	// Own Duck unconditionally while this feature is enabled. Waiting until a
	// hold was recognized let Rockstar process Ctrl first and invert crouch
	// underneath us (crouched -> standing was visible in the live trace).
	for (int group = 0; group < 3; ++group) DISABLE_CONTROL(group, duck);
	const bool duckDown = proneHoldInputDown(duck);
	const bool interested = duckDown || g_pronePressing || customProneActive();
	if (interested) proneEnsureDicts(now);

	if (g_proneRequireDuckRelease && !duckDown)
		g_proneRequireDuckRelease = false;
	// Duck is only accepted in a STABLE state. Presses made during a transition
	// used to sit in g_pronePressing and fire the instant the transition landed
	// - the log shows exiting_standing beginning 16 ms after entry completed,
	// off a press made while Arthur was still lying down. That queued input is
	// the stand/crouch/drop/stand chaos.
	const bool proneStable = g_proneState == ProneState::Standing ||
		g_proneState == ProneState::Crouched ||
		g_proneState == ProneState::Prone;
	if (!proneStable) {
		g_pronePressing = false;
		g_proneHoldHandled = false;
		if (duckDown) g_proneRequireDuckRelease = true;
	}
	if (proneStable && duckDown && !g_pronePressing && !g_proneRequireDuckRelease) {
		g_pronePressing = true;
		g_proneHoldHandled = false;
		g_pronePressedAt = now;
		// Capture the starting stance ONLY when we are not already prone.
		// Unconditionally, this fired on every Ctrl press made WHILE prone and
		// overwrote g_proneState with Crouched/Standing straight from the engine
		// crouch flag - silently, without setProneState, so nothing appeared in
		// the log. customProneActive() then went false, so the hold/tap handler
		// below routed to beginProne instead of beginProneExit. That is why Ctrl
		// re-entered prone forever instead of getting you out, and why the crawl
		// kept running after W was released: the prone branch had stopped
		// executing entirely, so nothing zeroed velocity or ended the walk loop.
		if (!customProneActive()) {
			g_proneStartedCrouched = GET_PED_CROUCH_MOVEMENT(ped) != FALSE;
			g_proneState = g_proneStartedCrouched ?
				ProneState::Crouched : ProneState::Standing;
			if (!g_proneStartedCrouched)
				applyCrouchStance(ped, true, false);
		}
	}
	// Duck cannot be both Rockstar's toggle and our hold gesture. The control is
	// suppressed above; the captured starting state drives an explicit crouch
	// transition or toggle, so crouched -> prone can never pass through standing.
	if (g_pronePressing && duckDown && !g_proneHoldHandled &&
		now - g_pronePressedAt >= (DWORD)g_proneHoldMs) {
		// Only mark the hold resolved once the transition actually started. If a
		// dictionary is still streaming we retry on the next frame instead of
		// swallowing the input.
		if (g_proneState != ProneState::Prone && proneHeadWouldSubmerge(ped)) {
			// Refuse rather than lie him down face-first into water.
			campMessage("Too deep to lie down here.");
			g_proneHoldHandled = true;
		} else {
			g_proneHoldHandled = g_proneState == ProneState::Prone ?
				beginProneExit(ped, false, "duck_hold") : beginProne(ped, "duck_hold");
		}
	}
	if (g_pronePressing && !duckDown) {
		if (!g_proneHoldHandled && g_proneState == ProneState::Prone)
			leaveProneToCrouchDirect(ped, "duck_tap");
		else if (!g_proneHoldHandled)
			applyCrouchStance(ped, !g_proneStartedCrouched, false);
		g_pronePressing = false;
		g_proneHoldHandled = false;
	}

	// This timer is armed by a stand-exit and belongs ONLY to the
	// SettlingStanding state it was armed for. It used to fire unconditionally,
	// so a pending settle from a previous exit would land in the middle of a NEW
	// prone session and slam the state to Standing behind setProneState's back -
	// no transition was logged, customProneActive() went false, and every
	// subsequent Ctrl ran beginProne instead of beginProneExit. That is the
	// "stuck in prone forever" bug: the state machine and the ped disagreed.
	if (g_proneStandAfterCrouchAt &&
		g_proneState != ProneState::SettlingStanding) {
		proneLog("dropped stale stand-settle timer (state moved on)");
		g_proneStandAfterCrouchAt = 0;
	}
	if (g_proneState == ProneState::SettlingStanding &&
		!g_proneStandAfterCrouchAt && !g_proneStandRequestedAt) {
		const bool crouchAccepted = GET_PED_CROUCH_MOVEMENT(ped) != FALSE;
		if (crouchAccepted) {
			// The existing 300 ms seat is now armed by a real crouch readback. It
			// previously never ran because finishProneExit cleared g_pronePed while
			// SettlingStanding still counted as an owned transition.
			g_proneStandAfterCrouchAt = now + 300;
			proneLog("standing exit intermediate crouch accepted readback=1 holdMs=300");
		} else if (now - g_proneStateAt >= 1500) {
			// Preserve an observable failure instead of hanging in a fake completed
			// state. This is a hard fallback, not ordinary exit behavior.
			proneLog("standing exit failed: crouch readback=0 after 1500ms");
			leaveProneImmediate(ped, false, "crouch_readback_failed");
			return;
		}
	}
	if (g_proneStandAfterCrouchAt && now >= g_proneStandAfterCrouchAt) {
		g_proneStandAfterCrouchAt = 0;
		// Ctrl is usually still held when a hold-exit finishes. Without this the
		// same unbroken press immediately satisfies the entry hold again and
		// Arthur cycles prone/stand/prone - the "up and down back and forth".
		g_proneRequireDuckRelease = true;
		g_pronePressing = false;
		g_proneHoldHandled = false;
		applyCrouchStance(ped, false, false);
		g_proneStandRequestedAt = now;
		proneLog(std::string("standing exit crouch-to-stand requested crouchReadback=") +
			(GET_PED_CROUCH_MOVEMENT(ped) ? "1" : "0"));
	}
	if (g_proneState == ProneState::SettlingStanding &&
		g_proneStandRequestedAt) {
		const bool stillCrouched = GET_PED_CROUCH_MOVEMENT(ped) != FALSE;
		if (!stillCrouched) {
			proneLog(std::string("standing exit complete crouchReadback=0 elapsedMs=") +
				std::to_string(now - g_proneStandRequestedAt));
			g_proneStandRequestedAt = 0;
			setProneState(ProneState::Standing, "stand_readback_complete");
			g_pronePed = 0;
			g_proneModel = 0;
			g_proneExitDict = nullptr;
			g_proneExitClip = nullptr;
		} else if (now - g_proneStandRequestedAt >= 1500) {
			proneLog("standing exit failed: crouch remained active 1500ms after stand request");
			leaveProneImmediate(ped, false, "stand_readback_failed");
			return;
		}
	}

	if (!customProneActive()) {
		const bool crouched = GET_PED_CROUCH_MOVEMENT(ped);
		if (!g_pronePressing)
			g_proneState = crouched ? ProneState::Crouched : ProneState::Standing;
		if (g_proneTrace && (duckDown || g_pronePressing) &&
			now - g_proneLastTrace >= 100) {
			g_proneLastTrace = now;
			std::ostringstream line;
			line << "hold state=" << proneStateName(g_proneState)
				<< " duckDown=" << (duckDown ? 1 : 0)
				<< " pressing=" << (g_pronePressing ? 1 : 0)
				<< " handled=" << (g_proneHoldHandled ? 1 : 0)
				<< " age=" << (g_pronePressing ? now - g_pronePressedAt : 0)
				<< " crouch=" << (crouched ? 1 : 0)
				<< " enterDict=" << (proneDictReady(kProneCrawlDict) ? 1 : 0)
				<< " crawlDict=" << (proneDictReady(kProneCrawlDict) ? 1 : 0);
			proneLog(line.str());
		}
		return;
	}

	if (g_proneState == ProneState::Entering) {
		const DWORD elapsed = now - g_proneStateAt;
		// The working reference waits exactly 900 ms before entering its crawl
		// loop; do not wait for a dive mover or a ragdoll postcondition here.
		const bool finished = elapsed >= 900;
		if (finished) {
			if (g_proneEntryFrozen) {
				ENTITY::FREEZE_ENTITY_POSITION(ped, FALSE);
				g_proneEntryFrozen = false;
			}
			const bool entryStillPlaying = ENTITY::IS_ENTITY_PLAYING_ANIM(
				ped, kProneCrawlDict, kProneEnterClip, 3) != FALSE;
			playReferenceCrawlAnimation(ped, kProneIdleClip, kProneIdleFlags);
			g_proneLocoClip = kProneIdleClip;
			g_proneLocoState = ProneLocoState::Idle;
			g_proneLocoAt = now;
			// Entry has authored displacement. Start the locomotion envelope at its
			// completed position rather than comparing the first crawl frame to the
			// position from before the crawl intro began.
			g_proneLastPosition = ENTITY_COORDS(ped);
			setProneState(ProneState::Prone, "entry_complete");
			proneLog(std::string("entry handoff elapsed=") +
				std::to_string(elapsed) + " entryPlaying=" +
				(entryStillPlaying ? "1" : "0") + " idleIssued=1");
		}
		return;
	}

	if (g_proneState == ProneState::ExitingCrouch ||
		g_proneState == ProneState::ExitingStanding) {
		const bool toCrouch = g_proneState == ProneState::ExitingCrouch;
		// A flat 600 ms cut prone_to_knees in half - hence "transitions toward
		// standing then jumps to crouch halfway through". Use the clip's own
		// authored length, same helper the entry already uses.
		const DWORD exitMs = toCrouch ?
			proneAnimDurationMs(g_proneExitDict, g_proneExitClip, 600, 2500) :
			600;
		const bool finished = now - g_proneStateAt >= exitMs;
		if (finished) finishProneExit(ped, toCrouch, "exit_complete");
		return;
	}
	if (g_proneState == ProneState::SettlingStanding) {
		return;
	}

	const float moveX = CONTROL_AXIS(0, joaat("INPUT_MOVE_LR"));
	const float moveY = CONTROL_AXIS(0, joaat("INPUT_MOVE_UD"));
	const float magnitude = (std::min)(1.0f, std::sqrt(moveX * moveX + moveY * moveY));
	const Hash aimControl = joaat("INPUT_AIM");
	const bool aimHeld = PAD::IS_CONTROL_PRESSED(0, aimControl) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, aimControl) ||
		PAD::IS_CONTROL_PRESSED(2, aimControl) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, aimControl) ||
		(GetAsyncKeyState(VK_RBUTTON) & 0x8000) != 0;
	const bool aiming = aimHeld || PLAYER::IS_PLAYER_FREE_AIMING(player) ||
		CAM::IS_AIM_CAM_ACTIVE();
	const bool wantMove = magnitude > 0.10f && !aiming;
	float proneTurnDelta = 0.0f;
	float proneTurnRequestedHeading = ENTITY_HEADING(ped);
	float proneTurnReadbackHeading = proneTurnRequestedHeading;
	const Hash wheel = joaat("INPUT_OPEN_WHEEL_MENU");
	const bool wheelOpen = PAD::IS_CONTROL_PRESSED(0, wheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, wheel) ||
		PAD::IS_CONTROL_PRESSED(2, wheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, wheel);
	// Weapon/satchel wheels reuse movement/look axes for selection. Disabling
	// those axes later in this function made the wheel appear to select a
	// handgun while GET_CURRENT_PED_WEAPON remained unarmed. Leave the crawl
	// task untouched and give the wheel all of its native inputs.
	// #195: grounded weapon handling does not exist yet, so rather than standing
	// Arthur up or letting him slide in a broken pose, prone REFUSES weapon
	// swapping and reloading outright. Swallow the controls every frame - the
	// wheel/satchel must never open, slot cycling must not fire, and reload is
	// dead. Aim and fire are left alone: they currently do nothing while prone,
	// and blocking them would also disable the head-tracking Lexer can see.
	// #195: with OneHandedWeapons on, the wheel and slot cycling are allowed
	// through so a pistol can actually be selected down here — the wheel handling
	// directly below already exists and was debugged for exactly this. RELOAD
	// stays dead in both modes: there is no authored face-down reload anywhere in
	// the game, and letting it fire is what stands him up mid-crawl.
	if (g_proneBlockWeaponActions || g_proneOneHandedWeapons) {
		static const Hash kProneBlockedAll[] = {
			joaat("INPUT_OPEN_WHEEL_MENU"), joaat("INPUT_OPEN_SATCHEL_MENU"),
			joaat("INPUT_SELECT_WEAPON"), joaat("INPUT_RELOAD"),
			joaat("INPUT_SELECT_NEXT_WEAPON"), joaat("INPUT_SELECT_PREV_WEAPON"),
			joaat("INPUT_TOGGLE_HOLSTER"), // was INPUT_HOLSTER_WEAPON: no such control
		};
		static const Hash kProneBlockedOneHanded[] = { joaat("INPUT_RELOAD") };
		for (int group = 0; group < 3; ++group) {
			if (g_proneOneHandedWeapons)
				for (Hash control : kProneBlockedOneHanded) DISABLE_CONTROL(group, control);
			else
				for (Hash control : kProneBlockedAll) DISABLE_CONTROL(group, control);
		}
	}
	// The wheel control does not read as a clean continuous press: the live trace
	// logged "wheel close" three times inside 3 seconds for ONE selection. Every
	// bounce re-entered this branch, so the selection was committed repeatedly and
	// never finished, and the walk clip below was orphaned each time. Latch the
	// wheel open across the gaps.
	if (wheelOpen) g_proneWheelSeenAt = now;
	const bool wheelHeld = g_proneWheelSeenAt &&
		now - g_proneWheelSeenAt <= (DWORD)g_proneWheelGraceMs;
	if (wheelHeld) {
		g_proneWheelWasOpen = true;
		// THE SLIDE. Nulling the clip pointer only made us FORGET which clip was
		// playing - it never stopped it. If the wheel opened mid-crawl, `walk` or
		// `walk_turn_r4` kept running with its root motion while this early return
		// skipped both the steering and the velocity pin, so he crawled off on his
		// own. The wheel also reuses the movement axes for selection, which is why
		// it read as fast travel in the direction of the last turn clip. Put him on
		// the idle clip, which has no root motion, and hold him still.
		if (g_proneLocoClip != kProneIdleClip) {
			playProneAnimation(ped, kProneCrawlDict, kProneIdleClip,
				2.0f, -1, 0x30000401, 0.0f);
			g_proneLocoClip = kProneIdleClip;
			g_proneLocoState = ProneLocoState::Idle;
		}
		Vector3 wheelVelocity = ENTITY_VELOCITY(ped);
		wheelVelocity.x = 0.0f;
		wheelVelocity.y = 0.0f;
		SET_ENTITY_VELOCITY(ped, wheelVelocity);
		return;
	}
	if (g_proneWheelWasOpen) {
		g_proneWheelWasOpen = false;
		g_proneWheelSeenAt = 0;
		const Hash selected = GET_CURRENT_WEAPON(ped);
		const bool selectedOneHanded = selected &&
			(WEAPON::_IS_WEAPON_PISTOL(selected) ||
			 WEAPON::_IS_WEAPON_REVOLVER(selected) ||
			 WEAPON::_IS_WEAPON_THROWABLE(selected));
		// Commit only the weapon class for which a face-down test exists.
		// prone_michael is a scripted full-body scene, not a generic weapon
		// bridge; using it here caused the invisible-rifle/frozen state. Clearing
		// all primary tasks for the draw window was just as unsafe because it
		// released the prone skeleton and let Arthur stand. Keep prone idle alive
		// and latch/reassert the selected one-handed weapon instead.
		if (g_proneOneHandedWeapons && selectedOneHanded) {
			g_proneEquipWeapon = selected;
			WEAPON::SET_CURRENT_PED_WEAPON(ped, selected, true, 0, false, false);
			g_proneEquipUntil = now + (DWORD)g_proneEquipHoldMs;
		} else if (selected && selected != joaat("WEAPON_UNARMED")) {
			// Longarms, bows and binoculars still have no accepted face-down rig.
			// Refuse the selection instead of exposing the rejected back-roll path
			// or leaving an invisible unsupported weapon attached.
			g_proneEquipWeapon = 0;
			g_proneEquipUntil = 0;
			WEAPON::SET_CURRENT_PED_WEAPON(ped, joaat("WEAPON_UNARMED"), true,
				0, false, false);
		}
		std::ostringstream equip;
		equip << "wheel close selected=0x" << std::hex << selected
			<< std::dec << " oneHanded=" << (selectedOneHanded ? 1 : 0)
			<< " assertWindowMs=" << g_proneEquipHoldMs;
		proneLog(equip.str());
	}
	if (now < g_proneEquipUntil) {
		// The full-body crawl task can reassert its authored unarmed state. Match
		// the reference mod's wheel-close SET_CURRENT_PED_WEAPON bridge, but do it
		// non-blockingly across the configured window while prone idle remains in
		// control of the body.
		if (g_proneEquipWeapon)
			WEAPON::SET_CURRENT_PED_WEAPON(ped, g_proneEquipWeapon, true,
				0, false, false);
		Vector3 drawVelocity = ENTITY_VELOCITY(ped);
		drawVelocity.x = 0.0f;
		drawVelocity.y = 0.0f;
		SET_ENTITY_VELOCITY(ped, drawVelocity);
		return;
	}
	if (g_proneEquipUntil) {
		g_proneEquipUntil = 0;
		g_proneEquipWeapon = 0;
	}
	const Hash attack = joaat("INPUT_ATTACK");
	const bool nativeAction = aiming ||
		PAD::IS_CONTROL_PRESSED(0, attack) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, attack);
	if (wheelOpen || nativeAction)
		g_proneActionResumeAt = now + 500;
	const Hash currentWeapon = GET_CURRENT_WEAPON(ped);
	const bool unarmed = !currentWeapon ||
		currentWeapon == joaat("WEAPON_UNARMED");
	const bool oneHanded = !unarmed &&
		(WEAPON::_IS_WEAPON_PISTOL(currentWeapon) ||
		 WEAPON::_IS_WEAPON_REVOLVER(currentWeapon) ||
		 WEAPON::_IS_WEAPON_THROWABLE(currentWeapon));
	const Hash weaponGroup = unarmed ? 0 :
		WEAPON::GET_WEAPONTYPE_GROUP(currentWeapon);
	const bool longarm = !unarmed &&
		(weaponGroup == joaat("GROUP_REPEATER") ||
		 weaponGroup == joaat("GROUP_RIFLE") ||
		 weaponGroup == joaat("GROUP_SNIPER") ||
		 weaponGroup == joaat("GROUP_SHOTGUN") ||
		 weaponGroup == joaat("GROUP_BOW"));
	const bool backRigRequested = (longarm && aimHeld) ||
		g_binocularsModeEngaged;
	const bool backRigActive =
		g_proneActionState == ProneActionState::RollingBack ||
		g_proneActionState == ProneActionState::BackAimIntro ||
		g_proneActionState == ProneActionState::BackAiming ||
		g_proneActionState == ProneActionState::BackAimOutro ||
		g_proneActionState == ProneActionState::RollingFront;

	// Rockstar authored no two-handed face-down aim set. Use the complete
	// face-down -> face-up -> aim -> face-down chain from the animation table
	// for longarms. Binoculars use the matching pistol-on-back rig so their
	// native forced-aim camera can remain active without a standing animation.
	// Disabled after the 2026-07-29 in-game test: fixed sweep clips do not
	// follow the reticle, Aim flickers while a scripted full-body task owns the
	// ped, and the resulting state repeatedly rolled Arthur through the ground.
	// Retain the decoded rig names for future native aim-task integration, but
	// never drive them as a timer-only animation state machine.
	const bool customBackRigEnabled = false;
	if (customBackRigEnabled && (backRigRequested || backRigActive)) {
		const bool requestedBinoRig = g_binocularsModeEngaged ||
			WEAPON::_IS_WEAPON_BINOCULARS(currentWeapon);
		const bool binoRig = backRigActive ?
			g_proneBackRigBino : requestedBinoRig;
		const char* backAimDict = binoRig ?
			kProneAimBackPistolDict : kProneAimBackRifleDict;
		if (g_proneActionState == ProneActionState::None &&
			proneDictReady(kProneRollBackDict) &&
			proneDictReady(backAimDict)) {
			g_proneActionState = ProneActionState::RollingBack;
			g_proneActionAt = now;
			g_proneActionWeapon = currentWeapon;
			g_proneBackRigBino = requestedBinoRig;
			playProneAnimation(ped, kProneRollBackDict, kProneRollBackClip,
				2.0f, -1, 0x10000410, 0.0f);
			g_proneLocoClip = nullptr;
			proneLog(binoRig ? "binocular roll to back" :
				"longarm roll to back");
		}
		if (g_proneActionState == ProneActionState::RollingBack &&
			now - g_proneActionAt >= proneAnimDurationMs(kProneRollBackDict,
				kProneRollBackClip, 250, 1800)) {
			g_proneActionState = ProneActionState::BackAimIntro;
			g_proneActionAt = now;
			playProneAnimation(ped, backAimDict, kProneAimBackIntro,
				2.0f, -1, 0x10000410, 0.0f);
			proneLog("on-back aim intro");
		}
		if (g_proneActionState == ProneActionState::BackAimIntro &&
			now - g_proneActionAt >= proneAnimDurationMs(backAimDict,
				kProneAimBackIntro, 200, 1500)) {
			g_proneActionState = ProneActionState::BackAiming;
			g_proneActionAt = now;
			playProneAnimation(ped, backAimDict, kProneAimBackLoop,
				2.0f, -1, 0x10000410, 0.0f);
			proneLog("on-back aim loop");
		}
		if (!backRigRequested &&
			g_proneActionState == ProneActionState::BackAiming) {
			g_proneActionState = ProneActionState::BackAimOutro;
			g_proneActionAt = now;
			playProneAnimation(ped, backAimDict, kProneAimBackOutro,
				2.0f, -1, 0x10000410, 0.0f);
			proneLog("on-back aim outro");
		}
		if (g_proneActionState == ProneActionState::BackAimOutro &&
			now - g_proneActionAt >= proneAnimDurationMs(backAimDict,
				kProneAimBackOutro, 200, 1500)) {
			g_proneActionState = ProneActionState::RollingFront;
			g_proneActionAt = now;
			playProneAnimation(ped, kProneRollFrontDict, kProneRollFrontClip,
				2.0f, -1, 0x10000410, 0.0f);
			proneLog("roll back to face-down");
		}
		if (g_proneActionState == ProneActionState::RollingFront &&
			now - g_proneActionAt >= proneAnimDurationMs(kProneRollFrontDict,
				kProneRollFrontClip, 250, 1800)) {
			g_proneActionState = ProneActionState::None;
			g_proneActionWeapon = 0;
			g_proneBackRigBino = false;
			g_proneLocoClip = nullptr;
			proneLog("on-back action complete");
		} else {
			Vector3 v = ENTITY_VELOCITY(ped);
			v.x = 0.0f;
			v.y = 0.0f;
			SET_ENTITY_VELOCITY(ped, v);
			return;
		}
	}

	// #195 EXPERIMENT (GroundedAimMode=1): hold the grounded one-handed pose as a
	// SECONDARY upper-body clip and never clear the native aim task, so Rockstar
	// keeps pointing the gun at the reticle underneath it. This is the one
	// mechanism the Worklog lists as untried; every previous attempt issued the
	// clip as a full-body task, which is precisely what stole the gun's tracking.
	// 0x20 is the SECONDARY bit on top of the usual 0x10000410 upper-body flags.
	if (g_proneGroundedAimMode == 1 && oneHanded && aimHeld &&
		proneDictReady(kProneAim1hDict)) {
		if (g_proneLocoClip != kProneAim1hLoop) {
			TASK::TASK_PLAY_ANIM(ped, kProneAim1hDict, kProneAim1hLoop,
				2.0f, 2.0f, -1, 0x10000430, 0.0f,
				FALSE, 0x02000000, FALSE, "", FALSE);
			g_proneLocoClip = kProneAim1hLoop;
			proneLog("grounded 1h aim as SECONDARY upper-body; native aim retained");
		}
		Vector3 aimVelocity = ENTITY_VELOCITY(ped);
		aimVelocity.x = 0.0f;
		aimVelocity.y = 0.0f;
		SET_ENTITY_VELOCITY(ped, aimVelocity);
		return;
	}
	if (g_proneLocoClip == kProneAim1hLoop && !aimHeld) {
		// The experiment owns only this secondary upper-body layer. Release it on
		// Aim-up so the sick weapon pose cannot remain welded over crawl/idle.
		TASK::CLEAR_PED_SECONDARY_TASK(ped);
		g_proneLocoClip = nullptr;
		proneLog("grounded 1h secondary aim released");
	}

	// Do not yield a one-handed aim to Rockstar's standing combat task. Drive
	// the exact grounded 1h intro/loop/outro used by Crawl N' Gun and leave Aim,
	// Attack and Reload readable so the weapon system can still do its work.
	// Kept OFF: re-enabling this reproduces the full-body build Lexer already
	// rejected in-game. See Worklog #195.
	const bool customOneHandAimEnabled = false;
	if (customOneHandAimEnabled && ((oneHanded && aimHeld) ||
		g_proneActionState != ProneActionState::None)) {
		const char* actionClip = nullptr;
		if (aimHeld && g_proneActionState == ProneActionState::None &&
			proneDictReady(kProneAim1hDict)) {
			g_proneActionState = ProneActionState::AimIntro;
			g_proneActionAt = now;
			g_proneActionWeapon = currentWeapon;
			actionClip = kProneAim1hIntro;
			playProneAnimation(ped, kProneAim1hDict, actionClip,
				2.0f, -1, 0x10000410, 0.0f);
			g_proneLocoClip = nullptr;
			proneLog("grounded 1h aim intro");
		}
		if (g_proneActionState == ProneActionState::AimIntro &&
			now - g_proneActionAt >= proneAnimDurationMs(kProneAim1hDict,
				kProneAim1hIntro, 150, 1200)) {
			g_proneActionState = ProneActionState::Aiming;
			g_proneActionAt = now;
			playProneAnimation(ped, kProneAim1hDict, kProneAim1hLoop,
				2.0f, -1, 0x10000410, 0.0f);
			proneLog("grounded 1h aim loop");
		}
		if (!aimHeld && (g_proneActionState == ProneActionState::AimIntro ||
			g_proneActionState == ProneActionState::Aiming)) {
			g_proneActionState = ProneActionState::AimOutro;
			g_proneActionAt = now;
			playProneAnimation(ped, kProneAim1hDict, kProneAim1hOutro,
				2.0f, -1, 0x10000410, 0.0f);
			proneLog("grounded 1h aim outro");
		}
		if (g_proneActionState == ProneActionState::AimOutro &&
			now - g_proneActionAt >= proneAnimDurationMs(kProneAim1hDict,
				kProneAim1hOutro, 150, 1200)) {
			g_proneActionState = ProneActionState::None;
			g_proneActionWeapon = 0;
			g_proneLocoClip = nullptr;
			proneLog("grounded 1h aim complete");
		} else {
			Vector3 v = ENTITY_VELOCITY(ped);
			v.x = 0.0f;
			v.y = 0.0f;
			SET_ENTITY_VELOCITY(ped, v);
			return;
		}
	}

	// Binocular access already owns its native camera/equip lifecycle. Do not
	// wrap it in prone roll clips; simply suspend crawl until it restores the
	// previous weapon, then resume idle on the next frame.
	const bool yieldToNativeAction = g_binocularsModeEngaged;

	// Crawl clips are full-body tasks. Clear one time when native equipment,
	// aiming, firing, throwing, or binocular use needs the skeleton; otherwise
	// weapon selection succeeds for a frame and the crawl task forces Arthur
	// straight back to unarmed. Restore prone idle after the native action ends.
	if (yieldToNativeAction) {
		if (!g_proneActionSuspended) {
			// Binocular access already cleared prone before equipping. Clearing
			// here would kill the binocular task we are specifically yielding to.
			if (!g_binocularsModeEngaged && g_proneTaskOwnsSkeleton)
				TASK::CLEAR_PED_TASKS(ped, true, false);
			g_proneTaskOwnsSkeleton = false;
			g_proneActionSuspended = true;
			g_proneLocoClip = nullptr;
			proneLog("yield crawl task to native equipment/action");
		}
		return;
	}
	if (g_proneActionSuspended) {
		g_proneActionSuspended = false;
		g_proneLocoClip = nullptr;
	}

	for (int group = 0; group < 3; ++group) {
		// FUN_18000f280 leaves LR/UD enabled. Rockstar must keep receiving the
		// held movement vector so its native locomotion graph can steer the root
		// mover as the camera turns. Disabling these axes locked held W to the
		// heading at which the scripted walk clip began.
		DISABLE_CONTROL(group, joaat("INPUT_SPRINT"));
		DISABLE_CONTROL(group, joaat("INPUT_JUMP"));
		DISABLE_CONTROL(group, joaat("INPUT_MELEE_ATTACK"));
	}

	// The reference crawl task owns the complete root transform. The rejected
	// controller also wrote coordinates, velocity, heading, pitch/roll and floor
	// height every frame; those competing owners caused the high-speed reverse
	// slide and pose corruption. Keep only readbacks here.
	const Vector3 proneFrameStart = ENTITY_COORDS(ped);
	proneTurnDelta = shortestHeadingDelta(ENTITY_HEADING(ped),
		CAM::GET_GAMEPLAY_CAM_ROT(2).z);
	const float frameDistance = cvLen(cvSub(proneFrameStart, g_proneLastPosition));
	if (frameDistance > 15.0f) {
		leaveProneImmediate(ped, g_proneSavedStealth, "teleport");
		return;
	}
	g_proneDriveSpeed = wantMove && dt > 0.0f ? frameDistance / dt : 0.0f;

	if (wantMove) {
		// The previous camera-relative repair only calculated and logged the yaw
		// error. It never changed the ped heading, so the authored root mover kept
		// the heading it had when `walk` began. Keep the reference crawl clips as
		// the only translation owner, but turn their base yaw toward the gameplay
		// camera at the configured bounded rate. This gives W the same camera-
		// relative contract as ordinary movement without adding coordinates,
		// velocity, floor placement, or a second displacement owner.
		const float currentHeading = ENTITY_HEADING(ped);
		proneTurnRequestedHeading = CAM::GET_GAMEPLAY_CAM_ROT(2).z;
		proneTurnDelta = shortestHeadingDelta(currentHeading,
			proneTurnRequestedHeading);
		const float maxTurn = (std::max)(0.0f, g_proneTurnSpeed * dt);
		const float turnStep = (std::max)(-maxTurn,
			(std::min)(maxTurn, proneTurnDelta));
		if (std::fabs(turnStep) > 0.05f)
			SET_ENTITY_HEADING(ped, currentHeading + turnStep);
		proneTurnReadbackHeading = ENTITY_HEADING(ped);

		auto directionDown = [](Hash control) {
			return PAD::IS_CONTROL_PRESSED(0, control) ||
				PAD::IS_DISABLED_CONTROL_PRESSED(0, control) ||
				PAD::IS_CONTROL_PRESSED(2, control) ||
				PAD::IS_DISABLED_CONTROL_PRESSED(2, control);
		};
		const bool left = directionDown(0x7065027D);   // INPUT_MOVE_LEFT_ONLY
		const bool right = directionDown(0xB4E465B4);  // INPUT_MOVE_RIGHT_ONLY
		const bool back = directionDown(0xD27782E3);   // INPUT_MOVE_DOWN_ONLY
		const char* walkClip = back ? kProneWalkBackwardClip :
			(left && !right ? kProneWalkLeftClip :
			(right && !left ? kProneWalkRightClip : kProneWalkClip));
		if (g_proneLocoClip != walkClip) {
			playReferenceCrawlAnimation(ped, walkClip, kProneMoveFlags);
			g_proneLocoClip = walkClip;
			proneLog(std::string("root-motion crawl clip=") + walkClip +
				" flags=0x30001C01");
		}
		const float rootRate = (std::max)(0.10f, (std::min)(3.0f,
			(g_proneCrawlSpeed / 0.85f) * g_proneMoveSpeedMultiplier));
		ENTITY::_SET_ENTITY_ANIM_SPEED(ped, kProneCrawlDict, walkClip, rootRate);
		g_proneLocoState = ProneLocoState::Moving;
	} else {
		if (g_proneLocoClip != kProneIdleClip) {
			playReferenceCrawlAnimation(ped, kProneIdleClip, kProneIdleFlags);
			g_proneLocoClip = kProneIdleClip;
			proneLog("root-motion crawl stopped clip=idle flags=0x30000401");
		}
		g_proneLocoState = ProneLocoState::Idle;
	}

	const Vector3 position = ENTITY_COORDS(ped);
	const float displacement = cvLen(cvSub(position, g_proneLastPosition));
	if (displacement > 15.0f) {
		leaveProneImmediate(ped, g_proneSavedStealth, "teleport");
		return;
	}
	// Crawling INTO deepening water is the same drowning as entering it prone.
	// Use the authored exit so he pushes himself up rather than snapping upright.
	if (g_proneState == ProneState::Prone && proneHeadWouldSubmerge(ped)) {
		campMessage("Too deep to stay down.");
		beginProneExit(ped, false, "water_too_deep");
		return;
	}
	g_proneLastPosition = position;

	if (now - g_proneLastTrace >= (g_proneTrace ? 250u : 5000u)) {
		g_proneLastTrace = now;
		const Vector3 tracePosition = ENTITY_COORDS(ped);
		Vector3 traceMovement = cvSub(tracePosition, g_proneTracePosition);
		traceMovement.z = 0.0f;
		const float traceMoveDistance = cvLen(traceMovement);
		const float cameraYaw = CAM::GET_GAMEPLAY_CAM_ROT(2).z;
		const float cameraRadians = cameraYaw * 0.0174532925f;
		const Vector3 cameraForward = {
			-std::sin(cameraRadians), std::cos(cameraRadians), 0.0f
		};
		const float movementCameraDot = traceMoveDistance > 0.001f ?
			cvDot(cvNorm(traceMovement), cameraForward) : 0.0f;
		std::ostringstream line;
		line << "state=" << proneStateName(g_proneState)
			<< " loco=" << (int)g_proneLocoState
			<< " clip=" << (g_proneLocoClip ? g_proneLocoClip : "-")
			<< " phase=" << proneAnimPhase(ped, kProneCrawlDict,
				g_proneLocoClip ? g_proneLocoClip : kProneIdleClip)
			<< " nativeProne=" << (PED::IS_PED_PRONE(ped) ? 1 : 0)
			<< " crouch=" << (GET_PED_CROUCH_MOVEMENT(ped) ? 1 : 0)
			<< " stealth=" << (PED::GET_PED_STEALTH_MOVEMENT(ped) ? 1 : 0)
			<< " input=" << moveX << "," << moveY
			// #170: the old trace could not answer "did he actually move", which
			// is the entire question. drive = what we command, moved = what the
			// world did with it (metres since the last trace line).
			<< " actualSpeed=" << g_proneDriveSpeed
			<< " moved=" << traceMoveDistance
			<< " movementCameraDot=" << movementCameraDot
			<< " cameraYaw=" << cameraYaw
			<< " pedHeading=" << ENTITY_HEADING(ped)
			<< " turnError=" << proneTurnDelta
			<< " turnRequested=" << proneTurnRequestedHeading
			<< " turnReadback=" << proneTurnReadbackHeading
			<< " aim=" << (aiming ? 1 : 0)
			<< " weapon=0x" << std::hex << GET_CURRENT_WEAPON(ped) << std::dec
			<< " crawlDict=" << (proneDictReady(kProneCrawlDict) ? 1 : 0);
		proneLog(line.str());
		g_proneTracePosition = tracePosition;
	}
}

static const char* climbStateName(ClimbState state) {
	switch (state) {
	case ClimbState::Grounded: return "grounded";
	case ClimbState::Grabbing: return "grabbing";
	case ClimbState::Climbing: return "climbing";
	case ClimbState::ToppingOut: return "topping_out";
	case ClimbState::Dismounting: return "dismounting";
	case ClimbState::Airborne: return "airborne";
	default: return "unknown";
	}
}

static void climbLog(const std::string& text) {
	// Gated by [Climbing] Trace, so INFO for the same reason as proneLog.
	if (!g_climbingTrace) return;
	gtLog("climbing", GT_INFO, text);
}

// #159: animation speed zero pauses a task on its current pose; it does not end
// the task. Stop the exact outgoing clip once on the input-release edge, then
// let the normal selector bind the idle grip. Never clear all tasks here.
static void stopClimbMotionOnRelease(Ped ped, DWORD now) {
	if (!g_climbAnimClip || !g_climbAnimDictInUse) return;
	g_climbReleaseDict = g_climbAnimDictInUse;
	g_climbReleaseClip = g_climbAnimClip;
	g_climbReleaseAuditAt = now;
	g_climbReleaseAuditPending = true;
	g_climbReleaseRetryCount = 0;
	TASK::STOP_ANIM_TASK(ped, g_climbReleaseDict, g_climbReleaseClip, -2.0f);
	std::ostringstream line;
	line << "release stop issued dict=" << g_climbReleaseDict
		<< " clip=" << g_climbReleaseClip;
	climbLog(line.str());
}

static void setClimbState(ClimbState next, const char* reason) {
	if (next == g_climbState) return;
	std::ostringstream line;
	line << climbStateName(g_climbState) << " -> " << climbStateName(next)
		<< " reason=" << reason;
	climbLog(line.str());
	g_climbState = next;
	g_climbStateAt = GetTickCount();
}

static void clearClimbProbes() {
	for (ClimbProbe& probe : g_climbProbes) {
		// Throwing away a live asynchronous shape test without ever reading it
		// leaks its slot in the engine's small shapetest pool, which several
		// other loaded ASIs share. Retrieve the result before discarding.
		if (probe.handle) {
			BOOL hit = FALSE;
			Vector3 end = {}, normal = {};
			Entity entity = 0;
			SHAPE_RESULT(probe.handle, &hit, &end, &normal, &entity);
		}
		probe = {};
	}
}

static bool climbEntityAllowed(Entity e) {
	if (!e) return true; // world collision
	if (ENTITY::IS_ENTITY_A_PED(e) || ENTITY::IS_ENTITY_A_VEHICLE(e)) return false;
	return ENTITY_SPEED(e) < 0.08f;
}

static bool climbAttached() {
	return g_climbState == ClimbState::Climbing ||
		g_climbState == ClimbState::Grabbing ||
		g_climbState == ClimbState::ToppingOut ||
		g_climbState == ClimbState::Dismounting;
}

// #169(e) REVERSE-MANTLE. Walking or sneaking off a climbable ledge should
// grab it, not step into thin air. It never could: the grab only ever probed
// the way he is FACING, and when you walk off an edge the surface you want
// is behind and below you. When this flag is set the same probe batch is
// fired backwards, which is the only direction that can find that face.
static bool g_climbScanReverse = false;
// This belongs to the in-flight/result batch, not the one-frame request flag.
// The resolver and entry gate must know that the returned surface came from
// the dedicated below-ledge reverse scan.
static bool g_climbProbeBatchReverse = false;
// #169(a) "HE IS STILL GOING INTO SLIDE MODE." The trace says why, and it is not
// the detector: the slide was SEEN on 262 frames and the grab fired on 3. On 228
// of those frames the probes reported no surface whatsoever. Every unattached
// probe is horizontal and aimed the way he is facing or looking, and a man
// sliding down scree is facing DOWNHILL - so the rays fly out over open air
// while the only climbable thing in the world, the slope he is on, is under his
// boots and behind him. He was never refused a grab; nothing was ever offered
// one. While slipping, aim the batch uphill and tilted down so it strikes the
// face he is actually on.
static bool g_climbScanSlideValid = false;
static Vector3 g_climbScanSlide = {};
static Vector3 climbScanDirection(Ped ped) {
	if (climbAttached()) return cvMul(g_climbNormal, -1.0f);
	if (g_climbScanSlideValid) return g_climbScanSlide;
	// Neither facing alone nor camera yaw alone acquired the mountain reliably:
	// while Rockstar's slide owns the ped the model can be turned well away from
	// the slope the player is looking at. Alternate between the two so a batch of
	// each is issued roughly every four frames instead of committing to one.
	const float yaw = (g_climbScanCamera ? CAM::GET_GAMEPLAY_CAM_ROT(2).z
		: ENTITY_HEADING(ped)) * 0.0174532925f;
	Vector3 forward = cvNorm(Vector3{ -std::sin(yaw), std::cos(yaw), 0.0f });
	// A reverse grab is defined by the ledge the player just walked off, not by
	// wherever the camera happens to face. Use actual horizontal travel while it
	// is observable, then fall back to the ped heading only at near-zero speed.
	if (g_climbScanReverse) {
		const Vector3 velocity = ENTITY_VELOCITY(ped);
		const Vector3 planar = { velocity.x, velocity.y, 0.0f };
		if (cvLen(planar) > 0.08f) forward = cvNorm(planar);
	}
	// A walked-off ledge is both behind and below the falling ped. Horizontal
	// reverse rays skim over its face as Arthur drops; tip them down so the same
	// batch can still acquire the wall during the short step-off window.
	return g_climbScanReverse ?
		cvNorm(cvAdd(cvMul(forward, -1.0f), Vector3{ 0.0f, 0.0f, -0.28f })) :
		forward;
}

static void beginClimbProbes(Ped ped) {
	const bool attached = climbAttached();
	g_climbProbeBatchReverse = !attached && g_climbScanReverse;
	const Vector3 base = attached ? g_climbAnchor : ENTITY_COORDS(ped);
	const Vector3 direction = climbScanDirection(ped);
	const float ordinaryHeights[6] = { 0.30f, 0.78f, 1.22f, 1.68f, 0.98f, 0.98f };
	// Once the feet have crossed a ledge, ordinary body-height rays mostly pass
	// over its top. Sample from below the root through torso height so the steep
	// vertical face can be proven while Arthur is still close enough to grab it.
	const float reverseHeights[6] = { -0.40f, 0.00f, 0.40f, 0.80f, 0.20f, 0.20f };
	const float* heights = g_climbProbeBatchReverse ? reverseHeights : ordinaryHeights;
	Vector3 scanRight = cvNorm(cvCross(Vector3{ 0.0f, 0.0f, 1.0f }, direction));
	// Attached probes start clear of the body and must reach well past the fitted
	// contact plane; the old 0.23 m of overshoot fell short of every irregular
	// bulge and dropped the contact within a quarter second of grabbing.
	const float standoff = g_climbSurfaceOffset + 0.35f;
	for (int i = 0; i < 6; ++i) {
		Vector3 start = base;
		start.z += heights[i];
		if (i == 4) start = cvAdd(start, cvMul(scanRight, -0.32f));
		if (i == 5) start = cvAdd(start, cvMul(scanRight, 0.32f));
		if (attached) start = cvAdd(start, cvMul(g_climbNormal, standoff));
		// A downward slide probe has to cross the body's own height before it can
		// reach the slope, so the ordinary grab reach cannot find it.
		const float reach = attached ? (standoff + g_climbProbeTolerance + 0.90f) :
			(g_climbScanSlideValid ? (std::max)(g_climbGrabDistance, 2.20f)
				: g_climbGrabDistance);
		Vector3 end = cvAdd(start, cvMul(direction, reach));
		g_climbProbes[i].handle = START_LOS_PROBE(start, end, 511, ped);
		g_climbProbes[i].hit = false;
		g_climbProbes[i].bodyHeight = heights[i];
	}
	if (!attached) g_climbScanCamera = !g_climbScanCamera;
}

static bool resolveClimbProbes(int* hitCount, Vector3* point, Vector3* normal,
	float* contactHeight) {
	bool anyPending = false;
	int hits = 0;
	Vector3 points = {}, normals = {};
	float heights = 0.0f;
	for (ClimbProbe& probe : g_climbProbes) {
		if (!probe.handle) continue;
		BOOL hit = FALSE;
		Vector3 end = {}, surface = {};
		Entity entity = 0;
		const int status = SHAPE_RESULT(probe.handle, &hit, &end, &surface, &entity);
		if (status == 1) { anyPending = true; continue; }
		probe.handle = 0;
		probe.hit = hit != FALSE && climbEntityAllowed(entity);
		probe.point = end;
		probe.normal = cvNorm(surface);
		probe.entity = entity;
	}
	if (anyPending) return false;
	Entity fittedEntity = 0;
	Vector3 firstNormal = {};
	bool haveFirst = false;
	for (const ClimbProbe& probe : g_climbProbes) {
		if (!probe.hit) continue;
		if (!haveFirst) {
			fittedEntity = probe.entity;
			firstNormal = probe.normal;
			haveFirst = true;
		} else if (probe.entity != fittedEntity ||
			cvDot(firstNormal, probe.normal) < 0.82f) {
			// Never average a post, roof, sign, and wall into one imaginary
			// climbable plane.
			continue;
		}
		++hits;
		points = cvAdd(points, probe.point);
		normals = cvAdd(normals, probe.normal);
		heights += probe.bodyHeight;
	}
	*hitCount = hits;
	if (hits) {
		const Vector3 fitNormal = cvNorm(normals);
		const Vector3 centroid = cvMul(points, 1.0f / hits);
		// #169(a) HANDS AND FEET CLIPPING THROUGH IRREGULAR SURFACES.
		// This used to hand back the AVERAGE of every contact point. On
		// anything that is not a flat wall - a bulge, a jutting rock, a
		// buttress - the average plane sits INSIDE the part that sticks out,
		// so the body is placed too close to it and whichever limb is over the
		// bulge goes straight through. Averaging can only ever be right on a
		// flat face, which is exactly the case that never looked broken.
		// Lexer asked for the real contact points so he is always touching
		// against the surface. The honest form of that with six probes is to
		// stand off from the MOST PROTRUDING contact rather than the mean one:
		// project every hit onto the fitted normal and keep the one nearest the
		// player. Then the closest piece of rock sets the distance and nothing
		// behind it can penetrate. The averaged normal is still what orients
		// him, so the pose stays stable instead of snapping to each bump.
		float furthest = -1e9f;
		Vector3 nearestPoint = centroid;
		for (const ClimbProbe& probe : g_climbProbes) {
			if (!probe.hit || probe.entity != fittedEntity) continue;
			if (cvDot(firstNormal, probe.normal) < 0.82f) continue;
			const float along = cvDot(probe.point, fitNormal);
			if (along > furthest) { furthest = along; nearestPoint = probe.point; }
		}
		// Keep the centroid's position ALONG the face and take only the
		// standoff distance from the protruding contact, so he does not slide
		// sideways onto whichever bump happened to win.
		const float lift = cvDot(cvSub(nearestPoint, centroid), fitNormal);
		*point = cvAdd(centroid, cvMul(fitNormal, (std::max)(0.0f, lift)));
		*normal = fitNormal;
		*contactHeight = heights / hits;
	}
	return true;
}

static bool climbEligible(Player player, Ped ped, bool unavailable, bool mission) {
	return g_climbingEnabled && ped && !unavailable && !mission &&
		!customProneActive() &&
		PLAYER_CONTROL_ON(player) && !ENTITY_INTERIOR(ped) &&
		!IS_PED_ON_MOUNT(ped) && !GET_VEHICLE(ped) && !IS_PED_SWIMMING(ped) &&
		!IS_PED_RAGDOLL(ped) && !IS_PED_MELEE(ped) &&
		!PED::_IS_PED_CLIMBING_LADDER(ped);
}

// Physics ownership is all-or-nothing: while attached the ped is frozen and
// driven from g_climbAnchor, so it must be released on every exit path,
// including leaps, top-out and the ineligible/mission bail-outs.
static void releaseClimbPhysics(Ped ped, bool snapToGround) {
	if (!g_climbPhysicsOwned) return;
	g_climbPhysicsOwned = false;
	g_climbAnimClip = nullptr;
	g_climbAnimDictInUse = nullptr;
	g_climbReverseGrab = false;
	g_climbReverseAnimStarted = false;
	g_climbReverseDurationMs = 0;
	g_climbStamina.reset();
	if (!ped) return;
	if (!snapToGround) {
		// A leap must keep its arc. Standing him up and dropping him onto the
		// ground under the wall is only correct for an ordinary dismount.
		SET_ENTITY_ROTATION(ped, { 0.0f, 0.0f, ENTITY_HEADING(ped) });
		PED::SET_PED_CAN_RAGDOLL(ped, TRUE);
		return;
	}
	// Handing physics back while Arthur was still pitched into the rock let the
	// solver resolve the interpenetration by ejecting him through the world at
	// lethal speed. Stand him upright, back him clear of the surface along its
	// normal, and drop him onto valid ground before unfreezing.
	Vector3 safe = cvAdd(g_climbAnchor, cvMul(g_climbNormal, 0.30f));
	float groundZ = safe.z;
	// The old band only accepted ground BELOW the anchor. Coming down a face the
	// anchor usually ends slightly under the terrain, so the snap was skipped,
	// he was released inside the ground, and the solver ejected him upward -
	// the sink-then-bounce. Accept ground above the anchor too.
	if (GROUND_Z(safe, &groundZ) && groundZ <= safe.z + 2.00f &&
		groundZ >= safe.z - 2.50f)
		safe.z = groundZ + 0.05f;
	SET_ENTITY_ROTATION(ped, { 0.0f, 0.0f, ENTITY_HEADING(ped) });
	SET_COORDS_NO_OFFSET(ped, safe);
	PED::SET_PED_CAN_RAGDOLL(ped, TRUE);
	SET_ENTITY_VELOCITY(ped, {});
}

static void attachClimbPhysics(Ped ped, const ClimbContact& contact) {
	g_climbNormal = contact.normal;
	g_climbPoint = contact.point;
	g_climbContactHeight = contact.height;
	g_climbAnchor = climbRootFromContact(contact.point, contact.normal,
		contact.height, g_climbSurfaceOffset);
	g_climbAttachFrom = ENTITY_COORDS(ped);
	g_climbLastContactAt = GetTickCount();
	clearClimbProbes();
	TASK::CLEAR_PED_TASKS(ped, true, false);
	SET_ENTITY_VELOCITY(ped, {});
	PED::SET_PED_CAN_RAGDOLL(ped, FALSE);
	// Full UFCO decompilation proves it never freezes the player; its sole
	// FREEZE_ENTITY_POSITION call applies to spawned treasure objects. The
	// climbing loop owns coordinates/heading every frame while leaving the ped
	// task and animation system live.
	g_climbStamina.begin(PLAYER::PLAYER_ID());
	g_climbGripReady = false;
	g_climbGripAt = GetTickCount();
	g_climbPhysicsOwned = true;
	g_climbMotion = ClimbMotion::Idle;
	g_climbSettleFrom = ClimbMotion::Idle;
	g_climbMotionAt = GetTickCount();
	g_climbReleaseAuditPending = false;
	g_climbTopOutBlockedUntilRelease = false;
	g_climbLateralAttemptAt = 0;
	g_climbLateralDirection = ClimbMotion::Idle;
	STREAMING::REQUEST_ANIM_DICT(kClimbAnimDict);
	STREAMING::REQUEST_ANIM_DICT(kClimbLedgeDict);
	if (g_climbReverseGrab) {
		STREAMING::REQUEST_ANIM_DICT(kClimbReverseDict);
	} else if (STREAMING::HAS_ANIM_DICT_LOADED(kClimbAnimDict)) {
		TASK::TASK_PLAY_ANIM(ped, kClimbAnimDict, kClimbEnter,
			3.0f, -2.0f, 650, 0, 0.0f, FALSE, 0, FALSE, "", FALSE);
		g_climbAnimClip = kClimbEnter;
		g_climbAnimDictInUse = kClimbAnimDict;
	}
}

static void leaveClimbing(Ped ped, const char* reason, bool clearTasks) {
	releaseClimbPhysics(ped, true);
	if (g_climbState == ClimbState::Grounded) {
		g_climbManualPending = false;
		g_climbSlipAt = 0;
		g_climbNativeTraversalAt = 0;
		return;
	}
	if (clearTasks) TASK::CLEAR_PED_TASKS(ped, true, false);
	clearClimbProbes();
	g_climbCache.valid = false;
	g_climbProtectedCore = -1;
	g_climbManualPending = false;
	g_climbSlipAt = 0;
	g_climbNativeTraversalAt = 0;
	g_climbReleaseAuditPending = false;
	g_climbTopOutBlockedUntilRelease = false;
	g_climbLateralAttemptAt = 0;
	g_climbLateralDirection = ClimbMotion::Idle;
	setClimbState(ClimbState::Grounded, reason);
}

static void updateClimbing(Player player, Ped ped, DWORD now, bool unavailable, bool mission) {
	static DWORD previous = now;
	float dt = (now - previous) * 0.001f;
	previous = now;
	if (dt <= 0.0f || dt > 0.10f) dt = 0.016f;

	const bool eligible = climbEligible(player, ped, unavailable, mission);
	if (g_climbingTrace && now - g_climbHeartbeatAt >= 5000) {
		g_climbHeartbeatAt = now;
		std::ostringstream heartbeat;
		heartbeat << "heartbeat state=" << climbStateName(g_climbState)
			<< " eligible=" << (eligible ? 1 : 0)
			<< " unavailable=" << (unavailable ? 1 : 0)
			<< " mission=" << (mission ? 1 : 0)
			<< " physicsOwned=" << (g_climbPhysicsOwned ? 1 : 0)
			<< " motion=" << (int)g_climbMotion;
		climbLog(heartbeat.str());
	}
	if (!eligible) {
		leaveClimbing(ped, mission ? "mission" : "ineligible", true);
		return;
	}

	const float moveX = CONTROL_AXIS(0, joaat("INPUT_MOVE_LR"));
	const float moveY = CONTROL_AXIS(0, joaat("INPUT_MOVE_UD"));
	const float inputMagnitude = (std::min)(1.0f, std::sqrt(moveX * moveX + moveY * moveY));
	if (g_climbTopOutBlockedUntilRelease && moveY >= -0.10f)
		g_climbTopOutBlockedUntilRelease = false;
	const bool sprint = PAD::IS_CONTROL_PRESSED(0, joaat("INPUT_SPRINT")) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, joaat("INPUT_SPRINT"));
	const bool jump = PAD::IS_CONTROL_JUST_PRESSED(0, joaat("INPUT_JUMP")) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, joaat("INPUT_JUMP"));
	// A top-out mover/solver impulse is never player-authored. The old code had
	// a cooldown variable but never assigned it, so it neither prevented an
	// immediate re-grab nor contained the lethal launch seen in the #97 trace.
	if (g_climbState == ClimbState::Grounded && g_climbTopOutAt &&
		now - g_climbTopOutAt < 500) {
		const Vector3 settleVelocity = ENTITY_VELOCITY(ped);
		if (settleVelocity.z > 1.0f || cvLen(settleVelocity) > 3.0f)
			SET_ENTITY_VELOCITY(ped, {});
	}
	const bool pushing = moveY < -0.35f;
	const bool airborne = IS_PED_FALLING(ped) || ENTITY::IS_ENTITY_IN_AIR(ped, 0);
	// #113: railings and uneven collision can report IS_ENTITY_IN_AIR for a
	// frame while Arthur is still effectively grounded.  The old midair gate
	// accepted that transient immediately, so merely running forward beside a
	// rail could hand the ped to the climbing owner and snap him onto its plane.
	// A real fall provides both sustained airborne state and meaningful ground
	// clearance; wait for those facts before allowing an automatic wall grab.
	static DWORD airborneSince = 0;
	if (g_climbState == ClimbState::Grounded && airborne) {
		if (!airborneSince) airborneSince = now;
	} else {
		airborneSince = 0;
	}
	const DWORD airborneAge = airborneSince && now >= airborneSince ?
		now - airborneSince : 0;
	const bool committedAirborne = airborneAge >= 160 &&
		HEIGHT_ABOVE_GROUND(ped) >= 0.35f;
	const bool nativeSliding = invoke<BOOL>(0xD6740E14E4CEFC0B, ped) != 0;
	// The live #169 trace proves the native flag flickers during one physical
	// slide. The old code cleared this latch on the false frame, then armed a new
	// "prequalified" episode from a contact found after the slide had begun. It
	// later teleported Arthur into climbing on that new surface. A slide episode
	// now survives gaps shorter than 500 ms, can arm only while genuinely
	// Grounded, and owns a copy of the contact that existed before its first
	// frame. It cannot re-arm while our climbing owner is active.
	const bool newSlideEpisode = !g_climbSlideLastSeenAt ||
		now - g_climbSlideLastSeenAt > 500;
	if (nativeSliding) {
		if (g_climbState == ClimbState::Grounded && newSlideEpisode) {
			g_climbSlideStartedAt = now;
			g_climbSlidePrequalified = g_climbCache.valid &&
				now - g_climbCache.at <= 400;
			g_climbSlideContact = g_climbSlidePrequalified ?
				g_climbCache : ClimbContact{};
		}
		g_climbSlideLastSeenAt = now;
	} else if (g_climbSlideLastSeenAt &&
		now - g_climbSlideLastSeenAt > 500) {
		g_climbSlideStartedAt = 0;
		g_climbSlideLastSeenAt = 0;
		g_climbSlidePrequalified = false;
		g_climbSlideContact = {};
	}
	// #169(e): remember the moment he left the ground, so a walk-off can be
	// told apart from a long fall. Only a fresh step-off gets a reverse grab.
	static DWORD lastGroundedAt = 0;
	if (!airborne) lastGroundedAt = now;
	const bool justSteppedOff = airborne && lastGroundedAt &&
		now - lastGroundedAt <= 650;
	const Vector3 velocity = ENTITY_VELOCITY(ped);
	const Vector3 intended = climbScanDirection(ped);
	const float forwardSpeed = velocity.x * intended.x + velocity.y * intended.y;
	// #119: downward velocity is normal while walking down a tiny rock or step.
	// Treating every grounded Z drop plus horizontal movement as an uncontrolled
	// slide made ordinary traversal eligible for coordinate-owning climbing; a
	// cached rock plane then pulled Arthur back into its climbing animation.
	// The inferred fallback is safe only when the player is actively pushing
	// into the face yet making no uphill progress (or moving backwards). A real
	// Rockstar sliding task remains handled independently by `nativeSliding`.
	const bool maybeSlipping = !airborne && pushing &&
		(forwardSpeed < -0.08f ||
			(velocity.z < -0.30f && forwardSpeed < 0.12f));

	// Six asynchronous shape tests every other frame, permanently, was pure
	// waste and put constant pressure on a shapetest pool shared with the other
	// loaded ASIs. The ground gate can only fire while sliding, airborne, or
	// resolving a jump, so probe only then and no faster than every 80 ms.
	const bool attachedNow = climbAttached() || g_climbState == ClimbState::Airborne;
	// Pre-resolve the face while the player is pressing into it. Starting the
	// first asynchronous probe only after Rockstar had already entered its slide
	// task guaranteed the visible slide-then-glitch transition reported in #97.
	const bool wantProbes = attachedNow || pushing || nativeSliding || airborne ||
		maybeSlipping || g_climbManualPending;

	bool probesActive = false;
	for (const ClimbProbe& probe : g_climbProbes) if (probe.handle) { probesActive = true; break; }
	if (!probesActive && wantProbes && (attachedNow || now - g_climbProbeAt >= 80)) {
		g_climbProbeAt = now;
		// Fire this batch backwards during the step-off window so the ledge he
		// just walked off can actually be seen; forwards the rest of the time.
		// Manual W+Jump must only inspect the wall in front. Previously a one-frame
		// airborne transition also qualified as a step-off, firing this batch behind
		// Arthur and caching the opposite building before manual-pending was latched.
		g_climbScanReverse = justSteppedOff && !jump && !g_climbManualPending &&
			!climbAttached();
		// While he is being carried down a slope, point the batch UPHILL (against
		// the way he is being dragged) and tilt it down into the face, which is
		// the only aim that can see the ground he is sliding on. Facing and camera
		// yaw both look downhill at that moment and always will.
		g_climbScanSlideValid = false;
		if (!climbAttached() && (nativeSliding || maybeSlipping)) {
			Vector3 flat = { velocity.x, velocity.y, 0.0f };
			Vector3 uphill = cvLen(flat) > 0.25f ? cvMul(cvNorm(flat), -1.0f)
				: cvMul(climbScanDirection(ped), -1.0f);
			// ~40 degrees below horizontal: shallow enough to still reach a near
			// vertical face, steep enough to strike a 45-60 degree scree slope.
			g_climbScanSlide = cvNorm(cvAdd(cvMul(uphill, 0.77f),
				Vector3{ 0.0f, 0.0f, -0.64f }));
			g_climbScanSlideValid = true;
		}
		beginClimbProbes(ped);
		g_climbScanReverse = false;
		g_climbScanSlideValid = false;
	}

	int hits = 0;
	Vector3 point = {}, normal = {};
	float contactHeight = g_climbContactHeight;
	const bool probesReady = resolveClimbProbes(&hits, &point, &normal,
		&contactHeight);
	const float maxNormalZ = std::cos(g_climbMinSurfaceAngle * 0.0174532925f);
	// Entry needs a continuous body-height plane. One hit admitted signs, roof
	// edges and overhangs; attached traversal tolerates one temporarily missing
	// contact without inventing a surface from a lone point.
	const int requiredHits = climbAttached() ? 2 :
		(g_climbProbeBatchReverse ? 2 : 3);
	const bool steepSurface = probesReady && hits >= requiredHits &&
		normal.z >= -0.15f && normal.z <= maxNormalZ;
	if (steepSurface) {
		g_climbCache.valid = true;
		g_climbCache.point = point;
		g_climbCache.normal = normal;
		g_climbCache.height = contactHeight;
		g_climbCache.at = now;
	}
	// A cached contact belongs to the place where it was observed. Never allow a
	// later jump into foliage to reuse a previous building's anchor.
	if (g_climbCache.valid && !climbAttached() &&
		cvLen(cvSub(ENTITY_COORDS(ped), g_climbCache.point)) > g_climbGrabDistance + 2.0f)
		g_climbCache.valid = false;
	// Two frames of probe latency must not read as "no wall". Entry and the
	// attached fit both work from the cache so a pending batch is invisible.
	const bool contactFresh = g_climbCache.valid && now - g_climbCache.at <= 400;

	if (g_climbState == ClimbState::Grounded) {
		const bool nativeTraversal = PED::IS_PED_CLIMBING(ped) || PED::IS_PED_VAULTING(ped);
		// Rockstar's private sliding flag does not cover every ordinary mountain
		// slip. Detect the observable equivalent: the player is pushing uphill
		// against a steep sloped contact but is being carried backward/downhill.
		const bool slideEpisodeActive = g_climbSlideStartedAt &&
			g_climbSlideLastSeenAt && now - g_climbSlideLastSeenAt <= 500;
		// Inferred loss of footing is useful only before Rockstar owns a slide.
		// Never let a one-frame false native flag turn the same visible slide into
		// the separate detected_slipping entry path.
		const bool slopedContact = contactFresh &&
			g_climbCache.normal.z > 0.05f && !slideEpisodeActive;
		const bool losingFooting = maybeSlipping && slopedContact;
		if (nativeSliding || losingFooting) {
			if (!g_climbSlipAt) g_climbSlipAt = now;
		} else {
			g_climbSlipAt = 0;
		}
		// Never steal a slide late. A face resolved only after the native slide
		// started produces exactly the delayed state swap #97 reports. Automatic
		// takeover is allowed only when the pre-warmed cache already knew the face;
		// otherwise this slide stays completely native and a later jump remains the
		// explicit way to grab it.
		const bool samePreSlideFace = g_climbSlideContact.valid &&
			cvLen(cvSub(g_climbCache.point, g_climbSlideContact.point)) <= 0.20f &&
			cvDot(g_climbCache.normal, g_climbSlideContact.normal) >= 0.97f;
		const bool slidePrequalified = nativeSliding && g_climbSlideStartedAt &&
			g_climbSlidePrequalified && contactFresh && samePreSlideFace &&
			now == g_climbSlideStartedAt;
		// The inferred slipping path already has a pre-warmed, steep contact. Waiting
		// another 140 ms let Rockstar visibly enter its slide before we attached,
		// producing the exact slide-then-glitch transition. Take it at onset.
		const bool sliding = slidePrequalified || losingFooting;

		if (jump && pushing) {
			// Let the real Jump action reach Rockstar first. Only take ownership
			// if its ordinary vault/mantle system has still not engaged.
			g_climbManualPending = true;
			g_climbManualAt = now;
			g_climbNativeTraversalAt = 0;
			climbLog("manual candidate: waiting for native traversal");
		}
		if (g_climbManualPending && nativeTraversal) {
			if (!g_climbNativeTraversalAt) g_climbNativeTraversalAt = now;
			// Ignore a transient one-frame climbing/vaulting report from the
			// failed Jump attempt. Yield only when native traversal persists.
			if (now - g_climbNativeTraversalAt >= 140)
				g_climbManualPending = false;
		} else if (!nativeTraversal) {
			g_climbNativeTraversalAt = 0;
		}
		if (g_climbManualPending && now - g_climbManualAt > 1100)
			g_climbManualPending = false;
		const bool failedNativeJump = g_climbManualPending &&
			now - g_climbManualAt >= 340 && !nativeTraversal;
		// Falling past a cliff must not silently attach; midair contact is only
		// taken when the player is actively steering into the surface.
		const bool topOutCooldown = g_climbTopOutAt &&
			now - g_climbTopOutAt < 1800;
		// #169(e): a walk-off is a grab too. `pushing` means steering INTO the
		// surface, which is never true when you stroll off a ledge - the wall
		// is behind you. A fresh step-off with a climbable face found by the
		// reverse probe counts on its own.
		const bool walkOrSneak = !IS_PED_RUNNING(ped) && !IS_PED_SPRINTING(ped);
		const bool walkOffGrabReady = justSteppedOff && g_climbProbeBatchReverse &&
			walkOrSneak && airborneAge >= 70 && HEIGHT_ABOVE_GROUND(ped) >= 0.12f;
		const bool midairGrab = committedAirborne &&
			!g_climbManualPending && !topOutCooldown && pushing ||
			!g_climbManualPending && !topOutCooldown && walkOffGrabReady;

		// Only trace frames that could matter. The old unconditional 4 Hz stream
		// wrote a line (opening and closing the log file each time) for every
		// second of ordinary walking around.
		const bool traceWorthy = wantProbes || contactFresh || jump || nativeTraversal;
		if (g_climbingTrace && traceWorthy && now - g_climbGroundTraceAt >= 250) {
			g_climbGroundTraceAt = now;
			std::ostringstream line;
			line << "ground hits=" << hits
				<< " ready=" << (probesReady ? 1 : 0)
				<< " steep=" << (steepSurface ? 1 : 0)
				<< " fresh=" << (contactFresh ? 1 : 0)
				<< " cacheAge=" << (g_climbCache.valid ? now - g_climbCache.at : 0)
				<< " normal=" << g_climbCache.normal.x << "," << g_climbCache.normal.y
				<< "," << g_climbCache.normal.z
				<< " input=" << moveX << "," << moveY
				<< " jump=" << (jump ? 1 : 0)
				<< " airborne=" << (airborne ? 1 : 0)
				<< " airborneAge=" << airborneAge
				<< " groundClearance=" << HEIGHT_ABOVE_GROUND(ped)
				<< " nativeSlide=" << (nativeSliding ? 1 : 0)
				<< " losingFooting=" << (losingFooting ? 1 : 0)
				<< " forwardSpeed=" << forwardSpeed
				<< " velocityZ=" << velocity.z
				<< " nativeTraversal=" << (nativeTraversal ? 1 : 0)
				<< " pending=" << (g_climbManualPending ? 1 : 0)
				<< " pendingAge=" << (g_climbManualPending ? now - g_climbManualAt : 0);
			climbLog(line.str());
		}
		if (contactFresh && (sliding || failedNativeJump || midairGrab) &&
			GET_STAMINA_BAR(player) > 1.0f) {
			g_climbProtectedCore = GET_CORE(ped, 1);
			setClimbState(ClimbState::Grabbing, sliding ?
				(nativeSliding ? "vanilla_sliding" : "detected_slipping") :
				(failedNativeJump ? "native_jump_failed" :
					(walkOffGrabReady ? "reverse_mantle" : "midair_contact")));
			g_climbManualPending = false;
			g_climbReverseGrab = midairGrab && walkOffGrabReady;
			g_climbReverseAnimStarted = false;
			g_climbReverseDurationMs = 0;
			// A native-slide entry uses only the contact copied before that slide.
			// The other explicit entry paths use the current verified contact.
			attachClimbPhysics(ped,
				slidePrequalified ? g_climbSlideContact : g_climbCache);
		}
		return;
	}

	if (g_climbState == ClimbState::Airborne) {
		// Re-grabbing 180 ms after a wall jump, while still only 0.3 m off the
		// face, meant the leap read as a one-frame flicker into falling and then
		// straight back onto the wall. Require real time AND real distance.
		const float leapTravel = cvLen(cvSub(ENTITY_COORDS(ped), g_climbLeapFrom));
		const bool leapClear = !g_climbLeapAt || (now - g_climbLeapAt >= 650 &&
			leapTravel >= 1.20f);
		if (steepSurface && leapClear && now - g_climbStateAt > 180 &&
			GET_STAMINA_BAR(player) > 1.0f) {
			g_climbProtectedCore = GET_CORE(ped, 1);
			g_climbReverseGrab = false;
			setClimbState(ClimbState::Grabbing, "airborne_regrab");
			attachClimbPhysics(ped, g_climbCache);
		} else if (!IS_PED_FALLING(ped) && !ENTITY::IS_ENTITY_IN_AIR(ped, 0)) {
			leaveClimbing(ped, "landed", false);
		}
		return;
	}
	if (g_climbState == ClimbState::ToppingOut) {
		// #160: do not release Arthur before the native mantle accepts him. The
		// previous path released physics immediately, let him fall for 1.2 seconds,
		// then teleported him to g_climbTopOutTarget when TASK_CLIMB never started.
		// Keep the already-owned lip for a bounded acceptance window and release
		// only after the live climb/vault postcondition appears.
		const bool nativeTraversal = PED::IS_PED_CLIMBING(ped) ||
			PED::IS_PED_VAULTING(ped);
		const DWORD topOutAge = now - g_climbStateAt;
		const int taskStatus = TASK::GET_SCRIPT_TASK_STATUS(ped,
			joaat("SCRIPT_TASK_CLIMB"), TRUE);
		// natives.json resolves status 1 as PERFORMING_TASK. It is the task
		// manager's acceptance postcondition and avoids deadlocking a valid mantle
		// behind our lip pin before IS_PED_CLIMBING becomes visible.
		// Task status 1 only means the task manager accepted the request. It does
		// not prove the visible mantle has begun. Keep the lip until Rockstar's
		// own climbing/vaulting predicate proves that ownership really transferred.
		const bool visibleTraversal = nativeTraversal;
		if (visibleTraversal && g_climbPhysicsOwned) {
			g_climbTopOutBlockedUntilRelease = false;
			releaseClimbPhysics(ped, false);
			SET_ENTITY_VELOCITY(ped, {});
			std::ostringstream accepted;
			accepted << "native top-out accepted ageMs=" << topOutAge
				<< " taskStatus=" << taskStatus
				<< " nativeTraversal=" << (nativeTraversal ? 1 : 0);
			climbLog(accepted.str());
		}
		if (nativeTraversal) g_climbNativeTopOutObserved = true;
		const bool taskTerminal = taskStatus == 7 || taskStatus == 8;
		if (g_climbPhysicsOwned && !taskTerminal && topOutAge < 1200) {
			SET_COORDS_NO_OFFSET_ALIGNED(ped, g_climbAnchor);
			SET_ENTITY_VELOCITY(ped, {});
			if (now - g_climbNativeTopOutTraceAt >= 100) {
				g_climbNativeTopOutTraceAt = now;
				std::ostringstream pending;
				pending << "native top-out pending ageMs=" << topOutAge
					<< " taskStatus=" << taskStatus
					<< " nativeTraversal=0 physicsOwned="
					<< (g_climbPhysicsOwned ? 1 : 0);
				climbLog(pending.str());
			}
			return;
		}
		if (g_climbPhysicsOwned) {
			TASK::CLEAR_PED_TASKS(ped, true, false);
			g_climbNativeTopOutStarted = false;
			g_climbTopOutBlockedUntilRelease = true;
			g_climbMotion = ClimbMotion::Idle;
			g_climbAnimClip = nullptr;
			g_climbAnimDictInUse = nullptr;
			g_climbLastContactAt = now;
			setClimbState(ClimbState::Climbing, "native_top_out_rejected_retained");
			std::ostringstream rejected;
			rejected << "native top-out rejected; retained lip taskStatus="
				<< taskStatus << " physicsOwned=" << (g_climbPhysicsOwned ? 1 : 0);
			climbLog(rejected.str());
			return;
		}
		const bool nativeComplete = !nativeTraversal &&
			(g_climbNativeTopOutObserved || taskStatus == 8);
		if (nativeComplete && topOutAge >= 250) {
			g_climbNativeTopOutStarted = false;
			g_climbNativeTopOutObserved = false;
			g_climbTopOutAt = now;
			setClimbState(ClimbState::Grounded, "native_top_out_complete");
		} else if (!g_climbPhysicsOwned && topOutAge >= 5000) {
			// A task that genuinely started but never completed yields at the live
			// position. Never replace the stalled native with a delayed coordinate
			// snap to the roof.
			TASK::CLEAR_PED_TASKS(ped, true, false);
			SET_ENTITY_VELOCITY(ped, {});
			PED::SET_PED_CAN_RAGDOLL(ped, TRUE);
			g_climbNativeTopOutStarted = false;
			g_climbNativeTopOutObserved = false;
			g_climbTopOutAt = now;
			setClimbState(ClimbState::Grounded, "native_top_out_stalled_no_snap");
		}
		return;
	}
	if (g_climbState == ClimbState::Dismounting) {
		const float seconds = STREAMING::HAS_ANIM_DICT_LOADED(kClimbAnimDict) ?
			ENTITY::GET_ANIM_DURATION(kClimbAnimDict, kClimbExitBottom) : 0.8f;
		const DWORD duration = (DWORD)((std::max)(0.35f,
			(std::min)(1.5f, seconds)) * 1000.0f);
		if (now - g_climbStateAt >= duration) {
			leaveClimbing(ped, "bottom_dismount_complete", false);
		}
		return;
	}

	for (int group = 0; group < 3; ++group) {
		DISABLE_CONTROL(group, joaat("INPUT_MOVE_LR"));
		DISABLE_CONTROL(group, joaat("INPUT_MOVE_UD"));
		DISABLE_CONTROL(group, joaat("INPUT_SPRINT"));
		DISABLE_CONTROL(group, joaat("INPUT_JUMP"));
		DISABLE_CONTROL(group, joaat("INPUT_ATTACK"));
		DISABLE_CONTROL(group, joaat("INPUT_MELEE_ATTACK"));
	}

	// Keep the frozen ped pinned every frame. Bailing out early on the frames
	// without a resolved batch was what let Rockstar's slide carry Arthur off the
	// face; the surface fit below only refines a position we already own.
	const float smoothing = 1.0f - std::exp(-g_climbSmoothing * dt);
	if (steepSurface) {
		g_climbLastContactAt = now;
		g_climbNormal = cvNorm(cvLerp(g_climbNormal, normal, smoothing));
		g_climbPoint = cvLerp(g_climbPoint, point, smoothing);
		g_climbContactHeight += (contactHeight - g_climbContactHeight) * smoothing;
	} else if (g_climbLastContactAt && now - g_climbLastContactAt > 1400) {
		// Was 700 ms. On irregular geometry - the jutting rock, corners, the
		// approach to a lip - the probe legitimately misses for a few frames
		// while the fit re-settles, and dropping him then reads as letting go at
		// random. Give the fit twice as long to recover before releasing.
		leaveClimbing(ped, "lost_surface", true);
		return;
	}
	if (g_climbState == ClimbState::Grabbing) {
		// A walk/sneak-off entry gets Rockstar's generic authored vault-down rather
		// than falling into the ordinary bottom-grab clip. Hold the known top pose
		// until the dictionary is ready; never substitute an unrelated scene anim.
		if (g_climbReverseGrab && !g_climbReverseAnimStarted) {
			STREAMING::REQUEST_ANIM_DICT(kClimbReverseDict);
			if (!STREAMING::HAS_ANIM_DICT_LOADED(kClimbReverseDict)) {
				SET_COORDS_NO_OFFSET_ALIGNED(ped, g_climbAttachFrom);
				SET_ENTITY_VELOCITY(ped, {});
				return;
			}
			const float authoredSeconds = ENTITY::GET_ANIM_DURATION(
				kClimbReverseDict, kClimbReverseClip);
			g_climbReverseDurationMs = (DWORD)((std::max)(450.0f,
				(std::min)(2000.0f, authoredSeconds * 1000.0f)));
			TASK::TASK_PLAY_ANIM(ped, kClimbReverseDict, kClimbReverseClip,
				2.0f, -2.0f, -1, 0, 0.0f, FALSE, 0, FALSE, "", FALSE);
			g_climbAnimClip = kClimbReverseClip;
			g_climbAnimDictInUse = kClimbReverseDict;
			g_climbReverseAnimStarted = true;
			g_climbStateAt = now;
			std::ostringstream reverse;
			reverse << "reverse mantle started dict=" << kClimbReverseDict
				<< " clip=" << kClimbReverseClip
				<< " durationMs=" << g_climbReverseDurationMs;
			climbLog(reverse.str());
		}
		// Blend the authored transition from the live top pose to the climbing
		// anchor. Non-reverse failed jumps retain the shorter bottom-grab blend.
		const float grabDuration = g_climbReverseGrab ?
			(float)g_climbReverseDurationMs : 320.0f;
		const float grabT = (std::min)(1.0f,
			(now - g_climbStateAt) / (std::max)(1.0f, grabDuration));
		const float eased = grabT * grabT * (3.0f - 2.0f * grabT);
		SET_COORDS_NO_OFFSET_ALIGNED(ped, cvLerp(g_climbAttachFrom, g_climbAnchor, eased));
		const Vector3 grabFace = cvMul(g_climbNormal, -1.0f);
		SET_ENTITY_HEADING(ped, std::atan2(-grabFace.x, grabFace.y) * 57.2957795f + g_climbFacingOffset);
		SET_ENTITY_VELOCITY(ped, {});
		if (grabT >= 1.0f) {
			const bool reverse = g_climbReverseGrab;
			g_climbReverseGrab = false;
			g_climbReverseAnimStarted = false;
			g_climbReverseDurationMs = 0;
			g_climbAnimClip = nullptr;
			g_climbAnimDictInUse = nullptr;
			setClimbState(ClimbState::Climbing,
				reverse ? "reverse_mantle_complete" : "grab_transition_complete");
		}
		else return;
	}
	// Reaching the bottom is a normal, expected end of a climb, and it must not
	// fall through to the lost_surface path: that released a pitched, frozen ped
	// straight into the rock. Detect ground under the feet while descending and
	// take the authored dismount.
	if (g_climbState == ClimbState::Climbing &&
		HEIGHT_ABOVE_GROUND(ped) < 0.45f && moveY > 0.35f) {
		if (STREAMING::HAS_ANIM_DICT_LOADED(kClimbAnimDict)) {
			SET_ENTITY_ROTATION(ped, { 0.0f, 0.0f, ENTITY_HEADING(ped) });
			TASK::TASK_PLAY_ANIM(ped, kClimbAnimDict, kClimbExitBottom,
				4.0f, -4.0f, -1, 1, 1.0f, FALSE, 0, FALSE, "", FALSE);
			g_climbAnimClip = kClimbExitBottom;
			g_climbAnimDictInUse = kClimbAnimDict;
		}
		// Do not release coordinate ownership on the same frame the dismount is
		// issued. That dropped Arthur inside the terrain before the clip could
		// move him clear, then the physics solver popped him back out standing.
		setClimbState(ClimbState::Dismounting, "reached_ground");
		return;
	}

	Vector3 worldUp = { 0.0f, 0.0f, 1.0f };
	Vector3 tangentRight = cvNorm(cvCross(worldUp, g_climbNormal));
	if (cvLen(tangentRight) < 0.5f) {
		leaveClimbing(ped, "ceiling_or_floor", true);
		return;
	}
	Vector3 tangentUp = cvNorm(cvCross(g_climbNormal, tangentRight));
	if (tangentUp.z < 0.0f) tangentUp = cvMul(tangentUp, -1.0f);
	const Vector3 camRot = CAM::GET_GAMEPLAY_CAM_ROT(2);
	const float camYaw = camRot.z * 0.0174532925f;
	const float camPitch = camRot.x * 0.0174532925f;
	Vector3 camForward = { -std::sin(camYaw) * std::cos(camPitch),
		std::cos(camYaw) * std::cos(camPitch), std::sin(camPitch) };
	Vector3 camRight = { std::cos(camYaw), std::sin(camYaw), 0.0f };
	Vector3 camUp = cvNorm(cvCross(camRight, camForward));
	Vector3 screenRight = cvNorm(cvSub(camRight, cvMul(g_climbNormal, cvDot(camRight, g_climbNormal))));
	Vector3 screenUp = cvNorm(cvSub(camUp, cvMul(g_climbNormal, cvDot(camUp, g_climbNormal))));
	if (cvLen(screenRight) < 0.35f) screenRight = tangentRight;
	if (cvLen(screenUp) < 0.35f) screenUp = tangentUp;
	// The leading flank probe sees an adjacent face before the body centre reaches
	// a corner. Blend onto it during lateral input so the anchor wraps the corner.
	// A jutting rock shows two faces at once, and adopting whichever one a probe
	// happened to report made the fit flip between them every single frame —
	// that is the vibrating, clipping, then suddenly-dropped report. Only turn
	// onto an adjacent face once the SAME face has been reported consistently
	// for SurfaceHoldMs; a one-frame glimpse of a different plane is noise.
	static Vector3 pendingNormal = {};
	static DWORD pendingNormalAt = 0;
	if (std::fabs(moveX) > 0.15f) {
		const ClimbProbe& lead = g_climbProbes[moveX < 0.0f ? 4 : 5];
		if (lead.hit) {
			const float turnDot = cvDot(g_climbNormal, lead.normal);
			if (turnDot > 0.15f && turnDot < 0.96f) {
				const bool sameAsPending = pendingNormalAt &&
					cvDot(pendingNormal, lead.normal) > 0.97f;
				if (!sameAsPending) {
					pendingNormal = lead.normal;
					pendingNormalAt = now;
				} else if (now - pendingNormalAt >= (DWORD)g_climbNormalHoldMs) {
					g_climbNormal = cvNorm(cvLerp(g_climbNormal, lead.normal, smoothing));
					g_climbPoint = cvLerp(g_climbPoint, lead.point, smoothing);
				}
			} else {
				pendingNormalAt = 0;
			}
		} else {
			pendingNormalAt = 0;
		}
	} else {
		pendingNormalAt = 0;
	}

	if (jump && g_climbState == ClimbState::Climbing) {
		if (GET_STAMINA_BAR(player) <= g_climbLeapCost) {
			leaveClimbing(ped, "leap_no_stamina", true);
			return;
		}
		invoke<BOOL>(0xC3D4B754C0E86B9E, ped, -g_climbLeapCost);
		Vector3 direction = cvAdd(cvMul(screenRight, moveX), cvMul(screenUp, -moveY));
		if (cvLen(direction) < 0.20f) direction = g_climbNormal; // outward wall jump
		else direction = cvNorm(cvAdd(cvNorm(direction), cvMul(g_climbNormal, sprint ? 0.35f : 0.65f)));
		// Add lift so the jump reads as a push off the face rather than a slide
		// down it, and turn him to face the way he is going.
		direction = cvNorm(cvAdd(direction, Vector3{ 0.0f, 0.0f, 0.45f }));
		TASK::CLEAR_PED_TASKS(ped, true, false);
		// snapToGround=false: a leap must keep its arc, not get stood up and
		// dropped onto the ground directly beneath the wall.
		releaseClimbPhysics(ped, false);
		g_climbLeapAt = now;
		g_climbLeapFrom = ENTITY_COORDS(ped);
		SET_ENTITY_HEADING(ped, std::atan2(-direction.x, direction.y) * 57.2957795f);
		SET_ENTITY_VELOCITY(ped, cvMul(direction, g_climbLeapDistance * (sprint ? 1.35f : 1.0f)));
		clearClimbProbes();
		g_climbCache.valid = false;
		setClimbState(ClimbState::Airborne, sprint ? "directional_leap" : "wall_jump");
		return;
	}

	const float drain = inputMagnitude < 0.08f ? g_climbIdleDrain :
		(sprint ? g_climbSprintDrain : g_climbMoveDrain);
	// RESTORE_PLAYER_STAMINA is a restore-only native; negative input did not
	// drain the bar and the trace showed stamina rising throughout a climb.
	// _CHANGE_PED_STAMINA explicitly accepts negative values.
	// Draining alone is not enough: the game refills the outer bar from the
	// stamina core faster than we remove it, which is why the bar never moved
	// while the core thumped. Hold a target that only ever decreases and pull
	// the bar down to it every frame, which cancels the regen as well.
	g_climbStamina.tick(player, ped, drain, dt);
	if (g_climbProtectedCore >= 0 && GET_CORE(ped, 1) < g_climbProtectedCore)
		SET_CORE(ped, 1, g_climbProtectedCore);
	if (GET_STAMINA_BAR(player) <= 1.0f) {
		leaveClimbing(ped, "stamina_empty", true);
		return;
	}

	// Let the grip establish itself before the player can move. This must be a
	// LATCH, not a per-frame test: the grip clip loops (~14 s), so comparing its
	// phase against a threshold blocked movement for the first ~5 s of every
	// single loop, not just at attachment. Settle once, then stay settled.
	if (!g_climbGripReady && now - g_climbGripAt >= (DWORD)g_climbGripSettleMs)
		g_climbGripReady = true;
	const bool lateralInput = std::fabs(moveX) > 0.10f && std::fabs(moveY) < 0.35f;
	// #169(d) "HE STARTS MOVING BEFORE THE ANIMATION STARTS" - still true, and the
	// blend ramp added last round could not have fixed it, because of ORDERING.
	// The gain is computed HERE, but the block that decides which clip the input
	// calls for and issues it runs at the BOTTOM of the function. So on the very
	// frame the player presses W, everything read here still describes the
	// previous state: the idle grip, which has been playing for seconds, so the
	// "has the clip started" test passes instantly and the ramp - measured from a
	// clip change that has not happened yet - is already at 1.0. He gets full
	// climbing speed on frame one against a grip pose, and the climb_up clip is
	// only requested afterwards. Judge the gain against the motion the INPUT is
	// asking for: until the state machine below has actually adopted that motion
	// and started its clip, he does not move at all.
	const ClimbMotion rawInputMotion = lateralInput ?
		(moveX < 0.0f ? ClimbMotion::Left : ClimbMotion::Right) :
		(moveY < -0.10f ? ClimbMotion::Up :
		(moveY > 0.10f ? ClimbMotion::Down : ClimbMotion::Idle));
	// After Rockstar rejects a mantle, retain the verified lip and idle grip
	// until Up is released. Continuing to process the held Up input moved the
	// anchor above the last real contact and made Arthur grab open air.
	const ClimbMotion inputMotion = g_climbTopOutBlockedUntilRelease ?
		ClimbMotion::Idle : rawInputMotion;
	static ClimbMotion previousInputMotion = ClimbMotion::Idle;
	static DWORD inputMotionAt = 0;
	if (inputMotion != previousInputMotion) {
		previousInputMotion = inputMotion;
		inputMotionAt = now;
		if (inputMotion == ClimbMotion::Left || inputMotion == ClimbMotion::Right) {
			g_climbLateralDirection = inputMotion;
			g_climbLateralReadbackAt = now;
			g_climbLateralStartAnchor = g_climbAnchor;
			g_climbLateralStartActual = ENTITY_COORDS(ped);
		} else {
			g_climbLateralDirection = ClimbMotion::Idle;
		}
	}
	const bool motionMatchesInput = inputMotion != ClimbMotion::Idle &&
		g_climbMotion == inputMotion;
	const float motionAnimPhase = (g_climbAnimClip && g_climbAnimDictInUse) ?
		ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(ped, g_climbAnimDictInUse,
			g_climbAnimClip) : 0.0f;
	const bool motionAnimPlaying = g_climbAnimClip && g_climbAnimDictInUse &&
		ENTITY::IS_ENTITY_PLAYING_ANIM(ped, g_climbAnimDictInUse,
			g_climbAnimClip, 3);
	// A progressing phase or the native playing predicate is a postcondition.
	// Retain the old bounded bind allowance only for the proven vertical ladder
	// set. #161 must not call a narrow-ledge timeout "bound" and then slide a
	// static pose sideways forever.
	const bool motionAnimBound = g_climbAnimClip && g_climbAnimDictInUse &&
		(motionAnimPhase > 0.001f || motionAnimPlaying ||
			(!lateralInput && now - g_climbLastAnim >= 160));
	// THE SLIDE-BEFORE-THE-ANIMATION WAS NEVER ACTUALLY FIXED.
	// Gating on IS_ENTITY_PLAYING_ANIM is not enough: that native reports true
	// the moment the task is ISSUED, while the clip is still blending in from
	// the previous pose. So for the whole blend he is already moving at full
	// speed with nothing visibly animating - exactly the reported slide.
	// Ramp the speed in over the blend instead of switching it on. This also
	// removes the abrupt start, because he accelerates as the clip takes hold.
	float motionGain = 0.0f;
	if (g_climbGripReady) {
		// #169(c) "HE KEEPS CLIMBING WHEN YOU STOP PRESSING".
		// Below the deadzone this set motion gain to FULL. Deliberate small
		// input got ramped in from zero, but anything under the threshold -
		// controller drift, a stick settling back to centre - was multiplied by
		// 1.0 and moved him at full speed. Releasing the stick therefore left
		// him creeping along the wall on residual drift, and the gain jumped
		// discontinuously between 1.0 and 0.0 either side of the threshold,
		// which is a fair part of the hitchy feel too. No input means no
		// movement; zero the gain and the vector both.
		if (inputMagnitude < 0.10f) {
			motionGain = 0.0f;
		} else if (motionMatchesInput && motionAnimBound) {
			// Ramp from whichever happened LATER: the clip actually starting, or
			// the player asking for this direction. Using the clip change alone
			// let a stale grip clip hand back a fully ramped gain instantly.
			const DWORD from = (std::max)(g_climbLastAnim, inputMotionAt);
			const DWORD since = now >= from ? now - from : 0;
			const float blend = (std::max)(1.0f, (float)g_climbMotionBlendMs);
			motionGain = (std::min)(1.0f, since / blend);
			motionGain = motionGain * motionGain * (3.0f - 2.0f * motionGain);
		}
	}
	const float speed = (sprint ? g_climbSprintSpeed : g_climbMoveSpeed) * motionGain;
	// Restore lateral movement with an authored cliff-traverse loop. Movement is
	// held until its clip is actually playing, eliminating the slide-before-anim.
	Vector3 movement = inputMagnitude < 0.10f ? Vector3{ 0.0f, 0.0f, 0.0f }
		: cvAdd(cvMul(screenUp, -moveY), cvMul(screenRight, moveX));
	if (cvLen(movement) > 1.0f) movement = cvNorm(movement);
	// The player owns motion along the surface; the probe fit only corrects the
	// standoff along the normal. Lerping the whole position toward the averaged
	// contact centroid is what previously slid Arthur sideways on its own and
	// fought every input.
	g_climbAnchor = cvAdd(g_climbAnchor, cvMul(movement, speed * dt));
	if (steepSurface) {
		const Vector3 fitted = climbRootFromContact(g_climbPoint, g_climbNormal,
			g_climbContactHeight, g_climbSurfaceOffset);
		float error = cvDot(cvSub(fitted, g_climbAnchor), g_climbNormal);
		error = (std::max)(-0.60f, (std::min)(0.60f, error));
		g_climbAnchor = cvAdd(g_climbAnchor, cvMul(g_climbNormal, error * smoothing));
	}
	// Dynamic contact correction: if either animated hand crosses behind the
	// fitted surface plane, move the owned root just far enough outward to keep it
	// on the face. A single fixed standoff could not handle changing wall shapes.
	const Vector3 leftHand = PED::GET_PED_BONE_COORDS(ped, 37709, 0.0f, 0.0f, 0.0f);
	const Vector3 rightHand = PED::GET_PED_BONE_COORDS(ped, 7966, 0.0f, 0.0f, 0.0f);
	const float handClearance = (std::min)(cvDot(cvSub(leftHand, g_climbPoint), g_climbNormal),
		cvDot(cvSub(rightHand, g_climbPoint), g_climbNormal));
	// LEXER WAS RIGHT: THIS IS WHY HE LET GO AT RANDOM.
	// A 0.22 m outward shove is larger than the 0.16 m standoff, so one frame of
	// hand penetration could push the root far enough off the face that the next
	// probe found no surface at all -> "lost_surface" -> released mid-climb, for
	// no reason the player could see. Correct gently and spread it over frames
	// instead of teleporting him off the wall in one go.
	if (handClearance < 0.015f) {
		const float correction = (std::min)(0.06f, 0.015f - handClearance);
		g_climbAnchor = cvAdd(g_climbAnchor, cvMul(g_climbNormal, correction * smoothing));
	}
	SET_COORDS_NO_OFFSET_ALIGNED(ped, g_climbAnchor);
	SET_ENTITY_VELOCITY(ped, {});
	const Vector3 face = cvMul(g_climbNormal, -1.0f);
	// FacingOffsetDegrees exists because "back against the surface" means this is
	// 180 degrees out, and I cannot confirm the right value without running it.
	// Flip it in the ini (hot-reloads in 2s) rather than waiting on a rebuild.
	const float heading = std::atan2(-face.x, face.y) * 57.2957795f
		+ g_climbFacingOffset;
	// Yaw alone left Arthur bolt upright against an inclined face, so only his
	// heading tracked the rock and his body punched through it. Pitch him by the
	// surface's tilt from vertical: a vertical wall gives 0, a 60-degree slope
	// (normal.z ~= 0.5) leans him 30 degrees into the hill. PitchSign exists
	// because the engine's pitch convention cannot be verified without the game
	// running — flip it in the ini, no rebuild needed.
	const float clampedNormalZ = (std::max)(-1.0f, (std::min)(1.0f, g_climbNormal.z));
	const float surfacePitch = g_climbPitchAlign ?
		g_climbPitchSign * std::asin(clampedNormalZ) * 57.2957795f : 0.0f;
	// LEANING HIM TO MATCH THE ROCK CANNOT BE AN OPTION, and it has been one:
	// AlignPitchToSurface defaulted to 0, so by default he stood bolt upright
	// against every slope while only his heading tracked it. Half the "he is
	// inside the rock" report is that, and the other half was the root placement
	// above. Both are now on by default and both are required to be right.
	// The reason it was made optional is real though: SET_ENTITY_ROTATION every
	// frame re-poses the ped and resets its animation to frame 0, which is what
	// A-posed him. The answer is not to skip the rotation, it is to stop issuing
	// it EVERY FRAME. The fitted normal is smoothed and nearly constant on a
	// steady face, so re-applying only when the orientation has actually moved
	// costs a call every few seconds instead of sixty a second - he stays
	// aligned and the clip is left alone to advance.
	static float appliedPitch = 0.0f, appliedHeading = 0.0f;
	static bool orientationApplied = false;
	static DWORD orientationAttachmentAt = 0;
	static bool orientationAuditPending = false;
	static DWORD orientationAuditAt = 0;
	static float orientationAuditPitch = 0.0f;
	static float orientationAuditHeading = 0.0f;
	const float headingDelta = std::fabs(shortestHeadingDelta(appliedHeading, heading));
	// Cloth physics cannot tolerate repeatedly pitching the entire ped as noisy
	// shape-test normals wander over an irregular rock. Apply the fitted lean at
	// attachment, then keep that pitch stable for this climb; only yaw follows a
	// genuinely new face. This preserves surface alignment without shocking the
	// coat tails every few frames.
	const bool newAttachment = !orientationApplied ||
		orientationAttachmentAt != g_climbStateAt;
	const bool orientationMoved = !orientationApplied ||
		headingDelta > 2.0f || newAttachment;
	if (orientationMoved) {
		orientationApplied = true;
		if (newAttachment) appliedPitch = surfacePitch;
		if (newAttachment) {
			orientationAttachmentAt = g_climbStateAt;
		}
		appliedHeading = heading;
		if (std::fabs(appliedPitch) > 0.5f)
			SET_ENTITY_ROTATION(ped, { appliedPitch, 0.0f, heading });
		else
			SET_ENTITY_HEADING(ped, heading);
		// GET_ENTITY_ROTATION is resolved in the shipped SDK natives table. This
		// immediate readback proves whether the engine accepted the setter; it is
		// not evidence that the pose still matches after its animation advances.
		const Vector3 immediate = ENTITY::GET_ENTITY_ROTATION(ped, 2);
		std::ostringstream line;
		line << "orientation applied requested=" << appliedPitch << ",0,"
			<< heading << " immediate=" << immediate.x << "," << immediate.y
			<< "," << immediate.z
			<< " pitchError=" << std::fabs(immediate.x - appliedPitch)
			<< " headingError="
			<< std::fabs(shortestHeadingDelta(immediate.z, heading))
			<< " newAttachment=" << (newAttachment ? 1 : 0);
		climbLog(line.str());
		if (newAttachment) {
			orientationAuditPending = true;
			orientationAuditAt = now;
			orientationAuditPitch = appliedPitch;
			orientationAuditHeading = heading;
		}
	}
	if (orientationAuditPending && now - orientationAuditAt >= 180) {
		orientationAuditPending = false;
		const Vector3 retained = ENTITY::GET_ENTITY_ROTATION(ped, 2);
		const float pitchError = std::fabs(retained.x - orientationAuditPitch);
		const float headingError = std::fabs(shortestHeadingDelta(
			retained.z, orientationAuditHeading));
		std::ostringstream line;
		line << "orientation retained requested=" << orientationAuditPitch
			<< ",0," << orientationAuditHeading
			<< " actual=" << retained.x << "," << retained.y << ","
			<< retained.z << " pitchError=" << pitchError
			<< " headingError=" << headingError
			<< " matched=" << ((pitchError <= 3.0f && headingError <= 3.0f) ? 1 : 0);
		climbLog(line.str());
	}

	// THE BUG: this block used `!IS_ENTITY_PLAYING_ANIM(...)` as a re-issue
	// condition. That predicate never became true here, so TASK_PLAY_ANIM was
	// called again EVERY FRAME, restarting the clip from phase 0 every frame.
	// An animation permanently re-started at frame 0 is, visually, a frozen
	// pose — which is exactly "Arthur strikes a climbing pose and floats".
	// Removing FREEZE_ENTITY_POSITION could never have fixed that on its own.
	//
	// The static UFCO grip is not acceptable for our kinematic traversal: it
	// visibly slides while the coordinates move. mech_ladders@base contains
	// authored climb_up/climb_down loops; select them from vertical input and
	// retain a hand-up grip only while idle. Issue only on clip changes so an
	// active loop is never pinned to frame zero.
	const bool releaseMotion = inputMotion == ClimbMotion::Idle &&
		(g_climbMotion == ClimbMotion::Up || g_climbMotion == ClimbMotion::Down ||
			g_climbMotion == ClimbMotion::Left || g_climbMotion == ClimbMotion::Right);
	if (releaseMotion) {
		stopClimbMotionOnRelease(ped, now);
		g_climbMotion = ClimbMotion::Idle;
		g_climbMotionAt = now;
	}
	if (STREAMING::HAS_ANIM_DICT_LOADED(kClimbAnimDict)) {
		// Reuse the same value the speed gate above judged, so the clip the player
		// sees and the motion he is allowed to move under can never disagree.
		const ClimbMotion requested = inputMotion;
		if ((requested == ClimbMotion::Up || requested == ClimbMotion::Down ||
			requested == ClimbMotion::Left || requested == ClimbMotion::Right) &&
			requested != g_climbMotion) {
			g_climbMotion = requested;
			g_climbMotionAt = now;
		} else if (g_climbMotion == ClimbMotion::Settling &&
			now - g_climbMotionAt >= 300) {
			g_climbMotion = ClimbMotion::Idle;
			g_climbMotionAt = now;
		}
		const bool starting = (g_climbMotion == ClimbMotion::Up ||
			g_climbMotion == ClimbMotion::Down) && now - g_climbMotionAt < 240;
		// LATERAL ANIMATION. `walk_left` is the authored dictionary and `move` is
		// its playable clip. Never substitute the rejected Story-scene sidle.
		const bool sideways = g_climbMotion == ClimbMotion::Left ||
			g_climbMotion == ClimbMotion::Right;
		if (sideways) {
			if (!g_climbLateralAttemptAt) {
				g_climbLateralAttemptAt = now;
				STREAMING::REQUEST_ANIM_DICT(kClimbLedgeDict);
			}
			if (!STREAMING::HAS_ANIM_DICT_LOADED(kClimbLedgeDict) &&
				now - g_climbLateralAttemptAt >= 600 && g_climbingTrace) {
				std::ostringstream pending;
				pending << "lateral authored dictionary still loading ageMs="
					<< (now - g_climbLateralAttemptAt)
					<< " dict=" << kClimbLedgeDict
					<< " fallback=none";
				gtLog("climbing", GT_WARN, pending.str());
				g_climbLateralAttemptAt = now;
			}
		}
		const char* wantClip =
			sideways ? kClimbLedgeClip :
			g_climbMotion == ClimbMotion::Up ? (starting ?
				(g_climbIdleLeftHand ? kClimbUpStartLeft : kClimbUpStartRight) : kClimbUp) :
			g_climbMotion == ClimbMotion::Down ? (starting ?
				(g_climbIdleLeftHand ? kClimbDownStartLeft : kClimbDownStartRight) : kClimbDown) :
			g_climbMotion == ClimbMotion::Settling ?
				(g_climbSettleFrom == ClimbMotion::Up ?
					(g_climbIdleLeftHand ? kClimbUpSettleLeft : kClimbUpSettleRight) :
					(g_climbIdleLeftHand ? kClimbDownSettleLeft : kClimbDownSettleRight)) :
				(g_climbIdleLeftHand ? kClimbIdleLeft : kClimbIdleRight);
		if (g_climbAnimClip != wantClip) {
			// Alternating the grip hand is what SELLS hand-over-hand traverse, but
			// it is a clip change, and a clip change restarted the blend ramp - so
			// every 0.45 m of sideways travel his speed was dragged back to zero
			// and ramped up again. That is a stutter, not a traverse. Only restart
			// the ramp when the KIND of motion changes; swapping grips inside a
			// continuous sideways move keeps the speed it has already earned.
			const bool gripSwapOnly =
				(g_climbAnimClip == kClimbIdleLeft && wantClip == kClimbIdleRight) ||
				(g_climbAnimClip == kClimbIdleRight && wantClip == kClimbIdleLeft);
			// Start->loop is one continuous held direction. Resetting the movement
			// ramp here forced its gain back to zero at 240 ms and manufactured the
			// exact hitch reported in #165.
			const bool verticalPhaseOnly =
				(g_climbMotion == ClimbMotion::Up && wantClip == kClimbUp &&
					(g_climbAnimClip == kClimbUpStartLeft ||
					 g_climbAnimClip == kClimbUpStartRight)) ||
				(g_climbMotion == ClimbMotion::Down && wantClip == kClimbDown &&
					(g_climbAnimClip == kClimbDownStartLeft ||
					 g_climbAnimClip == kClimbDownStartRight));
			g_climbAnimClip = wantClip;
			if (!gripSwapOnly && !verticalPhaseOnly) g_climbLastAnim = now;
			const bool side = g_climbMotion == ClimbMotion::Left ||
				g_climbMotion == ClimbMotion::Right;
			// The authored lateral clip lives in its own dictionary.
			const char* dict =
				(wantClip == kClimbLedgeClip) ? kClimbLedgeDict : kClimbAnimDict;
			if (!STREAMING::HAS_ANIM_DICT_LOADED(dict)) {
				STREAMING::REQUEST_ANIM_DICT(dict);
				g_climbAnimClip = nullptr;
				g_climbAnimDictInUse = nullptr;
			} else {
				TASK::TASK_PLAY_ANIM(ped, dict, wantClip,
					1.0f, 1.0f, -1, 1, 1.0f, FALSE, 1, FALSE, "", FALSE);
				g_climbAnimDictInUse = dict;
				// Playing a clip BACKWARDS to mean "the other direction" is only
				// meaningful for a directional traverse clip. Running a static
				// hand-up GRIP in reverse is meaningless, and it drove the pose
				// backwards through its blend-in. Reverse only the real traverse
				// clips, never the grip fallback.
				const bool directionalSideClip = side && wantClip == kClimbLedgeClip;
				if (directionalSideClip)
					ENTITY::_SET_ENTITY_ANIM_SPEED(ped, dict, wantClip,
						g_climbMotion == ClimbMotion::Left ? 1.0f : -1.0f);
			}
		}
		if (g_climbMotion == ClimbMotion::Left || g_climbMotion == ClimbMotion::Right) {
			if (g_climbAnimClip == kClimbLedgeClip)
				ENTITY::_SET_ENTITY_ANIM_SPEED(ped, kClimbLedgeDict, kClimbLedgeClip,
					g_climbMotion == ClimbMotion::Left ? 1.0f : -1.0f);
		}
		if (g_climbReleaseAuditPending && now - g_climbReleaseAuditAt >= 180) {
			const bool outgoingPlaying = g_climbReleaseDict && g_climbReleaseClip &&
				ENTITY::IS_ENTITY_PLAYING_ANIM(ped, g_climbReleaseDict,
					g_climbReleaseClip, 3);
			const bool idleSelected = g_climbMotion == ClimbMotion::Idle &&
				(g_climbAnimClip == kClimbIdleLeft ||
					g_climbAnimClip == kClimbIdleRight);
			const float idlePhase = idleSelected && g_climbAnimDictInUse ?
				ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(ped, g_climbAnimDictInUse,
					g_climbAnimClip) : 0.0f;
			if (g_climbingTrace) {
				std::ostringstream result;
				result << "release readback outgoingPlaying="
					<< (outgoingPlaying ? 1 : 0)
					<< " idleSelected=" << (idleSelected ? 1 : 0)
					<< " idlePhase=" << idlePhase
					<< " anchorSpeed=0";
				gtLog("climbing", (!outgoingPlaying && idleSelected) ?
					GT_INFO : GT_WARN, result.str());
			}
			if (outgoingPlaying && g_climbReleaseRetryCount < 2) {
				++g_climbReleaseRetryCount;
				TASK::STOP_ANIM_TASK(ped, g_climbReleaseDict,
					g_climbReleaseClip, -8.0f);
				g_climbReleaseAuditAt = now;
				g_climbAnimClip = nullptr;
				g_climbAnimDictInUse = nullptr;
				climbLog("release stop retry=" +
					std::to_string(g_climbReleaseRetryCount));
			} else {
				g_climbReleaseAuditPending = false;
			}
		}
	} else {
		// The dictionary was requested once at grab time and never again. If it
		// had not streamed by then, nothing would ever play. Keep asking.
		STREAMING::REQUEST_ANIM_DICT(kClimbAnimDict);
	}
	if ((g_climbMotion == ClimbMotion::Left ||
		g_climbMotion == ClimbMotion::Right) &&
		g_climbLateralReadbackAt && now - g_climbLateralReadbackAt >= 900) {
		const Vector3 actual = ENTITY_COORDS(ped);
		const float commandedTravel = cvLen(cvSub(g_climbAnchor,
			g_climbLateralStartAnchor));
		const float actualTravel = cvLen(cvSub(actual,
			g_climbLateralStartActual));
		const float phase = (g_climbAnimClip && g_climbAnimDictInUse) ?
			ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(ped, g_climbAnimDictInUse,
				g_climbAnimClip) : 0.0f;
		if (g_climbingTrace) {
			std::ostringstream result;
			result << "lateral readback direction="
				<< (g_climbMotion == ClimbMotion::Left ? "left" : "right")
				<< " path=narrow_ledge"
				<< " dict=" << (g_climbAnimDictInUse ? g_climbAnimDictInUse : "-")
				<< " clip=" << (g_climbAnimClip ? g_climbAnimClip : "-")
				<< " phase=" << phase << " gain=" << motionGain
				<< " commandedMeters=" << commandedTravel
				<< " actualMeters=" << actualTravel;
			gtLog("climbing", (phase > 0.001f && commandedTravel >= 0.05f &&
				actualTravel >= 0.05f) ? GT_INFO : GT_WARN, result.str());
		}
		g_climbLateralReadbackAt = now;
		g_climbLateralStartAnchor = g_climbAnchor;
		g_climbLateralStartActual = actual;
	}

	// A missing head contact is only a ledge candidate. Prove a walkable landing
	// behind and above the face before taking the authored mantle. A pole or beam
	// has only distant ground below, so it remains attached instead of falling.
	if (!g_climbTopOutBlockedUntilRelease && probesReady &&
		!g_climbProbes[3].hit && g_climbProbes[0].hit &&
		g_climbProbes[1].hit && moveY < -0.45f) {
		Vector3 landingProbe = cvAdd(g_climbAnchor,
			cvAdd(cvMul(g_climbNormal, -0.80f), Vector3{ 0.0f, 0.0f, 2.20f }));
		float landingZ = landingProbe.z;
		const bool hasLanding = GROUND_Z(landingProbe, &landingZ) &&
			landingZ >= g_climbAnchor.z + 0.45f &&
			landingZ <= g_climbAnchor.z + 2.10f;
		if (hasLanding) {
			g_climbTopOutTarget = landingProbe;
			g_climbTopOutTarget.z = landingZ + 0.05f;
			g_climbMotion = ClimbMotion::Idle;
			// Stop the custom ladder mover, but retain the verified lip until the
			// native climb/vault state proves TASK_CLIMB accepted. #160's reported
			// fall-then-teleport came from releasing here and snapping 1.2 s later.
			// Stop only our authored traversal clip. Clearing the entire task tree
			// collapsed Arthur out of his wall pose before TASK_CLIMB could visibly
			// take over, producing the slide/snap/mantle sequence.
			stopClimbMotionOnRelease(ped, now);
			SET_ENTITY_VELOCITY(ped, {});
			clearClimbProbes();
			g_climbCache.valid = false;
			g_climbProtectedCore = -1;
			g_climbNativeTopOutStarted = true;
			g_climbNativeTopOutObserved = false;
			g_climbNativeTopOutTraceAt = 0;
			TASK::TASK_CLIMB(ped, FALSE);
			setClimbState(ClimbState::ToppingOut, "verified_walkable_landing");
			return;
		}
		// A rejected ledge is not a movement release. Keep the current vertical
		// clip and earned gain while backing away from the invalid landing. Resetting
		// to Idle here made held Up restart its start clip on the next frame.
		g_climbAnchor = cvAdd(g_climbAnchor,
			cvMul(tangentUp, -g_climbMoveSpeed * dt));
		if (g_climbingTrace && now - g_climbLastTrace >= 500)
			climbLog("ledge blocked: no verified walkable top-out landing");
		return;
	}

	if (g_climbingTrace && now - g_climbLastTrace >= 500) {
		g_climbLastTrace = now;
		std::ostringstream line;
		const Vector3 actual = ENTITY_COORDS(ped);
		line << "state=" << climbStateName(g_climbState) << " hits=" << hits
			<< " dictLoaded=" << (STREAMING::HAS_ANIM_DICT_LOADED(kClimbAnimDict) ? 1 : 0)
			<< " wantClip=" << (g_climbAnimClip ? g_climbAnimClip : "-")
			// Query the dictionary the clip was actually ISSUED from. Hardcoding
			// mech_ladders here reported animPlaying=0/phase=0 for every lateral
			// and narrow-ledge frame, which is a lie the trace told us for as long
			// as lateral clips have come from anywhere else.
			<< " animDict=" << (g_climbAnimDictInUse ? g_climbAnimDictInUse : "-")
			<< " animPlaying=" << ((g_climbAnimClip && g_climbAnimDictInUse &&
				ENTITY::IS_ENTITY_PLAYING_ANIM(ped, g_climbAnimDictInUse, g_climbAnimClip, 3)) ? 1 : 0)
			<< " animPhase=" << ((g_climbAnimClip && g_climbAnimDictInUse) ?
				ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(ped, g_climbAnimDictInUse, g_climbAnimClip) : -1.0f)
			<< " ready=" << (probesReady ? 1 : 0)
			<< " contactAge=" << (now - g_climbLastContactAt)
			<< " normal=" << g_climbNormal.x << "," << g_climbNormal.y << "," << g_climbNormal.z
			<< " anchor=" << g_climbAnchor.x << "," << g_climbAnchor.y << "," << g_climbAnchor.z
			<< " actual=" << actual.x << "," << actual.y << "," << actual.z
			<< " physicsOwned=" << (g_climbPhysicsOwned ? 1 : 0)
			<< " clip=" << (g_climbAnimClip ? g_climbAnimClip : "-")
			<< " motion=" << (int)g_climbMotion
			<< " gain=" << motionGain
			<< " input=" << moveX << "," << moveY << " sprint=" << sprint
			<< " stamina=" << GET_STAMINA_BAR(player);
		climbLog(line.str());
	}
}

// One-time recovery for the 2026-08-05 CoreClock regression. Rockstar keeps
// the authoritative cumulative Health/Stamina/Dead Eye XP totals in
// Global_40.f_11095.f_11[0..2]. The bad SET_CORE path changed the ped's saved
// attribute points but did not touch these globals. Reapplying the global totals
// restores exact within-rank progress; challenge/equipment bonus ranks remain
// independent. The flag is deleted only after every readback matches.
static void repairCoreProgressionOnce(Ped ped, bool playerReady) {
	static bool checked = false;
	if (checked || !ped || !playerReady) return;
	const std::string flag = g_moduleDir + "\\GameplayTweaks.repair-core-ranks.once";
	const std::string valuesPath = g_moduleDir + "\\GameplayTweaks.repair-core-ranks.values";
	std::ifstream marker(flag);
	if (!marker) { checked = true; return; }
	marker.close();
	GtLogStream log("core-rank", GT_INFO);
	if (log) log << "--- repair attempt ---\n";
	bool valid = true;
	int wanted[3] = {};
	bool apply[3] = { true, true, true };
	// A values file is an exact recovery snapshot: three point totals, where -1
	// means leave that attribute untouched. The first failed attempt logged all
	// three pre-write values as 1100, so the corrective pass uses 1100,-1,-1 and
	// cannot disturb the already-correct Stamina or Dead Eye values.
	std::ifstream values(valuesPath);
	const bool hasExactValues = values && (values >> wanted[0] >> wanted[1] >> wanted[2]);
	if (hasExactValues) {
		for (int attribute = 0; attribute < 3; ++attribute) {
			apply[attribute] = wanted[attribute] >= 0;
			if (wanted[attribute] > 1100) valid = false;
			if (log) log << "attribute=" << attribute
				<< " exact_points=" << wanted[attribute]
				<< " before_points=" << GET_ATTRIBUTE_POINTS(ped, attribute)
				<< " before_base_rank=" << GET_ATTRIBUTE_BASE_RANK(ped, attribute)
				<< " bonus_rank=" << invoke<int>(0x0EFA71F4B4330E04, ped, attribute)
				<< "\n";
		}
	}
	if (!hasExactValues) {
		if (log) log << "REFUSED: exact recovery values file missing\n";
		checked = true;
		return;
	}
	for (int attribute = 0; attribute < 3; ++attribute) {
		if (hasExactValues) continue;
		float xp = *reinterpret_cast<float*>(getGlobalPtr(40 + 11095 + 11 + attribute));
		// Progression XP cannot legitimately be a positive subnormal. Rejecting
		// values below 1 also prevents the bad Health offset from ever becoming 0.
		if (!std::isfinite(xp) || xp < 1.0f || xp > 1100.0f) {
			valid = false;
			if (log) log << "attribute=" << attribute << " invalid_global_xp=" << xp << "\n";
			continue;
		}
		wanted[attribute] = (int)floorf(xp);
		if (log) log << "attribute=" << attribute
			<< " global_xp=" << xp
			<< " before_points=" << GET_ATTRIBUTE_POINTS(ped, attribute)
			<< " before_base_rank=" << GET_ATTRIBUTE_BASE_RANK(ped, attribute)
			<< " bonus_rank=" << invoke<int>(0x0EFA71F4B4330E04, ped, attribute)
			<< "\n";
	}
	if (!valid) { checked = true; return; }
	for (int attribute = 0; attribute < 3; ++attribute)
		if (apply[attribute]) SET_ATTRIBUTE_POINTS(ped, attribute, wanted[attribute]);
	bool verified = true;
	for (int attribute = 0; attribute < 3; ++attribute) {
		const int readback = GET_ATTRIBUTE_POINTS(ped, attribute);
		if (apply[attribute] && readback != wanted[attribute]) verified = false;
		if (log) log << "attribute=" << attribute
			<< " wanted_points=" << wanted[attribute]
			<< " applied=" << (apply[attribute] ? 1 : 0)
			<< " readback_points=" << readback
			<< " after_base_rank=" << GET_ATTRIBUTE_BASE_RANK(ped, attribute)
			<< " bonus_rank=" << invoke<int>(0x0EFA71F4B4330E04, ped, attribute)
			<< "\n";
	}
	if (verified) {
		DeleteFileA(flag.c_str());
		if (hasExactValues) DeleteFileA(valuesPath.c_str());
		if (log) log << "SUCCESS flag_deleted=1\n";
	} else if (log) log << "FAILED flag_retained=1\n";
	checked = true;
}

static void updateCoreXPGain(Ped ped, bool playerReady) {
	repairCoreProgressionOnce(ped, playerReady);
	if (g_coreXPGainEnabled) {
		g_coreXPPed = 0;
		g_coreXPRanksCaptured = false;
		return;
	}
	if (!ped || !playerReady) return;
	if (ped != g_coreXPPed) {
		g_coreXPPed = ped;
		g_coreXPRanksCaptured = false;
	}
	if (!g_coreXPRanksCaptured) {
		for (int attribute = 0; attribute < 3; ++attribute)
			g_coreXPRankCeiling[attribute] = GET_ATTRIBUTE_BASE_RANK(ped, attribute);
		g_coreXPRanksCaptured = true;
		return;
	}
	for (int attribute = 0; attribute < 3; ++attribute) {
		const int liveRank = GET_ATTRIBUTE_BASE_RANK(ped, attribute);
		if (liveRank > g_coreXPRankCeiling[attribute])
			SET_ATTRIBUTE_BASE_RANK(ped, attribute, g_coreXPRankCeiling[attribute]);
		else if (liveRank < g_coreXPRankCeiling[attribute])
			g_coreXPRankCeiling[attribute] = liveRank;
	}
}

// ---- Directional dodge roll (#6) -----------------------------------------
// Rockstar ships the complete roll set in this dictionary. The old #208 path
// searched a candidate list because the dictionary had not yet been found,
// then drove the ped with SET_ENTITY_VELOCITY for the duration of the clip.
// The shipped animation index and the live resolver log now both confirm the
// real dictionary, so movement can stay authored: stop only the incoming
// horizontal momentum and let the clip's root motion carry the roll.
static const char* kDodgeRollDict = "mech_strafe@generic@roll@base";

struct DodgeRollClip {
	const char* p1;
	const char* p2;
	float degrees;
};

// Combat Roll v1.03.1 contains exactly these eight P1/P2 pairs. Its decompiled
// selector chooses one pair from the four directional controls, plays P1 as the
// launch, then P2 as the recovery. P2 is not a fallback: omitting it was the
// central mismatch in every earlier implementation.
static const DodgeRollClip kDodgeRollClips[] = {
	{ "combatroll_fwd_p1_00",   "combatroll_fwd_p2_00",     0.0f },
	{ "combatroll_fwd_p1_45",   "combatroll_fwd_p2_45",    45.0f },
	{ "combatroll_bwd_p1_-45",  "combatroll_bwd_p2_-45",  -45.0f },
	{ "combatroll_fwd_p1_90",   "combatroll_fwd_p2_90",    90.0f },
	{ "combatroll_bwd_p1_-90",  "combatroll_bwd_p2_-90",  -90.0f },
	{ "combatroll_bwd_p1_135",  "combatroll_bwd_p2_135",  135.0f },
	{ "combatroll_bwd_p1_-135", "combatroll_bwd_p2_-135", -135.0f },
	{ "combatroll_bwd_p1_180",  "combatroll_bwd_p2_180",  180.0f },
};

static Ped g_dodgeRollPed = 0;
enum class DodgeRollStage { Idle, P1, P2 };
static DodgeRollStage g_dodgeRollStage = DodgeRollStage::Idle;
static const DodgeRollClip* g_dodgeRollPair = nullptr;
static DWORD g_dodgeRollStageAt = 0;
static DWORD g_dodgeRollSurvivalAt = 0;
static bool g_dodgeRollSurvivalLogged = true;
static const char* g_dodgeRollClipName = "";
static Hash g_dodgeRollWeapon = 0;
static bool g_dodgeRollWasCrouched = false;
static bool g_dodgeRollPredicateWasActive = false;
static bool g_dodgeRollTriggerPending = false;
static const DodgeRollClip* g_dodgeRollPendingPair = nullptr;
static DWORD g_dodgeRollPendingAt = 0;
static bool g_dodgeRollPainAudioMuted = false;
static float g_dodgeRollReferenceHeading = 0.0f;
static bool g_dodgeRollInputUp = false;
static bool g_dodgeRollInputDown = false;
static bool g_dodgeRollInputRight = false;
static bool g_dodgeRollInputLeft = false;
static DWORD g_dodgeRollHeartbeatAt = 0;
static unsigned g_dodgeRollUpdateFrames = 0;
static unsigned g_dodgeRollAcceptedSequence = 0;
static DWORD g_dodgeRollStartedAt = 0;
static DWORD g_dodgeRollStageExpectedMs = 0;
static DWORD g_dodgeRollIFrameEndAt = 0;
static float g_dodgeRollAnimSpeed = 1.0f;
static bool g_dodgeRollIFrameActive = false;
static bool g_dodgeRollRestoreDamageable = true;
static int g_dodgeRollRestoreAlpha = 255;
// Rate limit for the rejection trace so a held Dive cannot flood the log.
static DWORD g_dodgeRollLastRejectAt = 0;

// The five-second idle heartbeat and every attempted-roll postcondition must be
// present in production too. The earlier combatRollLog helper was development-
// gated, so a shipped failure could not distinguish a dead dispatcher from no
// qualifying trigger.
static void dodgeRollLog(const std::string& line) {
	gtLog("roll", GT_INFO, line);
}

static void dodgeRollReject(DWORD now, const char* stage) {
	if (now - g_dodgeRollLastRejectAt < 400) return;
	g_dodgeRollLastRejectAt = now;
	dodgeRollLog(std::string("dive edge seen, roll refused at stage=") + stage);
}

// ---- One affordability gate (#179) and one charge site (#173) -------------
// #179 and #173 are the two halves of a single ownership defect. Nothing ever
// asked whether the roll could be paid for, and the payment itself had two
// possible ways to vanish: a second roll the engine chained without dropping
// its predicate false was never seen as a new roll, and a charge that did land
// was written behind the back of StaminaRateController, which pins the bar to
// its own target every frame. Below there is exactly one place that decides a
// roll may happen and exactly one place that takes the payment.
static bool g_dodgeRollGateSuppressing = false;
static unsigned g_dodgeRollGateSuppressFrames = 0;
static unsigned g_dodgeRollGateRefusals = 0;
static DWORD g_dodgeRollChargeVerifyAt = 0;
static unsigned g_dodgeRollChargeVerifySequence = 0;
static float g_dodgeRollChargeVerifyBar = 0.0f;
static float g_dodgeRollChargeVerifyApplied = 0.0f;

static bool dodgeRollAffordable(Player player) {
	if (!(g_combatRollStaminaCost > 0.0f)) return true;
	return GET_STAMINA_BAR(player) + 0.001f >= g_combatRollStaminaCost;
}

static bool dodgeRollGateApplies(Ped ped) {
	if (!g_combatRollEnabled || !(g_combatRollStaminaCost > 0.0f)) return false;
	if (!ped || !ENTITY::DOES_ENTITY_EXIST(ped)) return false;
	// INPUT_DIVE is shared with swimming and mounted contexts, where this feature
	// replaces nothing and charges nothing. Suppressing it there would delete a
	// free move rather than gate a paid one.
	return !PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE) && !PED::IS_PED_ON_MOUNT(ped) &&
		!PED::IS_PED_SWIMMING(ped);
}

// Refusing our replacement is not enough: Rockstar's own dive/roll would still
// play for free. Rockstar's sanctioned way to take this exact move away is a
// per-frame DISABLE_CONTROL_ACTION on INPUT_DIVE - beat_drunk_dueler.c:7950,
// mudtown3b.c:57928, braithwaites1.c:57448, sadie3.c:37055/37223, mary1.c:64301
// and 14 further Story call sites all write
// PAD::DISABLE_CONTROL_ACTION(0, joaat("INPUT_DIVE"), false), re-issued every
// frame because that is the native's required cadence. The third argument stays
// false exactly as Rockstar writes it, so INPUT_JUMP - and therefore climbing
// and ordinary jumping - is never touched. INPUT_DIVE is read here only to
// suppress and to recognise a chained roll; it is never sufficient to start one.
static bool dodgeRollApplyStaminaGate(Player player, Ped ped) {
	const bool applies = dodgeRollGateApplies(ped);
	const bool affordable = !applies || dodgeRollAffordable(player);
	const bool suppress = applies && !affordable;
	if (suppress) {
		PAD::DISABLE_CONTROL_ACTION(0, joaat("INPUT_DIVE"), FALSE);
		++g_dodgeRollGateSuppressFrames;
	}
	if (suppress != g_dodgeRollGateSuppressing) {
		g_dodgeRollGateSuppressing = suppress;
		std::ostringstream line;
		line << "stamina gate " << (suppress ? "closed" : "opened")
			<< " bar=" << GET_STAMINA_BAR(player)
			<< " cost=" << g_combatRollStaminaCost
			<< " applies=" << (applies ? 1 : 0)
			<< " suppressFrames=" << g_dodgeRollGateSuppressFrames
			<< " refusals=" << g_dodgeRollGateRefusals;
		dodgeRollLog(line.str());
	}
	return affordable;
}

static void dodgeRollRefuse(Player player, const char* reason, const char* trigger,
	bool engineRolledAnyway) {
	++g_dodgeRollGateRefusals;
	std::ostringstream line;
	line << "roll refused reason=" << reason
		<< " trigger=" << trigger
		<< " bar=" << GET_STAMINA_BAR(player)
		<< " cost=" << g_combatRollStaminaCost
		<< " gateSuppressFrames=" << g_dodgeRollGateSuppressFrames
		<< " engineRolledAnyway=" << (engineRolledAnyway ? 1 : 0)
		<< " refusals=" << g_dodgeRollGateRefusals;
	dodgeRollLog(line.str());
}

// The one and only place a roll is paid for. It routes the spend through the
// stamina controller so the controller's own target moves with it, then records
// both meters before and after. GET_STAMINA_BAR and GET_PED_STAMINA are logged
// side by side because the cost is configured in bar units and the controller
// works in ped units; the trace, not an assumption, settles whether they agree.
static void chargeDodgeRollStamina(Player player, Ped ped, DWORD now,
	unsigned sequence) {
	const float barBefore = GET_STAMINA_BAR(player);
	const float pedBefore = GET_PED_STAMINA(ped);
	BOOL writeAccepted = FALSE;
	float applied = 0.0f;
	if (g_combatRollStaminaCost > 0.0f)
		applied = g_playerStaminaRate.spend(ped, g_combatRollStaminaCost,
			&writeAccepted);
	const float barAfter = GET_STAMINA_BAR(player);
	const float pedAfter = GET_PED_STAMINA(ped);
	const float expectedSpent = (std::min)(barBefore,
		(std::max)(0.0f, g_combatRollStaminaCost));
	const float actualSpent = (std::max)(0.0f, barBefore - barAfter);
	const bool readbackMatched =
		std::fabs(actualSpent - expectedSpent) <= 0.05f;
	// A same-frame readback only proves the write executed. Re-read the bar a
	// quarter second later so a charge silently handed back by a competing
	// stamina owner is reported as "executed with no result" rather than passing
	// as a success.
	g_dodgeRollChargeVerifyAt = now + 250;
	g_dodgeRollChargeVerifySequence = sequence;
	g_dodgeRollChargeVerifyBar = barBefore;
	g_dodgeRollChargeVerifyApplied = actualSpent;
	std::ostringstream line;
	line << "roll charged sequence=" << sequence
		<< " requestedCost=" << g_combatRollStaminaCost
		<< " appliedByController=" << applied
		<< " writeAccepted=" << (writeAccepted ? 1 : 0)
		<< " bar=" << barBefore << "->" << barAfter
		<< " pedStamina=" << pedBefore << "->" << pedAfter
		<< " expectedSpent=" << expectedSpent
		<< " actualSpent=" << actualSpent
		<< " readbackMatched=" << (readbackMatched ? 1 : 0)
		<< " controllerOwns=" << (g_playerStaminaRate.owner == ped ? 1 : 0)
		<< " controllerTarget=" << g_playerStaminaRate.target;
	dodgeRollLog(line.str());
}

static void verifyDodgeRollStaminaCharge(Player player, Ped ped, DWORD now) {
	if (!g_dodgeRollChargeVerifyAt || now < g_dodgeRollChargeVerifyAt) return;
	g_dodgeRollChargeVerifyAt = 0;
	const float bar = GET_STAMINA_BAR(player);
	const float stillSpent = g_dodgeRollChargeVerifyBar - bar;
	// Natural recovery over 250 ms is small next to a real cost; anything that
	// has already given back more than half the payment is a refund, not regen.
	const bool refunded = g_dodgeRollChargeVerifyApplied > 0.0f &&
		stillSpent < g_dodgeRollChargeVerifyApplied * 0.5f;
	std::ostringstream line;
	line << "roll charge persistence sequence=" << g_dodgeRollChargeVerifySequence
		<< " appliedAtCharge=" << g_dodgeRollChargeVerifyApplied
		<< " barAtCharge=" << g_dodgeRollChargeVerifyBar
		<< " barNow=" << bar
		<< " stillSpent=" << stillSpent
		<< " refunded=" << (refunded ? 1 : 0)
		<< " controllerOwns=" << (g_playerStaminaRate.owner == ped ? 1 : 0)
		<< " controllerTarget=" << g_playerStaminaRate.target;
	dodgeRollLog(line.str());
}

// Combat Roll v1.03.1 is the working reference Lexer identified. Direct PE
// disassembly resolves these numeric words against the RDR3 eScriptedAnimFlags
// layout (Halen84/RDR3-Native-Flags-And-Enums, commit 1049e650):
//   0x00800012 = HOLD_LAST_FRAME | SECONDARY |
//                SKIP_IF_BLOCKED_BY_HIGHER_PRIORITY_TASK
//   0x00800010 = SECONDARY | SKIP_IF_BLOCKED_BY_HIGHER_PRIORITY_TASK
//   0x20000000 = BLENDOUT_WRT_LAST_FRAME (two-handed P2 addition)
// The reference never clears the secondary task first.
static bool dodgeRollUsesLongarm(Hash weapon) {
	return invoke<BOOL>(0x0556E9D2ECF39D01, weapon) != FALSE; // _IS_WEAPON_TWO_HANDED
}

static bool dodgeRollReferenceCameraPredicate() {
	// CombatRoll.asi 0x1800019C1 calls this exact CAM native when its
	// DISABLE_ON_FIRST_PERSON setting is enabled. The SDK leaves its semantic
	// name unresolved; do not substitute a plausible camera predicate.
	return invoke<BOOL>(0xD1BA66940E94C547) != FALSE;
}

static bool dodgeRollReferenceControl(const char* name) {
	return PAD::IS_CONTROL_PRESSED(0, joaat(name)) != FALSE;
}

// Literal control flow from CombatRoll.asi 0x1800011C0..0x1800013D4. The
// reference reads the four *_ONLY controls and does not derive an analog angle.
// This matters: the removed approximation mapped keyboard D to -90, whereas
// the binary maps RIGHT_ONLY to combatroll_fwd_*_90.
static const DodgeRollClip* dodgeRollReferencePair() {
	const bool up = g_dodgeRollInputUp =
		dodgeRollReferenceControl("INPUT_MOVE_UP_ONLY");
	const bool down = g_dodgeRollInputDown =
		dodgeRollReferenceControl("INPUT_MOVE_DOWN_ONLY");
	const bool right = g_dodgeRollInputRight =
		dodgeRollReferenceControl("INPUT_MOVE_RIGHT_ONLY");
	const bool left = g_dodgeRollInputLeft =
		dodgeRollReferenceControl("INPUT_MOVE_LEFT_ONLY");
	if (up && right) return &kDodgeRollClips[1];
	if (up && left) return &kDodgeRollClips[2];
	if (down && right) return &kDodgeRollClips[5];
	if (down && left) return &kDodgeRollClips[6];
	if (up) return &kDodgeRollClips[0];
	if (down) return &kDodgeRollClips[7];
	if (right) return &kDodgeRollClips[3];
	if (left) return &kDodgeRollClips[4];
	return &kDodgeRollClips[0];
}

static bool dodgeRollPairLoaded(const DodgeRollClip* pair) {
	if (!pair || !STREAMING::HAS_ANIM_DICT_LOADED(kDodgeRollDict)) return false;
	const float p1 = ENTITY::GET_ANIM_DURATION(kDodgeRollDict, pair->p1);
	const float p2 = ENTITY::GET_ANIM_DURATION(kDodgeRollDict, pair->p2);
	return std::isfinite(p1) && p1 > 0.05f &&
		std::isfinite(p2) && p2 > 0.05f;
}

static DWORD dodgeRollExpectedStageMs(const char* clip, float activePhase) {
	const float duration = ENTITY::GET_ANIM_DURATION(kDodgeRollDict, clip);
	if (!std::isfinite(duration) || duration <= 0.0f ||
		!std::isfinite(g_dodgeRollAnimSpeed) || g_dodgeRollAnimSpeed <= 0.0f)
		return 1000;
	return (DWORD)(duration * activePhase * 1000.0f / g_dodgeRollAnimSpeed);
}

static void restoreDodgeRollIFrames(Ped ped, const char* reason) {
	if (!g_dodgeRollIFrameActive) return;
	g_dodgeRollIFrameActive = false;
	if (!ped || !ENTITY::DOES_ENTITY_EXIST(ped)) return;
	ENTITY::SET_ENTITY_CAN_BE_DAMAGED(ped,
		g_dodgeRollRestoreDamageable ? TRUE : FALSE);
	ENTITY::SET_ENTITY_ALPHA(ped, g_dodgeRollRestoreAlpha, FALSE);
	std::ostringstream line;
	line << "i-frames ended reason=" << (reason ? reason : "timeline")
		<< " damageable=" << (ENTITY::_GET_ENTITY_CAN_BE_DAMAGED(ped) ? 1 : 0)
		<< " alpha=" << ENTITY::GET_ENTITY_ALPHA(ped)
		<< " elapsedMs=" << (GetTickCount() - g_dodgeRollStartedAt);
	dodgeRollLog(line.str());
}

static void beginDodgeRollIFrames(Ped ped, DWORD now) {
	g_dodgeRollStartedAt = now;
	g_dodgeRollIFrameEndAt = now +
		(DWORD)std::lround(g_combatRollInvulnerabilitySeconds * 1000.0f);
	g_dodgeRollRestoreDamageable =
		ENTITY::_GET_ENTITY_CAN_BE_DAMAGED(ped) != FALSE;
	g_dodgeRollRestoreAlpha = ENTITY::GET_ENTITY_ALPHA(ped);
	g_dodgeRollIFrameActive = g_combatRollInvulnerabilitySeconds > 0.0f;
	if (!g_dodgeRollIFrameActive) return;
	const int requestedAlpha = (int)std::lround(
		255.0f * g_combatRollInvulnerabilityOpacityPercent / 100.0f);
	const int appliedAlpha = (std::min)(g_dodgeRollRestoreAlpha,
		(std::max)(0, (std::min)(255, requestedAlpha)));
	ENTITY::SET_ENTITY_CAN_BE_DAMAGED(ped, FALSE);
	ENTITY::SET_ENTITY_ALPHA(ped, appliedAlpha, FALSE);
	std::ostringstream line;
	line << "i-frames began duration=" << g_combatRollInvulnerabilitySeconds
		<< " opacityPercent=" << g_combatRollInvulnerabilityOpacityPercent
		<< " priorDamageable=" << (g_dodgeRollRestoreDamageable ? 1 : 0)
		<< " priorAlpha=" << g_dodgeRollRestoreAlpha
		<< " damageableReadback="
		<< (ENTITY::_GET_ENTITY_CAN_BE_DAMAGED(ped) ? 1 : 0)
		<< " alphaReadback=" << ENTITY::GET_ENTITY_ALPHA(ped);
	dodgeRollLog(line.str());
}

static void finishDirectionalDodgeRoll(Ped ped, const char* reason) {
	restoreDodgeRollIFrames(ped, reason ? reason : "finish");
	if (ped && g_dodgeRollStage != DodgeRollStage::Idle && g_dodgeRollPair) {
		const char* clip = g_dodgeRollStage == DodgeRollStage::P1 ?
			g_dodgeRollPair->p1 : g_dodgeRollPair->p2;
		TASK::STOP_ANIM_TASK(ped, kDodgeRollDict, clip, 2.0f);
	}
	if (ped && g_dodgeRollWasCrouched) {
		// Combat Roll's crouched path restores crouch with the exact native tail
		// (state=1, p2=1, immediately=0) after stopping P2.
		invoke<Void>(0x7DE9692C6F64CFE8, ped, TRUE, 1, FALSE);
	}
	if (ped && g_dodgeRollPainAudioMuted)
		AUDIO::DISABLE_PED_PAIN_AUDIO(ped, FALSE);
	if (reason) dodgeRollLog(std::string("roll finished reason=") + reason);
	g_dodgeRollStage = DodgeRollStage::Idle;
	g_dodgeRollPair = nullptr;
	g_dodgeRollStageAt = 0;
	g_dodgeRollWeapon = 0;
	g_dodgeRollWasCrouched = false;
	g_dodgeRollPainAudioMuted = false;
	g_dodgeRollReferenceHeading = 0.0f;
	g_dodgeRollClipName = "";
	g_dodgeRollStartedAt = 0;
	g_dodgeRollStageExpectedMs = 0;
	g_dodgeRollIFrameEndAt = 0;
	g_dodgeRollAnimSpeed = 1.0f;
}

static void advanceDirectionalDodgeRoll(Ped ped, DWORD now, bool blocked) {
	if (g_dodgeRollStage == DodgeRollStage::Idle || !g_dodgeRollPair) return;
	if (!ped || blocked || PED::IS_PED_RAGDOLL(ped) || PED::IS_PED_FALLING(ped)) {
		finishDirectionalDodgeRoll(ped, "interrupted");
		return;
	}
	// CombatRoll.asi does this inside both of its bounded animation polling
	// loops: P1 at 0x1800015D0..0x18000165A and P2 at
	// 0x1800017A0..0x180001846. It reads the heading back immediately after the
	// camera alignment, then reapplies that resolved value until P2 finishes.
	// Our one-shot alignment omitted those writes, allowing the roll clip's yaw
	// to accumulate into the reported 270-degree spin. This is live-roll state,
	// never an ordinary-locomotion/permanent per-frame heading owner.
	SET_ENTITY_HEADING(ped, g_dodgeRollReferenceHeading);
	if (g_dodgeRollIFrameActive && now >= g_dodgeRollIFrameEndAt)
		restoreDodgeRollIFrames(ped, "configured boundary");

	if (!g_dodgeRollSurvivalLogged && now >= g_dodgeRollSurvivalAt) {
		g_dodgeRollSurvivalLogged = true;
		const bool alive = ENTITY::IS_ENTITY_PLAYING_ANIM(ped, kDodgeRollDict,
			g_dodgeRollClipName, 3) != FALSE;
		std::ostringstream survive;
		survive << "roll survival t+150ms clip=" << g_dodgeRollClipName
			<< " alive=" << (alive ? 1 : 0)
			<< " ragdoll=" << (PED::IS_PED_RAGDOLL(ped) ? 1 : 0);
		survive << " headingPinned=" << g_dodgeRollReferenceHeading
			<< " headingReadback=" << ENTITY_HEADING(ped);
		dodgeRollLog(survive.str());
		if (!alive) {
			finishDirectionalDodgeRoll(ped, "task did not survive");
			return;
		}
	}
	// _GET_ENTITY_ANIM_CURRENT_TIME can report 1.0 for a task that never bound.
	// Do not interpret phase until the reference-compatible task predicate has
	// positively observed this stage alive.
	if (!g_dodgeRollSurvivalLogged) return;

	const char* activeClip = g_dodgeRollStage == DodgeRollStage::P1 ?
		g_dodgeRollPair->p1 : g_dodgeRollPair->p2;
	const float phase = ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(ped,
		kDodgeRollDict, activeClip);
	const DWORD age = now - g_dodgeRollStageAt;
	ENTITY::_SET_ENTITY_ANIM_SPEED(ped, kDodgeRollDict, activeClip,
		g_dodgeRollAnimSpeed);
	if (g_dodgeRollStage == DodgeRollStage::P1) {
		// Combat Roll v1.03.1 switches from launch P1 to recovery P2 at 0.84.
		// The watchdog is only a bounded escape if the phase native never advances.
		if (phase < 0.84f && age < g_dodgeRollStageExpectedMs + 750) return;
		const bool longarm = dodgeRollUsesLongarm(g_dodgeRollWeapon);
		const int flags = longarm ? 0x20800010 : 0x00800010;
		const char* taskFilter = longarm ? "noleftarm_filter" : "";
		TASK::TASK_PLAY_ANIM(ped, kDodgeRollDict, g_dodgeRollPair->p2,
			8.0f, -8.0f, -1, flags, 0.0f,
			FALSE, 0x020000A0, FALSE, taskFilter, FALSE);
		// P1 receives the configured scale on its issue frame. P2 must do the
		// same. Waiting for the 150 ms survival readback let the recovery run at
		// Rockstar's default speed for a material part of its short active phase,
		// so InvulnerabilitySeconds + RecoverySeconds was not the visible total.
		ENTITY::_SET_ENTITY_ANIM_SPEED(ped, kDodgeRollDict,
			g_dodgeRollPair->p2, g_dodgeRollAnimSpeed);
		g_dodgeRollStage = DodgeRollStage::P2;
		g_dodgeRollStageAt = now;
		g_dodgeRollClipName = g_dodgeRollPair->p2;
		g_dodgeRollSurvivalAt = now + 150;
		g_dodgeRollSurvivalLogged = false;
		g_dodgeRollStageExpectedMs = dodgeRollExpectedStageMs(
			g_dodgeRollPair->p2, g_dodgeRollWasCrouched ? 0.05f : 0.20f);
		std::ostringstream line;
		line << "roll P1->P2 phase=" << phase << " clip=" << g_dodgeRollPair->p2
			<< " flags=0x" << std::hex << flags << std::dec
			<< " weaponFilter=" << (longarm ? "noleftarm_filter" : "none");
		dodgeRollLog(line.str());
		return;
	}

	// The reference stops standing P2 at 0.20, crouched P2 at 0.05, then
	// restores crouch. Do not hold the clip for its entire authored duration.
	const float stopPhase = g_dodgeRollWasCrouched ? 0.05f : 0.20f;
	if (phase >= stopPhase || age >= g_dodgeRollStageExpectedMs + 750)
		finishDirectionalDodgeRoll(ped,
			age >= g_dodgeRollStageExpectedMs + 750 ? "P2 watchdog" : "P2 phase");
}

// Integrator entry point. This replaces updateCombatRoll at the existing
// dispatcher call; it deliberately has a distinct name so the old #208 code
// can be removed by its owning integration change without a symbol collision.
static void updateDirectionalDodgeRoll(Player player, Ped ped, DWORD now,
	bool blocked) {
	++g_dodgeRollUpdateFrames;
	if (ped != g_dodgeRollPed) {
		finishDirectionalDodgeRoll(g_dodgeRollPed, nullptr);
		g_dodgeRollPed = ped;
		g_dodgeRollPredicateWasActive = false;
		g_dodgeRollTriggerPending = false;
		g_dodgeRollPendingPair = nullptr;
		g_dodgeRollPendingAt = 0;
	}
	// The gate runs before anything else and on every frame, including while
	// P1/P2 own the ped, so a roll that cannot be paid for is prevented at the
	// input rather than merely refused after Rockstar has already started it.
	const bool affordable = dodgeRollApplyStaminaGate(player, ped);
	verifyDodgeRollStaminaCharge(player, ped, now);

	// Sample the engine predicate before the active-stage return. The prior
	// ordering did not observe a false predicate while P1/P2 owned the ped. A
	// rapid second roll could then remain part of the first latched true interval
	// and bypass both the replacement task and its one-time Stamina charge.
	const bool engineCombatRoll = ped && PED_IS_DOING_COMBAT_ROLL(ped);
	const bool predicateEdge = engineCombatRoll && !g_dodgeRollPredicateWasActive;
	g_dodgeRollPredicateWasActive = engineCombatRoll;
	// Sampling earlier closes the case where a false frame exists. It cannot
	// close the case where the engine chains a second roll without ever dropping
	// the predicate, because that interval produces no rising edge at all and the
	// second roll is then swallowed by the first - free. A fresh Dive press while
	// the engine is already rolling is the only remaining signal that another
	// roll was asked for. It is never sufficient on its own: engineCombatRoll
	// must already be true, so this can only ever split one true interval into
	// two rolls, never invent a roll.
	const Hash diveControl = joaat("INPUT_DIVE");
	const bool divePressEdge = PAD::IS_CONTROL_JUST_PRESSED(0, diveControl) != FALSE ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, diveControl) != FALSE;
	const bool chainedEdge = engineCombatRoll && !predicateEdge && divePressEdge;
	if ((predicateEdge || chainedEdge) && g_combatRollEnabled && ped) {
		const char* trigger = chainedEdge ? "chained-dive-press"
			: "engine-predicate-edge";
		if (!affordable) {
			// The gate above should have stopped the press reaching the engine. If
			// the engine rolled anyway, this line is the breach report, not a
			// silent skip.
			dodgeRollRefuse(player, "insufficient-stamina", trigger, predicateEdge);
			g_dodgeRollTriggerPending = false;
			g_dodgeRollPendingPair = nullptr;
		} else {
			g_dodgeRollPendingPair = dodgeRollReferencePair();
			g_dodgeRollTriggerPending = true;
			g_dodgeRollPendingAt = now;
			std::ostringstream edge;
			edge << "engine combat-roll predicate edge controls="
				<< (g_dodgeRollInputUp ? 1 : 0) << ","
				<< (g_dodgeRollInputDown ? 1 : 0) << ","
				<< (g_dodgeRollInputRight ? 1 : 0) << ","
				<< (g_dodgeRollInputLeft ? 1 : 0)
				<< " pair=" << g_dodgeRollPendingPair->p1 << "/"
				<< g_dodgeRollPendingPair->p2
				<< " trigger=" << trigger
				<< " activeStage=" << (int)g_dodgeRollStage;
			dodgeRollLog(edge.str());
		}
	}

	// Once the reference sequence starts, its own animation phases own the move.
	// Broad dispatcher gates must not tear it down midway; only the direct
	// fall/ragdoll/ped checks in advanceDirectionalDodgeRoll can interrupt it.
	// A rapid next predicate edge remains pending until P2 releases ownership.
	advanceDirectionalDodgeRoll(ped, now, false);
	if (g_dodgeRollStage != DodgeRollStage::Idle) return;

	if (now - g_dodgeRollHeartbeatAt >= 5000) {
		g_dodgeRollHeartbeatAt = now;
		std::ostringstream heartbeat;
		heartbeat << "heartbeat stage=idle enabled=" << (g_combatRollEnabled ? 1 : 0)
			<< " ped=" << (ped ? 1 : 0)
			<< " blockedHint=" << (blocked ? 1 : 0)
			<< " engineCombatRoll=" << (engineCombatRoll ? 1 : 0)
			<< " pending=" << (g_dodgeRollTriggerPending ? 1 : 0)
			<< " cost=" << g_combatRollStaminaCost
			<< " bar=" << GET_STAMINA_BAR(player)
			<< " affordable=" << (affordable ? 1 : 0)
			<< " gateClosed=" << (g_dodgeRollGateSuppressing ? 1 : 0)
			<< " gateSuppressFrames=" << g_dodgeRollGateSuppressFrames
			<< " refusals=" << g_dodgeRollGateRefusals
			<< " charged=" << g_dodgeRollAcceptedSequence
			<< " dictLoaded="
			<< (STREAMING::HAS_ANIM_DICT_LOADED(kDodgeRollDict) ? 1 : 0)
			<< " frames=" << g_dodgeRollUpdateFrames;
		dodgeRollLog(heartbeat.str());
	}

	if (!g_combatRollEnabled || !ped) {
		g_dodgeRollTriggerPending = false;
		g_dodgeRollPendingPair = nullptr;
		return;
	}

	if (!STREAMING::HAS_ANIM_DICT_LOADED(kDodgeRollDict))
		STREAMING::REQUEST_ANIM_DICT(kDodgeRollDict);
	if (!g_dodgeRollTriggerPending) return;
	if (now - g_dodgeRollPendingAt > 5000) {
		dodgeRollReject(now, "engine predicate seen but anim pair did not load");
		g_dodgeRollTriggerPending = false;
		g_dodgeRollPendingPair = nullptr;
		return;
	}
	if (!dodgeRollPairLoaded(g_dodgeRollPendingPair)) return;
	// #172: first-person rolls are not a supported option. The reference
	// predicate is now an unconditional rejection boundary.
	if (dodgeRollReferenceCameraPredicate()) {
		dodgeRollReject(now, "engine predicate seen in disabled first person");
		g_dodgeRollTriggerPending = false;
		g_dodgeRollPendingPair = nullptr;
		return;
	}

	// Second layer of the same gate. A roll queued while the bar was sufficient
	// can reach this point after the previous roll has already spent it, so
	// affordability is re-read against live state rather than the queued state.
	if (!dodgeRollAffordable(player)) {
		dodgeRollRefuse(player, "insufficient-stamina-at-issue", "queued-roll",
			engineCombatRoll);
		g_dodgeRollTriggerPending = false;
		g_dodgeRollPendingPair = nullptr;
		return;
	}

	const DodgeRollClip* clip = g_dodgeRollPendingPair;
	g_dodgeRollTriggerPending = false;
	g_dodgeRollPendingPair = nullptr;
	const Hash weapon = GET_CURRENT_WEAPON(ped);
	// CombatRoll.asi 0x1800014BC..0x180001577 aligns the ped to absolute gameplay
	// camera yaw, disables pain audio, and issues P1. It performs no Dive control
	// suppression, path probe, velocity write, teleport, or ragdoll request.
	const Vector3 cameraRotation = CAM::GET_GAMEPLAY_CAM_ROT(2);
	const bool wasCrouched = GET_PED_CROUCH_MOVEMENT(ped);
	SET_ENTITY_HEADING(ped, cameraRotation.z);
	// The reference reads SET_ENTITY_HEADING back and pins that accepted value,
	// not the unverified request, for both phase loops.
	g_dodgeRollReferenceHeading = ENTITY_HEADING(ped);
	AUDIO::DISABLE_PED_PAIN_AUDIO(ped, TRUE);
	g_dodgeRollPainAudioMuted = true;
	TASK::TASK_PLAY_ANIM(ped, kDodgeRollDict, clip->p1, 8.0f, -8.0f,
		-1, 0x00800012, 0.0f, FALSE, 0x020000A0, FALSE, "", FALSE);
	const float p1Duration = ENTITY::GET_ANIM_DURATION(kDodgeRollDict, clip->p1);
	const float p2Duration = ENTITY::GET_ANIM_DURATION(kDodgeRollDict, clip->p2);
	const float p2StopPhase = wasCrouched ? 0.05f : 0.20f;
	const float authoredActiveSeconds = p1Duration * 0.84f +
		p2Duration * p2StopPhase;
	const float requestedTotalSeconds = (std::max)(0.05f,
		g_combatRollInvulnerabilitySeconds + g_combatRollRecoverySeconds);
	g_dodgeRollAnimSpeed = (std::max)(0.05f, (std::min)(10.0f,
		authoredActiveSeconds / requestedTotalSeconds));
	g_dodgeRollStageExpectedMs = dodgeRollExpectedStageMs(clip->p1, 0.84f);
	ENTITY::_SET_ENTITY_ANIM_SPEED(ped, kDodgeRollDict, clip->p1,
		g_dodgeRollAnimSpeed);
	beginDodgeRollIFrames(ped, now);
	// #17/#173: charge once, only after the authored replacement roll is actually
	// issued, and only through chargeDodgeRollStamina - the single charge site.
	// A zero setting deliberately leaves stamina alone.
	const unsigned rollSequence = ++g_dodgeRollAcceptedSequence;
	chargeDodgeRollStamina(player, ped, now, rollSequence);
	g_dodgeRollStage = DodgeRollStage::P1;
	g_dodgeRollPair = clip;
	g_dodgeRollStageAt = now;
	g_dodgeRollWeapon = weapon;
	g_dodgeRollWasCrouched = wasCrouched;
	g_dodgeRollClipName = clip->p1;
	g_dodgeRollSurvivalAt = now + 150;
	g_dodgeRollSurvivalLogged = false;
	std::ostringstream line;
	line << "roll issued sequence=" << rollSequence
		<< " trigger=engineCombatRoll p1=" << clip->p1
		<< " p2=" << clip->p2 << " dict=loaded"
		<< " cameraYaw=" << cameraRotation.z
		<< " headingApplied=" << g_dodgeRollReferenceHeading
		<< " flags=0x00800012 taskFilter=0x20000A0 slot=secondary painAudio=muted"
		<< " crouched=" << (g_dodgeRollWasCrouched ? 1 : 0)
		<< " chargeSequence=" << rollSequence
		<< " requestedCost=" << g_combatRollStaminaCost
		<< " barAfterCharge=" << GET_STAMINA_BAR(player);
	line << " iFrameSeconds=" << g_combatRollInvulnerabilitySeconds
		<< " recoverySeconds=" << g_combatRollRecoverySeconds
		<< " totalSeconds=" << requestedTotalSeconds
		<< " authoredActiveSeconds=" << authoredActiveSeconds
		<< " animSpeed=" << g_dodgeRollAnimSpeed;
	dodgeRollLog(line.str());
}
