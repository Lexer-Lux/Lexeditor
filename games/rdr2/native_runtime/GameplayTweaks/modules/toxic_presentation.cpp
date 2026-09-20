// GitHub #102: vanilla-asset Toxic presentation.
//
// The existing toxicity owner sets SA_POISONED and drains only the outer Health
// bar. This module adds presentation only: it never reads or writes a core.

static const char* const kToxicPostFx = "MP_MoonshineToxic";
static const char* const kArthurToxicDict =
	"mech_loco_m@character@arthur@fidgets@sick@normal@unarmed@big_cough";
static const char* const kArthurToxicClips[] = { "sick_a", "sick_b", "sick_c" };

struct ToxicPresentationState {
	bool active = false;
	bool ownsPostFx = false;
	DWORD nextPulseAt = 0;
	DWORD nextFidgetAt = 0;
	unsigned int fidgetIndex = 0;
};

static ToxicPresentationState g_toxicPresentation;

static DWORD toxicPresentationSettingMs(const char* key, int defaultSeconds,
	int minimumSeconds, int maximumSeconds) {
	const int configured = (int)GetPrivateProfileIntA(
		"Toxicity", key, defaultSeconds, g_iniPath.c_str());
	const int seconds = (std::max)(minimumSeconds,
		(std::min)(maximumSeconds, configured));
	return (DWORD)seconds * 1000u;
}

static void stopToxicPresentation() {
	if (g_toxicPresentation.ownsPostFx &&
		GRAPHICS::ANIMPOSTFX_IS_RUNNING(kToxicPostFx))
		GRAPHICS::ANIMPOSTFX_STOP(kToxicPostFx);
	g_toxicPresentation = {};
}

static bool canPlayArthurToxicFidget(Ped ped) {
	if (!ped || ENTITY::GET_ENTITY_MODEL(ped) != joaat("PLAYER_ZERO")) return false;
	if (PED::IS_PED_ON_MOUNT(ped) || PED::IS_PED_IN_ANY_VEHICLE(ped, FALSE) ||
		PED::IS_PED_RAGDOLL(ped) || PED::IS_PED_FALLING(ped) ||
		PED::IS_PED_IN_COMBAT(ped, 0)) return false;
	if (PLAYER::IS_PLAYER_FREE_AIMING(PLAYER::PLAYER_ID()) || CAM::IS_AIM_CAM_ACTIVE())
		return false;
	return true;
}

static void updateToxicPresentation(Ped ped, DWORD now) {
	if (!g_toxicityEnabled || !g_toxicActive || !ped ||
		PED::IS_PED_DEAD_OR_DYING(ped, TRUE)) {
		stopToxicPresentation();
		return;
	}

	const DWORD pulseInterval = toxicPresentationSettingMs(
		"PresentationPulseSeconds", 30, 10, 300);
	const DWORD fidgetInterval = toxicPresentationSettingMs(
		"PresentationFidgetSeconds", 90, 30, 600);
	const bool onset = !g_toxicPresentation.active;
	if (onset) {
		g_toxicPresentation.active = true;
		g_toxicPresentation.nextPulseAt = now;
		g_toxicPresentation.nextFidgetAt = now + 1500;
	}

	if ((int)(now - g_toxicPresentation.nextPulseAt) >= 0) {
		// Timed playback supplies the requested fader without monopolizing the
		// screen for the entire multi-hour condition. Repeating it makes ongoing
		// poisoning visible instead of reducing Toxic to a HUD skull.
		GRAPHICS::_ANIMPOSTFX_PLAY_TIMED(kToxicPostFx, 4500);
		g_toxicPresentation.ownsPostFx = true;
		g_toxicPresentation.nextPulseAt = now + pulseInterval;
	}

	if ((int)(now - g_toxicPresentation.nextFidgetAt) < 0 ||
		!canPlayArthurToxicFidget(ped)) return;
	if (!STREAMING::HAS_ANIM_DICT_LOADED(kArthurToxicDict)) {
		STREAMING::REQUEST_ANIM_DICT(kArthurToxicDict);
		return;
	}

	const char* clip = kArthurToxicClips[
		g_toxicPresentation.fidgetIndex++ % _countof(kArthurToxicClips)];
	// Secondary/upper-body playback preserves locomotion and does not seize the
	// player the way a full vomiting scenario would. Combat, aiming, mounts,
	// vehicles, falls, and ragdoll are explicitly excluded above.
	TASK::TASK_PLAY_ANIM(ped, kArthurToxicDict, clip, 4.0f, -4.0f, 3200,
		48, 0.0f, FALSE, 0, FALSE, 0, FALSE);
	g_toxicPresentation.nextFidgetAt = now + fidgetInterval;
}
