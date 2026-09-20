// GameplayTweaks feature module: #59 regular Story binocular optics evidence.
//
// Rockstar's binoculars script accepts only WEAPON_KIT_BINOCULARS. The earlier
// imported Online item could appear in the wheel but selecting it could not
// enter that script. Zoom is therefore retuned on the regular component that
// Story actually consumes. This module records the rendered FOV/zoom factor of
// the working regular-binocular path; it does not grant or advertise the dead
// Online item.

namespace BinocularOptics {

static DWORD g_nextOpticsSampleAt = 0;
static DWORD g_nextMaskHeartbeatAt = 0;
static DWORD g_nextMaskRequestAt = 0;
static float g_lastRenderedFov = -1.0f;
static float g_lastZoomFactor = -1.0f;
static bool g_maskDictionaryRequested = false;

static constexpr const char* kMaskDictionary = "lex_binocular_mask";
static constexpr const char* kMaskTexture = "lex_binocular_mask";

static void drawZoomReadout(float renderedFov, float zoomFactor) {
	if (!g_binocularZoomReadout) return;
	char text[160] = {};
	const float magnification = renderedFov > 0.01f ? 50.0f / renderedFov : 0.0f;
	sprintf_s(text,
		"Native zoom %.2fx   rendered FOV %.2f deg   level %.2f",
		magnification, renderedFov, zoomFactor);
	drawReconText(text, 0.5f, 0.925f);
}

static void logOptics(float renderedFov, float zoomFactor) {
	std::ostringstream log;
	log << "#59 regular optics"
		<< " renderedFov=" << renderedFov
		<< " zoomFactor=" << zoomFactor;
	gtLog("binoculars", GT_TRACE, log.str());
}

static void releaseMaskDictionary(const char* reason) {
	if (!g_maskDictionaryRequested) return;
	TXD::SET_STREAMED_TEXTURE_DICT_AS_NO_LONGER_NEEDED(kMaskDictionary);
	g_maskDictionaryRequested = false;
	g_nextMaskRequestAt = 0;
	gtLog("binoculars", GT_INFO, std::string("#143 raster mask released reason=") +
		(reason ? reason : "unknown"));
}

static bool ensureMaskDictionary(DWORD now) {
	if (TXD::HAS_STREAMED_TEXTURE_DICT_LOADED(kMaskDictionary)) return true;
	if (!g_maskDictionaryRequested || now >= g_nextMaskRequestAt) {
		TXD::REQUEST_STREAMED_TEXTURE_DICT(kMaskDictionary, FALSE);
		g_maskDictionaryRequested = true;
		g_nextMaskRequestAt = now + 500;
		gtLog("binoculars", GT_TRACE,
			"#143 raster mask dictionary requested loaded=0");
	}
	return false;
}

static void drawMask(float scale, float opacity) {
	const int alpha = static_cast<int>(opacity * 255.0f + 0.5f);
	if (alpha <= 0) return;

	// The raster owns the curved edge. These four rectangles only fill the
	// straight space outside a mask scaled below the full viewport; they do not
	// approximate either lens and cannot create the old banded staircase.
	if (scale < 1.0f) {
		const float margin = (1.0f - scale) * 0.5f;
		GRAPHICS::DRAW_RECT(0.5f, margin * 0.5f, 1.0f, margin, 0, 0, 0, alpha, false, false);
		GRAPHICS::DRAW_RECT(0.5f, 1.0f - margin * 0.5f, 1.0f, margin, 0, 0, 0, alpha, false, false);
		GRAPHICS::DRAW_RECT(margin * 0.5f, 0.5f, margin, scale, 0, 0, 0, alpha, false, false);
		GRAPHICS::DRAW_RECT(1.0f - margin * 0.5f, 0.5f, margin, scale, 0, 0, 0, alpha, false, false);
	}
	GRAPHICS::DRAW_SPRITE(kMaskDictionary, kMaskTexture, 0.5f, 0.5f,
		scale, scale, 0.0f, 255, 255, 255, alpha, false);
}

} // namespace BinocularOptics

// Integration entry point retained under its registered name. Sampling only
// while the regular kit owns the real first-person aim camera distinguishes
// native zoom stages from ordinary gameplay-camera movement.
static void updateImprovedBinocularAccess(Ped ped, DWORD now) {
	using namespace BinocularOptics;
	if (!ped || GET_CURRENT_WEAPON(ped) != joaat("WEAPON_KIT_BINOCULARS")) {
		releaseMaskDictionary("regular_binocular_not_equipped");
		return;
	}
	const bool opticsReady = CAM::IS_FIRST_PERSON_AIM_CAM_ACTIVE() &&
		(!g_binocularsModeEngaged || g_binocularsActive);
	if (!g_binocularMaskEnabled || !opticsReady) {
		releaseMaskDictionary(!g_binocularMaskEnabled ? "disabled" : "optics_not_ready");
		return;
	}

	const bool maskLoaded = ensureMaskDictionary(now);
	if (now >= g_nextMaskHeartbeatAt) {
		g_nextMaskHeartbeatAt = now + 5000;
		std::ostringstream heartbeat;
		heartbeat << "#143 raster mask heartbeat loaded=" << (maskLoaded ? 1 : 0)
			<< " scale=" << g_binocularMaskScale
			<< " opacity=" << g_binocularMaskOpacity;
		gtLog("binoculars", GT_INFO, heartbeat.str());
	}

	const float renderedFov = CAM::GET_FINAL_RENDERED_CAM_FOV();
	const float zoomFactor = CAM::GET_FIRST_PERSON_AIM_CAM_ZOOM_FACTOR();
	if (maskLoaded) drawMask(g_binocularMaskScale, g_binocularMaskOpacity);
	drawZoomReadout(renderedFov, zoomFactor);

	if (now < g_nextOpticsSampleAt) return;
	g_nextOpticsSampleAt = now + 100;
	if (g_lastRenderedFov >= 0.0f &&
		fabsf(renderedFov - g_lastRenderedFov) < 0.01f &&
		fabsf(zoomFactor - g_lastZoomFactor) < 0.01f) return;
	g_lastRenderedFov = renderedFov;
	g_lastZoomFactor = zoomFactor;
	logOptics(renderedFov, zoomFactor);
}
