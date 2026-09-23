// GameplayTweaks feature module: #98 per-icon reserve counts in the weapon radial.
//
// Runtime evidence disproved the original DataBinding approach: every wheel
// opening logged that the focused-subslot list was unavailable from all guessed
// roots.  The wheel does expose its highlighted weapon hash reliably, however,
// and the weapon definitions authoritatively list each weapon's ammo row.  Use
// that weapon hash and the weapon/ammo natives instead of depending on private UI
// application state.  Rockstar continues to own the icons, order and input.
//
// FONT. The supplied NativeMenu reference provides the sanctioned script-text
// path: Drawing.cpp:253-283 wraps the literal in TEXTFORMAT/P/FONT markup and
// prefixes the payload with ~s~. Its inc/enums.h:3-21 identifies
// `FixedWidthNumbers` as RDR Lino Numbers, the correct family for a numeric
// wheel counter. The earlier "font is unreachable" conclusion looked only for
// a font native and ignored the working reference the issue explicitly linked.

namespace RadialAmmoCounts {

struct ReferenceCanvas {
	float scale;
	float width;
	float height;
};

struct RadialAmmoFamily {
	const char* name;
	const char* const* entries;
	int count;
};

// Ammo rows below are the `<DamageModes>` `<AmmoInfo>` sequence of the matching
// weapons in MyOverhaul/weapons.ymt, read in file order, which is the order the
// wheel's sub-slot list presents.  Verified rows, with the weapon whose block was
// read: WEAPON_REVOLVER_CATTLEMAN (weapons.ymt:51385-51493),
// WEAPON_PISTOL_MAUSER, WEAPON_REPEATER_CARBINE, WEAPON_RIFLE_BOLTACTION,
// WEAPON_SHOTGUN_PUMP, WEAPON_RIFLE_VARMINT and WEAPON_BOW.  Every multi-entry
// bullet weapon in that file shares one of these five signatures.
static const char* const kRevolver[] = {
	"AMMO_REVOLVER", "AMMO_REVOLVER_HIGH_VELOCITY", "AMMO_REVOLVER_SPLIT_POINT",
	"AMMO_REVOLVER_EXPRESS", "AMMO_REVOLVER_EXPRESS_EXPLOSIVE"
};
static const char* const kPistol[] = {
	"AMMO_PISTOL", "AMMO_PISTOL_HIGH_VELOCITY", "AMMO_PISTOL_SPLIT_POINT",
	"AMMO_PISTOL_EXPRESS", "AMMO_PISTOL_EXPRESS_EXPLOSIVE"
};
static const char* const kRepeater[] = {
	"AMMO_REPEATER", "AMMO_REPEATER_HIGH_VELOCITY", "AMMO_REPEATER_SPLIT_POINT",
	"AMMO_REPEATER_EXPRESS", "AMMO_REPEATER_EXPRESS_EXPLOSIVE"
};
static const char* const kRifle[] = {
	"AMMO_RIFLE", "AMMO_RIFLE_HIGH_VELOCITY", "AMMO_RIFLE_SPLIT_POINT",
	"AMMO_RIFLE_EXPRESS", "AMMO_RIFLE_EXPRESS_EXPLOSIVE"
};
static const char* const kShotgun[] = {
	"AMMO_SHOTGUN", "AMMO_SHOTGUN_BUCKSHOT_INCENDIARY", "AMMO_SHOTGUN_SLUG",
	"AMMO_SHOTGUN_SLUG_EXPLOSIVE"
};
// WEAPON_BOW's DamageModes row in weapons.ymt actually carries TWELVE entries.
// The trailing six - AMMO_ARROW_TRACKING, _CONFUSION, _DISORIENT, _DRAIN, _TRAIL
// and _WOUND - are Online ability arrows with no Story Mode acquisition, and the
// same six-then-six split appears on WEAPON_THROWING_KNIVES.  Only the first six
// are listed here.  This is the one seat count in this file that is a judgement
// rather than a straight read of the row, so it is the first thing to check if
// the bow's numbers sit off-centre; SeatCountArrow in the INI corrects it
// without a rebuild.
static const char* const kArrow[] = {
	"AMMO_ARROW", "AMMO_ARROW_IMPROVED", "AMMO_ARROW_SMALL_GAME",
	"AMMO_ARROW_POISON", "AMMO_ARROW_FIRE", "AMMO_ARROW_DYNAMITE"
};
static const char* const kVarmint[] = { "AMMO_22", "AMMO_22_TRANQUILIZER" };
// The elephant rifle ships in the mp007 pack, not weapons.ymt, so its row was
// read from MyOverhaul/weapon_rifle_elephant.ymt.  A single-entry row means the
// wheel draws no sub-slot list at all (sub_slot_list.ymt gates its children on
// `focusedEntrySubSlotItems.Size GREATER 1`), so nothing is drawn for it.
static const char* const kElephant[] = { "AMMO_RIFLE_ELEPHANT" };

static const RadialAmmoFamily kFamilies[] = {
	{ "revolver", kRevolver, (int)(sizeof(kRevolver) / sizeof(kRevolver[0])) },
	{ "pistol", kPistol, (int)(sizeof(kPistol) / sizeof(kPistol[0])) },
	{ "repeater", kRepeater, (int)(sizeof(kRepeater) / sizeof(kRepeater[0])) },
	{ "rifle", kRifle, (int)(sizeof(kRifle) / sizeof(kRifle[0])) },
	{ "shotgun", kShotgun, (int)(sizeof(kShotgun) / sizeof(kShotgun[0])) },
	{ "arrow", kArrow, (int)(sizeof(kArrow) / sizeof(kArrow[0])) },
	{ "varmint", kVarmint, (int)(sizeof(kVarmint) / sizeof(kVarmint[0])) },
	{ "elephant", kElephant, (int)(sizeof(kElephant) / sizeof(kElephant[0])) }
};

// ---------------------------------------------------------------- settings --

static bool  g_enabled       = true;
static int   g_fontSize      = 20;      // NativeMenu's option-counter size.
static char  g_fontFace[48]  = "FixedWidthNumbers";
static int   g_dropshadow    = 1;
static float g_stridePixels  = 38.0f;   // 32 px icon + 6 px stack padding.
static float g_countBaseline = 0.717f;
static float g_nudgeX        = 0.0f;
static float g_nudgeY        = 0.0f;
static int   g_seatOverrideArrow = 0;   // 0 = use the compiled row length.
static int   g_liveR = 245, g_liveG = 245, g_liveB = 245, g_liveA = 245;
static int   g_zeroR = 132, g_zeroG = 132, g_zeroB = 132, g_zeroA = 225;
static int   g_heartbeatMs = 5000;

static void loadSettings(DWORD now) {
	static DWORD nextRefresh = 0;
	if (now < nextRefresh) return;
	nextRefresh = now + 2000;

	const char* ini = g_iniPath.c_str();
	g_enabled = GetPrivateProfileIntA("RadialAmmoCounts", "Enabled", 1, ini) != 0;

	g_fontSize = GetPrivateProfileIntA("RadialAmmoCounts", "FontSize", 20, ini);
	GetPrivateProfileStringA("RadialAmmoCounts", "FontFace", "FixedWidthNumbers",
		g_fontFace, sizeof(g_fontFace), ini);
	g_dropshadow = GetPrivateProfileIntA("RadialAmmoCounts", "Dropshadow", 1, ini);
	g_stridePixels = GetPrivateProfileIntA("RadialAmmoCounts", "SeatStridePx", 380, ini) * 1.0e-1f;
	g_countBaseline = GetPrivateProfileIntA("RadialAmmoCounts", "CountBaselineY", 7170, ini) * 1.0e-4f;
	// Win32 returns UINT; decode signed offsets before converting to float.
	g_nudgeX = static_cast<int>(GetPrivateProfileIntA("RadialAmmoCounts", "NudgeX", 0, ini)) * 1.0e-4f;
	g_nudgeY = static_cast<int>(GetPrivateProfileIntA("RadialAmmoCounts", "NudgeY", 0, ini)) * 1.0e-4f;
	g_seatOverrideArrow = GetPrivateProfileIntA("RadialAmmoCounts", "SeatCountArrow", 0, ini);

	g_liveR = GetPrivateProfileIntA("RadialAmmoCounts", "LiveR", 245, ini);
	g_liveG = GetPrivateProfileIntA("RadialAmmoCounts", "LiveG", 245, ini);
	g_liveB = GetPrivateProfileIntA("RadialAmmoCounts", "LiveB", 245, ini);
	g_liveA = GetPrivateProfileIntA("RadialAmmoCounts", "LiveA", 245, ini);
	g_zeroR = GetPrivateProfileIntA("RadialAmmoCounts", "ZeroR", 132, ini);
	g_zeroG = GetPrivateProfileIntA("RadialAmmoCounts", "ZeroG", 132, ini);
	g_zeroB = GetPrivateProfileIntA("RadialAmmoCounts", "ZeroB", 132, ini);
	g_zeroA = GetPrivateProfileIntA("RadialAmmoCounts", "ZeroA", 225, ini);
	g_heartbeatMs = GetPrivateProfileIntA("RadialAmmoCounts", "HeartbeatMs", 5000, ini);

	if (g_fontSize < 8) g_fontSize = 8;
	if (g_fontSize > 72) g_fontSize = 72;
	if (!g_fontFace[0]) strcpy_s(g_fontFace, "FixedWidthNumbers");
	if (g_stridePixels <= 0.0f) g_stridePixels = 38.0f;
	if (g_heartbeatMs < 1000) g_heartbeatMs = 1000;
}

// --------------------------------------------------------------- diagnostic --

// #126: routed to the unified GameplayTweaks.log under subsystem
// "radial-counts". Each record is assembled whole and emitted in one call, so a
// line can never be left half-written the way the old per-token reopen did.
static void radialAmmoCountsLog(GtLogLevel level, const std::string& line) {
	static bool announced = false;
	if (!announced) {
		announced = true;
		gtLog("radial-counts", GT_INFO, "session start source=wheel-highlighted-weapon");
	}
	gtLog("radial-counts", level, line);
}

// -------------------------------------------------------------------- draw --

static bool referenceCanvas(ReferenceCanvas& canvas) {
	int width = 0, height = 0;
	GRAPHICS::GET_SCREEN_RESOLUTION(&width, &height);
	if (width <= 0 || height <= 0) return false;
	canvas.width = (float)width;
	canvas.height = (float)height;
	// Rockstar authors the wheel against a 1080-high canvas and centres it, so
	// scaling by height alone and anchoring to 0.5 keeps the seat run correct on
	// 16:9, 16:10 and ultrawide without stretching its spacing.
	canvas.scale = canvas.height / 1080.0f;
	return true;
}

static bool wheelOpen() {
	static const Hash kOpenWheel = joaat("INPUT_OPEN_WHEEL_MENU");
	return PAD::IS_CONTROL_PRESSED(0, kOpenWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(0, kOpenWheel) ||
		PAD::IS_CONTROL_PRESSED(2, kOpenWheel) ||
		PAD::IS_DISABLED_CONTROL_PRESSED(2, kOpenWheel);
}

static const RadialAmmoFamily* familyForWeapon(Hash weapon) {
	if (!weapon || weapon == joaat("WEAPON_UNARMED")) return nullptr;
	const Hash defaultAmmo = WEAPON::_GET_AMMO_TYPE_FOR_WEAPON(weapon);
	if (!defaultAmmo) return nullptr;
	for (const RadialAmmoFamily& family : kFamilies) {
		for (int index = 0; index < family.count; ++index) {
			if (defaultAmmo == joaat(family.entries[index])) return &family;
		}
	}
	return nullptr;
}

static int seatCount(const RadialAmmoFamily& family) {
	if (g_seatOverrideArrow > 0 && strcmp(family.name, "arrow") == 0) {
		return (g_seatOverrideArrow < family.count) ? g_seatOverrideArrow : family.count;
	}
	return family.count;
}

static float pixelX(const ReferenceCanvas& canvas, float offsetFromCentre) {
	return 0.5f + g_nudgeX + offsetFromCentre * canvas.scale / canvas.width;
}

static void drawCount(const char* text, float x, float y, bool empty) {
	if (empty) HUD::_SET_TEXT_COLOR(g_zeroR, g_zeroG, g_zeroB, g_zeroA);
	else HUD::_SET_TEXT_COLOR(g_liveR, g_liveG, g_liveB, g_liveA);
	HUD::SET_TEXT_DROPSHADOW(g_dropshadow, 0, 0, 0, 210);
	char markup[320] = {};
	sprintf_s(markup,
		"<TEXTFORMAT RIGHTMARGIN='0'><P ALIGN='Center'><FONT FACE='$%s' LETTERSPACING='0' SIZE='%d'>~s~%s</FONT></P><TEXTFORMAT>",
		g_fontFace, g_fontSize, text);
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", markup),
		-1.0f + x * 2.0f, y);
}

} // namespace RadialAmmoCounts

// Integration entry point. Call once per frame beside updateRadialAmmoScroll.
// It is read/draw-only and does not consume radial input.
static void updateRadialAmmoCounts(Ped ped) {
	using namespace RadialAmmoCounts;
	const DWORD now = GetTickCount();
	loadSettings(now);
	static DWORD lastHeartbeat = 0;
	static Hash lastLoggedWeapon = 0;
	static int lastLoggedCounts[16] = { 0 };

	// Idle heartbeat first, and unconditionally. A silent log now means the
	// module is not running at all, which is the distinction the previous
	// revision could not make.
	if (lastHeartbeat == 0 || now - lastHeartbeat >= (DWORD)g_heartbeatMs) {
		lastHeartbeat = now;
		std::ostringstream idle;
		idle << "idle enabled=" << (g_enabled ? 1 : 0)
			<< " ped=" << ped
			<< " wheel=" << (wheelOpen() ? "open" : "closed")
			<< " font=" << g_fontFace << " size=" << g_fontSize
			<< " baselineY=" << (g_countBaseline + g_nudgeY)
			<< " nudgeX=" << g_nudgeX << " nudgeY=" << g_nudgeY;
		radialAmmoCountsLog(GT_INFO, idle.str());
	}

	if (!g_enabled) return;
	if (!ped || !wheelOpen()) {
		lastLoggedWeapon = 0;
		return;
	}

	const Hash weapon = WHEEL_HIGHLIGHTED();
	const RadialAmmoFamily* family = familyForWeapon(weapon);
	if (!family) return;

	const int seats = seatCount(*family);
	// One entry means no sub-slot list is drawn by the wheel, so there is
	// nothing to annotate and drawing would put a stray number on the art.
	if (seats < 2) return;

	ReferenceCanvas canvas = {};
	if (!referenceCanvas(canvas)) return;

	const float baselineY = g_countBaseline + g_nudgeY;
	const float firstOffset = -0.5f * (float)(seats - 1) * g_stridePixels;

	int counts[16] = { 0 };
	for (int index = 0; index < seats && index < 16; ++index) {
		const Hash ammoType = joaat(family->entries[index]);
		const int reserve = (std::max)(0, GET_PED_AMMO_BY_TYPE(ped, ammoType));
		counts[index] = reserve;
		const bool empty = reserve == 0;
		const float x = pixelX(canvas, firstOffset + index * g_stridePixels);
		char number[16];
		sprintf_s(number, "%d", reserve);
		drawCount(number, x, baselineY, empty);
	}

	// Per-render record of what was found, emitted whenever the highlighted
	// weapon or any drawn count changes, so firing/buying/looting shows up as a
	// line rather than having to be inferred.
	bool changed = weapon != lastLoggedWeapon;
	for (int index = 0; index < seats && index < 16 && !changed; ++index) {
		if (counts[index] != lastLoggedCounts[index]) changed = true;
	}
	if (changed) {
		lastLoggedWeapon = weapon;
		std::ostringstream out;
		out << "render weapon=0x" << std::hex << weapon << std::dec
			<< " family=" << family->name << " seats=" << seats
			<< " baselineY=" << baselineY << " types=";
		for (int index = 0; index < seats && index < 16; ++index) {
			if (index) out << ',';
			out << family->entries[index] << '=' << counts[index];
			lastLoggedCounts[index] = counts[index];
		}
		radialAmmoCountsLog(GT_INFO, out.str());
	}
}
