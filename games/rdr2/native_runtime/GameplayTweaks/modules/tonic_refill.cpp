// GitHub #30: Bloodborne/DS2-style tonic capacity, overflow, and refilling.
//
// This module deliberately owns its persistence and configuration so feature
// agents never need to edit the shared dispatcher.  Integration includes this
// file after world_economy.cpp and calls updateTonicRefilling once per frame.

struct TonicTier {
	const char* item;
	const char* reserveKey;
	int reserve;
	int lastCount;
};

struct TonicFamily {
	const char* name;
	const char* capacityKey;
	TonicTier tiers[4]; // weak, standard, potent, special
};

static TonicFamily g_tonicFamilies[] = {
	{ "Health", "HealthCapacity", {
		{ "CONSUMABLE_MEDICINE_USED", "Weak", 0, 0 },
		{ "CONSUMABLE_MEDICINE", "Standard", 0, 0 },
		{ "CONSUMABLE_POTENT_MEDICINE", "Potent", 0, 0 },
		{ "CONSUMABLE_SPECIAL_MEDICINE_CRAFTED", "Special", 0, 0 }
	} },
	{ "Stamina", "StaminaCapacity", {
		{ "CONSUMABLE_RESTORATIVE_USED", "Weak", 0, 0 },
		{ "CONSUMABLE_RESTORATIVE", "Standard", 0, 0 },
		{ "CONSUMABLE_POTENT_RESTORATIVE", "Potent", 0, 0 },
		{ "CONSUMABLE_SPECIAL_RESTORATIVE_CRAFTED", "Special", 0, 0 }
	} },
	{ "DeadEye", "DeadEyeCapacity", {
		{ "CONSUMABLE_SNAKE_OIL_USED", "Weak", 0, 0 },
		{ "CONSUMABLE_SNAKE_OIL", "Standard", 0, 0 },
		{ "CONSUMABLE_POTENT_SNAKE_OIL", "Potent", 0, 0 },
		{ "CONSUMABLE_SPECIAL_SNAKE_OIL_CRAFTED", "Special", 0, 0 }
	} }
};

static bool g_tonicRefillLoaded = false;
static bool g_tonicRefillEnabled = true;
static std::string g_tonicStoragePath;
static DWORD g_tonicNextPollAt = 0;
static DWORD g_tonicPendingRefillAt = 0;
static bool g_tonicWasAtCamp = false;
static std::string g_tonicPendingReason;

static int tonicChallengeRank(const TonicFamily& family) {
	static const char* healthGoals[10][12] = {
		{ "ACW_HUNT_Rank_01_Skin" }, { "ACW_HUNT_Rank_02_Rabbits" },
		{ "ACW_HUNT_Rank_03_Binoculars" }, { "ACW_HUNT_Rank_04_CleanKill" },
		{ "ACW_HUNT_Rank_05_Bear" },
		{ "ACW_HUNT_Rank_06_CougarKill", "ACW_HUNT_Rank_06_CougarSkin" },
		{ "ACW_HUNT_Rank_07_BaitedKills" }, { "ACW_HUNT_Rank_08_LootedFish" },
		{ "ACW_HUNT_Rank_09_Possum" }, { "ACW_HUNT_Rank_10_Panther" }
	};
	static const char* staminaGoals[10][12] = {
		{ "ACW_HERB_Rank_01_Yarrow" }, { "ACW_HERB_Rank_02_Berries" },
		{ "ACW_HERB_Rank_03_SageCrafting" }, { "ACW_HERB_Rank_04_FeedMushrooms" },
		{ "ACW_HERB_Rank_05_TobaccoCrafting" }, { "ACW_HERB_Rank_06_PickingHerbs" },
		{ "ACW_HERB_Rank_07_CraftSpecialTonic", "ACW_HERB_Rank_07_UseSpecialTonic" },
		{ "ACW_HERB_Rank_08_PoisonWeapons" }, { "ACW_HERB_Rank_09_AllHerbs" },
		{ "ACW_HERB_Rank_10_ExoticBirdSeasoning", "ACW_HERB_Rank_10_TenderPorkSeasoning",
			"ACW_HERB_Rank_10_PlumpBirdSeasoning", "ACW_HERB_Rank_10_BigGameMeatSeasoning",
			"ACW_HERB_Rank_10_PrimeBeefSeasoning", "ACW_HERB_Rank_10_SucculentFishSeasoning",
			"ACW_HERB_Rank_10_GameMeatSeasoning", "ACW_HERB_Rank_10_FlakeyFishSeasoning",
			"ACW_HERB_Rank_10_CrustaceanMeatSeasoning", "ACW_HERB_Rank_10_GristlyMuttonSeasoning",
			"ACW_HERB_Rank_10_MatureVenisonSeasoning" }
	};
	static const char* deadEyeGoals[10][12] = {
		{ "ACW_WEAP_Rank_01_KnifeKills" }, { "ACW_WEAP_Rank_02_ThrowingKnife" },
		{ "ACW_WEAP_Rank_03_Tomahawk" }, { "ACW_WEAP_Rank_04_ShotgunCraftedAmmo" },
		{ "ACW_WEAP_Rank_05_Mounted" }, { "ACW_WEAP_Rank_06_Dynamite" },
		{ "ACW_WEAP_Rank_07_Tomahawk" }, { "ACW_WEAP_Rank_08_Sidearm" },
		{ "ACW_WEAP_Rank_09_Bow" }, { "ACW_WEAP_Rank_10_Bear" }
	};
	const char* root = nullptr;
	const char* completed = nullptr;
	const char* (*goals)[12] = nullptr;
	if (_stricmp(family.name, "Health") == 0) {
		root = "SP_CHAL_HUNT_ROOT";
		completed = "CHAL_MASTER_HUNTER_TREE_COMPLETED";
		goals = healthGoals;
	} else if (_stricmp(family.name, "Stamina") == 0) {
		root = "SP_CHAL_HERB_ROOT";
		completed = "CHAL_HERBALIST_TREE_COMPLETED";
		goals = staminaGoals;
	} else {
		root = "SP_CHAL_WEAP_ROOT";
		completed = "CHAL_WEAPONS_EXPERT_TREE_COMPLETED";
		goals = deadEyeGoals;
	}
	for (int rank = 0; rank < 10; ++rank)
		for (int goal = 0; goal < 12 && goals[rank][goal]; ++goal)
			if (GOAL_ACTIVE(joaat(root), joaat(goals[rank][goal]))) return rank;
	return UNLOCKED(joaat(completed)) ? 10 : 0;
}

static int tonicReadNonNegative(const char* section, const char* key,
	int fallback, const std::string& path) {
	const int value = GetPrivateProfileIntA(section, key, fallback, path.c_str());
	return value < 0 ? 0 : value;
}

static void tonicWriteInt(const char* section, const char* key, int value) {
	char text[32];
	sprintf_s(text, "%d", (std::max)(0, value));
	WritePrivateProfileStringA(section, key, text, g_tonicStoragePath.c_str());
}

static void tonicLog(GtLogLevel level, const std::string& line) {
	gtLog("tonics", level, line);
}

static int tonicCapacity(const TonicFamily& family) {
	const int base = tonicReadNonNegative("TonicRefill", family.capacityKey, 3, g_iniPath);
	const int bonus = tonicReadNonNegative(family.name, "CapacityBonus", 0,
		g_tonicStoragePath);
	return (std::min)(99, base + tonicChallengeRank(family) + bonus);
}

static int tonicLiveCount(const TonicTier& tier) {
	return (std::max)(0, INVENTORY_ITEM_COUNT(joaat(tier.item)));
}

static int tonicFamilyLiveCount(const TonicFamily& family) {
	int total = 0;
	for (int tier = 0; tier < 4; ++tier) total += tonicLiveCount(family.tiers[tier]);
	return total;
}

static int tonicFamilyReserveCount(const TonicFamily& family) {
	int total = 0;
	for (int tier = 0; tier < 4; ++tier) total += family.tiers[tier].reserve;
	return total;
}

static void loadTonicRefillState() {
	if (g_tonicRefillLoaded) return;
	g_tonicRefillLoaded = true;
	g_tonicRefillEnabled = GetPrivateProfileIntA("TonicRefill", "Enabled", 1,
		g_iniPath.c_str()) != 0;
	g_tonicStoragePath = g_moduleDir + "\\GameplayTweaks.tonic-storage.ini";
	for (TonicFamily& family : g_tonicFamilies) {
		for (TonicTier& tier : family.tiers) {
			tier.reserve = tonicReadNonNegative(family.name, tier.reserveKey, 0,
				g_tonicStoragePath);
			tier.lastCount = tonicLiveCount(tier);
		}
	}
	g_tonicNextPollAt = GetTickCount() + 2000;
	tonicLog(GT_INFO, "registered enabled=" + std::to_string(g_tonicRefillEnabled ? 1 : 0));
}

// Persist reserve immediately after the verified inventory delta. A crash can
// therefore never turn an unverified remove/add return value into stored stock.
static int moveTonicToReserve(TonicFamily& family, int tierIndex, int requested) {
	if (requested <= 0) return 0;
	TonicTier& tier = family.tiers[tierIndex];
	const Hash item = joaat(tier.item);
	const int before = tonicLiveCount(tier);
	if (before <= 0) return 0;
	INVENTORY_REMOVE_WITH_REASON(item, (std::min)(before, requested),
		joaat("REMOVE_REASON_DUPLICATE"));
	const int after = tonicLiveCount(tier);
	const int moved = (std::max)(0, before - after);
	if (moved > 0) {
		tier.reserve += moved;
		tonicWriteInt(family.name, tier.reserveKey, tier.reserve);
		tier.lastCount = after;
		tonicLog(GT_INFO, std::string("overflow family=") + family.name + " tier=" +
			tier.reserveKey + " moved=" + std::to_string(moved) + " stored=" +
			std::to_string(tier.reserve));
	}
	return moved;
}

static void enforceTonicCapacity(TonicFamily& family) {
	int counts[4] = {};
	int acquired[4] = {};
	int total = 0;
	for (int tier = 0; tier < 4; ++tier) {
		counts[tier] = tonicLiveCount(family.tiers[tier]);
		acquired[tier] = (std::max)(0, counts[tier] - family.tiers[tier].lastCount);
		total += counts[tier];
	}
	int overflow = total - tonicCapacity(family);
	int movedTotal = 0;
	int acquiredTotal = 0;
	for (int tier = 0; tier < 4; ++tier) acquiredTotal += acquired[tier];
	if (overflow > 0) {
		// Divert the item(s) that just arrived first. A high-tier pickup while the
		// active allotment is full goes to storage; it must not evict an unrelated
		// low-tier bottle from the player's satchel.
		for (int tier = 0; tier < 4 && overflow > 0; ++tier) {
			const int moved = moveTonicToReserve(family, tier,
				(std::min)(overflow, acquired[tier]));
			overflow -= moved;
			movedTotal += moved;
		}
		// Existing saves may begin above the new family cap. Normalize that one
		// time from weakest upward, preserving the strongest active tonics. Never
		// use that fallback in the same poll as an acquisition: if removing the
		// newly acquired tier is transiently rejected, evicting a different tonic
		// would silently change what the player chose to carry.
		if (acquiredTotal == 0) {
			for (int tier = 0; tier < 4 && overflow > 0; ++tier) {
				const int moved = moveTonicToReserve(family, tier, overflow);
				overflow -= moved;
				movedTotal += moved;
			}
		}
	}
	for (int tier = 0; tier < 4; ++tier) {
		const int current = tonicLiveCount(family.tiers[tier]);
		// Preserve a rejected positive delta so the next poll retries the same
		// tier rather than treating it as old inventory and removing a weaker one.
		if (overflow > 0 && acquired[tier] > 0)
			family.tiers[tier].lastCount = (std::min)(family.tiers[tier].lastCount, current);
		else family.tiers[tier].lastCount = current;
	}
	if (movedTotal > 0) {
		char message[128];
		sprintf_s(message, "%s tonics sent to storage (%d stored).",
			family.name, tonicFamilyReserveCount(family));
		CASING_FEED(message, "", 0);
	}
}

static int refillTonicFamily(TonicFamily& family) {
	int missing = (std::max)(0, tonicCapacity(family) - tonicFamilyLiveCount(family));
	const int requested = missing;
	// Highest tier first is the defining refill rule. Only a verified inventory
	// increase spends persistent reserve.
	for (int tierIndex = 3; tierIndex >= 0 && missing > 0; --tierIndex) {
		TonicTier& tier = family.tiers[tierIndex];
		const int want = (std::min)(missing, tier.reserve);
		if (want <= 0) continue;
		const int before = tonicLiveCount(tier);
		INVENTORY_ADD(joaat(tier.item), want);
		const int after = tonicLiveCount(tier);
		const int restored = (std::min)(want, (std::max)(0, after - before));
		if (restored <= 0) continue;
		tier.reserve -= restored;
		tier.lastCount = after;
		tonicWriteInt(family.name, tier.reserveKey, tier.reserve);
		missing -= restored;
		tonicLog(GT_INFO, std::string("refill family=") + family.name + " tier=" +
			tier.reserveKey + " restored=" + std::to_string(restored) +
			" stored=" + std::to_string(tier.reserve));
	}
	tonicLog(GT_INFO, std::string("refill-result family=") + family.name + " requested=" +
		std::to_string(requested) + " missing=" + std::to_string(missing));
	return missing;
}

static void performTonicRefill(const char* reason) {
	int missing[3] = {};
	for (int family = 0; family < 3; ++family)
		missing[family] = refillTonicFamily(g_tonicFamilies[family]);
	if (missing[0] || missing[1] || missing[2]) {
		char message[192];
		sprintf_s(message,
			"Tonic storage could not fully refill: Health %d, Stamina %d, Dead Eye %d short.",
			missing[0], missing[1], missing[2]);
		CASING_FEED(message, "", 0);
	}
	tonicLog(GT_INFO, std::string("refill-trigger reason=") + reason);
}

// Capacity sources (challenge modules, trinkets, or scripted rewards) call this
// instead of reaching into persistence. The bonus survives restarts and is
// additive with the INI base capacity.
static bool upgradeTonicCapacity(const char* familyName, int amount) {
	loadTonicRefillState();
	if (!familyName || amount <= 0) return false;
	for (TonicFamily& family : g_tonicFamilies) {
		if (_stricmp(family.name, familyName) != 0) continue;
		const int oldBonus = tonicReadNonNegative(family.name, "CapacityBonus", 0,
			g_tonicStoragePath);
		const int newBonus = (std::min)(99, oldBonus + amount);
		tonicWriteInt(family.name, "CapacityBonus", newBonus);
		tonicLog(GT_INFO, std::string("capacity-upgrade family=") + family.name + " old=" +
			std::to_string(oldBonus) + " new=" + std::to_string(newBonus));
		return newBonus != oldBonus;
	}
	return false;
}

static bool tonicAtRefillCamp(Ped ped) {
	if (!ped) return false;
	if (scriptRunning("player_camp") || scriptRunning("campfire_gang") ||
		scriptRunning("campfire_gang_es")) return true;
	const Vector3 playerPosition = ENTITY_COORDS(ped);
	for (const Campsite& camp : g_campsites) {
		if (camp.activated && campDistanceSq(playerPosition, camp.pos) <= 225.0f)
			return true;
	}
	return false;
}

// deathSequenceEnded is the existing post-death edge in script.cpp. Death
// waits briefly because Rockstar restores the inventory after that edge; camp
// entry refills immediately. The module still monitors acquisitions while no
// refill is pending.
static void updateTonicRefilling(Ped ped, DWORD now, bool deathSequenceEnded) {
	loadTonicRefillState();
	g_tonicRefillEnabled = GetPrivateProfileIntA("TonicRefill", "Enabled", 1,
		g_iniPath.c_str()) != 0;
	if (!g_tonicRefillEnabled || !ped) return;
	const bool atCamp = tonicAtRefillCamp(ped);
	if (atCamp && !g_tonicWasAtCamp) {
		g_tonicPendingReason = "camp";
		g_tonicPendingRefillAt = now;
	}
	g_tonicWasAtCamp = atCamp;
	if (deathSequenceEnded) {
		g_tonicPendingReason = "death";
		g_tonicPendingRefillAt = now + 1500;
	}
	if (now < g_tonicNextPollAt) return;
	g_tonicNextPollAt = now + 250;
	for (TonicFamily& family : g_tonicFamilies) enforceTonicCapacity(family);
	if (g_tonicPendingRefillAt && now >= g_tonicPendingRefillAt) {
		const std::string reason = g_tonicPendingReason;
		g_tonicPendingRefillAt = 0;
		g_tonicPendingReason.clear();
		performTonicRefill(reason.c_str());
	}
}
