// GitHub #151: recover an earned Story off-hand holster when the saved/current
// LOADOUT_3 component disappears.  This is not a permanent permission setter.
//
// Primary sources:
// - act_hunting_2.c progression case 24 chooses Arthur's
//   CLOTHING_SP_OFFHAND_000 (or John's -1515874150), grants it when absent,
//   equips it as MP_COMPONENT_TYPE_LOADOUT_3, and enables dual wield.
// - act_hunting_2.c func_444 maps LOADOUT_3 to component index 27; func_1099 and
//   func_799 read Global_1946804.f_1497.f_1[27 /*3*/] and compare it with
//   Global_1946804.f_57[27 /*11*/].  Only f_1497.f_1 has the extra field
//   offset; f_57 is the array itself and has no invented +1 header.
// - natives.json resolves the inventory, metaped, variation and dual-wield
//   calls below.  quickselectmenus_ymt.xml uses engine dual-wield available and
//   unlocked conditions for its three-handgun-slot provider.
//
// The dispatcher may call this every frame, but all native polling is capped at
// 4 Hz.  Recovery is one transition per observed missing-component episode,
// never runs while the radial/backup inventory owns a transaction, and requires
// the already-earned SP_WEAPON_DUALWIELD unlock.  It never invents progression,
// weapon ownership or clothing inventory records. It changes only the exact
// current LOADOUT_3 value that Rockstar's own wardrobe path publishes.

static const DWORD kDualWieldPollMs = 250;
static const DWORD kDualWieldHeartbeatMs = 3000;
static const DWORD kDualWieldSettleMs = 750;
static const DWORD kDualWieldStartupSettleMs = 15000;

// Global_1946804.f_1497.f_1[27 /*3*/].
static const int kDualWieldCurrentLoadout3Global =
	1946804 + 1497 + 1 + 27 * 3;
// Global_1946804.f_57[27 /*11*/].
static const int kDualWieldDefaultLoadout3Global =
	1946804 + 57 + 27 * 11;
static const int kStoryPlayerIdentityGlobal = 40 + 39;
static const Hash kUnsetLoadout3 = 2110595215u;

static DWORD g_dualWieldPollAt = 0;
static DWORD g_dualWieldHeartbeatAt = 0;
static DWORD g_dualWieldReadbackAt = 0;
static bool g_dualWieldKnown = false;
static bool g_dualWieldRepairLatched = false;
static bool g_dualWieldReadbackPending = false;
static int g_dualWieldRepairCount = 0;
static Ped g_dualWieldPed = 0;
static Hash g_dualWieldRepairItem = 0;
static DWORD g_dualWieldEligibleSince = 0;

static void dualWieldLog(GtLogLevel level, const std::string& line) {
	gtLog("dual-wield", level, line);
}

static bool dualWieldAllowed(Ped ped) {
	return invoke<BOOL>(0x918990BD9CE08582, ped) != FALSE;
}

static void setDualWieldAllowed(Ped ped, bool allowed) {
	invoke<Void>(0x83B8D50EB9446BBA, ped, allowed ? TRUE : FALSE);
}

static Hash dualWieldGlobalHash(int index) {
	return static_cast<Hash>(*getGlobalPtr(index));
}

static bool dualWieldWheelOpen() {
	static const Hash kWheel = joaat("INPUT_OPEN_WHEEL_MENU");
	return PAD::IS_CONTROL_PRESSED(0, kWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, kWheel) ||
		PAD::IS_CONTROL_PRESSED(2, kWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, kWheel);
}

static bool dualWieldInventoryBusy() {
	return invoke<BOOL>(0x7C7E4AB748EA3B07) != FALSE;
}

static bool dualWieldItemInUse(InventoryGuid* guid) {
	return guid && INVENTORY_GUID_VALID(guid) &&
		invoke<BOOL>(0x70E3A884ED000A01, 1, guid) != FALSE;
}

static bool dualWieldPhysicalComponent(Ped ped, Hash component) {
	return ped && component &&
		invoke<BOOL>(0xFB4891BD7578CDC1, ped, component) != FALSE;
}

static Hash dualWieldExpectedHolster() {
	const Hash storyPlayer = dualWieldGlobalHash(kStoryPlayerIdentityGlobal);
	return storyPlayer == joaat("PLAYER_THREE")
		? static_cast<Hash>(-1515874150) : joaat("CLOTHING_SP_OFFHAND_000");
}

static void dualWieldEquippedWeapons(Ped ped, Hash* primary, Hash* secondary) {
	if (primary) {
		*primary = 0;
		WEAPON::GET_CURRENT_PED_WEAPON(ped, primary, TRUE, 2, FALSE);
	}
	if (secondary) {
		*secondary = 0;
		WEAPON::GET_CURRENT_PED_WEAPON(ped, secondary, TRUE, 3, FALSE);
	}
}

static void dualWieldReadState(Ped ped, Hash item, std::ostringstream& line) {
	const Hash current = dualWieldGlobalHash(kDualWieldCurrentLoadout3Global);
	const Hash fallback = dualWieldGlobalHash(kDualWieldDefaultLoadout3Global);
	const int count = INVENTORY_ITEM_COUNT(item);
	InventoryGuid guid = {};
	const bool guidValid = INVENTORY_CLOTHING_GUID(item, &guid);
	const bool inUse = guidValid && dualWieldItemInUse(&guid);
	const bool physical = dualWieldPhysicalComponent(ped, item);
	Hash primary = 0, secondary = 0;
	dualWieldEquippedWeapons(ped, &primary, &secondary);
	line << "allow=" << (dualWieldAllowed(ped) ? 1 : 0)
		<< " unlock=" << (UNLOCK::_UNLOCK_IS_UNLOCKED(
			joaat("SP_WEAPON_DUALWIELD")) ? 1 : 0)
		<< " item=0x" << std::hex << item
		<< " count=" << std::dec << count
		<< " guid=" << (guidValid ? 1 : 0)
		<< " inUse=" << (inUse ? 1 : 0)
		<< " physical=" << (physical ? 1 : 0)
		<< " loadout3=0x" << std::hex << current
		<< " default=0x" << fallback
		<< " primary=0x" << primary
		<< " secondary=0x" << secondary << std::dec;
}

static void updateDualWieldGuard(Ped ped, DWORD now, bool mission) {
	if (now - g_dualWieldPollAt < kDualWieldPollMs) return;
	g_dualWieldPollAt = now;

	if (!ped || mission) {
		if (g_dualWieldPed != ped || g_dualWieldKnown)
			dualWieldLog(GT_INFO, std::string("gate=") +
				(!ped ? "no-ped" : "mission"));
		g_dualWieldPed = ped;
		g_dualWieldKnown = false;
		g_dualWieldRepairLatched = false;
		g_dualWieldReadbackPending = false;
		g_dualWieldEligibleSince = 0;
		if (!g_dualWieldHeartbeatAt ||
			now - g_dualWieldHeartbeatAt >= kDualWieldHeartbeatMs) {
			g_dualWieldHeartbeatAt = now;
			dualWieldLog(GT_INFO, std::string("heartbeat gate=") +
				(!ped ? "no-ped" : "mission") +
				" repairs=" + std::to_string(g_dualWieldRepairCount));
		}
		return;
	}

	if (g_dualWieldPed != ped) {
		g_dualWieldPed = ped;
		g_dualWieldKnown = false;
		g_dualWieldRepairLatched = false;
		g_dualWieldReadbackPending = false;
		g_dualWieldEligibleSince = 0;
		dualWieldLog(GT_INFO, "player ped observed=" + std::to_string(ped));
	}

	const Hash unlock = joaat("SP_WEAPON_DUALWIELD");
	const bool unlocked = UNLOCK::_UNLOCK_IS_UNLOCKED(unlock) != FALSE;
	const Hash expected = dualWieldExpectedHolster();
	const Hash current = dualWieldGlobalHash(kDualWieldCurrentLoadout3Global);
	const Hash fallback = dualWieldGlobalHash(kDualWieldDefaultLoadout3Global);
	const bool wheelOpen = dualWieldWheelOpen();
	const bool inventoryBusy = dualWieldInventoryBusy();
	const bool interactionBusy = ITEM_INTERACTION_RUNNING(ped);
	const bool playerControl = PLAYER_CONTROL_ON(PLAYER::PLAYER_ID());
	const bool physical = dualWieldPhysicalComponent(ped, expected);
	const int currentCount = current ? INVENTORY_ITEM_COUNT(current) : 0;
	const bool currentPhysical = dualWieldPhysicalComponent(ped, current);
	const bool missingComponent = current == 0 || current == kUnsetLoadout3 ||
		current == fallback || currentCount <= 0 ||
		(!currentPhysical && !physical);
	const int expectedCount = INVENTORY_ITEM_COUNT(expected);
	const bool safeRepairWindow = !wheelOpen && !inventoryBusy &&
		!interactionBusy && playerControl;
	if (unlocked && missingComponent && !physical && expectedCount > 0 &&
		safeRepairWindow) {
		if (!g_dualWieldEligibleSince) g_dualWieldEligibleSince = now;
	} else {
		g_dualWieldEligibleSince = 0;
	}
	const bool startupSettled = g_dualWieldEligibleSince &&
		now - g_dualWieldEligibleSince >= kDualWieldStartupSettleMs;

	if (g_dualWieldReadbackPending && now >= g_dualWieldReadbackAt) {
		std::ostringstream line;
		line << "repair settled ";
		dualWieldReadState(ped, g_dualWieldRepairItem, line);
		const bool postPhysical = dualWieldPhysicalComponent(
			ped, g_dualWieldRepairItem);
		const bool postAllow = dualWieldAllowed(ped);
		const bool postLoadout = dualWieldGlobalHash(
			kDualWieldCurrentLoadout3Global) == g_dualWieldRepairItem;
		dualWieldLog(postPhysical && postLoadout && postAllow ? GT_INFO : GT_ERROR,
			line.str());
		g_dualWieldReadbackPending = false;
	}

	// A non-default current LOADOUT_3 or the physical expected component means
	// the player's outfit owns this state.  Release the one-shot latch only after
	// an observed recovery so a later genuine disappearance can be repaired.
	if (!missingComponent || physical) g_dualWieldRepairLatched = false;

	if (!g_dualWieldKnown) {
		std::ostringstream line;
		line << "state ";
		dualWieldReadState(ped, expected, line);
		line << " currentCount=" << currentCount
			<< " currentPhysical=" << (currentPhysical ? 1 : 0);
		line << " wheel=" << (wheelOpen ? 1 : 0)
			<< " inventoryBusy=" << (inventoryBusy ? 1 : 0)
			<< " interactionBusy=" << (interactionBusy ? 1 : 0)
			<< " playerControl=" << (playerControl ? 1 : 0);
		dualWieldLog(GT_INFO, line.str());
		g_dualWieldKnown = true;
	}

	if (unlocked && missingComponent && !physical && expectedCount > 0 &&
		!g_dualWieldRepairLatched && startupSettled && safeRepairWindow) {
		g_dualWieldRepairLatched = true;
		g_dualWieldRepairItem = expected;
		std::ostringstream before;
		before << "repair begin ";
		dualWieldReadState(ped, expected, before);
		dualWieldLog(GT_WARN, before.str());

		const int beforeCount = expectedCount;
		// act_hunting_2.c func_397 first changes the requested LOADOUT_3 record,
		// then its command-19 wardrobe update applies that exact shop item to the
		// ped. The previous repair skipped the loadout transition and instead
		// edited the clothing inventory record. That failed its physical readback
		// and collided with the shared inventory layer used by shops. This bounded
		// recovery owns only the already-earned, already-owned LOADOUT_3 value.
		*getGlobalPtr(kDualWieldCurrentLoadout3Global) = (Any)expected;
		setDualWieldAllowed(ped, true);
		// natives.json resolves 0xD3A7B003ED343FD9 as
		// _APPLY_SHOP_ITEM_TO_PED. The decompiler's older
		// _SET_PED_COMPONENT_ENABLED name hid that distinction.
		invoke<Void>(0xD3A7B003ED343FD9,
			ped, expected, FALSE, FALSE, FALSE);
		invoke<Void>(0xAAB86462966168CE, ped, FALSE);
		invoke<Void>(0xCC8CA3E88256E58F,
			ped, FALSE, TRUE, TRUE, TRUE, FALSE);
		++g_dualWieldRepairCount;
		g_dualWieldReadbackPending = true;
		g_dualWieldReadbackAt = now + kDualWieldSettleMs;

		std::ostringstream immediate;
		immediate << "repair issued ownedBefore=" << beforeCount
			<< " inventoryMutation=0"
			<< " loadoutTransition=0x" << std::hex << expected << std::dec
			<< " repairCount=" << g_dualWieldRepairCount << " ";
		dualWieldReadState(ped, expected, immediate);
		dualWieldLog(dualWieldAllowed(ped) ? GT_INFO : GT_ERROR,
			immediate.str());
	} else if (!unlocked && missingComponent && !g_dualWieldKnown) {
		dualWieldLog(GT_INFO,
			"no repair: SP_WEAPON_DUALWIELD is not earned");
	}

	if (!g_dualWieldHeartbeatAt ||
		now - g_dualWieldHeartbeatAt >= kDualWieldHeartbeatMs) {
		g_dualWieldHeartbeatAt = now;
		std::ostringstream heartbeat;
		heartbeat << "heartbeat gate=active ";
		dualWieldReadState(ped, expected, heartbeat);
		heartbeat << " wheel=" << (wheelOpen ? 1 : 0)
			<< " expectedCount=" << expectedCount
			<< " currentCount=" << currentCount
			<< " currentPhysical=" << (currentPhysical ? 1 : 0)
			<< " inventoryBusy=" << (inventoryBusy ? 1 : 0)
			<< " interactionBusy=" << (interactionBusy ? 1 : 0)
			<< " playerControl=" << (playerControl ? 1 : 0)
			<< " missingComponent=" << (missingComponent ? 1 : 0)
			<< " startupSettleMs=" << (g_dualWieldEligibleSince ?
				now - g_dualWieldEligibleSince : 0)
			<< " repairs=" << g_dualWieldRepairCount
			<< " repairLatched=" << (g_dualWieldRepairLatched ? 1 : 0)
			<< " readbackPending=" << (g_dualWieldReadbackPending ? 1 : 0);
		dualWieldLog(GT_INFO, heartbeat.str());
	}
}
