// GameplayTweaks feature module: GitHub #3 wagon-team stamina and HUD.
//
// A draft vehicle's harness horses are not the player's mount, so Rockstar's
// _SHOW_HORSE_CORES(bool) cannot point the stock horse meters at them.
// The locally installed Hardcore Stamina reference establishes the intended
// circular meter proportions. Directly drawing Rockstar's rpg_meter masks is
// not equivalent to the reference mod's HUD path: live tests proved those
// masks become opaque white squares through DRAW_SPRITE. Use the project's
// alpha-backed copies of that ring geometry instead, and
// obtain the coach glyph from its actual `blips` dictionary.

namespace WagonStamina {

static constexpr int kMaximumDraftHorses = 6;
static constexpr float kReferenceWidth = 1920.0f;
static constexpr float kReferenceHeight = 1080.0f;

// From Lexer's 2048x1152 extended-minimap capture, projected onto the same
// centered 1920x1080 reference canvas used by fortification_hud.cpp.  This is
// the vanilla horse Stamina position; Hardcore Stamina's default (140, 927)
// sits elsewhere and is deliberately not copied.
static constexpr float kHorseStaminaX = 344.06f;
static constexpr float kHorseStaminaY = 723.75f;

// Hardcore Stamina's 242x430 ten-thousandths are a square on a 16:9 canvas:
// 242/10000 of screen width == 430/10000 of screen height (~46.5 px at 1080p).
static constexpr float kMeterWidth = 0.0242f;
static constexpr float kMeterHeight = 0.0430f;
static constexpr float kCoreFloorFraction = 0.10f;
static constexpr char kMeterDictionary[] = "generic_textures";
static constexpr char kMeterTexturePrefix[] = "lex_fortification_meter_";
static constexpr char kBlipDictionary[] = "blips";

struct DraftHorseState {
	Ped horse = 0;
	float target = -1.0f;
	int protectedCore = -1;
};

static DraftHorseState g_horses[kMaximumDraftHorses];
static Vehicle g_vehicle = 0;
static DWORD g_lastFrame = 0;

static void resetHorse(DraftHorseState& state) {
	state = {};
	state.target = -1.0f;
	state.protectedCore = -1;
}

static void resetTeam() {
	for (DraftHorseState& state : g_horses) resetHorse(state);
	g_vehicle = 0;
	g_lastFrame = 0;
}

static bool validHorse(Ped horse) {
	return horse && ENTITY::DOES_ENTITY_EXIST(horse) &&
		!ENTITY::IS_ENTITY_DEAD(horse);
}

static bool referenceCanvas(float& x, float& y) {
	int width = 0, height = 0;
	GRAPHICS::GET_SCREEN_RESOLUTION(&width, &height);
	if (width <= 0 || height <= 0) return false;
	const float scale = (float)height / kReferenceHeight;
	const float originX = ((float)width - kReferenceWidth * scale) * 0.5f;
	x = (originX + kHorseStaminaX * scale) / (float)width;
	y = (kHorseStaminaY * scale) / (float)height;
	return true;
}

static bool hudMayRender(bool gameplayLocked) {
	if (gameplayLocked || HUD::IS_PAUSE_MENU_ACTIVE() || HUD::IS_HUD_HIDDEN() ||
		HUD::IS_RADAR_HIDDEN() || CAM::IS_CINEMATIC_CAM_RENDERING()) return false;
	return true;
}

static void drawMeter(float staminaFraction) {
	float x = 0.0f, y = 0.0f;
	if (!referenceCanvas(x, y)) return;
	if (!invoke<BOOL>(0x54D6900929CCF162, kMeterDictionary)) {
		invoke<Void>(0xC1BA29DF5631B0F8, kMeterDictionary, FALSE);
		return;
	}
	if (!invoke<BOOL>(0x54D6900929CCF162, kBlipDictionary))
		invoke<Void>(0xC1BA29DF5631B0F8, kBlipDictionary, FALSE);

	const int percent = (std::max)(0, (std::min)(99,
		(int)std::lround(staminaFraction * 99.0f)));
	char fillTexture[48] = {};
	sprintf_s(fillTexture, "%s%d", kMeterTexturePrefix, percent);

	// These DXT5 sprites contain only the anti-aliased ring in alpha. The full
	// ring supplies the subdued vanilla track and the partial ring is the live
	// outer-Stamina fill; neither can cover the HUD with a square.
	GRAPHICS::DRAW_SPRITE(kMeterDictionary, "lex_fortification_meter_99", x, y,
		kMeterWidth, kMeterHeight, 0.0f, 35, 35, 35, 235, FALSE);
	if (percent > 0)
		GRAPHICS::DRAW_SPRITE(kMeterDictionary, fillTexture, x, y,
			kMeterWidth, kMeterHeight, 0.0f, 229, 229, 229, 255, FALSE);

	// BLIP_PLAYER_COACH belongs to `blips`, not `rpg_textures`. Skip the glyph
	// while that dictionary streams instead of asking DRAW_SPRITE for a missing
	// texture and producing another placeholder square.
	if (invoke<BOOL>(0x54D6900929CCF162, kBlipDictionary))
		GRAPHICS::DRAW_SPRITE(kBlipDictionary, "BLIP_PLAYER_COACH", x, y,
			kMeterWidth * 0.52f, kMeterHeight * 0.52f, 0.0f,
			255, 255, 255, 255, FALSE);
}

static int collectTeam(Vehicle wagon, Ped (&team)[kMaximumDraftHorses]) {
	int count = 0;
	for (int slot = 0; slot < kMaximumDraftHorses; ++slot) {
		const Ped horse = GET_DRAFT_HORSE(wagon, slot);
		if (validHorse(horse)) team[count++] = horse;
	}
	return count;
}

static DraftHorseState& stateFor(Ped horse, int fallbackSlot) {
	for (DraftHorseState& state : g_horses)
		if (state.horse == horse) return state;
	DraftHorseState& state = g_horses[fallbackSlot];
	resetHorse(state);
	state.horse = horse;
	return state;
}

static void drainHorse(DraftHorseState& state, float drain, float& fraction) {
	const float maximum = GET_PED_MAX_STAMINA(state.horse);
	float current = GET_PED_STAMINA(state.horse);
	if (!(maximum > 0.0f) || !std::isfinite(maximum) || !std::isfinite(current))
		return;

	// Own a monotonically decreasing target, as movement.cpp does.  A plain
	// negative native call loses to Rockstar's simultaneous idle regeneration.
	if (state.target < 0.0f || fabsf(current - state.target) > maximum * 0.35f)
		state.target = current;
	else if (current < state.target)
		state.target = current; // retain any stronger native exertion
	state.target = (std::max)(0.0f, state.target - drain);
	const float delta = state.target - GET_PED_STAMINA(state.horse);
	if (delta < -0.005f)
		invoke<BOOL>(0xC3D4B754C0E86B9E, state.horse, delta); // _CHANGE_PED_STAMINA

	current = GET_PED_STAMINA(state.horse);
	fraction = (std::min)(fraction, (std::max)(0.0f,
		(std::min)(1.0f, current / maximum)));

	// Wagon exertion consumes the outer bar, never the Stamina Core.  Also close
	// Rockstar's reserve spill for these non-owned harness horses when their bar
	// reaches the same visual floor used by NoReserveCores.
	const int liveCore = GET_CORE(state.horse, 1);
	if (current > maximum * kCoreFloorFraction || state.protectedCore < 0)
		state.protectedCore = liveCore;
	else if (liveCore < state.protectedCore)
		SET_HORSE_CORE(state.horse, 1, state.protectedCore);
}

} // namespace WagonStamina

// Integration entry point.  Replaces the legacy one-second WagonCores loop in
// script.cpp; call every frame after `ped`, `locked`, and hot-reloaded settings
// are known. DrainPerSecond now means real outer-Stamina points per real second.
static void updateWagonStamina(Ped ped, bool gameplayLocked, bool enabled,
	float drainPerSecond, float minimumSpeed, DWORD now) {
	using namespace WagonStamina;
	if (!enabled || !ped) { resetTeam(); return; }

	const Vehicle wagon = GET_VEHICLE(ped);
	if (!wagon || !IS_DRAFT(wagon)) { resetTeam(); return; }
	Ped team[kMaximumDraftHorses] = {};
	const int count = collectTeam(wagon, team);
	if (count == 0) { resetTeam(); return; }

	if (g_vehicle != wagon) {
		resetTeam();
		g_vehicle = wagon;
	}
	const float dt = g_lastFrame ?
		(std::min)(0.25f, (float)(now - g_lastFrame) / 1000.0f) : 0.0f;
	g_lastFrame = now;
	const bool moving = ENTITY_SPEED(wagon) >= (std::max)(0.0f, minimumSpeed);
	const float drain = moving ? (std::max)(0.0f, drainPerSecond) * dt : 0.0f;

	float worstFraction = 1.0f;
	for (int i = 0; i < count; ++i) {
		DraftHorseState& state = stateFor(team[i], i);
		drainHorse(state, drain, worstFraction);
	}
	if (hudMayRender(gameplayLocked)) drawMeter(worstFraction);
}
