// GitHub #115: newspaper vendors should advertise themselves only while the
// newspaper shop can actually sell the player a currently available edition.
// Included by script.cpp into the single ScriptHook translation unit.

struct NewspaperVendorMarker {
	const char* name;
	Vector3 position;
	Blip blip = 0;
};

static NewspaperVendorMarker g_newspaperVendorMarkers[] = {
	{ "Annesburg Newspaper",  { 2947.450f,  1344.723f,  44.552f } },
	{ "Blackwater Newspaper", { -806.585f, -1330.295f,  43.60916f } },
	{ "Rhodes Newspaper",     { 1332.786f, -1299.380f,  77.354f } },
	{ "Saint Denis Newspaper",{ 2683.454f, -1400.018f,  46.693f } },
	{ "Strawberry Newspaper", { -1773.417f, -394.250f, 157.091f } },
	{ "Valentine Newspaper",  { -269.754f,   785.441f, 118.489f } },
};

static int refreshNewspaperAvailabilityCache() {
	// shop_newspaper_boy.c::func_564 builds Global_1430252 as a private cache
	// for Rockstar's interaction owner. GameplayTweaks previously copied that
	// function and wrote the shared cache from its own loop. The #114 stage trace
	// proved those writes immediately destroyed and rebuilt every shop record.
	// Count the same 14 persisted records locally. Conditional map art needs only
	// the result; it must never take ownership of Rockstar's cache.
	constexpr int kGlobal40 = 40;
	constexpr int kNewspaperStates = 9479;
	constexpr int kNewspaperCount = 14;
	constexpr int kNewspaperStride = 4;
	int availableCount = 0;
	for (int issue = 0; issue < kNewspaperCount; ++issue) {
		const int state = static_cast<int>(*getGlobalPtr(
			kGlobal40 + kNewspaperStates + issue * kNewspaperStride));
		if (state == 0) ++availableCount;
	}
	return availableCount;
}

static void removeNewspaperVendorMarkers() {
	for (NewspaperVendorMarker& marker : g_newspaperVendorMarkers) {
		if (marker.blip) REMOVE_MAP_BLIP(&marker.blip);
		marker.blip = 0;
	}
}

static void updateNewspaperVendorMarkers() {
	static DWORD lastUpdate = 0;
	static int lastAvailableCount = -1;
	const DWORD now = GetTickCount();
	if (now - lastUpdate < 500) return;
	lastUpdate = now;

	const int availableCount = refreshNewspaperAvailabilityCache();
	if (availableCount != lastAvailableCount) {
		std::ostringstream log;
		log << "frame=" << MISC::GET_FRAME_COUNT()
			<< " available=" << availableCount
			<< " source=persistent_records_read_only"
			<< " markers=" << (availableCount > 0 ? "shown" : "removed");
		gtLog("newspaper", GT_INFO, log.str());
		lastAvailableCount = availableCount;
	}

	if (availableCount <= 0) {
		removeNewspaperVendorMarkers();
		return;
	}

	for (NewspaperVendorMarker& marker : g_newspaperVendorMarkers) {
		if (marker.blip && !MAP::DOES_BLIP_EXIST(marker.blip)) marker.blip = 0;
		if (marker.blip) continue;
		marker.blip = ADD_COORD_BLIP((Hash)-1337945352, marker.position);
		if (!marker.blip) continue;
		SET_BLIP_ICON(marker.blip, joaat("LEX_BLIP_NEWSPAPER_AVAILABLE"));
		SET_BLIP_NAME(marker.blip, marker.name);
	}
}
