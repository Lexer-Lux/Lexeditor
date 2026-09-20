// GitHub #64: remove only the four authored world mask props that duplicate
// Bandit rewards. The discoverable scenario, corpse, journal state, and the
// player's inventory are deliberately left alone.

struct WorldMaskSource {
	Hash model;
	Vector3 authoredPosition;
	const char* label;
};

static const WorldMaskSource kWorldMaskSources[] = {
	{ (Hash)1057717101,  { 2545.93f,   800.34f,   77.013f }, "Pig Mask" },
	{ (Hash)-1822543706, { -2904.945f, -254.221f, 187.3f },  "Pagan Skull Mask" },
	{ (Hash)-342606109,  { 2286.46f,  -727.94f,   42.98f },   "Cat Skull Mask" },
	{ (Hash)-987312756,  { -5151.3f, -2118.4f,    13.0f },   "Ram Skull Mask" },
};

struct WorldMaskSuppressionState {
	Entity entity = 0;
	bool suppressed = false;
};

static WorldMaskSuppressionState g_worldMaskStates[_countof(kWorldMaskSources)];
static DWORD g_worldMaskLastCheck = 0;
static DWORD g_worldMaskLastHeartbeat = 0;
static unsigned g_worldMaskTicks = 0;
static unsigned g_worldMaskScans = 0;
static unsigned g_worldMaskSuppressed = 0;

static float worldMaskDistanceSquared(const Vector3& a, const Vector3& b) {
	const float dx = a.x - b.x;
	const float dy = a.y - b.y;
	const float dz = a.z - b.z;
	return dx * dx + dy * dy + dz * dz;
}

void tickWorldCollectibleMaskRemoval(Ped player, DWORD now) {
	if (!player) return;
	++g_worldMaskTicks;

	// The discoverable script retains its spawned entity handle. Deleting the
	// object made DOES_ENTITY_EXIST fail and caused the script to recreate a new
	// takeable mask on its next tick. Keep the exact entity alive but hidden,
	// non-colliding, frozen and 50 m below its authored point instead.
	for (size_t i = 0; i < _countof(kWorldMaskSources); ++i) {
		WorldMaskSuppressionState& state = g_worldMaskStates[i];
		if (state.entity && !ENTITY::DOES_ENTITY_EXIST(state.entity)) {
			state.entity = 0;
			state.suppressed = false;
		} else if (state.entity && state.suppressed) {
			// Do not assume the one-time setter call remained authoritative. If
			// another script restores this same entity, resume the bounded scan and
			// re-establish the observable suppression postcondition.
			const Vector3 current = ENTITY::GET_ENTITY_COORDS(state.entity, true, false);
			if (ENTITY::IS_ENTITY_VISIBLE(state.entity) ||
				worldMaskDistanceSquared(current, kWorldMaskSources[i].authoredPosition) < 1600.0f) {
				state.suppressed = false;
			}
		}
	}

	const Vector3 playerPosition = ENTITY::GET_ENTITY_COORDS(player, true, false);
	bool needsScan = false;
	int nearbySources = 0;
	int activeSuppressions = 0;
	for (size_t i = 0; i < _countof(kWorldMaskSources); ++i) {
		const bool nearby = worldMaskDistanceSquared(
			playerPosition, kWorldMaskSources[i].authoredPosition) <= 22500.0f;
		if (nearby) ++nearbySources;
		if (g_worldMaskStates[i].suppressed) ++activeSuppressions;
		if (nearby && !g_worldMaskStates[i].suppressed) needsScan = true;
	}

	if (now - g_worldMaskLastHeartbeat >= 15000) {
		g_worldMaskLastHeartbeat = now;
		GtLogStream("world-masks", GT_INFO)
			<< "idle ticks=" << g_worldMaskTicks
			<< " nearby=" << nearbySources
			<< " scans=" << g_worldMaskScans
			<< " suppressions=" << g_worldMaskSuppressed
			<< " active=" << activeSuppressions << "\n";
	}
	if (!needsScan || now - g_worldMaskLastCheck < 25) return;
	g_worldMaskLastCheck = now;
	++g_worldMaskScans;

	int objects[4096] = {};
	const int count = worldGetAllObjects(objects, (int)_countof(objects));
	for (int i = 0; i < count; ++i) {
		const Object object = objects[i];
		if (!object || !ENTITY::DOES_ENTITY_EXIST(object)) continue;
		const Hash model = ENTITY::GET_ENTITY_MODEL(object);
		const Vector3 position = ENTITY::GET_ENTITY_COORDS(object, true, false);
		for (size_t sourceIndex = 0; sourceIndex < _countof(kWorldMaskSources); ++sourceIndex) {
			const WorldMaskSource& source = kWorldMaskSources[sourceIndex];
			WorldMaskSuppressionState& state = g_worldMaskStates[sourceIndex];
			if (state.suppressed) continue;
			// Model plus a tight authored-position boundary identifies the spawned
			// carriable prop without touching any scenario or corpse entity.
			if (model == source.model &&
				worldMaskDistanceSquared(position, source.authoredPosition) <= 9.0f) {
				ENTITY::SET_ENTITY_VISIBLE(object, FALSE);
				ENTITY::SET_ENTITY_COLLISION(object, FALSE, FALSE);
				ENTITY::FREEZE_ENTITY_POSITION(object, TRUE);
				ENTITY::SET_ENTITY_COORDS(object,
					source.authoredPosition.x, source.authoredPosition.y,
					source.authoredPosition.z - 50.0f, FALSE, FALSE, FALSE, FALSE);
				const Vector3 after = ENTITY::GET_ENTITY_COORDS(object, true, false);
				state.entity = object;
				state.suppressed = !ENTITY::IS_ENTITY_VISIBLE(object) &&
					worldMaskDistanceSquared(after, source.authoredPosition) >= 1600.0f;
				if (state.suppressed) ++g_worldMaskSuppressed;
				GtLogStream("world-masks", state.suppressed ? GT_INFO : GT_WARN)
					<< "suppress label=" << source.label
					<< " entity=" << object
					<< " before=" << position.x << "," << position.y << "," << position.z
					<< " after=" << after.x << "," << after.y << "," << after.z
					<< " visible=" << (ENTITY::IS_ENTITY_VISIBLE(object) ? 1 : 0)
					<< " ok=" << (state.suppressed ? 1 : 0) << "\n";
				break;
			}
		}
	}
}
