// GameplayTweaks feature module: persist the owned saddle horse where the
// player left it across a complete game restart (#123).

struct HorsePersistenceState {
	bool loaded = false;
	bool valid = false;
	bool startupResolved = false;
	bool restoring = false;
	Hash model = 0;
	Vector3 position = {};
	float heading = 0.0f;
	DWORD restoreUntil = 0;
	DWORD stableSince = 0;
	DWORD nextRestoreAt = 0;
	DWORD nextSaveAt = 0;
};

static HorsePersistenceState g_horsePersistence;

static std::string horsePersistencePath() {
	return g_moduleDir + "\\GameplayTweaks.horse-persistence.dat";
}

static void horsePersistenceLog(GtLogLevel level, const std::string& message) {
	gtLog("horse-persist", level, message);
}

static bool horsePersistencePositionValid(Vector3 p) {
	return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z) &&
		std::fabs(p.x) < 10000.0f && std::fabs(p.y) < 10000.0f &&
		p.z > -500.0f && p.z < 2500.0f;
}

static float horsePersistenceDistanceSq(Vector3 a, Vector3 b) {
	const float x = a.x - b.x, y = a.y - b.y, z = a.z - b.z;
	return x * x + y * y + z * z;
}

static void loadHorsePersistence() {
	if (g_horsePersistence.loaded) return;
	g_horsePersistence.loaded = true;
	std::ifstream in(horsePersistencePath());
	std::string line;
	if (!std::getline(in, line)) return;
	std::replace(line.begin(), line.end(), ',', ' ');
	unsigned version = 0, model = 0;
	HorsePersistenceState saved;
	if (!(std::istringstream(line) >> version >> model >> saved.position.x >>
		saved.position.y >> saved.position.z >> saved.heading) || version != 1 ||
		!model || !horsePersistencePositionValid(saved.position)) {
		horsePersistenceLog(GT_WARN, "ignored invalid persisted state");
		return;
	}
	g_horsePersistence.model = (Hash)model;
	g_horsePersistence.position = saved.position;
	g_horsePersistence.heading = saved.heading;
	g_horsePersistence.valid = true;
}

static void saveHorsePersistence(Ped horse) {
	if (!horse || !ENTITY::DOES_ENTITY_EXIST(horse) ||
		PED::IS_PED_DEAD_OR_DYING(horse, TRUE) || ENTITY::IS_ENTITY_ATTACHED(horse))
		return;
	const Vector3 position = ENTITY_COORDS(horse);
	if (!horsePersistencePositionValid(position)) return;
	std::ofstream out(horsePersistencePath(), std::ios::trunc);
	out << "1," << (unsigned)ENTITY_MODEL(horse) << "," << std::fixed <<
		std::setprecision(3) << position.x << "," << position.y << "," <<
		position.z << "," << ENTITY_HEADING(horse) << "\n";
	g_horsePersistence.model = ENTITY_MODEL(horse);
	g_horsePersistence.position = position;
	g_horsePersistence.heading = ENTITY_HEADING(horse);
	g_horsePersistence.valid = true;
}

static void updateHorsePersistence(Player player, Ped playerPed, DWORD now,
	bool locked, bool mission) {
	loadHorsePersistence();
	if (GetPrivateProfileIntA("HorsePersistence", "Enabled", 1,
		g_iniPath.c_str()) == 0) return;
	const Ped horse = GET_OWNED_MOUNT(player);
	if (!horse || !ENTITY::DOES_ENTITY_EXIST(horse) || !playerPed || locked ||
		mission || PED::IS_PED_DEAD_OR_DYING(horse, TRUE)) return;

	if (!g_horsePersistence.startupResolved) {
		// Never move the player with a mounted horse, disturb an attached/hitched
		// entity, or apply coordinates saved for a different owned horse.
		if (GET_MOUNT(playerPed) == horse || ENTITY::IS_ENTITY_ATTACHED(horse) ||
			!g_horsePersistence.valid ||
			ENTITY_MODEL(horse) != g_horsePersistence.model) {
			g_horsePersistence.startupResolved = true;
			g_horsePersistence.nextSaveAt = now + 2000;
			horsePersistenceLog(GT_INFO, "startup restore skipped: unsafe or stale state");
			return;
		}
		g_horsePersistence.restoring = true;
		g_horsePersistence.restoreUntil = now + 10000;
		g_horsePersistence.nextRestoreAt = 0;
		horsePersistenceLog(GT_INFO, "startup restore armed");
	}

	if (g_horsePersistence.restoring) {
		const float distanceSq = horsePersistenceDistanceSq(ENTITY_COORDS(horse),
			g_horsePersistence.position);
		if (distanceSq <= 9.0f) {
			if (!g_horsePersistence.stableSince) g_horsePersistence.stableSince = now;
			if (now - g_horsePersistence.stableSince >= 2000) {
				g_horsePersistence.restoring = false;
				g_horsePersistence.startupResolved = true;
				g_horsePersistence.nextSaveAt = now + 2000;
				horsePersistenceLog(GT_INFO, "startup restore stable");
			}
		} else {
			g_horsePersistence.stableSince = 0;
			if (now >= g_horsePersistence.nextRestoreAt) {
				STREAMING::REQUEST_COLLISION_AT_COORD(g_horsePersistence.position.x,
					g_horsePersistence.position.y, g_horsePersistence.position.z);
				SET_COORDS_HEADING(horse, g_horsePersistence.position,
					g_horsePersistence.heading);
				g_horsePersistence.nextRestoreAt = now + 250;
			}
		}
		if (now >= g_horsePersistence.restoreUntil) {
			g_horsePersistence.restoring = false;
			g_horsePersistence.startupResolved = true;
			g_horsePersistence.nextSaveAt = now + 2000;
			horsePersistenceLog(GT_INFO, "startup restore window ended");
		}
		return; // never overwrite the persisted location during startup recovery
	}

	if (g_horsePersistence.startupResolved && now >= g_horsePersistence.nextSaveAt) {
		g_horsePersistence.nextSaveAt = now + 2000;
		saveHorsePersistence(horse);
	}
}
