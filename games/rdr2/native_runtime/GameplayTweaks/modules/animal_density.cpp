// GitHub #29: apply the configured free-roam animal spawn multipliers.
//
// NativeDB identifies both hashes as *_THIS_FRAME. Rockstar's shipped mission
// scripts likewise issue 0.0/1.0/2.0 continuously while they own population
// suppression. This module therefore runs every tick; a call-site log is not a
// claim that already-streamed or explicitly scripted animals were removed.

static void updateAnimalDensity() {
	float density = g_animalEnabled ? g_animalMult : 1.0f;
	if (!std::isfinite(density)) density = 1.0f;
	if (density < 0.0f) density = 0.0f;
	// Do not silently cap the user's setting. The previous inline path turned
	// 99 into 10 while the editor and INI continued to show 99, invalidating the
	// returned comparison before the native ever saw the requested value.
	SET_ANIMAL_DENSITY(density);
	SET_SCENARIO_ANIMAL_DENSITY(density);
	const DWORD now = GetTickCount();

	// A setter call is not an animal-population result. Sample the existing
	// shared world-ped snapshot at a bounded cadence and report what actually
	// streamed during a stable one-minute setting window. The population-type
	// histogram is deliberately left numeric: no RDR2 source currently proves
	// the GTA population-type enum names carry over unchanged, so assigning
	// labels here would repeat the invented-evidence failure recorded in
	// fuckups.txt. This observer never creates, deletes, moves, or owns a ped.
	static DWORD windowStarted = 0;
	static DWORD lastSample = 0;
	static float windowDensity = -1.0f;
	static unsigned sampleCount = 0;
	static unsigned animalTotal = 0;
	static unsigned populationTypes[16] = {};
	static std::unordered_set<Ped> uniqueAnimals;
	if (windowStarted == 0 || density != windowDensity) {
		windowStarted = now;
		lastSample = 0;
		windowDensity = density;
		sampleCount = 0;
		animalTotal = 0;
		for (unsigned& count : populationTypes) count = 0;
		uniqueAnimals.clear();
	}
	if (now - lastSample >= 5000) {
		lastSample = now;
		Ped peds[256] = {};
		const int count = sharedWorldPedSnapshot(peds, (int)_countof(peds));
		unsigned animalsThisSample = 0;
		for (int index = 0; index < count; ++index) {
			const Ped candidate = peds[index];
			if (!candidate || !ENTITY::DOES_ENTITY_EXIST(candidate) ||
				PED::IS_PED_HUMAN(candidate)) continue;
			++animalsThisSample;
			uniqueAnimals.insert(candidate);
			const int populationType = ENTITY::GET_ENTITY_POPULATION_TYPE(candidate);
			if (populationType >= 0 && populationType < 16)
				++populationTypes[populationType];
		}
		++sampleCount;
		animalTotal += animalsThisSample;
	}
	if (sampleCount && now - windowStarted >= 60000) {
		std::ostringstream observed;
		observed << "observed-window configured=" << windowDensity
			<< " samples=" << sampleCount
			<< " meanLoadedAnimals=" << std::fixed << std::setprecision(2)
			<< ((double)animalTotal / (double)sampleCount)
			<< " uniqueHandles=" << uniqueAnimals.size()
			<< " populationTypes=";
		bool first = true;
		for (int type = 0; type < 16; ++type) {
			if (!populationTypes[type]) continue;
			if (!first) observed << ',';
			first = false;
			observed << type << ':' << populationTypes[type];
		}
		gtLog("animals", GT_INFO, observed.str());
		windowStarted = now;
		sampleCount = 0;
		animalTotal = 0;
		for (unsigned& count : populationTypes) count = 0;
		uniqueAnimals.clear();
	}

	static float lastApplied = -1.0f;
	static DWORD lastHeartbeat = 0;
	if (density != lastApplied || now - lastHeartbeat >= 15000) {
		lastApplied = density;
		lastHeartbeat = now;
		std::ostringstream line;
		line << "heartbeat configured=" << g_animalMult
			<< " applied=" << density
			<< " enabled=" << (g_animalEnabled ? 1 : 0)
			<< " cadence=every-frame"
			<< " populationBudget="
			<< invoke<float>(0x8A3945405B31048F)
			<< " existing-or-scripted-animals=not-owned";
		gtLog("animals", GT_INFO, line.str());
	}
}
