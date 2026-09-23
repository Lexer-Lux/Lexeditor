// GitHub #147: owning the functional pocket watch exposes the game clock as
// persistent bottom-right HUD information. This is read/draw-only: ownership is
// polled at a bounded cadence and no inventory or clock state is changed.

namespace PocketwatchTime {

static constexpr DWORD kOwnershipPollMs = 2000;
static constexpr DWORD kSettingsPollMs = 2000;
static constexpr DWORD kHeartbeatMs = 30000;
static constexpr DWORD kHudFadeMs = 250;
static constexpr int kTextAlpha = 235;
static constexpr int kShadowAlpha = 210;
static constexpr float kDefaultPositionXPercent = 96.0f;
static constexpr float kDefaultPositionYPercent = 92.83f;
static constexpr int kDefaultTextSize = 24;
static constexpr int kMinimumTextSize = 12;
static constexpr int kMaximumTextSize = 64;
static constexpr const char* kDefaultFontFace = "body1";

static Hash g_pocketwatchItem = 0;
static DWORD g_lastOwnershipPollAt = 0;
static DWORD g_lastSettingsPollAt = 0;
static DWORD g_lastHeartbeatAt = 0;
static int g_textSize = kDefaultTextSize;
static char g_fontFace[32] = "body1";
static float g_positionXPercent = kDefaultPositionXPercent;
static float g_positionYPercent = kDefaultPositionYPercent;
static bool g_owned = false;
static bool g_ownershipKnown = false;
static float g_hudAlpha = 0.0f;
static DWORD g_lastHudFadeAt = 0;

static void logState(const char* event, Ped ped, bool gameplayLocked) {
	std::ostringstream line;
	line << event << " owned=" << (g_owned ? 1 : 0)
		<< " known=" << (g_ownershipKnown ? 1 : 0)
		<< " ped=" << ped << " locked=" << (gameplayLocked ? 1 : 0)
		<< " text_size=" << g_textSize
		<< " font=" << g_fontFace
		<< " position=" << g_positionXPercent << "," << g_positionYPercent
		<< " inventory_poll_ms=" << kOwnershipPollMs
		<< " settings_poll_ms=" << kSettingsPollMs;
	gtLog("pocketwatch-time", GT_INFO, line.str());
}

static bool validFontFace(const char* value) {
	static constexpr const char* kFaces[] = {"body1", "FixedWidthNumbers", "catalog2", "Font5", "title"};
	for (const char* face : kFaces) if (std::strcmp(value, face) == 0) return true;
	return false;
}

static void loadSettings(DWORD now) {
	if (g_lastSettingsPollAt != 0 &&
		now - g_lastSettingsPollAt < kSettingsPollMs) return;
	g_lastSettingsPollAt = now;
	char requestedFont[32] = {};
	GetPrivateProfileStringA("Pocketwatch", "FontFace", kDefaultFontFace,
		requestedFont, sizeof(requestedFont), g_iniPath.c_str());
	const char* validatedFont = validFontFace(requestedFont) ? requestedFont : kDefaultFontFace;
	const int requested = GetPrivateProfileIntA("Pocketwatch", "TextSize",
		kDefaultTextSize, g_iniPath.c_str());
	const int validated = (std::max)(kMinimumTextSize,
		(std::min)(kMaximumTextSize, requested));
	const float requestedX = readF("Pocketwatch", "PositionXPercent",
		kDefaultPositionXPercent);
	const float requestedY = readF("Pocketwatch", "PositionYPercent",
		kDefaultPositionYPercent);
	const float validatedX = (std::max)(0.0f, (std::min)(100.0f, requestedX));
	const float validatedY = (std::max)(0.0f, (std::min)(100.0f, requestedY));
	if (validated == g_textSize && validatedX == g_positionXPercent &&
		validatedY == g_positionYPercent && std::strcmp(validatedFont, g_fontFace) == 0) return;
	g_textSize = validated;
	strcpy_s(g_fontFace, validatedFont);
	g_positionXPercent = validatedX;
	g_positionYPercent = validatedY;
	std::ostringstream line;
	line << "settings changed text_size=" << g_textSize
		<< " font=" << g_fontFace
		<< " requested=" << requested
		<< " position=" << g_positionXPercent << "," << g_positionYPercent
		<< " requested_position=" << requestedX << "," << requestedY
		<< " reload_ms=" << kSettingsPollMs;
	gtLog("pocketwatch-time", GT_INFO, line.str());
}

static void pollOwnership(Ped ped, DWORD now, bool gameplayLocked) {
	if (!ped || gameplayLocked) return;
	if (g_lastOwnershipPollAt != 0 &&
		now - g_lastOwnershipPollAt < kOwnershipPollMs) return;
	g_lastOwnershipPollAt = now;

	const int count = INVENTORY_ITEM_COUNT(g_pocketwatchItem);
	const bool owned = count > 0;
	if (!g_ownershipKnown || owned != g_owned) {
		g_owned = owned;
		g_ownershipKnown = true;
		std::ostringstream line;
		line << "ownership changed owned=" << (g_owned ? 1 : 0)
			<< " count=" << count << " item=KIT_PLAYER_POCKETWATCH";
		gtLog("pocketwatch-time", GT_INFO, line.str());
	}
}

static bool hardSuppressed(Ped ped, bool gameplayLocked) {
	if (!g_owned || !ped || gameplayLocked || SCREEN_FADED_OUT()) return true;
	if (HUD::IS_PAUSE_MENU_ACTIVE()) return true;
	if (CAM::IS_CINEMATIC_CAM_RENDERING()) return true;
	return false;
}

static int updateHudAlpha(Ped ped, DWORD now, bool gameplayLocked) {
	if (hardSuppressed(ped, gameplayLocked)) {
		g_hudAlpha = 0.0f;
		g_lastHudFadeAt = now;
		return 0;
	}

	// IS_HUD_HIDDEN only reflects the global HUD switch. RDR2's ordinary
	// auto-hide/show cycle is observable through the live radar state, so use
	// both as the visibility target and keep drawing while our alpha decays.
	const bool hudVisible = !HUD::IS_HUD_HIDDEN() && !HUD::IS_RADAR_HIDDEN();
	if (g_lastHudFadeAt == 0) g_lastHudFadeAt = now;
	const DWORD elapsed = now - g_lastHudFadeAt;
	g_lastHudFadeAt = now;
	const float boundedElapsed = (float)(std::min)(elapsed, kHudFadeMs);
	const float step = (float)kTextAlpha * boundedElapsed / (float)kHudFadeMs;
	if (hudVisible)
		g_hudAlpha = (std::min)((float)kTextAlpha, g_hudAlpha + step);
	else
		g_hudAlpha = (std::max)(0.0f, g_hudAlpha - step);
	return (int)(g_hudAlpha + 0.5f);
}

static void drawClock(int alpha) {
	const int hour24 = CLOCK_HOUR();
	const int minute = CLOCK_MINUTE();
	const bool afternoon = hour24 >= 12;
	int hour12 = hour24 % 12;
	if (hour12 == 0) hour12 = 12;

	char time[24] = {};
	sprintf_s(time, "%d:%02d %s", hour12, minute, afternoon ? "PM" : "AM");
	char markup[256] = {};
	// Scaleform RIGHTMARGIN is measured inward from the right edge. Convert the
	// requested screen X position to that distance; 100% therefore means 0 px.
	const int rightMargin =
		(int)(((100.0f - g_positionXPercent) / 100.0f) * 1920.0f);
	const float drawY = g_positionYPercent / 100.0f;
	sprintf_s(markup,
		"<TEXTFORMAT RIGHTMARGIN='%d'><P ALIGN='Right'><FONT FACE='$%s' "
		"LETTERSPACING='0' SIZE='%d'>~s~%s</FONT></P></TEXTFORMAT>",
		rightMargin, g_fontFace, g_textSize, time);

	HUD::_SET_TEXT_COLOR(245, 242, 234, alpha);
	const int shadowAlpha = (kShadowAlpha * alpha) / kTextAlpha;
	HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, shadowAlpha);
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", markup),
		0.0f, drawY);
}

} // namespace PocketwatchTime

static void initializePocketwatchTime() {
	using namespace PocketwatchTime;
	g_pocketwatchItem = joaat("KIT_PLAYER_POCKETWATCH");
	g_lastOwnershipPollAt = 0;
	g_lastSettingsPollAt = 0;
	g_lastHeartbeatAt = 0;
	g_textSize = kDefaultTextSize;
	strcpy_s(g_fontFace, kDefaultFontFace);
	g_positionXPercent = kDefaultPositionXPercent;
	g_positionYPercent = kDefaultPositionYPercent;
	g_owned = false;
	g_ownershipKnown = false;
	g_hudAlpha = 0.0f;
	g_lastHudFadeAt = 0;
	gtLog("pocketwatch-time", GT_INFO,
		"initialized item=KIT_PLAYER_POCKETWATCH draw=bottom-right format=12-hour");
}

// Integration entry point: call once per frame with the existing player ped,
// monotonic tick, and shared gameplay lock. Only the text draw is per-frame;
// the inventory native is bounded to one call every two seconds.
static void updatePocketwatchTime(Ped ped, DWORD now, bool gameplayLocked) {
	using namespace PocketwatchTime;
	loadSettings(now);
	pollOwnership(ped, now, gameplayLocked);

	if (g_lastHeartbeatAt == 0 || now - g_lastHeartbeatAt >= kHeartbeatMs) {
		g_lastHeartbeatAt = now;
		logState("idle heartbeat", ped, gameplayLocked);
	}
	const int alpha = updateHudAlpha(ped, now, gameplayLocked);
	if (alpha > 0) drawClock(alpha);
}
