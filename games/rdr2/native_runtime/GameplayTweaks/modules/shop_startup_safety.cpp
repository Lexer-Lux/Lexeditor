// GitHub #114: let Rockstar's short_update acquire a nearby shop owner before
// any GameplayTweaks feature can mutate game state.  This module is read-only.
//
// Primary source: short_update.c func_312 calls func_1172/1173/1177 to request
// and start every Story shop-family script.  The shop record layout used here
// is the same one read there:
//   Global_1914319.f_3[type /*446*/].f_10  location
//   .f_11                                      position
//   .f_18                                      thread
//   .f_19                                      activation radius
//   .f_23                                      shopkeeper entity

// Fixed-size script arrays in decompiled source include a one-slot header.
// Global_1914319.f_3[type /*446*/] therefore begins at base + 3 + 1, not
// base + 3. The first observer omitted this header and read every field one
// global early.

static constexpr int kShopGlobal = 1914319;
static constexpr int kShopRecordsOffset = 3;
static constexpr int kShopRecordHeader = 1;
static constexpr int kShopRecordStride = 446;
static constexpr int kShopTypeCount = 35;
static constexpr int kShopLocationCount = 153;

static int shopStartupRecordBase(int type) {
	return kShopGlobal + kShopRecordsOffset + kShopRecordHeader +
		type * kShopRecordStride;
}

static const char* shopStartupScriptName(int type) {
	switch (type) {
		case 0: return "shop_doctor";
		case 1: return "shop_train_station";
		case 2: return "shop_post_office";
		case 3: return "shop_general";
		case 4: return "shop_fence";
		case 6: return "shop_gunsmith";
		case 7: return "shop_tailor";
		case 8: return "shop_barber";
		case 9: return "shop_horse_shop_sp";
		case 10: return "shop_butcher";
		case 11: return "shop_dynamic";
		case 12:
		case 13:
		case 14: return "shop_market";
		case 15: return "shop_bank";
		case 17: return "shop_bait";
		case 18: return "shop_trapper";
		case 19: return "shop_pearson";
		case 20: return "shop_hotel";
		case 21: return "shop_photo_studio";
		case 22: return "shop_newspaper_boy";
		case 30: return "shop_coach";
		case 33: return "shop_bartender";
		default: return nullptr;
	}
}

static float shopStartupGlobalFloat(int index) {
	return *reinterpret_cast<float*>(getGlobalPtr(index));
}

struct ShopStartupCandidate {
	int type = -1;
	int location = -1;
	int thread = 0;
	int shopkeeper = 0;
	int recordFlags = 0;
	int typeFlags = 0;
	int locationFlags = 0;
	Blip blip = 0;
	float distance = 0.0f;
	float radius = 0.0f;
	Vector3 position = {};
};

struct ShopStartupRuntimeState {
	bool recordsLogged = false;
	int validRecords = 0;
	int trackedType = -1;
	DWORD enteredAt = 0;
	DWORD nextHeartbeat = 0;
	DWORD nextAudit = 0;
	bool ownerLogged = false;
	bool retainedAreaValid = false;
	Vector3 retainedPosition = {};
	float retainedRadius = 0.0f;
};

static void logShopStartupRecord(int type, const Vector3& player,
	const char* phase) {
	const char* script = shopStartupScriptName(type);
	if (!script) return;
	const int record = shopStartupRecordBase(type);
	const int location = static_cast<int>(*getGlobalPtr(record + 10));
	const float x = shopStartupGlobalFloat(record + 11);
	const float y = shopStartupGlobalFloat(record + 12);
	const float z = shopStartupGlobalFloat(record + 13);
	const float radius = shopStartupGlobalFloat(record + 19);
	const int thread = static_cast<int>(*getGlobalPtr(record + 18));
	const Blip blip = static_cast<Blip>(*getGlobalPtr(record + 14));
	const bool active = thread && SCRIPTS::IS_THREAD_ACTIVE(thread, false);
	float distance = -1.0f;
	if (std::isfinite(x) && std::isfinite(y) && std::isfinite(z)) {
		const float dx = player.x - x;
		const float dy = player.y - y;
		const float dz = player.z - z;
		distance = sqrtf(dx * dx + dy * dy + dz * dz);
	}
	std::ostringstream line;
	line << "phase=" << (phase ? phase : "record")
		<< " type=" << type
		<< " script=" << script
		<< " location=" << location
		<< " pos=" << x << "," << y << "," << z
		<< " radius=" << radius
		<< " distance=" << distance
		<< " thread=" << thread
		<< " active=" << (active ? 1 : 0)
		<< " refs=" << SCRIPTS::_GET_NUMBER_OF_REFERENCES_OF_SCRIPT_WITH_NAME_HASH(joaat(script))
		<< " blip=" << blip
		<< " blipExists=" << (blip && MAP::DOES_BLIP_EXIST(blip) ? 1 : 0)
		<< " recordFlags=0x" << std::hex
		<< static_cast<int>(*getGlobalPtr(record + 5));
	gtLog("shop-startup", GT_INFO, line.str());
}

static void logShopStartupRecordsOnce(Ped ped,
	ShopStartupRuntimeState& state) {
	if (state.recordsLogged || !ped) return;
	state.recordsLogged = true;
	const Vector3 player = ENTITY_COORDS(ped);
	for (int type = 0; type < kShopTypeCount; ++type)
		logShopStartupRecord(type, player, "pre-feature-records");
}

static bool nearestShopStartupCandidate(Ped ped, ShopStartupCandidate* out) {
	if (!ped || !out) return false;
	const Vector3 player = ENTITY_COORDS(ped);
	float nearestSq = 3.402823466e+38F;
	ShopStartupCandidate nearest = {};
	for (int type = 0; type < kShopTypeCount; ++type) {
		if (!shopStartupScriptName(type)) continue;
		const int record = shopStartupRecordBase(type);
		const int location = static_cast<int>(*getGlobalPtr(record + 10));
		const float radius = shopStartupGlobalFloat(record + 19);
		if (location < 0 || location >= kShopLocationCount || !std::isfinite(radius) ||
			radius <= 0.0f || radius > 1000.0f) continue;
		const float x = shopStartupGlobalFloat(record + 11);
		const float y = shopStartupGlobalFloat(record + 12);
		const float z = shopStartupGlobalFloat(record + 13);
		if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) continue;
		const float dx = player.x - x;
		const float dy = player.y - y;
		const float dz = player.z - z;
		const float distanceSq = dx * dx + dy * dy + dz * dz;
		if (distanceSq > radius * radius || distanceSq >= nearestSq) continue;
		nearestSq = distanceSq;
		nearest.type = type;
		nearest.location = location;
		nearest.thread = static_cast<int>(*getGlobalPtr(record + 18));
		nearest.shopkeeper = static_cast<int>(*getGlobalPtr(record + 23));
		nearest.recordFlags = static_cast<int>(*getGlobalPtr(record + 5));
		nearest.typeFlags = static_cast<int>(*getGlobalPtr(
			kShopGlobal + 16970 + 1 + type));
		nearest.locationFlags = static_cast<int>(*getGlobalPtr(
			kShopGlobal + 15614 + 1 + location));
		nearest.blip = static_cast<Blip>(*getGlobalPtr(record + 14));
		nearest.distance = sqrtf(distanceSq);
		nearest.radius = radius;
		nearest.position = { x, y, z };
	}
	if (nearest.type < 0) return false;
	*out = nearest;
	return true;
}

static void logShopStartupState(const ShopStartupCandidate& shop,
	const char* phase, DWORD elapsed) {
	const int worldFlags = static_cast<int>(*getGlobalPtr(1935630));
	const int transition = static_cast<int>(*getGlobalPtr(1914319 + 17370));
	const int sharedShopBusy = static_cast<int>(*getGlobalPtr(1395601 + 1));
	const int duel = static_cast<int>(*getGlobalPtr(1935630 + 24));
	const bool active = shop.thread &&
		SCRIPTS::IS_THREAD_ACTIVE(shop.thread, false);
	std::ostringstream line;
	line << "phase=" << phase
		<< " type=" << shop.type
		<< " script=" << shopStartupScriptName(shop.type)
		<< " location=" << shop.location
		<< " distance=" << shop.distance
		<< " radius=" << shop.radius
		<< " thread=" << shop.thread
		<< " active=" << (active ? 1 : 0)
		<< " refs=" << SCRIPTS::_GET_NUMBER_OF_REFERENCES_OF_SCRIPT_WITH_NAME_HASH(
			joaat(shopStartupScriptName(shop.type)))
		<< " shopkeeper=" << shop.shopkeeper
		<< " blip=" << shop.blip
		<< " blipExists=" << (shop.blip && MAP::DOES_BLIP_EXIST(shop.blip) ? 1 : 0)
		<< " recordFlags=0x" << std::hex << shop.recordFlags
		<< " typeFlags=0x" << shop.typeFlags
		<< " locationFlags=0x" << shop.locationFlags
		<< " worldBlock=" << ((worldFlags & 2097152) ? 1 : 0)
		<< " transition=" << std::dec << transition
		<< " sharedBusy=" << sharedShopBusy
		<< " duel=" << duel
		<< " elapsedMs=" << elapsed;
	gtLog("shop-startup", active ? GT_INFO : GT_WARN, line.str());
}

static void auditShopStartupState(Ped ped, DWORD now,
	ShopStartupRuntimeState& state) {
	if (!ped) return;
	logShopStartupRecordsOnce(ped, state);
	if (state.nextAudit && now < state.nextAudit) return;
	state.nextAudit = now + 1000;

	int validRecords = 0;
	int liveThreads = 0;
	int liveBlips = 0;
	int queued[8] = {};
	for (int slot = 0; slot < 8; ++slot)
		queued[slot] = static_cast<int>(*getGlobalPtr(
			kShopGlobal + 15927 + 1 + slot));
	for (int type = 0; type < kShopTypeCount; ++type) {
		if (!shopStartupScriptName(type)) continue;
		const int record = shopStartupRecordBase(type);
		const int location = static_cast<int>(*getGlobalPtr(record + 10));
		const float radius = shopStartupGlobalFloat(record + 19);
		if (location >= 0 && location < kShopLocationCount &&
			std::isfinite(radius) && radius > 0.0f && radius <= 1000.0f)
			++validRecords;
		const int thread = static_cast<int>(*getGlobalPtr(record + 18));
		if (thread && SCRIPTS::IS_THREAD_ACTIVE(thread, false)) ++liveThreads;
		const Blip blip = static_cast<Blip>(*getGlobalPtr(record + 14));
		if (blip && MAP::DOES_BLIP_EXIST(blip)) ++liveBlips;
	}
	state.validRecords = validRecords;
	ShopStartupCandidate nearest = {};
	const bool nearby = nearestShopStartupCandidate(ped, &nearest);
	std::ostringstream line;
	line << "summary validRecords=" << validRecords
		<< " liveThreads=" << liveThreads
		<< " liveBlips=" << liveBlips
		<< " shortUpdateRefs=" << SCRIPT_REFS(joaat("short_update"))
		<< " shopControllerRefs=" << SCRIPT_REFS(joaat("shop_controller"))
		<< " freeStacks6005=" << MISC::GET_NUMBER_OF_FREE_STACKS_OF_THIS_SIZE(6005)
		<< " worldBlock=" << ((static_cast<int>(*getGlobalPtr(1935630)) & 2097152) ? 1 : 0)
		<< " transition=" << static_cast<int>(*getGlobalPtr(kShopGlobal + 17370))
		<< " sharedBusy=" << static_cast<int>(*getGlobalPtr(1395601 + 1))
		<< " queued=";
	for (int slot = 0; slot < 8; ++slot) {
		if (slot) line << ",";
		line << queued[slot];
	}
	line << " nearby=" << (nearby ? 1 : 0);
	if (nearby) {
		line << " nearestType=" << nearest.type
			<< " nearestScript=" << shopStartupScriptName(nearest.type)
			<< " nearestDistance=" << nearest.distance
			<< " nearestRadius=" << nearest.radius
			<< " nearestThread=" << nearest.thread
			<< " nearestBlip=" << nearest.blip;
	}
	gtLog("shop-startup", validRecords > 0 ? GT_INFO : GT_WARN, line.str());
}

static bool protectShopOwnerAcquisition(Ped ped, DWORD now,
	ShopStartupRuntimeState& state) {
	auditShopStartupState(ped, now, state);
	// An uninitialized shop table is not permission to run mod features. It is
	// the strongest possible ownership failure: short_update has no authored
	// record from which it can create map icons or start a shop. Keep every
	// GameplayTweaks update stopped until the table exists.
	if (state.validRecords == 0) return true;

	ShopStartupCandidate shop = {};
	if (!nearestShopStartupCandidate(ped, &shop)) {
		if (state.retainedAreaValid) {
			const Vector3 player = ENTITY_COORDS(ped);
			const float dx = player.x - state.retainedPosition.x;
			const float dy = player.y - state.retainedPosition.y;
			const float dz = player.z - state.retainedPosition.z;
			const float distanceSq = dx * dx + dy * dy + dz * dz;
			if (distanceSq <= state.retainedRadius * state.retainedRadius) {
				// short_update streams shop records in and out while the player
				// remains inside overlapping shop regions. Keep the last verified
				// authored area; a missing record for one frame is not an exit.
				return true;
			}
		}
		state.trackedType = -1;
		state.enteredAt = 0;
		state.nextHeartbeat = 0;
		state.ownerLogged = false;
		state.retainedAreaValid = false;
		state.retainedRadius = 0.0f;
		return false;
	}
	state.retainedAreaValid = true;
	state.retainedPosition = shop.position;
	state.retainedRadius = shop.radius;
	if (state.trackedType != shop.type) {
		state.trackedType = shop.type;
		state.enteredAt = now;
		state.nextHeartbeat = 0;
		state.ownerLogged = false;
		logShopStartupState(shop, "entered", 0);
	}
	const DWORD elapsed = now - state.enteredAt;
	const bool active = shop.thread &&
		SCRIPTS::IS_THREAD_ACTIVE(shop.thread, false);
	if (active) {
		if (!state.ownerLogged) {
			logShopStartupState(shop, "owner-active", elapsed);
			state.ownerLogged = true;
		}
		// A live owner is only the start of Rockstar's shop transaction. The
		// returned trace proved that releasing GameplayTweaks here let feature
		// updates run before the shop became usable, after which the owner died.
		// Keep the read-only containment for the complete nearby-shop session.
		return true;
	}
	if (!state.nextHeartbeat || now >= state.nextHeartbeat) {
		state.nextHeartbeat = now + 1000;
		logShopStartupState(shop, "contained", elapsed);
	}
	// Do not let unrelated GameplayTweaks updates run while Rockstar has an
	// authored nearby shop record. This is a containment boundary, not a
	// fabricated shop repair. Story remains free to load, start, and run its own
	// shop transaction without an overlapping GameplayTweaks feature update.
	return true;
}
