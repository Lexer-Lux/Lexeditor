// GameplayTweaks feature module: #23 visible fortification overfill.
//
// ---------------------------------------------------------------------------
// WHERE THIS GEOMETRY AND THIS DRAW METHOD COME FROM
// ---------------------------------------------------------------------------
// Everything below is taken from a static disassembly of the reference mod
// Lexer supplied, `_downloads/inspect/hardcore-stamina/Y_Hardcore_Stamina.asi`,
// not from experiment.  Its faux core draw routine lives at 0x180008D26 and its
// sprite helper at 0x1800026C0.  The helper is:
//
//     drawSprite(rcx = txd, rdx = texture, xmm2 = left, xmm3 = top,
//                [rsp+0xA0] = w, [rsp+0xA8] = h, [rsp+0xB0] = rotation,
//                [rsp+0xB8..0xD0] = r, g, b, a)
//
// and internally it
//   * calls HAS_STREAMED_TEXTURE_DICT_LOADED (0x54D6900929CCF162) on the txd,
//   * calls REQUEST_STREAMED_TEXTURE_DICT   (0xC1BA29DF5631B0F8) when it is not
//     loaded and returns without drawing that frame,
//   * converts the supplied LEFT/TOP to a centre by adding w*0.5 and h*0.5
//     (the 0.5f constant is at RVA 0x1AC7C), then
//   * calls DRAW_SPRITE (0xC9884ECADE94CB34).
//
// This is exactly the "request the dictionary, then draw" rule that fixed our
// custom map icons - see `ensureLexBlipTextures()` in collectibles_map.cpp.
//
// The sprites it uses are Rockstar's own, and they are the reason its cores
// look vanilla.  There are no authored dots and no per-segment rectangles:
//
//     txd "rpg_textures"     tex "rpg_background"    - the dark core disc
//     txd "rpg_meter_track"  tex "rpg_meter_track_9" - the ring's empty track
//     txd "rpg_meter"        tex "rpg_meter_0".."rpg_meter_99"
//                                                    - ONE authored, continuous,
//                                                      anti-aliased ring arc per
//                                                      percent, drawn as a
//                                                      single sprite
//     txd "blips"            tex "blip_player_coach" - the glyph inside the disc
//
// Note the dictionary names: the arc sprites live in txd "rpg_meter", NOT in
// "rpg_textures".  Our previous attempt drew "rpg_textures"/"rpg_meter_N", which
// is a different resource, and that is what produced the solid yellow discs.
//
// Its layout constants (RVA 0x180008CE0-0x180008DBA), all relative to one
// per-core box (W, H) whose top-left is (X, Y):
//
//     rpg_background   drawn at 0.90 * (W, H), concentric   (double at 0x1ACC0)
//     rpg_meter_track_9 drawn at 1.00 * (W, H)
//     rpg_meter_N      drawn at 1.05 * (W, H), concentric   (double at 0x1ACC8)
//
// and its INI box, parsed at 0x180002E52-0x180002F19:
//
//     POSITION_X / POSITION_Y  * 1.0e-3  -> normalised screen coords
//     WIDTH      / HEIGHT      * 1.0e-4  -> normalised screen size
//
// so its shipped [CORE_POSITION] WIDTH=242 HEIGHT=430 is a box of
// 0.0242 x 0.0430 normalised, i.e. a physical square on a 16:9 display.  That
// box size is the author's own calibration of a vanilla core and is reused
// verbatim below.  Its POSITION values are deliberately NOT reused: that mod
// paints one extra core wherever the user points it, so its default position is
// evidence of nothing about where Rockstar's five meters actually sit.
//
// The five seat centres below are instead validated directly against Lexer's
// own returned-test screenshots on issue #23.  In the last screenshot the
// overlay this module drew at seat 0 lands within one screenshot pixel of the
// centre of the vanilla health disc (measured 81.0 vs 82.0 px) and the overlay
// at seat 2 lands within 1.5 px of the Dead Eye disc (244.0 vs 242.5 px).  The
// seat table was therefore never the defect; size and colour were.
//
// ---------------------------------------------------------------------------
// HOW THE THREE REPORTED DEFECTS ARE ANSWERED
// ---------------------------------------------------------------------------
// (a) Dots.  Gone.  Each arc is now ONE DRAW_SPRITE of one authored Rockstar
//     ring texture, `rpg_meter/rpg_meter_<percent>`.  There is no compositing,
//     no segment loop and no custom texture dictionary.
//
// (b) Alignment and thickness.  The arc is drawn at the reference mod's own
//     calibrated core box scaled by its own 1.05 factor, so it lands on the
//     vanilla ring and is as thick as the vanilla ring, because it IS the
//     vanilla ring art at the vanilla ring's size.  The previous 128x128
//     hand-drawn texture put a 10/128 stroke inside a 118/128 circle, which is
//     the "not nearly thick enough" ring in the screenshot.
//
// (c) Gold on gold.  This module no longer draws anything gold.  When an
//     attribute is fortified the game has already painted the whole ring gold;
//     drawing a second gold arc on top of it can never read.  Instead we
//     overdraw the SPENT part of the ring in the ordinary un-fortified meter
//     colour - the same 0xE5E5E5 the reference mod uses for a normal fill - so
//     the only gold left on screen is the arc the player still has.  The gold
//     the player sees is Rockstar's own gold, at Rockstar's own thickness and
//     position, and its LENGTH is the remaining overfill. Core and bar timers
//     share that one outer ring; they never create concentric rings.

namespace VisibleGoldOverfill {

static constexpr float kTimerEpsilon = 0.05f;

// The three native ids read out of the reference binary.  They are recorded
// here as evidence and are exactly the ids behind the SDK wrappers this module
// calls (natives.h lines 1806, 7757 and 7758), so the wrappers are used for
// type safety without losing the provenance.
//   HAS_STREAMED_TEXTURE_DICT_LOADED = 0x54D6900929CCF162
//   REQUEST_STREAMED_TEXTURE_DICT    = 0xC1BA29DF5631B0F8
//   DRAW_SPRITE                      = 0xC9884ECADE94CB34

// Rockstar's continuous ring-arc family. 100 authored frames, 0 = empty.
static constexpr char kMeterDictionary[] = "rpg_meter";
static constexpr char kMeterTexturePrefix[] = "rpg_meter_";

// Defaults are the reference mod's shipped calibration; every one of them is
// overridable from [Fortification] so a nudge does not need a rebuild, which is
// exactly why that mod exposes the same four numbers.
static float g_boxWidth = 0.0242f;      // Fortification/BoxWidth,  1e-4 units
static float g_boxHeight = 0.0430f;     // Fortification/BoxHeight, 1e-4 units
static float g_barRingScale = 1.05f;    // Fortification/BarRingScale,  1e-2
// Retained only for backward-compatible INI parsing; no inner ring is drawn.
static float g_coreRingScale = 0.86f;   // Fortification/CoreRingScale, legacy
static float g_nudgeX = 0.0f;           // Fortification/NudgeX, 1e-4 normalised
static float g_nudgeY = 0.0f;           // Fortification/NudgeY, 1e-4 normalised
static bool g_enabled = true;
static bool g_showBars = true;
static bool g_showCores = true;
// The colour the spent part of the ring is repainted in. 229/229/229 is the
// reference mod's own normal-fill colour (0xE5 at 0x180008F31).
static int g_spentBarR = 229, g_spentBarG = 229, g_spentBarB = 229, g_spentBarA = 255;
// Legacy values are still parsed so existing INIs remain valid; the rejected
// inner-core ring renderer no longer consumes them.
static int g_spentCoreR = 0, g_spentCoreG = 0, g_spentCoreB = 0, g_spentCoreA = 215;
// Explicit overlay colour. Relying on Rockstar's binary fortified tint made
// stamina invisible when that native state did not recolour its vanilla ring.
static int g_goldR = 255, g_goldG = 196, g_goldB = 64, g_goldA = 255;

// Centre positions in pixels on a 1920x1080 reference canvas: Arthur's
// Health / Stamina / Dead Eye, then the current mount's Health / Stamina.
struct MeterSeat {
	float x;
	float y;
};

static MeterSeat g_seats[5] = {
	{ 93.75f, 723.75f },
	{ 154.69f, 701.25f },
	{ 219.38f, 689.06f },
	{ 283.13f, 701.25f },
	{ 344.06f, 723.75f },
};
static constexpr const char* kSeatNames[5] = {
	"PLAYER HEALTH", "PLAYER STAMINA", "PLAYER DEAD EYE",
	"HORSE HEALTH", "HORSE STAMINA"
};
static constexpr const char* kSeatKeys[5] = {
	"PlayerHealth", "PlayerStamina", "PlayerDeadEye",
	"HorseHealth", "HorseStamina"
};
static int g_calibrationSeat = 0;

struct TimerPeak {
	float peak = 0.0f;
	float previous = 0.0f;
};

static TimerPeak g_barTimers[5];
static TimerPeak g_coreTimers[5];

static float saneSeconds(float seconds) {
	return std::isfinite(seconds) && seconds > kTimerEpsilon ? seconds : 0.0f;
}

// Native durations differ between weak, potent and special tonics.  Learning
// the peak from the live timer avoids hard-coding those item tiers.  A timer
// increase is a tonic refresh and starts a new full arc.  Loading a save in the
// middle of an effect deliberately treats its current remainder as the peak,
// so the arc is immediately useful and still drains smoothly to zero.
static float remainingFraction(TimerPeak& timer, float rawSeconds) {
	const float seconds = saneSeconds(rawSeconds);
	if (seconds == 0.0f) {
		timer = {};
		return 0.0f;
	}

	const bool newlyActive = timer.previous <= kTimerEpsilon || timer.peak <= kTimerEpsilon;
	const bool refreshed = !newlyActive && seconds > timer.previous + 0.75f;
	if (newlyActive || refreshed) timer.peak = seconds;
	else if (seconds > timer.peak) timer.peak = seconds;
	timer.previous = seconds;

	return (std::max)(0.0f, (std::min)(1.0f, seconds / timer.peak));
}

static float barSeconds(Ped ped, int attribute) {
	return invoke<float>(0x4C9F782180712742, ped, attribute);
}

static float coreSeconds(Ped ped, int core) {
	return invoke<float>(0xB429F58803D285B1, ped, core);
}

struct ReferenceCanvas {
	float originX;
	float scale;
	float screenWidth;
	float screenHeight;
};

static bool referenceCanvas(ReferenceCanvas& canvas) {
	int width = 0, height = 0;
	GRAPHICS::GET_SCREEN_RESOLUTION(&width, &height);
	if (width <= 0 || height <= 0) return false;

	canvas.screenWidth = (float)width;
	canvas.screenHeight = (float)height;
	canvas.scale = canvas.screenHeight / 1080.0f;
	const float referenceWidth = 1920.0f * canvas.scale;
	canvas.originX = (canvas.screenWidth - referenceWidth) * 0.5f;
	return true;
}

static float readFortificationFloat(const char* key, float fallback) {
	char fallbackText[32] = {};
	char value[32] = {};
	sprintf_s(fallbackText, "%.3f", fallback);
	GetPrivateProfileStringA("Fortification", key, fallbackText, value,
		sizeof(value), g_iniPath.c_str());
	char* end = nullptr;
	const float parsed = strtof(value, &end);
	return end != value && std::isfinite(parsed) ? parsed : fallback;
}

static void loadSettings() {
	static bool loaded = false;
	if (loaded) return;
	loaded = true;

	const char* ini = g_iniPath.c_str();
	g_enabled = GetPrivateProfileIntA("Fortification", "Enabled", 1, ini) != 0;
	g_showBars = GetPrivateProfileIntA("Fortification", "ShowBars", 1, ini) != 0;
	g_showCores = GetPrivateProfileIntA("Fortification", "ShowCores", 1, ini) != 0;

	// Same integer encodings the reference mod's INI uses, so a value copied out
	// of HardcoreStamina.ini means the same thing here.
	g_boxWidth = GetPrivateProfileIntA("Fortification", "BoxWidth", 242, ini) * 1.0e-4f;
	g_boxHeight = GetPrivateProfileIntA("Fortification", "BoxHeight", 430, ini) * 1.0e-4f;
	g_barRingScale = GetPrivateProfileIntA("Fortification", "BarRingScale", 105, ini) * 1.0e-2f;
	g_coreRingScale = GetPrivateProfileIntA("Fortification", "CoreRingScale", 86, ini) * 1.0e-2f;
	// Signed nudges, so one number moves all five seats together if Lexer wants
	// the whole cluster shifted rather than each meter re-measured.
	g_nudgeX = GetPrivateProfileIntA("Fortification", "NudgeX", 0, ini) * 1.0e-4f;
	g_nudgeY = GetPrivateProfileIntA("Fortification", "NudgeY", 0, ini) * 1.0e-4f;
	for (int seat = 0; seat < 5; ++seat) {
		char key[48] = {};
		sprintf_s(key, "%sX", kSeatKeys[seat]);
		g_seats[seat].x = readFortificationFloat(key, g_seats[seat].x);
		sprintf_s(key, "%sY", kSeatKeys[seat]);
		g_seats[seat].y = readFortificationFloat(key, g_seats[seat].y);
	}

	g_spentBarR = GetPrivateProfileIntA("Fortification", "SpentBarR", 229, ini);
	g_spentBarG = GetPrivateProfileIntA("Fortification", "SpentBarG", 229, ini);
	g_spentBarB = GetPrivateProfileIntA("Fortification", "SpentBarB", 229, ini);
	g_spentBarA = GetPrivateProfileIntA("Fortification", "SpentBarA", 255, ini);
	g_spentCoreR = GetPrivateProfileIntA("Fortification", "SpentCoreR", 0, ini);
	g_spentCoreG = GetPrivateProfileIntA("Fortification", "SpentCoreG", 0, ini);
	g_spentCoreB = GetPrivateProfileIntA("Fortification", "SpentCoreB", 0, ini);
	g_spentCoreA = GetPrivateProfileIntA("Fortification", "SpentCoreA", 215, ini);
	g_goldR = GetPrivateProfileIntA("Fortification", "GoldR", 255, ini);
	g_goldG = GetPrivateProfileIntA("Fortification", "GoldG", 196, ini);
	g_goldB = GetPrivateProfileIntA("Fortification", "GoldB", 64, ini);
	g_goldA = GetPrivateProfileIntA("Fortification", "GoldA", 255, ini);

	if (g_boxWidth <= 0.0f) g_boxWidth = 0.0242f;
	if (g_boxHeight <= 0.0f) g_boxHeight = 0.0430f;
	if (g_barRingScale <= 0.0f) g_barRingScale = 1.05f;
	if (g_coreRingScale <= 0.0f) g_coreRingScale = 0.86f;
}

static void saveCalibration() {
	char value[32] = {};
	for (int seat = 0; seat < 5; ++seat) {
		char key[48] = {};
		sprintf_s(value, "%.2f", g_seats[seat].x);
		sprintf_s(key, "%sX", kSeatKeys[seat]);
		WritePrivateProfileStringA("Fortification", key, value, g_iniPath.c_str());
		sprintf_s(value, "%.2f", g_seats[seat].y);
		sprintf_s(key, "%sY", kSeatKeys[seat]);
		WritePrivateProfileStringA("Fortification", key, value, g_iniPath.c_str());
	}
	sprintf_s(value, "%d", (int)std::lround(g_boxWidth * 10000.0f));
	WritePrivateProfileStringA("Fortification", "BoxWidth", value, g_iniPath.c_str());
	sprintf_s(value, "%d", (int)std::lround(g_boxHeight * 10000.0f));
	WritePrivateProfileStringA("Fortification", "BoxHeight", value, g_iniPath.c_str());
}

// One authored, continuous Rockstar ring arc, drawn once. `fraction` is the
// actual visible length; unlike the rejected pass this never infers gold from
// whatever binary tint the vanilla HUD happened to use for that attribute.
static void drawAuthoredArc(const ReferenceCanvas& canvas, const MeterSeat& seat,
	float ringScale, float fraction, int r, int g, int b, int a) {
	// rpg_meter_0 is an empty ring: drawing it is a no-op, and it is also what
	// a fully-remaining effect asks for, so skip it rather than pay a draw call.
	const int percent = (int)std::lround(fraction * 99.0f);
	if (percent <= 0) return;
	const int clamped = (std::min)(99, percent);

	char texture[32] = {};
	sprintf_s(texture, "%s%d", kMeterTexturePrefix, clamped);

	const float width = g_boxWidth * ringScale;
	const float height = g_boxHeight * ringScale;
	const float centerX =
		(canvas.originX + seat.x * canvas.scale) / canvas.screenWidth + g_nudgeX;
	const float centerY = (seat.y * canvas.scale) / canvas.screenHeight + g_nudgeY;

	GRAPHICS::DRAW_SPRITE(kMeterDictionary, texture, centerX, centerY,
		width, height, 0.0f, r, g, b, a, FALSE);
}

static bool overlayMayRender(Ped ped, bool gameplayLocked) {
	if (!ped || gameplayLocked) return false;
	if (HUD::IS_PAUSE_MENU_ACTIVE() || HUD::IS_HUD_HIDDEN() ||
		HUD::IS_RADAR_HIDDEN()) return false;
	if (CAM::IS_CINEMATIC_CAM_RENDERING()) return false;
	return true;
}

static void resetSeat(int seat) {
	g_barTimers[seat] = {};
	g_coreTimers[seat] = {};
}

static void drawMeter(int seat, float bar, float coreFill,
	const ReferenceCanvas& canvas) {
	// One meter gets one circular overlay. The previous implementation drew a
	// second, smaller ring for the core timer; that source-authored duplication
	// is exactly the concentric-circle failure Lexer reported. Core-only boosts
	// remain representable by sharing this one outer ring rather than inventing
	// another circle.
	const float displayed = (std::max)(g_showBars ? bar : 0.0f,
		g_showCores ? coreFill : 0.0f);
	if (displayed <= 0.0f) return;
	drawAuthoredArc(canvas, g_seats[seat], g_barRingScale, 1.0f,
		g_spentBarR, g_spentBarG, g_spentBarB, g_spentBarA);
	drawAuthoredArc(canvas, g_seats[seat], g_barRingScale, displayed,
		g_goldR, g_goldG, g_goldB, g_goldA);
}

static void updateCalibration(DWORD now, const ReferenceCanvas& canvas) {
	static bool toggleLatch = false;
	static bool cycleLatch = false;
	static bool saveLatch = false;
	static DWORD lastNudge = 0;
	if (!developmentModeActive()) {
		g_fortificationCalibrationOwnsNumpad = false;
		toggleLatch = false;
		cycleLatch = false;
		saveLatch = false;
		return;
	}
	const bool toggleDown = (GetAsyncKeyState(VK_NUMPAD0) & 0x8000) != 0;
	if (toggleDown && !toggleLatch) {
		g_fortificationCalibrationOwnsNumpad =
			!g_fortificationCalibrationOwnsNumpad;
	}
	toggleLatch = toggleDown;
	if (!g_fortificationCalibrationOwnsNumpad) return;

	const bool cycleDown = (GetAsyncKeyState(VK_NUMPAD1) & 0x8000) != 0;
	if (cycleDown && !cycleLatch)
		g_calibrationSeat = (g_calibrationSeat + 1) % 5;
	cycleLatch = cycleDown;

	if (now - lastNudge >= 16) {
		const bool fine = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
		const float positionStep = fine ? 0.10f : 1.0f;
		const float scaleFactor = fine ? 0.999f : 0.99f;
		bool changed = false;
		if (GetAsyncKeyState(VK_NUMPAD4) & 0x8000) { g_seats[g_calibrationSeat].x -= positionStep; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD6) & 0x8000) { g_seats[g_calibrationSeat].x += positionStep; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD8) & 0x8000) { g_seats[g_calibrationSeat].y -= positionStep; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD2) & 0x8000) { g_seats[g_calibrationSeat].y += positionStep; changed = true; }
		if (GetAsyncKeyState(VK_NUMPAD7) & 0x8000) {
			g_boxWidth *= scaleFactor; g_boxHeight *= scaleFactor; changed = true;
		}
		if (GetAsyncKeyState(VK_NUMPAD9) & 0x8000) {
			g_boxWidth /= scaleFactor; g_boxHeight /= scaleFactor; changed = true;
		}
		g_boxWidth = (std::max)(0.005f, (std::min)(0.10f, g_boxWidth));
		g_boxHeight = (std::max)(0.009f, (std::min)(0.18f, g_boxHeight));
		if (changed) lastNudge = now;
	}

	const bool saveDown = (GetAsyncKeyState(VK_NUMPAD5) & 0x8000) != 0;
	if (saveDown && !saveLatch) saveCalibration();
	saveLatch = saveDown;

	// Calibration must work without consuming five tonics. Draw exactly one ring
	// per seat. The previous selected-seat inner ring plus the live overlay made
	// the editor visibly show two different rings for one meter.
	for (int seat = 0; seat < 5; ++seat) {
		const bool selected = seat == g_calibrationSeat;
		drawAuthoredArc(canvas, g_seats[seat], g_barRingScale, 1.0f,
			255, 255, 255, selected ? 255 : 80);
	}
	char line[256] = {};
	sprintf_s(line, "FORTIFICATION CALIBRATION  %s  x %.2f  y %.2f  size %d x %d",
		kSeatNames[g_calibrationSeat], g_seats[g_calibrationSeat].x,
		g_seats[g_calibrationSeat].y,
		(int)std::lround(g_boxWidth * 10000.0f),
		(int)std::lround(g_boxHeight * 10000.0f));
	drawReconText(line, 0.5f, 0.76f);
	drawReconText("numpad 1 next meter   4/6 move X   8/2 move Y   7/9 scale all   shift fine   5 save   0 exit",
		0.5f, 0.79f);
}

} // namespace VisibleGoldOverfill

// Integration entry point. Call once per frame after `locked` is calculated.
static void updateVisibleGoldOverfill(Ped ped, bool gameplayLocked) {
	using namespace VisibleGoldOverfill;
	if (!ped) return;
	loadSettings();
	if (!g_enabled) return;

	float bars[5] = {};
	float cores[5] = {};
	for (int meter = 0; meter < 3; ++meter) {
		bars[meter] = remainingFraction(g_barTimers[meter], barSeconds(ped, meter));
		cores[meter] = remainingFraction(g_coreTimers[meter], coreSeconds(ped, meter));
	}

	// The vanilla horse seats follow the owned mount while it is nearby, not
	// merely while Arthur is sitting on it. Prefer the ridden entity, then the
	// player's owned mount, so the custom arcs follow the same visible seats.
	Ped mount = GET_MOUNT(ped);
	if (!mount) mount = GET_OWNED_MOUNT(PLAYER::PLAYER_ID());
	const bool hasMount = mount && ENTITY::DOES_ENTITY_EXIST(mount);
	if (hasMount) {
		for (int attribute = 0; attribute < 2; ++attribute) {
			const int seat = attribute + 3;
			bars[seat] = remainingFraction(g_barTimers[seat], barSeconds(mount, attribute));
			cores[seat] = remainingFraction(g_coreTimers[seat], coreSeconds(mount, attribute));
		}
	} else {
		resetSeat(3);
		resetSeat(4);
	}

	// Keep sampling while the HUD is hidden so a tonic refresh during a pause or
	// cinematic is still recognized when the meters return. The Numpad-0 layout
	// calibrator is an authoring tool and updateCalibration itself rejects input
	// unless the shared tilde-controlled developer mode is active.
	if (!overlayMayRender(ped, gameplayLocked)) return;

	ReferenceCanvas canvas = {};
	if (!referenceCanvas(canvas)) return;

	// The map-icon rule: a non-resident dictionary draws nothing (or black) until
	// it is requested, and it is never requested for you. Request it every pass
	// and never release it; skip this frame until it reports loaded.
	if (!TXD::HAS_STREAMED_TEXTURE_DICT_LOADED(kMeterDictionary)) {
		TXD::REQUEST_STREAMED_TEXTURE_DICT(kMeterDictionary, FALSE);
		return;
	}
	updateCalibration(GetTickCount(), canvas);
	// Calibration is a mutually exclusive preview. Do not composite live
	// fortification meters underneath it or the preview ceases to be one ring.
	if (g_fortificationCalibrationOwnsNumpad) return;

	for (int meter = 0; meter < 3; ++meter)
		drawMeter(meter, bars[meter], cores[meter], canvas);
	if (hasMount)
		for (int meter = 3; meter < 5; ++meter)
			drawMeter(meter, bars[meter], cores[meter], canvas);
}
