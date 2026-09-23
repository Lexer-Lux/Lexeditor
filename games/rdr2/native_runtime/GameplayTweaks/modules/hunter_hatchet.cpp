// GitHub #67: the Hunter's Hatchet kills ordinary animals in one registered
// hit while preserving the quality the animal had before that hit.  This owns
// neither harvesting nor inventory; Rockstar remains the sole loot producer.

struct HunterHatchetAnimalState {
	Ped ped = 0;
	Hash model = 0;
	int quality = 0;
	DWORD lastSeen = 0;
	bool processed = false;
};

static HunterHatchetAnimalState g_hunterHatchetAnimals[96] = {};

static void hunterHatchetLog(Ped animal, Hash model, int quality, bool dead) {
	std::ostringstream line;
	line << "processed ped=" << animal
		<< " model=0x" << std::hex << model << std::dec
		<< " quality=" << quality << " dead=" << (dead ? 1 : 0);
	gtLog("hatchet", GT_INFO, line.str());
}

static void resetHunterHatchetAnimals() {
	for (HunterHatchetAnimalState& state : g_hunterHatchetAnimals)
		state = HunterHatchetAnimalState{};
}

static bool isLegendaryAnimal(Ped ped, Hash model) {
	// Story legendary hunts normally own their animal as a mission entity.  The
	// model/outfit checks are a second guard for spawn/teardown frames where
	// Rockstar has not yet (or no longer) marked that ownership.
	static const Hash legendaryModels[] = {
		joaat("A_C_BOARLEGENDARY_01"),
		joaat("A_C_BUFFALO_TATANKA_01"),
	};
	for (Hash legendaryModel : legendaryModels)
		if (model == legendaryModel) return true;

	const Hash outfit = PED::_GET_PED_META_OUTFIT_HASH(ped);
	static const Hash legendaryOutfits[] = {
		joaat("BEAR_LEGENDARY"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_BEAVER"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_BIGHORNRAM"),
		joaat("DISCOVERABLES_WHITE_BUFFALO"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_BOAR"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_BUCK"),
		(Hash)47534268, // Tatanka bison; literal used by hunting_zone_buffalo_tatanka.
		joaat("COUGAR_LEGENDARY"),
		joaat("COYOTE_LEGENDARY"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_ELK"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_FOX"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_MOOSE"),
		joaat("PANTHER_LEGENDARY"),
		joaat("META_OUTFIT_ANIMAL_ALBINO_PRONGHORN"),
		joaat("META_OUTFIT_ANIMAL_LEGENDARY_WOLF"),
	};
	for (Hash legendaryOutfit : legendaryOutfits)
		if (outfit == legendaryOutfit) return true;
	return false;
}

static HunterHatchetAnimalState& hunterHatchetState(Ped ped, Hash model, DWORD now) {
	HunterHatchetAnimalState* empty = nullptr;
	HunterHatchetAnimalState* oldest = &g_hunterHatchetAnimals[0];
	for (HunterHatchetAnimalState& state : g_hunterHatchetAnimals) {
		// A stale handle may be reused for another ped with the same model.  Only
		// reuse a matching cache entry while it has remained continuously nearby.
		if (state.ped == ped && state.model == model && now - state.lastSeen <= 1000)
			return state;
		if (!state.ped && !empty) empty = &state;
		if (state.lastSeen < oldest->lastSeen) oldest = &state;
	}
	HunterHatchetAnimalState& state = empty ? *empty : *oldest;
	state.ped = ped;
	state.model = model;
	state.quality = PED::_GET_PED_QUALITY(ped);
	state.lastSeen = now;
	state.processed = false;
	return state;
}

static void updateHunterHatchet(Ped playerPed, bool mission) {
	if (!g_hunterHatchetEnabled || mission) {
		resetHunterHatchetAnimals();
		return;
	}

	const DWORD now = GetTickCount();
	const Hash hunter = joaat("WEAPON_MELEE_HATCHET_HUNTER");
	int nearby[65] = {};
	nearby[0] = 32;
	const int count = NEARBY_PEDS(playerPed, nearby);
	for (int i = 0; i < count && i < 32; ++i) {
		const Ped animal = nearby[i + 1];
		if (!animal || PED::IS_PED_HUMAN(animal) ||
			ENTITY::IS_ENTITY_A_MISSION_ENTITY(animal)) continue;
		const Hash model = ENTITY_MODEL(animal);
		if (isLegendaryAnimal(animal, model)) continue;

		HunterHatchetAnimalState& state = hunterHatchetState(animal, model, now);
		state.lastSeen = now;
		if (state.processed || !DAMAGED_BY_WEAPON(animal, hunter) ||
			!ENTITY::HAS_ENTITY_BEEN_DAMAGED_BY_ENTITY(animal, playerPed, 1, 1)) continue;

		// Preserve the cached natural tier rather than upgrading every animal to
		// perfect.  Do this even if the original strike was already fatal.
		if (state.quality >= 0) PED::_SET_PED_QUALITY(animal, state.quality);
		state.processed = true;
		if (!ENTITY::IS_ENTITY_DEAD(animal))
			invoke<Void>(0xAC2767ED8BDFAB15, animal, 0, playerPed);
		hunterHatchetLog(animal, model, state.quality,
			ENTITY::IS_ENTITY_DEAD(animal) != FALSE);
	}
}
