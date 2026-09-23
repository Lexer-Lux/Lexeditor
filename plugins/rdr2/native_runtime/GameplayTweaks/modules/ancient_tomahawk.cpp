// GitHub #65: return the Ancient Tomahawk to the inventory the instant the
// thrown weapon hits something.
//
// Deliberately separate from recoverable_unique_weapons.ini and the generic
// unique-weapon recovery path (#66): no locker, no despawn watcher, no timer,
// and no dependency on that feature's enable flag.
//
// ---------------------------------------------------------------------------
// ATTEMPT 4 POST-MORTEM (read this before changing the arming edge again)
// ---------------------------------------------------------------------------
//
// The shipped build armed on an OWNERSHIP-LOSS EDGE: HAS_PED_GOT_WEAPON true
// last frame, false this frame. GameplayTweaks.ancient-tomahawk.log from
// Lexer's test session (43 lines, ~22 minutes of wall clock, timestamps
// 630308546..631626578) contains the initialization line and nothing but idle
// heartbeats. Every one of them reads `owned=1`. There is no `launch` line, so
// no scan line, so no return line: the entire detection chain below the arming
// edge was unreachable, exactly as in attempts 1-3.
//
// The reason ownership never drops is that a throwable is AMMO, not a weapon
// slot. Rockstar's own scripts say so in two places:
//
//   * coachrobberies_gang3.c:30131 — "does the player have a throwable to use"
//     is written as
//       HAS_PED_GOT_WEAPON(ped, WEAPON_THROWN_DYNAMITE, 0, false)
//         && GET_AMMO_IN_PED_WEAPON(ped, WEAPON_THROWN_DYNAMITE) > 0
//     The ammo term is not redundant. If throwing cleared HAS_PED_GOT_WEAPON,
//     Rockstar would not need it.
//
//   * coachrobberies_gang3.c:30222-30224 — "has the player thrown it and has it
//     landed" is written as
//       (!HAS_PED_GOT_WEAPON(...) || GET_AMMO_IN_PED_WEAPON(...) == 0)
//         && !IS_PROJECTILE_TYPE_WITHIN_DISTANCE(coords, weapon, 10f, false)
//     That is the shipped shape of the exact query this feature needs: the
//     THROWN state is ammo==0, and the IN-FLIGHT state is a live projectile
//     query. Not an object-pool handle, and not an ownership edge.
//
//   * MyOverhaul/pickups.meta:3121-3136 — PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT
//     carries the flag KeepWeaponThatUsesThisAmmoEquipped and grants
//     REWARD_WEAPON_THROWN_TOMAHAWK_ANCIENT *and* REWARD_AMMO_TOMAHAWK_ANCIENT
//     as two separate rewards (:3144-3145). Weapon presence and ammo count are
//     two stores, and only the second one moves when you throw.
//
// So this build arms on the AMMO edge and keeps the ownership edge only as a
// secondary reason. If the next log shows `ammoWeapon` and `ammoType` both
// staying non-zero across a throw, the ammo model is wrong too and the two
// remaining arming reasons (`projectile-seen`, `ownership-lost`) will say so.
//
// ---------------------------------------------------------------------------
// IMPACT SIGNALS (four, independent, each named in the return line)
// ---------------------------------------------------------------------------
//
//   projectile-settled  MISC::IS_PROJECTILE_TYPE_WITHIN_DISTANCE(pedCoords,
//                       WEAPON_THROWN_TOMAHAWK_ANCIENT, r, true) was true and
//                       has gone false. This is Rockstar's own model. The
//                       native IS verified against a real shipped call site
//                       that passes the Ancient Tomahawk specifically:
//                       rcm_bh_bandito_shack.c:32346
//                         IS_PROJECTILE_TYPE_WITHIN_DISTANCE(
//                           GET_ENTITY_COORDS(...),
//                           joaat("WEAPON_THROWN_TOMAHAWK_ANCIENT"),
//                           fParam1, true)
//                       (fuckups.txt entry 2 is about the *ped-relative*
//                       GET_COORDS_OF_PROJECTILE_TYPE_WITHIN_DISTANCE, which
//                       has zero tomahawk call sites. This is the different,
//                       coordinate-based native, and it does.)
//
//   object-collision / object-came-to-rest / pickup-spawned
//                       The object-pool signals from attempt 4. Retained
//                       because they are cheap and the tree case is exactly an
//                       object that collided and stopped, but no longer the
//                       only thing that can fire. MyOverhaul/pickups.meta:3122
//                       binds the pickup to model w_melee_tomahawk02.
//
// The impact decision and inventory grant are never timed, delayed,
// locker-backed or despawn-triggered. A bounded post-grant observer exists only
// to remove the engine's later projectile-to-pickup conversion.
//
// ---------------------------------------------------------------------------
// DIAGNOSTICS CONTRACT — the next log must distinguish three outcomes
// ---------------------------------------------------------------------------
//   NEVER ARMED          only `idle` lines. Read ammoWeapon/ammoType/owned
//                        across the throw: whichever of them moves is the
//                        signal, and if none move the ASI cannot see the throw.
//   ARMED, NO IMPACT     a `launch` line, `scan` lines, then `no-signal-abort`.
//                        The scan line prints every signal term separately.
//   IMPACT, GRANT FAILED a `return` line with ownedAfter/ammoAfter still 0.
// The idle heartbeat also prints the RAW object-pool count and how many
// w_melee_tomahawk02 entries were attached vs loose, so `baselineObjects=0`
// can no longer be ambiguous between "pool scan broken" and "nothing nearby".
// All of it now goes to the unified GameplayTweaks.log under subsystem
// "tomahawk" (#126); the idle heartbeat stays at INFO so a silent log remains
// positive evidence that this module is not running.

// Not in script.cpp's helper block; hashes taken from
// _downloads/RDR2_SDK/SDK/inc/natives.h, which is the build include path
// (GameplayTweaks/build.bat line 7).
//   natives.h:8640 WEAPON::GET_AMMO_IN_PED_WEAPON      0x015A522136D7F951
//   natives.h:8625 WEAPON::_ADD_AMMO_TO_PED            0xB190BCA3F4042F95
//   natives.h:3121 MISC::IS_PROJECTILE_TYPE_WITHIN_DISTANCE 0xF51C9BAAD9ED64C4
// 752097756 == joaat("ADD_REASON_DEFAULT"); it is the reason Rockstar passes
// when topping up a throwable the player already owns
// (braithwaites2.c:36546-36548 gates on HAS_PED_GOT_WEAPON then calls
// _ADD_AMMO_TO_PED(ped, WEAPON_THROWN_MOLOTOV, 10, 752097756)).
static const Hash kAncientTomahawkAddReason = 752097756;

struct AncientTomahawkReturnState {
	Hash weapon = 0;
	Hash ammoType = 0;
	Hash model = 0;
	bool armed = false;
	bool everOwned = false;
	bool everArmed = false;
	bool previousOwned = false;
	int previousAmmoWeapon = -1;
	int previousAmmoType = -1;
	bool previousProjectileNear = false;
	bool previousHeldWeaponEntity = false;
	Hash previousWeapon = 0;
	DWORD launchedAt = 0;
	DWORD lastBaselineAt = 0;
	DWORD lastIdleLogAt = 0;
	DWORD lastScanLogAt = 0;
	DWORD returnedAt = 0;
	DWORD cleanupUntil = 0;
	DWORD lastCleanupLogAt = 0;
	unsigned ticks = 0;
	Object tracked = 0;
	Object returnedObject = 0;
	Pickup returnedPickup = 0;
	bool trackedMoved = false;
	bool sawProjectile = false;
	bool cleanupActive = false;
	bool returnFeedPosted = false;
	float trackedTopSpeed = 0.0f;
	Vector3 trackedPosition = {};
	Vector3 impact = {};
	std::unordered_set<int> baselineObjects;
	std::unordered_set<int> baselinePickups;
};

static AncientTomahawkReturnState g_ancientTomahawkReturn;

static float ancientTomahawkDistanceSquared(Vector3 a, Vector3 b) {
	const float dx = a.x - b.x;
	const float dy = a.y - b.y;
	const float dz = a.z - b.z;
	return dx * dx + dy * dy + dz * dz;
}

static void ancientTomahawkLog(GtLogLevel level, const std::string& line) {
	gtLog("tomahawk", level, line);
}

static std::string ancientTomahawkPoint(Vector3 p) {
	std::ostringstream out;
	out << std::fixed << std::setprecision(2) << p.x << "," << p.y << "," << p.z;
	return out.str();
}

static int ancientTomahawkAmmoInWeapon(Ped ped) {
	return invoke<int>(0x015A522136D7F951, ped, g_ancientTomahawkReturn.weapon);
}

// A live projectile of this exact weapon type within `radius` of `origin`.
// Coordinate form, three separate floats -- see natives.h:3121 and the shipped
// call at rcm_bh_bandito_shack.c:32346.
static bool ancientTomahawkProjectileNear(Vector3 origin, float radius) {
	return invoke<BOOL>(0xF51C9BAAD9ED64C4, origin.x, origin.y, origin.z,
		g_ancientTomahawkReturn.weapon, radius, TRUE) != 0;
}

// Every w_melee_tomahawk02 object currently in the pool. The held weapon object
// is attached to the player, so it is counted separately and never treated as a
// landed tomahawk. `rawPoolCount` is reported so a zero result can be told apart
// from a pool scan that returned nothing at all.
static int ancientTomahawkScanObjects(Ped ped, std::vector<Object>* out,
	int* attachedCount, int* rawPoolCount) {
	// 4096 to match the object pool ceiling; 1024 could truncate before reaching
	// a tomahawk sitting late in the pool.
	static std::vector<int> objects(4096);
	std::fill(objects.begin(), objects.end(), 0);
	const int count = worldGetAllObjects(objects.data(), (int)objects.size());
	if (rawPoolCount) *rawPoolCount = count;
	int attached = 0;
	for (int i = 0; i < count; ++i) {
		const Object object = objects[i];
		if (!object || ENTITY_MODEL(object) != g_ancientTomahawkReturn.model) continue;
		if (ped && ENTITY::IS_ENTITY_ATTACHED_TO_ENTITY(object, ped)) { ++attached; continue; }
		out->push_back(object);
	}
	if (attachedCount) *attachedCount = attached;
	return (int)out->size();
}

static int ancientTomahawkScanPickups(std::vector<Pickup>* out, int* rawPoolCount) {
	int pickups[512] = {};
	const int count = worldGetAllPickups(pickups, 512);
	if (rawPoolCount) *rawPoolCount = count;
	for (int i = 0; i < count; ++i) {
		const Pickup pickup = pickups[i];
		if (!pickup) continue;
		const Object object = OBJECT::GET_PICKUP_OBJECT(pickup);
		if (!object || ENTITY_MODEL(object) != g_ancientTomahawkReturn.model) continue;
		out->push_back(pickup);
	}
	return (int)out->size();
}

// Snapshot what already exists so a pre-placed world tomahawk (the original site
// spawn) can never be mistaken for the one the player just threw. Only taken
// while we demonstrably still hold the weapon, so an embedded tomahawk from a
// throw we are tracking can never be absorbed into the baseline.
static void ancientTomahawkRefreshBaseline(Ped ped, DWORD now) {
	AncientTomahawkReturnState& state = g_ancientTomahawkReturn;
	std::vector<Object> objects;
	std::vector<Pickup> pickups;
	ancientTomahawkScanObjects(ped, &objects, nullptr, nullptr);
	ancientTomahawkScanPickups(&pickups, nullptr);
	state.baselineObjects.clear();
	state.baselinePickups.clear();
	for (size_t i = 0; i < objects.size(); ++i) state.baselineObjects.insert(objects[i]);
	for (size_t i = 0; i < pickups.size(); ++i) state.baselinePickups.insert(pickups[i]);
	state.lastBaselineAt = now;
}

// Remove only the world copy of the tomahawk we just handed back, including a
// pickup/object the engine materializes after the impact tick. Anything already
// in the baseline (including the original world spawn) is left alone.
static void cleanupReturnedAncientTomahawk(Ped ped, DWORD now) {
	AncientTomahawkReturnState& state = g_ancientTomahawkReturn;
	if (!state.cleanupActive) return;

	int removedPickups = 0;
	int remainingPickups = 0;
	std::vector<Pickup> pickups;
	ancientTomahawkScanPickups(&pickups, nullptr);
	for (size_t i = 0; i < pickups.size(); ++i) {
		const Pickup pickup = pickups[i];
		if (state.baselinePickups.count(pickup)) continue;
		const Object object = OBJECT::GET_PICKUP_OBJECT(pickup);
		// The projectile-lifecycle impact signal has no coordinate output. The old
		// fallback stored the player's position, then skipped every returned copy
		// more than five metres from the player. The per-throw baseline is the
		// ownership boundary: every new unbaselined Ancient pickup belongs to this
		// throw, regardless of its distance from the player.
		OBJECT::REMOVE_PICKUP(pickup);
		if (OBJECT::DOES_PICKUP_EXIST(pickup)) ++remainingPickups;
		else ++removedPickups;
	}

	// Impact and pickup conversion are not atomic. The engine can replace the
	// projectile with a loose object/pickup on a later tick, so delete every
	// nearby, unbaselined loose copy throughout this bounded post-impact window.
	// The held inventory prop is attached to the ped and is excluded by the scan.
	int deletedObjects = 0;
	int remainingObjects = 0;
	std::vector<Object> objects;
	ancientTomahawkScanObjects(ped, &objects, nullptr, nullptr);
	for (size_t i = 0; i < objects.size(); ++i) {
		const Object object = objects[i];
		if (state.baselineObjects.count(object)) continue;
		// As above, do not apply a fabricated radius to a signal that exposes no
		// impact coordinate. Attached held props were excluded by the scan and all
		// pre-existing loose objects are protected by baselineObjects.
		Object victim = object;
		ENTITY::SET_ENTITY_AS_MISSION_ENTITY(victim, TRUE, TRUE);
		ENTITY::DELETE_ENTITY(&victim);
		if (ENTITY::DOES_ENTITY_EXIST(object)) ++remainingObjects;
		else ++deletedObjects;
	}

	// The same-frame inventory readback can lag the grant. Post the acquisition
	// feed on a later tick only after the returned charge is observable.
	const bool grantVisible = HAS_WEAPON(ped, state.weapon) && ancientTomahawkAmmoInWeapon(ped) > 0;
	if (!state.returnFeedPosted && now != state.returnedAt && grantVisible) {
		CASING_FEED("Ancient Tomahawk returned", "INVENTORY_ITEMS", state.weapon);
		state.returnFeedPosted = true;
	}

	if (removedPickups || deletedObjects || remainingPickups || remainingObjects ||
		now >= state.cleanupUntil || now - state.lastCleanupLogAt >= 250) {
		state.lastCleanupLogAt = now;
		std::ostringstream line;
		line << "post-return-cleanup elapsedMs=" << (now - state.returnedAt)
			<< " removedPickups=" << removedPickups
			<< " deletedObjects=" << deletedObjects
			<< " remainingPickups=" << remainingPickups
			<< " remainingObjects=" << remainingObjects
			<< " grantVisible=" << (grantVisible ? 1 : 0)
			<< " feedPosted=" << (state.returnFeedPosted ? 1 : 0);
		ancientTomahawkLog((remainingPickups || remainingObjects) ? GT_WARN : GT_TRACE, line.str());
	}

	if (now >= state.cleanupUntil) {
		state.cleanupActive = false;
		state.returnedObject = 0;
		state.returnedPickup = 0;
	}
}

static void initializeAncientTomahawkReturn() {
	g_ancientTomahawkReturn = {};
	g_ancientTomahawkReturn.weapon = joaat("WEAPON_THROWN_TOMAHAWK_ANCIENT");
	// pickups.meta:4396-4400 binds REWARD_AMMO_TOMAHAWK_ANCIENT to AmmoRef
	// AMMO_TOMAHAWK_ANCIENT with SatchelItem WEAPON_THROWN_TOMAHAWK_ANCIENT.
	g_ancientTomahawkReturn.ammoType = joaat("AMMO_TOMAHAWK_ANCIENT");
	// pickups.meta:3121-3122 PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT -> Model
	// w_melee_tomahawk02.
	g_ancientTomahawkReturn.model = joaat("w_melee_tomahawk02");
	std::ostringstream line;
	line << "#65 Ancient Tomahawk impact return initialized"
		<< " weapon=" << g_ancientTomahawkReturn.weapon
		<< " ammoType=" << g_ancientTomahawkReturn.ammoType
		<< " model=" << g_ancientTomahawkReturn.model;
	ancientTomahawkLog(GT_INFO, line.str());
}

static void beginAncientTomahawkThrow(Ped ped, DWORD now, const char* reason,
	int ammoWeapon, int ammoType, bool owned, bool projectileNear) {
	AncientTomahawkReturnState& state = g_ancientTomahawkReturn;
	state.armed = true;
	state.everArmed = true;
	state.launchedAt = now;
	state.lastScanLogAt = 0;
	state.tracked = 0;
	state.trackedMoved = false;
	state.sawProjectile = projectileNear;
	state.trackedTopSpeed = 0.0f;
	std::ostringstream line;
	line << "launch reason=" << reason
		<< " at=" << ancientTomahawkPoint(ENTITY_COORDS(ped))
		<< " ammoWeapon=" << ammoWeapon
		<< " ammoType=" << ammoType
		<< " owned=" << (owned ? 1 : 0)
		<< " projNear=" << (projectileNear ? 1 : 0)
		<< " prevAmmoWeapon=" << state.previousAmmoWeapon
		<< " prevAmmoType=" << state.previousAmmoType
		<< " baselineObjects=" << state.baselineObjects.size()
		<< " baselinePickups=" << state.baselinePickups.size();
	ancientTomahawkLog(GT_INFO, line.str());
}

static void finishAncientTomahawkReturn(Ped ped, DWORD now, Vector3 impact, const char* signal) {
	AncientTomahawkReturnState& state = g_ancientTomahawkReturn;
	state.armed = false;
	state.impact = impact;
	state.returnedAt = now;
	state.cleanupUntil = now + 2500;
	state.lastCleanupLogAt = 0;
	state.cleanupActive = true;
	state.returnFeedPosted = false;
	state.returnedObject = state.tracked;

	const bool ownedBefore = HAS_WEAPON(ped, state.weapon);
	const int ammoWeaponBefore = ancientTomahawkAmmoInWeapon(ped);
	const int ammoTypeBefore = GET_PED_AMMO_BY_TYPE(ped, state.ammoType);

	// Granted on the impact frame itself. There is no delay, timeout, locker or
	// despawn step anywhere in this path.
	//
	// Two steps, because the weapon and its ammo are separate stores. GIVE_WEAPON
	// re-adds the weapon if it is genuinely gone, but on a ped that already has
	// the weapon entry it will not restore the thrown charge -- which, per the
	// post-mortem above, is the state we are actually in. Rockstar tops a
	// throwable back up with _ADD_AMMO_TO_PED on a ped that already passes
	// HAS_PED_GOT_WEAPON (braithwaites2.c:36546-36548).
	if (!ownedBefore) GIVE_WEAPON(ped, state.weapon);
	if (ancientTomahawkAmmoInWeapon(ped) < 1)
		invoke<Void>(0xB190BCA3F4042F95, ped, state.weapon, 1, kAncientTomahawkAddReason);

	cleanupReturnedAncientTomahawk(ped, now);

	const bool ownedAfter = HAS_WEAPON(ped, state.weapon);
	const int ammoWeaponAfter = ancientTomahawkAmmoInWeapon(ped);
	const int ammoTypeAfter = GET_PED_AMMO_BY_TYPE(ped, state.ammoType);
	const bool grantOk = ownedAfter && ammoWeaponAfter > 0;
	std::ostringstream line;
	line << "return signal=" << signal
		<< " impact=" << ancientTomahawkPoint(impact)
		<< " tracked=" << state.tracked
		<< " topSpeed=" << std::fixed << std::setprecision(2) << state.trackedTopSpeed
		<< " ownedBefore=" << (ownedBefore ? 1 : 0)
		<< " ownedAfter=" << (ownedAfter ? 1 : 0)
		<< " ammoWeapon=" << ammoWeaponBefore << "->" << ammoWeaponAfter
		<< " ammoType=" << ammoTypeBefore << "->" << ammoTypeAfter
		<< " grantOk=" << (grantOk ? 1 : 0)
		<< " flightMs=" << (now - state.launchedAt);
	ancientTomahawkLog(GT_INFO, line.str());
	// Seed the edge detectors with the post-grant readings so the grant itself
	// cannot immediately re-arm the controller.
	state.previousAmmoWeapon = ammoWeaponAfter;
	state.previousAmmoType = ammoTypeAfter;
	state.previousOwned = ownedAfter;
	state.previousProjectileNear = false;
	state.sawProjectile = false;
	state.tracked = 0;
}

static void updateAncientTomahawkReturn(Ped ped, DWORD now) {
	AncientTomahawkReturnState& state = g_ancientTomahawkReturn;
	if (!ped || ENTITY::IS_ENTITY_DEAD(ped)) {
		state.armed = false;
		state.cleanupActive = false;
		state.tracked = 0;
		state.returnedObject = 0;
		state.returnedPickup = 0;
		state.previousOwned = false;
		state.previousAmmoWeapon = -1;
		state.previousAmmoType = -1;
		state.previousProjectileNear = false;
		state.previousHeldWeaponEntity = false;
		return;
	}
	++state.ticks;
	cleanupReturnedAncientTomahawk(ped, now);

	const Hash currentWeapon = GET_CURRENT_WEAPON(ped);
	// The hash-level current-weapon reader did not expose the Ancient Tomahawk in
	// Lexer's retained session. Rockstar also exposes the actual current weapon
	// entity; weapons.ymt and pickups.meta both bind this variant to the unique
	// w_melee_tomahawk02 model, so the live prop is an independent exact signal.
	const Entity currentWeaponEntity = invoke<Entity>(0x3B390A939AF0B5FC, ped, 0);
	const Hash currentWeaponEntityModel = currentWeaponEntity &&
		ENTITY::DOES_ENTITY_EXIST(currentWeaponEntity) ?
		ENTITY_MODEL(currentWeaponEntity) : 0;
	const bool heldWeaponEntity = currentWeaponEntityModel == state.model;
	const bool owned = HAS_WEAPON(ped, state.weapon);
	const int ammoWeapon = ancientTomahawkAmmoInWeapon(ped);
	const int ammoType = GET_PED_AMMO_BY_TYPE(ped, state.ammoType);
	if (owned) state.everOwned = true;

	const Vector3 pedPosition = ENTITY_COORDS(ped);
	const bool equipped = currentWeapon == state.weapon || heldWeaponEntity;
	// The previous implementation ran the projectile query plus complete object
	// and pickup-pool baselines whenever the player merely owned a charge. That
	// made this feature active while unarmed and caused the staged startup abort.
	// Observe the projectile lifecycle only while this weapon is equipped, was
	// equipped on the prior tick, or a throw is already armed.
	const bool monitorProjectile = state.armed || equipped ||
		state.previousWeapon == state.weapon || state.previousHeldWeaponEntity;
	// 60 m covers a thrown tomahawk's whole flight; Rockstar uses 10 m for a
	// dynamite stick it expects at its feet (coachrobberies_gang3.c:30224).
	const bool projectileNear = monitorProjectile &&
		ancientTomahawkProjectileNear(pedPosition, 60.0f);

	const bool held = equipped && (ammoWeapon > 0 || ammoType > 0);

	// Only baseline while we can still prove we are holding a charge. Doing it
	// unconditionally would absorb a tomahawk already stuck in a tree.
	const bool newlyEquipped = held && state.previousWeapon != state.weapon &&
		!state.previousHeldWeaponEntity;
	const bool chargeRestored = held &&
		(ammoWeapon > state.previousAmmoWeapon || ammoType > state.previousAmmoType);
	// A returned charge can make the held prop reappear while Rockstar is still
	// converting the thrown projectile into a loose object/pickup. Refreshing the
	// baseline here would bless that late duplicate as pre-existing and make it
	// undeletable for the rest of the cleanup window.
	if (!state.armed && !state.cleanupActive && held &&
		(newlyEquipped || chargeRestored))
		ancientTomahawkRefreshBaseline(ped, now);

	// ---- arming ----------------------------------------------------------
	// Primary: the ammo charge went to zero. Secondary reasons exist so that a
	// wrong primary can never make the whole chain unreachable again, and the
	// launch line always names which one fired.
	const char* armReason = nullptr;
	if (!state.armed) {
		if (state.previousAmmoWeapon > 0 && ammoWeapon == 0) armReason = "ammo-weapon-drop";
		else if (state.previousAmmoType > 0 && ammoType == 0) armReason = "ammo-type-drop";
		else if (state.previousOwned && !owned &&
			(currentWeapon == state.weapon || state.previousWeapon == state.weapon))
			armReason = "ownership-lost";
		else if (projectileNear && !state.previousProjectileNear) armReason = "projectile-seen";
	}
	if (armReason)
		beginAncientTomahawkThrow(ped, now, armReason, ammoWeapon, ammoType, owned, projectileNear);

	if (state.armed) {
		if (projectileNear) state.sawProjectile = true;

		std::vector<Object> objects;
		int attached = 0;
		int rawObjects = 0;
		ancientTomahawkScanObjects(ped, &objects, &attached, &rawObjects);

		// Adopt the nearest unbaselined tomahawk object as the projectile.
		if (!state.tracked || !ENTITY::DOES_ENTITY_EXIST(state.tracked)) {
			Object best = 0;
			float bestDistance = 0.0f;
			for (size_t i = 0; i < objects.size(); ++i) {
				if (state.baselineObjects.count(objects[i])) continue;
				const float distance = ancientTomahawkDistanceSquared(
					ENTITY_COORDS(objects[i]), pedPosition);
				if (!best || distance < bestDistance) { best = objects[i]; bestDistance = distance; }
			}
			if (best && best != state.tracked) {
				state.tracked = best;
				state.trackedMoved = false;
				state.trackedTopSpeed = 0.0f;
			}
		}

		bool collided = false;
		bool vanished = false;
		float speed = 0.0f;
		if (state.tracked) {
			if (!ENTITY::DOES_ENTITY_EXIST(state.tracked)) {
				vanished = true;
			} else {
				state.trackedPosition = ENTITY_COORDS(state.tracked);
				speed = ENTITY::GET_ENTITY_SPEED(state.tracked);
				if (speed > state.trackedTopSpeed) state.trackedTopSpeed = speed;
				if (speed > 3.0f) state.trackedMoved = true;
				collided = ENTITY::HAS_ENTITY_COLLIDED_WITH_ANYTHING(state.tracked) != 0;
			}
		}

		std::vector<Pickup> pickups;
		int rawPickups = 0;
		ancientTomahawkScanPickups(&pickups, &rawPickups);
		Pickup freshPickup = 0;
		for (size_t i = 0; i < pickups.size(); ++i)
			if (!state.baselinePickups.count(pickups[i])) { freshPickup = pickups[i]; break; }

		// Rockstar's own "thrown and no longer in flight" test: the projectile
		// query was satisfied and now is not (coachrobberies_gang3.c:30222-30224).
		// This is the signal that covers a tomahawk embedded in a tree without
		// depending on the object pool containing it at all.
		const bool projectileSettled = state.sawProjectile && !projectileNear;

		// Per-tick diagnostic, capped at 100 ms so one throw cannot flood the
		// file. Every impact term is printed separately and unaggregated.
		if (now - state.lastScanLogAt >= 100) {
			state.lastScanLogAt = now;
			std::ostringstream line;
			line << "scan armedMs=" << (now - state.launchedAt)
				<< " rawObjects=" << rawObjects
				<< " tomahawkObjects=" << objects.size() << " attached=" << attached
				<< " tracked=" << state.tracked
				<< " speed=" << std::fixed << std::setprecision(2) << speed
				<< " moved=" << (state.trackedMoved ? 1 : 0)
				<< " collided=" << (collided ? 1 : 0)
				<< " vanished=" << (vanished ? 1 : 0)
				<< " projNear=" << (projectileNear ? 1 : 0)
				<< " sawProjectile=" << (state.sawProjectile ? 1 : 0)
				<< " settled=" << (projectileSettled ? 1 : 0)
				<< " rawPickups=" << rawPickups
				<< " tomahawkPickups=" << pickups.size() << " freshPickup=" << freshPickup
				<< " owned=" << (owned ? 1 : 0)
				<< " ammoWeapon=" << ammoWeapon << " ammoType=" << ammoType;
			ancientTomahawkLog(GT_TRACE, line.str());
		}

		if (state.tracked && !vanished && (collided || (state.trackedMoved && speed < 0.5f))) {
			finishAncientTomahawkReturn(ped, now, state.trackedPosition,
				collided ? "object-collision" : "object-came-to-rest");
		} else if (freshPickup) {
			// A landed tomahawk becomes PICKUP_WEAPON_THROWN_TOMAHAWK_ANCIENT. Its
			// appearance is itself the impact event.
			const Object pickupObject = OBJECT::GET_PICKUP_OBJECT(freshPickup);
			state.returnedPickup = freshPickup;
			finishAncientTomahawkReturn(ped, now,
				pickupObject ? ENTITY_COORDS(pickupObject) : state.trackedPosition,
				"pickup-spawned");
		} else if (projectileSettled) {
			finishAncientTomahawkReturn(ped, now,
				state.tracked ? state.trackedPosition : pedPosition, "projectile-settled");
		} else if (vanished && state.trackedMoved) {
			finishAncientTomahawkReturn(ped, now, state.trackedPosition, "projectile-gone");
		}

		if (state.armed && now - state.launchedAt > 30000) {
			// Never degrade into a timed or despawn-driven regrant. Log and stop.
			std::ostringstream line;
			line << "no-signal-abort armedMs=" << (now - state.launchedAt)
				<< " tracked=" << state.tracked
				<< " sawProjectile=" << (state.sawProjectile ? 1 : 0)
				<< " ammoWeapon=" << ammoWeapon << " ammoType=" << ammoType
				<< " owned=" << (owned ? 1 : 0);
			ancientTomahawkLog(GT_WARN, line.str());
			state.armed = false;
			state.tracked = 0;
			state.sawProjectile = false;
		}
	} else {
		// Idle heartbeat. A silent log now proves the module is not running; a log
		// of nothing but idle lines proves the arming edge never fired, and the
		// ammo/owned/projNear columns say which candidate edge, if any, moved. The
		// heartbeat is deliberately read-only and never enumerates world pools.
		if (now - state.lastIdleLogAt >= 15000) {
			state.lastIdleLogAt = now;
			std::ostringstream line;
			line << "idle ticks=" << state.ticks
				<< " owned=" << (owned ? 1 : 0)
				<< " everOwned=" << (state.everOwned ? 1 : 0)
				<< " everArmed=" << (state.everArmed ? 1 : 0)
				<< " ammoWeapon=" << ammoWeapon
				<< " ammoType=" << ammoType
				<< " projNear=" << (projectileNear ? 1 : 0)
				<< " currentWeapon=" << currentWeapon
				<< " weaponEntity=" << currentWeaponEntity
				<< " weaponEntityModel=" << currentWeaponEntityModel
				<< " heldWeaponEntity=" << (heldWeaponEntity ? 1 : 0)
				<< " monitoring=" << (monitorProjectile ? 1 : 0)
				<< " equipped=" << (equipped ? 1 : 0)
				<< " baselineObjects=" << state.baselineObjects.size()
				<< " baselinePickups=" << state.baselinePickups.size();
			ancientTomahawkLog(GT_INFO, line.str());
		}
	}

	state.previousWeapon = currentWeapon;
	state.previousOwned = owned;
	state.previousAmmoWeapon = ammoWeapon;
	state.previousAmmoType = ammoType;
	state.previousProjectileNear = projectileNear;
	state.previousHeldWeaponEntity = heldWeaponEntity;
}
