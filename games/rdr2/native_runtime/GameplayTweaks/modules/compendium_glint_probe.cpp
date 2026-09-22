// GitHub #85: read-only compendium discovery probe.
//
// The animal observed getter is documented, but the equivalent per-entry
// readback for herbs, horses, weapons, and equipment is not.  Do not turn a
// category total into a per-object guess: this probe records the engine's raw
// answers for a target under the reticle so runtime evidence can establish the
// correct predicate for every requested compendium family before glints ship.

static bool g_compendiumGlintProbeEnabled = false;
static bool g_compendiumGlintProbeKeyWasDown = false;
static unsigned int g_compendiumGlintProbeCapture = 0;

static void loadCompendiumGlintProbeConfig() {
	g_compendiumGlintProbeEnabled = GetPrivateProfileIntA("CompendiumGlintProbe",
		"Enabled", 0, g_iniPath.c_str()) != 0;
}

static void initializeCompendiumGlintProbe() {
	g_compendiumGlintProbeKeyWasDown = false;
	g_compendiumGlintProbeCapture = 0;
	// #126: the probe now writes to the unified GameplayTweaks.log under
	// subsystem "glint". One gtLog call per record, so a record can never be
	// half-written.
	gtLog("glint", GT_INFO, "# GitHub #85 read-only compendium probe");
	gtLog("glint", GT_INFO, "# Aim at the requested world target and press F10 once.");
	gtLog("glint", GT_INFO, "# No COMPENDIUM_* setter or progress write is called.");
}

static void logCompendiumUnlockProbe(const char* label, Hash value) {
	const bool unlocked = value && invoke<BOOL>(0xC4B660C7B6040E75, value) != 0;
	const bool visible = value && invoke<BOOL>(0x8588A14B75AF096B, value) != 0;
	std::ostringstream log;
	log << label << "=0x" << std::hex << (unsigned int)value << std::dec
		<< " unlock_unlocked=" << (unlocked ? 1 : 0)
		<< " unlock_visible=" << (visible ? 1 : 0);
	gtLog("glint", GT_INFO, log.str());
}

static void logCompendiumCategoryCensus() {
	static const char* categories[] = {
		"ANIMALS", "FISH", "HERBS", "HORSES", "WEAPONS", "EQUIPMENT"
	};
	for (const char* name : categories) {
		const Hash category = joaat(name);
		const int discovered = invoke<int>(0x729D52F61A5A9E22, category);
		std::ostringstream log;
		log << "category name=" << name << " hash=0x" << std::hex
			<< (unsigned int)category << std::dec
			<< " discovered_entries=" << discovered;
		gtLog("glint", GT_INFO, log.str());
	}
}

static void logCompendiumPed(const char* label, Ped ped,
	const Vector3& playerAt) {
	if (!ped || !ENTITY::DOES_ENTITY_EXIST(ped)) {
		gtLog("glint", GT_INFO, std::string(label) + " ped=none");
		return;
	}
	std::ostringstream log;
	const Vector3 at = ENTITY_COORDS(ped);
	const float dx = at.x - playerAt.x;
	const float dy = at.y - playerAt.y;
	const float dz = at.z - playerAt.z;
	const Hash model = ENTITY_MODEL(ped);
	const Hash animalType = ENTITY::_GET_PED_ANIMAL_TYPE(ped);
	const Hash shortDescription = invoke<Hash>(0x6C5E5D48E48B4C65, ped);
	const bool observed = invoke<BOOL>(0x23B5E9C5160BC04F, ped) != 0;
	const Hash animalCategory = joaat("ANIMALS");
	const Hash horseCategory = joaat("HORSES");
	const Hash animalSubcategory = invoke<Hash>(0x9B657550DF55EC96,
		animalCategory, ped);
	const Hash horseSubcategory = invoke<Hash>(0x9B657550DF55EC96,
		horseCategory, ped);
	const int animalPedEntry = invoke<int>(0x1CFA0219D8E1CF25,
		animalCategory, ped);
	const int horsePedEntry = invoke<int>(0x1CFA0219D8E1CF25,
		horseCategory, ped);
	const int animalStatEntry = invoke<int>(0x66EC938394D76C85,
		animalCategory, animalType);
	const int horseStatEntry = invoke<int>(0x66EC938394D76C85,
		horseCategory, animalType);
	log << label << " ped=" << ped << " model=0x" << std::hex
		<< (unsigned int)model << " animal_type=0x" << (unsigned int)animalType
		<< " short_description=0x" << (unsigned int)shortDescription
		<< " animal_subcategory=0x" << (unsigned int)animalSubcategory
		<< " horse_subcategory=0x" << (unsigned int)horseSubcategory
		<< std::dec << " distance=" << sqrtf(dx * dx + dy * dy + dz * dz)
		<< " human=" << (PED::IS_PED_HUMAN(ped) ? 1 : 0)
		<< " horse=" << (invoke<BOOL>(0x772A1969F649E902, model) ? 1 : 0)
		<< " observed=" << (observed ? 1 : 0)
		<< " animal_ped_entry=" << animalPedEntry
		<< " horse_ped_entry=" << horsePedEntry
		<< " animal_stat_entry=" << animalStatEntry
		<< " horse_stat_entry=" << horseStatEntry;
	gtLog("glint", GT_INFO, log.str());
	logCompendiumUnlockProbe("ped_model", model);
	logCompendiumUnlockProbe("ped_animal_type", animalType);
	logCompendiumUnlockProbe("ped_short_description", shortDescription);
}

static void logCompendiumEntity(Entity entity, const Vector3& playerAt) {
	if (!entity || !ENTITY::DOES_ENTITY_EXIST(entity)) {
		gtLog("glint", GT_INFO, "aimed entity=none");
		return;
	}
	Hash discoverableType = 0;
	const Hash discoverableName = invoke<Hash>(0x0139637A3BFF8B6D, entity,
		&discoverableType);
	const Hash model = ENTITY_MODEL(entity);
	const Vector3 at = ENTITY_COORDS(entity);
	const float dx = at.x - playerAt.x;
	const float dy = at.y - playerAt.y;
	const float dz = at.z - playerAt.z;
	std::ostringstream log;
	log << "aimed entity=" << entity << " model=0x" << std::hex
		<< (unsigned int)model << " discoverable_name=0x"
		<< (unsigned int)discoverableName << " discoverable_type=0x"
		<< (unsigned int)discoverableType << std::dec
		<< " distance=" << sqrtf(dx * dx + dy * dy + dz * dz)
		<< " is_ped=" << (ENTITY::IS_ENTITY_A_PED(entity) ? 1 : 0)
		<< " is_object=" << (ENTITY::IS_ENTITY_AN_OBJECT(entity) ? 1 : 0);
	gtLog("glint", GT_INFO, log.str());
	logCompendiumUnlockProbe("aimed_model", model);
	logCompendiumUnlockProbe("aimed_discoverable_name", discoverableName);
	logCompendiumUnlockProbe("aimed_discoverable_type", discoverableType);
	if (ENTITY::IS_ENTITY_A_PED(entity))
		logCompendiumPed("aimed", (Ped)entity, playerAt);
}

static void logCompendiumWeapons(Ped playerPed) {
	static const int slots[] = { 0, 1, 2, 3, 7, 8, 9, 10 };
	for (int slot : slots) {
		Hash weapon = 0;
		const bool present = WEAPON::GET_CURRENT_PED_WEAPON(playerPed, &weapon,
			TRUE, slot, FALSE) != 0;
		const int weaponEntry = invoke<int>(0x66EC938394D76C85,
			joaat("WEAPONS"), weapon);
		const int equipmentEntry = invoke<int>(0x66EC938394D76C85,
			joaat("EQUIPMENT"), weapon);
		std::ostringstream log;
		log << "weapon slot=" << slot << " present=" << (present ? 1 : 0)
			<< " hash=0x" << std::hex << (unsigned int)weapon << std::dec
			<< " weapon_entry=" << weaponEntry
			<< " equipment_entry=" << equipmentEntry;
		gtLog("glint", GT_INFO, log.str());
		if (weapon) logCompendiumUnlockProbe("weapon_hash", weapon);
	}
}

static void captureCompendiumGlintProbe(Ped playerPed) {
	const Vector3 playerAt = ENTITY_COORDS(playerPed);
	std::ostringstream header;
	header << "=== capture " << ++g_compendiumGlintProbeCapture
		<< " player=" << playerPed << " xyz=" << playerAt.x
		<< "," << playerAt.y << "," << playerAt.z << " ===";
	gtLog("glint", GT_INFO, header.str());
	logCompendiumCategoryCensus();

	Entity aimed = 0;
	const bool targeted = PLAYER::GET_PLAYER_TARGET_ENTITY(PLAYER::PLAYER_ID(),
		&aimed) != 0;
	if (!targeted)
		PLAYER::GET_ENTITY_PLAYER_IS_FREE_AIMING_AT(PLAYER::PLAYER_ID(), &aimed);
	logCompendiumEntity(aimed, playerAt);
	logCompendiumWeapons(playerPed);

	int peds[160] = {};
	const int count = sharedWorldPedSnapshot(peds, (int)_countof(peds));
	int logged = 0;
	for (int index = 0; index < count && logged < 24; ++index) {
		const Ped candidate = peds[index];
		if (!candidate || candidate == playerPed ||
			!ENTITY::DOES_ENTITY_EXIST(candidate) || PED::IS_PED_HUMAN(candidate))
			continue;
		const Vector3 at = ENTITY_COORDS(candidate);
		const float dx = at.x - playerAt.x;
		const float dy = at.y - playerAt.y;
		const float dz = at.z - playerAt.z;
		if (dx * dx + dy * dy + dz * dz > 10000.0f) continue;
		logCompendiumPed("nearby", candidate, playerAt);
		++logged;
	}
	std::ostringstream tail;
	tail << "nearby_nonhuman_logged=" << logged << " pool_count=" << count;
	gtLog("glint", GT_INFO, tail.str());
	gtLog("glint", GT_INFO, "--- capture complete ---");
	AUDIO::PLAY_SOUND_FRONTEND("SELECT", "HUD_SHOP_SOUNDSET", TRUE, 0);
}

static void updateCompendiumGlintProbe(Ped playerPed, bool blocked) {
	if (!g_compendiumGlintProbeEnabled || blocked || !playerPed ||
		ENTITY::IS_ENTITY_DEAD(playerPed)) {
		g_compendiumGlintProbeKeyWasDown = false;
		return;
	}
	const bool keyDown = (GetAsyncKeyState(VK_F10) & 0x8000) != 0;
	if (keyDown && !g_compendiumGlintProbeKeyWasDown)
		captureCompendiumGlintProbe(playerPed);
	g_compendiumGlintProbeKeyWasDown = keyDown;
}
