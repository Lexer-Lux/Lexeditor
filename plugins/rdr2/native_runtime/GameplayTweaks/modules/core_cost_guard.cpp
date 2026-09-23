// GitHub #146: prevent use of items whose configured negative core effects
// would take any player core below zero.
//
// Rockstar's generic item scripts resolve catalog effects through the two
// ITEM_DATABASE natives below, then turn an effect percent into the 0..100 HUD
// core scale. The inventory enable/disable natives are short_update's own
// cross-surface availability mechanism, so one decision greys radial/satchel
// entries and prevents their normal activation paths.

struct CoreCostEffectIds {
	Any count;
	Any capacity;
	Any ids[20];
};

struct CoreCostEffectInfo {
	Any fields[7];
};

struct CoreCostGuardItem {
	const char* name;
	Hash hash;
	float cost[3]; // Health, Stamina, Dead Eye on the displayed 0..100 scale.
	bool resolved;
	bool blocked;
	bool availabilityOwned;
	bool availabilityConfirmed;
	unsigned readbackFailStreak;
	bool writesAbandoned;
	DWORD lastAvailabilityWriteAt;
};

// An availability write whose own readback never confirms is not a transient
// miss; it means this surface does not own that item's disabled state. Retrying
// it forever produced 600+ unconfirmed engine writes in one session against the
// same shared inventory layer Story's shop scripts use. Stop after this many
// consecutive failures and report once, instead of churning for the session.
static constexpr unsigned kCoreCostMaxReadbackFailures = 3;

// Generated from every catalog item referencing a negative EFFECT_*_CORE in
// the shipped MyOverhaul/catalog_sp.ymt. The verifier rejects catalog drift.
// Values are deliberately not compiled here: the live ITEM_DATABASE remains
// authoritative for the effect amount and any multi-core combination.
static CoreCostGuardItem g_coreCostItems[] = {
	{ "CONSUMABLE_JERKY" },
	{ "CONSUMABLE_MOONSHINE" },
	{ "CONSUMABLE_WHISKEY" },
	{ "CONSUMABLE_BRANDY" },
	{ "CONSUMABLE_CIGARETTE_BOX_CHEAP" },
	{ "CONSUMABLE_RUM" },
	{ "CONSUMABLE_OFFAL" },
	{ "CONSUMABLE_CRACKERS" },
	{ "CONSUMABLE_JERKY_VENISON" },
	{ "CONSUMABLE_BISCUIT_BOX" },
	{ "CONSUMABLE_CIGARETTE_BOX" },
	{ "CONSUMABLE_MEAL_CHILLI" },
	{ "CONSUMABLE_SALOON_WHISKEY" },
	{ "CONSUMABLE_GIN" },
	{ "CONSUMABLE_SALOON_BEER" },
};

static bool g_coreCostEnabled = true;
static DWORD g_coreCostConfigAt = 0;
static DWORD g_coreCostResolveAt = 0;
static DWORD g_coreCostHeartbeatAt = 0;
static Hash g_coreCostRejectedInteraction = 0;
static int g_coreCostLastSettledInventoryRevision = -1;
static unsigned g_coreCostAvailabilityChecks = 0;
static unsigned g_coreCostAvailabilityWrites = 0;
static unsigned g_coreCostAvailabilityReadbackFailures = 0;
static DWORD g_coreCostPlayerReadyAt = 0;
static constexpr DWORD kCoreCostStartupSettleMs = 15000;

static int coreCostSlotInt(Any slot) {
	return (int)(int32_t)(uint32_t)slot;
}

static float coreCostSlotFloat(Any slot) {
	union { uint32_t bits; float value; } decoded = {};
	decoded.bits = (uint32_t)slot;
	return decoded.value;
}

static int coreCostIndex(Hash effectType) {
	if (effectType == joaat("EFFECT_HEALTH_CORE")) return 0;
	if (effectType == joaat("EFFECT_STAMINA_CORE")) return 1;
	if (effectType == joaat("EFFECT_DEADEYE_CORE")) return 2;
	return -1;
}

static float coreCostEffectiveDelta(const CoreCostEffectInfo& info) {
	// generic_single_use_item.c func_23: percent is authoritative when nonzero;
	// otherwise value/8 is converted to the 0..100 core scale. Its internal
	// -100..100 store doubles both sides, so the displayed-scale delta is exactly
	// percent, or value/8*100 for the fallback.
	const float percent = coreCostSlotFloat(info.fields[5]);
	if (percent != 0.0f) return percent;
	return ((float)coreCostSlotInt(info.fields[2]) / 8.0f) * 100.0f;
}

static bool coreCostResolve(CoreCostGuardItem& item) {
	item.hash = joaat(item.name);
	item.cost[0] = item.cost[1] = item.cost[2] = 0.0f;
	CoreCostEffectIds ids = {};
	// Decompiled short_update uses `Var0.f_1 = 20`, passes `&Var0`, reads the
	// returned count from Var0, and indexes effect IDs from Var0.f_1[i]. Script
	// VM fixed arrays carry their capacity in that f_1 header slot; values begin
	// after it. The old C struct omitted the header, so our first "effect ID" was
	// the literal capacity 20 and every ITEM_EFFECT_INFO lookup failed.
	ids.capacity = 20;
	if (!ITEM_EFFECT_IDS(item.hash, reinterpret_cast<Any*>(&ids))) return false;
	const int count = (std::max)(0, (std::min)(20, coreCostSlotInt(ids.count)));
	for (int index = 0; index < count; ++index) {
		CoreCostEffectInfo info = {};
		if (!ITEM_EFFECT_INFO((Hash)ids.ids[index],
			reinterpret_cast<Any*>(&info))) return false;
		const int core = coreCostIndex((Hash)info.fields[1]);
		if (core < 0) continue;
		const float delta = coreCostEffectiveDelta(info);
		// Positive/zero effects never offset or contribute to the guard. If an
		// item has multiple negative entries for one core, all costs accumulate.
		if (delta < 0.0f) item.cost[core] += -delta;
	}
	item.resolved = true;
	GtLogStream("core-cost", GT_INFO)
		<< "resolved item=" << item.name
		<< " health=" << item.cost[0]
		<< " stamina=" << item.cost[1]
		<< " deadeye=" << item.cost[2] << "\n";
	return true;
}

static void coreCostResolvePending(DWORD now) {
	if (now - g_coreCostResolveAt < 2000) return;
	g_coreCostResolveAt = now;
	for (CoreCostGuardItem& item : g_coreCostItems) {
		if (!item.resolved && !coreCostResolve(item)) {
			GtLogStream("core-cost", GT_WARN)
				<< "effect lookup not ready item=" << item.name
				<< "; retrying\n";
		}
	}
}

static float coreCostCurrent(Ped ped, int core) {
	// The item scripts modify Global_40.f_11095[0..2] as floats and then derive
	// the integer native core readback from it. Reading the same source preserves
	// exact 6.25/12.5 thresholds instead of rounding them away.
	float internal = *reinterpret_cast<float*>(getGlobalPtr(40 + 11095 + core));
	if (std::isfinite(internal) && internal >= -100.01f && internal <= 100.01f)
		return (internal + 100.0f) * 0.5f;
	return (float)GET_CORE(ped, core);
}

static bool coreCostWouldUnderflow(const CoreCostGuardItem& item,
	const float current[3], int* insufficientCore) {
	for (int core = 0; core < 3; ++core) {
		// Exactly equal is allowed; use strict underflow with no arbitrary buffer.
		if (item.cost[core] > 0.0f && current[core] < item.cost[core]) {
			if (insufficientCore) *insufficientCore = core;
			return true;
		}
	}
	return false;
}

static bool coreCostItemBlocked(Hash hash) {
	for (const CoreCostGuardItem& item : g_coreCostItems)
		if (item.resolved && item.hash == hash) return item.blocked;
	return false;
}

static bool coreCostStoryItemDisabled(Hash item) {
	// satchel_ui_event_handler.c::func_110 rejects ordinary item use when this
	// exact predicate is true. Read the disabled state before and after our
	// matching availability setter. Do not infer success from the void call.
	return invoke<BOOL>(0x3D10D7179D7034AF, 1, item, FALSE) != FALSE;
}

static bool coreCostSetAvailability(CoreCostGuardItem& item, bool available,
	DWORD now, const char* reason) {
	++g_coreCostAvailabilityChecks;
	const bool desiredDisabled = !available;
	const bool beforeDisabled = coreCostStoryItemDisabled(item.hash);
	if (beforeDisabled == desiredDisabled) {
		item.availabilityConfirmed = true;
		return true;
	}

	if (available) INVENTORY_ENABLE_ITEM(item.hash);
	else INVENTORY_DISABLE_ITEM(item.hash);
	++g_coreCostAvailabilityWrites;
	item.lastAvailabilityWriteAt = now;
	const bool afterDisabled = coreCostStoryItemDisabled(item.hash);
	item.availabilityConfirmed = afterDisabled == desiredDisabled;
	if (item.availabilityConfirmed) {
		item.readbackFailStreak = 0;
	} else {
		++g_coreCostAvailabilityReadbackFailures;
		if (++item.readbackFailStreak >= kCoreCostMaxReadbackFailures &&
			!item.writesAbandoned) {
			item.writesAbandoned = true;
			GtLogStream("core-cost", GT_WARN)
				<< "availability writes abandoned item=" << item.name
				<< " consecutiveReadbackFailures=" << item.readbackFailStreak
				<< " reason=setter_does_not_own_this_item\n";
		}
	}
	GtLogStream("core-cost", item.availabilityConfirmed ? GT_INFO : GT_WARN)
		<< "availability " << (available ? "restore" : "block")
		<< " item=" << item.name
		<< " reason=" << reason
		<< " beforeDisabled=" << (beforeDisabled ? 1 : 0)
		<< " afterDisabled=" << (afterDisabled ? 1 : 0)
		<< " confirmed=" << (item.availabilityConfirmed ? 1 : 0)
		<< " writes=" << g_coreCostAvailabilityWrites << "\n";
	return item.availabilityConfirmed;
}

static bool coreCostWheelOpen() {
	static const Hash kWheel = joaat("INPUT_OPEN_WHEEL_MENU");
	return PAD::IS_CONTROL_PRESSED(0, kWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, kWheel) ||
		PAD::IS_CONTROL_PRESSED(2, kWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, kWheel);
}

static void coreCostRestoreOwnedAvailability(bool mutationSafe, DWORD now) {
	if (!mutationSafe) return;
	for (CoreCostGuardItem& item : g_coreCostItems) {
		if (!item.availabilityOwned) continue;
		if (coreCostSetAvailability(item, true, now, "feature_disabled"))
			item.availabilityOwned = false;
		item.blocked = false;
	}
}

static void updateCoreCostGuard(Ped ped, DWORD now, bool unavailable) {
	if (!g_coreCostConfigAt || now - g_coreCostConfigAt >= 2000) {
		g_coreCostConfigAt = now;
		g_coreCostEnabled = readB("CoreCostGuard", "Enabled", true);
	}
	if (unavailable || !ped ||
		!ENTITY::DOES_ENTITY_EXIST(ped) || ENTITY::IS_ENTITY_DEAD(ped)) return;
	if (!g_coreCostPlayerReadyAt) g_coreCostPlayerReadyAt = now;
	const bool interactionRunning = ITEM_INTERACTION_RUNNING(ped);
	const bool backupInventory = invoke<BOOL>(0x7C7E4AB748EA3B07) != FALSE;
	const bool wheelOpen = coreCostWheelOpen();
	const bool mutationSafe = now - g_coreCostPlayerReadyAt >=
		kCoreCostStartupSettleMs && !interactionRunning && !backupInventory &&
		!wheelOpen;
	if (!g_coreCostEnabled) {
		coreCostRestoreOwnedAvailability(mutationSafe, now);
		return;
	}

	coreCostResolvePending(now);
	const float current[3] = {
		coreCostCurrent(ped, 0),
		coreCostCurrent(ped, 1),
		coreCostCurrent(ped, 2),
	};
	// short_update.c::func_845 advances f_28 to f_27 after it completes its
	// bounded inventory-availability pass. Reconcile once when a new revision
	// settles. Never fight that pass while it is active, and never reassert on
	// every GameplayTweaks frame.
	const int requestedInventoryRevision = (int)*getGlobalPtr(1935496 + 27);
	const int appliedInventoryRevision = (int)*getGlobalPtr(1935496 + 28);
	const bool inventoryRevisionSettled =
		requestedInventoryRevision == appliedInventoryRevision;
	const bool reconcileSettledRevision = inventoryRevisionSettled &&
		requestedInventoryRevision != g_coreCostLastSettledInventoryRevision;
	if (reconcileSettledRevision)
		g_coreCostLastSettledInventoryRevision = requestedInventoryRevision;
	int blockedCount = 0;
	int resolvedCount = 0;
	int abandonedCount = 0;
	for (CoreCostGuardItem& item : g_coreCostItems) {
		if (!item.resolved) continue;
		++resolvedCount;
		if (item.writesAbandoned) ++abandonedCount;
		int insufficientCore = -1;
		const bool blocked = coreCostWouldUnderflow(item, current, &insufficientCore);
		if (blocked) ++blockedCount;
		const bool decisionChanged = blocked != item.blocked;
		const bool cooldownElapsed = now - item.lastAvailabilityWriteAt >= 5000;
		if (decisionChanged) {
			// A real core edge is new information, so a previously hopeless item
			// gets exactly one fresh streak rather than staying silent forever.
			item.readbackFailStreak = 0;
			item.writesAbandoned = false;
		}
		const bool reconcile = reconcileSettledRevision && cooldownElapsed &&
			!item.writesAbandoned;
		const bool retryFailedReadback = blocked &&
			!item.availabilityConfirmed && cooldownElapsed && !item.writesAbandoned;
		if (mutationSafe && (decisionChanged || reconcile || retryFailedReadback ||
			(!blocked && item.availabilityOwned && cooldownElapsed))) {
			if (blocked) {
				// Do not claim ownership when another Story condition already made the
				// item unavailable. Restore only a disable that our own write confirmed.
				const bool wasDisabled = coreCostStoryItemDisabled(item.hash);
				++g_coreCostAvailabilityChecks;
				if (!wasDisabled) {
					item.availabilityOwned = coreCostSetAvailability(item, false, now,
						decisionChanged ? "core_edge" : "inventory_revision");
				} else {
					item.availabilityConfirmed = true;
				}
			} else if (item.availabilityOwned) {
				if (coreCostSetAvailability(item, true, now,
					decisionChanged ? "core_edge" : "restore_retry"))
					item.availabilityOwned = false;
			}
		}
		if (decisionChanged) {
			item.blocked = blocked;
			GtLogStream("core-cost", GT_INFO)
				<< (blocked ? "blocked" : "restored")
				<< " item=" << item.name
				<< " core=" << insufficientCore
				<< " current=" << (insufficientCore >= 0 ? current[insufficientCore] : -1.0f)
				<< " cost=" << (insufficientCore >= 0 ? item.cost[insufficientCore] : 0.0f)
				<< " inventory=" << INVENTORY_ITEM_COUNT(item.hash)
				<< " availabilityOwned=" << (item.availabilityOwned ? 1 : 0)
				<< " availabilityConfirmed=" << (item.availabilityConfirmed ? 1 : 0)
				<< "\n";
		}
	}

	// short_update caches its chosen quick-use item at this exact global before
	// presenting INPUT_QUICK_USE_ITEM. Disable that action if the cached item has
	// become insufficient since selection; inventory disabling handles selection
	// and greying, while this closes the cached-shortcut race.
	const Hash quickItem = (Hash)*getGlobalPtr(1935496 + 67 + 2);
	if (coreCostItemBlocked(quickItem)) {
		DISABLE_CONTROL(0, joaat("INPUT_QUICK_USE_ITEM"));
		DISABLE_CONTROL(2, joaat("INPUT_QUICK_USE_ITEM"));
	}

	// A direct/contextual TASK_ITEM_INTERACTION can bypass inventory UI. The
	// normal paths never reach this branch because their item is already disabled;
	// clear an observed bypass immediately, before the generic script's authored
	// effect/consume animation event, and keep the item disabled.
	if (interactionRunning) {
		const Hash interaction = ITEM_INTERACTION_ITEM(ped);
		if (coreCostItemBlocked(interaction) &&
			g_coreCostRejectedInteraction != interaction) {
			TASK::CLEAR_PED_TASKS(ped, TRUE, FALSE);
			g_coreCostRejectedInteraction = interaction;
			GtLogStream("core-cost", GT_WARN)
				<< "rejected direct item interaction item=0x" << std::hex
				<< (uint32_t)interaction << std::dec
				<< " inventory=" << INVENTORY_ITEM_COUNT(interaction) << "\n";
		}
	} else {
		g_coreCostRejectedInteraction = 0;
	}

	if (now - g_coreCostHeartbeatAt >= 5000) {
		g_coreCostHeartbeatAt = now;
		GtLogStream("core-cost", GT_INFO)
			<< "heartbeat resolved=" << resolvedCount << "/"
			<< (sizeof(g_coreCostItems) / sizeof(g_coreCostItems[0]))
			<< " blocked=" << blockedCount
			<< " health=" << current[0]
			<< " stamina=" << current[1]
			<< " deadeye=" << current[2]
			<< " quick=0x" << std::hex << (uint32_t)quickItem << std::dec
			<< " inventoryRevision=" << requestedInventoryRevision
			<< "/" << appliedInventoryRevision
			<< " mutationSafe=" << (mutationSafe ? 1 : 0)
			<< " wheel=" << (wheelOpen ? 1 : 0)
			<< " backupInventory=" << (backupInventory ? 1 : 0)
			<< " interaction=" << (interactionRunning ? 1 : 0)
			<< " availabilityChecks=" << g_coreCostAvailabilityChecks
			<< " availabilityWrites=" << g_coreCostAvailabilityWrites
			<< " readbackFailures=" << g_coreCostAvailabilityReadbackFailures
			<< " writesAbandoned=" << abandonedCount
			<< " cadence=core_edge_or_settled_inventory_revision" << "\n";
	}
}
