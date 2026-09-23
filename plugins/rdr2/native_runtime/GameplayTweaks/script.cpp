/*
	GameplayTweaks — native-driven gameplay changes, ini-tunable (hot-reload
	every 2s). All effects apply per-frame via natives.

	  Minimap        base radar zoom (TODO #4)
	  HumanStamina   drain + recovery multipliers for the player (TODO #11)
	  HorseStamina   drain + recovery multipliers for the current mount (#11)
	  AnimalDensity  global ambient animal spawn multiplier (TODO #7)
	  CoreClock      cores drain by game time; sleep refills Dead Eye (#21)
	  NoReserveCores outer bars cannot spend their cores as backup reserves
	  WagonCores     moving draft vehicles drain attached horses' outer stamina (#3)
	  TrainTracking  map blips from the engine's active track manager (#20)
	  Collectibles   persistent category-filtered collectible map markers (#28)
	  BanditMasks    challenge-mask powers and honor-sensitive shop prices
	  SpentCasings   physical, collectible firearm casings replacing shell VFX
	  CombatRoll     replaces the weapon-out dive with a directional dodge roll,
	                 on the Dive input only, never the Jump input (#208)
	  Binoculars     hold F / RS-click to look through owned binos (#116)
	  ReconTagging   binocular-marked peds with HUD health/distance and minimap blips
*/
#include "main.h"
#include "natives.h"
#include "development_build.h"
#include <windows.h>
#include <Xinput.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

// Temporary crash tracer for the startup regression introduced by the
// 2026-08-06 combined build. It preserves the current update-stage name and
// records fatal first-chance exceptions before Rockstar replaces them with the
// generic FFFFFFFF dialog. Remove after the offending call is repaired.
static const char* volatile g_crashTraceStage = "dll startup";
static char g_crashTracePath[MAX_PATH] = {};

static LONG CALLBACK gameplayTweaksCrashTrace(PEXCEPTION_POINTERS exception) {
	if (!exception || !exception->ExceptionRecord) return EXCEPTION_CONTINUE_SEARCH;
	const DWORD code = exception->ExceptionRecord->ExceptionCode;
	if (code != EXCEPTION_ACCESS_VIOLATION && code != EXCEPTION_ILLEGAL_INSTRUCTION &&
		code != EXCEPTION_STACK_OVERFLOW && code != EXCEPTION_ARRAY_BOUNDS_EXCEEDED &&
		code != EXCEPTION_DATATYPE_MISALIGNMENT)
		return EXCEPTION_CONTINUE_SEARCH;

	const void* address = exception->ExceptionRecord->ExceptionAddress;
	HMODULE module = nullptr;
	char modulePath[MAX_PATH] = "unknown";
	ULONGLONG moduleOffset = 0;
	if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
		GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
		reinterpret_cast<LPCSTR>(address), &module) && module) {
		GetModuleFileNameA(module, modulePath, MAX_PATH);
		moduleOffset = reinterpret_cast<ULONGLONG>(address) -
			reinterpret_cast<ULONGLONG>(module);
	}

	char line[1024] = {};
	const int length = sprintf_s(line,
		"tick=%lu code=0x%08lX address=%p module=%s offset=0x%llX stage=%s\r\n",
		GetTickCount(), code, address, modulePath, moduleOffset,
		g_crashTraceStage ? g_crashTraceStage : "unknown");
	if (length > 0 && g_crashTracePath[0]) {
		HANDLE file = CreateFileA(g_crashTracePath, FILE_APPEND_DATA,
			FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
			FILE_ATTRIBUTE_NORMAL, nullptr);
		if (file != INVALID_HANDLE_VALUE) {
			DWORD written = 0;
			WriteFile(file, line, static_cast<DWORD>(length), &written, nullptr);
			FlushFileBuffers(file);
			CloseHandle(file);
		}
	}
	return EXCEPTION_CONTINUE_SEARCH;
}

// #114 watchpoint hook. Lexer's own experiment already settled that removing
// GameplayTweaks restores shops, so the remaining question is WHICH part of it
// corrupts the shop array. Every dispatcher stage boundary is already marked
// below, so routing the marker through an optional hook turns all of them into
// checkpoints at once: the shop probe samples the watched cells on each
// transition and reports the exact stage interval a change lands in. The hook
// is null until the probe installs it, so startup marking is unaffected.
static void (*g_shopWatchStageHook)(const char*) = nullptr;
#define CRASH_TRACE_STAGE(name) (g_crashTraceStage = (name), 	g_shopWatchStageHook ? g_shopWatchStageHook(name) : (void)0)

// FREEZE WATCHDOG, 2026-08-07.
//
// The vectored handler above only fires on a fatal EXCEPTION. Lexer's game is
// HANGING, so it never fires and no crash-trace file is ever produced - every
// subsystem log simply stops at the same instant, which says "we froze" but not
// "where".
//
// This thread is independent of the script thread, so it keeps running while
// the script thread is blocked. It samples g_crashTraceStage - the name of the
// update stage currently executing - and rewrites it to a small file. When the
// game freezes, the LAST line names the stage that was running when everything
// stopped. `ticks` is the script thread's own counter: if it stops advancing
// while the watchdog keeps writing, the script thread is wedged inside that
// named stage.
static std::atomic<unsigned long long> g_watchdogScriptTicks{ 0 };
static char g_watchdogPath[MAX_PATH] = {};

static DWORD WINAPI gameplayTweaksWatchdog(LPVOID) {
	unsigned long long lastTicks = ~0ull;
	int stall = 0;
	for (;;) {
		Sleep(250);
		if (!g_watchdogPath[0]) continue;
		const unsigned long long ticks = g_watchdogScriptTicks.load();
		stall = (ticks == lastTicks) ? stall + 1 : 0;
		lastTicks = ticks;
		char line[512] = {};
		const int length = sprintf_s(line,
			"tick=%lu scriptTicks=%llu stalledSamples=%d stage=%s\r\n",
			GetTickCount(), ticks, stall,
			g_crashTraceStage ? g_crashTraceStage : "unknown");
		if (length <= 0) continue;
		HANDLE file = CreateFileA(g_watchdogPath, FILE_APPEND_DATA,
			FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
			FILE_ATTRIBUTE_NORMAL, nullptr);
		if (file == INVALID_HANDLE_VALUE) continue;
		DWORD written = 0;
		WriteFile(file, line, (DWORD)length, &written, nullptr);
		FlushFileBuffers(file);
		CloseHandle(file);
	}
	return 0;
}

// #126. Included this early because script.cpp itself logs long before the
// feature modules are included, and every module below logs through gtLog().
#include "modules/unified_log.cpp"

static Hash joaat(const char* s);
static std::string g_moduleDir;
static void drawReconText(const char* text, float x, float y);
// Every build starts with authoring disabled.  A development build still has
// the shared Tilde edge, but editor/trace code cannot enter the first Story
// frames before Rockstar's ambient and shop owners have initialized.
static bool g_runtimeDevelopmentMode = GameplayTweaksBuild::Development;
static bool developmentModeActive() {
	return g_runtimeDevelopmentMode;
}
// #23: the fortification live calibrator and the camera editor share the
// numpad.  The active calibrator owns those keys for the entire frame so one
// adjustment can never silently change both feature profiles.
static bool g_fortificationCalibrationOwnsNumpad = false;

// _DRAW_MARKER takes a marker-type HASH, and "MARKER_TYPE_CYLINDER" was an
// invented name - it appears nowhere in the game, in any casing, so it hashed
// to a type the renderer does not know and drew NOTHING. That is why the
// tracers could not be seen. 0x94FDAE17 is the tall thin vertical cylinder
// Rockstar's own scripts draw with (fm_mission_controller, fm_deathmatch_
// controller), used there with the same p19=2 we pass.
static const Hash kMarkerVerticalCylinder = 0x94FDAE17;
// hashes from the alloc8or native db (multiplier natives take a float value)
static Ped   GET_MOUNT(Ped p) { return invoke<Ped>(0xE7E11B8DCBED1058, p); }
static Ped   GET_OWNED_MOUNT(Player p) { return invoke<Ped>(0xF49F14462F0AE27C, p); }
static Vector3 ENTITY_COORDS(Entity e) { return invoke<Vector3>(0xA86D5F069399F44D, e, TRUE, FALSE); }
static void ADD_ATTRIBUTE_POINTS(Ped p, int attribute, int points) { invoke<Void>(0x75415EE0CB583760, p, attribute, points); }
static void  SET_PLAYER_STAMINA_RECHARGE(Player p, float m) { invoke<Void>(0xFECA17CF3343694B, p, m); }
static void  SET_PLAYER_SPRINT_DEPLETION(Player p, float m) { invoke<Void>(0xBBADFB5E5E5766FB, p, m); }
static void  SET_PED_STAMINA_DEPLETION(Ped p, float m) { invoke<Void>(0xEF5A3D2285D8924B, p, m); }
static void  SET_PED_STAMINA_RECHARGE(Ped p, float m) { invoke<Void>(0x345C9F993A8AB4A4, p, m); }
static void  SET_ANIMAL_DENSITY(float m) { invoke<Void>(0xC0258742B034DFAF, m); }
static void  SET_SCENARIO_ANIMAL_DENSITY(float m) { invoke<Void>(0xDB48E99F8E064E56, m); }
static Vehicle GET_VEHICLE(Ped p) { return invoke<Vehicle>(0x9A9112A0FE9A4713, p, FALSE); }
static bool IS_DRAFT(Vehicle v) { return invoke<BOOL>(0xEA44E97849E9F3DD, v) != 0; }
static Ped GET_DRAFT_HORSE(Vehicle v, int slot) { return invoke<Ped>(0xA8BA0BAE0173457B, v, slot); }
static float ENTITY_SPEED(Entity e) { return invoke<float>(0xFB6BA510A533DF81, e); }
static bool TRAIN_ON_TRACK(int track) { return invoke<BOOL>(0xC29996A337BDD099, track) != 0; }
static Vector3 TRAIN_TRACK_POS(int track) { return invoke<Vector3>(0x1E8A921112891651, track); }
static Blip ADD_COORD_BLIP(Hash style, Vector3 p) { return invoke<Blip>(0x554D9D53F696D002, style, p.x, p.y, p.z); }
static void SET_BLIP_POS(Blip b, Vector3 p) { invoke<Void>(0x4FF674F5E23D49CE, b, p.x, p.y, p.z); }
static void SET_BLIP_ICON(Blip b, Hash icon) { invoke<Void>(0x74F74D3207ED525C, b, icon, TRUE); }
static void ADD_BLIP_MODIFIER(Blip b, Hash modifier) { invoke<Void>(0x662D364ABF16DE2F, b, modifier); }
static void SET_BLIP_SCALE(Blip b, float scale) { invoke<Void>(0xD38744167B2FA257, b, scale); }
static void SET_BLIP_NAME(Blip b, const char* name) { invoke<Void>(0x9CB1A1623062F402, b, name); }
static void REMOVE_MAP_BLIP(Blip* b) { invoke<Void>(0xF2C3C9DA47AAA54A, b); }
static int   GET_CORE(Ped p, int core) { return invoke<int>(0x36731AC041289BB1, p, core); }
// Rockstar's player_horse.c func_644 writes horse Health/Stamina cores through
// _SET_ATTRIBUTE_CORE_VALUE only. SET_ATTRIBUTE_POINTS is player progression
// state and can change a horse's maximum outer bar when misapplied to a mount.
static void  SET_HORSE_CORE(Ped horse, int core, int value) { invoke<Void>(0xC6258F41D86676E0, horse, core, value); }
// Current core fill and permanent attribute progression are different stores.
// SET_ATTRIBUTE_POINTS changes Health/Stamina/Dead Eye progression and therefore
// their maximum outer rings. Feeding CoreClock's ordinary 0..100 fill values to
// it corrupted the saved maxima on restart (Dead Eye 0, Health/Stamina ~25).
// CoreClock must write only the derived 0..100 core value.
static void  SET_CORE(Ped p, int core, int value) {
	invoke<Void>(0xC6258F41D86676E0, p, core, value);
}
static float GET_HEALTH_BAR(Player p) { return invoke<float>(0x0317C947D062854E, p); }
static float GET_STAMINA_BAR(Player p) { return invoke<float>(0x0FF421E467373FCF, p); }
static float GET_PED_STAMINA(Ped p) { return invoke<float>(0x775A1CA7893AA8B5, p); }
static float GET_PED_MAX_STAMINA(Ped p) { return invoke<float>(0xCB42AFE2B613EE55, p); }
static Hash  GET_CURRENT_WEAPON(Ped p) { Hash weapon = 0; invoke<BOOL>(0x3A87E44BB9A01D54, p, &weapon, TRUE, 0, FALSE); return weapon; }
// A weapon does not have a "drawn" flag - it has an ATTACH POINT, and the point
// it sits on IS its state. The map below is derived from Rockstar's own scripts
// (every literal SET_CURRENT_PED_WEAPON call in script_rel, bucketed by slot),
// not guessed: 0 in use, 1 off-hand, 2/3 right/left hip holster (revolvers
// only), 4 knife sheath, 7 bow sling, 9 and 10 the two LONGARM slots on his
// back (repeaters, rifles, shotguns and nothing else).
// p3 MUST be false for a slot query. Rockstar never passes true with a slot
// index: it is `true, 0, false` when they want "his current weapon" and
// `false, N, false` when they want "what is sitting on point N" (script_rel
// uses the second form for points 0, 2, 7, 8, 9 and 10). Passing true with a
// slot asks a question the native does not answer.
static Hash  GET_WEAPON_AT_ATTACH_POINT(Ped p, int attachPoint) {
	Hash weapon = 0;
	invoke<BOOL>(0x3A87E44BB9A01D54, p, &weapon, FALSE, attachPoint, FALSE);
	return weapon;
}
// Documented as "unequip current weapon and set current weapon to
// WEAPON_UNARMED" - this is the same path taken when you pick fists, which is
// the behaviour Lexer confirmed actually puts a longarm away.
static void  HIDE_PED_WEAPONS(Ped p, int mode, bool immediately) { invoke<Void>(0xFCCC886EDE3C63EC, p, mode, immediately ? TRUE : FALSE); }
static int   GET_CLIP_AMMO(Ped p, Hash weapon) { int ammo = -1; return invoke<BOOL>(0x2E1202248937775C, p, &ammo, weapon) ? ammo : -1; }
// #78. THIS IS NOT A PERCENTAGE AND IT IS NOT THE OUTER RING.
// 0xA81D24AE0AF99A5E is `_GET_PLAYER_DEAD_EYE`
// (_downloads/NativeMenuBase/.../inc/natives.h:7897) - the RAW absolute Dead Eye
// amount, i.e. outer ring PLUS the core reserve this item exists to fence off.
// Measured in GameplayTweaks.reserve.log at rest: `deadeye=133.56 core=77`.
// It is therefore NOT on a 0..100 scale, and worklog/issues/github-78.md records
// it bottoming at ~25-28 while the rendered ring was already empty. Any
// comparison of this value against a PERCENT threshold, or against ~0 as
// "empty", is unreachable by construction - which is what previous builds did in
// two decisive places and is why Dead Eye could be used forever.
// Its only sound use is as a diagnostic. Do not gate behaviour on it.
static float GET_DEADEYE_RAW(Player p) { return invoke<float>(0xA81D24AE0AF99A5E, p); }
// Back-compatible alias. #125's updateDeadeyeConsumption and
// modules/combat_inventory.cpp:744 read this native as a closed-loop measurement
// of drain RATE, where the absolute scale cancels out and the value is sound.
// #78 must not use it; it is renamed above so that misuse is visible at the call
// site rather than hidden behind a name that says "bar".
static float GET_DEADEYE_BAR(Player p) { return GET_DEADEYE_RAW(p); }
// _GET_PLAYER_DEAD_EYE_METER_LEVEL (natives.h:7896). WHICH PARAMETER SELECTS THE
// OUTER RING IS NOT PROVEN, and the previous comment here claimed it was.
// What the corpus actually shows:
//   TRUE  form: rcm_bh_skinner_search.c:19848/:19853 test it for exactly 0f and
//               >0f during ordinary play (a transient meter).
//   FALSE form: shop_doctor.c:11014 and :11049 compare it with 0.5f alongside
//               half health, and winter4.c:37843 with >0f (a condition check).
// Both forms are normalized; neither citation identifies ring vs core. This is
// logged, and used only as a RELEASE hysteresis test, never as the exhaustion
// trigger - the trigger below is scale-free.
static float GET_DEADEYE_METER_LEVEL(Player p) { return invoke<float>(0x3A6AE4EEE30370FE, p, FALSE); }
static float GET_DEADEYE_METER_LEVEL_ALT(Player p) { return invoke<float>(0x3A6AE4EEE30370FE, p, TRUE); }
// REMOVED: `DEACTIVATE_SPECIAL_ABILITY(Player)` wrapping 0x1D77B47AFA584E90.
// That native is `_SPECIAL_ABILITY_START_RESTORE(Player player, int p1, BOOL p2)`
// (natives.h:7882) - three arguments, and a RESTORE, not a deactivate. All 20
// Story Mode call sites pass three (gang1.c:25440 `(PLAYER_ID(), -1, true)`).
// The wrapper passed ONE, so the native read p1/p2 from unset argument slots
// every frame the exhaustion latch held while Dead Eye was active.
// Rockstar's own end-Dead-Eye idiom needs neither: where they want an active
// ability to stop they test 0xB16223CB7DA965F0 and then call
// 0xAE637BB8EF017875(player, 1) - SET_DEADEYE_DISABLED - which the latch below
// already does. See abigail2_1.c:75189-75191 for the pair.
static int   GET_ATTRIBUTE_POINTS(Ped p, int attribute) { return invoke<int>(0x219DA04BAA9CB065, p, attribute); }
static void  SET_ATTRIBUTE_POINTS(Ped p, int attribute, int points) { invoke<Void>(0x09A59688C26D88DF, p, attribute, points); }
static int   GET_ATTRIBUTE_BASE_RANK(Ped p, int attribute) { return invoke<int>(0x147149F2E909323C, p, attribute); }
static void  SET_ATTRIBUTE_BASE_RANK(Ped p, int attribute, int rank) { invoke<Void>(0x5DA12E025D47D4E5, p, attribute, rank); }
static bool  DEADEYE_ENABLED(Player p) { return invoke<BOOL>(0xDE6C85975F9D4894, p) != 0; }
static void  SET_DEADEYE_DISABLED(Player p, bool disabled) { invoke<Void>(0xAE637BB8EF017875, p, disabled); }
// GitHub #125. Unlike the rejected 0x22B3... guess, this native is named and
// typed by the native database as _SET_SPECIAL_ABILITY_DURATION_COST, with
// durationCost explicitly documented as "per second". Passing 0 clears the
// override; Rockstar uses that same reset in its special-ability cleanup.
static void  SET_DEADEYE_DURATION_COST(Player p, float pointsPerSecond) {
	invoke<Void>(0xB783F75940B23014, p, pointsPerSecond);
}
static int   GET_ENTITY_HEALTH(Entity e) { return invoke<int>(0x82368787EA73C0F7, e); }
static void  SET_ENTITY_HEALTH(Entity e, int value) { invoke<Void>(0xAC2767ED8BDFAB15, e, value, 0); }
static float GET_PLAYER_HEALTH_RECHARGE_MULTIPLIER(Player p) {
	return invoke<float>(0x22CD23BB0C45E0CD, p);
}
static void  START_STATUS_ICON(int status) { invoke<Void>(0xFB6E111908502871, status); }
static void  STOP_STATUS_ICON(int status) { invoke<Void>(0x3FC4C027FD0936F4, status); }
static void  DISABLE_CONTROL(int group, Hash control) { invoke<Void>(0xFE99B66D079CF6BC, group, control, TRUE); }
static void  SET_CONTROL_NORMAL(int group, Hash control, float amount) { invoke<BOOL>(0xE8A25867FBA3B05E, group, control, amount); }
static void  CLEAR_PED_SECONDARY_TASK(Ped p) { invoke<Void>(0x176CECF6F920D707, p); }
static void  SET_PED_CURRENT_WEAPON_VISIBLE(Ped p, BOOL vis, BOOL deselect, BOOL p3, BOOL p4) { invoke<Void>(0x0725A4CCFDED9A70, p, vis, deselect, p3, p4); }
static int   GET_PED_AMMO_BY_TYPE(Ped p, Hash ammoType) { return invoke<int>(0x39D22031557946C1, p, ammoType); }
static void  SET_PED_AMMO_BY_TYPE(Ped p, Hash ammoType, int ammo) { invoke<Void>(0x5FD1E1F011E76D7E, p, ammoType, ammo); }
static float GET_DESIRED_MOVE_BLEND(Ped p) { return invoke<float>(0x8517D4A6CA8513ED, p); }
static bool  IS_PED_RUNNING(Ped p) { return invoke<BOOL>(0xC5286FFC176F28A2, p) != 0; }
static bool  IS_PED_SPRINTING(Ped p) { return invoke<BOOL>(0x57E457CD2C0FC168, p) != 0; }
static int   CLOCK_HOUR() { return invoke<int>(0xC82CF208C2B19199); }
static int   CLOCK_MINUTE() { return invoke<int>(0x4E162231B823DBBF); }
static bool  SCREEN_FADED_OUT() { return invoke<BOOL>(0xF5472C80DF2FF847) != 0; }
static bool  PLAYER_CONTROL_ON(Player p) { return invoke<BOOL>(0x7964097FCE4C244B, p) != 0; }
static int   INVENTORY_ITEM_COUNT(Hash item) { return invoke<int>(0xE787F05DFC977BDE, 1, item, FALSE); }
static bool  INVENTORY_ITEM_EQUIPPED(Hash item) { return invoke<BOOL>(0x3D10D7179D7034AF, 1, item, FALSE) != 0; }
static void  INVENTORY_DISABLE_ITEM(Hash item) { invoke<Void>(0x766315A564594401, 1, item, 0); }
static void  INVENTORY_ENABLE_ITEM(Hash item) { invoke<Void>(0x6A564540FAC12211, 1, item); }
struct InventoryGuid { Any data[4]; };
static_assert(sizeof(InventoryGuid) == 32, "RDR2 inventory GUID must be four 64-bit script slots");
static bool INVENTORY_GUID_FROM_ITEM(InventoryGuid* parent, Hash item, Hash slot, InventoryGuid* out) { return invoke<BOOL>(0x886DFD3E185C8A89, 1, parent, item, slot, out) != 0; }
static bool INVENTORY_GUID_VALID(InventoryGuid* guid) { return invoke<BOOL>(0xB881CA836CC4B6D4, guid) != 0; }
static Hash INVENTORY_ITEM_SLOT(Hash item, Hash container) { return invoke<Hash>(0x6452B1D357D81742, item, container); }
static bool INVENTORY_FITS_SLOT(Hash item, Hash slot) { return invoke<BOOL>(0x780C5B9AE2819807, item, slot) != 0; }
static void INVENTORY_SET_HIDDEN(InventoryGuid* guid, bool hidden) { invoke<Void>(0x9A113C660AEA3832, 1, guid, hidden ? TRUE : FALSE); }
static void INVENTORY_SET_HIDDEN_SATCHEL(InventoryGuid* guid, bool hidden) { invoke<Void>(0xD740F11FBC8AEF43, 1, guid, hidden ? TRUE : FALSE); }
static void INVENTORY_SET_CLOTHING_ACTIVE(InventoryGuid* guid, bool active) { invoke<Void>(0x65A5F70F4A292EBE, 1, guid, active ? TRUE : FALSE); }
static bool INVENTORY_CLOTHING_ACTIVE(InventoryGuid* guid) { return invoke<BOOL>(0x70E3A884ED000A01, 1, guid) != FALSE; }
static int INVENTORY_GUID_COUNT(InventoryGuid* guid) { return invoke<int>(0xC97E0D2302382211, 1, guid, FALSE); }
static int INVENTORY_SATCHEL_ITEM_COUNT(Hash item) {
	InventoryGuid empty = {}, root = {}, itemGuid = {};
	INVENTORY_GUID_FROM_ITEM(&empty, joaat("CHARACTER"), joaat("SLOTID_NONE"), &root);
	if (!INVENTORY_GUID_VALID(&root)) return -1;
	INVENTORY_GUID_FROM_ITEM(&root, item, joaat("SLOTID_SATCHEL"), &itemGuid);
	if (!INVENTORY_GUID_VALID(&itemGuid)) return -1;
	return INVENTORY_GUID_COUNT(&itemGuid);
}
static bool INVENTORY_MOVE(InventoryGuid* item, InventoryGuid* destination, Hash slot, InventoryGuid* out) {
	return invoke<BOOL>(0xDCCAA7C3BFD88862, 1, item, destination, slot, 1, out) != 0;
}
static bool INVENTORY_ADD(Hash item, int quantity) {
	InventoryGuid empty = {}, root = {}, itemGuid = {};
	INVENTORY_GUID_FROM_ITEM(&empty, joaat("CHARACTER"), joaat("SLOTID_NONE"), &root);
	if (!INVENTORY_GUID_VALID(&root)) return false;
	INVENTORY_GUID_FROM_ITEM(&root, item, joaat("SLOTID_SATCHEL"), &itemGuid);
	// ADD_REASON_DEFAULT is what 1062 of the game's own scripts pass; the
	// previous "ADD_REASON_NOTIFICATION" appears in ZERO game scripts
	// (fabricated value), which is why grants were silent.
	return invoke<BOOL>(0xCB5D11F9508A928D, 1, &itemGuid, &root, item, joaat("SLOTID_SATCHEL"), quantity, joaat("ADD_REASON_DEFAULT")) != 0;
}
static bool INVENTORY_ADD_CLOTHING(Hash item, int quantity, int* stage) {
	if (stage) *stage = 1;
	InventoryGuid empty = {}, root = {}, destination = {}, itemGuid = {};
	INVENTORY_GUID_FROM_ITEM(&empty, joaat("CHARACTER"), joaat("SLOTID_NONE"), &root);
	if (!INVENTORY_GUID_VALID(&root)) return false;
	destination = root;
	Hash slot = joaat("SLOTID_WARDROBE");
	if (!INVENTORY_FITS_SLOT(item, slot)) {
		if (stage) *stage = 2;
		INVENTORY_GUID_FROM_ITEM(&root, joaat("WARDROBE"), joaat("SLOTID_WARDROBE"), &destination);
		if (!INVENTORY_GUID_VALID(&destination)) return false;
		if (stage) *stage = 3;
		slot = INVENTORY_ITEM_SLOT(item, joaat("WARDROBE"));
		if (!slot) return false;
	}
	if (stage) *stage = 4;
	INVENTORY_GUID_FROM_ITEM(&destination, item, slot, &itemGuid);
	if (stage) *stage = 5;
	const bool added = invoke<BOOL>(0xCB5D11F9508A928D, 1, &itemGuid, &destination,
		item, slot, quantity, joaat("ADD_REASON_DEFAULT")) != 0;
	if (stage) *stage = added ? 0 : 6;
	return added;
}
static bool INVENTORY_CLOTHING_GUID(Hash item, InventoryGuid* out) {
	InventoryGuid empty = {}, root = {}, destination = {};
	INVENTORY_GUID_FROM_ITEM(&empty, joaat("CHARACTER"), joaat("SLOTID_NONE"), &root);
	if (!INVENTORY_GUID_VALID(&root)) return false;
	destination = root;
	Hash slot = joaat("SLOTID_WARDROBE");
	if (!INVENTORY_FITS_SLOT(item, slot)) {
		INVENTORY_GUID_FROM_ITEM(&root, joaat("WARDROBE"), joaat("SLOTID_WARDROBE"), &destination);
		if (!INVENTORY_GUID_VALID(&destination)) return false;
		slot = INVENTORY_ITEM_SLOT(item, joaat("WARDROBE"));
		if (!slot) return false;
	}
	INVENTORY_GUID_FROM_ITEM(&destination, item, slot, out);
	return INVENTORY_GUID_VALID(out);
}
static bool INVENTORY_REMOVE_WITH_REASON(Hash item, int quantity, Hash reason) { return invoke<BOOL>(0xB4158C8C9A3B5DCE, 1, item, quantity, reason) != 0; }
static bool INVENTORY_REMOVE(Hash item, int quantity) { return INVENTORY_REMOVE_WITH_REASON(item, quantity, joaat("REMOVE_REASON_DUPLICATE")); }
static bool ITEM_INTERACTION_RUNNING(Ped ped) { return invoke<BOOL>(0xEC7E480FF8BD0BED, ped) != 0; }
static Hash ITEM_INTERACTION_ITEM(Ped ped) { return invoke<Hash>(0x804425C4BBD00883, ped); }
static Hash ITEM_INTERACTION_STATE(Ped ped) { return invoke<Hash>(0x6AA3DCA2C6F5EB6D, ped); }
static void SET_ITEM_INTERACTION_STATE(Ped ped, Hash state, float blend) { invoke<Void>(0xB35370D5353995CB, ped, state, blend); }
static float GET_PED_DRUNKNESS(Ped ped) { return invoke<float>(0x6FB76442469ABD68, ped); }
static void SET_PED_DRUNKNESS(Ped ped, bool enabled, float level) { invoke<Void>(0x406CCF555B04FAD3, ped, enabled, level); }
static void SET_PED_IS_DRUNK(Ped ped, bool enabled) { invoke<Void>(0x95D2D383D5396B8A, ped, enabled); }
static void TASK_KNOCKED_OUT(Ped ped, float duration, bool permanently) { invoke<Void>(0xF90427F00A495A28, ped, duration, permanently); }
static int   GET_BOUNTY_VALUE(Player p) { return invoke<int>(0x54310AAB97B92816, p); }
static void  SET_BOUNTY_VALUE(Player p, int amount) { invoke<Void>(0x093A9D1F72DF0D19, p, amount); }
static bool  WITNESSES_ACTIVE(Player p) { return invoke<BOOL>(0x69E181772886F48B, p) != 0 || invoke<BOOL>(0x0BB6DE7D23C60626, p) != 0; }
static void  SUPPRESS_WITNESSES(Player p) { invoke<Void>(0x96722257E5381E00, p); }
static int   CASH_BALANCE() { return invoke<int>(0x0C02DABFA3B98176); }
static bool  ADD_CASH(int amount) { return invoke<BOOL>(0xBC3422DC91667621, amount, joaat("ADD_REASON_DEFAULT")) != 0; }
static bool  REMOVE_CASH(int amount) { return invoke<BOOL>(0x466BC8769CF26A7A, amount) != 0; }
static int   SCRIPT_REFS(Hash script) { return invoke<int>(0x8E34C953364A76DD, script); }
static bool  SCRIPT_THREAD_ACTIVE(int id) { return id > 0 && invoke<BOOL>(0x46E9AE36D8FA6417, id, FALSE) != 0; }
static void  FORCE_THREAD_CLEANUP(int id, int flags) { invoke<Void>(0xF4C9512A2F0A3031, id, flags); }
static bool  UIAPP_ACTIVE(Hash app) { return invoke<BOOL>(0x25B7A0206BDFAC76, app) != 0; }
static Any   DATABINDING_CONTAINER(const char* path) { return invoke<Any>(0x0C827D175F1292F2, path); }
static Any   DATABINDING_ITEM_CONTEXT(Any list, int index) { return invoke<Any>(0xE96D7F9FEFCC105F, list, index); }
static int   DATABINDING_READ_INT(Any parent, const char* field) { return invoke<int>(0xFFC566A4801F6B40, parent, field); }
static bool  DATABINDING_READ_BOOL(Any parent, const char* field) { return invoke<BOOL>(0xA8EDE09FE07BD77F, parent, field) != 0; }
static void  DATABINDING_WRITE_INT(Any parent, const char* field, int value) { invoke<Void>(0x9EFA98238BA08FC4, parent, field, value); }
static void  DATABINDING_WRITE_BOOL(Any parent, const char* field, bool value) { invoke<Void>(0xBDFE546E4C2D0E21, parent, field, value ? TRUE : FALSE); }
static void  DATABINDING_WRITE_BOOL_ID(Any entry, bool value) { invoke<Void>(0xAB888B4B91046770, entry, value ? TRUE : FALSE); }
static int   DATABINDING_ARRAY_COUNT(Any array) { return invoke<int>(0xD23F5DE04FE717E2, array); }
static bool  DATABINDING_VALID(Any entry) { return invoke<BOOL>(0x1E7130793AAAAB8D, entry) != 0; }
static bool  STAT_GET(Hash id, int* value) { Any stat[2] = { id, 0 }; return invoke<BOOL>(0x767FBC2AC802EF3E, stat, value) != 0; }
static bool  STAT_SET(Hash id, int value) { Any stat[2] = { id, 0 }; return invoke<BOOL>(0xA4DDF5DF95E65EEE, stat, value, TRUE) != 0; }
static bool  UNLOCKED(Hash id) { return invoke<BOOL>(0xC4B660C7B6040E75, id) != 0; }
static int   PARSEDDATA_LOAD(Hash file) { return invoke<int>(0xD97D8D905F1562F2, file); }
static bool  PARSEDDATA_LOADED(int file) { return invoke<BOOL>(0x603AC35FD4602C76, file) != 0; }
static void  PARSEDDATA_REGISTER(int file, int query, const char* path) { invoke<Any>(0xAE156A747C39A741, file, query, path); }
static bool  PARSEDDATA_HASH(Hash* value, Any* query) { return invoke<BOOL>(0xFBFF3FF2F5E80C0B, value, query) != 0; }
static void  PARSEDDATA_UNLOAD(int file) { invoke<Void>(0x129567F0C05F81B9, file); }
static void  SET_MELEE_DAMAGE(Player p, float value) { invoke<Void>(0xE4CB5A3F18170381, p, value); }
static void  SET_WEAPON_DEFENSE(Player p, float value) { invoke<Void>(0xD15CC2D493160BE3, p, value); }
static void  SET_BOUNTY_COOLDOWN(Hash key, int value) { invoke<Void>(0xF19706B1F8FFA88F, key, value); }
static int   NEARBY_PEDS(Ped p, int* buffer) { return invoke<int>(0x23F8F5FC7E8C4A6B, p, buffer, -1, -1); }
static bool  IS_CHILD(Ped p) { return invoke<BOOL>(0x137772000DAF42C5, p) != 0; }
static Entity PED_DEATH_SOURCE(Ped p) { return invoke<Entity>(0x93C8B64DEB84728C, p); }
static Hash  PED_DEATH_CAUSE(Ped p) { return invoke<Hash>(0x16FFE42AB2D2DC59, p); }
static Ped   PED_LOOTER(Entity e) { return invoke<Ped>(0xEF2D9ED7CE684F08, e); }
static bool  MISSION_ACTIVE() { return invoke<BOOL>(0xB15CD1CF58771DE1) != 0; }
static bool  PLAYER_DEAD(Player p) { return invoke<BOOL>(0x2E9C3FCB6798F397, p) != 0; }
static bool  SAFE_PED_COORD(Vector3 p, Vector3* out) { return invoke<BOOL>(0xB61C8E878A4199CA, p.x, p.y, p.z, TRUE, out, 0) != 0; }
static bool  GROUND_Z(Vector3 p, float* z) { return invoke<BOOL>(0x24FA4267BB8D2431, p.x, p.y, p.z + 20.0f, z, FALSE) != 0; }
static Vector3 OFFSET_FROM_COORDS(Vector3 p, float heading, float x, float y, float z) { return invoke<Vector3>(0x163E252DE035A133, p.x, p.y, p.z, heading, x, y, z); }
static bool  GOAL_ACTIVE(Hash challenge, Hash goal) { return invoke<BOOL>(0x04DAC3929796EB87, challenge, goal) != 0; }
static bool  CONTROL_JUST_PRESSED(int group, Hash control) { return invoke<BOOL>(0x580417101DDB492F, group, control) != 0; }
static bool  DISABLED_CONTROL_JUST_PRESSED(int group, Hash control) { return invoke<BOOL>(0x91AEF906BCA88877, group, control) != 0; }
static Hash  WHEEL_HIGHLIGHTED() { return invoke<Hash>(0x9C409BBC492CB5B1); }
static void  START_ITEM_INTERACTION(Ped ped, Hash item, Hash state) { invoke<Void>(0xAE72E7DF013AAA61, ped, item, state, 1, 0, -1.0f); }
static void  SET_CONTROL_NEXT_FRAME(int group, Hash control, float value) { invoke<Void>(0xE8A25867FBA3B05E, group, control, value); }
static Hash  AMMO_TYPE_FROM_WEAPON(Ped p, Hash weapon) { return invoke<Hash>(0x7FEAD38B326B9F74, p, weapon); }
static bool  AMMO_VALID_FOR_WEAPON(Hash weapon, Hash ammo) { return invoke<BOOL>(0xC570B881754DF609, weapon, ammo) != 0; }
static bool  WEAPON_HAS_MULTIPLE_AMMO(Hash weapon) { return invoke<BOOL>(0x58425FCA3D3A2D15, weapon) != 0; }
static void  SET_WEAPON_AMMO_TYPE(Ped p, Hash weapon, Hash ammo) { invoke<Void>(0xCC9C4393523833E2, p, weapon, ammo); }
// XInputGetState against an EMPTY slot is a documented several-hundred-
// microsecond call (it walks the device stack every time). Four independent
// helpers were each polling all four slots every frame; once climbing and prone
// were both enabled that reached ~20 calls per frame and dominated the script's
// frame cost, which is the heavy lag reported on 2026-07-28. Poll once per tick
// and stop touching a slot that reported "not connected" until a rescan.
struct PadSnapshot { XINPUT_STATE state; bool connected; };
static PadSnapshot g_pads[XUSER_MAX_COUNT] = {};
static DWORD g_padPollAt = 0;
static DWORD g_padRescanAt = 0;

static void pollGamepads() {
	const DWORD now = GetTickCount();
	if (g_padPollAt == now) return;
	g_padPollAt = now;
	const bool rescan = now - g_padRescanAt >= 3000;
	if (rescan) g_padRescanAt = now;
	for (DWORD i = 0; i < XUSER_MAX_COUNT; ++i) {
		if (!g_pads[i].connected && !rescan) continue;
		XINPUT_STATE state = {};
		g_pads[i].connected = XInputGetState(i, &state) == ERROR_SUCCESS;
		g_pads[i].state = state;
	}
}

static bool padButtonDown(WORD mask) {
	pollGamepads();
	for (const PadSnapshot& pad : g_pads)
		if (pad.connected && (pad.state.Gamepad.wButtons & mask)) return true;
	return false;
}

static float CONTROL_AXIS(int group, Hash control) {
	float value = 0.0f;
	for (int padGroup = 0; padGroup < 3; ++padGroup) {
		const float enabled = PAD::GET_CONTROL_NORMAL(padGroup, control);
		const float disabled = PAD::GET_DISABLED_CONTROL_NORMAL(padGroup, control);
		if (std::fabs(enabled) > std::fabs(value)) value = enabled;
		if (std::fabs(disabled) > std::fabs(value)) value = disabled;
	}
	// PAD movement normals have repeatedly returned zero after this ASI owns
	// movement controls. Preserve keyboard and XInput movement explicitly while
	// retaining PAD above for remapped bindings and non-XInput controllers.
	if (control == joaat("INPUT_MOVE_LR") || control == joaat("INPUT_MOVE_UD")) {
		float direct = 0.0f;
		if (control == joaat("INPUT_MOVE_LR")) {
			if (GetAsyncKeyState('A') & 0x8000) direct -= 1.0f;
			if (GetAsyncKeyState('D') & 0x8000) direct += 1.0f;
		} else {
			if (GetAsyncKeyState('W') & 0x8000) direct -= 1.0f;
			if (GetAsyncKeyState('S') & 0x8000) direct += 1.0f;
		}
		pollGamepads();
		for (const PadSnapshot& pad : g_pads) {
			if (!pad.connected) continue;
			const SHORT raw = control == joaat("INPUT_MOVE_LR") ?
				pad.state.Gamepad.sThumbLX : pad.state.Gamepad.sThumbLY;
			const int deadzone = XINPUT_GAMEPAD_LEFT_THUMB_DEADZONE;
			float axis = std::abs((int)raw) <= deadzone ? 0.0f :
				(float)raw / (raw < 0 ? 32768.0f : 32767.0f);
			if (control == joaat("INPUT_MOVE_UD")) axis = -axis;
			if (std::fabs(axis) > std::fabs(direct)) direct = axis;
		}
		if (std::fabs(direct) > std::fabs(value)) value = direct;
	}
	return value;
}
static float ENTITY_HEADING(Entity e) { return invoke<float>(0xC230DD956E2F5507, e); }
static int   ENTITY_INTERIOR(Entity e) { return invoke<int>(0xB417689857646F61, e); }
static bool  GROUND_Z_NORMAL(Vector3 p, float* z, Vector3* normal) { return invoke<BOOL>(0x2A29CA9A6319E6AB, p.x, p.y, p.z + 3.0f, z, normal) != 0; }
static bool  WATER_HEIGHT(Vector3 p, float* z) { return invoke<BOOL>(0xDCF3690AA262C03F, p.x, p.y, p.z + 2.0f, z) != 0; }
static void  SET_COORDS_HEADING(Entity e, Vector3 p, float heading) { invoke<Void>(0x203BEFFDBE12E96A, e, p.x, p.y, p.z, heading, FALSE, FALSE, TRUE); }
static void  REQUEST_SCRIPT(const char* name) { invoke<Void>(0x46ED607DDD40D7FE, name); }
static bool  SCRIPT_LOADED(const char* name) { return invoke<BOOL>(0xE97BD36574F8B0A6, name) != 0; }
static int   START_SCRIPT_ARGS(const char* name, Any* args, int count, int stack) { return invoke<int>(0xB8BA7F44DF1575E1, name, args, count, stack); }
static Vector3 ENTITY_VELOCITY(Entity e) { return invoke<Vector3>(0x4805D2B1D8CF94A9, e, 0); }
static void SET_ENTITY_VELOCITY(Entity e, Vector3 v) { invoke<Void>(0x1C99BB7B6E96D16F, e, v.x, v.y, v.z); }
static void SET_ENTITY_ROTATION(Entity e, Vector3 r) { invoke<Void>(0x9CC8314DFEDE441E, e, r.x, r.y, r.z, 2, TRUE); }
static bool IS_PED_RAGDOLL(Ped p) { return invoke<BOOL>(0x47E4E977581C5B55, p) != 0; }
static bool GET_PED_CROUCH_MOVEMENT(Ped p) { return invoke<BOOL>(0xD5FE956C70FF370B, p) != 0; }
static void SET_PED_CROUCH_MOVEMENT(Ped p, bool state, bool immediately) { invoke<Void>(0x7DE9692C6F64CFE8, p, state, 0, immediately); }
static void SET_PED_STEALTH_MOVEMENT(Ped p, bool state) { invoke<Void>(0x88CBB5CEB96B7BD2, p, state, 0, 0); }
static bool IS_PED_MELEE(Ped p) { return invoke<BOOL>(0x4E209B2C1EAD5159, p) != 0; }
static bool IS_PED_ON_MOUNT(Ped p) { return invoke<BOOL>(0x460BC76A0E10655E, p) != 0; }
static bool IS_PED_SWIMMING(Ped p) { return invoke<BOOL>(0x9DE327631295B4C2, p) != 0; }
static bool IS_PED_FALLING(Ped p) { return invoke<BOOL>(0xFB92A102F1C4DFA3, p) != 0; }
static float HEIGHT_ABOVE_GROUND(Entity e) { return invoke<float>(0x0D3B5BAEA08F63E9, e); }
static int START_LOS_PROBE(Vector3 a, Vector3 b, int flags, Entity ignore) { return invoke<int>(0x7EE9F5D83DD4F90E, a.x, a.y, a.z, b.x, b.y, b.z, flags, ignore, 7); } // p8=7 matches every Rockstar script call site
static int SHAPE_RESULT(int handle, BOOL* hit, Vector3* end, Vector3* normal, Entity* entity) { return invoke<int>(0xEDE8AC7C5108FB1D, handle, hit, end, normal, entity); }
static void SET_COORDS_NO_OFFSET(Entity e, Vector3 p) { invoke<Void>(0x239A3351AC1DA385, e, p.x, p.y, p.z, FALSE, FALSE, TRUE); }
// UFCO's per-frame climbing coord write passes axis flags 1,1,1 (decompiled:
// FUN_180007840(x,y,z,1,1,1)). We were passing FALSE,FALSE,TRUE on the same
// native, every frame, while attached - and the animation never advanced past
// frame 0. Match the reference exactly on the climbing path only, so the other
// three call sites in this file keep their existing behaviour.
static void SET_COORDS_NO_OFFSET_ALIGNED(Entity e, Vector3 p) { invoke<Void>(0x239A3351AC1DA385, e, p.x, p.y, p.z, TRUE, TRUE, TRUE); }
static void SET_ENTITY_HEADING(Entity e, float heading) { invoke<Void>(0xCF2B9C0645C4651B, e, heading); }
static void RESTORE_STAMINA(Player p, float amount) { invoke<Void>(0xC41F4B6E23FE6A4A, p, amount); }
static Hash  ENTITY_MODEL(Entity e) { return invoke<Hash>(0xDA76A9F39210D365, e); }
static Object PICKUP_OBJECT(Pickup p) { return invoke<Object>(0x5099BC55630B25AE, p); }
static bool  HAS_WEAPON(Ped p, Hash weapon) { return invoke<BOOL>(0x8DECB02F88F428BC, p, weapon, 0, FALSE) != 0; }
static void  GIVE_WEAPON(Ped p, Hash weapon) { invoke<Hash>(0x5E3BDDBCB83F3D84, p, weapon, 1, FALSE, FALSE, 0, FALSE, 0.0f, 0.0f, joaat("ADD_REASON_DEFAULT"), TRUE, 0.0f, FALSE); }
static bool  DAMAGED_BY_WEAPON(Entity e, Hash weapon) { return invoke<BOOL>(0xDCF06D0CDFF68424, e, weapon, 0) != 0; }
static void  CLEAR_LAST_WEAPON_DAMAGE(Entity e) { invoke<Void>(0xC5D3B0AABF535C4F, e); }
static Hash  REL_GROUP(Ped p) { return invoke<Hash>(0x7DBDD04862D95F04, p); }
static void  FLEE_PED(Ped p, Ped from) { invoke<Void>(0x22B0D0E37CCB840D, p, from, 250.0f, -1, 0, 3.0f, 0); }
static void  SET_SEEING(Ped p, float value) { invoke<Void>(0xF29CF591C4BF6CEE, p, value); }
static void  SET_HEARING(Ped p, float value) { invoke<Void>(0x33A8F7F7D5F7F33C, p, value); }
static Any   DB_GET_PATH(const char* path) { return invoke<Any>(0x0C827D175F1292F2, path); }
static bool  DB_VALID(Any id) { return invoke<BOOL>(0x1E7130793AAAAB8D, id) != 0; }
static int   DB_READ_INT(Any parent, const char* key) { return invoke<int>(0xFFC566A4801F6B40, parent, key); }
static void  DB_WRITE_INT(Any parent, const char* key, int value) { invoke<Void>(0x9EFA98238BA08FC4, parent, key, value); }
static void  DB_WRITE_HASH(Any parent, const char* key, Hash value) { invoke<Void>(0x0971F04E1EAA7AE8, parent, key, value); }
static int   DB_COUNT(Any list) { return invoke<int>(0xD23F5DE04FE717E2, list); }
static Any   DB_ADD_LIST(Any parent, const char* key) { return invoke<Any>(0xFE74FA57E0CE6824, parent, key); }
static Any   DB_ADD_CONTAINER(Any parent, const char* key) { return invoke<Any>(0xEB4F9A3537EEABCD, parent, key); }
static Any   DB_ADD_HASH(Any parent, const char* key, Hash value) { return invoke<Any>(0x8538F1205D60ECA6, parent, key, value); }
static Any   DB_ADD_INT(Any parent, const char* key, int value) { return invoke<Any>(0x307A3247C5457BDE, parent, key, value); }
static Any   DB_ADD_BOOL(Any parent, const char* key, bool value) { return invoke<Any>(0x58BAA5F635DA2FF4, parent, key, value); }
static Any   DB_ADD_STRING(Any parent, const char* key, const char* value) { return invoke<Any>(0x617FCA1C5652BBAD, parent, key, value); }
static void  DB_INSERT(Any list, int index, Hash alias, Any row) { invoke<Void>(0xEE97A05C05F16E41, list, index, alias, row); }
static bool  ITEM_EFFECT_IDS(Hash item, Any* data) { return invoke<BOOL>(0x9379BE60DC55BBE6, item, data) != 0; }
static bool  ITEM_EFFECT_INFO(Hash effect, Any* info) { return invoke<BOOL>(0xCF2D360D27FD1ABF, effect, info) != 0; }

static Hash joaat(const char* s) {
	unsigned h = 0; while (*s) { char c = *s++; if (c >= 'A' && c <= 'Z') c += 32; h += (unsigned char)c; h += h << 10; h ^= h >> 6; }
	h += h << 3; h ^= h >> 11; h += h << 15; return h;
}




static std::string g_iniPath;
static FILETIME g_lastWrite = {};
static FILETIME g_buyerOverrideLastWrite = {};
static std::unordered_map<UINT64, int> g_merchantBuyOverrides;

static bool  g_humanStamEnabled = true;
static float g_humanIdleRate = 12.0f, g_humanWalkRate = 6.0f;
static float g_humanJogRate = -4.0f, g_humanSprintRate = -12.0f, g_humanSwimRate = -8.0f;
static float g_humanRoadDrainMultiplier = 0.5f;
// #11: draw the current movement mode and its applied rate on screen.
static bool  g_staminaShowMode = false;
static bool  g_horseStamEnabled = true;
static float g_horseIdleRate = 16.0f, g_horseWalkRate = 8.0f, g_horseTrotRate = 2.0f;
static float g_horseCanterRate = -6.0f, g_horseGallopRate = -14.0f, g_horseSwimRate = -8.0f;
static float g_horseRoadDrainMultiplier = 0.5f;
static bool  g_animalEnabled = false;
static float g_animalMult = 1.0f;
static bool  g_coreClockEnabled = true;
static float g_healthDrainHours = 24.0f, g_staminaDrainHours = 24.0f, g_deadeyeDrainHours = 24.0f;
static float g_deadeyeSleepRefillHours = 12.0f;
static bool  g_toxicityEnabled = true;
static float g_toxicHealthDrainPointsPerSecond = 1.0f;
static bool  g_temperatureEnabled = true;
static float g_temperatureBaseDrainHours = 24.0f;
static float g_heatDrainMultiplier = 1.0f;
static float g_coldDrainMultiplier = 1.0f;
static bool  g_toxicActive = false;
static Hash  g_recentToxicInteraction = 0;
static DWORD g_recentToxicInteractionAt = 0;
static bool  g_toxicCountsInitialized = false;
static int   g_toxicItemCounts[5] = {};
static bool  g_noReserveCores = true;
// Hysteresis floor for RELEASING the #78 exhaustion latch. It is NOT the
// exhaustion trigger any more: a normalized meter whose ring-vs-core meaning is
// unproven must not decide the boundary. See the latch for the trigger.
static float g_deadeyeEmptyFrac = 0.01f;
// KEPT. An earlier edit in this pass deleted this as "never called" after
// grepping only script.cpp - modules/combat_inventory.cpp:613 calls it. Recording
// the near-miss because it is the same one-file-grep mistake fuckups.txt entry 17
// is about. Its caller is #125's territory, not #78's, so its behaviour is
// unchanged; only the comment above it is corrected.
static bool deadeyeOuterEmpty(Player p) {
	return GET_DEADEYE_METER_LEVEL(p) <= g_deadeyeEmptyFrac;
}

// GitHub #125. Requested Dead Eye consumption in bar points per second while
// Dead Eye is active. 0 means zero consumption, exactly as requested; it must
// still be submitted because returning early would leave Rockstar's vanilla
// duration cost active.
static float g_deadeyeConsumptionRate = 1.0f;

// GitHub #125. Set the engine's own per-second Dead Eye duration cost directly.
// The sampled bar delta is readback evidence only; it never feeds another
// speculative controller and it cannot make the implementation claim success.
static void updateDeadeyeConsumption(Player player, DWORD now, bool deadeyeActive) {
	static DWORD sampleTick = 0;
	static float sampleBar = 0.0f;
	static bool costApplied = false;
	static DWORD nextLog = 0;

	if (!deadeyeActive) {
		if (costApplied) {
			SET_DEADEYE_DURATION_COST(player, 0.0f);
			costApplied = false;
			gtLog("deadeye-rate", GT_INFO, "released");
		}
		sampleTick = 0;
		return;
	}

	SET_DEADEYE_DURATION_COST(player, g_deadeyeConsumptionRate);
	costApplied = true;

	const float bar = GET_DEADEYE_BAR(player);
	if (!sampleTick) { sampleTick = now; sampleBar = bar; return; }

	const DWORD elapsed = now - sampleTick;
	if (elapsed < 250) return;                 // need a measurable window
	const float seconds = elapsed / 1000.0f;
	const float observed = (sampleBar - bar) / seconds;   // points per second
	sampleTick = now;
	sampleBar = bar;

	if (now >= nextLog) {
		nextLog = now + 1000;
		std::ostringstream line;
		line << "requested=" << g_deadeyeConsumptionRate
			<< " observed=" << observed
			<< " bar=" << bar
			<< " durationCost=" << g_deadeyeConsumptionRate
			<< " dt=" << elapsed;
		gtLog("deadeye-rate", GT_INFO, line.str());
	}
}
static bool  g_wagonCoreEnabled = true;
static float g_wagonCoreDrain = 0.25f, g_wagonMinSpeed = 1.0f;
// #25. Disabled means ordinary Rockstar activity XP cannot raise the three
// base core ranks. The currently loaded ranks are captured, never reset.
static bool  g_coreXPGainEnabled = false;
static Ped   g_coreXPPed = 0;
static bool  g_coreXPRanksCaptured = false;
static int   g_coreXPRankCeiling[3] = {};
static bool  g_trainTracking = true;
static Blip  g_trainBlips[32] = {};
static bool  g_collectiblesEnabled = true;
static bool  g_collectCards = true, g_collectBones = true, g_collectCarvings = true;
static bool  g_collectDreamcatchers = true, g_collectGraves = true;
static bool  g_collectExotics = true, g_collectTreasureClues = true, g_collectPois = true;
static bool  g_collectLegendaryFish = true, g_collectShacks = true;
static bool  g_collectGangHideouts = true;
static bool  g_collectiblesDirty = true;
static unsigned g_collectibleUnlocks = 0;
static bool g_banditMasksEnabled = true, g_honorPricesEnabled = true;
static bool g_fenceHonorReversed = true; // #43: at fences, LOW honor gets the good prices
static bool g_bottleProbeEnabled = false;   // BottleProbe, development builds only
static bool g_emptyBottlesEnabled = true, g_humanTonicBottles = false;
static int  g_emptyBottleStowDelayMs = 1450;
static bool g_carriedMaskEnabled = true;
static std::string g_carriedMask = "KIT_MASK_GREY_CLOTH";
// Partial bounty repayment is an always-on overhaul feature, not a setting.
static constexpr bool g_partialBountyEnabled = true;
static constexpr int g_partialBountyMinPayment = 1;
// Hold F (keyboard) or RS-click (controller) past HoldMs to equip owned
// binoculars and look; release stows and restores the previous weapon. Never
// triggers while aiming a gun. See updateBinocularAccess().
static bool g_binocularsEnabled = true;
static int  g_binocularsHoldMs = 250;
static bool g_binocularsRequireOwned = true;
// #59: the RDO improved kit is imported by MyOverhaul but Story Mode has no
// vanilla acquisition path for it. Ensure it is actually present in the
// player's inventory so the regular/improved optics comparison is testable.
// 0 = keyboard F only; 1 = controller pad-button only; 2 = both
static int  g_binocularsHoldMode = 2;
// Which keyboard key raises binoculars (virtual-key code). DEFAULT CHANGED from
// F to B: F is INPUT_PICKUP, and the pickup reach animation is what displaces the
// binocular model. Using a key the game does not already own avoids the bug
// entirely instead of fighting the animation.
static int  g_binocularsKey = 0x42; // 'B'
// #116: FALSE = play the authored satchel draw / put-away, which is what the
// weapon wheel does. TRUE = the old behaviour, kit teleported into his hands.
static bool g_binocularsInstantEquip = false;
// How long to let the draw play before forcing the scope. Must cover the
// satchel animation now that it actually runs.
static int  g_binocularsDrawMs = 900;
// How long to let the put-away play before the previous weapon is restored.
static int  g_binocularsStowMs = 900;
// Runtime binocular presentation. Unlike LookingGlassScale/LookingGlassFOV in
// weaponcomponents.meta, these ASI-owned controls hot-reload from the INI.
static bool  g_binocularMaskEnabled = true;
static float g_binocularMaskScale = 1.0f;
static float g_binocularMaskOpacity = 1.0f;
static bool  g_binocularZoomReadout = true;
// Set by updateBinocularAccess after the real scope camera is active. Recon
// must not run just because the binocular weapon happens to be equipped.
static bool g_binocularsActive = false;
// True from the moment the hold crosses its threshold until the binoculars
// are put away. Prone yields its full-body crawl task during this interval so
// Rockstar's binocular equip/aim task can own the skeleton.
static bool g_binocularsModeEngaged = false;
static void loadCompendiumGlintProbeConfig();
// Defined with the prone system further down. A native standing task must never
// clear the crawl skeleton out from under Arthur; it has to ask prone to run its
// authored exit first. See proneRequestStandForNativeAction.
static bool customProneActive();
static bool proneRequestStandForNativeAction(Ped ped, const char* reason);
// Shared task ownership handshake: binocular access clears an existing prone
// task before equipping, then prone knows not to clear the newly-created
// binocular task on the following update in the same frame.
static bool g_proneTaskOwnsSkeleton = false;
static bool g_reconTaggingEnabled = true;
static bool g_reconBlipsEnabled = true;
static bool g_reconMarkedOnlyMinimap = true;
static int  g_reconObserveMs = 900;
static float g_reconMinProjectedExtent = 0.025f;
static float g_reconMaxDistance = 350.0f;
static float g_reconAimRadius = 0.060f;
static int  g_reconMaxTags = 24;
// #113(d): allow plants and other world pickups to be tagged, not just peds.
static bool g_reconTagPickups = true;
// #113(d): restrict tagging to models the harvest learner has confirmed.
static bool g_reconPlantsOnly = true;
static std::vector<Hash> g_plantModels;
static bool g_plantModelsLoaded = false;
static bool g_climbingEnabled = true;
static bool g_climbingTrace = false;
static float g_climbIdleDrain = 0.35f;
static float g_climbMoveDrain = 1.25f;
static float g_climbSprintDrain = 2.5f;
static float g_climbMoveSpeed = 0.75f;
static float g_climbSprintSpeed = 1.25f;
static float g_climbLeapCost = 12.0f;
static float g_climbLeapDistance = 3.2f;
static float g_climbGrabDistance = 1.10f;
static float g_climbMinSurfaceAngle = 45.0f;
static float g_climbSurfaceOffset = 0.36f;
// #169(f): real vertical clearance over the lip during the mantle. The curve
// only reaches half its control offset, so this is doubled where it is used.
static float g_climbTopOutClearance = 0.45f;
static float g_climbProbeTolerance = 0.42f;
static float g_climbSmoothing = 12.0f;
static bool  g_climbPitchAlign = true;
static float g_climbFacingOffset = 180.0f;
static int   g_climbGripSettleMs = 400;
// How long a climb motion clip takes to blend in. Movement speed ramps in over
// this window so he never travels while nothing is visibly animating.
static int   g_climbMotionBlendMs = 220;
// A jutting rock presents two competing faces. Adopting a new surface normal
// the instant a probe reports it makes the fit flip-flop between them every
// frame, which is the vibrating-and-clipping report. Require the candidate to
// stay consistent for this long before switching to it.
static int   g_climbNormalHoldMs = 180;
// #98: holstering must actually put the gun away, not just change his pose.
static bool  g_alwaysHolster = true;
// Diagnostic: records what the game reports at the longarm attach points on
// each holster press, so the slot behaviour can be confirmed rather than assumed.
static bool  g_alwaysHolsterLog = false;
// #103: optional visible confirmation when the empty bottle is granted. OFF by
// default so it can never double up with a working native feed.
// #131: lantern off the radial, hung on the belt, lights itself after dark.
static bool  g_beltLanternEnabled = true;
static int   g_beltLanternOnHour = 19;
static int   g_beltLanternOffHour = 6;
static float g_beltLanternRange = 7.5f;
static float g_beltLanternBrightness = 3.2f;
static float g_beltLanternScale = 1.0f;

static bool  g_climbGripReady = false;
static DWORD g_climbGripAt = 0;
static float g_climbPitchSign = -1.0f;
// Which controller button raises binos (XInput mask). Default RS/R3 — its
// vanilla Look Behind is suppressed while held (see updateBinocularAccess) so
// it no longer turns the camera. Configurable via PadButton.
static WORD g_binocularPadMask = XINPUT_GAMEPAD_RIGHT_THUMB;
static WORD xinputButtonFromName(const char* n) {
	if (_stricmp(n, "dpad_up") == 0 || _stricmp(n, "up") == 0)       return XINPUT_GAMEPAD_DPAD_UP;
	if (_stricmp(n, "dpad_down") == 0 || _stricmp(n, "down") == 0)   return XINPUT_GAMEPAD_DPAD_DOWN;
	if (_stricmp(n, "dpad_left") == 0 || _stricmp(n, "left") == 0)   return XINPUT_GAMEPAD_DPAD_LEFT;
	if (_stricmp(n, "dpad_right") == 0 || _stricmp(n, "right") == 0) return XINPUT_GAMEPAD_DPAD_RIGHT;
	if (_stricmp(n, "lb") == 0 || _stricmp(n, "l1") == 0)           return XINPUT_GAMEPAD_LEFT_SHOULDER;
	if (_stricmp(n, "rb") == 0 || _stricmp(n, "r1") == 0)           return XINPUT_GAMEPAD_RIGHT_SHOULDER;
	if (_stricmp(n, "ls") == 0 || _stricmp(n, "l3") == 0)           return XINPUT_GAMEPAD_LEFT_THUMB;
	if (_stricmp(n, "rs") == 0 || _stricmp(n, "r3") == 0)           return XINPUT_GAMEPAD_RIGHT_THUMB;
	if (_stricmp(n, "back") == 0)                                   return XINPUT_GAMEPAD_BACK;
	return XINPUT_GAMEPAD_DPAD_UP;
}
static bool g_spentCasingsEnabled = true;
static int g_spentCasingLifetimeSeconds = 600;
static int g_spentCasingMaximum = 128;
static float g_casingPickupRange = 1.2f;
// How long after a shot a lever/bolt/pump cycle still counts as ejecting that
// shot's casing. Replaces the old "player must still be in a shooting posture"
// gate, which could never be true at the moment the cycle actually completes.
static int   g_casingCycleWindowMs = 8000;
static float g_casingLookAngleDeg = 20.0f;
static std::string g_casingSoundName = "SELECT";
static std::string g_casingSoundSet = "HUD_SHOP_SOUNDSET";
static float g_casingGlowIntensity = 0.3f;
static float g_casingGlowRange = 0.7f;
static float g_casingGlowYellowness = 0.85f;
static bool g_casingGlintEnabled = true;
static float g_casingGlintSize = 1.5f;
static float g_casingGlintAlpha = 0.45f;
static float g_casingGlintBrightness = 0.75f;
static int g_casingGlintDurationMs = 1200;
static int g_casingGlintFadeInMs = 250;
static int g_casingGlintFadeOutMs = 450;
static int g_casingGlintPauseMs = 1600;
static int g_casingGlintTimingRandomnessMs = 1000;
static bool g_spentCasingDebugMarker = false;
// 0 = engine pickup system (weapon-style TAB prompt, bend anim) - works, but
//     TAB key because pickups.meta button-press is the weapon-pickup action
// 2 = our own loot-key (INPUT_LOOT) prompt + grant + item card, using Lexer's
//     tuned PickupRange/PickupLookAngleDeg. No bend animation. DEFAULT.
// (mode 1 / carriable removed: TASK_CARRIABLE tasked the player and broke crouch)
static int g_casingMode = 2;
// Directional dodge roll (#6). The shipped dictionary and clips are confirmed;
// movement.cpp keeps vanilla Dive unless a directional authored roll is ready
// and its path is safe.
static bool g_combatRollEnabled = true;
static float g_combatRollStaminaCost = 10.0f;
// The two durations are the complete player-authored roll timeline: their sum
// is total roll length. The prefix is invulnerable; the remainder is recovery.
static float g_combatRollInvulnerabilitySeconds = 0.35f;
static float g_combatRollRecoverySeconds = 0.35f;
static float g_combatRollInvulnerabilityOpacityPercent = 55.0f;
static bool g_combatRollTrace = false;
static DWORD g_nextCombatRollAt = 0;
static bool g_camPitchEnabled = true;
static float g_camPitchMin = -85.0f;
static float g_camPitchMax = 45.0f;
// Verified in Rockstar's shipped animation dictionary. This is the right-hand
// ground pickup used by the generic pickup system, not an invented clip name.
static const char* kCasingAnimDict = "mech_pickup@system@rh";
static const char* kCasingAnimClip = "ground_near";
static bool g_recoverUniqueWeapons = true;
static bool g_hunterHatchetEnabled = true;
static bool g_duplicateCardsEnabled = true;

struct AlcoholStrength {
	std::string item;
	Hash hash;
	float target;
	float vanilla;
	int swigs;
};
static std::vector<AlcoholStrength> g_alcoholStrengths;
static FILETIME g_alcoholLastWrite = {};
static Hash g_activeAlcoholInteraction = 0;
static float g_alcoholLevelBefore = 0.0f;
static int g_alcoholCompletedSwigs = 0;
static bool g_alcoholEventWasFired = false;

static Hash alcoholItemHash(const std::string& item) {
	if (item.size() > 2 && item[0] == '0' && (item[1] == 'x' || item[1] == 'X'))
		return (Hash)strtoul(item.c_str() + 2, nullptr, 16);
	return joaat(item.c_str());
}

static void loadAlcoholStrengths() {
	std::vector<AlcoholStrength> next;
	std::ifstream input(g_moduleDir + "\\alcohol_strengths.csv");
	std::string line;
	while (std::getline(input, line)) {
		if (!line.empty() && line.back() == '\r') line.pop_back();
		if (line.empty() || line[0] == '#') continue;
		std::stringstream fields(line);
		std::string target, vanilla, swigs;
		AlcoholStrength row;
		if (!std::getline(fields, row.item, ',') ||
			!std::getline(fields, target, ',') ||
			!std::getline(fields, vanilla, ',') ||
			!std::getline(fields, swigs, ',')) continue;
		row.hash = alcoholItemHash(row.item);
		row.target = (float)atof(target.c_str());
		row.vanilla = (float)atof(vanilla.c_str());
		row.swigs = atoi(swigs.c_str());
		if (!row.hash || row.target < 0.0f || row.target > 1.0f ||
			row.vanilla < 0.0f || row.vanilla > 1.0f || row.swigs < 1) continue;
		next.push_back(row);
	}
	g_alcoholStrengths.swap(next);
}

static void updateAlcohol(Ped ped, DWORD now) {
	const bool running = ITEM_INTERACTION_RUNNING(ped);
	const Hash item = running ? ITEM_INTERACTION_ITEM(ped) : 0;
	AlcoholStrength* configured = nullptr;
	for (AlcoholStrength& row : g_alcoholStrengths)
		if (row.hash == item) { configured = &row; break; }

	if (!configured) {
		g_activeAlcoholInteraction = 0;
		g_alcoholCompletedSwigs = 0;
		g_alcoholEventWasFired = false;
		return;
	}
	float* levelGlobal = reinterpret_cast<float*>(getGlobalPtr(1935436 + 9));
	if (g_activeAlcoholInteraction != item) {
		g_activeAlcoholInteraction = item;
		g_alcoholLevelBefore = (std::max)(0.0f, (std::min)(1.0f, *levelGlobal));
		g_alcoholCompletedSwigs = 0;
		g_alcoholEventWasFired = false;
	}
	const bool eventFired = ENTITY::HAS_ANIM_EVENT_FIRED(ped, 442509369);
	if (eventFired && !g_alcoholEventWasFired &&
		g_alcoholCompletedSwigs < configured->swigs) {
		++g_alcoholCompletedSwigs;
		const float fraction = (float)g_alcoholCompletedSwigs / (float)configured->swigs;
		const float level = (std::max)(0.0f, (std::min)(1.0f,
			g_alcoholLevelBefore + configured->target * fraction));
		// generic_alcohol_item has already applied Rockstar's authored amount on
		// this event. Replace that result with the configured absolute target.
		*levelGlobal = level;
		SET_PED_DRUNKNESS(ped, level > 0.0f, level);
		SET_PED_IS_DRUNK(ped, level > 0.0f);
	}
	g_alcoholEventWasFired = eventFired;
}

static std::string statePath(const char* name) { return g_moduleDir + "\\" + name; }

static float g_witnessTalkChance = 0.5f, g_fenceMoneyMult = 2.0f;
static float g_bountyGainMult = 0.5f, g_catHorseRegenMult = 2.0f;
static float g_psychoMeleeMult = 2.0f, g_psychoBulletTakenMult = 0.5f;
static float g_paganHonorLossMult = 2.0f, g_lawPerceptionMult = 0.5f;
static bool  g_walletCapEnabled = true;
static int   g_walletCapCents[11] = { 100, 200, 400, 750, 1250, 2000, 4000, 7500, 15000, 25000, 0 };
static float g_honorPrice[17] = {};
static std::string g_rank4GlassesItem;

// #147b: NAMES ARE NOT UNIQUE, AND EVERYTHING KEYED ON THEM WAS WRONG.
// All twenty dreamcatchers are called "Dreamcatcher"; nineteen exotics repeat
// too (twenty "Gator Eggs", twenty "Moccasin Flower Orchid", ...). Both the
// collected-state file and the F3 fixup file matched on category+name alone, so
// ONE fixup line rewrote the coordinates of ALL twenty dreamcatchers - which is
// exactly why they ended up stacked on one spot - and collecting one exotic
// retired every other spot for that flower. `index` is the occurrence number
// within (category, name) and is what identity is keyed on now.
struct CollectibleMarker {
	std::string category, name;
	int index;        // 0-based occurrence within (category, name); makes the key unique
	std::string require;  // #147e: mission id that must be COMPLETED before this shows
	Vector3 position;
	Blip blip;
	bool collected;   // player has been to this spot; its blip is retired for good
};
static std::vector<CollectibleMarker> g_collectibles;
// When the player comes within this 2D radius of a marker we treat it as
// collected and retire its blip (persisted so it stays gone across sessions).
static bool  g_collectAutoClear = false;   // off until coords are accurate (#147)
static bool  g_collectProbeEnabled = false; // #147 probe, development builds only
static bool  g_proneEnabled = true;
static bool  g_proneTrace = false;
static int   g_proneHoldMs = 500;
static float g_proneMoveSpeedMultiplier = 1.0f;
// #170: metres per second the crawl drive actually moves him. Movement no
// longer depends on how much displacement each crawl clip happens to carry.
static float g_proneCrawlSpeed = 0.85f;
// #170: hold him on the surface while prone. Rotating the root tips the
// collision capsule under the terrain and the solver's recovery is what threw
// him back to standing.
static bool  g_proneFloorClamp = true;
static float g_proneGroundClearance = 0.05f;
static float g_proneDriveSpeed = 0.0f;
// #170: metres of water above the ground plane that count as "his head would be
// under". 0 disables the check entirely.
static float g_proneWaterHeadClearance = 0.30f;
static float g_proneTurnSpeed = 360.0f;
static int   g_proneEntryStyle = 0;
static bool  g_proneBlockActions = true;
static bool  g_proneAlignGround = true;
// #1: cut sprint while the outer Stamina bar still has THIS much left (percent
// of full). The old hardcoded 0.6 was so close to empty that Rockstar still got
// a frame or two to spend the core before the control was disabled, which is the
// visible "dip into the core then it snaps back". Give it real headroom.
static float g_reserveSprintCutBar = 3.0f;
// #1: at or below this outer-bar percentage, ANY fall in the matching core is a
// reserve spend and is refused outright — no size heuristic, no requirement that
// a particular control be held. Covers swimming (player) and every horse gait.
static float g_reserveBarFloor = 10.0f;
// The wheel-open control flickers, so a raw per-frame read bounces in and out of
// the wheel branch several times per selection. Hold it open for this long after
// the last pressed frame.
static int   g_proneWheelGraceMs = 250;
// How long to hand the skeleton to Rockstar's own draw after a wheel selection,
// so the weapon actually appears in his hands before crawl takes over again.
static int   g_proneEquipHoldMs = 700;
// Binoculars have no authored prone form. 0 = block them while prone (default,
// per #195: refuse rather than half-work), 1 = run the authored prone->crouch
// exit first, then glass.
static int   g_proneBinocularMode = 0;
// #195: grounded weapon handling does not exist yet. Until it does, prone simply
// REFUSES weapon swapping and reloading instead of standing Arthur up or leaving
// him sliding in a broken pose. Set 0 to let them through while building the rig.
static bool  g_proneBlockWeaponActions = true;
// #195 GROUNDED AIM. 0 = shipped behaviour: weapons refused while prone.
// 1 = the one experiment that has NOT been tried yet, recorded in Worklog #195.
//
// What is already known, from reading Dive-Crawl-N-Gun's decompilation and from
// Lexer's own in-game rejection of the previous build:
//   - Rockstar authored NO two-handed face-down aim set. Only `@1h` exists.
//     Longarms therefore cannot aim face-down without new animations.
//   - The reference mod has no continuous prone aiming either. It plays one
//     canned clip for 1000 ms and clears. Porting it cannot give what he asked.
//   - The real obstacle is task ownership: the native aim task points the gun at
//     the reticle, and any FULL-BODY grounded clip takes the skeleton off it, so
//     the gun stops tracking. Every clip issued so far has been full-body.
// The untried mechanism is to issue the grounded clip as a SECONDARY upper-body
// task and never clear the native aim task, so Rockstar keeps driving the gun
// underneath our pose. That is what mode 1 does. Off by default — it is an
// experiment, and prone movement should be judged without it in the way.
static int   g_proneGroundedAimMode = 0;
static bool  g_proneOneHandedWeapons = false;
static float g_pronePitchSign = -1.0f;
static float g_proneRollSign = 1.0f;
// #70: one combined carry limit per ammunition family instead of a separate cap
// for every variant (all .225 together, all .307 together, ...).
static bool  g_sharedAmmoEnabled = true;
static bool  g_radialAmmoEnabled = true, g_radialAmmoRequireOwned = true;
static bool  g_radialAmmoWrap = true, g_radialAmmoShowFeed = true;
static float g_radialAmmoCentreDeadzone = 0.18f;
// 0 = vanilla only/off, 2 = legacy corona blob, 4 = luminous streak (default).
// Rockstar's original weapon-data tracers remain untouched; the added renderer
// is independently controlled by [ProjectileVisibility] Enabled.
static int   g_projectileVisibilityMode = 4;
static float g_projectileMarkerSpeed = 20.0f;
// Shared carry pools for ITEMS (herbs, food/drink): one combined limit across a
// whole group, mirroring the ammo pools. Membership comes from
// shared_item_caps.csv so pools can be changed without a rebuild.
static bool  g_sharedItemCapsEnabled = true;
static int   g_itemCapHerbs = 0, g_itemCapFood = 0;
struct SharedItemPool { std::string pool; std::vector<std::string> items; };
static std::vector<SharedItemPool> g_sharedItemPools;
static int   g_ammoCap225 = 0, g_ammoCap307 = 0, g_ammoCap444 = 0,
             g_ammoCapShotgun = 0, g_ammoCapArrow = 0;
static float g_collectClearRadius = 6.0f;
static float g_collectMoveMaxDistance = 150.0f;
// #59: virtual-key code for placing/removing a campsite. VK_F3 (0x72) by
// default so vanilla's F4 keeps working.
static int   g_campKey = 0x72;
// How long, after the game says you are alive again, we keep re-asserting the
// campsite position before giving up. Rockstar's own respawn placement lands
// inside this window; one shot at the death edge loses the race to it.
static int   g_campRespawnWindowMs = 15000;

static float readF(const char* s, const char* k, float d) {
	char buf[64] = {}, def[64]; sprintf_s(def, "%g", d);
	GetPrivateProfileStringA(s, k, def, buf, sizeof(buf), g_iniPath.c_str());
	return (float)atof(buf);
}
static bool readB(const char* s, const char* k, bool d) {
	return GetPrivateProfileIntA(s, k, d ? 1 : 0, g_iniPath.c_str()) != 0;
}

static bool readCsvField(std::stringstream& row, std::string& out);
static void loadSharedItemPools();
// #50. Defined next to the bloodstain state it fills, which lives further down.
static void loadBloodstainSettings();
// #8. Defined in modules/gameplay_camera.cpp below; reloading the INI must also
// refresh camera transition speed and profiles instead of requiring a restart.
static void loadGameplayCameraConfig();
static void loadConfig() {
	loadCompendiumGlintProbeConfig();
	g_humanStamEnabled = readB("HumanStamina", "Enabled", true);
	g_staminaShowMode = readB("HumanStamina", "ShowMode", false);
	g_humanIdleRate = readF("HumanStamina", "StandingRate", 12.0f);
	g_humanWalkRate = readF("HumanStamina", "WalkingSneakingRate", 6.0f);
	g_humanJogRate = readF("HumanStamina", "JoggingRate", -4.0f);
	g_humanSprintRate = readF("HumanStamina", "SprintingRate", -12.0f);
	g_humanSwimRate = readF("HumanStamina", "SwimmingRate", -8.0f);
	g_humanRoadDrainMultiplier = (std::max)(0.0f, (std::min)(1.0f,
		readF("HumanStamina", "RoadDrainMultiplier", 0.5f)));

	g_horseStamEnabled = readB("HorseStamina", "Enabled", true);
	g_horseIdleRate = readF("HorseStamina", "StandingRate", 16.0f);
	g_horseWalkRate = readF("HorseStamina", "WalkingRate", 8.0f);
	g_horseTrotRate = readF("HorseStamina", "TrottingRate", 2.0f);
	g_horseCanterRate = readF("HorseStamina", "CanteringRate", -6.0f);
	g_horseGallopRate = readF("HorseStamina", "GallopingRate", -14.0f);
	g_horseSwimRate = readF("HorseStamina", "SwimmingRate", -8.0f);
	g_horseRoadDrainMultiplier = (std::max)(0.0f, (std::min)(1.0f,
		readF("HorseStamina", "RoadDrainMultiplier", 0.5f)));

	// Campsites: key is a Windows virtual-key code. 0x72 = F3, 0x73 = F4.
	// Read as a STRING and parsed base-0: GetPrivateProfileIntA stops at the 'x'
	// in "0x72" and silently returns 0, so hex in the ini would be ignored.
	{
		char keyBuf[32] = {};
		GetPrivateProfileStringA("Campsites", "Key", "0x72", keyBuf,
			sizeof(keyBuf), g_iniPath.c_str());
		g_campKey = (int)strtol(keyBuf, nullptr, 0);
	}
	g_campRespawnWindowMs = GetPrivateProfileIntA("Campsites", "RespawnWindowMs",
		15000, g_iniPath.c_str());
	if (g_campKey <= 0 || g_campKey > 0xFE) g_campKey = 0x72;
	if (g_campRespawnWindowMs < 1000) g_campRespawnWindowMs = 1000;

	g_animalEnabled = readB("AnimalDensity", "Enabled", false);
	g_animalMult = readF("AnimalDensity", "Multiplier", 1.0f);
	g_coreXPGainEnabled = readB("CoreXPGain", "Enabled", false);
	g_coreClockEnabled = readB("CoreClock", "Enabled", true);
	g_healthDrainHours = readF("CoreClock", "HealthDrainHours", 24.0f);
	g_staminaDrainHours = readF("CoreClock", "StaminaDrainHours", 24.0f);
	g_deadeyeDrainHours = readF("CoreClock", "DeadEyeDrainHours", 24.0f);
	g_deadeyeSleepRefillHours = readF("CoreClock", "DeadEyeSleepRefillHours", 12.0f);
	if (g_healthDrainHours < 0.01f) g_healthDrainHours = 0.01f;
	if (g_staminaDrainHours < 0.01f) g_staminaDrainHours = 0.01f;
	if (g_deadeyeDrainHours < 0.01f) g_deadeyeDrainHours = 0.01f;
	if (g_deadeyeSleepRefillHours < 0.01f) g_deadeyeSleepRefillHours = 0.01f;
	g_toxicityEnabled = readB("Toxicity", "Enabled", true);
	g_toxicHealthDrainPointsPerSecond = readF("Toxicity",
		"HealthBarDrainPointsPerSecond", 1.0f);
	if (g_toxicHealthDrainPointsPerSecond < 0.0f)
		g_toxicHealthDrainPointsPerSecond = 0.0f;
	g_temperatureEnabled = readB("Temperature", "Enabled", true);
	g_temperatureBaseDrainHours = readF("Temperature", "BaseDrainHours", 24.0f);
	g_heatDrainMultiplier = readF("Temperature", "HeatDrainMultiplier", 1.0f);
	g_coldDrainMultiplier = readF("Temperature", "ColdDrainMultiplier", 1.0f);
	if (g_temperatureBaseDrainHours < 0.01f) g_temperatureBaseDrainHours = 0.01f;
	if (g_heatDrainMultiplier < 0.0f) g_heatDrainMultiplier = 0.0f;
	if (g_coldDrainMultiplier < 0.0f) g_coldDrainMultiplier = 0.0f;
	// #125. Bar points per second while Dead Eye is active. The engine treats
	// zero as its default cost, so zero is not a supported no-drain value. The
	// saved value is normalized too: the editor/INI must show the same value the
	// runtime actually applies instead of retaining a misleading out-of-range
	// request.
	const float requestedDeadeyeConsumption =
		readF("DeadEye", "ConsumptionPointsPerSecond", 1.0f);
	g_deadeyeConsumptionRate = requestedDeadeyeConsumption;
	if (g_deadeyeConsumptionRate < 1.0f) g_deadeyeConsumptionRate = 1.0f;
	if (g_deadeyeConsumptionRate > 100.0f) g_deadeyeConsumptionRate = 100.0f;
	if (g_deadeyeConsumptionRate != requestedDeadeyeConsumption) {
		std::ostringstream normalized;
		normalized << g_deadeyeConsumptionRate;
		WritePrivateProfileStringA("DeadEye", "ConsumptionPointsPerSecond",
			normalized.str().c_str(), g_iniPath.c_str());
		gtLog("deadeye-rate", GT_WARN,
			std::string("normalized saved ConsumptionPointsPerSecond from ") +
			std::to_string(requestedDeadeyeConsumption) + " to " +
			normalized.str());
	}
	g_noReserveCores = readB("NoReserveCores", "Enabled", true);
	g_deadeyeEmptyFrac = readF("NoReserveCores", "DeadEyeEmptyPercent", 1.0f) / 100.0f;
	if (g_deadeyeEmptyFrac < 0.01f) g_deadeyeEmptyFrac = 0.01f;
	if (g_deadeyeEmptyFrac > 0.9f) g_deadeyeEmptyFrac = 0.9f;
	g_wagonCoreEnabled = readB("WagonCores", "Enabled", true);
	g_wagonCoreDrain = readF("WagonCores", "DrainPerSecond", 0.25f);
	g_wagonMinSpeed = readF("WagonCores", "MinimumSpeed", 1.0f);
	g_trainTracking = readB("TrainTracking", "Enabled", true);
	g_collectiblesEnabled = readB("CollectibleMap", "Enabled", true);
	g_collectCards = readB("CollectibleMap", "CigaretteCards", true);
	g_collectBones = readB("CollectibleMap", "DinosaurBones", true);
	g_collectCarvings = readB("CollectibleMap", "RockCarvings", true);
	g_collectDreamcatchers = readB("CollectibleMap", "Dreamcatchers", true);
	g_collectGraves = readB("CollectibleMap", "Graves", true);
	g_collectExotics = readB("CollectibleMap", "Exotics", true);
	g_collectLegendaryFish = readB("CollectibleMap", "LegendaryFish", true);
	g_collectShacks = readB("CollectibleMap", "Shacks", true);
	g_collectTreasureClues = readB("CollectibleMap", "TreasureClues", true);
	g_collectPois = readB("CollectibleMap", "PointsOfInterest", true);
	g_collectGangHideouts = readB("CollectibleMap", "GangHideouts", true);
	g_collectAutoClear = readB("CollectibleMap", "AutoClearOnReach", false);
	g_collectMoveMaxDistance = (std::max)(1.0f,
		readF("CollectibleMap", "DeveloperMoveMaxDistance", 150.0f));
	g_collectProbeEnabled = developmentModeActive() &&
		readB("CollectibleProbe", "Enabled", false);
	g_sharedAmmoEnabled = readB("SharedAmmoCaps", "Enabled", true);
	g_radialAmmoEnabled = readB("RadialAmmoScroll", "Enabled", true);
	g_radialAmmoRequireOwned = readB("RadialAmmoScroll", "RequireOwnedAmmo", true);
	g_radialAmmoWrap = readB("RadialAmmoScroll", "Wrap", true);
	g_radialAmmoShowFeed = readB("RadialAmmoScroll", "ShowFeedText", true);
	g_radialAmmoCentreDeadzone = (std::max)(0.02f, (std::min)(0.45f, readF("RadialAmmoScroll", "CentreDeadzone", 0.18f)));
	{
		char mode[32] = {};
		GetPrivateProfileStringA("ProjectileVisibility", "Mode", "luminous_streak",
			mode, sizeof(mode), g_iniPath.c_str());
		for (char& c : mode) c = (char)tolower((unsigned char)c);
		g_projectileVisibilityMode = strcmp(mode, "corona") == 0 ? 2 :
			(strcmp(mode, "off") == 0 || strcmp(mode, "disabled") == 0 ? 0 : 4);
	}
	g_projectileMarkerSpeed = (std::max)(0.1f, readF("ProjectileSpeed", "GlobalFirearmSpeed", 20.0f));
	g_sharedItemCapsEnabled = readB("SharedItemCaps", "Enabled", true);
	g_itemCapHerbs = GetPrivateProfileIntA("SharedItemCaps", "Herbs", 0, g_iniPath.c_str());
	g_itemCapFood  = GetPrivateProfileIntA("SharedItemCaps", "Food",  0, g_iniPath.c_str());
	g_ammoCap225      = GetPrivateProfileIntA("SharedAmmoCaps", "Caliber225", 0, g_iniPath.c_str());
	g_ammoCap307      = GetPrivateProfileIntA("SharedAmmoCaps", "Caliber307", 0, g_iniPath.c_str());
	g_ammoCap444      = GetPrivateProfileIntA("SharedAmmoCaps", "Caliber444", 0, g_iniPath.c_str());
	g_ammoCapShotgun  = GetPrivateProfileIntA("SharedAmmoCaps", "Shotgun",  0, g_iniPath.c_str());
	g_ammoCapArrow    = GetPrivateProfileIntA("SharedAmmoCaps", "Arrow",    0, g_iniPath.c_str());
	g_proneEnabled = readB("Prone", "Enabled", true);
	g_proneTrace = developmentModeActive() &&
		readB("Prone", "DevelopmentTrace", true);
	g_proneHoldMs = GetPrivateProfileIntA("Prone", "HoldMs", 500, g_iniPath.c_str());
	g_proneHoldMs = (std::max)(150, (std::min)(1500, g_proneHoldMs));
	g_proneMoveSpeedMultiplier = readF("Prone", "MoveSpeedMultiplier", 1.0f);
	g_proneMoveSpeedMultiplier = (std::max)(0.25f,
		(std::min)(3.0f, g_proneMoveSpeedMultiplier));
	g_proneCrawlSpeed = readF("Prone", "CrawlSpeed", 0.85f);
	g_proneCrawlSpeed = (std::max)(0.10f, (std::min)(4.0f, g_proneCrawlSpeed));
	g_proneFloorClamp = readB("Prone", "FloorClamp", true);
	g_proneGroundClearance = (std::max)(0.0f, (std::min)(0.50f, readF("Prone", "GroundClearanceMeters", 0.05f)));
	g_proneWaterHeadClearance = readF("Prone", "WaterHeadClearance", 0.30f);
	g_proneWaterHeadClearance = (std::max)(0.0f,
		(std::min)(3.0f, g_proneWaterHeadClearance));
	g_proneTurnSpeed = readF("Prone", "TurnDegreesPerSecond", 120.0f);
	g_proneTurnSpeed = (std::max)(90.0f, (std::min)(720.0f, g_proneTurnSpeed));
	g_reserveSprintCutBar = readF("NoReserveCores", "SprintCutBarPercent", 3.0f);
	g_reserveSprintCutBar = (std::max)(0.1f, (std::min)(25.0f, g_reserveSprintCutBar));
	g_reserveBarFloor = readF("NoReserveCores", "BarFloorPercent", 10.0f);
	g_reserveBarFloor = (std::max)(1.0f, (std::min)(50.0f, g_reserveBarFloor));
	g_proneWheelGraceMs = GetPrivateProfileIntA("Prone", "WheelGraceMs", 250,
		g_iniPath.c_str());
	g_proneWheelGraceMs = (std::max)(0, (std::min)(1000, g_proneWheelGraceMs));
	g_proneEquipHoldMs = GetPrivateProfileIntA("Prone", "EquipHoldMs", 700,
		g_iniPath.c_str());
	g_proneEquipHoldMs = (std::max)(0, (std::min)(2500, g_proneEquipHoldMs));
	g_proneBinocularMode = GetPrivateProfileIntA("Prone", "BinocularMode", 0,
		g_iniPath.c_str());
	g_proneBinocularMode = (std::max)(0, (std::min)(1, g_proneBinocularMode));
	g_proneBlockWeaponActions = readB("Prone", "BlockWeaponActions", true);
	g_proneGroundedAimMode = GetPrivateProfileIntA("Prone", "GroundedAimMode", 0,
		g_iniPath.c_str());
	g_proneGroundedAimMode = (std::max)(0, (std::min)(1, g_proneGroundedAimMode));
	g_proneOneHandedWeapons = g_proneGroundedAimMode == 1;
	g_proneEntryStyle = GetPrivateProfileIntA("Prone", "EntryStyle", 0, g_iniPath.c_str());
	g_proneEntryStyle = (std::max)(0, (std::min)(2, g_proneEntryStyle));
	g_proneBlockActions = readB("Prone", "BlockActionsWhileProne", true);
	g_proneAlignGround = readB("Prone", "AlignToGround", true);
	g_pronePitchSign = readF("Prone", "PitchSign", -1.0f) >= 0.0f ? 1.0f : -1.0f;
	g_proneRollSign = readF("Prone", "RollSign", 1.0f) >= 0.0f ? 1.0f : -1.0f;
	g_collectClearRadius = readF("CollectibleMap", "ClearRadius", 6.0f);
	if (g_collectClearRadius < 1.0f) g_collectClearRadius = 1.0f;
	g_collectiblesDirty = true;
	g_banditMasksEnabled = readB("BanditMasks", "Enabled", true);
	g_witnessTalkChance = readF("BanditMasks", "MetalWitnessTalkChance", 0.5f);
	g_fenceMoneyMult = readF("BanditMasks", "PigFenceMoneyMultiplier", 2.0f);
	g_bountyGainMult = readF("BanditMasks", "SackBountyGainMultiplier", 0.5f);
	g_catHorseRegenMult = readF("BanditMasks", "CatHorseRecoveryMultiplier", 2.0f);
	g_psychoMeleeMult = readF("BanditMasks", "PsychoMeleeDamageMultiplier", 2.0f);
	g_psychoBulletTakenMult = readF("BanditMasks", "PsychoBulletDamageTakenMultiplier", 0.5f);
	g_paganHonorLossMult = readF("BanditMasks", "PaganHonorLossMultiplier", 2.0f);
	g_lawPerceptionMult = readF("BanditMasks", "BanditMasterLawPerceptionMultiplier", 0.5f);
	g_walletCapEnabled = readB("WalletCap", "Enabled", true);
	{
		static const float defaults[11] = { 1.0f, 2.0f, 4.0f, 7.5f, 12.5f, 20.0f,
			40.0f, 75.0f, 150.0f, 250.0f, 0.0f };
		for (int rank = 0; rank <= 10; ++rank) {
			char key[32];
			sprintf_s(key, "Rank%dDollars", rank);
			const float dollars = (std::max)(0.0f, readF("WalletCap", key, defaults[rank]));
			g_walletCapCents[rank] = (int)floorf(dollars * 100.0f + 0.5f);
		}
	}
	char glasses[96] = {};
	GetPrivateProfileStringA("BanditMasks", "Rank4GlassesItem", "", glasses, sizeof(glasses), g_iniPath.c_str());
	g_rank4GlassesItem = glasses;
	g_honorPricesEnabled = readB("HonorPrices", "Enabled", true);
	g_fenceHonorReversed = readB("HonorPrices", "FenceReversed", true);
	g_bottleProbeEnabled = developmentModeActive() &&
		readB("BottleProbe", "Enabled", false);
	g_emptyBottlesEnabled = readB("EmptyBottles", "Enabled", true);
	g_humanTonicBottles = readB("EmptyBottles", "HumanTonicBottles", false);
	g_emptyBottleStowDelayMs = GetPrivateProfileIntA("EmptyBottles", "StowDelayMs", 1450, g_iniPath.c_str());
	g_emptyBottleStowDelayMs = (std::max)(900, (std::min)(1750, g_emptyBottleStowDelayMs));
	g_carriedMaskEnabled = readB("CarriedMask", "Enabled", true);
	char carriedMaskBuf[80] = {};
	GetPrivateProfileStringA("CarriedMask", "Item", "KIT_MASK_GREY_CLOTH",
		carriedMaskBuf, sizeof(carriedMaskBuf), g_iniPath.c_str());
	g_carriedMask = carriedMaskBuf;
	g_binocularsEnabled = readB("Binoculars", "Enabled", true);
	g_binocularsHoldMs = GetPrivateProfileIntA("Binoculars", "HoldMs", 250, g_iniPath.c_str());
	if (g_binocularsHoldMs < 50) g_binocularsHoldMs = 50;
	if (g_binocularsHoldMs > 2000) g_binocularsHoldMs = 2000;
	g_binocularsRequireOwned = readB("Binoculars", "RequireOwned", true);
	{
		char k[16] = {};
		GetPrivateProfileStringA("Binoculars", "KeyboardKey", "B", k, sizeof(k), g_iniPath.c_str());
		g_binocularsKey = (k[0] >= 'a' && k[0] <= 'z') ? (k[0] - 32) : (k[0] ? k[0] : 0x42);
	}
	g_binocularsInstantEquip = readB("Binoculars", "InstantEquip", false);
	g_binocularsDrawMs = GetPrivateProfileIntA("Binoculars", "DrawMs", 900, g_iniPath.c_str());
	g_binocularsStowMs = GetPrivateProfileIntA("Binoculars", "StowMs", 900, g_iniPath.c_str());
	if (g_binocularsDrawMs < 0) g_binocularsDrawMs = 0;
	if (g_binocularsStowMs < 0) g_binocularsStowMs = 0;
	g_binocularMaskEnabled = readB("Binoculars", "MaskEnabled", true);
	g_binocularMaskScale = readF("Binoculars", "MaskScale", 1.0f);
	g_binocularMaskScale = (std::max)(0.60f, (std::min)(1.60f,
		g_binocularMaskScale));
	g_binocularMaskOpacity = readF("Binoculars", "MaskOpacity", 1.0f);
	g_binocularMaskOpacity = (std::max)(0.0f, (std::min)(1.0f,
		g_binocularMaskOpacity));
	g_binocularZoomReadout = readB("Binoculars", "ShowZoomReadout", true);
	{
		char mode[32] = {};
		GetPrivateProfileStringA("Binoculars", "HoldMode", "both", mode, sizeof(mode), g_iniPath.c_str());
		if (_stricmp(mode, "key") == 0 || _stricmp(mode, "keyboard") == 0 || _stricmp(mode, "F") == 0)
			g_binocularsHoldMode = 0;
		else if (_stricmp(mode, "pad") == 0 || _stricmp(mode, "controller") == 0 || _stricmp(mode, "rs") == 0)
			g_binocularsHoldMode = 1;
		else
			g_binocularsHoldMode = 2; // both
	}
	{
		char btn[32] = {};
		GetPrivateProfileStringA("Binoculars", "PadButton", "rs", btn, sizeof(btn), g_iniPath.c_str());
		g_binocularPadMask = xinputButtonFromName(btn);
	}
	g_reconTaggingEnabled = readB("ReconTagging", "Enabled", true);
	g_reconBlipsEnabled = readB("ReconTagging", "MinimapBlips", true);
	g_reconMarkedOnlyMinimap = readB("ReconTagging", "MarkedOnlyMinimap", true);
	const int legacyObserveMs = GetPrivateProfileIntA("ReconTagging", "ObserveMs", 900, g_iniPath.c_str());
	g_reconObserveMs = GetPrivateProfileIntA("ReconTagging", "StudyTimeMs", legacyObserveMs, g_iniPath.c_str());
	g_reconObserveMs = (std::max)(150, (std::min)(5000, g_reconObserveMs));
	const float legacyMinHeight = readF("ReconTagging", "MinApparentHeight", 0.025f);
	g_reconMinProjectedExtent = readF("ReconTagging", "MinProjectedExtent", legacyMinHeight);
	g_reconMinProjectedExtent = (std::max)(0.002f, (std::min)(0.50f, g_reconMinProjectedExtent));
	g_reconMaxDistance = readF("ReconTagging", "MaxDistanceMeters", 350.0f);
	g_reconMaxDistance = (std::max)(5.0f, (std::min)(1000.0f, g_reconMaxDistance));
	const float legacyReticleRadius = readF("ReconTagging", "ReticleRadius", 0.060f);
	g_reconAimRadius = readF("ReconTagging", "AimToleranceScreenRadius", legacyReticleRadius);
	g_reconAimRadius = (std::max)(0.005f, (std::min)(0.15f, g_reconAimRadius));
	g_reconMaxTags = GetPrivateProfileIntA("ReconTagging", "MaxTags", 24, g_iniPath.c_str());
	g_reconTagPickups = readB("ReconTagging", "TagPlantsAndPickups", true);
	g_reconPlantsOnly = readB("ReconTagging", "PlantsOnly", true);
	g_reconMaxTags = (std::max)(1, (std::min)(64, g_reconMaxTags));
	g_climbingEnabled = readB("Climbing", "Enabled", true);
	g_climbingTrace = developmentModeActive() &&
		readB("Climbing", "DevelopmentTrace", true);
	g_climbIdleDrain = (std::max)(0.0f, readF("Climbing", "IdleStaminaPerSecond", 0.35f));
	g_climbMoveDrain = (std::max)(0.0f, readF("Climbing", "MoveStaminaPerSecond", 1.25f));
	g_climbSprintDrain = (std::max)(0.0f, readF("Climbing", "SprintStaminaPerSecond", 2.5f));
	g_climbMoveSpeed = (std::max)(0.1f, (std::min)(3.0f, readF("Climbing", "MoveMetersPerSecond", 0.75f)));
	g_climbSprintSpeed = (std::max)(g_climbMoveSpeed, (std::min)(5.0f, readF("Climbing", "SprintMetersPerSecond", 1.25f)));
	g_climbLeapCost = (std::max)(0.0f, readF("Climbing", "LeapStaminaCost", 12.0f));
	g_climbLeapDistance = (std::max)(0.5f, (std::min)(8.0f, readF("Climbing", "LeapDistanceMeters", 3.2f)));
	g_climbGrabDistance = (std::max)(0.35f, (std::min)(1.8f, readF("Climbing", "GrabDistanceMeters", 1.10f)));
	g_climbMinSurfaceAngle = (std::max)(35.0f, (std::min)(88.0f, readF("Climbing", "MinimumSurfaceAngleDegrees", 45.0f)));
	g_climbSurfaceOffset = (std::max)(0.10f, (std::min)(0.60f, readF("Climbing", "SurfaceOffsetMeters", 0.30f)));
	g_climbTopOutClearance = (std::max)(0.10f, (std::min)(1.50f, readF("Climbing", "TopOutClearanceMeters", 0.45f)));
	g_climbProbeTolerance = (std::max)(0.10f, (std::min)(1.0f, readF("Climbing", "ProbeToleranceMeters", 0.42f)));
	g_climbSmoothing = (std::max)(1.0f, (std::min)(30.0f, readF("Climbing", "SurfaceSmoothing", 12.0f)));
	g_climbPitchAlign = readB("Climbing", "AlignPitchToSurface", true);
	g_climbFacingOffset = readF("Climbing", "FacingOffsetDegrees", 180.0f);
	g_climbMotionBlendMs = GetPrivateProfileIntA("Climbing", "MotionBlendMs", 220,
		g_iniPath.c_str());
	g_climbMotionBlendMs = (std::max)(0, (std::min)(1000, g_climbMotionBlendMs));
	g_climbNormalHoldMs = GetPrivateProfileIntA("Climbing", "SurfaceHoldMs", 180,
		g_iniPath.c_str());
	g_climbNormalHoldMs = (std::max)(0, (std::min)(1000, g_climbNormalHoldMs));
	g_alwaysHolster = readB("AlwaysHolster", "Enabled", true);
	g_alwaysHolsterLog = readB("AlwaysHolster", "Log", false);
	g_beltLanternEnabled = readB("BeltLantern", "Enabled", true);
	g_beltLanternOnHour = (std::max)(0, (std::min)(23,
		(int)GetPrivateProfileIntA("BeltLantern", "LightsAtHour", 19, g_iniPath.c_str())));
	g_beltLanternOffHour = (std::max)(0, (std::min)(23,
		(int)GetPrivateProfileIntA("BeltLantern", "OutAtHour", 6, g_iniPath.c_str())));
	g_beltLanternRange = (std::max)(1.0f, (std::min)(30.0f,
		readF("BeltLantern", "Range", 7.5f)));
	g_beltLanternBrightness = (std::max)(0.0f, (std::min)(20.0f,
		readF("BeltLantern", "Brightness", 3.2f)));
	g_beltLanternScale = (std::max)(0.25f, (std::min)(2.0f,
		readF("BeltLantern", "Scale", 1.0f)));
	g_climbGripSettleMs = (std::max)(0, (std::min)(2000,
		(int)GetPrivateProfileIntA("Climbing", "GripSettleMs", 400, g_iniPath.c_str())));
	g_climbPitchSign = readF("Climbing", "PitchSign", -1.0f) >= 0.0f ? 1.0f : -1.0f;
	g_spentCasingsEnabled = readB("SpentCasings", "Enabled", true);
	g_spentCasingLifetimeSeconds = GetPrivateProfileIntA("SpentCasings", "LifetimeSeconds", 600, g_iniPath.c_str());
	g_spentCasingMaximum = GetPrivateProfileIntA("SpentCasings", "MaximumWorldCasings", 128, g_iniPath.c_str());
	g_casingCycleWindowMs = GetPrivateProfileIntA("SpentCasings", "CycleWindowMs",
		8000, g_iniPath.c_str());
	g_casingCycleWindowMs = (std::max)(500, (std::min)(20000, g_casingCycleWindowMs));
	g_casingPickupRange = readF("SpentCasings", "PickupRange", 1.8f);
	if (g_casingPickupRange < 0.5f) g_casingPickupRange = 0.5f;
	if (g_casingPickupRange > 5.0f) g_casingPickupRange = 5.0f;
	g_casingLookAngleDeg = readF("SpentCasings", "PickupLookAngleDeg", 20.0f);
	if (g_casingLookAngleDeg < 3.0f) g_casingLookAngleDeg = 3.0f;
	if (g_casingLookAngleDeg > 180.0f) g_casingLookAngleDeg = 180.0f;
	char casingBuf[96] = {};
	GetPrivateProfileStringA("SpentCasings", "PickupSoundName", "SELECT", casingBuf, sizeof(casingBuf), g_iniPath.c_str());
	g_casingSoundName = casingBuf;
	GetPrivateProfileStringA("SpentCasings", "PickupSoundSet", "HUD_SHOP_SOUNDSET", casingBuf, sizeof(casingBuf), g_iniPath.c_str());
	g_casingSoundSet = casingBuf;
	loadBloodstainSettings();
	g_casingGlowIntensity = readF("SpentCasings", "GlowIntensity", 0.3f);
	if (g_casingGlowIntensity < 0.0f) g_casingGlowIntensity = 0.0f;
	if (g_casingGlowIntensity > 10.0f) g_casingGlowIntensity = 10.0f;
	g_casingGlowRange = readF("SpentCasings", "GlowRange", 0.7f);
	if (g_casingGlowRange < 0.05f) g_casingGlowRange = 0.05f;
	if (g_casingGlowRange > 10.0f) g_casingGlowRange = 10.0f;
	g_casingGlowYellowness = readF("SpentCasings", "GlowYellowness", 0.85f);
	if (g_casingGlowYellowness < 0.0f) g_casingGlowYellowness = 0.0f;
	if (g_casingGlowYellowness > 1.0f) g_casingGlowYellowness = 1.0f;
	g_casingGlintEnabled = readB("SpentCasings", "GlintEnabled", true);
	g_casingGlintSize = readF("SpentCasings", "GlintSize", 1.5f);
	if (g_casingGlintSize < 0.05f) g_casingGlintSize = 0.05f;
	if (g_casingGlintSize > 10.0f) g_casingGlintSize = 10.0f;
	g_casingGlintAlpha = readF("SpentCasings", "GlintAlpha", 0.45f);
	g_casingGlintAlpha = (std::max)(0.0f, (std::min)(1.0f, g_casingGlintAlpha));
	g_casingGlintBrightness = readF("SpentCasings", "GlintBrightness", 0.75f);
	g_casingGlintBrightness = (std::max)(0.0f,
		(std::min)(1.0f, g_casingGlintBrightness));
	g_casingGlintDurationMs = (std::max)(50, (std::min)(10000,
		(int)GetPrivateProfileIntA("SpentCasings", "GlintDurationMs", 1200, g_iniPath.c_str())));
	g_casingGlintFadeInMs = (std::max)(0, (std::min)(5000,
		(int)GetPrivateProfileIntA("SpentCasings", "GlintFadeInMs", 250, g_iniPath.c_str())));
	g_casingGlintFadeOutMs = (std::max)(0, (std::min)(5000,
		(int)GetPrivateProfileIntA("SpentCasings", "GlintFadeOutMs", 450, g_iniPath.c_str())));
	g_casingGlintPauseMs = (std::max)(0, (std::min)(30000,
		(int)GetPrivateProfileIntA("SpentCasings", "GlintPauseMs", 1600, g_iniPath.c_str())));
	g_casingGlintTimingRandomnessMs = (std::max)(0, (std::min)(30000,
		(int)GetPrivateProfileIntA("SpentCasings", "GlintTimingRandomnessMs", 1000,
			g_iniPath.c_str())));
	g_spentCasingDebugMarker = developmentModeActive() &&
		readB("SpentCasings", "DebugMarker", false);
	GetPrivateProfileStringA("SpentCasings", "PickupMode", "native", casingBuf, sizeof(casingBuf), g_iniPath.c_str());
	g_casingMode = (_stricmp(casingBuf, "native") == 0 || _stricmp(casingBuf, "tab") == 0) ? 0 : 2;
	g_combatRollEnabled = readB("CombatRoll", "Enabled", true);
	g_combatRollTrace = developmentModeActive() &&
		readB("CombatRoll", "DevelopmentTrace", true);
	g_combatRollStaminaCost = (std::max)(0.0f,
		readF("CombatRoll", "StaminaCost", 10.0f));
	g_combatRollInvulnerabilitySeconds = (std::max)(0.0f, (std::min)(10.0f,
		readF("CombatRoll", "InvulnerabilitySeconds", 0.35f)));
	g_combatRollRecoverySeconds = (std::max)(0.20f, (std::min)(10.0f,
		readF("CombatRoll", "RecoverySeconds", 0.35f)));
	g_combatRollInvulnerabilityOpacityPercent = (std::max)(0.0f, (std::min)(100.0f,
		readF("CombatRoll", "InvulnerabilityOpacityPercent", 55.0f)));
	g_camPitchEnabled = readB("CameraPitch", "Enabled", true);
	g_camPitchMin = readF("CameraPitch", "MinPitchDeg", -85.0f);
	g_camPitchMax = readF("CameraPitch", "MaxPitchDeg", 45.0f);
	if (g_camPitchMin < -89.0f) g_camPitchMin = -89.0f;
	if (g_camPitchMax > 89.0f) g_camPitchMax = 89.0f;
	g_recoverUniqueWeapons = readB("RecoverableUniqueWeapons", "Enabled", true);
	g_hunterHatchetEnabled = readB("HunterHatchet", "Enabled", true);
	g_duplicateCardsEnabled = readB("DuplicateCigaretteCards", "Enabled", true);
	if (g_spentCasingLifetimeSeconds < 10) g_spentCasingLifetimeSeconds = 10;
	if (g_spentCasingMaximum < 1) g_spentCasingMaximum = 1;
	if (g_spentCasingMaximum > 512) g_spentCasingMaximum = 512;
	loadSharedItemPools();
	static const float defaults[17] = { 1.50f,1.50f,1.50f,1.25f,1.25f,1.25f,1.10f,1.0f,1.0f,1.0f,0.90f,0.90f,0.90f,0.75f,0.75f,0.50f,0.50f };
	for (int rank = -8; rank <= 8; ++rank) { char key[24]; sprintf_s(key, "Rank%+dMultiplier", rank); g_honorPrice[rank + 8] = readF("HonorPrices", key, defaults[rank + 8]); }
	loadGameplayCameraConfig();
}

static bool wearing(const char* item) { return g_banditMasksEnabled && INVENTORY_ITEM_EQUIPPED(joaat(item)); }

static int honorValue() { int value = 0; STAT_GET(joaat("HONOR_CURRENT"), &value); return value; }
static int honorRank(int value) { int rank = value / 40; return rank < -8 ? -8 : rank > 8 ? 8 : rank; }
static bool scriptRunning(const char* name) { return SCRIPT_REFS(joaat(name)) > 0; }
static bool shopActive() {
	static const char* names[] = { "shop_bait","shop_barber","shop_butcher","shop_doctor","shop_dynamic","shop_fence","shop_general","shop_gunsmith","shop_horse_shop_sp","shop_hotel","shop_market","shop_newspaper_boy","shop_pearson","shop_photo_studio","shop_post_office","shop_tailor","shop_train_station","shop_trapper" };
	for (const char* name : names) if (scriptRunning(name)) return true; return false;
}
static bool fenceActive() { return scriptRunning("shop_fence") || scriptRunning("stable_mount") || scriptRunning("generic_wagon_fence_core"); }

// Every Story shop inserts its honor multiplier under this modifier key in
// Global_1914319.f_3[shop].f_35.f_141. The catalog UI and transaction both
// read this same value, so changing it here keeps the shown price, affordability
// check, and charged price identical.
static void updateHonorShopPriceModifier() {
	// Do not touch the shop-global modifier table during interaction startup.
	// The shop scripts own that transition.  The price table is relevant only
	// after Rockstar has opened SHOP_MENU, where both the displayed price and
	// the transaction read the same modifier entry.
	if (!g_honorPricesEnabled || !shopActive() || !UIAPP_ACTIVE(joaat("SHOP_MENU"))) return;
	int rank = honorRank(honorValue());
	float desired = (g_fenceHonorReversed && fenceActive())
		? g_honorPrice[8 - rank]
		: ((rank < 0 && wearing("KIT_MASK_BLACK_HOOD")) ? 1.0f : g_honorPrice[rank + 8]);
	constexpr int kShopGlobal = 1914319;
	constexpr int kShopArrayOffset = 3;
	constexpr int kShopStride = 446;
	constexpr int kPriceDataOffset = 35;
	constexpr int kModifiersOffset = 141;
	constexpr int kModifierStride = 7;
	constexpr int kModifierCount = 20;
	// #114 ROOT CAUSE. This was 38. Rockstar bounds shop types at 35
	// (short_update.c:35377 `func_1090`: `iParam0 > -1 && iParam0 < 35`, plus
	// three `while (iVar0 < 35)` sweeps). With stride 446 and the array header,
	// f_3 occupies offsets 3..15613 and `f_15614` begins immediately after -
	// 3 + 1 + 35 * 446 == 15614 exactly. Looping to 38 therefore ran 1338 cells
	// past the end of the shop array, scanning and writing floats straight
	// through `f_15614` (the blip presentation bitmask that carries bit 16384,
	// BLIP_MODIFIER_LOCKED) and on into `f_16855` (the live shop/menu binding).
	// That single overrun produced the locked padlocked map icons, the blips
	// missing from the minimap via the modifier's 0.10 alpha, the churning
	// volume/perschar handles, SHOPKEEPER_DEAD with its "you killed me" dialogue,
	// shopkeepers failing to spawn, and the shop teardown/rebuild loop.
	constexpr int kShopSlots = 35;
	constexpr int kHonorModifier = -345829263;
	// #114. Script fixed arrays store their capacity in the first cell, so
	// Global_1914319.f_3[shop] begins at base + 3 + 1, not base + 3. The
	// missing +1 made every scan and every write land one cell short across all
	// 38 shop records, comparing the wrong cell against the honor modifier key
	// and, on a spurious match, writing a float into unrelated shop data. The
	// #114 probe settled the base empirically: only the +1 form resolves each
	// shop's perschar slot to the clerk ped the shop actually holds.
	constexpr int kShopArrayHeader = 1;
	for (int shop = 0; shop < kShopSlots; ++shop) {
		int first = kShopGlobal + kShopArrayOffset + kShopArrayHeader
			+ shop * kShopStride + kPriceDataOffset + kModifiersOffset;
		for (int modifier = 0; modifier < kModifierCount; ++modifier) {
			int entry = first + modifier * kModifierStride;
			if ((int)*getGlobalPtr(entry) != kHonorModifier) continue;
			float* multiplier = reinterpret_cast<float*>(getGlobalPtr(entry + 6));
			if (fabsf(*multiplier - desired) > 0.0001f) *multiplier = desired;
		}
	}
}
static bool isLaw(Ped p) { Hash group = REL_GROUP(p); return group == joaat("REL_COP") || group == joaat("REL_PINKERTONS"); }

static int clockMinute() { return CLOCK_HOUR() * 60 + CLOCK_MINUTE(); }
static int forwardMinutes(int from, int to) { int d = to - from; if (d < 0) d += 1440; return d; }

static int wholeCorePoints(double& bank) {
	int points = (int)(bank + 0.000001);
	bank -= points;
	return points;
}

static void drainCoreByMinutes(Ped ped, int core, int minutes, float fullDrainHours, double& bank, int& managedValue) {
	if (minutes <= 0) return;
	bank += (double)minutes * 100.0 / ((double)fullDrainHours * 60.0);
	int points = wholeCorePoints(bank);
	if (points <= 0) return;
	managedValue -= points;
	if (managedValue < 0) managedValue = 0;
	SET_CORE(ped, core, managedValue);
}

static void fillCoreByMinutes(Ped ped, int core, int minutes, float fullFillHours, double& bank, int& managedValue) {
	if (minutes <= 0) return;
	bank += (double)minutes * 100.0 / ((double)fullFillHours * 60.0);
	int points = wholeCorePoints(bank);
	if (points <= 0) return;
	managedValue += points;
	if (managedValue > 100) managedValue = 100;
	SET_CORE(ped, core, managedValue);
}

static void saveToxicityState() {
	WritePrivateProfileStringA("State", "Active", g_toxicActive ? "1" : "0",
		statePath("GameplayTweaks.toxicity.ini").c_str());
}

static void setToxicity(bool active) {
	if (g_toxicActive == active) return;
	g_toxicActive = active;
	Ped ped = PLAYER::PLAYER_PED_ID();
	if (ped) SET_ATTRIBUTE_POINTS(ped, 11, active ? 100 : 0); // SA_POISONED
	if (active) START_STATUS_ICON(5); // STATUS_SNAKE_VENOM / Toxic
	else STOP_STATUS_ICON(5);
	saveToxicityState();
}

static bool isToxicCure(Hash item) {
	return item == joaat("CONSUMABLE_MEDICINE") ||
		item == joaat("CONSUMABLE_MEDICINE_USED") ||
		item == joaat("CONSUMABLE_POTENT_MEDICINE") ||
		item == joaat("CONSUMABLE_SPECIAL_MEDICINE_CRAFTED");
}

static void updateToxicInteraction(Ped ped) {
	if (!g_toxicityEnabled) {
		if (g_toxicActive) setToxicity(false);
		g_recentToxicInteraction = 0;
		g_toxicCountsInitialized = false;
		return;
	}
	static const Hash items[5] = {
		joaat("CONSUMABLE_HERB_OLEANDER_SAGE"),
		joaat("CONSUMABLE_MEDICINE"),
		joaat("CONSUMABLE_MEDICINE_USED"),
		joaat("CONSUMABLE_POTENT_MEDICINE"),
		joaat("CONSUMABLE_SPECIAL_MEDICINE_CRAFTED")
	};
	if (!g_toxicCountsInitialized) {
		for (int i = 0; i < 5; ++i) g_toxicItemCounts[i] = INVENTORY_ITEM_COUNT(items[i]);
		g_toxicCountsInitialized = true;
	}
	DWORD now = GetTickCount();
	if (ITEM_INTERACTION_RUNNING(ped)) {
		Hash item = ITEM_INTERACTION_ITEM(ped);
		if (item) { g_recentToxicInteraction = item; g_recentToxicInteractionAt = now; }
	}
	for (int i = 0; i < 5; ++i) {
		int current = INVENTORY_ITEM_COUNT(items[i]);
		if (current < g_toxicItemCounts[i] && g_recentToxicInteraction == items[i] &&
			now - g_recentToxicInteractionAt <= 3000) {
			if (i == 0) setToxicity(true);
			else if (isToxicCure(items[i])) setToxicity(false);
		}
		g_toxicItemCounts[i] = current;
	}
	if (g_toxicActive && GET_ATTRIBUTE_POINTS(ped, 11) < 100)
		SET_ATTRIBUTE_POINTS(ped, 11, 100);
}

static void updateToxicHealthDrain(Player player, Ped ped, DWORD now,
	bool active, double& bank) {
	static DWORD lastTick = 0;
	static bool rechargeSuppressed = false;
	static Player rechargePlayer = -1;
	static float previousRechargeMultiplier = 1.0f;

	if (!active || !ped || PED::IS_PED_DEAD_OR_DYING(ped, TRUE)) {
		if (rechargeSuppressed) {
			PLAYER::SET_PLAYER_HEALTH_RECHARGE_MULTIPLIER(rechargePlayer,
				previousRechargeMultiplier);
			gtLog("toxicity", GT_INFO, "natural Health regeneration restored");
		}
		rechargeSuppressed = false;
		rechargePlayer = -1;
		lastTick = 0;
		bank = 0.0;
		return;
	}

	if (!rechargeSuppressed || rechargePlayer != player) {
		if (rechargeSuppressed)
			PLAYER::SET_PLAYER_HEALTH_RECHARGE_MULTIPLIER(rechargePlayer,
				previousRechargeMultiplier);
		previousRechargeMultiplier =
			GET_PLAYER_HEALTH_RECHARGE_MULTIPLIER(player);
		rechargePlayer = player;
		rechargeSuppressed = true;
		lastTick = now;
		gtLog("toxicity", GT_INFO,
			"natural Health regeneration suppressed; real-time drain active");
	}

	// Rockstar may rewrite the multiplier, so enforce the owned zero while the
	// condition is active and restore the captured value when it clears.
	PLAYER::SET_PLAYER_HEALTH_RECHARGE_MULTIPLIER(player, 0.0f);
	if (!lastTick) { lastTick = now; return; }
	const DWORD elapsedMs = (std::min)(now - lastTick, static_cast<DWORD>(250));
	lastTick = now;
	bank += (double)g_toxicHealthDrainPointsPerSecond *
		((double)elapsedMs / 1000.0);
	const int points = wholeCorePoints(bank);
	if (points <= 0) return;

	const int health = GET_ENTITY_HEALTH(ped);
	if (health <= 100) return;
	// The bottom 100 entity-health points back the Health core. Toxic owns the
	// outer bar only and therefore never crosses that boundary.
	SET_ENTITY_HEALTH(ped, (std::max)(100, health - points));
}


// Feature code is organized by topic but deliberately included into this one
// translation unit. This preserves the existing internal-linkage state and call
// order while still producing one GameplayTweaks.asi. New cross-module APIs can
// be promoted to real headers independently instead of forcing an all-at-once ABI
// rewrite of several thousand lines of working gameplay code.
// Several independent HUD/gameplay systems need the current ped set. Calling
// ScriptHook's global-pool enumerator from each system (some every frame) made
// one frame perform multiple full pool walks and eventually produced the
// asynchronous ERROR:FFFFFFFF fatal. Share one short-lived snapshot instead.
// Callers still validate every handle before use.
static std::vector<Ped> g_sharedWorldPedSnapshot;
static DWORD g_sharedWorldPedSnapshotRefreshedAt = 0;
static DWORD g_sharedWorldPedSnapshotQuarantineUntil = 0;

static void quarantineSharedWorldPedSnapshot(DWORD until) {
	g_sharedWorldPedSnapshot.clear();
	g_sharedWorldPedSnapshotRefreshedAt = 0;
	g_sharedWorldPedSnapshotQuarantineUntil = until;
}

static int sharedWorldPedSnapshot(Ped* destination, int capacity) {
	const DWORD now = GetTickCount();
	if (now < g_sharedWorldPedSnapshotQuarantineUntil) return 0;
	if (g_sharedWorldPedSnapshot.empty() ||
		now - g_sharedWorldPedSnapshotRefreshedAt >= 250) {
		int peds[256] = {};
		const int count = (std::max)(0, (std::min)(256,
			worldGetAllPeds(peds, (int)_countof(peds))));
		g_sharedWorldPedSnapshot.assign(peds, peds + count);
		g_sharedWorldPedSnapshotRefreshedAt = now;
	}
	const int copied = (std::max)(0,
		(std::min)(capacity, (int)g_sharedWorldPedSnapshot.size()));
	for (int index = 0; index < copied; ++index)
		destination[index] = g_sharedWorldPedSnapshot[index];
	return copied;
}

// Horse weapon selection is a live inventory/equip transaction. No mod-owned
// inventory or ammo-cap mutation may run while the wheel is open or during the
// short period in which Rockstar commits the selected horse weapon.
static bool weaponWheelTransactionBusy(DWORD now) {
	static DWORD lastOpenAt = 0;
	static const Hash kOpenWheel = joaat("INPUT_OPEN_WHEEL_MENU");
	const bool open =
		PAD::IS_CONTROL_PRESSED(0, kOpenWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, kOpenWheel) ||
		PAD::IS_CONTROL_PRESSED(2, kOpenWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, kOpenWheel);
	if (open) lastOpenAt = now;
	return open || (lastOpenAt && now - lastOpenAt < 2000);
}

#include "modules/collectibles_map.cpp"
#include "modules/world_collectible_masks.cpp"
#include "modules/newspaper_map.cpp"
#include "modules/campfire_icons.cpp"
#include "modules/campfire_policy.cpp"
#include "modules/animal_density.cpp"
#include "modules/world_economy.cpp"
#include "modules/bloodstain_hat.cpp"
#include "modules/always_holster.cpp"
#include "modules/wanted_system.cpp"
#include "modules/serious_crime_payoff.cpp"
#include "modules/child_vulnerability.cpp"
#include "modules/duplicate_cigarette_cards.cpp"
#include "modules/premium_cigarette_cards.cpp"
#include "modules/hunter_hatchet.cpp"
#include "modules/gameplay_camera.cpp"
#include "modules/belt_lantern.cpp"
#include "modules/ancient_tomahawk.cpp"
#include "modules/horse_camera.cpp"
#include "modules/horse_persistence.cpp"
#include "modules/horse_core_clock.cpp"
#include "modules/core_cost_guard.cpp"
#include "modules/shop_state_probe.cpp"
#include "modules/pocketwatch_time.cpp"
#include "modules/thermometer.cpp"
#include "modules/reusable_canteen.cpp"
#include "modules/water_pumps.cpp"
#include "modules/items_casings.cpp"
#include "modules/overflow_storage.cpp"
#include "modules/projectile_visibility.cpp"
#include "modules/combat_inventory.cpp"
#include "modules/binocular_optics.cpp"
#include "modules/compendium_glint_probe.cpp"
#include "modules/recon.cpp"
#include "modules/stealth_indicators.cpp"
#include "modules/custom_crafting.cpp"
#include "modules/honor_actions.cpp"
#include "modules/toxic_presentation.cpp"
#include "modules/settings_menu.cpp"
#include "modules/fortification_hud.cpp"
#include "modules/wagon_stamina.cpp"
#include "modules/radial_ammo_counts.cpp"
#include "modules/dual_wield_guard.cpp"
#include "modules/horse_needs.cpp"
#include "modules/movement.cpp"
#include "modules/human_movement.cpp"

void ScriptMain() {
#ifdef GAMEPLAYTWEAKS_CRASH_SAFE_MODE
	// Emergency containment build: keep ScriptHook's script registered but make
	// no native calls and mutate no game state. This is used only to establish
	// whether GameplayTweaks is responsible for the repeated Saint Denis
	// ERROR:FFFFFFFF failure without deleting or rolling back feature source.
	for (;;) WAIT(0);
#endif

	initIniPath();
	sprintf_s(g_crashTracePath, "%s\\GameplayTweaks.crash-trace.log",
		g_moduleDir.c_str());
	// A crash is reported AFTER the game has been restarted, so deleting this
	// file on startup destroyed the only record of the run that actually
	// crashed. Keep the previous run as .prev.log instead; that is the file to
	// read when Lexer reports a crash from a session that has already ended.
	{
		char previousTracePath[MAX_PATH] = {};
		sprintf_s(previousTracePath, "%s\\GameplayTweaks.crash-trace.prev.log",
			g_moduleDir.c_str());
		DeleteFileA(previousTracePath);
		MoveFileA(g_crashTracePath, previousTracePath);
		DeleteFileA(g_crashTracePath);
	}
	AddVectoredExceptionHandler(1, gameplayTweaksCrashTrace);
	// #126. Unified log opens before any subsystem runs, so the very first
	// subsystem event of a session is already captured in order.
	gtLogInit(g_moduleDir,
		GetPrivateProfileIntA("Logging", "Verbose", 0, g_iniPath.c_str()) != 0,
		GameplayTweaksBuild::Development ? "development" : "release");
	CRASH_TRACE_STAGE("initializeChildVulnerability");
	initializeChildVulnerability();
	CRASH_TRACE_STAGE("initializePocketwatchTime");
	initializePocketwatchTime();
	// Freeze watchdog: independent thread, so it survives a wedged script thread.
	sprintf_s(g_watchdogPath, "%s\\GameplayTweaks.watchdog.log", g_moduleDir.c_str());
	DeleteFileA(g_watchdogPath);
	CreateThread(nullptr, 0, gameplayTweaksWatchdog, nullptr, 0, nullptr);
	CRASH_TRACE_STAGE("initialization logs");
	// #126: the session record in gtLogInit already carries build and tick, so
	// the two per-feature "loaded" banners are redundant.
	CRASH_TRACE_STAGE("loadConfig");
	loadConfig();
	CRASH_TRACE_STAGE("initialize wanted system");
	loadWantedSystemSettings();
	initializeWantedSystemTrace();
	initializeAncientTomahawkReturn();
	CRASH_TRACE_STAGE("loadCollectibles");
	loadCollectibles();
	applyCollectibleFixups();
	CRASH_TRACE_STAGE("loadCampsites");
	loadCampsites();
	loadBloodstain();
	g_toxicActive = GetPrivateProfileIntA("State", "Active", 0,
		statePath("GameplayTweaks.toxicity.ini").c_str()) != 0;
	// Runtime state is deliberately not touched here. ScriptHook can start this
	// script while the frontend/loading ped is still being replaced and player
	// control is unavailable. The startup quarantine below defers every native
	// read/write that depends on the live Story Mode player until that ped has
	// remained valid and controllable for five continuous seconds.
	CRASH_TRACE_STAGE("initializeCompendiumGlintProbe");
	initializeCompendiumGlintProbe();
	configureWaterPumpCanteenApi({
		reusableCanteenOwned,
		reusableCanteenCharges,
		reusableCanteenCapacity,
		refillReusableCanteen,
		reusableCanteenStaminaCorePerDrink,
	});
	gtLog("casings", GT_INFO, std::string("registered enabled=") +
		(g_spentCasingsEnabled ? "1" : "0"));
	bool buyerDumped = false;
	DWORD lastBuyerDumpTick = 0;
	DWORD lastCheck = 0, sleepApplyAt = 0, lastTrainTick = 0, lastUnlockCheck = 0, lastBanditTick = 0, lastCigaretteTick = 0, lastVikingTick = 0, lastUniqueTick = 0, lastHunterTick = 0, lastReserveTrace = 0, greetWindowUntil = 0, lastCollectClearTick = 0, lastAmmoCapTick = 0, lastNativeCollectTick = 0, lastStaminaRateTick = 0;
	int lastClock = 0, preHealth = 100, preStamina = 100, preDeadeye = 100, sleepMinutes = 0;
	int managedCore[3] = { 100, 100, 100 };
	double coreDrainBank[3] = {}, deadeyeSleepFillBank = 0.0;
	double temperatureDrainBank[2] = {}, toxicHealthDrainBank = 0.0;
	int lastCash = 0, lastBounty = 0, lastHonor = 0, savedHunterCooldown = 0;
	bool startupRuntimeReady = false;
	bool startupWaitLogged = false;
	DWORD startupReadySince = 0;
	static constexpr DWORD kStartupReadySettleMs = 5000;
#if defined(GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE) && defined(GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE)
#error Select exactly one progressive crash-bisect mode.
#endif
#if defined(GAMEPLAYTWEAKS_CRASH_FIRST_HALF_RESUME_UNIQUES) && !defined(GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE)
#error GAMEPLAYTWEAKS_CRASH_FIRST_HALF_RESUME_UNIQUES requires the first-half progressive mode.
#endif
#if defined(GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE) || defined(GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE)
	// One-run crash localization. The ordinary unified log can order calls, but
	// ERROR:FFFFFFFF may be raised by Rockstar several frames after the native
	// which poisoned engine state. Activate one mutation group at a time and log
	// the boundary BEFORE it executes, so a delayed failure still has a bounded
	// causal window without requiring another build/relaunch per group.
	DWORD progressiveBisectStartedAt = 0;
	unsigned progressiveBisectActivated = 0;
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
	static constexpr DWORD kProgressiveBisectStepMs = 15000;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
	static constexpr DWORD kFirstHalfProgressiveStepMs = 3000;
#endif
#endif
	bool blackout = false, pendingSleep = false, coreClockInitialized = false, witnessEvent = false, suppressWitnessEvent = false, ramWasWorn = false, wasDead = false;
	// #59. IS_PLAYER_DEAD goes false long before the death sequence is over -
	// during the sky cutscene the player is already "alive" with no control.
	// Everything that must stay off for the WHOLE sequence gates on this latch,
	// not on `dead`.
	bool inDeathSequence = false;
	bool deadeyeDisabledByUs = false, deadeyeExhausted = false, staminaSuppressedByUs = false;
	// #78: one truncation flag for GameplayTweaks.reserve.log, shared by the live
	// trace and the idle heartbeat so neither can wipe the other's lines.
	int previousDeadeyeCore = -1, previousStaminaCore = -1;
	int protectedHorseStaminaCore = -1, protectedHorseHealthCore = -1;
	Ped previousMount = 0;
	std::vector<Ped> perceptionPeds;
	bool staminaExhausted = false;
	bool staminaReleasedAfterExhaustion = false;
	bool horseStaminaExhausted = false;
	bool horseSprintReleasedAfterExhaustion = false;
#ifdef GAMEPLAYTWEAKS_CRASH_INIT_ONLY
	// Diagnostic split: run the ordinary initialization path, then yield without
	// entering any per-frame feature updates. Never ship this as a release build.
	for (;;) WAIT(0);
#endif
	while (true) {
		CRASH_TRACE_STAGE("loop begin");
		// Watchdog liveness: if this stops advancing while the watchdog thread
		// keeps writing, the script thread is wedged inside the stage named on
		// the watchdog's last line.
		g_watchdogScriptTicks.fetch_add(1);
		DWORD now = GetTickCount();
		if (now - lastCheck > 2000) {
			CRASH_TRACE_STAGE("reloadIfChanged");
			lastCheck = now;
			reloadIfChanged();
		}

		Player player = PLAYER::PLAYER_ID();
		Ped ped = PLAYER::PLAYER_PED_ID();
		const bool startupPedExists = ped && ENTITY::DOES_ENTITY_EXIST(ped);
		const bool startupCandidate = startupPedExists &&
			!PED::IS_PED_DEAD_OR_DYING(ped, TRUE) &&
			PLAYER_CONTROL_ON(player) && !SCREEN_FADED_OUT();
		if (!startupRuntimeReady) {
			if (!startupCandidate) {
				startupReadySince = 0;
				if (!startupWaitLogged) {
					gtLog("core", GT_INFO,
						"startup quarantine waiting for stable controllable player ped");
					startupWaitLogged = true;
				}
			} else if (!startupReadySince) {
				startupReadySince = now;
				gtLog("core", GT_INFO,
					"startup quarantine player ready; beginning 5000 ms settle");
			} else if ((DWORD)(now - startupReadySince) >= kStartupReadySettleMs) {
				// Seed every delta-based system from the settled live save before
				// its first update. No frontend/loading value may become a baseline.
				CRASH_TRACE_STAGE("startup deferred initialization");
				initializeRecoverableUniques();
				if (g_toxicActive) {
					SET_ATTRIBUTE_POINTS(ped, 11, 100);
					START_STATUS_ICON(5);
				}
				lastClock = clockMinute();
				lastCash = CASH_BALANCE();
				lastBounty = GET_BOUNTY_VALUE(player);
				lastHonor = honorValue();
				lastBuyerDumpTick = now;
				CRASH_TRACE_STAGE("dumpVanillaShopBuyers");
				buyerDumped = dumpVanillaShopBuyers();
				startupRuntimeReady = true;
				gtLog("core", GT_INFO,
					"startup quarantine released after stable 5000 ms settle");
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
				progressiveBisectStartedAt = now;
				progressiveBisectActivated = 0;
				gtLog("crash-bisect", GT_INFO,
					"progressive baseline active through binocular group; next=plant-learning at +15000 ms");
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
	#ifdef GAMEPLAYTWEAKS_CRASH_FIRST_HALF_RESUME_UNIQUES
				progressiveBisectStartedAt = now - kFirstHalfProgressiveStepMs * 9u;
				progressiveBisectActivated = 0xFFu;
				gtLog("crash-bisect", GT_INFO,
					"first-half continuation active through recoverable-uniques; next=ancient-tomahawk now, hunter +3000 ms, sparkle +6000 ms, child +9000 ms");
	#else
				progressiveBisectStartedAt = now;
				progressiveBisectActivated = 0;
				gtLog("crash-bisect", GT_INFO,
					"first-half progressive baseline active through stealth-radial-projectile; next=movement-prone-climbing at +3000 ms");
	#endif
#endif
			}
			if (!startupRuntimeReady) {
				CRASH_TRACE_STAGE("startup quarantine WAIT");
				WAIT(0);
				continue;
			}
		}

		CRASH_TRACE_STAGE("updateShopStateProbe");
		updateShopStateProbe(ped, now);
#if defined(GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE) || defined(GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE)
		auto progressiveBisectHold = [&](DWORD releaseAfterMs, unsigned stageBit,
			const char* group, const char* waitStage) -> bool {
			if ((DWORD)(now - progressiveBisectStartedAt) < releaseAfterMs) {
				CRASH_TRACE_STAGE(waitStage);
				return true;
			}
			if ((progressiveBisectActivated & stageBit) == 0) {
				progressiveBisectActivated |= stageBit;
				char line[256] = {};
				sprintf_s(line, "activated group=%s elapsed_ms=%lu",
					group, (unsigned long)(now - progressiveBisectStartedAt));
				gtLog("crash-bisect", GT_INFO, line);
			}
			return false;
		};
#endif
		// #20: the runtime authoring switch exists only in a development build.
		// Gameplay dispatch is outside this compile-time boundary; a release build
		// must lose editors and diagnostics, never prone or another player feature.
#if GAMEPLAYTWEAKS_DEV_MODE
		if ((GetAsyncKeyState(VK_OEM_3) & 1) != 0) {
			g_runtimeDevelopmentMode = !g_runtimeDevelopmentMode;
			loadConfig();
			CASING_FEED(g_runtimeDevelopmentMode ?
				"Developer mode enabled" : "Developer mode disabled", "", 0);
			gtLog("dev-mode", GT_INFO, std::string("enabled=") +
				(g_runtimeDevelopmentMode ? "1" : "0"));
		}
#endif
		if (!buyerDumped && now - lastBuyerDumpTick > 30000) {
			lastBuyerDumpTick = now;
			buyerDumped = dumpVanillaShopBuyers();
		}
		CRASH_TRACE_STAGE("updateOverflowStorage");
		if (updateOverflowStorage(now)) {
			// The storage page pauses Rockstar's other Story threads while it owns
			// input. Do not let a later GameplayTweaks hotkey consume the same edge.
			CRASH_TRACE_STAGE("overflow storage WAIT");
			WAIT(0);
			continue;
		}
		CRASH_TRACE_STAGE("updateCustomCraftingMenu");
		const bool customCraftingOwnsInput = updateCustomCraftingMenu(now);
		CRASH_TRACE_STAGE("updateInGameSettingsMenu");
		const bool settingsMenuOwnsInput = !customCraftingOwnsInput && updateInGameSettingsMenu();
		const bool customMenuOwnsInput = customCraftingOwnsInput || settingsMenuOwnsInput;
		CRASH_TRACE_STAGE("collectibleUnlocks");
		if (now - lastUnlockCheck > 1000) { lastUnlockCheck = now; unsigned unlocked = collectibleUnlocks(); if (unlocked != g_collectibleUnlocks) { g_collectibleUnlocks = unlocked; g_collectiblesDirty = true; } }
		CRASH_TRACE_STAGE("updateNewspaperVendorMarkers");
		updateNewspaperVendorMarkers();

		const bool postOfficeMailProtected = false;
		bool mission = MISSION_ACTIVE();
		CRASH_TRACE_STAGE("updateCampfirePolicy");
		updateCampfirePolicy(mission);
		CRASH_TRACE_STAGE("updateSeriousCrimePayoff");
		updateSeriousCrimePayoff(player, ped,
			customMenuOwnsInput || postOfficeMailProtected);
		// IS_PLAYER_DEAD alone drops false mid-sequence; the ped's own dying
		// state outlasts it, so OR them.
		bool dead = PLAYER_DEAD(player) ||
			(ped && PED::IS_PED_DEAD_OR_DYING(ped, TRUE));
		CRASH_TRACE_STAGE("tickWorldCollectibleMaskRemoval");
		tickWorldCollectibleMaskRemoval(ped, now);
		bool locked = SCREEN_FADED_OUT() || !PLAYER_CONTROL_ON(player) || customMenuOwnsInput;
		// A fast-travel/teleport can move the player hundreds of metres between two
		// scheduled script frames. The shared world-ped snapshot then still contains
		// streaming-out handles from the old region while dense destination peds are
		// being created. Quarantine every full-ped scan for five seconds and force a
		// fresh snapshot after the transition instead of mutating either population.
		static bool haveStablePlayerPosition = false;
		static Vector3 lastStablePlayerPosition = {};
		if (ped && ENTITY::DOES_ENTITY_EXIST(ped) && !locked) {
			const Vector3 currentPlayerPosition = ENTITY_COORDS(ped);
			if (haveStablePlayerPosition) {
				const float dx = currentPlayerPosition.x - lastStablePlayerPosition.x;
				const float dy = currentPlayerPosition.y - lastStablePlayerPosition.y;
				const float dz = currentPlayerPosition.z - lastStablePlayerPosition.z;
				const float jumpSq = dx * dx + dy * dy + dz * dz;
				if (jumpSq > 250.0f * 250.0f) {
					quarantineSharedWorldPedSnapshot(now + 5000);
					char transition[256] = {};
					sprintf_s(transition,
						"world-transition quarantine distance=%.1f from=%.1f,%.1f,%.1f to=%.1f,%.1f,%.1f until=%lu",
						sqrtf(jumpSq), lastStablePlayerPosition.x,
						lastStablePlayerPosition.y, lastStablePlayerPosition.z,
						currentPlayerPosition.x, currentPlayerPosition.y,
						currentPlayerPosition.z,
						(unsigned long)g_sharedWorldPedSnapshotQuarantineUntil);
					gtLog("core", GT_WARN, transition);
				}
			}
			lastStablePlayerPosition = currentPlayerPosition;
			haveStablePlayerPosition = true;
		}
		const bool worldTransitionQuarantine =
			now < g_sharedWorldPedSnapshotQuarantineUntil;
		updateWantedSystemTrace(player, ped, now, locked || mission);
		updateVisibleGoldOverfill(ped, locked);
		CRASH_TRACE_STAGE("updateWagonStamina");
		updateWagonStamina(ped, locked, g_wagonCoreEnabled,
			g_wagonCoreDrain, g_wagonMinSpeed, now);
		updateHorsePersistence(player, ped, now, locked, mission);
		CRASH_TRACE_STAGE("updateAutonomousHorseNeeds");
		updateAutonomousHorseNeeds(player, ped, now, locked || mission);
		CRASH_TRACE_STAGE("updateHorseCoreClock");
		updateHorseCoreClock(player, ped, now);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_QUARTER
		// Binary-search build: stop after the first section of the early update
		// group (menus/map vendors/system traces/wagon/horse state).
		CRASH_TRACE_STAGE("bisect early-quarter WAIT");
		WAIT(0);
		continue;
#endif
		// #14: the pause-map prompt and MMB/R3 edge input are frame-scoped.
		updatePauseMapRecenter(ped);
		updateCoreXPGain(ped, !dead && !locked);
		// Latch: raised the moment he dies, lowered only once the game has
		// actually finished putting him back - alive, unfaded, control returned.
		const bool wasInDeathSequence = inDeathSequence;
		if (dead) {
			// drop any tracers still in flight, or they resume mid-air on fade-in
			if (!inDeathSequence) g_visibleProjectiles.clear();
			inDeathSequence = true;
		} else if (inDeathSequence && !locked && ped) {
			inDeathSequence = false;
		}
		// The game has finished placing him exactly now. This is the only honest
		// moment to start moving him to his campsite.
		const bool deathSequenceEnded = wasInDeathSequence && !inDeathSequence;
		if (!postOfficeMailProtected) updateHonorShopPriceModifier();
		if (!postOfficeMailProtected && ped && !inDeathSequence) updateSpentCasings(ped, now);
		if (!postOfficeMailProtected && ped && !dead) updateBottleProbe(ped);
		if (!postOfficeMailProtected && ped && !dead) updateEmptyBottles(ped, now);
		if (!postOfficeMailProtected) updateCarriedMask(now);
		if (!postOfficeMailProtected && !dead && !SCREEN_FADED_OUT()) updatePartialBounty(player, now);
		if (!postOfficeMailProtected && !dead && !SCREEN_FADED_OUT()) updateMerchantBuyOverrides(now);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_MID_A
		// Binary-search build: stop before dodge/binocular/recon/stealth/radial and
		// projectile updates.
		CRASH_TRACE_STAGE("bisect early-mid-a WAIT");
		WAIT(0);
		continue;
#endif
		CRASH_TRACE_STAGE("updateDirectionalDodgeRoll");
		if (ped && !dead) updateDirectionalDodgeRoll(player, ped, now, locked || mission);
		// Binocular hold: DE control and/or VK_F. Only hard-lock on dead/fade.
		CRASH_TRACE_STAGE("updateBinocularAccess");
		if (ped) updateBinocularAccess(player, ped, now,
			dead || SCREEN_FADED_OUT() || customMenuOwnsInput ||
			worldTransitionQuarantine);
		CRASH_TRACE_STAGE("updateImprovedBinocularAccess");
		if (ped) updateImprovedBinocularAccess(ped, now);
		CRASH_TRACE_STAGE("updateCompendiumGlintProbe");
		if (ped) updateCompendiumGlintProbe(ped,
			dead || SCREEN_FADED_OUT() || customMenuOwnsInput);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_BINOCULAR_GROUP
		// Binary-search build: include dodge/binocular/compendium updates, then
		// stop before plant/recon/stealth/radial/projectile systems.
		CRASH_TRACE_STAGE("bisect binocular-group WAIT");
		WAIT(0);
		continue;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs, 1u,
			"plant-learning", "progressive hold before plant-learning WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (ped && !dead) learnPlantModels(ped, now);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PLANT_ONLY
		// Final split between plant-model discovery and recon tagging.
		CRASH_TRACE_STAGE("bisect plant-only WAIT");
		WAIT(0);
		continue;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs * 2u, 2u,
			"recon", "progressive hold before recon WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (ped) updateReconTagging(ped, now,
			dead || SCREEN_FADED_OUT() || customMenuOwnsInput ||
			worldTransitionQuarantine);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_RECON_GROUP
		// Binary-search build: include plant learning and recon, then stop before
		// stealth indicators, radial ammo, and projectile visibility.
		CRASH_TRACE_STAGE("bisect recon-group WAIT");
		WAIT(0);
		continue;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs * 3u, 4u,
			"stealth-radial-projectile", "progressive hold before stealth-radial-projectile WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		CRASH_TRACE_STAGE("updateStealthDetectionIndicators");
		if (ped) updateStealthDetectionIndicators(ped, now,
			dead || SCREEN_FADED_OUT() || customMenuOwnsInput ||
			worldTransitionQuarantine);
		if (ped && !dead && !SCREEN_FADED_OUT() && !customMenuOwnsInput)
			updateRadialAmmoScroll(ped, now);
		// #114 isolation: #151 still performs an unaccepted clothing/loadout
		// transaction after startup. Keep it out of the shop-recovery build until
		// its own settled physical postcondition passes in-game.
		// updateDualWieldGuard(ped, now, mission);
		if (ped && !dead && !SCREEN_FADED_OUT() && !customMenuOwnsInput)
			updateRadialAmmoCounts(ped);
		// Killers keep firing at the corpse through the death cam, and every one
		// of those shots was drawing a corona aimed at his chest - that is the
		// "bullets flying in from offscreen" during the sky shot, not lost input.
		CRASH_TRACE_STAGE("updateProjectileVisibility");
		if (ped && !inDeathSequence) updateProjectileVisibility(ped, now);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_EARLY_MID
		// Binary-search build: include the safe early-quarter plus the next
		// pause-map/inventory/recon/stealth/projectile section, then yield.
		CRASH_TRACE_STAGE("bisect early-mid WAIT");
		WAIT(0);
		continue;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs * 4u, 8u,
			"first-half-remainder", "progressive hold before first-half-remainder WAIT")) {
			WAIT(0);
			continue;
		}
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs, 1u,
			"movement-prone-climbing", "first-half hold before movement-prone-climbing WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		// Prone must update before climbing: each system rejects the other's
		// active state, and removing this call silently disabled prone entirely.
		if (ped) updateProne(player, ped, now,
			dead || SCREEN_FADED_OUT() || customMenuOwnsInput, mission);
		if (ped) updateClimbing(player, ped, now, dead || SCREEN_FADED_OUT() || locked, mission);
		if (ped) updateHumanMovementRework(player, ped, now,
			dead || SCREEN_FADED_OUT() || customMenuOwnsInput ||
			customProneActive() || climbAttached() ||
			g_dodgeRollStage != DodgeRollStage::Idle);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 2u, 2u,
			"caps-camera-clamp", "first-half hold before caps-camera-clamp WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (!postOfficeMailProtected && ped && !dead && !locked &&
			!weaponWheelTransactionBusy(now) && now - lastAmmoCapTick >= 250) {
			lastAmmoCapTick = now; updateSharedAmmoCaps(player, ped); updateSharedItemCaps(ped);
		}
		// widen the third-person look-down clamp (vanilla stops ~-50deg,
		// which makes aiming the cursor at ground items miserable)
		if (g_camPitchEnabled) {
			CAM::_CLAMP_GAMEPLAY_CAM_PITCH(g_camPitchMin, g_camPitchMax);
			CAM::_SET_FIRST_PERSON_CAM_PITCH_RANGE(g_camPitchMin, g_camPitchMax);
		}
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 3u, 4u,
			"death-campsites", "first-half hold before death-campsites WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (dead && !wasDead && !mission) {
			// #244: choose the nearest row that is actually activated, but defer
			// every player-facing result until Rockstar has completed the death
			// sequence. A toast on the death screen is not a useful warning.
			g_campRespawnFallbackMessage = nullptr;
			g_campRespawnVanillaCaptured = false;
			g_campRespawnTeleported = false;
			g_campRespawnTarget = {};
			g_pendingCampRespawn = nearestActivatedCampsite(ENTITY_COORDS(ped));
			if (g_pendingCampRespawn < 0) {
				g_campRespawnFallbackMessage = g_campsites.empty()
					? "No campsites are placed; normal respawn used."
					: "No activated campsite is available; normal respawn used.";
			} else {
				const Campsite& selected = g_campsites[g_pendingCampRespawn];
				GtLogStream("campsites", GT_INFO)
					<< "respawn selected site=" << g_pendingCampRespawn
					<< " activated=" << (selected.activated ? 1 : 0)
					<< " deathDistance=" << sqrtf(campDistanceSq(ENTITY_COORDS(ped), selected.pos))
					<< "\n";
			}
			int cash = CASH_BALANCE(); int keepPercent = (std::min)(100, gamblerRank() * 10);
			int dropped = (cash * (100 - keepPercent) + 50) / 100;
			if (dropped > 0 && REMOVE_CASH(dropped)) placeBloodstain(ENTITY_COORDS(ped), dropped);
			else { removeBloodstainBlip(); removeBloodstainProp(); g_bloodstain = {}; saveBloodstain(); }
			lastCash = CASH_BALANCE();
		}
		// Alive again with a campsite owed: open the re-assert window rather than
		// teleporting once. See g_campRespawnActive.
		// Was `!dead && wasDead`, which fired at the START of the death cam - the
		// 15 s window then expired during the cutscene and the teleport was
		// abandoned before the game had even respawned him. Hence "still not
		// respawning at the nearest campsite".
		// #244: surface the no-destination case only after normal gameplay has
		// returned. Exactly one terminal message is queued per death edge.
		if (deathSequenceEnded && !mission && g_campRespawnFallbackMessage) {
			campRespawnNotify(g_campRespawnFallbackMessage);
			g_campRespawnFallbackMessage = nullptr;
		}
		if (deathSequenceEnded && !mission && g_pendingCampRespawn >= 0 &&
			(g_pendingCampRespawn >= (int)g_campsites.size() ||
			 !g_campsites[g_pendingCampRespawn].activated)) {
			campRespawnNotify("The selected campsite is no longer active; normal respawn kept.");
			g_pendingCampRespawn = -1;
		}
		if (deathSequenceEnded && !mission && g_pendingCampRespawn >= 0 &&
			g_pendingCampRespawn < (int)g_campsites.size() &&
			g_campsites[g_pendingCampRespawn].activated) {
			g_campRespawnActive = true;
			g_campRespawnTeleported = false;
			g_campRespawnVanillaCaptured = false;
			g_campRespawnTarget = {};
			g_campRespawnUntil = now + (DWORD)g_campRespawnWindowMs;
		}
		if (g_campRespawnActive) {
			if (dead) {
				// A second death owns its own selection edge; do not emit a stale
				// fallback toast from the abandoned attempt.
				g_campRespawnActive = false;
				g_campRespawnTeleported = false;
				g_campRespawnVanillaCaptured = false;
			} else if (g_pendingCampRespawn < 0 ||
				g_pendingCampRespawn >= (int)g_campsites.size() ||
				!g_campsites[g_pendingCampRespawn].activated) {
				if (ped && g_campRespawnTeleported && g_campRespawnVanillaCaptured) {
					STREAMING::REQUEST_COLLISION_AT_COORD(g_campRespawnVanillaOrigin.x,
						g_campRespawnVanillaOrigin.y, g_campRespawnVanillaOrigin.z);
					SET_COORDS_HEADING(ped, g_campRespawnVanillaOrigin,
						g_campRespawnVanillaHeading);
				}
				if (g_campRespawnTeleported) CAM::DO_SCREEN_FADE_IN(300);
				campRespawnNotify("Campsite respawn became unavailable; normal respawn kept.");
				g_campRespawnActive = false;
				g_campRespawnTeleported = false;
				g_campRespawnVanillaCaptured = false;
				g_pendingCampRespawn = -1;
			} else if (!ped) {
				// no ped this frame; keep waiting
			} else {
				Campsite& c = g_campsites[g_pendingCampRespawn];
				// The saved campsite coordinate is player_camp's campfire origin.
				// Move exactly once behind an instant fade. Reissuing this every
				// frame caused the camera to fly between streaming origins.
				STREAMING::REQUEST_COLLISION_AT_COORD(c.pos.x, c.pos.y, c.pos.z);
				Vector3 respawn = g_campRespawnTarget;
				const bool hasSafeRespawn = g_campRespawnTeleported ||
					campsiteRespawnPosition(c, &respawn);
				if (hasSafeRespawn && !g_campRespawnTeleported) {
					// Capture the exact Rockstar post-death placement immediately before
					// our one-shot move. Timeout can now restore a truthful vanilla fallback.
					g_campRespawnVanillaOrigin = ENTITY_COORDS(ped);
					g_campRespawnVanillaHeading = ENTITY_HEADING(ped);
					g_campRespawnVanillaCaptured = true;
					CAM::DO_SCREEN_FADE_OUT(0);
					STREAMING::REQUEST_COLLISION_AT_COORD(respawn.x, respawn.y, respawn.z);
					SET_COORDS_HEADING(ped, respawn, c.heading);
					g_campRespawnTarget = respawn;
					g_campRespawnTeleported = true;
				}
				const bool placed =
					g_campRespawnTeleported && hasSafeRespawn &&
					campDistanceSq(ENTITY_COORDS(ped), respawn) < 9.0f &&
					ENTITY::HAS_COLLISION_LOADED_AROUND_ENTITY(ped) &&
					PLAYER_CONTROL_ON(player);
				const bool timedOut = now >= g_campRespawnUntil;
				// A far-away campsite usually has no collision/navmesh on the first
				// post-respawn frame. Keep requesting and retrying for the configured
				// window; treating that first false probe as a permanent failure made
				// an activated campsite fall straight through to vanilla respawn.
				if (placed || timedOut) {
					if (placed) {
						Ped horse = GET_OWNED_MOUNT(player);
						if (horse && !invoke<BOOL>(0x7D5B1F88E7504BBA, horse)) {
							const float radians = (c.heading + 90.0f) * 0.0174532925f;
							Vector3 hp = { c.pos.x + std::cos(radians) * 4.0f,
								c.pos.y + std::sin(radians) * 4.0f, c.pos.z };
							SET_COORDS_HEADING(horse, hp, c.heading);
						}
						materializeCampsite(g_pendingCampRespawn);
						campMessage("You respawned at your nearest activated campsite.");
					} else {
						// If we moved before the final collision/control readback became
						// acceptable, put Arthur back exactly where Rockstar respawned him.
						if (g_campRespawnTeleported && g_campRespawnVanillaCaptured) {
							STREAMING::REQUEST_COLLISION_AT_COORD(g_campRespawnVanillaOrigin.x,
								g_campRespawnVanillaOrigin.y, g_campRespawnVanillaOrigin.z);
							SET_COORDS_HEADING(ped, g_campRespawnVanillaOrigin,
								g_campRespawnVanillaHeading);
						}
						campRespawnNotify("No safe campsite respawn point was available; normal respawn kept.");
					}
					if (g_campRespawnTeleported) CAM::DO_SCREEN_FADE_IN(300);
					g_campRespawnActive = false;
					g_campRespawnTeleported = false;
					g_campRespawnVanillaCaptured = false;
					g_campRespawnFallbackMessage = nullptr;
					g_pendingCampRespawn = -1;
				}
			}
		}
		wasDead = dead;
		CRASH_TRACE_STAGE("updateCampsites");
		updateCampsites(player, ped, now, dead, mission);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 4u, 8u,
			"bloodstain-holster-lantern", "first-half hold before bloodstain-holster-lantern WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		CRASH_TRACE_STAGE("updateBloodstain");
		if (ped && !dead) updateBloodstain(ped);
		CRASH_TRACE_STAGE("updateAlwaysHolster");
		if (ped && !dead) updateAlwaysHolster(ped, now, mission);
		if (ped) updateBeltLantern(ped, mission);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 5u, 16u,
			"gameplay-horse-camera-feed", "first-half hold before gameplay-horse-camera-feed WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		CRASH_TRACE_STAGE("updateGameplayCameraEditor");
		if (ped && !dead) updateGameplayCameraEditor(ped, now, mission);
		if (ped && !dead) updateHorseCameraCentering(ped);
		updatePocketwatchTime(ped, now, locked);
		Thermometer::update(ped, now,
			dead || locked || postOfficeMailProtected);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 6u, 32u,
			"cards-alcohol-toxic-honor", "first-half hold before cards-alcohol-toxic-honor WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (CONTROL_JUST_PRESSED(0, joaat("INPUT_INTERACT_POS"))) greetWindowUntil = now + 5000;
		if (!postOfficeMailProtected && ped && !dead)
			updatePremiumCigaretteCards(ped, now);
		if (!postOfficeMailProtected && ped && now - lastCigaretteTick >= 100) {
			lastCigaretteTick = now;
			DuplicateCigaretteCards::update(g_duplicateCardsEnabled);
		}
		if (!postOfficeMailProtected && ped && !dead) updateAlcohol(ped, now);
		if (!postOfficeMailProtected && ped && !dead) updateToxicInteraction(ped);
		updateToxicPresentation((ped && !postOfficeMailProtected && !dead) ? ped : 0, now);
		updateToxicHealthDrain(player, ped, now,
			g_toxicityEnabled && g_toxicActive && ped && !dead,
			toxicHealthDrainBank);
		updateHonorActions(now);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 7u, 64u,
			"canteen-water", "first-half hold before canteen-water WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		updateReusableCanteen(ped, now,
			dead || locked || postOfficeMailProtected, &managedCore[1]);
		CRASH_TRACE_STAGE("updateWaterPumps");
		updateWaterPumps(player, ped, now,
			dead || locked || postOfficeMailProtected, mission,
			&managedCore[1]);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 8u, 128u,
			"recoverable-uniques", "first-half hold before recoverable-uniques WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (!postOfficeMailProtected && ped && !dead && now - lastUniqueTick >= 1000) { lastUniqueTick = now; updateRecoverableUniques(ped, now, mission); }
		updateRecoverableUniqueLocker(ped, now,
			dead || locked || postOfficeMailProtected, mission);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 9u, 256u,
			"ancient-tomahawk", "first-half hold before ancient-tomahawk WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (!postOfficeMailProtected && ped && !dead) updateAncientTomahawkReturn(ped, now);
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 10u, 512u,
			"hunter-hatchet", "first-half hold before hunter-hatchet WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (!postOfficeMailProtected && ped && !dead && now - lastHunterTick >= 50) { lastHunterTick = now; updateHunterHatchet(ped, mission); }
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 11u, 1024u,
			"owned-gear-sparkles", "first-half hold before owned-gear-sparkles WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		// #69 weapon sparkle suppression is intentionally absent from the live
		// pipeline. Both pickup-pool and guarded object-pool scanners independently
		// produced Rockstar's delayed ERROR:FFFFFFFF before child vulnerability was
		// released. Do not silently restore either failed runtime path.
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		if (progressiveBisectHold(kFirstHalfProgressiveStepMs * 12u, 2048u,
			"child-vulnerability", "first-half hold before child-vulnerability WAIT")) {
			WAIT(0);
			continue;
		}
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF_PROGRESSIVE
		CRASH_TRACE_STAGE("first-half progressive complete WAIT");
		WAIT(0);
		continue;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_FIRST_HALF
		// Binary-search build: exercise initialization and the early update group,
		// then yield before core/economy/combat/movement and the remaining group.
		CRASH_TRACE_STAGE("bisect first-half WAIT");
		WAIT(0);
		continue;
#endif
#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs * 5u, 16u,
			"core-clock-minimap", "progressive hold before core-clock-minimap WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		int currentClock = clockMinute();
		int jump = forwardMinutes(lastClock, currentClock);
		// #78. Read Dead Eye's live state BEFORE the CoreClock block runs.
		// THIS ORDERING IS THE BUG THAT KEPT #78 ALIVE. CoreClock's symmetric
		// one-point hold below ("else if (live != managedCore[core]) SET_CORE(...)")
		// restores a single-point core drop in the SAME frame the engine spends it.
		// The #78 detector further down then re-read the core with GET_CORE and saw
		// the already-restored value, so `live < previous` was never once true, the
		// latch never rose, and Dead Eye stayed usable with an empty ring - exactly
		// "my bar drains, hits 0, and i'm still in deadeye".
		// Sampling here, ahead of any of our own writes, is the only place the
		// reserve tick is still visible.
		const bool deadeyeActiveNow = ped && invoke<BOOL>(0xB16223CB7DA965F0, player) != 0;
		const int  deadeyeCorePreClock = ped ? GET_CORE(ped, 2) : -1;
		// Set by the CoreClock loop when it refuses a Dead Eye core spend, and by
		// the #78 block when it observes one directly. Either is proof the engine
		// crossed the outer ring into the reserve.
		bool deadeyeReserveTick = false;
		CRASH_TRACE_STAGE("coreClock");
		if (ped && g_coreClockEnabled) {
			if (!coreClockInitialized) {
				for (int core = 0; core < 3; ++core) managedCore[core] = GET_CORE(ped, core);
				coreClockInitialized = true;
			}
			if (!blackout && !pendingSleep) {
				// Accept refills and substantial scripted/item penalties. Ignore one-point
				// native background ticks because CoreClock replaces that metabolism.
				//
				// #1 SWIMMING HOLE: the "substantial drop = a real scripted penalty"
				// heuristic is what let the Stamina core act as a reserve in water.
				// Walking around spends the core one point at a time and was caught
				// here; swimming spends it fast enough that a single sample sees a
				// multi-point drop, which this rule then ACCEPTED as legitimate.
				// So: while the matching outer bar is at its floor, a falling core is
				// a reserve spend by definition, whatever its size, and is refused.
				// (Trade-off: a genuine scripted core penalty landing in the same
				// instant as an empty bar is also refused. That is the correct
				// priority for this item — cores are never a reserve tank.)
				const bool staminaBarFloor = GET_STAMINA_BAR(player) <= g_reserveBarFloor;
				// #78. `deadeyeBarFloor` USED TO BE HERE as
				//   GET_DEADEYE_BAR(player) <= g_reserveBarFloor
				// comparing _GET_PLAYER_DEAD_EYE - a RAW ABSOLUTE amount measured at
				// 133.56 at rest and recorded bottoming at ~25-28 with the ring already
				// empty - against a PERCENT threshold of 10. It could never be true, so
				// core 2 had no reserve protection at all. Deleted, not retuned: there is
				// no percent to tune it to.
				// The scale-free replacement: while Dead Eye is ACTIVE, a falling Dead Eye
				// core IS a reserve spend, by definition and at any bar level. This is the
				// same rule the Stamina core already uses for swimming, and it needs no
				// knowledge of where the ring ends.
				for (int core = 0; core < 3; ++core) {
					int live = GET_CORE(ped, core);
					// #1 "STILL ACTS AS A RESERVE WHEN SWIMMING".
					// The floor rule only refuses a core spend once the outer bar has
					// already reached its last 10%. Swimming drains the bar fast enough
					// that a single sample can see a MULTI-POINT core drop while the bar
					// is still above that floor - and a multi-point drop is deliberately
					// treated as a real scripted penalty and accepted. That is the hole
					// the swim drain fell through, and it is why this specific case
					// survived every previous fix.
					// While he is actually in the water, the Stamina core is protected at
					// ANY bar level. Nothing else spends a core that fast, so this costs
					// nothing on land.
					const bool swimming = IS_PED_SWIMMING(ped);
					const bool onFloor = g_noReserveCores && !locked &&
						((core == 1 && (staminaBarFloor || swimming)) ||
						 (core == 2 && deadeyeActiveNow));
					if (live < managedCore[core] && onFloor) {
						SET_CORE(ped, core, managedCore[core]);
						// Tell the #78 latch that this frame's spend was refused here.
						// Without this the restore below hides the event from it.
						if (core == 2) deadeyeReserveTick = true;
					}
						// SYMMETRIC: native one-point ticks are refused in BOTH directions.
						// Refusing only the drops - which is all this did - left vanilla's
						// own core REGENERATION accepted unconditionally, so every CoreClock
						// drain tick was immediately undone by a +1 regen tick and then
						// re-applied. GameplayTweaks.reserve.log shows the result: the
						// Stamina core oscillating 61-60-61-60 roughly three times a second
						// for a whole session, with the outer bar at 90% and nothing being
						// spent. Each transition makes the game flash its core-state screen
						// treatment - the intermittent haze that came and went "no matter
						// what". A real refill (food, tonic, sleep) moves more than one point
						// and is still accepted, exactly as a real scripted penalty is.
						else if (live > managedCore[core] + 1 || live < managedCore[core] - 1) managedCore[core] = live;
						else if (live != managedCore[core]) SET_CORE(ped, core, managedCore[core]);
				}
			}
			if (locked && !blackout) {
				blackout = true;
				preHealth = managedCore[0]; preStamina = managedCore[1]; preDeadeye = managedCore[2];
			}
			bool sleepJump = blackout && jump <= 1200 && (pendingSleep || jump >= 30);
			if (sleepJump) { sleepMinutes += jump; pendingSleep = true; }
			else if (!pendingSleep && jump > 0 && jump <= 1200) {
				drainCoreByMinutes(ped, 0, jump, g_healthDrainHours, coreDrainBank[0], managedCore[0]);
				drainCoreByMinutes(ped, 1, jump, g_staminaDrainHours, coreDrainBank[1], managedCore[1]);
				drainCoreByMinutes(ped, 2, jump, g_deadeyeDrainHours, coreDrainBank[2], managedCore[2]);
				if (g_temperatureEnabled) {
					// Attribute 12 is Story Mode's clothing-adjusted exposure state:
					// 0 cold, 50 comfortable, 100 hot.
					int exposure = GET_ATTRIBUTE_POINTS(ped, 12);
					if (exposure >= 100 && g_heatDrainMultiplier > 0.0f)
						drainCoreByMinutes(ped, 1, jump, g_temperatureBaseDrainHours / g_heatDrainMultiplier,
							temperatureDrainBank[0], managedCore[1]);
					else if (exposure <= 0 && g_coldDrainMultiplier > 0.0f)
						drainCoreByMinutes(ped, 0, jump, g_temperatureBaseDrainHours / g_coldDrainMultiplier,
							temperatureDrainBank[1], managedCore[0]);
				}
			}
			if (!locked && blackout) { blackout = false; if (pendingSleep) sleepApplyAt = now + 750; }
			if (pendingSleep && sleepApplyAt && now >= sleepApplyAt) {
				managedCore[0] = preHealth; managedCore[1] = preStamina; managedCore[2] = preDeadeye;
				drainCoreByMinutes(ped, 0, sleepMinutes, g_healthDrainHours, coreDrainBank[0], managedCore[0]);
				drainCoreByMinutes(ped, 1, sleepMinutes, g_staminaDrainHours, coreDrainBank[1], managedCore[1]);
				fillCoreByMinutes(ped, 2, sleepMinutes, g_deadeyeSleepRefillHours, deadeyeSleepFillBank, managedCore[2]);
				pendingSleep = false; sleepApplyAt = 0; sleepMinutes = 0;
			}
		}
		else coreClockInitialized = false;
		lastClock = currentClock;

		updateCustomMinimapZoom(now);

#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs * 6u, 32u,
			"deadeye-stamina-horse-reserve", "progressive hold before deadeye-stamina-horse-reserve WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (ped) {
			CRASH_TRACE_STAGE("deadeyeReserve");
			// Compare against the PRE-CORECLOCK sample taken above, not a fresh
			// GET_CORE. A fresh read here is post-restore and can no longer show the
			// spend; that read is what made this branch dead for every prior build.
			int liveDeadeyeCore = deadeyeCorePreClock >= 0 ? deadeyeCorePreClock : GET_CORE(ped, 2);
			bool deadeyeActive = deadeyeActiveNow;
			CRASH_TRACE_STAGE("deadeyeConsumption");
			updateDeadeyeConsumption(player, now, deadeyeActive);
			if (g_noReserveCores && !locked && deadeyeActive && previousDeadeyeCore >= 0 && liveDeadeyeCore < previousDeadeyeCore) {
				// The cached special-ability amount does not reliably expose the outer-ring
				// boundary. A falling core while Dead Eye is active proves the engine crossed
				// it; undo that first reserve tick and end Dead Eye immediately.
				SET_CORE(ped, 2, previousDeadeyeCore);
				managedCore[2] = previousDeadeyeCore;
				deadeyeReserveTick = true;
				liveDeadeyeCore = previousDeadeyeCore;
			}
			previousDeadeyeCore = liveDeadeyeCore;
			const float staminaBar = GET_STAMINA_BAR(player);
			// GitHub #48: vanilla lets an exhausted swimmer tread water while Health
			// drains away. Zero OUTER Stamina is the drowning boundary here: kill on
			// the first frame at the floor, without spending the Stamina core or
			// waiting through vanilla's slow Health-loss phase. IS_PED_SWIMMING keeps
			// shallow-water wading and ordinary on-foot exhaustion out of this path.
			if (!dead && !locked && IS_PED_SWIMMING(ped) && staminaBar <= 0.01f)
				SET_ENTITY_HEALTH(ped, 0);
			const bool sprintHeld = PAD::IS_CONTROL_PRESSED(0, 0x8FFC75D6) ||
				PAD::IS_DISABLED_CONTROL_PRESSED(0, 0x8FFC75D6);
			if (!g_noReserveCores || locked) {
				staminaExhausted = false;
				staminaReleasedAfterExhaustion = false;
			} else if (!staminaExhausted && staminaBar <= g_reserveSprintCutBar) {
				staminaExhausted = true;
				staminaReleasedAfterExhaustion = false;
			} else if (staminaExhausted) {
				if (!sprintHeld) staminaReleasedAfterExhaustion = true;
				if (staminaReleasedAfterExhaustion &&
					staminaBar >= g_reserveSprintCutBar + 1.5f)
					staminaExhausted = false;
			}
			// PIN THE CORE BEFORE IT CAN BE SPENT, NOT AFTER. This pin used to live
			// inside the staminaEmpty branch below and only reacted to a decrement it
			// had already observed, so there was always at least one RENDERED frame
			// where the core visibly dropped and then snapped back - the "really
			// obvious dip into your core" report. Hold it from the moment the bar
			// gets low, well before the cut threshold is reached.
			if (g_noReserveCores && !locked && ped &&
				(staminaExhausted || staminaBar <= g_reserveSprintCutBar * 2.0f)) {
				const int liveStaminaCoreEarly = GET_CORE(ped, 1);
				if (previousStaminaCore >= 0 && liveStaminaCoreEarly < previousStaminaCore) {
					SET_CORE(ped, 1, previousStaminaCore);
					managedCore[1] = previousStaminaCore;
				}
			}
			const bool staminaEmpty = g_noReserveCores && !locked && staminaExhausted;
			if (g_noReserveCores && !locked) {
				// Health has no grace reserve: once the outer bar is empty, death is immediate.
				if (GET_HEALTH_BAR(player) <= 0.01f)
					SET_ENTITY_HEALTH(ped, 0);

				// Do not let continued sprinting spill exertion into the Stamina core.
				if (staminaEmpty) {
					DISABLE_CONTROL(0, 0x8FFC75D6); // INPUT_SPRINT
					DISABLE_CONTROL(2, 0x8FFC75D6);
					DISABLE_CONTROL(0, 0xD9D0E1C0); // INPUT_JUMP
					DISABLE_CONTROL(0, 0xB2F377E8); // INPUT_MELEE_ATTACK
					DISABLE_CONTROL(0, 0x2277FAE9); // INPUT_MELEE_GRAPPLE
					DISABLE_CONTROL(0, 0x018C47CF); // INPUT_MELEE_GRAPPLE_CHOKE
					Hash weapon = GET_CURRENT_WEAPON(ped);
					if (weapon == joaat("WEAPON_BOW") || weapon == joaat("WEAPON_BOW_IMPROVED") ||
						weapon == joaat("WEAPON_LASSO") || weapon == joaat("WEAPON_LASSO_REINFORCED")) {
						DISABLE_CONTROL(0, 0xF84FA74F); // INPUT_AIM
						DISABLE_CONTROL(0, 0x07CE1E61); // INPUT_ATTACK
					}
					int liveStaminaCore = GET_CORE(ped, 1);
					if (previousStaminaCore >= 0 && liveStaminaCore < previousStaminaCore) {
						SET_CORE(ped, 1, previousStaminaCore);
						managedCore[1] = previousStaminaCore;
					}
				}
				previousStaminaCore = GET_CORE(ped, 1);

				// #78. Dead Eye ends at an empty outer ring instead of consuming its
				// core. Keep an exhaustion latch: disabling Dead Eye can make the raw
				// amount bounce upward, and the old stateless test then re-enabled it.
				// Release only after Dead Eye is inactive AND the normalized meter has
				// genuinely refilled above the cutoff (with hysteresis). An attempted
				// zero-bar activation is active, so it can never release its own latch.
				CRASH_TRACE_STAGE("deadeyeExhaustionLatch");
				const float deadeyeMeter = GET_DEADEYE_METER_LEVEL(player);
				// THE TRIGGER IS THE REFUSED RESERVE TICK, NOTHING ELSE.
				// The two value tests that used to sit here are both gone:
				//   deadeyeBar <= 0.01f  - _GET_PLAYER_DEAD_EYE is a raw absolute
				//     amount (133.56 at rest) that the worklog records bottoming at
				//     ~25-28 with the ring already empty. Unreachable.
				//   deadeyeMeter <= 1%   - the FALSE-form meter's ring-vs-core meaning
				//     is not established by any call site in script_rel; it may simply
				//     be tracking the core, in which case it is unreachable too.
				// `deadeyeReserveTick` needs no scale and no threshold: the engine took
				// a point out of the Dead Eye core while Dead Eye was running, which is
				// the definition of the ring having run out. That event is caught in the
				// only frame it is visible (before CoreClock restores it).
				if (!deadeyeExhausted && deadeyeReserveTick)
					deadeyeExhausted = true;
				const float deadeyeRelease = (std::min)(1.0f, g_deadeyeEmptyFrac + 0.02f);
				if (deadeyeExhausted && !deadeyeActive && deadeyeMeter >= deadeyeRelease) {
					deadeyeExhausted = false;
					SET_DEADEYE_DISABLED(player, false);
					deadeyeDisabledByUs = false;
				}
				if (deadeyeExhausted) {
					// Do not depend on DEADEYE_ENABLED: it reports the unlock state, not
					// whether reserve-backed activation is currently possible.
					//
					// #129 / IDEMPOTENCE. This used to also call 0x1D77B47AFA584E90 with
					// one argument on a three-argument native, EVERY FRAME the latch held,
					// with the ability active and possibly mid-aim. That is removed. The
					// two natives left here are Rockstar's own end-Dead-Eye pair
					// (abigail2_1.c:75189-75191), and SET_DEADEYE_DISABLED is now issued
					// only on the EDGE - re-asserting an already-true disable every frame
					// was pure native spam with no effect on the result.
					if (!deadeyeDisabledByUs) SET_DEADEYE_DISABLED(player, true);
					deadeyeDisabledByUs = true;
					// Do not disable INPUT_SPECIAL_ABILITY or its siblings. MMB uses that
					// shared action for Eagle Eye outside aiming, so per-frame control
					// suppression broke Eagle Eye for the entire exhaustion latch. The
					// Dead Eye-specific native owns activation blocking while leaving the
					// contextual Eagle Eye action available.
				} else if (deadeyeDisabledByUs) {
					SET_DEADEYE_DISABLED(player, false);
					deadeyeDisabledByUs = false;
				}
			} else if (deadeyeDisabledByUs) {
				SET_DEADEYE_DISABLED(player, false);
				deadeyeDisabledByUs = false;
				deadeyeExhausted = false;
			}
			const float staminaDt = lastStaminaRateTick
				? (std::min)(0.10f, (now - lastStaminaRateTick) / 1000.0f) : 0.0f;
			lastStaminaRateTick = now;
			if (g_humanStamEnabled) {
				// Neutralize the multiplier layer; the signed mode rate below owns the
				// final result and cancels any simultaneous native drain or recovery.
				SET_PLAYER_STAMINA_RECHARGE(player, 1.0f);
				SET_PLAYER_SPRINT_DEPLETION(player, 1.0f);
				SET_PED_STAMINA_DEPLETION(ped, 1.0f);
				SET_PED_STAMINA_RECHARGE(ped, 1.0f);
				// RIDING IS THE HORSE'S EXERTION, NOT ARTHUR'S. While mounted the
				// player ped inherits the mount's entity speed and locomotion flags,
				// so playerMovementStaminaRate read a galloping horse as Arthur
				// sprinting and drove the SPRINT drain onto HIS bar. That is why an
				// exhausted horse core started draining player stamina: hold sprint on
				// a spent horse and this one call was pulling both meters down. Only
				// run the player controller when he moves under his own power.
				const bool ownPower = g_climbState == ClimbState::Grounded &&
					!PED::IS_PED_ON_MOUNT(ped) &&
					!PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE);
				if (ownPower)
					g_playerStaminaRate.tick(ped, playerMovementStaminaRate(ped), staminaDt);
				else g_playerStaminaRate.reset();
				staminaSuppressedByUs = false;
			} else {
				g_playerStaminaRate.reset();
				if (staminaSuppressedByUs) {
				SET_PLAYER_SPRINT_DEPLETION(player, 1.0f);
				SET_PED_STAMINA_DEPLETION(ped, 1.0f);
				staminaSuppressedByUs = false;
				}
			}
			{
				Ped mount = GET_MOUNT(ped);
				if (mount) {
					if (mount != previousMount) {
						previousMount = mount;
						protectedHorseStaminaCore = GET_CORE(mount, 1);
						protectedHorseHealthCore = GET_CORE(mount, 0);
						horseStaminaExhausted = false; horseSprintReleasedAfterExhaustion = false;
					}
					float mountMax = GET_PED_MAX_STAMINA(mount);
					float mountStamina = GET_PED_STAMINA(mount);
					int liveHorseStaminaCore = GET_CORE(mount, 1);
					const int mountHealth = ENTITY::GET_ENTITY_HEALTH(mount);
					const int mountMaxHealth = ENTITY::GET_ENTITY_MAX_HEALTH(mount, TRUE);
					const bool horseSprintHeld = PAD::IS_CONTROL_PRESSED(0, 0x5AA007D7) ||
						PAD::IS_DISABLED_CONTROL_PRESSED(0, 0x5AA007D7);
					// The horse meter has a non-zero visual floor. Detect the first core
					// spend near that floor, undo it immediately, and use that exact
					// boundary as exhaustion instead of waiting for 0.5%.
					//
					// #1 HORSE HOLE: this used to require horseSprintHeld, so a core
					// spent at a canter, at a gallop under momentum, while swimming or
					// on a jump was never seen — and the baseline below then latched the
					// lowered core as legitimate. The gait does not matter; a falling
					// core under a floored bar is a reserve spend.
					// #1 HORSE SWIMMING HOLE: the same hole the player's Stamina core
					// fell through, never closed on this side. The pin below only fires
					// under a floored bar; above it the baseline is refreshed instead.
					// Swimming spends the core faster than one sample while the bar is
					// still well above 16%, so the drop was adopted as the new protected
					// value and the core drained as a reserve exactly as before. While
					// the mount is in water its Stamina core is protected at ANY bar
					// level, matching the player rule.
					const bool mountSwimming = IS_PED_SWIMMING(mount);
					const bool mountBarFloored = mountMax > 0.0f && mountStamina <= 0.16f * mountMax;
					// #1: reaching the horse meter's visual floor IS exhaustion. The old
					// code merely watched this band for a later core drop, then tried to
					// undo that drop. The completed probe caught the resulting one-second
					// hole: 21.8/140 with core 30 became 7.8/100 with core 20 before the
					// exhausted latch was raised. Latch at the boundary so neither
					// Rockstar's drain nor our net-rate controller can reach the core.
					if (g_noReserveCores && !locked && mountBarFloored && !horseStaminaExhausted) {
						horseStaminaExhausted = true;
						horseSprintReleasedAfterExhaustion = false;
					}
					const bool reserveTick = g_noReserveCores && !locked &&
						(mountBarFloored || mountSwimming) &&
						protectedHorseStaminaCore >= 0 && liveHorseStaminaCore < protectedHorseStaminaCore;
					if (reserveTick) {
						SET_HORSE_CORE(mount, 1, protectedHorseStaminaCore);
						liveHorseStaminaCore = protectedHorseStaminaCore;
						// Only a FLOORED bar means exhaustion. A protected swim tick with
						// a healthy bar must not disable sprint and jump — that would be a
						// new bug traded for the old one.
						if (mountBarFloored) {
							horseStaminaExhausted = true;
							horseSprintReleasedAfterExhaustion = false;
						}
					}
					if (!g_noReserveCores || locked || mountMax <= 0.0f) {
						horseStaminaExhausted = false; horseSprintReleasedAfterExhaustion = false;
					} else if (!horseStaminaExhausted && mountStamina <= 0.01f * mountMax) {
						horseStaminaExhausted = true; horseSprintReleasedAfterExhaustion = false;
					} else if (horseStaminaExhausted) {
						if (!horseSprintHeld) horseSprintReleasedAfterExhaustion = true;
						// The latch now begins at the 16% visual floor, not at 1%, so the
						// former 2% release threshold would clear it immediately whenever
						// sprint was already released. Require visible recovery above the
						// floor, with a small hysteresis band to prevent edge oscillation.
						if (horseSprintReleasedAfterExhaustion && mountStamina >= 0.18f * mountMax)
							horseStaminaExhausted = false;
					}
					bool mountStaminaEmpty = g_noReserveCores && !locked && horseStaminaExhausted;
					if (mountStaminaEmpty) {
						DISABLE_CONTROL(0, 0x5AA007D7); // INPUT_HORSE_SPRINT
						DISABLE_CONTROL(0, 0xE4D2CE1D); // INPUT_HORSE_JUMP
						int liveCore = GET_CORE(mount, 1);
						// Pin the pre-exhaustion value every frame. Restoring only the
						// first spent tick allowed Rockstar to spend it again next frame.
						if (protectedHorseStaminaCore >= 0 && liveCore < protectedHorseStaminaCore)
							SET_HORSE_CORE(mount, 1, protectedHorseStaminaCore);
					} else if (!(g_noReserveCores && !locked && (mountBarFloored || mountSwimming))) {
						// Only re-baseline while the bar is comfortably ABOVE the floor.
						// Refreshing it unconditionally (the old behaviour) meant every
						// core point the engine spent near empty was immediately adopted
						// as the new protected value — the pin could never fire, which is
						// exactly why the horse core still drained as a reserve.
						protectedHorseStaminaCore = GET_CORE(mount, 1);
					}
					if (g_noReserveCores && !locked) {
						// RAGE ped Health normally reserves the bottom 100 native points;
						// the visible outer bar is empty at that boundary. A horse whose
						// max was already corrupted down to 100 has no such range, so use
						// zero for that legacy case rather than killing it while "full".
						const int horseHealthFloor = mountMaxHealth > 100 ? 100 : 0;
						if (mountHealth <= horseHealthFloor) {
							const int liveCore = GET_CORE(mount, 0);
							if (protectedHorseHealthCore >= 0 && liveCore < protectedHorseHealthCore)
								SET_HORSE_CORE(mount, 0, protectedHorseHealthCore);
							// Empty outer Health kills. Merely restoring the first core tick
							// left the horse alive to spend it again as a reserve next frame.
							SET_ENTITY_HEALTH(mount, 0);
						} else {
							protectedHorseHealthCore = GET_CORE(mount, 0);
						}
					}
					if (g_horseStamEnabled) {
						// Once the visual bar is empty, suppress the engine drain and do not
						// let our own negative rate push through the floor. Positive recovery
						// remains active, so releasing sprint still restores the outer bar.
						SET_PED_STAMINA_DEPLETION(mount, horseStaminaExhausted ? 0.0f : 1.0f);
						SET_PED_STAMINA_RECHARGE(mount, 1.0f);
						float rate = horseMovementStaminaRate(mount);
						if (horseStaminaExhausted && rate < 0.0f) rate = 0.0f;
						if (rate > 0.0f && wearing("CLOTHING_ITEM_SKULLMASK_MR1_002_1"))
							rate *= g_catHorseRegenMult;
						g_horseStaminaRate.tick(mount, rate, staminaDt);
					} else g_horseStaminaRate.reset();
				}
				else {
					previousMount = 0;
					g_horseStaminaRate.reset();
					protectedHorseStaminaCore = -1;
					protectedHorseHealthCore = -1;
					horseStaminaExhausted = false; horseSprintReleasedAfterExhaustion = false;
				}
			}
			// #11: live mode readout. You asked how you actually enter each mode
			// and what the difference is — this shows the mode you are in right
			// now, the rate it is applying, and your speed, for you AND the horse.
			// Turn it on with [HumanStamina] ShowMode=1.
			if (g_staminaShowMode && ped && !locked) {
				char line[192];
				sprintf_s(line, "%s  %+.1f/s   bar %.0f%%  core %d   (%.1f m/s)",
					playerMovementStaminaMode(ped), playerMovementStaminaRate(ped),
					GET_STAMINA_BAR(player), GET_CORE(ped, 1), ENTITY_SPEED(ped));
				drawReconText(line, 0.5f, 0.06f);
				Ped showMount = GET_MOUNT(ped);
				if (showMount) {
					const float mountMax = GET_PED_MAX_STAMINA(showMount);
					sprintf_s(line, "Horse: %s  %+.1f/s   bar %.0f%%  core %d   (%.1f m/s)",
						horseMovementStaminaMode(showMount),
						horseMovementStaminaRate(showMount),
						mountMax > 0.0f ? 100.0f * GET_PED_STAMINA(showMount) / mountMax : 0.0f,
						GET_CORE(showMount, 1), ENTITY_SPEED(showMount));
					drawReconText(line, 0.5f, 0.10f);
				}
			}
			if (now - lastReserveTrace >= 1000) {
				CRASH_TRACE_STAGE("reserveTrace");
				lastReserveTrace = now;
				// Append-only with no truncation grew this past 5.8 MB / 41k lines
				// of accumulated cross-session history. Restart it once per launch
				// so it describes THIS session and cannot grow without bound.
				// The flag is declared at function scope so the idle heartbeat below
				// shares it; see the note there.
				// #126: the unified log owns truncation now (once per launch, in
				// gtLogInit), so this feature no longer manages its own file.
				std::ostringstream trace;
				trace << "stamina=" << GET_STAMINA_BAR(player) << " core=" << GET_CORE(ped, 1)
					<< " exhausted=" << (staminaExhausted ? 1 : 0)
					<< " sprinting=" << (IS_PED_SPRINTING(ped) ? 1 : 0)
					<< " running=" << (IS_PED_RUNNING(ped) ? 1 : 0)
					<< " blend=" << GET_DESIRED_MOVE_BLEND(ped)
					<< " speed=" << ENTITY_SPEED(ped)
					// #78 DIAGNOSTICS. `deadeyeRaw` is _GET_PLAYER_DEAD_EYE - absolute,
					// NOT a percent; it is here to be read, never to be compared.
					// meterF/meterT are the two parameter forms of
					// _GET_PLAYER_DEAD_EYE_METER_LEVEL, logged side by side so one play
					// session settles which (if either) tracks the OUTER RING. Until that
					// is settled neither may gate behaviour.
					// `dexh`/`dtick` are the latch and its trigger. A line with
					// active=1 dexh=0 dtick=0 while the ring reads empty is the exact
					// failure Lexer reports, and now proves the trigger did not fire
					// rather than leaving a silent log.
					<< " deadeyeRaw=" << GET_DEADEYE_RAW(player) << " core=" << GET_CORE(ped, 2)
					<< " meterF=" << GET_DEADEYE_METER_LEVEL(player)
					<< " meterT=" << GET_DEADEYE_METER_LEVEL_ALT(player)
					<< " active=" << (deadeyeActiveNow ? 1 : 0)
					<< " dexh=" << (deadeyeExhausted ? 1 : 0)
					<< " dtick=" << (deadeyeReserveTick ? 1 : 0)
					<< " disabled=" << (deadeyeDisabledByUs ? 1 : 0)
					<< " noReserve=" << (g_noReserveCores ? 1 : 0);
				Ped traceMount = GET_MOUNT(ped);
				if (traceMount) trace << " horseStamina=" << GET_PED_STAMINA(traceMount)
					<< "/" << GET_PED_MAX_STAMINA(traceMount)
					<< " horseStamCore=" << GET_CORE(traceMount, 1)
					<< " protectedStamCore=" << protectedHorseStaminaCore
					// GITHUB #78 COMMENT 2026-08-06T18:54Z, the horse-gait report.
					// horseSpeed is the whole story: horseMovementStaminaRate()
					// (modules/movement.cpp:113-128) is banded on GROUND SPEED, and the
					// only positive bands are below 5.0 m/s. Disabling INPUT_HORSE_SPRINT
					// does not lower a horse's gait the way it drops the player out of a
					// sprint, so an exhausted horse coasts on above 5.0, the rate stays
					// negative, the exhausted clamp turns it into exactly 0.0, and the bar
					// neither drains nor recovers until the rider presses slow-down.
					// Log the speed and the applied rate so that is measurable next run.
					<< " horseSpeed=" << ENTITY_SPEED(traceMount)
					<< " horseMode=" << horseMovementStaminaMode(traceMount)
					<< " horseRawRate=" << horseMovementStaminaRate(traceMount)
					<< " horseExh=" << (horseStaminaExhausted ? 1 : 0)
					<< " horseHealth=" << ENTITY::GET_ENTITY_HEALTH(traceMount)
					<< "/" << ENTITY::GET_ENTITY_MAX_HEALTH(traceMount, TRUE)
					<< " horseHealthCore=" << GET_CORE(traceMount, 0)
					<< " protectedHealthCore=" << protectedHorseHealthCore;
				trace << " locked=" << (locked ? 1 : 0);
				// Per-second state sample: TRACE, so it is available under
				// [Logging] Verbose=1 without drowning a normal session.
				gtLog("reserve", GT_TRACE, trace.str());
			}
		}
		else if (now - lastReserveTrace >= 1000) {
			// IDLE HEARTBEAT (#78). The whole reserve/Dead Eye controller lives inside
			// `if (ped)`, so with no player ped the trace simply stopped and the log
			// looked identical to "the feature ran and saw nothing". The shipped log
			// this pass was two lines, both locked=1 - unreadable as evidence either
			// way. A silent log must now mean the process is dead, not that the
			// controller declined to speak.
			lastReserveTrace = now;
			// Idle heartbeat stays GT_INFO: a silent log must keep meaning "this
			// controller is not running", which is the property that made several
			// of today's bugs diagnosable.
			gtLog("reserve", GT_INFO, "idle noPed locked=" +
				std::string(locked ? "1" : "0") +
				" noReserve=" + (g_noReserveCores ? "1" : "0"));
		}

#ifdef GAMEPLAYTWEAKS_CRASH_UPDATE_PROGRESSIVE
		if (progressiveBisectHold(kProgressiveBisectStepMs * 7u, 64u,
			"bandit-economy-world", "progressive hold before bandit-economy-world WAIT")) {
			WAIT(0);
			continue;
		}
#endif
		if (ped && g_banditMasksEnabled) {
			bool psycho = wearing("KIT_MASK_PSYCHO");
			SET_MELEE_DAMAGE(player, psycho ? g_psychoMeleeMult : 1.0f);
			SET_WEAPON_DEFENSE(player, psycho ? g_psychoBulletTakenMult : 1.0f);

			bool witnesses = WITNESSES_ACTIVE(player);
			if (witnesses && !witnessEvent) {
				witnessEvent = true;
				float roll = (float)(((now * 1103515245u + 12345u) >> 8) & 0xffff) / 65535.0f;
				suppressWitnessEvent = wearing("KIT_MASK_METAL") && roll >= g_witnessTalkChance;
			}
			if (!witnesses) { witnessEvent = false; suppressWitnessEvent = false; }
			if (suppressWitnessEvent) SUPPRESS_WITNESSES(player);

			bool ram = wearing("CLOTHING_ITEM_SKULLMASK_MR1_000_1");
			Hash cooldown = joaat("BOUNTYHUNTERSGLOBALCOOLDOWN");
			if (ram) {
				if (!ramWasWorn) savedHunterCooldown = invoke<int>(0x76CF93D4B416B288, cooldown);
				SET_BOUNTY_COOLDOWN(cooldown, 0x3fffffff);
				int nearby[65] = {}; nearby[0] = 32;
				int count = NEARBY_PEDS(ped, nearby);
				for (int i = 0; i < count && i < 32; ++i) {
					Ped hunter = nearby[i + 1];
					if (hunter && REL_GROUP(hunter) == joaat("REL_BOUNTY_HUNTER")) FLEE_PED(hunter, ped);
				}
			} else if (ramWasWorn) SET_BOUNTY_COOLDOWN(cooldown, savedHunterCooldown);
			ramWasWorn = ram;
		}

		if (ped && now - lastBanditTick >= 100) {
			lastBanditTick = now;
			int bounty = GET_BOUNTY_VALUE(player);
			if (wearing("KIT_MASK_BROWN_SACK") && bounty > lastBounty) {
				bounty = lastBounty + (int)((bounty - lastBounty) * g_bountyGainMult + 0.5f);
				SET_BOUNTY_VALUE(player, bounty);
			}
			lastBounty = bounty;

			int honor = honorValue();
			if (!mission && now <= greetWindowUntil && hasItem("PROVISION_DISCO_VIKING_COMB") && honor > lastHonor) {
				int gain = honor - lastHonor;
				if (gain <= 20) { honor = (std::min)(320, honor + gain); STAT_SET(joaat("HONOR_CURRENT"), honor); greetWindowUntil = 0; }
			}
			if (wearing("CLOTHING_ITEM_SKULLMASK_MR1_001_1") && honor < lastHonor) {
				int loss = lastHonor - honor;
				if (loss <= 80) { honor = lastHonor - (int)(loss * g_paganHonorLossMult + 0.5f); if (honor < -320) honor = -320; STAT_SET(joaat("HONOR_CURRENT"), honor); }
			}
			lastHonor = honor;

			int cash = CASH_BALANCE();
			int delta = cash - lastCash;
			if (delta > 0 && wearing("CLOTHING_ITEM_MASK_PIG_001") && fenceActive()) {
				int bonus = (int)(delta * (g_fenceMoneyMult - 1.0f) + 0.5f);
				if (bonus > 0 && ADD_CASH(bonus)) cash += bonus;
			}
			lastCash = enforceWalletCap();

			bool mastery = UNLOCKED(joaat("PROVISION_REINFORCED_GUNBELT_GATOR"));
			if (!mastery && !perceptionPeds.empty()) {
				for (Ped law : perceptionPeds) { SET_SEEING(law, 50.0f); SET_HEARING(law, 50.0f); }
				perceptionPeds.clear();
			}
			if (mastery) {
				int nearby[65] = {}; nearby[0] = 32;
				int count = NEARBY_PEDS(ped, nearby);
				for (int i = 0; i < count && i < 32; ++i) {
					Ped law = nearby[i + 1]; if (!law || !isLaw(law)) continue;
					SET_SEEING(law, 50.0f * g_lawPerceptionMult); SET_HEARING(law, 50.0f * g_lawPerceptionMult);
					if (std::find(perceptionPeds.begin(), perceptionPeds.end(), law) == perceptionPeds.end()) perceptionPeds.push_back(law);
				}
			}
		}
		if (ped && now - lastVikingTick >= 100) { lastVikingTick = now; if (updateVikingVictims(ped, mission)) lastCash = CASH_BALANCE(); }

		// Wildlife comes from two independent population paths. Scaling only the
		// ambient one left scenario-spawned wildlife untouched and made 0.1 look
		// essentially vanilla.
		// Both resolved density natives are *_THIS_FRAME. Apply both paths every
		// tick; disabled explicitly applies vanilla 1.0 for that frame.
		updateAnimalDensity();

		// Native collectables: load once Story Mode has data, then re-check found
		// state periodically so a marker vanishes as soon as the GAME marks it
		// collected (no proximity guessing, works across saves by itself).
		if (ped && !dead && now - lastNativeCollectTick >= 2000) {
			lastNativeCollectTick = now;
			if (!g_nativeCarvingsLoaded) loadNativeCollectibles();
			refreshNativeCollectibleBlips();
		}
		if (g_collectiblesDirty) refreshCollectibleBlips();
		if (ped && g_collectiblesEnabled && now - lastCollectClearTick >= 500 && PLAYER_CONTROL_ON(player)) {
			lastCollectClearTick = now; clearReachedCollectibles(ped);
		}
		{   // F2 = move nearest collectible marker to the player (manual fixup)
			static bool f2Was = false;
			bool f2 = developmentModeActive() &&
				(GetAsyncKeyState(0x71) & 0x8000) != 0; // VK_F2
			if (f2 && !f2Was && ped && !dead) relocateNearestCollectible(ped);
			f2Was = f2;
		}
		if (g_collectProbeEnabled) {
			probeContinuousTap();   // auto-log momentary taps (wheel page-flip etc.)
			static bool probeKeyWas = false;
			bool probeKey = (GetAsyncKeyState(0x79) & 0x8000) != 0; // VK_F10
			if (probeKey && !probeKeyWas) probeCollectibleNatives();
			probeKeyWas = probeKey;
		}
		// #146 observes after the other item systems. Its internal startup and UI
		// ownership gates defer every inventory-availability write until Rockstar's
		// shop and inventory owners are settled.
		// #114 isolation: #146 writes Rockstar inventory availability. Its player-
		// visible result is still unaccepted, so it cannot share the shop-recovery
		// build until shops are proven stable.
		// updateCoreCostGuard(ped, now, dead || SCREEN_FADED_OUT());
		CRASH_TRACE_STAGE("updateTrainBlips");
		if (now - lastTrainTick >= 250) { lastTrainTick = now; updateTrainBlips(); }
		CRASH_TRACE_STAGE("WAIT");
		WAIT(0);
	}
}
