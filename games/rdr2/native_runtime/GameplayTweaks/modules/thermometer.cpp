// GitHub #148: a persistent ambient-temperature readout owned by the
// LEX_THERMOMETER inventory item.
//
// Rockstar's location/info popup reads _GET_TEMPERATURE_AT_COORDS, converts
// C to F with (C * 1.8) + 32 when _SHOULD_USE_METRIC_TEMPERATURE is false,
// then rounds to an integer (aguasdulces.c func_66 / func_120).  Keep those
// semantics, but draw only the temperature beneath the top-right watch line.
// Native reads are bounded to 1 Hz; only the frame-scoped text draw runs each
// update while the item is owned.

namespace Thermometer {

static constexpr DWORD kSampleIntervalMs = 1000;
static constexpr DWORD kHeartbeatIntervalMs = 30000;
static constexpr float kDefaultPositionXPercent = 95.8f;
static constexpr float kDefaultPositionYPercent = 10.5f;

static bool g_initialized = false;
static bool g_owned = false;
static bool g_metric = true;
static bool g_suppressed = true;
static int g_inventoryCount = 0;
static int g_degrees = 0;
static DWORD g_lastSampleAt = 0;
static DWORD g_lastHeartbeatAt = 0;
static float g_positionXPercent = kDefaultPositionXPercent;
static float g_positionYPercent = kDefaultPositionYPercent;

static float temperatureAt(const Vector3& position) {
	return invoke<float>(0xB98B78C3768AF6E0, position.x, position.y, position.z);
}

static bool shouldUseMetricTemperature() {
	return invoke<BOOL>(0xFF4AAF3275BAAB4F) != 0;
}

static int roundLikeRockstar(float value) {
	return value >= 0.0f ? (int)std::floor(value + 0.5f) :
		(int)std::ceil(value - 0.5f);
}

static void logState(const char* event) {
	std::ostringstream line;
	line << event << " owned=" << (g_owned ? 1 : 0)
		<< " inventory=" << g_inventoryCount
		<< " suppressed=" << (g_suppressed ? 1 : 0)
		<< " position=" << g_positionXPercent << "," << g_positionYPercent;
	if (g_owned) line << " temperature=" << g_degrees << (g_metric ? "C" : "F");
	gtLog("thermometer", GT_INFO, line.str());
}

static void sample(Ped ped, DWORD now) {
	g_positionXPercent = (std::max)(0.0f, (std::min)(100.0f,
		readF("Thermometer", "PositionXPercent", kDefaultPositionXPercent)));
	g_positionYPercent = (std::max)(0.0f, (std::min)(100.0f,
		readF("Thermometer", "PositionYPercent", kDefaultPositionYPercent)));
	const bool wasOwned = g_owned;
	g_inventoryCount = (std::max)(0, INVENTORY_ITEM_COUNT(joaat("LEX_THERMOMETER")));
	g_owned = g_inventoryCount > 0;
	if (g_owned && ped) {
		const Vector3 position = ENTITY_COORDS(ped);
		float value = temperatureAt(position);
		g_metric = shouldUseMetricTemperature();
		if (!g_metric) value = value * 1.8f + 32.0f;
		g_degrees = roundLikeRockstar(value);
	}
	g_lastSampleAt = now;
	if (!g_initialized || wasOwned != g_owned) logState(g_owned ? "display-on" : "display-off");
	g_initialized = true;
}

static void draw() {
	char markup[256] = {};
	// Scaleform RIGHTMARGIN is measured inward from the right edge. Convert the
	// requested screen X position to that distance; 100% therefore means 0 px.
	const int rightMargin =
		(int)(((100.0f - g_positionXPercent) / 100.0f) * 1920.0f);
	sprintf_s(markup,
		"<TEXTFORMAT RIGHTMARGIN='%d'><P ALIGN='Right'><FONT FACE='$body' "
		"LETTERSPACING='0' SIZE='20'>~s~%d&#176;%c</FONT></P></TEXTFORMAT>",
		rightMargin, g_degrees, g_metric ? 'C' : 'F');
	HUD::_SET_TEXT_COLOR(245, 245, 245, 235);
	HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, 210);
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", markup),
		0.0f, g_positionYPercent / 100.0f);
}

// suppressed should be true for death, scripted/gameplay locks and protected
// post-office UI.  Sampling continues while suppressed so ownership changes
// and the first post-lock frame are current; rendering does not.
static void update(Ped ped, DWORD now, bool suppressed) {
	g_suppressed = suppressed || !ped;
	if (!g_initialized || now - g_lastSampleAt >= kSampleIntervalMs)
		sample(ped, now);
	if (g_owned && !g_suppressed) draw();
	if (!g_lastHeartbeatAt || now - g_lastHeartbeatAt >= kHeartbeatIntervalMs) {
		logState("heartbeat");
		g_lastHeartbeatAt = now;
	}
}

} // namespace Thermometer
