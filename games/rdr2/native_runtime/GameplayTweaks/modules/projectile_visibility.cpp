// GameplayTweaks feature module: visible firearm tracers (#16).
//
// Draw an adjustable luminous world-space streak along the deliberately slowed
// firearm path. The game's weapon records still own their vanilla tracer hashes;
// [ProjectileVisibility] Enabled simply controls this added renderer and leaves
// those records alone. Do not replay `core/bullet_tracer`: that would add a
// second copy of the same smoke-like trail rather than restore vanilla.

struct VisibleProjectile {
	Vector3 origin;
	Vector3 direction;
	float segmentDistance;
	float nearestDistance;
	DWORD createdAt;
};

static std::vector<VisibleProjectile> g_visibleProjectiles;

struct PendingVisibleShot {
	Vector3 origin;
	DWORD firedAt;
};

struct ShooterImpactState {
	bool initialized = false;
	Vector3 lastImpact = {};
	std::vector<PendingVisibleShot> pending;
};

static std::unordered_map<Ped, ShooterImpactState> g_shooterImpacts;

struct ProjectileRenderSettings {
	bool enabled = true;
	float size = 0.05f;
	float opacity = 1.0f;
	float brightness = 8.0f;
	int red = 255;
	int green = 92;
	int blue = 18;
	float tailLength = 1.5f;
	int tailSegments = 7;
	float maxDistance = 250.0f;
	float lightRange = 1.8f;
};

static ProjectileRenderSettings projectileRenderSettings(DWORD now) {
	static ProjectileRenderSettings settings;
	static DWORD nextReadAt = 0;
	if (nextReadAt && now < nextReadAt) return settings;
	nextReadAt = now + 1000;
	settings.enabled = readB("ProjectileVisibility", "Enabled", true);
	settings.size = (std::max)(0.005f, (std::min)(0.50f,
		readF("ProjectileVisibility", "SizeMeters", 0.05f)));
	settings.opacity = (std::max)(0.0f, (std::min)(1.0f,
		readF("ProjectileVisibility", "Opacity", 1.0f)));
	settings.brightness = (std::max)(0.0f, (std::min)(100.0f,
		readF("ProjectileVisibility", "Brightness", 8.0f)));
	settings.red = (std::max)(0, (std::min)(255, (int)GetPrivateProfileIntA(
		"ProjectileVisibility", "Red", 255, g_iniPath.c_str())));
	settings.green = (std::max)(0, (std::min)(255, (int)GetPrivateProfileIntA(
		"ProjectileVisibility", "Green", 92, g_iniPath.c_str())));
	settings.blue = (std::max)(0, (std::min)(255, (int)GetPrivateProfileIntA(
		"ProjectileVisibility", "Blue", 18, g_iniPath.c_str())));
	settings.tailLength = (std::max)(0.10f, (std::min)(10.0f,
		readF("ProjectileVisibility", "TailLengthMeters", 1.5f)));
	settings.tailSegments = (std::max)(2, (std::min)(16, (int)GetPrivateProfileIntA(
		"ProjectileVisibility", "TailSegments", 7, g_iniPath.c_str())));
	settings.maxDistance = (std::max)(5.0f, (std::min)(500.0f,
		readF("ProjectileVisibility", "MaxDistanceMeters", 250.0f)));
	settings.lightRange = (std::max)(0.10f, (std::min)(20.0f,
		readF("ProjectileVisibility", "LightRangeMeters", 1.8f)));
	return settings;
}

static float projectileVectorLength(Vector3 value) {
	return sqrtf(value.x * value.x + value.y * value.y + value.z * value.z);
}

static bool projectileMuzzleOrigin(Entity weaponEntity, Vector3* origin) {
	if (!origin) return false;

	// GET_CURRENT_PED_WEAPON_ENTITY_INDEX gives the actual in-hand weapon prop.
	// Rockstar's own mounted-gun scripts resolve `Gun_Muzzle` on that entity and
	// use its local +X axis as the barrel direction (ambush_exc_wagon_bomb.c
	// func_508/509).  The old implementation used right-hand bone 7966 plus the
	// gameplay-camera rotation; that was the visible eye-origin/parallax trail.
	if (!weaponEntity || !ENTITY::DOES_ENTITY_EXIST(weaponEntity)) return false;

	const int muzzleBone = ENTITY::GET_ENTITY_BONE_INDEX_BY_NAME(weaponEntity, "Gun_Muzzle");
	if (muzzleBone < 0) return false;
	const Vector3 muzzle = ENTITY::GET_WORLD_POSITION_OF_ENTITY_BONE(weaponEntity, muzzleBone);
	const Vector3 weaponOrigin = ENTITY::GET_ENTITY_COORDS(weaponEntity, TRUE, FALSE);
	const Vector3 weaponForward = ENTITY::GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(
		weaponEntity, 1.0f, 0.0f, 0.0f);
	Vector3 barrel = {
		weaponForward.x - weaponOrigin.x,
		weaponForward.y - weaponOrigin.y,
		weaponForward.z - weaponOrigin.z
	};
	const float length = projectileVectorLength(barrel);
	if (length < 0.001f) return false;
	barrel = { barrel.x / length, barrel.y / length, barrel.z / length };

	// Begin just beyond the muzzle so the luminous head never appears inside
	// the shooter's hand/face in close third-person or first-person cameras.
	*origin = {
		muzzle.x + barrel.x * 0.10f,
		muzzle.y + barrel.y * 0.10f,
		muzzle.z + barrel.z * 0.10f
	};
	return true;
}

static void clearVisibleProjectiles() {
	g_visibleProjectiles.clear();
	g_shooterImpacts.clear();
}

static float projectileDistanceSquared(Vector3 a, Vector3 b) {
	const float x = a.x - b.x;
	const float y = a.y - b.y;
	const float z = a.z - b.z;
	return x * x + y * y + z * z;
}

static float projectileNearestDistanceToCamera(Vector3 origin, Vector3 direction,
	float segmentDistance) {
	const Vector3 camera = CAM::GET_GAMEPLAY_CAM_COORD();
	const Vector3 delta = { camera.x - origin.x, camera.y - origin.y, camera.z - origin.z };
	const float along = delta.x * direction.x + delta.y * direction.y + delta.z * direction.z;
	return (std::max)(0.0f, (std::min)(segmentDistance, along));
}

static void updateProjectileVisibility(Ped ped, DWORD now) {
	const ProjectileRenderSettings settings = projectileRenderSettings(now);
	// Enabled=0 removes only our added renderer, leaving Rockstar's preserved
	// weapon-data tracer as the vanilla path. Mode=off remains a legacy alias.
	if (!settings.enabled ||
		(g_projectileVisibilityMode != 2 && g_projectileVisibilityMode != 4)) {
		clearVisibleProjectiles();
		return;
	}

	static std::unordered_map<Ped, DWORD> lastShot;
	static std::unordered_map<Ped, Entity> lastMuzzleWeapon;
	int peds[160] = {};
	const int count = sharedWorldPedSnapshot(peds, 160);
	for (int p = 0; p < count; ++p) {
		const Ped shooter = peds[p];
		if (!shooter || !ENTITY::DOES_ENTITY_EXIST(shooter) ||
			ENTITY::IS_ENTITY_DEAD(shooter) || !PED::IS_PED_SHOOTING(shooter))
			continue;
		if (shooter != ped && !PED::IS_PED_IN_COMBAT(shooter, ped)) continue;
		const Hash weapon = GET_CURRENT_WEAPON(shooter);
		if (!casingItemForWeapon(weapon)) continue; // firearms only; never thrown weapons
		if (now - lastShot[shooter] < 75) continue;

		// Rockstar queries indices 0 and 1 together in Story scripts. They are the
		// two current held-weapon entities, so alternating distinct entities keeps
		// dual-wield shots on alternating real muzzles instead of pinning every
		// trail to the primary hand. A single held gun simply resolves index 0.
		const Entity weapon0 = WEAPON::GET_CURRENT_PED_WEAPON_ENTITY_INDEX(shooter, 0);
		const Entity weapon1 = WEAPON::GET_CURRENT_PED_WEAPON_ENTITY_INDEX(shooter, 1);
		Entity weaponEntity = weapon0;
		if (weapon1 && weapon1 != weapon0 && ENTITY::DOES_ENTITY_EXIST(weapon1)) {
			weaponEntity = lastMuzzleWeapon[shooter] == weapon0 ? weapon1 : weapon0;
		}
		Vector3 origin = {};
		if (!projectileMuzzleOrigin(weaponEntity, &origin)) continue;
		lastMuzzleWeapon[shooter] = weaponEntity;
		lastShot[shooter] = now;

		// Do not manufacture a trajectory from the weapon prop's transform. NPC
		// aim, dispersion and animation can all make that axis differ wildly from
		// the bullet Rockstar actually fired. Queue the real muzzle and wait for
		// GET_PED_LAST_WEAPON_IMPACT_COORD to publish a fresh endpoint.
		ShooterImpactState& impact = g_shooterImpacts[shooter];
		if (!impact.initialized) {
			Vector3 baseline = {};
			if (WEAPON::GET_PED_LAST_WEAPON_IMPACT_COORD(shooter, &baseline))
				impact.lastImpact = baseline;
			impact.initialized = true;
			// The first observed shot has no trustworthy before-value. Drop it rather
			// than mistaking an older impact for this shot.
			continue;
		}
		impact.pending.push_back({ origin, now });
	}

	// Resolve queued shots only from a changed Rockstar impact coordinate. The
	// oldest live muzzle owns the next changed endpoint; rapid-fire queues remain
	// ordered. A shot that produces no readable impact expires silently instead
	// of drawing the incorrect barrel-axis tracer reported in-game.
	for (auto it = g_shooterImpacts.begin(); it != g_shooterImpacts.end();) {
		const Ped shooter = it->first;
		ShooterImpactState& impact = it->second;
		if (!shooter || !ENTITY::DOES_ENTITY_EXIST(shooter)) {
			it = g_shooterImpacts.erase(it);
			continue;
		}
		while (!impact.pending.empty() && now - impact.pending.front().firedAt > 500)
			impact.pending.erase(impact.pending.begin());

		Vector3 endpoint = {};
		const bool hasEndpoint =
			WEAPON::GET_PED_LAST_WEAPON_IMPACT_COORD(shooter, &endpoint) != 0;
		const bool changed = hasEndpoint &&
			projectileDistanceSquared(endpoint, impact.lastImpact) > 0.0025f;
		if (changed) {
			impact.lastImpact = endpoint;
			if (!impact.pending.empty()) {
				const Vector3 origin = impact.pending.front().origin;
				impact.pending.erase(impact.pending.begin());
				Vector3 direction = {
					endpoint.x - origin.x,
					endpoint.y - origin.y,
					endpoint.z - origin.z
				};
				const float distance = projectileVectorLength(direction);
				if (distance > 0.50f) {
					direction = { direction.x / distance, direction.y / distance,
						direction.z / distance };
					const float segmentDistance = (std::min)(settings.maxDistance, distance);
					g_visibleProjectiles.push_back({ origin, direction, segmentDistance,
						projectileNearestDistanceToCamera(origin, direction, segmentDistance), now });
				}
			}
		}
		++it;
	}

	for (int i = (int)g_visibleProjectiles.size() - 1; i >= 0; --i) {
		VisibleProjectile& projectile = g_visibleProjectiles[i];
		// #16/#116: impact-synchronized visibility aid, not a simulated projectile.
		// Keep one short dash on the confirmed muzzle->impact segment for 100 ms.
		if (now - projectile.createdAt > 100) {
			g_visibleProjectiles.erase(g_visibleProjectiles.begin() + i);
			continue;
		}
		const float pointDistance = (std::max)(0.0f,
			(std::min)(projectile.segmentDistance, projectile.nearestDistance));
		const Vector3 nearest = {
			projectile.origin.x + projectile.direction.x * pointDistance,
			projectile.origin.y + projectile.direction.y * pointDistance,
			projectile.origin.z + projectile.direction.z * pointDistance
		};
		if (g_projectileVisibilityMode == 4) {
			const float dashLength = (std::min)(settings.tailLength, projectile.segmentDistance);
			const float maxStart = (std::max)(0.0f, projectile.segmentDistance - dashLength);
			const float startDistance = (std::max)(0.0f,
				(std::min)(maxStart, pointDistance - dashLength * 0.5f));
			for (int segment = 0; segment < settings.tailSegments; ++segment) {
				const float fraction = segment / (float)(settings.tailSegments - 1);
				const float along = startDistance + dashLength * fraction;
				const Vector3 streak = {
					projectile.origin.x + projectile.direction.x * along,
					projectile.origin.y + projectile.direction.y * along,
					projectile.origin.z + projectile.direction.z * along
				};
				const float edge = fabsf(fraction - 0.5f) * 2.0f;
				const float size = settings.size * (1.15f - 0.45f * edge);
				const int alpha = (std::max)(0, (std::min)(255,
					(int)((245.0f - 120.0f * edge) * settings.opacity)));
				GRAPHICS::_DRAW_MARKER(0x94FDAE17, streak.x, streak.y, streak.z,
					0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
					size, size, size, settings.red, settings.green, settings.blue,
					alpha, FALSE, FALSE, 2, FALSE, nullptr, nullptr, FALSE);
			}
		} else {
			GRAPHICS::_DRAW_MARKER(0x94FDAE17, nearest.x, nearest.y, nearest.z,
				0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
				settings.size, settings.size, settings.size,
				settings.red, settings.green, settings.blue,
				(int)(255.0f * settings.opacity), FALSE, FALSE, 2, FALSE,
				nullptr, nullptr, FALSE);
		}
		if (settings.brightness > 0.0f)
			GRAPHICS::DRAW_LIGHT_WITH_RANGE(nearest.x, nearest.y, nearest.z,
				settings.red, settings.green, settings.blue,
				settings.lightRange, settings.brightness);
	}

}
