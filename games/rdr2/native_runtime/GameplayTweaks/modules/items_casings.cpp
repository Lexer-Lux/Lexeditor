// GameplayTweaks feature module: Spent casings, bottle recovery, empty bottles, and carried-mask synchronization.
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


// Same texture ids the catalog assigns to each casing item, so the feed
// card matches the satchel icon until custom icons land.
// Real texture ids only: AMMO_SHOTGUN is a vanilla texture, the bullet
// casings share vanilla's AMMO_BULLET_NORMAL until custom icons land.
// (The old AMMO_REVOLVER/PISTOL/... ids existed nowhere - invented names.)
// One pickup definition per caliber: the engine takes the prompt's label
// (and possibly the grant) from the pickup's reward, so a shared definition
// made every casing announce itself as .357 Magnum.
static Hash casingPickupType(Hash item) {
	if (item == joaat("LEX_CASING_REVOLVER")) return joaat("PICKUP_LEX_CASING_REVOLVER");
	if (item == joaat("LEX_CASING_PISTOL")) return joaat("PICKUP_LEX_CASING_PISTOL");
	if (item == joaat("LEX_CASING_REPEATER")) return joaat("PICKUP_LEX_CASING_REPEATER");
	if (item == joaat("LEX_CASING_RIFLE")) return joaat("PICKUP_LEX_CASING_RIFLE");
	if (item == joaat("LEX_CASING_SHOTGUN")) return joaat("PICKUP_LEX_CASING_SHOTGUN");
	if (item == joaat("LEX_CASING_VARMINT")) return joaat("PICKUP_LEX_CASING_VARMINT");
	return 0;
}

static const char* casingIconName(Hash item) {
	if (item == joaat("LEX_CASING_PISTOL")) return "LEX_CASING_225";
	if (item == joaat("LEX_CASING_REVOLVER")) return "LEX_CASING_307";
	if (item == joaat("LEX_CASING_REPEATER")) return "LEX_CASING_444";
	if (item == joaat("LEX_CASING_RIFLE")) return "LEX_CASING_444";
	if (item == joaat("LEX_CASING_VARMINT")) return "AMMO_RIFLE";
	return "LEX_CASING_SHOTGUN";
}

static const char* casingIconDict(Hash item) {
	if (item == joaat("LEX_CASING_VARMINT")) return "INVENTORY_ITEMS";
	// The custom drawings extend a complete replacement of GENERIC_TEXTURES.
	// Story shop scripts use this dictionary directly, and its small complete
	// source can be preserved safely without the converter ceiling hit by the
	// 803-texture INVENTORY_ITEMS dictionary.
	return "GENERIC_TEXTURES";
}

// Item display name straight from the game's localization (strings.gxt2 is
// keyed by the item hash), so renaming an item in LEXEDITOR is reflected
// automatically. Family names are only a fallback for missing labels.
static std::string casingDisplayName(Hash item) {
	const char* label = invoke<const char*>(0xBD5DD5EAE2B6CE14, item); // GET_STRING_FROM_HASH_KEY
	if (label && label[0] && strcmp(label, "NULL") != 0) return label;
	if (item == joaat("LEX_CASING_VARMINT") || item == joaat("LEX_CASING_PISTOL")) return ".225 Casing";
	if (item == joaat("LEX_CASING_REVOLVER")) return ".307 Casing";
	if (item == joaat("LEX_CASING_REPEATER") || item == joaat("LEX_CASING_RIFLE")) return ".444 Casing";
	if (item == joaat("LEX_CASING_SHOTGUN")) return "Shotgun Shell";
	return "Casing";
}

static float casingRandom(float minimum, float maximum) {
	g_casingRng ^= g_casingRng << 13; g_casingRng ^= g_casingRng >> 17; g_casingRng ^= g_casingRng << 5;
	return minimum + (maximum - minimum) * (float)(g_casingRng & 0xFFFF) / 65535.0f;
}

static Hash casingItemForWeapon(Hash weapon) {
	if (weapon == joaat("WEAPON_RIFLE_VARMINT")) return joaat("LEX_CASING_PISTOL");
	Hash group = WEAPON::GET_WEAPONTYPE_GROUP(weapon);
	if (group == joaat("GROUP_REVOLVER")) return joaat("LEX_CASING_REVOLVER");
	if (group == joaat("GROUP_PISTOL")) return joaat("LEX_CASING_PISTOL");
	if (group == joaat("GROUP_REPEATER")) return joaat("LEX_CASING_REPEATER");
	if (group == joaat("GROUP_RIFLE") || group == joaat("GROUP_SNIPER")) return joaat("LEX_CASING_REPEATER");
	if (group == joaat("GROUP_SHOTGUN")) return joaat("LEX_CASING_SHOTGUN");
	return 0;
}

static bool casingWeaponIsRevolver(Hash weapon) {
	return WEAPON::GET_WEAPONTYPE_GROUP(weapon) == joaat("GROUP_REVOLVER");
}

static bool casingWeaponIsPistol(Hash weapon) {
	return WEAPON::GET_WEAPONTYPE_GROUP(weapon) == joaat("GROUP_PISTOL");
}

static bool casingWeaponIsBreakAction(Hash weapon) {
	return weapon == joaat("WEAPON_SHOTGUN_SAWEDOFF") ||
		weapon == joaat("WEAPON_SHOTGUN_SAWEDOFF_CHARLES") ||
		weapon == joaat("WEAPON_SHOTGUN_DOUBLEBARREL") ||
		weapon == joaat("WEAPON_SHOTGUN_DOUBLEBARREL_EXOTIC");
}

// One prop per caliber - the game ships a whole family of shell models
// (s_shell_9mm / _45mm / _rifle / _22wrf / _sg), not the single generic
// casing the inherited code assumed. Carriable mode maps model -> item, so
// distinct models are what give each caliber its own collectible.
static Hash casingModelForItem(Hash item) {
	if (item == joaat("LEX_CASING_REVOLVER")) return joaat("s_shell_45mm");
	if (item == joaat("LEX_CASING_PISTOL")) return joaat("s_shell_9mm");
	if (item == joaat("LEX_CASING_RIFLE")) return joaat("s_shell_rifle");
	if (item == joaat("LEX_CASING_SHOTGUN")) return joaat("s_shell_sg");
	if (item == joaat("LEX_CASING_VARMINT")) return joaat("s_shell_22wrf");
	return joaat("p_bulletcasing01x"); // repeater
}

static void requestCasingModels() {
	// Only ask for models that are not already resident. Re-requesting all
	// seven every frame (v7.1) thrashed the streamer and made spawned casings
	// pop in and out, taking their glint and glow with them.
	static const char* kModels[] = { "s_shell_45mm", "s_shell_9mm", "s_shell_rifle",
		"s_shell_sg", "s_shell_22wrf", "p_bulletcasing01x", "p_shellshotgun01x" };
	for (const char* m : kModels) {
		Hash h = joaat(m);
		if (!STREAMING::HAS_MODEL_LOADED(h)) STREAMING::REQUEST_MODEL(h, FALSE);
	}
}

// #130 A pickup placement and its physical pickup object are created on
// DIFFERENT frames. CREATE_PICKUP registers the placement; CPickupManager
// builds the object afterwards, so GET_PICKUP_OBJECT returns 0 on the frame
// the pickup is made. Every Rockstar caller that needs the object polls for it
// from a later update behind a latch and never reads it at the creation site:
//   rcm_crackpot3.c:6077 creates, :2318 polls under `if (!bLocal_44)`
//   gang3.c:52146 creates, :52929 early-returns until the object exists
//   winter1.c:57698 polls under `if (!func_177(iLocal_908, 32))`
//   guama2.c:25662 and braithwaites3.c:54573 use the same guard
// The ejection impulse therefore cannot be applied at spawn time. It is parked
// here against the pickup handle and applied on the frame the object appears,
// so the casing still leaves the weapon with the motion #45 asked for.
struct PendingCasingImpulse {
	Pickup pickup = 0;
	Vector3 rotation = {};
	Vector3 velocity = {};
};
static std::vector<PendingCasingImpulse> g_casingPendingImpulses;

// How long a placed pickup may go without producing its object before we treat
// it as genuinely dead and reclaim it. Generous: the wait is a streaming wait.
static const DWORD kCasingPickupObjectWaitMs = 3000;

static void forgetPendingCasingImpulse(Pickup pickup) {
	for (size_t i = 0; i < g_casingPendingImpulses.size(); ++i) {
		if (g_casingPendingImpulses[i].pickup == pickup) {
			g_casingPendingImpulses.erase(g_casingPendingImpulses.begin() + i);
			return;
		}
	}
}

static void applyCasingEjection(Object obj, const Vector3& rotation, const Vector3& velocity) {
	ENTITY::SET_ENTITY_DYNAMIC(obj, TRUE);
	ENTITY::SET_ENTITY_COLLISION(obj, TRUE, TRUE);
	ENTITY::SET_ENTITY_HAS_GRAVITY(obj, TRUE);
	PHYSICS::ACTIVATE_PHYSICS(obj);
	ENTITY::SET_ENTITY_ROTATION(obj, rotation.x, rotation.y, rotation.z, 2, TRUE);
	SET_ENTITY_VELOCITY(obj, velocity);
}

static bool applyPendingCasingImpulse(Pickup pickup, Object obj) {
	for (size_t i = 0; i < g_casingPendingImpulses.size(); ++i) {
		if (g_casingPendingImpulses[i].pickup != pickup) continue;
		applyCasingEjection(obj, g_casingPendingImpulses[i].rotation,
			g_casingPendingImpulses[i].velocity);
		g_casingPendingImpulses.erase(g_casingPendingImpulses.begin() + i);
		return true;
	}
	return false;
}

static void deleteCasing(SpentCasing& casing) {
	if (casing.fxHandle) {
		GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
		casing.fxHandle = 0;
	}
	if (casing.pickup) forgetPendingCasingImpulse(casing.pickup);
	if (casing.pickup && OBJECT::DOES_PICKUP_EXIST(casing.pickup)) {
		OBJECT::REMOVE_PICKUP(casing.pickup);
	} else if (casing.object && ENTITY::DOES_ENTITY_EXIST(casing.object)) {
		Object obj = casing.object;
		OBJECT::DELETE_OBJECT(&obj);
	}
	casing.pickup = 0;
	casing.object = 0;
}

static void trimSpentCasings() {
	while ((int)g_spentCasings.size() >= g_spentCasingMaximum && !g_spentCasings.empty()) {
		deleteCasing(g_spentCasings.front());
		g_spentCasings.erase(g_spentCasings.begin());
	}
}

static void ensureCasingPrompt();

struct CasingEjectionTuning {
	float spawnRight;
	float spawnForward;
	float spawnUp;
	float ordinalSpread;
	float ejectRight;
	float ejectForward;
	float ejectUp;
	float velocityJitter;
	float inheritedVelocity;
	float reloadMomentum;
};

static float casingTuned(const char* key, float fallback, float minimum, float maximum) {
	return (std::max)(minimum, (std::min)(maximum,
		readF("CasingEjection", key, fallback)));
}

static CasingEjectionTuning casingEjectionTuning() {
	// Read at spawn time: calibration edits take effect on the very next casing
	// without adding another shared loadConfig dependency.
	CasingEjectionTuning t = {};
	t.spawnRight = casingTuned("SpawnRight", -0.08f, -0.50f, 0.50f);
	t.spawnForward = casingTuned("SpawnForward", -0.02f, -0.50f, 0.50f);
	t.spawnUp = casingTuned("SpawnUp", 0.04f, -0.30f, 0.50f);
	t.ordinalSpread = casingTuned("ReloadOrdinalSpread", 0.025f, 0.0f, 0.15f);
	t.ejectRight = casingTuned("EjectRight", -1.15f, -5.0f, 5.0f);
	t.ejectForward = casingTuned("EjectForward", -0.10f, -5.0f, 5.0f);
	t.ejectUp = casingTuned("EjectUp", 0.85f, -2.0f, 5.0f);
	t.velocityJitter = casingTuned("VelocityJitter", 0.16f, 0.0f, 2.0f);
	t.inheritedVelocity = casingTuned("InheritedPedVelocity", 1.0f, 0.0f, 2.0f);
	t.reloadMomentum = casingTuned("ReloadMomentumMultiplier", 0.55f, 0.0f, 2.0f);
	return t;
}

// Spawns the physical casing near the weapon (or at the ped for reload dumps).
static void spawnCasingObject(Ped ped, Hash item, DWORD now, int ordinal, bool atPed) {
	GtLogStream log("casings", GT_INFO);
	Hash model = casingModelForItem(item);
	if (!STREAMING::HAS_MODEL_LOADED(model)) {
		STREAMING::REQUEST_MODEL(model, FALSE);
		// never drop a casing just because a per-caliber prop is slow (or
		// absent): fall back to the generic one, which is always loaded
		Hash fallback = joaat("p_bulletcasing01x");
		if (model != fallback && STREAMING::HAS_MODEL_LOADED(fallback)) {
			GtLogStream("casings", GT_WARN)
				<< "model 0x" << std::hex << model << " unavailable, using generic casing\n" << std::dec;
			model = fallback;
		} else {
			GtLogStream("casings", GT_WARN)
				<< "model pending=0x" << std::hex << model << std::dec << "\n";
			return;
		}
	}
	// Always prefer the weapon entity — during a revolver reload the gun is
	// in hand, so casings leave the CYLINDER, not the ped origin (which sits
	// at the pelvis and made reload dumps "fall out of my ass").
	Entity weaponEntity = WEAPON::GET_CURRENT_PED_WEAPON_ENTITY_INDEX(ped, 0);
	bool fromWeapon = weaponEntity && ENTITY::DOES_ENTITY_EXIST(weaponEntity);
	Entity basis = fromWeapon ? weaponEntity : ped;
	Vector3 right = {}, forward = {}, up = {}, position = {};
	ENTITY::GET_ENTITY_MATRIX(basis, &right, &forward, &up, &position);
	const CasingEjectionTuning tuning = casingEjectionTuning();
	const float spread = ordinal * tuning.ordinalSpread;
	// ped fallback: offset to hand height instead of the pelvis origin
	const float fallbackUp = fromWeapon ? 0.0f : 0.91f;
	const float fallbackRight = fromWeapon ? 0.0f : -0.22f;
	Vector3 spawn = {
		position.x + right.x * (tuning.spawnRight + fallbackRight - spread) +
			forward.x * tuning.spawnForward + up.x * (tuning.spawnUp + fallbackUp),
		position.y + right.y * (tuning.spawnRight + fallbackRight - spread) +
			forward.y * tuning.spawnForward + up.y * (tuning.spawnUp + fallbackUp),
		position.z + right.z * (tuning.spawnRight + fallbackRight - spread) +
			forward.z * tuning.spawnForward + up.z * (tuning.spawnUp + fallbackUp)
	};
	trimSpentCasings();
	// The six PICKUP_LEX_CASING_<CALIBER> entries (pickups.meta:3894-4078) each
	// carry ManualPickUp + RequiresButtonPressToPickup + RequiresPickingUpAnim
	// and a brass glow, so the ENGINE supplies the prompt, the bend animation and
	// the corona. Their rewards are CPickupRewardAmmo records with a SatchelItem
	// (pickups.meta:5034-5075), the same shape as the 82 vanilla ammo rewards.
	// CREATE_PICKUP places the pickup; its object arrives on a later frame.
	bool asPickup = g_casingMode == 0;
	Pickup pickup = 0;
	Object obj = 0;
	bool objectPending = false;
	Hash pickupType = casingPickupType(item);
	if (asPickup && !pickupType) asPickup = false;
	if (asPickup) {
		pickup = OBJECT::CREATE_PICKUP(pickupType,
			spawn.x, spawn.y, spawn.z, 0, -1, TRUE, 0, 0, 0.0f, 0);
		const bool placed = pickup && OBJECT::DOES_PICKUP_EXIST(pickup);
		if (placed) obj = OBJECT::GET_PICKUP_OBJECT(pickup);
		if (!placed) {
			// The only genuine creation failure: the placement itself was refused
			// (unknown pickup type, or the pickup pool is full).
			GtLogStream("casings", GT_WARN)
				<< "pickup placement failed type=0x" << std::hex << pickupType << std::dec
				<< " handle=" << pickup << " - falling back to plain object\n";
			pickup = 0;
			asPickup = false;
			obj = 0;
			ensureCasingPrompt();
		} else if (!obj || !ENTITY::DOES_ENTITY_EXIST(obj)) {
			// NOT a failure - see the PendingCasingImpulse comment above. The old
			// code logged "PICKUP_LEX_CASING create failed" here and then DELETED a
			// pickup that had been placed correctly, which is why every casing ended
			// up an inert object and the acquisition card never fired (#130). The
			// message was false: the pickup was never the thing that failed.
			obj = 0;
			objectPending = true;
			log << "pickup placed type=0x" << std::hex << pickupType << std::dec
				<< " pickup=" << pickup << " object pending\n";
		}
	}
	if (!asPickup && !obj)
		obj = OBJECT::CREATE_OBJECT(model, spawn.x, spawn.y, spawn.z, FALSE, FALSE, TRUE, FALSE, FALSE);
	if (!objectPending && (!obj || !ENTITY::DOES_ENTITY_EXIST(obj))) {
		GtLogStream("casings", GT_ERROR)
			<< "casing object create failed model=0x" << std::hex << model << std::dec << "\n";
		if (pickup && OBJECT::DOES_PICKUP_EXIST(pickup)) OBJECT::REMOVE_PICKUP(pickup);
		return;
	}
	// A dynamic object created with no velocity simply drops straight down. Give
	// it the actual motion requested by #45: inherit the shooter's movement, then
	// add local weapon-side ejection with small per-casing variation. Reload dumps
	// use the same direction at lower strength so a full cylinder fans out rather
	// than exploding across the room.
	const float momentum = atPed ? tuning.reloadMomentum : 1.0f;
	const float jitterRight = casingRandom(-tuning.velocityJitter, tuning.velocityJitter);
	const float jitterForward = casingRandom(-tuning.velocityJitter, tuning.velocityJitter);
	const float jitterUp = casingRandom(-tuning.velocityJitter * 0.5f, tuning.velocityJitter);
	const Vector3 inherited = ENTITY_VELOCITY(ped);
	const Vector3 velocity = {
		inherited.x * tuning.inheritedVelocity + momentum *
			(right.x * (tuning.ejectRight + jitterRight) +
			 forward.x * (tuning.ejectForward + jitterForward) +
			 up.x * (tuning.ejectUp + jitterUp)),
		inherited.y * tuning.inheritedVelocity + momentum *
			(right.y * (tuning.ejectRight + jitterRight) +
			 forward.y * (tuning.ejectForward + jitterForward) +
			 up.y * (tuning.ejectUp + jitterUp)),
		inherited.z * tuning.inheritedVelocity + momentum *
			(right.z * (tuning.ejectRight + jitterRight) +
			 forward.z * (tuning.ejectForward + jitterForward) +
			 up.z * (tuning.ejectUp + jitterUp))
	};
	const Vector3 rotation = {
		casingRandom(-180.0f, 180.0f), casingRandom(-180.0f, 180.0f),
		casingRandom(-180.0f, 180.0f)
	};
	if (obj) {
		applyCasingEjection(obj, rotation, velocity);
	} else {
		// Park the impulse; the update loop applies it the frame the pickup's
		// object appears, so the casing still ejects instead of materialising
		// motionless where it was placed.
		PendingCasingImpulse queued;
		queued.pickup = pickup;
		queued.rotation = rotation;
		queued.velocity = velocity;
		g_casingPendingImpulses.push_back(queued);
	}
	SpentCasing casing;
	casing.pickup = pickup;
	casing.object = obj;
	casing.item = item;
	casing.model = model;
	casing.createdAt = now;
	casing.lastPosition = spawn;
	// A revolver reload creates all retained casings in one update. Give every
	// casing its own phase immediately so their glints never inherit that spawn
	// lockstep unless the user explicitly sets timing randomness to zero.
	casing.nextGlintAt = now + (DWORD)casingRandom(0.0f,
		(float)g_casingGlintTimingRandomnessMs);
	casing.isPickup = asPickup;
	// NOTE: carriable mode (TASK_CARRIABLE) was removed - that native tasks
	// the PLAYER into a carry state (it is how Arthur shoulders a deer), which
	// broke crouching and left a "Take" prompt that granted nothing. Making a
	// script-spawned object a genuine carriable-inventory prop has no clean
	// native path found; the working modes are the engine pickup (native) and
	// our own loot-key prompt (legacy).
	g_spentCasings.push_back(casing);
	log << "spawned casing object=" << obj
		<< (objectPending ? " (pickup object pending)" : "")
		<< " pickup=" << pickup
		<< " item=0x" << std::hex << item << std::dec
		<< (atPed ? " (reload dump)" : "")
		<< " spawn=" << spawn.x << "," << spawn.y << "," << spawn.z
		<< " velocity=" << velocity.x << "," << velocity.y << "," << velocity.z
		<< " basis=" << (fromWeapon ? "weapon" : "ped")
		<< " world=" << g_spentCasings.size() << "\n";
}

static void ensureCasingPrompt() {
	if (g_casingPromptRegistered) return;
	g_casingPrompt = CASING_PROMPT_BEGIN();
	CASING_PROMPT_CONTROL(g_casingPrompt, joaat("INPUT_LOOT"));
	CASING_PROMPT_TEXT(g_casingPrompt, CASING_LITERAL("Collect Casing"));
	CASING_PROMPT_HOLD(g_casingPrompt, joaat("SHORT_TIMED_EVENT"));
	CASING_PROMPT_END(g_casingPrompt);
	CASING_PROMPT_VISIBLE(g_casingPrompt, FALSE);
	CASING_PROMPT_ENABLED(g_casingPrompt, FALSE);
	g_casingPromptRegistered = true;
	GtLogStream log("casings", GT_INFO);
	log << "loot prompt registered handle=" << g_casingPrompt << "\n";
}

// #85 true while any of the loot inputs is physically down, disabled or not.
static bool casingLootKeyHeld() {
	static const Hash kLoot[3] = { joaat("INPUT_LOOT"), joaat("INPUT_LOOT2"), joaat("INPUT_LOOT3") };
	for (Hash h : kLoot) {
		if (PAD::IS_CONTROL_PRESSED(0, h) || PAD::IS_DISABLED_CONTROL_PRESSED(0, h) ||
			PAD::IS_CONTROL_PRESSED(2, h) || PAD::IS_DISABLED_CONTROL_PRESSED(2, h)) return true;
	}
	return false;
}

// #85 hold the loot inputs shut for the rest of the press that collected a
// casing. Called every frame while the block is up; releasing the key ends it.
static void updateCasingLootBlock() {
	if (!g_casingLootBlocked) return;
	if (!casingLootKeyHeld()) { g_casingLootBlocked = false; return; }
	PAD::DISABLE_CONTROL_ACTION(0, joaat("INPUT_LOOT"), TRUE);
	PAD::DISABLE_CONTROL_ACTION(0, joaat("INPUT_LOOT2"), TRUE);
	PAD::DISABLE_CONTROL_ACTION(0, joaat("INPUT_LOOT3"), TRUE);
}

static void updateSpentCasings(Ped ped, DWORD now) {
	static Hash lastWeapon = 0;
	static int lastAmmo = -1, lastClip = -1;
	static bool wasReloading = false;
	if (!g_spentCasingsEnabled) {
		for (SpentCasing& casing : g_spentCasings) deleteCasing(casing);
		g_spentCasings.clear(); g_pendingEjects.clear();
		g_casingPendingImpulses.clear();
		g_revolverOwed = 0; lastWeapon = 0; lastAmmo = -1; lastClip = -1;
		if (g_casingPromptRegistered) { CASING_PROMPT_VISIBLE(g_casingPrompt, FALSE); CASING_PROMPT_ENABLED(g_casingPrompt, FALSE); }
		g_casingLootBlocked = false;
		return;
	}

	updateCasingLootBlock();
	requestCasingModels();
	// #130 Idle heartbeat. The casings log is truncated once per launch
	// (script.cpp:1770), so before this a log holding only the two startup lines
	// was ambiguous: it could mean "the module is dead" or "nothing was shot".
	// A 10 s heartbeat makes a silent log prove the first, and makes the pickup
	// state observable without needing to fire a round.
	{
		static DWORD lastCasingHeartbeat = 0;
		if (!lastCasingHeartbeat || now - lastCasingHeartbeat >= 10000u) {
			lastCasingHeartbeat = now;
			size_t asPickups = 0, awaitingObject = 0;
			for (const SpentCasing& c : g_spentCasings) {
				if (!c.isPickup) continue;
				++asPickups;
				if (!c.object) ++awaitingObject;
			}
			GtLogStream log("casings", GT_INFO);
			if (log) log << "heartbeat mode=" << g_casingMode
				<< " world=" << g_spentCasings.size()
				<< " pickups=" << asPickups
				<< " awaitingObject=" << awaitingObject
				<< " queuedImpulses=" << g_casingPendingImpulses.size() << "\n";
		}
	}
	// Feed cards snapshot their icon when posted, so both dictionaries must be
	// resident before a casing can be collected.
	if (!invoke<BOOL>(0x54D6900929CCF162, "INVENTORY_ITEMS")) // HAS_STREAMED_TEXTURE_DICT_LOADED
		invoke<Void>(0xC1BA29DF5631B0F8, "INVENTORY_ITEMS", FALSE); // REQUEST_STREAMED_TEXTURE_DICT
	if (!invoke<BOOL>(0x54D6900929CCF162, "GENERIC_TEXTURES"))
		invoke<Void>(0xC1BA29DF5631B0F8, "GENERIC_TEXTURES", FALSE);
	static bool casingInventoryProbed = false;
	if (!casingInventoryProbed) {
		casingInventoryProbed = true;
		const bool exists =
			invoke<BOOL>(0x7332461FC59EB7EC, "GENERIC_TEXTURES") != 0;
		const bool loaded =
			invoke<BOOL>(0x54D6900929CCF162, "GENERIC_TEXTURES") != 0;
		GtLogStream log("casings", GT_INFO);
		if (log) log << "texture dictionary GENERIC_TEXTURES exists="
			<< (exists ? 1 : 0) << " loaded_before_request="
			<< (loaded ? 1 : 0) << "\n";
	}
	if (g_casingMode == 2) ensureCasingPrompt();

	// ---- fire detection (ammo counters) ----
	Hash weapon = GET_CURRENT_WEAPON(ped);
	int ammo = weapon ? WEAPON::GET_AMMO_IN_PED_WEAPON(ped, weapon) : -1;
	int clip = weapon ? GET_CLIP_AMMO(ped, weapon) : -1;
	// instrumentation for the "repeaters produce nothing" report: log the
	// first frames of shooting so we can see whether the ammo counters move
	static bool wasShooting = false;
	static DWORD lastShootingAt = 0;
	bool shooting = PED::IS_PED_SHOOTING(ped) != 0;
	if (shooting) lastShootingAt = now;
	if (shooting && !wasShooting) {
		GtLogStream log("casings", GT_INFO);
		log << "shooting weapon=0x" << std::hex << weapon
			<< " group=0x" << WEAPON::GET_WEAPONTYPE_GROUP(weapon) << std::dec
			<< " clip=" << clip << " ammo=" << ammo << "\n";
	}
	wasShooting = shooting;
	if (weapon != lastWeapon) {
		// weapon switched: a spent case stays chambered; its PendingEject
		// survives and resolves when this weapon is drawn and cycled again
		lastWeapon = weapon; lastAmmo = ammo; lastClip = clip;
	} else {
		int clipSpent = clip >= 0 && lastClip >= 0 ? (std::max)(0, lastClip - clip) : 0;
		int ammoSpent = ammo >= 0 && lastAmmo >= 0 ? (std::max)(0, lastAmmo - ammo) : 0;
		int fired = (std::max)(clipSpent, ammoSpent);
		// Ammo-type switches unload the clip (clip drops without a shot),
		// which counted as "fired" and dumped a full cylinder of phantom
		// brass. Only count expenditure within 400 ms of actual shooting.
		if (fired > 0 && (!lastShootingAt || now - lastShootingAt > 400)) {
			GtLogStream log("casings", GT_INFO);
			log << "ammo shuffle ignored (delta=" << fired << ", no recent shot)\n";
			fired = 0;
		}
		if (fired > 0) {
			fired = (std::min)(fired, 12);
			Hash item = casingItemForWeapon(weapon);
			GtLogStream log("casings", GT_INFO);
			if (!item) {
				GtLogStream("casings", GT_WARN)
					<< "unsupported weapon=0x" << std::hex << weapon << std::dec << "\n";
			} else if (casingWeaponIsRevolver(weapon) || casingWeaponIsBreakAction(weapon)) {
				// Revolvers retain brass in the cylinder; break-action shotguns
				// retain hulls in their chambers. Both eject only when opened
				// for reload, never immediately after firing.
				g_revolverOwed = (std::min)(g_revolverOwed + fired, 12);
				g_revolverOwedItem = item;
				log << "retained weapon owes " << g_revolverOwed << " casing(s) until reload\n";
			} else if (casingWeaponIsPistol(weapon)) {
				for (int i = 0; i < fired; ++i) {
					PendingEject pe; pe.weapon = weapon; pe.item = item;
					pe.firedAt = now; pe.spawnAt = now + 60 + i * 30;
					g_pendingEjects.push_back(pe);
				}
				log << "pistol eject queued count=" << fired << "\n";
			} else {
				// lever/bolt/pump: the casing leaves the gun when it is cycled,
				// i.e. when the weapon becomes ready to shoot again
				for (int i = 0; i < fired; ++i) {
					PendingEject pe; pe.weapon = weapon; pe.item = item;
					pe.firedAt = now; pe.waitForCycle = true;
					g_pendingEjects.push_back(pe);
				}
				log << "cycle eject pending count=" << fired << "\n";
			}
		}
	}
	if (ammo >= 0) lastAmmo = ammo;
	if (clip >= 0) lastClip = clip;

	// ---- revolver reload dump ----
	bool reloading = PED::IS_PED_RELOADING(ped) != 0;
	if (reloading && !wasReloading && g_revolverOwed > 0 && weapon &&
		(casingWeaponIsRevolver(weapon) || casingWeaponIsBreakAction(weapon))) {
		GtLogStream log("casings", GT_INFO);
		log << "reload started: ejecting " << g_revolverOwed << " retained casing(s)\n";
		for (int i = 0; i < g_revolverOwed; ++i)
			spawnCasingObject(ped, g_revolverOwedItem, now, i, true);
		g_revolverOwed = 0;
	}
	wasReloading = reloading;

	// ---- cycle detection: the action-cycle ANIMATION itself ----
	// The lever/bolt/pump throw is a discrete clip pair (cock_start/cock_end)
	// in the mech_weapons_* fire dicts — one dict per stance, including a
	// dedicated hip-fire dict, so no aim-state guessing is needed at all.
	// Dict/clip names verified against femga/rdr3_discoveries ingameanims.
	// ---- cycle detection: IS_PED_WEAPON_READY_TO_SHOOT edge ----
	// Anim polling is dead: a full probe (all dicts x anim types 0-3 x
	// ped+weapon entity) never registered a single motion-tree clip. The
	// ready-flag returns as primary detector - its earlier phantom flips
	// happened on the corrupted-flags weapons baseline (missing
	// OnlyFireOneShotPerTriggerPress etc.); every flip is logged so the
	// fixed baseline's real semantics become evidence.
	static bool wasReady = true;
	bool hasCyclePending = false;
	for (const PendingEject& pe : g_pendingEjects)
		if (pe.waitForCycle && pe.weapon == weapon) { hasCyclePending = true; break; }
	bool ready = weapon ? WEAPON::IS_PED_WEAPON_READY_TO_SHOOT(ped) != 0 : true;
	// The flip alone still fires on stance exits. Gate: the flip only counts
	// as a cycle while the ped is actually in a shooting posture — free-aim,
	// lock-on, or an active ranged-attack task (covers hip-fire). A rejected
	// flip leaves the pending chambered; the catch-up lever anim on the next
	// raise produces an accepted flip and ejects it then, like the real gun.
	bool freeAim = PLAYER::IS_PLAYER_FREE_AIMING(PLAYER::PLAYER_ID()) != 0;
	bool targeting = invoke<BOOL>(0x4605C66E0F935F83, PLAYER::PLAYER_ID()) != 0; // IS_PLAYER_TARGETTING_ANYTHING
	bool attackTask = invoke<BOOL>(0x5EA655F01D93667A, ped) != 0; // _GET_TASK_COMBAT_READY_TO_SHOOT
	bool inShootingPosture = freeAim || targeting || attackTask;
	// THE POSTURE GATE WAS TESTED AT THE WRONG MOMENT, AND IT BROKE LONG-GUN
	// CASINGS ENTIRELY. A lever/bolt/pump cycle finishes AFTER the trigger is
	// released, so by the rising 0->1 flip the combat task has already ended and
	// free-aim/lock-on are false. The live log shows exactly that: every rising
	// flip logged `freeAim=0 targeting=0 attackTask=0 accepted=0`, followed by
	// "NO CYCLE detected in 20s ... dropping pending". Revolvers still worked
	// because they use the reload path, not this one.
	// A pending eject only exists because a shot was already fired, so the shot
	// is the proof of intent. Bound it by TIME since that shot instead of by a
	// posture that cannot survive the cycle.
	if (ready != wasReady && hasCyclePending) {
		GtLogStream log("casings", GT_INFO);
		log << "ready-flip " << (wasReady ? 1 : 0) << "->" << (ready ? 1 : 0)
			<< " freeAim=" << freeAim << " targeting=" << targeting
			<< " attackTask=" << attackTask
			<< " posture=" << (inShootingPosture ? 1 : 0)
			<< " accepted=" << (ready && !wasReady ? 1 : 0) << "\n";
	}
	if (ready && !wasReady) {
		for (int i = (int)g_pendingEjects.size() - 1; i >= 0; --i) {
			PendingEject& pe = g_pendingEjects[i];
			if (!pe.waitForCycle || pe.weapon != weapon) continue;
			if (now - pe.firedAt > (DWORD)g_casingCycleWindowMs) continue;
			spawnCasingObject(ped, pe.item, now, 0, false);
			g_pendingEjects.erase(g_pendingEjects.begin() + i);
			break; // one casing per cycle
		}
	}
	wasReady = ready;

	// ---- timed ejects + stale cleanup ----
	for (int i = (int)g_pendingEjects.size() - 1; i >= 0; --i) {
		PendingEject& pe = g_pendingEjects[i];
		if (!pe.waitForCycle && now >= pe.spawnAt) {
			spawnCasingObject(ped, pe.item, now, 0, false);
			g_pendingEjects.erase(g_pendingEjects.begin() + i);
		} else if (pe.waitForCycle && pe.weapon == weapon && now - pe.firedAt > 20000) {
			GtLogStream log("casings", GT_WARN);
			log << "NO CYCLE detected in 20s for weapon=0x" << std::hex << pe.weapon << std::dec
				<< "; dropping pending\n";
			g_pendingEjects.erase(g_pendingEjects.begin() + i);
		}
	}

	// ---- world upkeep + collection prompt ----
	Vector3 playerPosition = ENTITY::GET_ENTITY_COORDS(ped, TRUE, FALSE);
	Vector3 camCoord = invoke<Vector3>(0x595320200B98596E);       // GET_GAMEPLAY_CAM_COORD
	Vector3 camRot = invoke<Vector3>(0x0252D2B5582957A6, 2);      // GET_GAMEPLAY_CAM_ROT
	float camPitch = camRot.x * 0.0174532925f, camYaw = camRot.z * 0.0174532925f;
	Vector3 camForward = { -sinf(camYaw) * cosf(camPitch), cosf(camYaw) * cosf(camPitch), sinf(camPitch) };
	float lookCos = cosf(g_casingLookAngleDeg * 0.0174532925f);
	int nearest = -1;
	float nearestDistSq = g_casingPickupRange * g_casingPickupRange;
	bool collectionInProgress = false;
	for (int i = (int)g_spentCasings.size() - 1; i >= 0; --i) {
		SpentCasing& casing = g_spentCasings[i];
		if (casing.collecting) {
			collectionInProgress = true;
			if (now >= casing.collectAt) {
				bool granted = INVENTORY_ADD(casing.item, 1);
				CASING_FEED(CASING_LITERAL(casingDisplayName(casing.item).c_str()),
					casingIconDict(casing.item), joaat(casingIconName(casing.item)));
				if (!g_casingSoundName.empty())
					CASING_SOUND(g_casingSoundName.c_str(), g_casingSoundSet.c_str());
				GtLogStream log("casings", GT_INFO);
				log << "casing animation pickup completed item=0x" << std::hex << casing.item
					<< std::dec << " granted=" << (granted ? 1 : 0) << "\n";
				deleteCasing(casing);
				g_spentCasings.erase(g_spentCasings.begin() + i);
			}
			continue;
		}
		if (casing.pickup && OBJECT::HAS_PICKUP_BEEN_COLLECTED(casing.pickup)) {
			// Native pickup rewards add the satchel item, but their custom reward
			// metadata does not produce Rockstar's acquisition card.  Mode 2 already
			// posts this card after INVENTORY_ADD; do the same exactly once before
			// the collected native pickup is erased.
			const char* iconDict = casingIconDict(casing.item);
			const char* iconName = casingIconName(casing.item);
			CASING_FEED(CASING_LITERAL(casingDisplayName(casing.item).c_str()),
				iconDict, joaat(iconName));
			GtLogStream log("casings", GT_INFO);
			log << "casing collected by native pickup item=0x" << std::hex << casing.item
				<< std::dec << " feed_dict=" << iconDict << " feed_icon=" << iconName << "\n";
			if (casing.fxHandle) GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
			g_spentCasings.erase(g_spentCasings.begin() + i);
			continue;
		}
		// #130 A placed pickup whose physical object has not been built yet is the
		// normal state for the first frames of its life, not a failure. Adopt the
		// object on the frame it appears and release the withheld ejection impulse
		// then. Only a placement that never produces an object within the wait is
		// reclaimed. Without this, the check below would erase a live pickup (and
		// leak it, since that branch never calls REMOVE_PICKUP).
		if (casing.isPickup && casing.pickup &&
			(!casing.object || !ENTITY::DOES_ENTITY_EXIST(casing.object))) {
			if (!OBJECT::DOES_PICKUP_EXIST(casing.pickup)) {
				GtLogStream log("casings", GT_WARN);
				log << "pickup vanished before its object appeared item=0x"
					<< std::hex << casing.item << std::dec << "\n";
				forgetPendingCasingImpulse(casing.pickup);
				if (casing.fxHandle) GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
				g_spentCasings.erase(g_spentCasings.begin() + i);
				continue;
			}
			Object late = OBJECT::GET_PICKUP_OBJECT(casing.pickup);
			if (late && ENTITY::DOES_ENTITY_EXIST(late)) {
				casing.object = late;
				const bool impulsed = applyPendingCasingImpulse(casing.pickup, late);
				GtLogStream log("casings", GT_INFO);
				log << "pickup object adopted after " << (now - casing.createdAt)
					<< " ms item=0x" << std::hex << casing.item << std::dec
					<< " object=" << late << " impulse=" << (impulsed ? 1 : 0) << "\n";
			} else {
				if (now - casing.createdAt > kCasingPickupObjectWaitMs) {
					GtLogStream log("casings", GT_WARN);
					log << "pickup object never appeared within " << kCasingPickupObjectWaitMs
						<< " ms item=0x" << std::hex << casing.item << std::dec
						<< " pickup=" << casing.pickup << " - reclaiming placement\n";
					forgetPendingCasingImpulse(casing.pickup);
					OBJECT::REMOVE_PICKUP(casing.pickup);
					if (casing.fxHandle) GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
					g_spentCasings.erase(g_spentCasings.begin() + i);
				}
				continue; // still streaming in; nothing below can run without an object
			}
		}
		if (!casing.object || !ENTITY::DOES_ENTITY_EXIST(casing.object)) {
			GtLogStream log("casings", GT_WARN);
			log << "casing object vanished without pickup collection item=0x"
				<< std::hex << casing.item << std::dec << "\n";
			if (casing.fxHandle) GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
			g_spentCasings.erase(g_spentCasings.begin() + i);
			continue;
		}
		if (now - casing.createdAt > (DWORD)g_spentCasingLifetimeSeconds * 1000u) {
			deleteCasing(casing);
			g_spentCasings.erase(g_spentCasings.begin() + i);
			continue;
		}
		// #32: `scr_event_glint` is a real looped effect, so every requested
		// dimension is under script control. Each casing owns an independent
		// pulse schedule; reload-dumped chambers no longer flash in lockstep.
		if (!g_casingGlintEnabled) {
			if (casing.fxHandle)
				GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
			casing.fxHandle = 0;
			casing.glintStartedAt = 0;
			// Seed a stagger while disabled too, so re-enabling the effect does not
			// make every existing casing flash together on the same frame.
			if (!casing.nextGlintAt)
				casing.nextGlintAt = now + (DWORD)casingRandom(0.0f,
					(float)g_casingGlintTimingRandomnessMs);
		} else if (g_casingGlintEnabled && casing.fxHandle) {
			const DWORD elapsed = now - casing.glintStartedAt;
			if (elapsed >= (DWORD)g_casingGlintDurationMs) {
				GRAPHICS::STOP_PARTICLE_FX_LOOPED(casing.fxHandle, FALSE);
				casing.fxHandle = 0;
				casing.glintStartedAt = 0;
				const int randomOffset = (int)casingRandom(
					(float)-g_casingGlintTimingRandomnessMs,
					(float)g_casingGlintTimingRandomnessMs);
				const int delay = (std::max)(0, g_casingGlintPauseMs + randomOffset);
				casing.nextGlintAt = now + (DWORD)delay;
			} else {
				float envelope = 1.0f;
				if (g_casingGlintFadeInMs > 0)
					envelope = (std::min)(envelope,
						(float)elapsed / (float)g_casingGlintFadeInMs);
				if (g_casingGlintFadeOutMs > 0) {
					const DWORD remaining = (DWORD)g_casingGlintDurationMs - elapsed;
					envelope = (std::min)(envelope,
						(float)remaining / (float)g_casingGlintFadeOutMs);
				}
				envelope = (std::max)(0.0f, (std::min)(1.0f, envelope));
				GRAPHICS::SET_PARTICLE_FX_LOOPED_SCALE(casing.fxHandle,
					g_casingGlintSize);
				GRAPHICS::SET_PARTICLE_FX_LOOPED_COLOUR(casing.fxHandle,
					g_casingGlintBrightness, g_casingGlintBrightness,
					g_casingGlintBrightness, FALSE);
				GRAPHICS::SET_PARTICLE_FX_LOOPED_ALPHA(casing.fxHandle,
					g_casingGlintAlpha * envelope);
			}
		} else if (g_casingGlintEnabled && now >= casing.nextGlintAt) {
			STREAMING::REQUEST_NAMED_PTFX_ASSET(joaat("scr_generic"));
			if (invoke<BOOL>(0x65BB72F29138F5D6, joaat("scr_generic"))) { // HAS_NAMED_PTFX_ASSET_LOADED
				GRAPHICS::USE_PARTICLE_FX_ASSET("scr_generic");
				casing.fxHandle = GRAPHICS::START_PARTICLE_FX_LOOPED_ON_ENTITY(
					"scr_event_glint", casing.object, 0.0f, 0.0f, 0.02f,
					0.0f, 0.0f, 0.0f, g_casingGlintSize, FALSE, FALSE, FALSE);
				if (casing.fxHandle) {
					casing.glintStartedAt = now;
					GRAPHICS::SET_PARTICLE_FX_LOOPED_COLOUR(casing.fxHandle,
						g_casingGlintBrightness, g_casingGlintBrightness,
						g_casingGlintBrightness, FALSE);
					GRAPHICS::SET_PARTICLE_FX_LOOPED_ALPHA(casing.fxHandle, 0.0f);
				}
			}
		}
		casing.lastPosition = ENTITY::GET_ENTITY_COORDS(casing.object, TRUE, FALSE);
		// FX anchor = the model's bounding-box center in world space; the
		// entity origin sits at one end of the casing, not its middle
		Vector3 bbMin = {}, bbMax = {}, cRight = {}, cFwd = {}, cUp = {}, cPos = {};
		MISC::GET_MODEL_DIMENSIONS(casing.model, &bbMin, &bbMax);
		ENTITY::GET_ENTITY_MATRIX(casing.object, &cRight, &cFwd, &cUp, &cPos);
		float ox = (bbMin.x + bbMax.x) * 0.5f, oy = (bbMin.y + bbMax.y) * 0.5f, oz = (bbMin.z + bbMax.z) * 0.5f;
		Vector3 fxPos = {
			cPos.x + cRight.x * ox + cFwd.x * oy + cUp.x * oz,
			cPos.y + cRight.y * ox + cFwd.y * oy + cUp.y * oz,
			cPos.z + cRight.z * ox + cFwd.z * oy + cUp.z * oz
		};
		if (g_casingGlowIntensity > 0.0f) {
			float t = g_casingGlowYellowness;
			int glowR = 255, glowG = (int)(255.0f - 50.0f * t), glowB = (int)(255.0f - 195.0f * t);
			GRAPHICS::DRAW_LIGHT_WITH_RANGE(fxPos.x, fxPos.y, fxPos.z + 0.20f,
				glowR, glowG, glowB, g_casingGlowRange, g_casingGlowIntensity);
		}
		if (g_spentCasingDebugMarker) {
			GRAPHICS::_DRAW_MARKER(0x94FDAE17, fxPos.x, fxPos.y, fxPos.z,
				0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.08f, 0.08f, 0.08f,
				255, 185, 35, 220, FALSE, FALSE, 2, FALSE, nullptr, nullptr, FALSE);
		}
		float dx = casing.lastPosition.x - playerPosition.x;
		float dy = casing.lastPosition.y - playerPosition.y;
		float dz = casing.lastPosition.z - playerPosition.z;
		float distSq = dx * dx + dy * dy + dz * dz;
		// the custom prompt only serves legacy mode; pickup and carriable
		// modes have engine-owned prompts
		if (!casing.isPickup && distSq < nearestDistSq && dz > -2.0f && dz < 2.0f) {
			// prompt only when the camera points at the casing — Lexer's
			// tuned angle/distance rules apply at every range; the widened
			// look-down clamp is what makes near casings targetable
			float cx = casing.lastPosition.x - camCoord.x;
			float cy = casing.lastPosition.y - camCoord.y;
			float cz = casing.lastPosition.z - camCoord.z;
			float clen = sqrtf(cx * cx + cy * cy + cz * cz);
			if (clen > 0.01f) {
				float dot = (cx * camForward.x + cy * camForward.y + cz * camForward.z) / clen;
				if (dot >= lookCos) { nearestDistSq = distSq; nearest = i; }
			}
		}
	}

	bool showPrompt = nearest >= 0 && !collectionInProgress;
	if (showPrompt) {
		STREAMING::REQUEST_ANIM_DICT(kCasingAnimDict);
		static bool animDiagLogged = false;
		if (!animDiagLogged) {
			animDiagLogged = true;
			GtLogStream log("casings", GT_INFO);
			log << "animDict '" << kCasingAnimDict << "' exists="
				<< (STREAMING::DOES_ANIM_DICT_EXIST(kCasingAnimDict) ? 1 : 0) << "\n";
		}
	}
	static Hash lastPromptItem = 0;
	if (showPrompt && g_spentCasings[nearest].item != lastPromptItem) {
		lastPromptItem = g_spentCasings[nearest].item;
		std::string label = std::string("Pick Up ") + casingDisplayName(lastPromptItem);
		CASING_PROMPT_TEXT(g_casingPrompt, CASING_LITERAL(label.c_str()));
	}
	CASING_PROMPT_VISIBLE(g_casingPrompt, showPrompt ? TRUE : FALSE);
	CASING_PROMPT_ENABLED(g_casingPrompt, showPrompt ? TRUE : FALSE);
	if (showPrompt && CASING_PROMPT_DONE(g_casingPrompt)) {
		SpentCasing& casing = g_spentCasings[nearest];
		// #85 the press that collected this casing must not reach vanilla's
		// hold-E rest; swallow it for as long as the key stays down
		g_casingLootBlocked = true;
		updateCasingLootBlock();
		bool animDictLoaded = STREAMING::HAS_ANIM_DICT_LOADED(kCasingAnimDict) != 0;
		// #85(b) THE RIFLE CLIPPING THROUGH THE GROUND, AND WHY.
		// Lexer asked how the vanilla game does its pickups. It does NOT do this.
		// Rockstar never plays a raw pickup clip; every vanilla pickup goes through
		// the item-interaction system, which owns a rifle-aware variant of each
		// animation - the game data carries a whole family of *_LEFT_HAND_RIFLE
		// states, and the mask code in this file already uses two of them. What we
		// do here instead is play one authored right-hand ground reach across the
		// whole skeleton with no idea what is in his hands, so a longarm is dragged
		// through the floor along with it.
		// FIXED PROPERLY: two interaction states are now authored in
		// iteminteractioninfo.meta - LEX_CASING_PICKUP_UNARMED and _RIFLE - cloned
		// from Rockstar's own USE_HANDFULL_SATCHEL pair, whose FALLBACKS@HANDFULL
		// clip sets are the generic "a handful of something goes into the satchel"
		// animation, with the shell prop swapped in. The rifle variant is left-handed
		// and authored against a held longarm, so nothing is dragged through the
		// floor. The raw clip is kept only as a fallback if the interaction refuses.
		const Hash heldNow = GET_CURRENT_WEAPON(ped);
		const bool holdingLongarm = heldNow &&
			(heldNow == GET_WEAPON_AT_ATTACH_POINT(ped, 9) ||
			 heldNow == GET_WEAPON_AT_ATTACH_POINT(ped, 10));
		// #85(b) MY REGRESSION: HE ATE IT. The states I cloned came from
		// Rockstar's CONSUMABLE family - generic_single_use_item, the
		// FALLBACKS@HANDFULL clip sets - which is the "raise a handful to your
		// mouth" animation. Correct hand, correct rifle awareness, completely
		// wrong action: he ate the casing. Every state in that file is
		// InteractionType Consumable or Outfit; there is no pickup family to
		// clone, which is the thing I should have checked before shipping it.
		// Back to the ground reach, which looked right, and still no reach at all
		// while holding a longarm so nothing clips through the floor.
		const bool interactionTook = false;
		if (animDictLoaded && !holdingLongarm) {
			// Fallback only. Never for a longarm - that is the clipping case.
			TASK::TASK_PLAY_ANIM(ped, kCasingAnimDict, kCasingAnimClip,
				8.0f, -4.0f, 1050, 0, 0.0f, FALSE, 0, FALSE, "", FALSE);
			casing.collecting = true;
			casing.collectAt = now + 650;
		} else {
			casing.collecting = true;
			casing.collectAt = now + 120;
		}
		GtLogStream log("casings", GT_INFO);
		log << "casing pickup requested item=0x" << std::hex << casing.item << std::dec
			<< " animDictLoaded=" << (animDictLoaded ? 1 : 0) << "\n";
		CASING_PROMPT_VISIBLE(g_casingPrompt, FALSE);
		CASING_PROMPT_ENABLED(g_casingPrompt, FALSE);
		CASING_PROMPT_RESTART(g_casingPrompt);
	}
}


// ---------------------------------------------------------------------------
// BottleProbe — read-only investigation for the collectible-empty-bottle idea.
//
// Two questions decide whether we cut the drink anim short (no throw, stow the
// bottle) or let it throw and spawn a pickup:
//   1. Is the bottle-throw a SEPARATE clip in the drinking dictionary? RDR2 has
//      no native to enumerate a dict, so we test candidate clip names against
//      IS_ENTITY_PLAYING_ANIM and log whichever answers.
//   2. What object is in Arthur's hands while drinking, and what becomes of it?
//      Logged per-phase so we can see when it spawns and when it goes away.
//
// Changes nothing. Writes GameplayTweaks.bottle.log. Off unless
// [BottleProbe] Enabled=1.
// ---------------------------------------------------------------------------
static const char* kDrinkDicts[] = {
	"MECH_INVENTORY@DRINKING@BOTTLE_CYLINDER_D1",
	"MECH_INVENTORY@DRINKING@BOTTLE_OVAL_L5",
	"MECH_INVENTORY@DRINKING@BOTTLE_OVAL_L6",
	"MECH_INVENTORY@DRINKING@BOTTLE_RECTANGLE_L4",
};
// RDR2 clip naming is conventional enough that a candidate list is cheap to try.
static const char* kDrinkClips[] = {
	"base", "enter", "exit", "intro", "outro", "loop", "idle",
	"drink", "drink_a", "drink_base", "throw", "throw_bottle", "discard",
	"toss", "finish", "end", "action", "quick",
};

// RDR2 hashes from the SDK header, NOT the GTA5 ones - those silently no-op here.
static bool ANIM_PLAYING(Ped p, const char* dict, const char* clip) {
	return ENTITY::IS_ENTITY_PLAYING_ANIM(p, dict, clip, 3) != 0;
}
static float ANIM_TIME(Ped p, const char* dict, const char* clip) {
	return ENTITY::_GET_ENTITY_ANIM_CURRENT_TIME(p, dict, clip);
}

static void bottleProbeLog(const std::string& line) {
	GtLogStream log("bottle", GT_INFO);
	log << line << "\n";
}

static void updateBottleProbe(Ped ped) {
	if (!g_bottleProbeEnabled || !ped) return;
	static bool wasDrinking = false;
	static std::string lastSeen;
	// Heartbeat: without it, "no matching clip" and "probe never ran" produce the same
	// empty file, which already wasted one play session.
	static DWORD lastBeat = 0;
	DWORD nowMs = GetTickCount();
	if (nowMs - lastBeat > 10000) {
		lastBeat = nowMs;
		bottleProbeLog("[alive] probe polling, no drink clip matched yet");
	}

	for (const char* dict : kDrinkDicts) {
		if (!STREAMING::HAS_ANIM_DICT_LOADED(dict)) STREAMING::REQUEST_ANIM_DICT(dict);
		for (const char* clip : kDrinkClips) {
			if (!ANIM_PLAYING(ped, dict, clip)) continue;
			char buf[256];
			sprintf_s(buf, "PLAYING dict=%s clip=%s t=%.3f", dict, clip, ANIM_TIME(ped, dict, clip));
			if (lastSeen != buf) { lastSeen = buf; bottleProbeLog(buf); }
			if (!wasDrinking) {
				wasDrinking = true;
				bottleProbeLog("--- drink started ---");
			}
			// what is in his hands right now
			Vector3 pos = ENTITY::GET_ENTITY_COORDS(ped, TRUE, FALSE);
			for (Hash m : { joaat("P_BOTTLEJD_USED01X"), joaat("S_BRANDY_USED01X"),
			                joaat("S_INV_GIN_USED01X"), joaat("S_INV_USEDRUM01X"),
			                joaat("S_INV_WHISKEY01X"), joaat("S_BRANDY01X"),
			                joaat("S_INV_GIN01X"), joaat("S_INV_RUM01X") }) {
				Object o = invoke<Object>(0xE143FA2249364369, pos.x, pos.y, pos.z, 3.0f, m, FALSE, FALSE, FALSE);
				if (o) {
					char ob[192];
					sprintf_s(ob, "  prop model=0x%08X obj=%d attached=%d",
						m, o, ENTITY::IS_ENTITY_ATTACHED(o) ? 1 : 0);
					bottleProbeLog(ob);
				}
			}
			return;
		}
	}
	if (wasDrinking) { wasDrinking = false; lastSeen.clear(); bottleProbeLog("--- drink ended ---\n"); }
}

// #103. generic_alcohol_item sets its authored swig count to one for inventory
// alcohol. Full and _USED records are separate one-swig consumables; drinking a
// full Kentucky Bourbon does not first convert it to CONSUMABLE_WHISKEY_USED.
static void updateEmptyBottles(Ped ped, DWORD now) {
	struct BottleSource {
		const char* fullName;
		const char* usedName;
		Hash full;
		Hash used;
		bool tonic;
	};
	static BottleSource sources[] = {
		{ "CONSUMABLE_WHISKEY", "CONSUMABLE_WHISKEY_USED", 0, 0, false },
		{ "CONSUMABLE_BRANDY", "CONSUMABLE_BRANDY_USED", 0, 0, false },
		{ "CONSUMABLE_GIN", "CONSUMABLE_GIN_USED", 0, 0, false },
		{ "CONSUMABLE_RUM", "CONSUMABLE_RUM_USED", 0, 0, false },
		{ "CONSUMABLE_MEDICINE", "CONSUMABLE_MEDICINE_USED", 0, 0, true },
		{ "CONSUMABLE_POTENT_MEDICINE", nullptr, 0, 0, true },
		{ "CONSUMABLE_SPECIAL_MEDICINE_CRAFTED", nullptr, 0, 0, true },
		{ "CONSUMABLE_RESTORATIVE", "CONSUMABLE_RESTORATIVE_USED", 0, 0, true },
		{ "CONSUMABLE_POTENT_RESTORATIVE", nullptr, 0, 0, true },
		{ "CONSUMABLE_SPECIAL_RESTORATIVE_CRAFTED", nullptr, 0, 0, true },
		{ "CONSUMABLE_SNAKE_OIL", "CONSUMABLE_SNAKE_OIL_USED", 0, 0, true },
		{ "CONSUMABLE_POTENT_SNAKE_OIL", nullptr, 0, 0, true },
		{ "CONSUMABLE_SPECIAL_SNAKE_OIL_CRAFTED", nullptr, 0, 0, true },
		{ "CONSUMABLE_TONIC", "CONSUMABLE_TONIC_USED", 0, 0, true },
		{ "CONSUMABLE_POTENT_TONIC", nullptr, 0, 0, true },
		{ "CONSUMABLE_SPECIAL_TONIC_CRAFTED", nullptr, 0, 0, true },
	};
	static int active = -1;
	static Hash activeItem = 0;
	static int beforeTotal = 0;
	static int emptyBefore = 0;
	static DWORD endedAt = 0;
	static bool stowing = false;
	static bool stowAnimStarted = false;
	static bool granted = false;
	static bool grantResolved = false;
	static bool removalAttempted = false;
	static DWORD grantAt = 0;
	static DWORD forceConsumeAt = 0;
	static DWORD cancelAt = 0;
	static DWORD finalSwigAt = 0;
	static Object activeBottleProp = 0;
	static Hash activeBottleModel = 0;
	static Hash lastLoggedState = 0;
	static const Hash kConsumeAnimEvent = 442509369;
	static const char* kStowDict =
		"mech_inventory@item@_templates@cylinder@d6-5_h1-5_inspectz@unarmed@base";
	static const char* kStowClip = "cylinder_put_away_satchel";
	for (BottleSource& source : sources) {
		if (!source.full) source.full = joaat(source.fullName);
		if (source.usedName && !source.used) source.used = joaat(source.usedName);
	}
	const bool running = ITEM_INTERACTION_RUNNING(ped);
	const Hash item = running ? ITEM_INTERACTION_ITEM(ped) : 0;
	if (active < 0 && item) {
		for (int i = 0; i < (int)(sizeof(sources) / sizeof(sources[0])); ++i) {
			if (item != sources[i].full && item != sources[i].used) continue;
			active = i;
			activeItem = item;
			beforeTotal = INVENTORY_ITEM_COUNT(sources[i].full) +
				(sources[i].used ? INVENTORY_ITEM_COUNT(sources[i].used) : 0);
			emptyBefore = INVENTORY_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE"));
			endedAt = 0;
			stowing = false;
			stowAnimStarted = false;
			granted = false;
			grantResolved = false;
			removalAttempted = false;
			grantAt = 0;
			forceConsumeAt = 0;
			cancelAt = 0;
			finalSwigAt = 0;
			activeBottleProp = 0;
			activeBottleModel = 0;
			lastLoggedState = 0;
			break;
		}
	}
	if (active < 0) return;
	BottleSource& source = sources[active];
	const int currentTotal = INVENTORY_ITEM_COUNT(source.full) +
		(source.used ? INVENTORY_ITEM_COUNT(source.used) : 0);
	const bool shouldKeep = g_emptyBottlesEnabled &&
		(!source.tonic || g_humanTonicBottles);
	// Preload throughout the drink so the replacement animation is ready at the
	// inventory transition instead of being requested after the discard starts.
	if (running && shouldKeep && !STREAMING::HAS_ANIM_DICT_LOADED(kStowDict))
		STREAMING::REQUEST_ANIM_DICT(kStowDict);
	const Hash interactionState = running ? ITEM_INTERACTION_STATE(ped) : 0;
	if (running && interactionState != lastLoggedState) {
		lastLoggedState = interactionState;
		GtLogStream("bottles", GT_INFO)
			<< "source=" << source.fullName << " interaction-state=0x"
			<< std::hex << interactionState << std::dec << " item=0x"
			<< std::hex << item << std::dec << " total=" << currentTotal << "\n";
	}
	// generic_alcohol_item applies the swig on this authored animation event.
	// Give that script the rest of this frame to process the same non-consuming
	// event, then cancel on our next tick. The live trace put the discard 1.844s
	// later, so this seam is early enough to prevent the throw.
	if (!stowing && !finalSwigAt && running && shouldKeep &&
		ENTITY::HAS_ANIM_EVENT_FIRED(ped, kConsumeAnimEvent)) {
		finalSwigAt = now;
		// The authored swig event occurs well before the discard. Keep the drink
		// playing until shortly before the measured throw seam, then replace the
		// discard with the satchel animation.
		cancelAt = now + (DWORD)g_emptyBottleStowDelayMs;
		Vector3 pos = ENTITY::GET_ENTITY_COORDS(ped, TRUE, FALSE);
		static const char* bottleModels[] = {
			"P_BOTTLEJD_USED01X", "S_BRANDY_USED01X", "S_INV_GIN_USED01X",
			"S_INV_USEDRUM01X", "S_INV_WHISKEY01X", "S_BRANDY01X",
			"S_INV_GIN01X", "S_INV_RUM01X", "S_INV_SNAKEOIL01X",
			"S_INV_TONIC01X", "S_INV_MEDICINE01X"
		};
		for (const char* modelName : bottleModels) {
			const Hash model = joaat(modelName);
			Object object = invoke<Object>(0xE143FA2249364369,
				pos.x, pos.y, pos.z, 3.0f, model, FALSE, FALSE, FALSE);
			if (!object || !ENTITY::IS_ENTITY_ATTACHED(object)) continue;
			activeBottleProp = object;
			activeBottleModel = model;
			break;
		}
		GtLogStream("bottles", GT_INFO)
			<< "source=" << source.fullName
			<< " final-swig-event state=0x" << std::hex << interactionState
			<< " prop=" << activeBottleProp << " model=0x" << activeBottleModel
			<< std::dec << " before=" << beforeTotal
			<< " emptyBefore=" << emptyBefore << "\n";
	}
	if (!stowing && finalSwigAt && now >= cancelAt && shouldKeep) {
		stowing = true;
		grantAt = now + 520;
		forceConsumeAt = now + 120;
		if (activeBottleProp && ENTITY::DOES_ENTITY_EXIST(activeBottleProp))
			OBJECT::DELETE_OBJECT(&activeBottleProp);
		TASK::CLEAR_PED_TASKS(ped, true, false);
		if (STREAMING::HAS_ANIM_DICT_LOADED(kStowDict)) {
			TASK::TASK_PLAY_ANIM(ped, kStowDict, kStowClip,
				6.0f, -3.0f, 1000, 0, 0.0f, FALSE, 0, FALSE, "", FALSE);
			stowAnimStarted = true;
		}
		GtLogStream("bottles", GT_INFO)
			<< "source=" << source.fullName
			<< " final-swig-cancel-stow"
			<< " stowLoaded=" << STREAMING::HAS_ANIM_DICT_LOADED(kStowDict)
			<< " before=" << beforeTotal << " current=" << currentTotal << "\n";
	}
	if (stowing) {
		if (!stowAnimStarted && STREAMING::HAS_ANIM_DICT_LOADED(kStowDict)) {
			TASK::TASK_PLAY_ANIM(ped, kStowDict, kStowClip,
				6.0f, -3.0f, 1000, 0, 0.0f, FALSE, 0, FALSE, "", FALSE);
			stowAnimStarted = true;
			GtLogStream("bottles", GT_INFO)
				<< "source=" << source.fullName << " delayed-stow-start\n";
		}
		int liveTotal = INVENTORY_ITEM_COUNT(source.full) +
			(source.used ? INVENTORY_ITEM_COUNT(source.used) : 0);
		if (!removalAttempted && now >= forceConsumeAt && liveTotal >= beforeTotal) {
			removalAttempted = true;
			const bool removed = INVENTORY_REMOVE_WITH_REASON(
				activeItem, 1, joaat("REMOVE_REASON_DEFAULT"));
			const int afterRemove = INVENTORY_ITEM_COUNT(source.full) +
				(source.used ? INVENTORY_ITEM_COUNT(source.used) : 0);
			GtLogStream("bottles", GT_INFO)
				<< "source=" << source.fullName
				<< " forced-consume returned=" << removed
				<< " item=0x" << std::hex << activeItem << std::dec
				<< " before=" << liveTotal << " after=" << afterRemove << "\n";
			liveTotal = afterRemove;
		}
		if (!grantResolved && now >= grantAt && liveTotal < beforeTotal) {
			const int beforeAdd = INVENTORY_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE"));
			const bool addReturned = INVENTORY_ADD(joaat("PROVISION_EMPTY_BOTTLE"), 1);
			const int afterAdd = INVENTORY_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE"));
			granted = afterAdd > beforeAdd;
			grantResolved = true;
			char feed[96];
			if (granted) {
				sprintf_s(feed, "Empty Bottle (%d/5)", afterAdd);
				CASING_FEED(feed, "INVENTORY_ITEMS", joaat("GENERIC_BOTTLE"));
			} else if (beforeAdd >= 5) {
				sprintf_s(feed, "Empty Bottle satchel full (%d/5)", beforeAdd);
				CASING_FEED(feed, "INVENTORY_ITEMS", joaat("GENERIC_BOTTLE"));
			}
			GtLogStream("bottles", GT_INFO)
				<< "source=" << source.fullName
				<< " stow-grant returned=" << addReturned
				<< " realDelta=" << (afterAdd - beforeAdd)
				<< " inventoryBefore=" << beforeAdd
				<< " inventoryAfter=" << afterAdd
				<< " satchelGuidCount="
				<< INVENTORY_SATCHEL_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE")) << "\n";
		}
		if (!grantResolved && now < grantAt + 1500) return;
		if (grantResolved && now < grantAt + 650) return;
		active = -1;
		activeItem = 0;
		stowing = false;
		stowAnimStarted = false;
		finalSwigAt = 0;
		activeBottleProp = 0;
		return;
	}
	if (running) {
		endedAt = 0;
		return;
	}
	if (!endedAt) {
		endedAt = now;
		return;
	}
	// Inventory conversion/removal lands shortly after the interaction ends.
	if (now - endedAt < 750) return;
	const int afterTotal = INVENTORY_ITEM_COUNT(source.full) +
		(source.used ? INVENTORY_ITEM_COUNT(source.used) : 0);
	const int consumed = (std::max)(0, beforeTotal - afterTotal);
	if (g_emptyBottlesEnabled && consumed > 0 &&
		(!source.tonic || g_humanTonicBottles)) {
		const int beforeAdd = INVENTORY_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE"));
		const bool addReturned = INVENTORY_ADD(joaat("PROVISION_EMPTY_BOTTLE"), consumed);
		const int after = INVENTORY_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE"));
		char feed[96];
		if (after > beforeAdd) {
			sprintf_s(feed, "Empty Bottle (%d/5)", after);
			CASING_FEED(feed, "INVENTORY_ITEMS", joaat("GENERIC_BOTTLE"));
		} else if (beforeAdd >= 5) {
			sprintf_s(feed, "Empty Bottle satchel full (%d/5)", beforeAdd);
			CASING_FEED(feed, "INVENTORY_ITEMS", joaat("GENERIC_BOTTLE"));
		}
		GtLogStream("bottles", GT_INFO)
			<< "source=" << source.fullName << " beforeTotal=" << beforeTotal
			<< " afterTotal=" << afterTotal << " bottles=" << consumed
			<< " addReturned=" << addReturned
			<< " realDelta=" << (after - beforeAdd)
			<< " inventoryAfter=" << after
			<< " satchelGuidCount="
			<< INVENTORY_SATCHEL_ITEM_COUNT(joaat("PROVISION_EMPTY_BOTTLE")) << "\n";
	}
	active = -1;
	activeItem = 0;
	endedAt = 0;
	finalSwigAt = 0;
	activeBottleProp = 0;
}

// Catalog category of an item, as bandana.c func_10 reads it. The decompiler's
// struct<2> counts 64-bit script slots, not the complete native output. Public
// DataView callers allocate six to eight 64-bit slots and read category from
// slot 1. Keep two guard slots beyond that observed six-slot contract. The old
// Any[2] buffer corrupted the caller's stack.
// Cached because the worn-scan asks about the same few components every frame.
static Hash itemCategory(Hash item) {
	static std::unordered_map<Hash, Hash> cache;
	auto it = cache.find(item);
	if (it != cache.end()) return it->second;
	Any info[8] = {};
	Hash category = 0;
	if (invoke<BOOL>(0xFE90ABBCBFDC13B2, item, &info))
		category = static_cast<Hash>(info[1]);
	cache.emplace(item, category);
	return category;
}

static void updateCarriedMask(DWORD now) {
	struct MaskRoute { const char* real; const char* proxy; };
	static const MaskRoute routes[] = {
		{"KIT_MASK_BLACK_HOOD", "LEX_CARRIED_MASK_BLACK_HOOD"},
		{"KIT_MASK_BROWN_SACK", "LEX_CARRIED_MASK_BROWN_SACK"},
		{"KIT_MASK_GREY_CLOTH", "LEX_CARRIED_MASK_GREY_CLOTH"},
		{"KIT_MASK_METAL", "LEX_CARRIED_MASK_METAL"},
		{"KIT_MASK_PSYCHO", "LEX_CARRIED_MASK_PSYCHO"},
		{"CLOTHING_ITEM_MASK_PIG_001", "LEX_CARRIED_MASK_PIG"},
		{"CLOTHING_ITEM_SKULLMASK_MR1_000_1", "LEX_CARRIED_MASK_SKULL_0"},
		{"CLOTHING_ITEM_SKULLMASK_MR1_001_1", "LEX_CARRIED_MASK_SKULL_1"},
		{"CLOTHING_ITEM_SKULLMASK_MR1_002_1", "LEX_CARRIED_MASK_SKULL_2"}
	};
	static DWORD lastApply = 0;
	static DWORD nextFailureLog = 0;
	static Hash redirectedProxy = 0;
	static bool logBooted = false;
	static Hash lastDesiredProxy = 0;
	// #114: these are edge latches, not a periodic reconciliation licence.
	// Rockstar's shop scripts refuse service while the inventory subsystem is
	// busy. Reissuing availability/hidden/in-use writes every 500 ms kept that
	// subsystem in a near-continuous transaction and made every shopkeeper fall
	// back to ordinary ped dialogue. Only write when our requested state changes.
	static unsigned previousEquippedBits = 0;
	static bool equippedBitsInitialized = false;
	// Set whenever WE start a mask on/off interaction. While this is running the
	// equipped bits are changing because of us, not because Lexer picked a new
	// mask at a wardrobe, and must never be read as a selection change.
	static DWORD maskSelfEquipUntil = 0;
	// #77 REGRESSION ROOT CAUSE: the weapon-wheel transaction guard used to sit
	// HERE, at the top of the function, and returned before the proxy redirect
	// further down. The redirect is the one thing that MUST run in exactly that
	// window: the carrier's item interaction begins the instant the radial
	// closes, which is inside "INPUT_OPEN_WHEEL_MENU held + 2000 ms". With the
	// redirect skipped, Rockstar's BANDANA script ran against the PROXY item, so
	// it played the put-on animation and then applied the proxy's clothing at its
	// anim event - and the proxy has no mask component. That is exactly the
	// reported "the animation plays but the mask never actually goes on, nor does
	// the check mark appear".
	//   Script evidence: bandana.c __EntryFunction__ (bandana.c:6-24) takes the
	//   item as ScriptParam_0.f_2 -> Local_0.f_1, and at anim event 822176400
	//   applies clothing for THAT item (bandana.c:88-101: func_11 when
	//   func_10(item) == 81053684, else func_12). So the interaction has to be
	//   restarted on the REAL record before that event fires.
	//   Runtime evidence: the installed session's GameplayTweaks.carried-mask.log
	//   holds five "weapon-wheel: carrier sync deferred" lines, one startup
	//   "worn=0 scan=0 latch=0 pending=-1" line, and ZERO "proxy-redirect" lines
	//   for the entire session - the redirect never executed once.
	// The guard is NOT removed. It is moved down to wrap only the inventory,
	// clothing-active and carried-clothing-cache MUTATIONS it was added for. The
	// redirect below only fires when the RUNNING item interaction is our own
	// carrier proxy, which can never be Rockstar's horse-weapon equip
	// transaction, and it touches tasks rather than inventory records.
	// The component globals do not change at the same instant as the radial
	// interaction.  Keep the state we explicitly requested authoritative until
	// the component scan catches up; a wall-clock timeout let a stale pre-removal
	// component turn the carrier check mark back on.
	// -1 = no command pending, 0 = waiting for removed, 1 = waiting for worn.
	static int pendingMaskWornState = -1;
	// The radial check mark and the "release to remove" prompt come from the
	// carrier's clothing-active state. Keep the last settled/commanded state for
	// diagnostics; pendingMaskWornState owns the UI while a component transition
	// is still settling.
	static int maskWornRouteLatch = -1;
	int wornRoute = -1;
	unsigned equippedBits = 0;
	int wornSlot = -1;
	bool bandanaWorn = false;
	// THE WORN SCAN NEVER MATCHED ANYTHING. It compared the applied component
	// against joaat("KIT_MASK_PSYCHO") and friends, and your log shows the result:
	// wornRoute=-1 for the whole session, mask on his face or not. So `worn` was
	// always false, every use issued MASK_ON and never MASK_OFF, and the check mark
	// rode entirely on the latch - which is why it stayed lit however I patched
	// the latch. The applied component is not the catalog hash we ask for; it is
	// whatever wardrobe record fits that slot. bandana.c func_30 never compares
	// hashes either - it takes the component in the slot, rejects it if it is zero
	// or still the outfit default, and asks the item database for its CATEGORY.
	// Do exactly that. -525676072 = CI_CATEGORY_WARDROBE_MASK, 81053684 = bandana.
	bool maskOnFace = false;
	for (int slot = 0; slot < 39; ++slot) {
		const Hash component = (Hash)*getGlobalPtr(1946804 + 1498 + slot * 3);
		if (!component) continue;
		// Global_1946804.f_57[slot*11] is the slot's outfit default; equal means
		// he is simply dressed, not that he pulled something on.
		if (component == (Hash)*getGlobalPtr(1946804 + 57 + slot * 11)) continue;
		const Hash category = itemCategory(component);
		if (category == (Hash)81053684) bandanaWorn = true;
		if (category == (Hash)-525676072) {
			if (!maskOnFace) { maskOnFace = true; wornSlot = slot; }
			// Exact-hash identification still drives wardrobe SELECTION below,
			// where knowing which mask was previewed is the whole point.
			for (int i = 0; i < (int)_countof(routes); ++i)
				if (component == joaat(routes[i].real) && wornRoute < 0) wornRoute = i;
		}
	}
	for (int i = 0; i < (int)_countof(routes); ++i)
		if (INVENTORY_ITEM_EQUIPPED(joaat(routes[i].real))) equippedBits |= 1u << i;
	if (!logBooted) {
		logBooted = true;
		GtLogStream("carried-mask", GT_INFO)
			<< "session-start enabled=" << g_carriedMaskEnabled
			<< " configured=" << g_carriedMask << "\n";
	}
	// A wardrobe preview temporarily applies the real large-mask metaped
	// component. Persist that exact item before Rockstar removes it on exit.
	int newlyEquippedRoute = -1;
	int currentRoute = -1;
	for (int i = 0; i < (int)_countof(routes); ++i)
		if (g_carriedMask == routes[i].real) { currentRoute = i; break; }
	if (equippedBitsInitialized) {
		const unsigned rising = equippedBits & ~previousEquippedBits;
		// THE CARRIER MUST NEVER REWRITE WHICH MASK YOU OWN.
		// Putting the carried mask ON equips its real record, which makes that
		// record's equipped bit RISE. The old code read any rising bit as "the
		// player chose a new mask at the wardrobe" - so the carrier's own action
		// fed straight back into the selection detector. Worse, it took the
		// LOWEST-INDEX rising bit, not the one we actually equipped, so wearing
		// Psycho (index 4) could silently hand the carrier to whatever rose
		// alongside it at a lower index. That is exactly the reported "I selected
		// the Psycho mask and it turned into the Executioner Hood - and actually
		// changed my equipped mask to it".
		// Two guards: ignore rising bits entirely while our own interaction owns
		// the change, and never treat our own route rising as a new selection.
		if (now < maskSelfEquipUntil ||
			ITEM_INTERACTION_RUNNING(PLAYER::PLAYER_PED_ID())) {
			newlyEquippedRoute = -1;
		} else if (currentRoute >= 0 && (rising & (1u << currentRoute))) {
			newlyEquippedRoute = -1;
		} else {
			for (int i = 0; i < (int)_countof(routes); ++i)
				if (rising & (1u << i)) { newlyEquippedRoute = i; break; }
		}
	} else equippedBitsInitialized = true;
	previousEquippedBits = equippedBits;
	// Several wardrobe mask records can remain marked equipped at once. Only a
	// newly rising record (or the component actually worn in the preview) is a
	// selection change; choosing the last true bit caused stale Psycho/Metal.
	const int observedRoute = newlyEquippedRoute >= 0 ? newlyEquippedRoute : wornRoute;
	bool selectionChangedThisFrame = false;
	if (g_carriedMaskEnabled && observedRoute >= 0 &&
		g_carriedMask != routes[observedRoute].real) {
			// This is an actual wardrobe selection, not our radial interaction.
			// Any older commanded state belongs to the previous carried item.
			pendingMaskWornState = -1;
			g_carriedMask = routes[observedRoute].real;
			selectionChangedThisFrame = true;
			WritePrivateProfileStringA("CarriedMask", "Item",
				g_carriedMask.c_str(), g_iniPath.c_str());
			GtLogStream("carried-mask", GT_INFO)
				<< "component-selected=" << g_carriedMask
				<< " slot=" << wornSlot
				<< " newlyEquipped=" << (newlyEquippedRoute == observedRoute) << "\n";
	}
	int selectedRoute = -1;
	for (int i = 0; i < (int)_countof(routes); ++i)
		if (g_carriedMask == routes[i].real) { selectedRoute = i; break; }
	const bool usingMask = g_carriedMaskEnabled && selectedRoute >= 0;
	// short_update uses bit 8 of this global availability mask for the ordinary
	// clothing/bandana bucket. Respect the same state so camp, animations, and
	// other invalid contexts grey the segment instead of offering a dead action.
	// Slot placement and use availability are independent. quickselectitems maps
	// the carrier into CLOTHING_ITEMS, but its catalog category remains
	// CI_CATEGORY_WARDROBE_MASK (-525676072), whose short_update availability
	// mask is 8. Ordinary KIT_BANDANA uses mask 4.
	bool radialAvailable = ((*getGlobalPtr(1935496 + 27) & 8) != 0);
	// #42: the segment never greyed out in camp, where a mask cannot be worn, so
	// it could be selected and simply do nothing. The availability bit above does
	// not cover camp, so gate on it explicitly: standing in camp, or an item
	// interaction / scripted task already owning the ped.
	const Ped maskPed = PLAYER::PLAYER_PED_ID();
	// #42 PERMANENTLY DISABLED. This used to be `SCRIPT_REFS("player_camp") > 0`,
	// which is not "you are in camp" at all. Our own campsite system starts
	// player_camp as soon as you come within 120m of any placed campsite and
	// leaves it running, so on any save with campsites the gate was true across
	// almost the whole map - the carrier got INVENTORY_DISABLE_ITEM every 500ms
	// and the wheel segment was dead forever. Ask the question we actually meant:
	// is the player standing in the materialized camp.
	bool inCamp = false;
	if (maskPed && g_materializedCamp >= 0 &&
		g_materializedCamp < (int)g_campsites.size()) {
		inCamp = campDistanceSq(ENTITY_COORDS(maskPed),
			g_campsites[g_materializedCamp].pos) < 15.0f * 15.0f;
	}
	// Mounted and in a wagon are NOT invalid contexts - vanilla lets you pull a
	// mask on from the saddle, and gating on them is what made the segment dead
	// for minutes at a time (your log: busy=1 from 525205968 to 525399562, a
	// straight three minutes of riding). They are gone from this list.
	const bool busy = maskPed && (
		PED::IS_PED_DEAD_OR_DYING(maskPed, TRUE) ||
		PED::IS_PED_RAGDOLL(maskPed) ||
		PED::IS_PED_SWIMMING(maskPed) ||
		PED::IS_PED_USING_ANY_SCENARIO(maskPed) ||
		ITEM_INTERACTION_RUNNING(maskPed));
	const bool bitAvailable = radialAvailable;
	if (inCamp || busy) radialAvailable = false;
	// The carrier-sync line below only prints when the DESIRED ITEM changes, so a
	// segment that greys out mid-session left no trace at all - the last session's
	// log held one line, radialAvailable=1, and nothing after. Print every
	// transition with the reason, so "it is disabled" is a readable fact.
	{
		static int lastRadialAvailable = -1;
		const int nowAvailable = radialAvailable ? 1 : 0;
		if (nowAvailable != lastRadialAvailable) {
			lastRadialAvailable = nowAvailable;
			GtLogStream("carried-mask", GT_INFO)
				<< "radialAvailable=" << nowAvailable
				<< " bit8=" << (bitAvailable ? 1 : 0)
				<< " inCamp=" << (inCamp ? 1 : 0)
				<< " busy=" << (busy ? 1 : 0)
				<< " materializedCamp=" << g_materializedCamp << "\n";
		}
	}
	const char* desiredProxyName = usingMask
		? routes[selectedRoute].proxy : "LEX_CARRIED_BANDANA";
	const char* desiredRealName = usingMask
		? routes[selectedRoute].real : "KIT_BANDANA";
	const Hash desiredProxy = joaat(desiredProxyName);
	const Hash desiredReal = joaat(desiredRealName);
	// An empty process-local latch means only that the ASI has just loaded. It is
	// not a player selection and must not authorize a clothing-inventory write.
	// The old code treated this first observation as a change, unhid the existing
	// proxy, and rewrote its in-use state on the first GameplayTweaks frame. That
	// raced Rockstar's shop-owner acquisition (#114).
	const bool desiredProxyChanged = lastDesiredProxy != 0 &&
		lastDesiredProxy != desiredProxy;

	// Diagnostics that can observe their own failure (#77 cost several builds to
	// a redirect that simply never ran, with nothing in the log to say so):
	//  - every change of the running item-interaction item is recorded, so a
	//    carrier use that did NOT redirect is visible as an `interaction=` line
	//    with our proxy hash and no following `proxy-redirect` line;
	//  - a 30 s heartbeat means a silent log proves "updateCarriedMask is not
	//    running", not "nothing happened".
	{
		static Hash lastInteractionItem = 0;
		const bool running = ITEM_INTERACTION_RUNNING(PLAYER::PLAYER_PED_ID());
		const Hash observed = running ? ITEM_INTERACTION_ITEM(PLAYER::PLAYER_PED_ID()) : 0;
		if (observed != lastInteractionItem) {
			lastInteractionItem = observed;
			GtLogStream("carried-mask", GT_INFO)
				<< "interaction=0x" << std::hex << observed
				<< " desiredProxy=0x" << desiredProxy
				<< " redirectedProxy=0x" << redirectedProxy << std::dec
				<< " wheelGuard=" << (weaponWheelTransactionBusy(now) ? 1 : 0) << "\n";
		}
		static DWORD lastHeartbeat = 0;
		if (now - lastHeartbeat >= 30000) {
			lastHeartbeat = now;
			GtLogStream("carried-mask", GT_INFO)
				<< "heartbeat selectedRoute=" << selectedRoute
				<< " usingMask=" << (usingMask ? 1 : 0)
				<< " maskOnFace=" << (maskOnFace ? 1 : 0)
				<< " pending=" << pendingMaskWornState
				<< " radialAvailable=" << (radialAvailable ? 1 : 0)
				<< " wheelGuard=" << (weaponWheelTransactionBusy(now) ? 1 : 0) << "\n";
		}
	}

	if (ITEM_INTERACTION_RUNNING(PLAYER::PLAYER_PED_ID())) {
		const Hash interactionItem = ITEM_INTERACTION_ITEM(PLAYER::PLAYER_PED_ID());
		if (interactionItem == desiredProxy && redirectedProxy != desiredProxy) {
			redirectedProxy = desiredProxy;
			CLEAR_PED_SECONDARY_TASK(PLAYER::PLAYER_PED_ID());
			Hash primary = 0, secondary = 0;
			invoke<BOOL>(0x3A87E44BB9A01D54, PLAYER::PLAYER_PED_ID(), &primary, TRUE, 0, FALSE);
			invoke<BOOL>(0x3A87E44BB9A01D54, PLAYER::PLAYER_PED_ID(), &secondary, TRUE, 1, FALSE);
			const bool rifle = secondary == joaat("WEAPON_UNARMED") &&
				primary != joaat("WEAPON_UNARMED") &&
				invoke<BOOL>(0x0556E9D2ECF39D01, primary) != 0;
			// Which way to toggle. The live trace proved the component scan can stay
			// false even after the real MASK_ON interaction: two consecutive radial
			// selections both logged `worn=0`, so the second selection issued MASK_ON
			// again and the check mark could never clear. While we have a commanded
			// carrier state, that state is the authoritative pre-toggle value. Once it
			// has settled, the route latch is the next-best source; the physical scan
			// remains the fallback for wardrobe/script changes we did not command.
			const bool scanWorn = usingMask ? maskOnFace : bandanaWorn;
			const bool latchedWorn = usingMask
				? maskWornRouteLatch == selectedRoute : maskWornRouteLatch == -2;
			const bool worn = pendingMaskWornState >= 0
				? pendingMaskWornState != 0
				: (latchedWorn || scanWorn);
			const Hash state = usingMask
				? joaat(worn
					? (rifle ? "MASK_OFF_LEFT_HAND_RIFLE" : "MASK_OFF_RIGHT_HAND")
					: (rifle ? "MASK_ON_LEFT_HAND_RIFLE" : "MASK_ON_RIGHT_HAND"))
				: joaat(worn
					? (rifle ? "BANDANA_OFF_LEFT_HAND_RIFLE" : "BANDANA_OFF_RIGHT_HAND")
					: (rifle ? "BANDANA_ON_LEFT_HAND_RIFLE" : "BANDANA_ON_RIGHT_HAND"));
			// Record which way we just toggled it. `worn` here is the state
			// BEFORE the interaction, so the result is its inverse.
			if (usingMask) maskWornRouteLatch = worn ? -1 : selectedRoute;
			else maskWornRouteLatch = worn ? -1 : -2;   // -2 = bandana worn
			pendingMaskWornState = worn ? 0 : 1;
			// This is the carrier's own clothing transaction, not the unrelated
			// horse-weapon transaction protected below. Publish the commanded state
			// immediately so the radial's check mark changes with the selection rather
			// than two seconds later when the general wheel-settle guard expires.
			// Rockstar's real mask interaction is about to mutate clothing in this same
			// window, so deferring only our proxy's in-use bit served no safety purpose.
			InventoryGuid commandedCarrierGuid = {};
			const bool commandedGuidValid =
				INVENTORY_CLOTHING_GUID(desiredProxy, &commandedCarrierGuid);
			if (commandedGuidValid) {
				INVENTORY_SET_CLOTHING_ACTIVE(&commandedCarrierGuid, !worn);
			}
			START_ITEM_INTERACTION(PLAYER::PLAYER_PED_ID(), desiredReal, state);
			// Everything this interaction does to the equipped bits is OUR doing.
			// Blind the wardrobe-selection detector until well after it settles,
			// or wearing a mask silently reassigns which mask you carry.
			maskSelfEquipUntil = now + 4000;
			GtLogStream("carried-mask", GT_INFO)
				<< "proxy-redirect proxy=" << desiredProxyName
				<< " real=" << desiredRealName
				<< " worn=" << worn
				<< " carrierCommand=" << (!worn ? 1 : 0)
				<< " guidValid=" << (commandedGuidValid ? 1 : 0)
				<< " state=0x" << std::hex << state << std::dec << "\n";
		}
	} else if (!ITEM_INTERACTION_RUNNING(PLAYER::PLAYER_PED_ID())) {
		redirectedProxy = 0;
	}

	// Never mutate inventory records or clothing-active state while the weapon
	// wheel is open (or while its
	// selection is settling). Horse weapon selection temporarily drops the
	// clothing availability bit; feeding that transient state back through
	// INVENTORY_DISABLE_ITEM and INVENTORY_SET_CLOTHING_ACTIVE collided with the
	// game's weapon equip transaction and produced
	// ERROR:FFFFFFFF. Everything below this point is that mutation; everything
	// above it is read-only scanning plus the proxy redirect.
	static bool loggedWheelDeferral = false;
	if (weaponWheelTransactionBusy(now)) {
		if (!loggedWheelDeferral) {
			loggedWheelDeferral = true;
			GtLogStream("carried-mask", GT_INFO)
				<< "weapon-wheel: carrier mutation deferred\n";
		}
		return;
	}
	loggedWheelDeferral = false;
	if (now - lastApply < 500) return;
	lastApply = now;
	static const char* allProxies[] = {
		"LEX_CARRIED_BANDANA",
		"LEX_CARRIED_MASK_BLACK_HOOD",
		"LEX_CARRIED_MASK_BROWN_SACK",
		"LEX_CARRIED_MASK_GREY_CLOTH",
		"LEX_CARRIED_MASK_METAL",
		"LEX_CARRIED_MASK_PSYCHO",
		"LEX_CARRIED_MASK_PIG",
		"LEX_CARRIED_MASK_SKULL_0",
		"LEX_CARRIED_MASK_SKULL_1",
		"LEX_CARRIED_MASK_SKULL_2"
	};
	bool inventoryChanged = false;
	bool desiredPresent = false;
	int addStage = -1;
	for (const char* proxyName : allProxies) {
		const Hash proxy = joaat(proxyName);
		const int count = INVENTORY_ITEM_COUNT(proxy);
		if (proxy == desiredProxy) {
			desiredPresent = count > 0;
			if (!desiredPresent && (selectionChangedThisFrame || desiredProxyChanged)) {
				const bool added = INVENTORY_ADD_CLOTHING(proxy, 1, &addStage);
				desiredPresent = added || INVENTORY_ITEM_COUNT(proxy) > 0;
				inventoryChanged = inventoryChanged || added;
			}
		} else if ((selectionChangedThisFrame || desiredProxyChanged) && count > 0) {
			inventoryChanged = INVENTORY_REMOVE(proxy, count) || inventoryChanged;
		}
	}
	// Use only Rockstar's inventory natives for clothing granted after startup.
	// Do not imitate short_update's func_1650/func_2906 cache writes here. The
	// removed implementation started the structure at f_2658 instead of f_2657,
	// wrote the mask count into the wrong category, and omitted func_3762 and the
	// later cache-copy semantics. That one-slot shift corrupted the shared
	// clothing state used by shop presentation. Rockstar remains the sole owner
	// of Global_1946804 and its carried-clothing cache.
	bool guidValid = false;
	int guidCount = -1;
	if (desiredPresent) {
		// #114: Rockstar owns item availability.  Its bit-8 value changes while
		// shop and other inventory UIs acquire ownership.  Mirroring that
		// temporary value through INVENTORY_DISABLE_ITEM/ENABLE_ITEM created a
		// new inventory transaction inside the shop-startup window and made the
		// owner fall back to ordinary ped dialogue.  The carrier may observe the
		// bit for diagnostics, but it must never write availability from it.
		InventoryGuid carrierGuid = {};
		guidValid = INVENTORY_CLOTHING_GUID(desiredProxy, &carrierGuid);
		if (guidValid) {
			guidCount = INVENTORY_GUID_COUNT(&carrierGuid);
			if (inventoryChanged)
				INVENTORY_SET_HIDDEN(&carrierGuid, false);
			// Outside our own transition, mirror the physical component directly.
			const bool scanSaysWorn = usingMask ? maskOnFace : bandanaWorn;
			const bool interactionRunning = maskPed && ITEM_INTERACTION_RUNNING(maskPed);
			// #77: a removal command means unchecked immediately.  Do not OR that
			// command with the old face component: Rockstar removes the component at
			// an animation event, and it can remain readable after our four-second
			// selection-blindness window.  The explicit command remains authoritative
			// until the scan reaches the requested state.  Once settled, external
			// wardrobe/script changes are mirrored directly from the scan.
			const bool commandedStatePending = pendingMaskWornState >= 0;
			const bool carrierWorn = commandedStatePending
				? pendingMaskWornState != 0 : scanSaysWorn;
			if (commandedStatePending && !interactionRunning &&
				scanSaysWorn == (pendingMaskWornState != 0)) {
				maskWornRouteLatch = scanSaysWorn
					? (usingMask ? selectedRoute : -2) : -1;
				pendingMaskWornState = -1;
			} else if (!commandedStatePending) {
				maskWornRouteLatch = scanSaysWorn
					? (usingMask ? selectedRoute : -2) : -1;
			}
			const bool latchSaysWorn = usingMask ? (maskWornRouteLatch == selectedRoute)
				: (maskWornRouteLatch == -2);
			const bool carrierInUse = INVENTORY_CLOTHING_ACTIVE(&carrierGuid);
			// Loading the ASI does not own Rockstar's existing in-use state. Only a
			// real wardrobe selection or a proxy created by this transition may
			// initialize it here. Radial use remains owned by the command above.
			if ((selectionChangedThisFrame || inventoryChanged) &&
				carrierInUse != carrierWorn) {
				INVENTORY_SET_CLOTHING_ACTIVE(&carrierGuid, carrierWorn);
			}
			static bool loggedWorn = false;
			static bool lastCarrierWorn = false;
			if (!loggedWorn || carrierWorn != lastCarrierWorn) {
				loggedWorn = true; lastCarrierWorn = carrierWorn;
				GtLogStream("carried-mask", GT_INFO)
					<< "worn=" << (carrierWorn ? 1 : 0)
					<< " scan=" << (scanSaysWorn ? 1 : 0)
					<< " latch=" << (latchSaysWorn ? 1 : 0)
					<< " pending=" << pendingMaskWornState
					<< " maskOnFace=" << (maskOnFace ? 1 : 0)
					<< " wornSlot=" << wornSlot
					<< " wornRoute=" << wornRoute
					<< " selectedRoute=" << selectedRoute
					<< " bandanaWorn=" << (bandanaWorn ? 1 : 0) << "\n";
			}
		}
	}
	if (lastDesiredProxy != desiredProxy || inventoryChanged ||
		(!desiredPresent && now >= nextFailureLog)) {
		if (!desiredPresent) nextFailureLog = now + 5000;
		lastDesiredProxy = desiredProxy;
		GtLogStream("carried-mask", GT_INFO)
			<< "carrier-sync desired=" << desiredProxyName
			<< " present=" << desiredPresent
			<< " enabled=" << (desiredPresent && radialAvailable)
			<< " guidValid=" << guidValid
			<< " guidCount=" << guidCount
			<< " cacheOwner=rockstar"
			<< " changed=" << inventoryChanged
				<< " radialAvailable=" << radialAvailable
			<< " selectedRoute=" << selectedRoute
			<< " wornRoute=" << wornRoute
				<< " equippedBits=0x" << std::hex << equippedBits << std::dec
			<< " addStage=" << addStage << "\n";
	}
}
