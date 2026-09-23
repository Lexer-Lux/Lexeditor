// GitHub #114 - read-only shop-state probe.
//
// Six builds have guessed at this. This module guesses at nothing: it samples
// the exact Story Mode state that decides whether a shop has a clerk, whether
// its blip is locked, and whether its script may run, then prints it. It never
// writes an engine value, never creates or removes a blip, never starts or
// terminates a script and never registers a prompt.
//
// Primary sources, all under _downloads/RDR2-Decompiled-Scripts/script_rel/:
//   short_update.c  - shop controller: clerk resolution, availability mode,
//                     script launch (START_NEW_SCRIPT_WITH_ARGS at :37804,
//                     free-stack gate at :37795).
//   long_update.c   - persistent blips: presentation bits read by func_2371
//                     (:73915), LOCKED via func_2374 (:73959) testing bit
//                     16384, OUTSIDE_TOD via func_2375 (:73983) testing 32768,
//                     HIDDEN via func_2373 (:73934).
//   shop_general.c  - func_13 terminates the shop thread when the shop's bound
//                     location index is -1.
//
// ARRAY-BASE HONESTY. Script fixed arrays carry their capacity in the first
// cell, so a record base is `global + offset + 1 + index * stride`. #114's own
// mail reader shipped a whole diagnosis built on omitting that +1. Rather than
// repeat that, every indexed read below is emitted under BOTH interpretations,
// labelled `h1` (with the header skip) and `h0` (without). One launch then
// settles which is real instead of another correction round.

static bool g_shopProbeEnabled = true;
static DWORD g_shopProbeConfigAt = 0;
static DWORD g_shopProbeHeartbeatAt = 0;
static bool g_shopProbeStaticsLogged = false;

// short_update.c::func_2452 (:74790) type -> script name.
struct ShopProbeType { int type; const char* name; };
static const ShopProbeType kShopProbeTypes[] = {
	{ 0,  "shop_doctor" },
	{ 1,  "shop_train_station" },
	{ 2,  "shop_post_office" },
	{ 3,  "shop_general" },
	{ 6,  "shop_gunsmith" },
	{ 8,  "shop_barber" },
	{ 9,  "shop_horse_shop_sp" },
	{ 15, "shop_bank" },
	{ 22, "shop_newspaper_boy" },
	{ 33, "shop_bartender" },
};

// Global bases and strides taken from the decompiled field notation
// `Global_1914319.f_3[type /*446*/]`, `Global_1895087[slot /*3*/].f_1`,
// `Global_1914319.f_19001[loc*3].f_1`, `Global_1914319.f_15614[loc]`.
static constexpr int kShopProbeShopRoot = 1914319;
static constexpr int kShopProbeShopArray = 3;
static constexpr int kShopProbeShopStride = 446;
static constexpr int kShopProbePresentation = 15614;
static constexpr int kShopProbeModeArray = 19001;
static constexpr int kShopProbeModeStride = 3;
static constexpr int kShopProbePerscharRoot = 1895087;
static constexpr int kShopProbePerscharStride = 3;
static constexpr int kShopProbeStoryClock = 1899515;

static int shopProbeRead(int index) {
	return (int)*getGlobalPtr(index);
}

// `header` selects the +1 fixed-array capacity skip described above.
static int shopProbeShopField(int type, int field, bool header) {
	return shopProbeRead(kShopProbeShopRoot + kShopProbeShopArray +
		(header ? 1 : 0) + type * kShopProbeShopStride + field);
}

static int shopProbePresentationBits(int loc, bool header) {
	if (loc < 0) return 0;
	return shopProbeRead(kShopProbeShopRoot + kShopProbePresentation +
		(header ? 1 : 0) + loc);
}

static int shopProbeMode(int loc, bool header) {
	if (loc < 0) return -1;
	return shopProbeRead(kShopProbeShopRoot + kShopProbeModeArray +
		(header ? 1 : 0) + loc * kShopProbeModeStride + 1);
}

static int shopProbePerscharId(int slot, bool header) {
	if (slot < 0) return 0;
	return shopProbeRead(kShopProbePerscharRoot + (header ? 1 : 0) +
		slot * kShopProbePerscharStride + 1);
}

// PERSCHAR validity pair used by short_update.c::func_1181. Read-only queries.
static bool shopProbePerscharValid(int id) {
	return invoke<BOOL>(0x800DF3FC913355F3, id) != FALSE;
}

static int shopProbePerscharPed(int id) {
	return invoke<int>(0x31C70A716CAE1FEE, id);
}

// MISC::GET_NUMBER_OF_FREE_STACKS_OF_THIS_SIZE, hash resolved via
// _downloads/grep_natives.py, call site short_update.c:37797.
// VOLUME::DOES_VOLUME_EXIST, hash from _downloads/grep_natives.py.
// short_update.c::func_1236 (:39791) returns false when the shop's f_25 volume
// does not exist, which func_2460 turns into state 6 and func_1185 reports as
// mode 5 - printed to the player as SHOP_UNAVAILABLE_SHOPKEEPER_AGGROED even
// though no ped is aggroed. A live clerk with mode 5 therefore means "check the
// volume", not "check the shopkeeper".
static bool shopProbeVolumeExists(int volume) {
	return invoke<BOOL>(0x92A78D0BEDB332A3, volume) != FALSE;
}

static int shopProbeFreeStacks(int size) {
	return invoke<int>(0x40DC2907A9697EF7, size);
}

// Clerk-side reads. short_update.c::func_313 (:11245-11257) tags a resolved
// clerk with SET_PED_CONFIG_FLAG(ped, 130, true) and adds him to the
// "shop_keeper_group" audio mix. A clerk that resolves but is missing flag 130
// is exactly the reported symptom: the ped offers only the generic
// Rob / Greet / Antagonize options because nothing marked him as a vendor.
// func_2460 (:74972) additionally reaches its aggro states via IS_PED_FLEEING
// and GET_IS_TASK_ACTIVE(clerk, 0), so both are sampled here to separate
// "never tagged" from "tagged then displaced by a task".
static bool shopProbePedConfigFlag(int ped, int flagId) {
	return invoke<BOOL>(0x7EE53118C892B513, ped, flagId, FALSE) != FALSE;
}

static Hash shopProbeRelationshipGroup(int ped) {
	return invoke<Hash>(0x7DBDD04862D95F04, ped);
}

static bool shopProbePedFleeing(int ped) {
	return invoke<BOOL>(0xBBCCE00B381F8482, ped) != FALSE;
}

static bool shopProbeTaskActive(int ped, int taskIndex) {
	return invoke<BOOL>(0xB0760331C7AA4155, ped, taskIndex) != FALSE;
}

static const char* shopProbeModeName(int mode) {
	switch (mode) {
		case 1:  return "TOD";
		case 2:  return "LOCKDOWN";
		case 5:  return "SHOPKEEPER_AGGROED";
		case 10: return "SHOPKEEPER_DEAD";
		default: return "other";
	}
}

static void shopProbeEmitOnce() {
	if (g_shopProbeStaticsLogged) return;
	g_shopProbeStaticsLogged = true;
	// short_update.c:37795 gates every shop script launch on this, and all shop
	// families share stack size 6005. Zero here means no shop script can start
	// regardless of clerk or blip state.
	const int packed = shopProbeRead(kShopProbeStoryClock);
	GtLogStream("shop-probe", GT_INFO)
		<< "static freeStacks6005=" << shopProbeFreeStacks(6005)
		<< " storyClockRaw=" << packed
		<< " storyClockHour=" << ((packed >> 12) & 31)
		<< " clockHours=" << CLOCK::GET_CLOCK_HOURS()
		<< " clockYear=" << CLOCK::GET_CLOCK_YEAR()
		<< " writes=0 hooks=0\n";
}

// long_update.c::func_158 (:4736) allocates persistent script blips from the
// fixed array Global_36308: cell 0 is the capacity header, entries follow, and
// the allocator returns -1 and creates NOTHING once every slot is taken. Our
// mod adds collectible, recon, newspaper, horse-need and campfire blips, so an
// exhausted pool would stop Rockstar creating new shop blips while previously
// created ones stay on the map. Read-only occupancy count.
static constexpr int kShopProbeBlipPool = 36308;

static void shopProbeEmitBlipPool() {
	const int capacity = shopProbeRead(kShopProbeBlipPool);
	int handles = 0, live = 0;
	const int scan = (capacity > 0 && capacity <= 512) ? capacity : 250;
	for (int i = 0; i < scan; ++i) {
		const int blip = shopProbeRead(kShopProbeBlipPool + 1 + i);
		if (!blip) continue;
		++handles;
		if (invoke<BOOL>(0xCD82FA174080B3B1, blip) != FALSE) ++live;
	}
	GtLogStream("shop-probe", GT_INFO)
		<< "blipPool capacity=" << capacity
		<< " scanned=" << scan
		<< " nonZeroHandles=" << handles
		<< " liveBlips=" << live
		<< " freeSlots=" << (scan - handles)
		<< (handles >= scan ? " EXHAUSTED=1" : " EXHAUSTED=0") << "\n";
}

static void shopProbeEmitType(const ShopProbeType& entry, bool header) {
	const char tag = header ? '1' : '0';
	const int state = shopProbeShopField(entry.type, 1, header);
	const int flags = shopProbeShopField(entry.type, 7, header);
	const int loc = shopProbeShopField(entry.type, 10, header);
	const int thread = shopProbeShopField(entry.type, 18, header);
	const int radius = shopProbeShopField(entry.type, 19, header);
	const int perscharSlot = shopProbeShopField(entry.type, 21, header);
	const int clerkPed = shopProbeShopField(entry.type, 23, header);
	const int feed = shopProbeShopField(entry.type, 440, header);
	const int volume = shopProbeShopField(entry.type, 25, header);
	const int volumeExists = volume ? (shopProbeVolumeExists(volume) ? 1 : 0) : -1;
	int clerkFlag130 = -1, clerkFleeing = -1, clerkTask0 = -1;
	Hash clerkRelGroup = 0;
	if (clerkPed && ENTITY::DOES_ENTITY_EXIST(clerkPed)) {
		clerkFlag130 = shopProbePedConfigFlag(clerkPed, 130) ? 1 : 0;
		clerkFleeing = shopProbePedFleeing(clerkPed) ? 1 : 0;
		clerkTask0 = shopProbeTaskActive(clerkPed, 0) ? 1 : 0;
		clerkRelGroup = shopProbeRelationshipGroup(clerkPed);
	}
	const int bits = shopProbePresentationBits(loc, header);
	const int mode = shopProbeMode(loc, header);

	// THE PRIMARY HYPOTHESIS. If the clerk's persistent character stops being
	// valid, short_update yields availability mode 10 SHOPKEEPER_DEAD, clears
	// the clerk entity, and tears the shop down - which sets the bound location
	// to -1 and is exactly shop_general.c::func_13's terminate condition.
	int perscharId = 0, perscharPed = 0;
	int perscharValid = -1;
	if (perscharSlot >= 0 && perscharSlot < 954) {
		perscharId = shopProbePerscharId(perscharSlot, header);
		if (perscharId) {
			perscharValid = shopProbePerscharValid(perscharId) ? 1 : 0;
			if (perscharValid) perscharPed = shopProbePerscharPed(perscharId);
		}
	}

	GtLogStream("shop-probe", GT_INFO)
		<< "h" << tag << " type=" << entry.type << " (" << entry.name << ")"
		<< " state=" << state
		<< " flags=0x" << std::hex << (uint32_t)flags << std::dec
		<< " loc=" << loc
		<< " thread=" << thread
		<< " radius=" << radius
		<< " clerkPed=" << clerkPed
		<< " feed=" << feed
		<< " volume=" << volume
		<< " volumeExists=" << volumeExists
		<< " clerkFlag130=" << clerkFlag130
		<< " clerkFleeing=" << clerkFleeing
		<< " clerkTask0=" << clerkTask0
		<< " clerkRelGroup=0x" << std::hex << (uint32_t)clerkRelGroup << std::dec
		<< " perscharSlot=" << perscharSlot
		<< " perscharId=0x" << std::hex << (uint32_t)perscharId << std::dec
		<< " perscharValid=" << perscharValid
		<< " perscharPed=" << perscharPed
		<< " presentationBits=0x" << std::hex << (uint32_t)bits << std::dec
		<< " HIDDEN=" << ((bits & 32) ? 1 : 0)
		<< " LOCKED=" << ((bits & 16384) ? 1 : 0)
		<< " OUTSIDE_TOD=" << ((bits & 32768) ? 1 : 0)
		<< " mode=" << mode << " (" << shopProbeModeName(mode) << ")"
		<< "\n";
}

// ---------------------------------------------------------------------------
// #114 WATCHPOINT
//
// Removing GameplayTweaks restores shops, so the culprit is inside this ASI.
// This samples a small fixed set of shop cells at every dispatcher stage
// boundary and reports the exact interval in which one of them changes, naming
// the stage that ran immediately before. It performs no write of any kind.
//
// Watched cells, all on the proven h1 base:
//   f_3[3].f_1   general-store state machine
//   f_3[3].f_18  shop thread id      (churns when the shop restarts)
//   f_3[3].f_21  perschar slot       (was stable when healthy)
//   f_3[3].f_25  volume handle       (churns when broken)
//   f_15614[loc] blip presentation bits, incl. bit 16384 LOCKED
// ---------------------------------------------------------------------------

static bool g_shopWatchArmed = false;
static const char* g_shopWatchLastStage = "frame-boundary";
static int g_shopWatchPrev[5] = {};
static bool g_shopWatchSeeded = false;
static unsigned g_shopWatchReports = 0;

static void shopWatchRead(int out[5]) {
	out[0] = shopProbeShopField(3, 1, true);
	out[1] = shopProbeShopField(3, 18, true);
	out[2] = shopProbeShopField(3, 21, true);
	out[3] = shopProbeShopField(3, 25, true);
	const int loc = shopProbeShopField(3, 10, true);
	out[4] = (loc >= 0) ? shopProbePresentationBits(loc, true) : 0;
}

static void shopWatchStage(const char* stage) {
	if (!g_shopWatchArmed) return;
	int now5[5];
	shopWatchRead(now5);
	if (!g_shopWatchSeeded) {
		for (int i = 0; i < 5; ++i) g_shopWatchPrev[i] = now5[i];
		g_shopWatchSeeded = true;
		g_shopWatchLastStage = stage;
		return;
	}
	static const char* kNames[5] = { "state", "thread", "perscharSlot",
		"volume", "presentationBits" };
	for (int i = 0; i < 5; ++i) {
		if (now5[i] == g_shopWatchPrev[i]) continue;
		// Cap the report volume so a fast-changing cell cannot flood the log and
		// push the first, most useful observations out of the rotation.
		if (g_shopWatchReports < 400) {
			++g_shopWatchReports;
			GtLogStream("shop-watch", GT_WARN)
				<< "CHANGED field=" << kNames[i]
				<< " from=" << g_shopWatchPrev[i]
				<< " to=" << now5[i]
				<< " afterStage=" << (g_shopWatchLastStage ? g_shopWatchLastStage : "?")
				<< " atStage=" << (stage ? stage : "?")
				<< " report=" << g_shopWatchReports << "\n";
		}
		g_shopWatchPrev[i] = now5[i];
	}
	g_shopWatchLastStage = stage;
}

static void updateShopStateProbe(Ped playerPed, DWORD now) {
	if (!g_shopProbeConfigAt || now - g_shopProbeConfigAt >= 2000) {
		g_shopProbeConfigAt = now;
		g_shopProbeEnabled = readB("ShopStateProbe", "Enabled", true);
	}
	if (!g_shopProbeEnabled) return;
	if (!playerPed || !ENTITY::DOES_ENTITY_EXIST(playerPed)) return;
	// Idle heartbeat only. A silent log therefore proves the probe did not run,
	// rather than leaving "not executed" indistinguishable from "no result".
	// Two seconds, not ten. The reported failure includes a prompt that appears
	// and then blanks out, and a 10 s cadence cannot see that transition at all.
	if (g_shopProbeHeartbeatAt && now - g_shopProbeHeartbeatAt < 2000) return;
	g_shopProbeHeartbeatAt = now;

	shopProbeEmitOnce();
	shopProbeEmitBlipPool();
	// Arm only once a shop is actually bound, so the boundary sweep costs
	// nothing during loading or out in the world.
	if (!g_shopWatchArmed && shopProbeShopField(3, 10, true) >= 0) {
		g_shopWatchArmed = true;
		g_shopWatchStageHook = &shopWatchStage;
		GtLogStream("shop-watch", GT_INFO)
			<< "armed watching general-store state/thread/perscharSlot/volume"
			<< " and its presentation bits at every dispatcher stage boundary\n";
	}
	// h1 is settled: the perschar chain resolves to the same ped the shop holds
	// as its clerk, which the h0 base could never produce. Only h1 is emitted
	// now, and only for shops actually bound to a location, so a session spent
	// standing at one counter is readable instead of 20 rows of -1.
	for (const ShopProbeType& entry : kShopProbeTypes) {
		if (shopProbeShopField(entry.type, 10, true) < 0) continue;
		shopProbeEmitType(entry, true);
	}
	GtLogStream("shop-probe", GT_INFO)
		<< "heartbeat types=" << (sizeof(kShopProbeTypes) / sizeof(kShopProbeTypes[0]))
		<< " freeStacks6005=" << shopProbeFreeStacks(6005)
		<< " readOnly=1 writes=0 hooks=0\n";
}
