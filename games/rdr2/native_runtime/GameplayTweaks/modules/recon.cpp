// GameplayTweaks feature module: Binocular recon tagging, plant/object discovery, markers, prompts, and hostile-blip suppression.
// Included by script.cpp into the single ScriptHook translation unit.

// #126: adapter so existing `log << "field=" << value` code writes to the one
// unified log without a single field being restated or renamed. Each '\n' in
// the stream ends one record, which is emitted immediately via gtLog(), so
// ordering against other subsystems stays exact. Guarded because several
// modules carry this same block into the one translation unit.
#ifndef GT_LOG_STREAM_DEFINED
#define GT_LOG_STREAM_DEFINED
struct GtLogStream {
	GtLogStream(const char* subsystem, GtLogLevel level)
		: subsystem_(subsystem), level_(level) {}
	~GtLogStream() { drain(true); }
	template <class T> GtLogStream& operator<<(const T& value) {
		buffer_ << value; drain(false); return *this;
	}
	GtLogStream& operator<<(std::ostream& (*manip)(std::ostream&)) {
		buffer_ << manip; drain(false); return *this;
	}
	GtLogStream& operator<<(std::ios_base& (*manip)(std::ios_base&)) {
		buffer_ << manip; drain(false); return *this;
	}
	// Contextual conversion only, so the legacy `if (log)` guards still compile
	// and no built-in operator<< can hijack an insertion.
	explicit operator bool() const { return true; }
private:
	void drain(bool final) {
		pending_ += buffer_.str();
		buffer_.str(std::string()); // clears the buffer, keeps hex/dec/precision
		size_t nl;
		while ((nl = pending_.find('\n')) != std::string::npos) {
			std::string line = pending_.substr(0, nl);
			pending_.erase(0, nl + 1);
			if (!line.empty() && line[line.size() - 1] == '\r') line.erase(line.size() - 1);
			if (!line.empty()) gtLog(subsystem_, level_, line);
		}
		if (final && !pending_.empty()) {
			gtLog(subsystem_, level_, pending_);
			pending_.clear();
		}
	}
	const char* subsystem_;
	GtLogLevel level_;
	std::ostringstream buffer_;
	std::string pending_;
};
#endif


// ---- Binocular recon tagging ------------------------------------------------
// Marking requires an actual line of sight through the binocular camera. Once
// marked, the marker intentionally uses world-to-HUD projection without an LOS
// check, so it remains usable behind cover without pretending to render an
// x-ray model.
enum class ReconDisposition { Enemy, Neutral, Ally };
enum class ReconHumanRole { Generic, Law, BountyHunter };
struct ReconTarget {
	Ped ped = 0;
	Blip blip = 0;
	ReconDisposition disposition = ReconDisposition::Neutral;
	DWORD markedAt = 0;
	bool playerHorse = false;
	// A tagged hostile must not flicker back to neutral when the game's transient
	// combat task drops at range. Explicit friendly relationship state may still
	// clear the latch, so a genuinely changed relationship is reflected.
	bool enemyLatched = false;
	int blipRecreateCount = 0;
};
static std::vector<ReconTarget> g_reconTargets;
struct ReconCompendiumStudy {
	Ped ped = 0;
	Hash model = 0;
	Hash animalType = 0;
	Hash discoverableName = 0;
	Hash discoverableType = 0;
	DWORD readyAt = 0;
	DWORD verifyAt = 0;
	bool writeIssued = false;
};
static std::vector<ReconCompendiumStudy> g_reconCompendiumStudies;
static void reconLog(const std::string& message);

// #96 A HARVESTABLE PLANT IS A SCENARIO POINT, NOT A MODEL, NOT A PED, NOT A
// PICKUP, AND NOT A SCRIPT OBJECT. THE OLD MODEL TABLE HERE WAS FABRICATED.
//
// The removed comment claimed every name in `kPlantModelNames` was "copied
// verbatim" out of a shipped model enumeration in
// `fm_mission_controller` / `net_gun_for_hire_offline`. Both claims are false
// and were checked, not assumed:
//   * Neither of those files exists in
//     `_downloads/RDR2-Decompiled-Scripts/script_rel/` at all. They are GTA
//     Online script names.
//   * Grepping the whole decompiled Story Mode corpus for each of the 41 names
//     ("THYME_P", "VIOSNWDRP_P", "S_VIOLETSNOWDROP01X", "S_GINSENG01X",
//     "MILKWEED_P", ...) returns ZERO hits, case-insensitive. The single
//     apparent hit for MILKWEED_P is the substring inside
//     "LEVDES_SPAWN_MILKWEED_PICKUP" (campfire_always.c:18367).
// So `isKnownPlantModel()` was comparing live model hashes against 41 hashes of
// invented strings, and could only ever return true by coincidence.
//
// WHAT A PLANT ACTUALLY IS. Rockstar ships one pick-up script per species,
// `herb_<species>.c` (49 files). They are byte-identical apart from one species
// index: `herb_creeping_thyme.c:287` calls `func_41(uParam0, 12)` and
// `herb_evergreen_huckleberry.c:287` calls `func_41(uParam0, 16)` - that diff is
// the ONLY difference between the two files Lexer named. The script's entry
// point takes a SCENARIO POINT id as its script parameter and never touches an
// entity handle for the plant:
//     herb_evergreen_huckleberry.c:48   Var0.f_6 = ScriptParam_0.f_1;
//     herb_evergreen_huckleberry.c:58   TASK::_DOES_SCENARIO_POINT_EXIST(ScriptParam_0.f_1)
//     herb_evergreen_huckleberry.c:62   TASK::_GET_SCENARIO_POINT_COORDS(ScriptParam_0.f_1, true)
// The complete native list used by that script contains no OBJECT:: native, no
// PICKUP native, and no GET_ENTITY_MODEL. The plant's visible mesh is map data
// hung off the scenario point; the harvest is driven entirely by the point.
//
// That is the whole answer to "why is it finnicky, and why can I tag creeping
// thyme but not evergreen huckleberry":
//   * A plant is not a ped, so the ped scan never sees it.
//   * A plant is not a script object, so the object-pool scan never sees it.
//   * The only path that ever worked was the camera shape-test, which returns
//     the map-geometry entity handle under the reticle. That is why tagging
//     succeeded at all, and why it felt random - it depended on the probe
//     landing on the mesh AND on the model hash coincidentally matching one of
//     41 invented hashes.
//
// THE SANCTIONED ENGINE PATH, which is also the answer to "rampage editor lets
// me spawn plants at will so there's clearly already a way of knowing what
// plants are". Scenario points are typed. Do not call the SDK's bulk
// `_GET_SCENARIO_POINT_CLOSE_TO_COORDS`: its undocumented out-buffer ABI
// overwrites this ScriptHook caller's stack. Query one known WB_ type at a time:
//     TASK::_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE 0xF533D68FF970D190
//     TASK::_GET_SCENARIO_POINT_TYPE            0xA92450B5AE687AAF natives.h:7394
//     TASK::_GET_SCENARIO_POINT_COORDS          0xA8452DD321607029 natives.h:7289
//     TASK::_DOES_SCENARIO_POINT_EXIST          0x841475AC96E794D1 natives.h:7284
//     TASK::_IS_SCENARIO_POINT_ACTIVE           0x0CC36D4156006509 natives.h:7386
//     TASK::_GET_ENTITY_SCENARIO_POINT_IS_ATTACHED_TO 0x7467165EE97D3C68 natives.h:7286
//
// THE TYPE TABLE BELOW IS SHIPPED, NOT INVENTED. Every `WB_*` name is a literal
// in Rockstar's own scenario-type enumeration, sitting in the same switch as
// WORLD_HUMAN_* and PROP_HUMAN_*: campfire_always.c:20560-20256 (e.g.
// "WB_BERRY_EVERGREEN_HUCKLEBERRY" at campfire_always.c:20168 and
// "WB_SPICE_CREEPING_THYME" at campfire_always.c:20256), duplicated in
// campfire_gang.c:23362 / 23450. That a WB_* name really is a scenario TYPE and
// not a label is proven by a live call site passing one straight to the
// find-by-type native: act_fishing06.c:43764 passes joaat("WB_GATOR_EGG_NEST")
// to TASK::_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE.
// The list is the complete WB_ harvestable set from that enumeration; it
// contains both species Lexer named, which the old model table did not.
static const char* const kPlantScenarioTypeNames[] = {
	// Berries.
	"WB_BERRY_BLACK_BERRY", "WB_BERRY_EVERGREEN_HUCKLEBERRY",
	"WB_BERRY_RED_RASPBERRY", "WB_BERRY_WINTERGREEN_BERRY",
	// Herbs.
	"WB_HERB_ALASKAN_GINSENG", "WB_HERB_AMERICAN_GINSENG",
	"WB_HERB_BLACK_CURRANT", "WB_HERB_BURDOCK_ROOT",
	"WB_HERB_BURDOCK_ROOT_SINGLE", "WB_HERB_DESERT_SAGE",
	"WB_HERB_ENGLISH_MACE", "WB_HERB_ENGLISH_MACE_SINGLE",
	"WB_HERB_GOLDEN_CURRANT", "WB_HERB_HUMMINGBIRD_SAGE",
	"WB_HERB_INDIAN_TOBACCO", "WB_HERB_MILKWEED", "WB_HERB_MILKWEED_SINGLE",
	"WB_HERB_OLEANDER_SAGE", "WB_HERB_OLEANDER_SAGE_SINGLE",
	"WB_HERB_PRAIRIE_POPPY", "WB_HERB_RED_SAGE", "WB_HERB_VANILLA_FLOWER",
	"WB_HERB_VIOLET_SNOWDROP", "WB_HERB_WILD_FEVERFEW", "WB_HERB_YARROW",
	"WB_HERB_YARROW_SINGLE",
	// Horse-restoring herbs.
	"WB_HORSE_HERB_COMMON_BULRUSH", "WB_HORSE_HERB_WILD_CARROTS",
	// Mushrooms.
	"WB_MUSHROOM_BAY_BOLETE", "WB_MUSHROOM_CHANTERELLES",
	"WB_MUSHROOM_PARASOL_MUSHROOM", "WB_MUSHROOM_RAMS_HEAD",
	// Spices.
	"WB_SPICE_CREEPING_THYME", "WB_SPICE_OREGANO", "WB_SPICE_WILD_MINT",
	// Orchids.
	"WB_ORCHID_ACUNAS_STAR", "WB_ORCHID_CIGAR", "WB_ORCHID_CLAMSHELL",
	"WB_ORCHID_DRAGONS_MOUTH", "WB_ORCHID_GHOST", "WB_ORCHID_LADY_OF_NIGHT",
	"WB_ORCHID_LADY_SLIPPER", "WB_ORCHID_MOCCASIN_FLOWER",
	"WB_ORCHID_NIGHT_SCENTED", "WB_ORCHID_QUEENS", "WB_ORCHID_RAT_TAIL",
	"WB_ORCHID_SPARROWS_EGG", "WB_ORCHID_SPIDER",
	// Exotic flowers.
	"WB_FLOWER_AGARITA", "WB_FLOWER_AGARITA_SINGLE",
	"WB_FLOWER_BITTERWEED", "WB_FLOWER_BITTERWEED_SINGLE",
	"WB_FLOWER_BLOOD_FLOWER", "WB_FLOWER_BLOOD_FLOWER_SINGLE",
	"WB_FLOWER_CARDINAL_FLOWER", "WB_FLOWER_CARDINAL_FLOWER_SINGLE",
	"WB_FLOWER_CHOCOLATE_DAISY", "WB_FLOWER_CHOCOLATE_DAISY_SINGLE",
	"WB_FLOWER_CREEK_PLUM", "WB_FLOWER_CREEK_PLUM_SINGLE",
	"WB_FLOWER_TEXAS_BLUE_BONNET", "WB_FLOWER_TEXAS_BLUE_BONNET_SINGLE",
	"WB_FLOWER_WILD_RHUBARB", "WB_FLOWER_WILD_RHUBARB_SINGLE",
	"WB_FLOWER_WISTERIA", "WB_FLOWER_WISTERIA_SINGLE"
};

// The reticle ray frequently resolves the visible entity attached to a plant
// rather than its scenario point. This is the complete unlooted visual-model
// set from Rockstar's extracted
// common_0_data/ai/looting/lootable_herbs.meta. Unlike the removed fabricated
// list, every name is checked by the #96 verifier against both that metadata
// and the extracted object catalog. LootedOnly models are deliberately absent.
static const char* const kPlantVisualModelNames[] = {
	"alaskanginseng_p", "blackcurrant_p", "bulrush_p", "burdock_p",
	"crowsgarlic_p", "desertsage_p", "engmace_p", "feverfew_p",
	"ginseng_p", "goldencurrant_p", "humbirdsage_p", "indtobacco_p",
	"milkweed_p", "orchid_v_p", "oregano_p", "orleander_p",
	"prariepoppy_p", "redsage_p", "s_gatoregg01x", "s_gatoreggnest01x",
	"s_inv_alaskanginseng01bx", "s_inv_alaskanginseng01cx", "s_inv_alaskanginseng01dx", "s_inv_alaskanginseng01x",
	"s_inv_baybolete", "s_inv_baybolete01bx", "s_inv_blackberry01x", "s_inv_blackcurrant01bx",
	"s_inv_blackcurrant01cx", "s_inv_blackcurrant01x", "s_inv_bloodflower01bx", "s_inv_bloodflower01cx",
	"s_inv_bloodflower01x", "s_inv_bulrush01bx", "s_inv_bulrush01cx", "s_inv_bulrush01dx",
	"s_inv_bulrush01x", "s_inv_burdock01bx", "s_inv_burdock01cx", "s_inv_burdock01dx",
	"s_inv_burdock01x", "s_inv_cardinalflw01bx", "s_inv_cardinalflw01cx", "s_inv_cardinalflw01dx",
	"s_inv_cardinalflw01x", "s_inv_chanterelles", "s_inv_chanterelles01bx", "s_inv_crowsgarlic01bx",
	"s_inv_crowsgarlic01cx", "s_inv_crowsgarlic01x", "s_inv_desertsage01bx", "s_inv_desertsage01cx",
	"s_inv_desertsage01dx", "s_inv_desertsage01ex", "s_inv_desertsage01x", "s_inv_engmace01bx",
	"s_inv_engmace01cx", "s_inv_engmace01dx", "s_inv_engmace01x", "s_inv_feverfew01bx",
	"s_inv_feverfew01cx", "s_inv_feverfew01dx", "s_inv_feverfew01x", "s_inv_ginseng01bx",
	"s_inv_ginseng01cx", "s_inv_ginseng01dx", "s_inv_ginseng01x", "s_inv_goldencurrant01bx",
	"s_inv_goldencurrant01cx", "s_inv_goldencurrant01x", "s_inv_huckleberry01x", "s_inv_humbirdsage01bx",
	"s_inv_humbirdsage01cx", "s_inv_humbirdsage01dx", "s_inv_humbirdsage01x", "s_inv_indtobacco01cx",
	"s_inv_indtobacco01dx", "s_inv_indtobacco01x", "s_inv_milkweed01bx", "s_inv_milkweed01cx",
	"s_inv_milkweed01dx", "s_inv_milkweed01x", "s_inv_orchid_acunastar_01x", "s_inv_orchid_cigar_01x",
	"s_inv_orchid_clam_01bx", "s_inv_orchid_clam_01x", "s_inv_orchid_dm_01x", "s_inv_orchid_ghost_01bx",
	"s_inv_orchid_ghost_01x", "s_inv_orchid_lnight_01bx", "s_inv_orchid_lnight_01x", "s_inv_orchid_ls_01x",
	"s_inv_orchid_mf_01x", "s_inv_orchid_nghtscnt_01x", "s_inv_orchid_q_01x", "s_inv_orchid_rattail_01x",
	"s_inv_orchid_se_01x", "s_inv_orchid_spider_01bx", "s_inv_orchid_spider_01x", "s_inv_orchid_v_01bx",
	"s_inv_orchid_v_01x", "s_inv_oregano01bx", "s_inv_oregano01cx", "s_inv_oregano01dx",
	"s_inv_oregano01x", "s_inv_orleander01bx", "s_inv_orleander01cx", "s_inv_orleander01dx",
	"s_inv_orleander01x", "s_inv_parasol", "s_inv_parasol01bx", "s_inv_prariepoppy01bx",
	"s_inv_prariepoppy01cx", "s_inv_prariepoppy01dx", "s_inv_prariepoppy01x", "s_inv_ramshead",
	"s_inv_ramshead01bx", "s_inv_raspberry01x", "s_inv_redsage01bx", "s_inv_redsage01cx",
	"s_inv_redsage01dx", "s_inv_redsage01x", "s_inv_rhubarb01bx", "s_inv_rhubarb01cx",
	"s_inv_rhubarb01dx", "s_inv_rhubarb01ex", "s_inv_rhubarb01x", "s_inv_saltbush01bx",
	"s_inv_saltbush01cx", "s_inv_saltbush01dx", "s_inv_saltbush01ex", "s_inv_saltbush01x",
	"s_inv_thyme01bx", "s_inv_thyme01cx", "s_inv_thyme01x", "s_inv_viosnwdrp01bx",
	"s_inv_viosnwdrp01cx", "s_inv_viosnwdrp01x", "s_inv_wildcarrot01bx", "s_inv_wildcarrot01cx",
	"s_inv_wildcarrot01dx", "s_inv_wildcarrot01x", "s_inv_wildmint01bx", "s_inv_wildmint01cx",
	"s_inv_wildmint01x", "s_inv_wintergreen01bx", "s_inv_wintergreen01x", "s_inv_yarrow01cx",
	"s_inv_yarrow01dx", "s_inv_yarrow01x", "thyme_p", "viosnwdrp_p",
	"wildcarrot_p", "wildmint_p"
};

// `g_plantModels` / `g_plantModelsLoaded` / `learnPlantModels` keep their names
// and signatures because they are declared and called from script.cpp, which
// this change does not own. The vector now holds scenario TYPE hashes.
static void loadPlantModels() {
	g_plantModels.clear();
	for (int i = 0; i < (int)_countof(kPlantScenarioTypeNames); ++i)
		g_plantModels.push_back(joaat(kPlantScenarioTypeNames[i]));
	g_plantModelsLoaded = true;
}

static bool isKnownPlantScenarioType(Hash scenarioType) {
	return std::find(g_plantModels.begin(), g_plantModels.end(), scenarioType) !=
		g_plantModels.end();
}

static bool isKnownPlantVisualModel(Hash model) {
	for (const char* name : kPlantVisualModelNames)
		if (model == joaat(name)) return true;
	return false;
}

static void learnPlantModels(Ped ped, DWORD now) {
	(void)ped;
	(void)now;
	if (!g_plantModelsLoaded) loadPlantModels();
}

// #113(d) TAGGING PLANTS.
// The scanner only ever looked at peds, so a plant could not be selected at
// all - it is not a person or an animal. Harvestable plants are PICKUP
// entities, so they must be found without inventing model names - which is the
// exact mistake that made the holster key, the tracers
// and the tag artwork silently do nothing. Anything the world offers as a
// pickup is taggable; the reticle and the study timer keep it deliberate.
struct ReconObjectTarget {
	Entity entity = 0;       // Preferred: validated reticle-hit plant visual.
	Hash model = 0;
	int scenarioPoint = 0;   // Safe typed-scenario fallback.
	Hash scenarioType = 0;
	Vector3 coords = {};
	Blip blip = 0;
	DWORD markedAt = 0;
};
static std::vector<ReconObjectTarget> g_reconObjectTargets;

static bool isReconObjectTagged(int scenarioPoint, Entity entity = 0) {
	for (const ReconObjectTarget& tag : g_reconObjectTargets)
		if ((entity && tag.entity == entity) ||
			(scenarioPoint && tag.scenarioPoint == scenarioPoint)) return true;
	return false;
}

// #96 diagnostic counters for one selection pass. A plant that is rejected must
// say WHY, and an idle heartbeat must prove the scan is running at all.
struct ReconPlantScanStats {
	int visualCandidates = 0;
	int visualModels = 0;
	int enumerated = 0;      // typed scenario points returned near the reticle
	int existing = 0;        // survived _DOES_SCENARIO_POINT_EXIST
	int typedPlant = 0;      // type hash matched the shipped WB_ table
	int inRange = 0;         // within g_reconMaxDistance
	int projected = 0;       // projected onto the screen
	int withinReticle = 0;   // inside the aim radius
	int radiusRejected = 0;  // projected, but outside the configured radius
	float nearestScreen = 999.0f;
	int alreadyTagged = 0;
	Hash nearestRejectedType = 0;
};

struct ReconPlantCandidate {
	Entity entity = 0;
	Hash model = 0;
	int scenarioPoint = 0;
	Hash scenarioType = 0;
	Vector3 coords = {};
	bool valid() const { return entity != 0 || scenarioPoint != 0; }
};

// The asynchronous reticle ray supplies the world position around which the
// type-specific plant query searches. It remains valid only briefly so a camera
// move cannot keep selecting a scenario point near an old reticle position.
static Vector3 g_reconReticleHit = {};
static bool g_reconReticleHitValid = false;
static DWORD g_reconReticleHitAt = 0;

static void reconLog(const std::string& message) {
	// The unified log stamps the tick itself.
	gtLog("recon", GT_INFO, message);
}

static float reconDistance(Vector3 a, Vector3 b) {
	const float dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
	return std::sqrt(dx * dx + dy * dy + dz * dz);
}

static Vector3 reconAnchor(Ped target) {
	Vector3 p = ENTITY_COORDS(target);
	// Anchor to the actual head bone. Model bounds are only a fallback for
	// unusual animal skeletons that do not expose the standard SKEL_HEAD tag.
	// THE OFFSET ARGUMENTS ARE IN BONE-LOCAL SPACE, NOT WORLD SPACE. The head
	// bone's local axes do not point at the sky, so raising the third argument
	// from 0.18 to 0.52 pushed the marker FORWARD/RIGHT of the target instead of
	// up. Take the bone position raw and add the clearance in world Z.
	Vector3 head = PED::GET_PED_BONE_COORDS(target, 21030, 0.0f, 0.0f, 0.0f);
	if (reconDistance(head, p) >= 0.15f && reconDistance(head, p) <= 6.0f) {
		return head;
	}
	Vector3 minimum = {}, maximum = {};
	MISC::GET_MODEL_DIMENSIONS(ENTITY::GET_ENTITY_MODEL(target), &minimum, &maximum);
	const float height = maximum.z - minimum.z;
	p.z += PED::IS_PED_HUMAN(target) ? 1.08f :
		(height >= 0.25f && height <= 6.0f ? maximum.z + 0.10f : 0.72f);
	return p;
}

struct ReconModelBounds {
	Vector3 minimum = {};
	Vector3 maximum = {};
};
static std::unordered_map<Hash, ReconModelBounds> g_reconModelBounds;

static ReconModelBounds reconBounds(Ped target) {
	const Hash model = ENTITY::GET_ENTITY_MODEL(target);
	auto found = g_reconModelBounds.find(model);
	if (found != g_reconModelBounds.end()) return found->second;
	ReconModelBounds bounds;
	MISC::GET_MODEL_DIMENSIONS(model, &bounds.minimum, &bounds.maximum);
	if (bounds.maximum.z - bounds.minimum.z < 0.05f ||
		bounds.maximum.z - bounds.minimum.z > 8.0f) {
		bounds.minimum = { -0.25f, -0.25f, 0.0f };
		bounds.maximum = { 0.25f, 0.25f, PED::IS_PED_HUMAN(target) ? 1.75f : 1.15f };
	}
	g_reconModelBounds[model] = bounds;
	return bounds;
}

static float reconProjectedExtent(Ped target) {
	const ReconModelBounds bounds = reconBounds(target);
	float minX = 1.0f, minY = 1.0f, maxX = 0.0f, maxY = 0.0f;
	int projected = 0;
	for (int xi = 0; xi < 2; ++xi) {
		for (int yi = 0; yi < 2; ++yi) {
			for (int zi = 0; zi < 2; ++zi) {
				const float lx = xi ? bounds.maximum.x : bounds.minimum.x;
				const float ly = yi ? bounds.maximum.y : bounds.minimum.y;
				const float lz = zi ? bounds.maximum.z : bounds.minimum.z;
				const Vector3 corner = ENTITY::GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(target, lx, ly, lz);
				float sx = 0.0f, sy = 0.0f;
				if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(corner.x, corner.y, corner.z, &sx, &sy))
					continue;
				minX = (std::min)(minX, (std::max)(0.0f, sx));
				maxX = (std::max)(maxX, (std::min)(1.0f, sx));
				minY = (std::min)(minY, (std::max)(0.0f, sy));
				maxY = (std::max)(maxY, (std::min)(1.0f, sy));
				++projected;
			}
		}
	}
	if (!projected || maxX <= minX || maxY <= minY) return 0.0f;
	// Square-root area preserves roughly the old "fraction of screen height"
	// scale while accounting continuously for width, orientation, distance/FOV,
	// and zoom. No animal-size categories or thresholds are involved.
	return std::sqrt((maxX - minX) * (maxY - minY));
}

static ReconDisposition reconDispositionFromObservation(int relation, bool inCombat) {
	if (inCombat || relation >= 4) return ReconDisposition::Enemy;
	if (relation >= 0 && relation <= 2) return ReconDisposition::Ally;
	return ReconDisposition::Neutral;
}

static ReconDisposition reconDispositionFor(Ped playerPed, Ped target) {
	const int relation = PED::GET_RELATIONSHIP_BETWEEN_PEDS(target, playerPed);
	return reconDispositionFromObservation(relation,
		PED::IS_PED_IN_COMBAT(target, playerPed) != 0);
}

static ReconHumanRole reconHumanRole(Ped target) {
	if (!target || !PED::IS_PED_HUMAN(target)) return ReconHumanRole::Generic;
	const Hash group = PED::GET_PED_RELATIONSHIP_GROUP_HASH(target);
	if (group == joaat("REL_COP")) return ReconHumanRole::Law;
	if (group == joaat("REL_BOUNTY_HUNTER")) return ReconHumanRole::BountyHunter;
	return ReconHumanRole::Generic;
}

static Hash reconBlipStyle(Ped target, ReconDisposition disposition) {
	const ReconHumanRole role = reconHumanRole(target);
	// #297: keep Rockstar's authored law/bounty styles. BLIP_STYLE_BOUNTY_HUNTER
	// inherits BLIP_STYLE_COP in blipdata.ymt, so both retain the game's own
	// wanted/search color transitions and conditional cop heading cone.
	if (role == ReconHumanRole::Law) return joaat("BLIP_STYLE_COP");
	if (role == ReconHumanRole::BountyHunter) return joaat("BLIP_STYLE_BOUNTY_HUNTER");
	switch (disposition) {
		case ReconDisposition::Enemy: return joaat("BLIP_STYLE_ENEMY");
		case ReconDisposition::Ally: return joaat("BLIP_STYLE_FRIENDLY_ON_RADAR");
		case ReconDisposition::Neutral: return joaat("DEFAULT");
	}
	return joaat("DEFAULT");
}

static float reconAnimalBlipScale(Ped target) {
	const ReconModelBounds bounds = reconBounds(target);
	const float width = (std::max)(0.05f, bounds.maximum.x - bounds.minimum.x);
	const float length = (std::max)(0.05f, bounds.maximum.y - bounds.minimum.y);
	const float height = (std::max)(0.05f, bounds.maximum.z - bounds.minimum.z);
	// Stable four-bucket scale from cached model volume. This separates tiny
	// birds/rats, rabbit/fox-sized animals, deer/wolves, and bear/bison/alligator
	// without a brittle hand-maintained species list or frame-to-frame jitter.
	const float characteristic = std::cbrt(width * length * height);
	if (characteristic < 0.35f) return 0.45f;
	if (characteristic < 0.80f) return 0.55f;
	if (characteristic < 1.45f) return 0.68f;
	return 0.82f;
}

// #86 ROOT CAUSE OF THE "BLACK BOXES".
//
// The diamond icon itself was never the problem. A separate streamed
// `lex_blips` dictionary still rendered as an untextured square even when it
// was requested and reported loaded. LEX_BLIP_RECON_ANIMAL is therefore
// declared in the complete resident `INVENTORY_ITEMS_MP` archive shared by all
// custom map icons (#153):
//     <Item key="LEX_BLIP_RECON_ANIMAL">
//       <Linkage>lex_blip_recon_animal</Linkage>
//       <TextureDictionary>INVENTORY_ITEMS_MP</TextureDictionary>
//       <HigherLinkage>BLIP_AMBIENT_HIGHER</HigherLinkage>
//       <LowerLinkage>BLIP_AMBIENT_LOWER</LowerLinkage>
// `prepare_blips_override.py` rebuilds the complete resident archive from all
// vanilla textures and appends this sprite; it does not ship a partial archive.
//
// SIZE SCALING. MAP::SET_BLIP_SCALE is Rockstar's own per-blip scale channel -
// short_update.c:27727 drives it from live data the same way. Rockstar's other
// size mechanism is data-side: authored per-size linkages
// (BLIP_AMBIENT_PED_SMALL / _MEDIUM, blipdata.ymt:1503 and 1511) and the
// BM_SetScale modifiers BLIP_MODIFIER_SCALE_1 (1.2) and BLIP_MODIFIER_SCALE_2
// (1.5) at blipdata.ymt:11071-11084. Those are only three fixed steps against
// one authored art size; SET_BLIP_SCALE off cached GET_MODEL_DIMENSIONS bounds
// gives the four buckets #86 asked for over every animal model without a
// species table, and keeps the single tintable diamond so the vanilla
// tint/elevation rules still apply. Both are genuine Rockstar mechanisms; the
// scale channel is the one that fits the requirement.
static void configureReconBlip(Blip blip, Ped target, ReconDisposition disposition) {
	if (!blip || !target) return;
	if (!PED::IS_PED_HUMAN(target)) {
		SET_BLIP_ICON(blip, joaat("LEX_BLIP_RECON_ANIMAL"));
		MAP::SET_BLIP_SCALE(blip, reconAnimalBlipScale(target));
		// #86: this recon-owned data modifier contains only Rockstar's
		// BM_ShowHeading/LOSCone action and its action-local white override. It
		// cannot replace the diamond linkage or mutate disposition color, fade,
		// scale, or category. Story applies the equivalent guard modifier once to
		// entity blips (act_caunc_rustling.c:3935-3938), so the attached animal
		// owns subsequent heading updates; do not fight it with SET_BLIP_ROTATION.
		const Hash coneModifier = joaat("LEX_BLIP_MODIFIER_RECON_ANIMAL_CONE");
		const bool coneAccepted = MAP::_BLIP_SET_MODIFIER(blip, coneModifier) != 0;
		// Rockstar resolves the species label through this exact discoverable-name
		// pair before displaying an animal info box (short_update.c:31880-31882).
		// Configure-time only: no per-frame localization/native traffic.
		Hash discoverableType = 0;
		const Hash discoverableName = invoke<Hash>(0x0139637A3BFF8B6D, target,
			&discoverableType);
		const char* localizedName = discoverableName ?
			MISC::_CREATE_VAR_STRING(0, discoverableName) : nullptr;
		if (localizedName && localizedName[0]) SET_BLIP_NAME(blip, localizedName);
		char line[256] = {};
		sprintf_s(line,
			"animal blip configured ped=%d nameHash=0x%08x typeHash=0x%08x named=%d cone=LEX_RECON_ANIMAL accepted=%d heading=%.1f existsAfter=%d",
			(int)target, (unsigned int)discoverableName,
			(unsigned int)discoverableType,
			localizedName && localizedName[0] ? 1 : 0,
			coneAccepted ? 1 : 0, ENTITY::GET_ENTITY_HEADING(target),
			MAP::DOES_BLIP_EXIST(blip) ? 1 : 0);
		reconLog(line);
	} else {
		MAP::SET_BLIP_SCALE(blip, 0.65f);
		const ReconHumanRole role = reconHumanRole(target);
		// #296: generic tagged hostiles use the same proven Recon-owned
		// heading/FOV cone as tagged animals. Law and bounty hunters deliberately
		// do not receive it: their authored BLIP_STYLE_COP family already owns
		// the conditional cop cone, so applying ours would duplicate/override it.
		if (role == ReconHumanRole::Generic && disposition == ReconDisposition::Enemy) {
			const Hash coneModifier = joaat("LEX_BLIP_MODIFIER_RECON_ANIMAL_CONE");
			const bool coneAccepted = MAP::_BLIP_SET_MODIFIER(blip, coneModifier) != 0;
			char line[192] = {};
			sprintf_s(line,
				"human enemy cone ped=%d role=generic accepted=%d heading=%.1f",
				(int)target, coneAccepted ? 1 : 0, ENTITY::GET_ENTITY_HEADING(target));
			reconLog(line);
		}
	}
}

static void removeReconTarget(ReconTarget& target) {
	if (target.blip && MAP::DOES_BLIP_EXIST(target.blip)) MAP::REMOVE_BLIP(&target.blip);
	target.blip = 0;
}

static void clearReconTargets() {
	for (ReconTarget& target : g_reconTargets) removeReconTarget(target);
	g_reconTargets.clear();
	g_reconCompendiumStudies.clear();
	for (ReconObjectTarget& target : g_reconObjectTargets)
		if (target.blip && MAP::DOES_BLIP_EXIST(target.blip)) MAP::REMOVE_BLIP(&target.blip);
	g_reconObjectTargets.clear();
}

static void drawReconDisc(float x, float y, float radius, int r, int g, int b, int a) {
	// HUD coordinates are wider than they are tall. Scale X so these bands form a
	// real circle rather than an oval on a 16:9 screen.
	const float xRadius = radius * 0.5625f;
	for (int row = -4; row <= 4; ++row) {
		const float fraction = std::sqrt((std::max)(0.0f, 1.0f - (row * row) / 25.0f));
		GRAPHICS::DRAW_RECT(x, y + radius * row / 4.7f, xRadius * 2.0f * fraction,
			radius / 4.45f, r, g, b, a, FALSE, FALSE);
	}
}

static void drawReconArc(float x, float y, float radius, float fill,
	int r, int g, int b, int alpha = 245) {
	// 144 rectangles per ring exhausted the HUD draw-command budget after only
	// two or three tags, which made later health rings vanish intermittently.
	// 36 overlapping segments keep the core silhouette while allowing all tags.
	const int segments = 36;
	const int drawn = (int)std::ceil((std::max)(0.0f, (std::min)(1.0f, fill)) * segments);
	for (int i = 0; i < drawn; ++i) {
		const float angle = -3.14159265f / 2.0f + (6.2831853f * i / segments);
		const float px = x + std::cos(angle) * radius * 0.5625f;
		const float py = y + std::sin(angle) * radius;
		GRAPHICS::DRAW_RECT(px, py, radius * 0.075f * 0.5625f, radius * 0.075f,
			r, g, b, alpha, FALSE, FALSE);
	}
}

// #2 "the font on the distance text is still wrong".
//
// There is no font-selection NATIVE in RDR2: a grep for FONT across both SDK
// header dumps on disk (_downloads/RDR2_SDK/SDK/inc/natives.h and
// _downloads/NativeMenuBase/RDR2-Native-Menu-Base-master/inc/natives.h) finds
// only NEXT_ONSCREEN_KEYBOARD_RESULT_WILL_DISPLAY_USING_THESE_FONTS, which is
// unrelated. That is why every previous attempt to change this font failed:
// it was never reachable through the call being made.
//
// The real mechanism is markup inside the literal string. Halen84's
// RDR2-Native-Menu-Base - one of the two references Lexer linked on this very
// issue - builds it at src/NativeMenuBase/UI/Drawing.cpp:275:
//     "<TEXTFORMAT ...><P ALIGN='%s'><FONT FACE='$%s' LETTERSPACING='%s'
//      SIZE='%s'>~s~%s</FONT></P><TEXTFORMAT>"
// and passes the result through the same
// _CREATE_VAR_STRING(10, "LITERAL_STRING", ...) + _DISPLAY_TEXT pair used here
// (Drawing.cpp:281). The face names it accepts are enumerated at
// Drawing.cpp:112-113:
//     body, body1, catalog1..catalog5, chalk, Debug_BOLD, FixedWidthNumbers,
//     Font5, gamername, handwritten, ledger, RockstarTAG,
//     SOCIAL_CLUB_COND_BOLD, title, wantedPostersGeneric
//
// The earlier conclusion that RDR Lino was unresolved ignored the enum comments
// in the same supplied reference: inc/enums.h identifies `title` as RDR Lino
// and `FixedWidthNumbers` as RDR Lino Numbers. DistanceFont therefore defaults
// to `title`, and drawReconText uses the reference's complete formatting wrapper
// rather than the bare FONT tag that the game rendered literally.
// FREEZE FIX 2026-08-07 (GameplayTweaks.log evidence: the game hung 78 ms after
// the first ped was tagged).
//
// GetPrivateProfileIntA/StringA read the INI file from DISK on every call.
// Several of this module's settings were being read from inside per-marker draw
// paths, i.e. once per tagged entity per frame - with MaxTags=24 that is dozens
// of synchronous file reads every frame on the main thread, which is what
// wedged the game as soon as a tag existed.
//
// The INI's own contract is "re-read every 2 seconds", so these are cached and
// refreshed on that cadence. Editing settings while playing still works; the
// disk is simply not touched once per draw.
struct ReconCachedSettings {
	DWORD nextRefresh = 0;
	float maximumTagDisplayDistanceMeters = 1000.0f;
	float tagFadeStartPercent = 75.0f;
	int coreBackground = 1;
	int coreTrack = 1;
	int healthPerRing = 100; // #102: fixed HP represented by one complete non-horse ring
	int plantLiftCm = 85;
	int tagDisplayMode = 0; // 0=2D fixed screen size, 1=3D distance-scaled
	float tagHeadGapMeters = 0.30f;
	float tag3DMinimumSizeMultiplier = 0.75f;
	float tag3DMaximumSizeMultiplier = 1.50f;
	float studyProgressDecayPercentPerSecond = 50.0f;
	int distanceTextGapPixels = 14;
	int showDistanceText = 1;
	int distanceTextShadow = 1;
	int taggedOnlyMinimap = -1;   // -1 = key absent, use the module default
	// FREEZE BISECT 2026-08-07. Disabling [ReconTagging] Enabled=0 stops the
	// freeze; nothing narrower has. These four switches split recon into its
	// independent halves so the culprit can be found from the INI in one launch
	// each, with no rebuild. All default ON, so normal play is unchanged.
	//   PartMinimap  - the hostile-blip suppression sweep + SET_POLICE_RADAR_BLIPS
	//   PartMarkers  - the on-screen tag markers (sprites, arcs, distance text)
	//   PartBlips    - creating/refreshing our own tag blips on the minimap
	//   PartPlants   - the #96 plant scenario-point scan and its markers
	int partMinimap = 1;
	int partMarkers = 1;
	int partBlips = 1;
	int partPlants = 1;
};
static ReconCachedSettings g_reconCachedSettings;
static bool g_reconDisplayDistanceSettingsLogged = false;

static void reconRefreshCachedSettings(DWORD now) {
	if (now < g_reconCachedSettings.nextRefresh) return;
	g_reconCachedSettings.nextRefresh = now + 2000;
	const float previousDisplayMax =
		g_reconCachedSettings.maximumTagDisplayDistanceMeters;
	const float previousFadeStart = g_reconCachedSettings.tagFadeStartPercent;
	const float previousAimRadius = g_reconAimRadius;
	const float legacyAimRadius = readF("ReconTagging", "ReticleRadius", 0.060f);
	const float requestedAimRadius = readF("ReconTagging",
		"AimToleranceScreenRadius", legacyAimRadius);
	// GET_SCREEN_COORD_FROM_WORLD_COORD returns normalized 0..1 coordinates.
	// sqrt(0.5^2 + 0.5^2) is the farthest possible distance from screen centre;
	// accepting values through that corner distance makes a deliberate `1`
	// visibly different instead of silently pinning it to the old 0.15 ceiling.
	g_reconAimRadius = (std::max)(0.001f,
		(std::min)(0.70710678f, requestedAimRadius));
	g_reconCachedSettings.maximumTagDisplayDistanceMeters =
		(std::max)(1.0f, (std::min)(10000.0f,
			readF("ReconTagging", "MaximumTagDisplayDistanceMeters", 1000.0f)));
	g_reconCachedSettings.tagFadeStartPercent =
		(std::max)(0.0f, (std::min)(100.0f,
			readF("ReconTagging", "TagFadeStartPercent", 75.0f)));
	if (!g_reconDisplayDistanceSettingsLogged ||
		previousDisplayMax != g_reconCachedSettings.maximumTagDisplayDistanceMeters ||
		previousFadeStart != g_reconCachedSettings.tagFadeStartPercent ||
		previousAimRadius != g_reconAimRadius) {
		g_reconDisplayDistanceSettingsLogged = true;
		char line[192] = {};
		sprintf_s(line,
			"tag-display config maxMeters=%.1f fadeStartPercent=%.1f hotReloadMs=2000",
			g_reconCachedSettings.maximumTagDisplayDistanceMeters,
			g_reconCachedSettings.tagFadeStartPercent);
		reconLog(line);
		char aimLine[224] = {};
		sprintf_s(aimLine,
			"aim-radius config requested=%.6f effective=%.6f units=normalized-screen max=0.707107 hotReloadMs=2000",
			requestedAimRadius, g_reconAimRadius);
		reconLog(aimLine);
	}
	g_reconCachedSettings.coreBackground =
		GetPrivateProfileIntA("ReconTagging", "CoreBackground", 1, g_iniPath.c_str());
	g_reconCachedSettings.coreTrack =
		GetPrivateProfileIntA("ReconTagging", "CoreTrack", 1, g_iniPath.c_str());
	g_reconCachedSettings.healthPerRing = (std::max)(1, (std::min)(10000,
		(int)GetPrivateProfileIntA("ReconTagging", "HealthPerRing", 100, g_iniPath.c_str())));
	g_reconCachedSettings.plantLiftCm =
		GetPrivateProfileIntA("ReconTagging", "PlantMarkerLiftCm", 85, g_iniPath.c_str());
	g_reconCachedSettings.tagDisplayMode = (std::max)(0, (std::min)(1,
		(int)GetPrivateProfileIntA("ReconTagging", "TagDisplayMode", 0,
			g_iniPath.c_str())));
	g_reconCachedSettings.tagHeadGapMeters = (std::max)(0.0f, (std::min)(5.0f,
		readF("ReconTagging", "TagHeadGapMeters", 0.30f)));
	g_reconCachedSettings.tag3DMinimumSizeMultiplier = (std::max)(0.10f, (std::min)(4.0f,
		readF("ReconTagging", "Tag3DMinimumSizeMultiplier", 0.75f)));
	g_reconCachedSettings.tag3DMaximumSizeMultiplier = (std::max)(0.10f, (std::min)(4.0f,
		readF("ReconTagging", "Tag3DMaximumSizeMultiplier", 1.50f)));
	g_reconCachedSettings.studyProgressDecayPercentPerSecond = (std::max)(0.0f, (std::min)(1000.0f,
		readF("ReconTagging", "StudyProgressDecayPercentPerSecond", 50.0f)));
	g_reconCachedSettings.distanceTextGapPixels = (std::max)(0, (std::min)(100,
		(int)GetPrivateProfileIntA("ReconTagging", "DistanceTextGapPixels", 14,
			g_iniPath.c_str())));
	g_reconCachedSettings.showDistanceText =
		GetPrivateProfileIntA("ReconTagging", "ShowDistanceText", 1,
			g_iniPath.c_str()) != 0;
	g_reconCachedSettings.distanceTextShadow =
		GetPrivateProfileIntA("ReconTagging", "DistanceTextShadow", 1,
			g_iniPath.c_str()) != 0;
	char value[16] = {};
	GetPrivateProfileStringA("Misc", "TaggedOnlyOnMinimap", "", value,
		sizeof(value), g_iniPath.c_str());
	g_reconCachedSettings.taggedOnlyMinimap =
		value[0] ? (strtol(value, nullptr, 10) != 0 ? 1 : 0) : -1;
	g_reconCachedSettings.partMinimap =
		GetPrivateProfileIntA("ReconTagging", "PartMinimap", 1, g_iniPath.c_str());
	g_reconCachedSettings.partMarkers =
		GetPrivateProfileIntA("ReconTagging", "PartMarkers", 1, g_iniPath.c_str());
	g_reconCachedSettings.partBlips =
		GetPrivateProfileIntA("ReconTagging", "PartBlips", 1, g_iniPath.c_str());
	g_reconCachedSettings.partPlants =
		GetPrivateProfileIntA("ReconTagging", "PartPlants", 1, g_iniPath.c_str());
}

// #96 completed-tag visibility. Acquisition distance (MaxDistanceMeters) and
// completed-tag display distance are deliberately independent. Every completed
// world tag -- human, animal, horse or plant -- goes through this one curve.
static int reconTagDisplayOpacity(Vector3 playerPos, Vector3 tagPos) {
	const float maximum =
		g_reconCachedSettings.maximumTagDisplayDistanceMeters;
	const float distance = reconDistance(playerPos, tagPos);
	if (distance >= maximum) return 0;
	const float fadeStart = maximum *
		(g_reconCachedSettings.tagFadeStartPercent * 0.01f);
	if (distance <= fadeStart || fadeStart >= maximum) return 255;
	const float remaining = (maximum - distance) / (maximum - fadeStart);
	// Integer alpha is quantized, but a tag inside the configured maximum must
	// remain nonzero; zero is reserved exactly for at/beyond the maximum.
	return (std::max)(1, (std::min)(255,
		(int)std::lround(remaining * 255.0f)));
}

static const char* reconTextFontFace() {
	static char face[48] = {};
	static bool loaded = false;
	if (!loaded) {
		loaded = true;
		GetPrivateProfileStringA("ReconTagging", "DistanceFont", "title", face,
			sizeof(face), g_iniPath.c_str());
		if (!face[0]) strcpy_s(face, "title");
	}
	return face;
}

static void drawReconTextStyled(const char* text, float x, float y, int alpha,
	bool shadow, int fontSize = 18) {
	HUD::_SET_TEXT_COLOR(255, 255, 255, alpha);
	if (shadow) HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, (std::min)(220, alpha));
	// Halen84's supplied NativeMenu reference does not pass a bare FONT tag.
	// Drawing.cpp:253-283 uses this complete TEXTFORMAT/P/FONT wrapper, prefixes
	// the payload with ~s~, and maps centred x from 0..1 to -1..1. Its enum at
	// inc/enums.h:3-21 identifies `title` as RDR Lino. The old partial tag was
	// rendered literally in game, exactly as Lexer's returned screenshot showed.
	char markup[320] = {};
	sprintf_s(markup,
		"<TEXTFORMAT RIGHTMARGIN='0'><P ALIGN='Center'><FONT FACE='$%s' LETTERSPACING='0' SIZE='%d'>~s~%s</FONT></P><TEXTFORMAT>",
		reconTextFontFace(), fontSize, text);
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", markup),
		-1.0f + x * 2.0f, y);
}

static void drawReconText(const char* text, float x, float y) {
	drawReconTextStyled(text, x, y, 235, true);
}

// #130: mouse-wheel ammunition cycling only while the radial pointer is in the
// centre. Rockstar keeps ordinary slot scrolling because we do nothing outside
// the configured centre deadzone.
static void updateRadialAmmoScroll(Ped ped, DWORD now) {
	static const char* const kAmmoNames[] = {
		"AMMO_22", "AMMO_22_TRANQUILIZER",
		"AMMO_ARROW", "AMMO_ARROW_DYNAMITE", "AMMO_ARROW_FIRE", "AMMO_ARROW_IMPROVED",
		"AMMO_ARROW_POISON", "AMMO_ARROW_SMALL_GAME",
		"AMMO_PISTOL", "AMMO_PISTOL_EXPRESS", "AMMO_PISTOL_EXPRESS_EXPLOSIVE",
		"AMMO_PISTOL_HIGH_VELOCITY", "AMMO_PISTOL_SPLIT_POINT",
		"AMMO_REPEATER", "AMMO_REPEATER_EXPRESS", "AMMO_REPEATER_EXPRESS_EXPLOSIVE",
		"AMMO_REPEATER_HIGH_VELOCITY", "AMMO_REPEATER_SPLIT_POINT",
		"AMMO_REVOLVER", "AMMO_REVOLVER_EXPRESS", "AMMO_REVOLVER_EXPRESS_EXPLOSIVE",
		"AMMO_REVOLVER_HIGH_VELOCITY", "AMMO_REVOLVER_SPLIT_POINT",
		"AMMO_RIFLE", "AMMO_RIFLE_ELEPHANT", "AMMO_RIFLE_EXPRESS",
		"AMMO_RIFLE_EXPRESS_EXPLOSIVE", "AMMO_RIFLE_HIGH_VELOCITY", "AMMO_RIFLE_SPLIT_POINT",
		"AMMO_SHOTGUN", "AMMO_SHOTGUN_BUCKSHOT_INCENDIARY",
		"AMMO_SHOTGUN_SLUG", "AMMO_SHOTGUN_SLUG_EXPLOSIVE"
	};
	static std::string message;
	static DWORD messageUntil = 0;
	static bool logBooted = false;
	static bool wheelValueLatched = false;
	static DWORD lastStateLog = 0;
	static DWORD lastCycleAt = 0;
	static Hash pendingReadbackWeapon = 0;
	static Hash pendingReadbackBefore = 0;
	static DWORD pendingReadbackAt = 0;
	if (!logBooted) {
		logBooted = true;
		GtLogStream("radial-ammo", GT_INFO)
			<< "session start enabled=" << (g_radialAmmoEnabled ? 1 : 0) << "\n";
	}
	if (g_radialAmmoShowFeed && now < messageUntil && !message.empty())
		drawReconText(message.c_str(), 0.5f, 0.74f);
	if (!g_radialAmmoEnabled || !ped) return;

	const Hash wheel = joaat("INPUT_OPEN_WHEEL_MENU");
	const bool open = PAD::IS_CONTROL_PRESSED(0, wheel) || PAD::IS_DISABLED_CONTROL_PRESSED(0, wheel) ||
		PAD::IS_CONTROL_PRESSED(2, wheel) || PAD::IS_DISABLED_CONTROL_PRESSED(2, wheel);
	if (!open) {
		wheelValueLatched = false;
		return;
	}

	// Rockstar's PAD cursor and radial-axis natives both return 0,0 for the PC
	// mouse in this wheel. Read the existing OS cursor position without
	// registering, hooking, capturing, or otherwise altering mouse input.
	float cursorX = 0.0f, cursorY = 0.0f;
	float centreDistance = 999.0f;
	POINT cursorPoint = {};
	HWND gameWindow = GetForegroundWindow();
	RECT clientRect = {};
	if (gameWindow && GetCursorPos(&cursorPoint) &&
		ScreenToClient(gameWindow, &cursorPoint) &&
		GetClientRect(gameWindow, &clientRect)) {
		const float width = (float)(clientRect.right - clientRect.left);
		const float height = (float)(clientRect.bottom - clientRect.top);
		const float scale = (std::max)(1.0f, (std::min)(width, height));
		cursorX = width > 0.0f ? cursorPoint.x / width : 0.0f;
		cursorY = height > 0.0f ? cursorPoint.y / height : 0.0f;
		const float dxPixels = cursorPoint.x - width * 0.5f;
		const float dyPixels = cursorPoint.y - height * 0.5f;
		centreDistance = sqrtf(dxPixels * dxPixels + dyPixels * dyPixels) / scale;
	}
	const Hash highlighted = WHEEL_HIGHLIGHTED();
	if (pendingReadbackWeapon && now > pendingReadbackAt) {
		const Hash readback = AMMO_TYPE_FROM_WEAPON(ped, pendingReadbackWeapon);
		if (readback != pendingReadbackBefore) {
			GtLogStream("radial-ammo", GT_INFO)
				<< "ammo-cycle applied weapon=0x" << std::hex
				<< pendingReadbackWeapon << " old=0x" << pendingReadbackBefore
				<< " readback=0x" << readback << std::dec << "\n";
			pendingReadbackWeapon = 0;
		} else if (now - pendingReadbackAt >= 750) {
			GtLogStream("radial-ammo", GT_INFO)
				<< "ammo-cycle ignored weapon=0x" << std::hex
				<< pendingReadbackWeapon << " unchanged=0x" << readback << std::dec << "\n";
			pendingReadbackWeapon = 0;
		}
	}
	const bool centre = centreDistance <= g_radialAmmoCentreDeadzone;
	const bool centreIntent = centre;

	struct WheelPair { const char* name; Hash forward; Hash backward; };
	static const WheelPair wheelPairs[] = {
		{ "slot", 0xE71F89B8u, 0x93D6723Fu },
		{ "cursor", 0x62800C92u, 0x8BDE7443u },
		{ "menu", 0x81457A1Au, 0x9DA42644u },
		{ "radial", 0xD0842EDFu, 0xF78D7337u },
		{ "weapon", 0xFD0F0C2Cu, 0xCC1075A7u },
		{ "alternate", 0x9E6A9358u, 0xD33B28BEu }
	};
	bool forward = false, backward = false;
	const char* source = "none";
	bool pairForward[sizeof(wheelPairs) / sizeof(wheelPairs[0])] = {};
	bool pairBackward[sizeof(wheelPairs) / sizeof(wheelPairs[0])] = {};
	for (int i = 0; i < (int)(sizeof(wheelPairs) / sizeof(wheelPairs[0])); ++i) {
		for (int group : { 0, 1, 2 }) {
			pairForward[i] = pairForward[i] ||
				CONTROL_JUST_PRESSED(group, wheelPairs[i].forward) ||
				DISABLED_CONTROL_JUST_PRESSED(group, wheelPairs[i].forward);
			pairBackward[i] = pairBackward[i] ||
				CONTROL_JUST_PRESSED(group, wheelPairs[i].backward) ||
				DISABLED_CONTROL_JUST_PRESSED(group, wheelPairs[i].backward);
		}
		// Never combine aliases: use the first pair that supplies an
		// unambiguous direction. OR-ing all pairs caused the previous 1,1 log.
		if (!forward && !backward && pairForward[i] != pairBackward[i]) {
			forward = pairForward[i];
			backward = pairBackward[i];
			source = wheelPairs[i].name;
		}
	}
	if (now - lastStateLog >= 250 || forward || backward) {
		lastStateLog = now;
		// One record: the pair table is appended to the same line it always was.
		GtLogStream state("radial-ammo", GT_TRACE);
		state << "open highlight=0x" << std::hex << highlighted << std::dec
			<< " cursor=" << cursorX << "," << cursorY << " centre=" << centre
			<< " centreDistance=" << centreDistance
			<< " centreIntent=" << centreIntent
			<< " direction=" << forward << "," << backward
			<< " source=" << source << " pairs=";
		for (int i = 0; i < (int)(sizeof(wheelPairs) / sizeof(wheelPairs[0])); ++i)
			state << (i ? ";" : "") << wheelPairs[i].name << ":"
				<< pairForward[i] << "," << pairBackward[i];
		state << "\n";
	}
	if (!centreIntent) {
		if (!forward && !backward) wheelValueLatched = false;
		return;
	}
	// The hovered/highlighted weapon is authoritative in the radial; the ped's
	// current weapon can still be the pre-wheel weapon during horse retrieval.
	const Hash weapon = highlighted;
	if (!weapon || weapon == joaat("WEAPON_UNARMED") ||
		!WEAPON_HAS_MULTIPLE_AMMO(weapon)) return;
	int ownedCompatible = 0;
	for (const char* ammoName : kAmmoNames) {
		const Hash ammo = joaat(ammoName);
		if (!AMMO_VALID_FOR_WEAPON(weapon, ammo)) continue;
		if (g_radialAmmoRequireOwned && GET_PED_AMMO_BY_TYPE(ped, ammo) <= 0) continue;
		++ownedCompatible;
	}
	if (ownedCompatible < 2) return;

	// Mouse wheel normally changes the weapon inside the hovered slot. Suppress
	// only those raw aliases, and only over a verified multi-ammo weapon in the
	// centre. The Items page and ordinary slot navigation remain untouched.
	for (int group : { 0, 2 }) {
		DISABLE_CONTROL(group, 0xFD0F0C2Cu); // INPUT_NEXT_WEAPON
		DISABLE_CONTROL(group, 0xCC1075A7u); // INPUT_PREV_WEAPON
		DISABLE_CONTROL(group, 0x9E6A9358u); // mouse-wheel alias
		DISABLE_CONTROL(group, 0xD33B28BEu); // mouse-wheel alias
	}
	if (!forward && !backward) {
		wheelValueLatched = false;
		return;
	}
	if (forward == backward || wheelValueLatched || now - lastCycleAt < 180) return;
	wheelValueLatched = true;
	lastCycleAt = now;

	// Translate one debounced mouse-wheel edge into Rockstar's own ammo-row
	// navigation action. This changes the live radial and lets the owning script
	// commit the selection; no weapon/ammo inventory native is called here.
	static const Hash ammoNext = 0xF1421CF5u; // INPUT_QUICK_SELECT_SECONDARY_NAV_NEXT
	static const Hash ammoPrev = 0xD9F9F017u; // INPUT_QUICK_SELECT_SECONDARY_NAV_PREV
	const Hash before = AMMO_TYPE_FROM_WEAPON(ped, weapon);
	const Hash translated = forward ? ammoNext : ammoPrev;
	SET_CONTROL_NEXT_FRAME(0, translated, 1.0f);
	pendingReadbackWeapon = weapon;
	pendingReadbackBefore = before;
	pendingReadbackAt = now;
	GtLogStream("radial-ammo", GT_INFO)
		<< "ammo-cycle requested direction="
		<< (forward ? "forward" : "backward") << " weapon=0x" << std::hex
		<< weapon << " before=0x" << before << " action=0x" << translated
		<< std::dec << "\n";
	if (g_radialAmmoShowFeed) {
		message.clear();
		messageUntil = 0;
	}
}

#if 0 // Superseded by projectile_visibility.cpp (#16): real weapon muzzle path.
// #112 diagnostic visibility. Rockstar's ordinary bullet mesh is too small to
// judge slow travel reliably, so draw a bright synchronized marker along the
// camera firing ray at the same configured global speed. This is visual only.
struct VisibleProjectile {
	Vector3 origin;
	Vector3 direction;
	float distance;
	float maxDistance;
	DWORD lastTick;
	int particleFx;
};
static std::vector<VisibleProjectile> g_visibleProjectiles;

static void removeProjectileFx(VisibleProjectile& projectile) {
	if (projectile.particleFx && GRAPHICS::DOES_PARTICLE_FX_LOOPED_EXIST(projectile.particleFx))
		GRAPHICS::REMOVE_PARTICLE_FX(projectile.particleFx, FALSE);
	projectile.particleFx = 0;
}

static void clearVisibleProjectiles() {
	for (VisibleProjectile& projectile : g_visibleProjectiles) removeProjectileFx(projectile);
	g_visibleProjectiles.clear();
}

static void updateProjectileVisibility(Ped ped, DWORD now) {
	// Mode 4 moves Rockstar's resident bullet-tracer particle through world space.
	// It is a real particle trail, not a HUD line and not the already-present
	// per-weapon tracer assignment. Mode 2 is the rejected corona fallback.
	if (g_projectileVisibilityMode != 2 && g_projectileVisibilityMode != 4) {
		clearVisibleProjectiles();
		return;
	}
	const Hash particleAsset = joaat("core");
	if (g_projectileVisibilityMode == 4 &&
		!STREAMING::HAS_NAMED_PTFX_ASSET_LOADED(particleAsset))
		STREAMING::REQUEST_NAMED_PTFX_ASSET(particleAsset);
	static std::unordered_map<Ped, DWORD> lastShot;
	int peds[160] = {};
	const int count = sharedWorldPedSnapshot(peds, 160);
	const Vector3 playerChest = PED::GET_PED_BONE_COORDS(ped, 21030, 0.0f, 0.0f, -0.12f);
	for (int p = 0; p < count; ++p) {
		const Ped shooter = peds[p];
		if (!shooter || !ENTITY::DOES_ENTITY_EXIST(shooter) ||
			ENTITY::IS_ENTITY_DEAD(shooter) || !PED::IS_PED_SHOOTING(shooter))
			continue;
		if (shooter != ped && !PED::IS_PED_IN_COMBAT(shooter, ped)) continue;
		const Hash weapon = GET_CURRENT_WEAPON(shooter);
		if (!casingItemForWeapon(weapon)) continue;
		if (now - lastShot[shooter] < 75) continue;
		lastShot[shooter] = now;
		Vector3 origin = PED::GET_PED_BONE_COORDS(shooter, 7966, 0.12f, 0.0f, 0.0f);
		Vector3 direction = {};
		float maxDistance = 250.0f;
		if (shooter == ped) {
			const Vector3 rotation = CAM::GET_GAMEPLAY_CAM_ROT(2);
			const float pitch = rotation.x * 0.0174532925199433f;
			const float yaw = rotation.z * 0.0174532925199433f;
			direction = { -sinf(yaw) * cosf(pitch), cosf(yaw) * cosf(pitch), sinf(pitch) };
		} else {
			const float x = playerChest.x - origin.x;
			const float y = playerChest.y - origin.y;
			const float z = playerChest.z - origin.z;
			const float length = sqrtf(x * x + y * y + z * z);
			if (length < 0.25f) continue;
			direction = { x / length, y / length, z / length };
			maxDistance = length + 12.0f;
		}
		int fx = 0;
		if (g_projectileVisibilityMode == 4 &&
			STREAMING::HAS_NAMED_PTFX_ASSET_LOADED(particleAsset)) {
			const float horizontal = sqrtf(direction.x * direction.x + direction.y * direction.y);
			const float pitchDeg = atan2f(direction.z, horizontal) * 57.2957795130823f;
			const float yawDeg = atan2f(-direction.x, direction.y) * 57.2957795130823f;
			GRAPHICS::USE_PARTICLE_FX_ASSET("core");
			fx = GRAPHICS::START_PARTICLE_FX_LOOPED_AT_COORD("bullet_tracer",
				origin.x, origin.y, origin.z, pitchDeg, 0.0f, yawDeg,
				g_projectileParticleScale, FALSE, FALSE, FALSE, FALSE);
			if (fx) {
				GRAPHICS::SET_PARTICLE_FX_LOOPED_ALPHA(fx, g_projectileParticleAlpha);
				GRAPHICS::SET_PARTICLE_FX_LOOPED_FAR_CLIP_DIST(fx, 300.0f);
			}
		}
		g_visibleProjectiles.push_back({ origin, direction, 0.35f, maxDistance, now, fx });
	}
	for (int i = (int)g_visibleProjectiles.size() - 1; i >= 0; --i) {
		VisibleProjectile& projectile = g_visibleProjectiles[i];
		const float dt = (std::min)(0.10f, (now - projectile.lastTick) / 1000.0f);
		projectile.lastTick = now;
		projectile.distance += g_projectileMarkerSpeed * dt;
		if (projectile.distance > projectile.maxDistance) {
			removeProjectileFx(projectile);
			g_visibleProjectiles.erase(g_visibleProjectiles.begin() + i);
			continue;
		}
		const Vector3 position = {
			projectile.origin.x + projectile.direction.x * projectile.distance,
			projectile.origin.y + projectile.direction.y * projectile.distance,
			projectile.origin.z + projectile.direction.z * projectile.distance
		};
		const float tailDistance = (std::max)(0.0f,
			projectile.distance - g_projectileStreakLength);
		const Vector3 tail = {
			projectile.origin.x + projectile.direction.x * tailDistance,
			projectile.origin.y + projectile.direction.y * tailDistance,
			projectile.origin.z + projectile.direction.z * tailDistance
		};
		if (g_projectileVisibilityMode == 4) {
			if (projectile.particleFx && GRAPHICS::DOES_PARTICLE_FX_LOOPED_EXIST(projectile.particleFx)) {
				const float horizontal = sqrtf(projectile.direction.x * projectile.direction.x +
					projectile.direction.y * projectile.direction.y);
				const float pitchDeg = atan2f(projectile.direction.z, horizontal) * 57.2957795130823f;
				const float yawDeg = atan2f(-projectile.direction.x, projectile.direction.y) * 57.2957795130823f;
				GRAPHICS::SET_PARTICLE_FX_LOOPED_OFFSETS(projectile.particleFx,
					position.x, position.y, position.z, pitchDeg, 0.0f, yawDeg);
			}
		} else {
			for (int segment = 1; segment <= 4; ++segment) {
				const float blend = segment / 5.0f;
				const Vector3 streak = {
					tail.x + (position.x - tail.x) * blend,
					tail.y + (position.y - tail.y) * blend,
					tail.z + (position.z - tail.z) * blend
				};
				const float size = g_projectileMarkerSize * (0.45f + 0.10f * segment);
				GRAPHICS::_DRAW_MARKER(0x94FDAE17, streak.x, streak.y, streak.z,
					0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
					size, size, size, 255, 195, 75, 175 + segment * 12,
					FALSE, FALSE, 2, FALSE, nullptr, nullptr, FALSE);
			}
			GRAPHICS::_DRAW_MARKER(0x94FDAE17, position.x, position.y, position.z,
				0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
				g_projectileMarkerSize, g_projectileMarkerSize, g_projectileMarkerSize,
				255, 215, 120, 230, FALSE, FALSE, 2, FALSE, nullptr, nullptr, FALSE);
			if (g_projectileMarkerBrightness > 0.0f)
				GRAPHICS::DRAW_LIGHT_WITH_RANGE(position.x, position.y, position.z,
					255, 185, 35, 1.5f, g_projectileMarkerBrightness);
		}
	}
}

#endif

// Streamed texture dictionaries need to be requested for several frames before
// HAS_STREAMED_TEXTURE_DICT_LOADED reports true. Call this every frame from the
// recon update so the owned-horse blip sprite is actually available when a tag
// is drawn.
// #182 THE TAGS LOOKED "COMPLETELY UNCHANGED" BECAUSE THE NEW ART NEVER DREW.
// Every sprite and the outer ring were gated on a texture dictionary called
// "MINIMAP_BLIPS", which does not exist - it appears nowhere in the game's own
// scripts. So the loaded-check was false forever, the ring and the sprite were
// both skipped, and what survived was exactly the old plain arc-and-disc: the
// visual Lexer correctly said had not changed at all. It is also why the horse
// kept the generic disc instead of its own icon.
// WHICH FILE IS ACTUALLY THE AUTHORITY FOR A DRAW_SPRITE TEXTURE NAME.
//
// Two different namespaces have been confused here repeatedly, so both are
// written down once:
//
//   * MyOverhaul/blipdata.ymt <Linkage> values are BLIP STYLE linkage names -
//     the ids SET_BLIP_ICON / _BLIP_ADD_FOR_COORD resolve. There are 737 of
//     them and they are spelled in upper case by convention. This file is NOT
//     a manifest of what is inside any texture dictionary; it only names the
//     dictionary a linkage points at (<TextureDictionary>).
//   * The authority for a DRAW_SPRITE TEXTURE name is the dictionary's own
//     contents. This repo has the resident `blips` dictionary unpacked, sprite
//     by sprite, at GameplayTweaks/icons/vanilla/png/blips/ - 321 files, and
//     GameplayTweaks/icons/README.md records that this is the full extraction
//     used to reconstruct the dictionary in build_blips_override.ps1.
//
// Checked against that 321-sprite extraction, every name this module draws out
// of `blips` is present, in the lower-case spelling used below:
//   blip_overlay_ring.png  blip_plant.png  blip_horse_owned.png
//   blip_ambient_bounty_target.png  blip_animal.png
//   blip_ambient_companion.png  blip_ambient_npc.png
// The absent one that caused #96's white square, blip_ambient_herb.png, is
// likewise absent from that directory - so the extraction reproduces the known
// failure and the known successes, which is what makes it usable as evidence.
// Names are written in the extraction's own lower case rather than in
// blipdata.ymt's upper-case linkage spelling, because the extraction is the
// dictionary and blipdata.ymt is not.
static const char* const kBlipTextureDict = "blips";

// #2: THE METERS NO LONGER COME FROM A CUSTOM DICTIONARY.
// The previous code drew `lex_fortification_meter_<percent>` out of a custom
// txd `generic_textures`. That is the same shape of mistake as #23 and #96: a
// custom dictionary whose contents cannot be verified (MyOverhaul/stream/
// generic_textures.ytd is RSC8-compressed, so no name inside it can be read
// statically) standing in for authored Rockstar art that already exists.
// modules/fortification_hud.cpp lines 26-47 record the real art, read out of a
// disassembly of the reference mod Lexer supplied:
//     txd "rpg_textures"    tex "rpg_background"     - the dark core disc
//     txd "rpg_meter_track" tex "rpg_meter_track_9"  - the empty ring track
//     txd "rpg_meter"       tex "rpg_meter_0".."rpg_meter_99" - one authored
//                                                      continuous arc per percent
// with the concentric layout 0.90 / 1.00 / 1.05 of one core box
// (fortification_hud.cpp:45-47). That module ships this exact draw and it is
// what answers Lexer's outstanding note on #2 - "where's the black circle
// background the cores have?" - because rpg_background IS that black disc.
static const char* const kReconCoreDiscDict = "rpg_textures";
static const char* const kReconCoreDiscTexture = "rpg_background";
static const char* const kReconMeterTrackDict = "rpg_meter_track";
static const char* const kReconMeterTrackTexture = "rpg_meter_track_9";
static const char* const kReconMeterDict = "rpg_meter";

static void reconEnsureBlipTextures(DWORD now) {
	// HAS_STREAMED_TEXTURE_DICT_LOADED 0x54D6900929CCF162 /
	// REQUEST_STREAMED_TEXTURE_DICT 0xC1BA29DF5631B0F8, the same pair
	// fortification_hud.cpp:336-337 and collectibles_map.cpp:822-823 use.
	static DWORD nextCheck = 0;
	if (now < nextCheck) return;
	nextCheck = now + 1000;
	static const char* const kDicts[] = {
		kBlipTextureDict, kReconCoreDiscDict, kReconMeterTrackDict,
		kReconMeterDict
	};
	for (const char* dict : kDicts)
		if (!invoke<BOOL>(0x54D6900929CCF162, dict))
			invoke<Void>(0xC1BA29DF5631B0F8, dict, FALSE);
}

// #182(b) THE TAGS DREW ON TOP OF THE SATCHEL. These markers are world-space
// overlays and have no business being on screen while a full-screen UI owns
// it. Rockstar's satchel runs as its own script, so its presence is the
// reliable signal - along with the pause menu.
static bool reconOverlaySuppressed() {
	// Freeze bisect switch: [ReconTagging] PartMarkers=0 stops every on-screen
	// marker draw (sprites, arcs, distance text) without touching scanning,
	// blips or tag state.
	// Evaluate expensive frontend/script state once per frame, not once for every
	// tagged ped and plant. The weapon wheel is included because the remaining
	// FFFFFFFF captures occurred during live horse-weapon/radial transactions.
	static DWORD cachedAt = 0;
	static bool cached = false;
	const DWORD now = GetTickCount();
	if (now == cachedAt) return cached;
	cachedAt = now;
	cached = g_reconCachedSettings.partMarkers == 0 ||
		weaponWheelTransactionBusy(now) || HUD::IS_PAUSE_MENU_ACTIVE() != 0 ||
		scriptRunning("satchel_ui_event_handler") || scriptRunning("satchel");
	return cached;
}

// #113(d): a plant has no health arcs and no disposition, so it gets the same
// seat ring and disc as everything else with a neutral pickup glyph inside it,
// rather than a made-up shape.
// #96 WHITE SQUARE / ICON INSIDE THE PLANT.
//
// (a) The glyph was drawn as texture "blip_ambient_herb" out of txd "blips".
//     That texture does not exist. `MyOverhaul/blipdata.ymt` - the project's own
//     stated authority for this dictionary - declares 737 <Linkage> texture
//     names and "blip_ambient_herb" is not among them in any casing. DRAW_SPRITE
//     of a name the dictionary does not contain renders an untextured quad,
//     which is exactly the white square Lexer reported. This is the same
//     wrong-name/wrong-dictionary defect that cost #23 four builds.
//     Lexer also asked directly: "Isn't there a white plant icon in the vanilla
//     UI already?" There is. blipdata.ymt declares
//         <Item key="BLIP_PLANT"><Linkage>BLIP_PLANT</Linkage>
//         <TextureDictionary>blips</TextureDictionary>
//     so the authored vanilla plant glyph is used instead of an invented name.
//     "BLIP_OVERLAY_RING" is likewise present in blipdata.ymt and is now spelled
//     with its declared casing rather than a guessed lowercase form.
// (b) "the tag icons don't appear above the plant but within it" - the marker
//     anchored at the scenario point coords plus a flat 0.35 m. Plant scenario
//     points sit at the base of the mesh, so 0.35 m is inside the foliage. The
//     clearance is now an INI value under [ReconTagging] so it can be nudged
//     without a rebuild, defaulting to 0.85 m.
static float reconPlantMarkerLift() {
	// [ReconTagging] PlantMarkerLiftCm, in centimetres so the INI stays integer
	// like every other key this module reads. Cached: this is called per plant
	// marker per frame.
	return g_reconCachedSettings.plantLiftCm * 0.01f;
}

static float reconTagScaleMultiplier(Vector3 playerPos, Vector3 tagPos) {
	if (g_reconCachedSettings.tagDisplayMode == 0) return 1.0f;
	const float maximum = (std::max)(1.0f, g_reconCachedSettings.maximumTagDisplayDistanceMeters);
	const float t = (std::max)(0.0f, (std::min)(1.0f, reconDistance(playerPos, tagPos) / maximum));
	const float nearScale = g_reconCachedSettings.tag3DMaximumSizeMultiplier;
	const float farScale = g_reconCachedSettings.tag3DMinimumSizeMultiplier;
	return nearScale + (farScale - nearScale) * t;
}

static float reconProjectedWorldGap(Ped target) {
	if (g_reconCachedSettings.tagHeadGapMeters <= 0.0f) return 0.0f;
	const Vector3 head = reconAnchor(target);
	float hx=0.0f, hy=0.0f, gx=0.0f, gy=0.0f;
	if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(head.x, head.y, head.z, &hx, &hy)) return 0.0f;
	if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(head.x, head.y,
		head.z + g_reconCachedSettings.tagHeadGapMeters, &gx, &gy)) return 0.0f;
	return (std::max)(0.0f, hy - gy);
}

static void drawReconObjectMarker(Vector3 anchorPos, int opacity = 255) {
	if (reconOverlaySuppressed()) return;
	float x = 0.0f, y = 0.0f;
	if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(anchorPos.x, anchorPos.y,
		anchorPos.z + reconPlantMarkerLift(), &x, &y)) return;
	if (x < -0.08f || x > 1.08f || y < -0.08f || y > 1.08f) return;
	const Vector3 playerPos = ENTITY_COORDS(PLAYER::PLAYER_PED_ID());
	const float scaleMultiplier = reconTagScaleMultiplier(playerPos, anchorPos);
	const float radius = 0.018f * scaleMultiplier;
	const float ringBase = y - 0.006f * scaleMultiplier;
	const float coreWidth = radius * 2.0f * 0.5625f;
	const float coreHeight = radius * 2.0f;
	if (invoke<BOOL>(0x54D6900929CCF162, kReconCoreDiscDict))
		GRAPHICS::DRAW_SPRITE(kReconCoreDiscDict, kReconCoreDiscTexture, x, ringBase,
			coreWidth * 0.90f, coreHeight * 0.90f, 0.0f, 0, 0, 0, opacity, FALSE);
	if (invoke<BOOL>(0x54D6900929CCF162, kBlipTextureDict))
		GRAPHICS::DRAW_SPRITE(kBlipTextureDict, "blip_plant", x, ringBase,
			radius * 0.72f, radius * 0.72f * 1.78f, 0.0f, 255, 255, 255,
			opacity, FALSE);
	if (invoke<BOOL>(0x54D6900929CCF162, kReconMeterDict))
		GRAPHICS::DRAW_SPRITE(kReconMeterDict, "rpg_meter_99", x, ringBase,
			coreWidth * 1.05f, coreHeight * 1.05f, 0.0f,
			229, 229, 229, opacity, FALSE);
}

static bool reconMarkerScreenAnchor(Ped target, float* screenX, float* screenTopY) {
	const Vector3 head = reconAnchor(target);
	if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(head.x, head.y, head.z,
		screenX, screenTopY)) return false;

	// SKEL_HEAD is near the centre of the skull. At binocular magnification the
	// projected distance from that bone to the visible crown becomes large enough
	// for a fixed-size tag to overlap the head. Project the model's four top
	// corners and use the highest visible point while keeping the head's X, so the
	// configured pixel gap remains a gap above the rendered silhouette at any FOV.
	const ReconModelBounds bounds = reconBounds(target);
	for (int xi = 0; xi < 2; ++xi) {
		for (int yi = 0; yi < 2; ++yi) {
			const Vector3 top = ENTITY::GET_OFFSET_FROM_ENTITY_IN_WORLD_COORDS(target,
				xi ? bounds.maximum.x : bounds.minimum.x,
				yi ? bounds.maximum.y : bounds.minimum.y, bounds.maximum.z);
			float sx = 0.0f, sy = 0.0f;
			if (GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(top.x, top.y, top.z, &sx, &sy))
				*screenTopY = (std::min)(*screenTopY, sy);
		}
	}
	return true;
}

struct ReconHealthCapacityReadback {
	int entityMax = 1;
	int horseCapacity = 100;
	DWORD nextRefresh = 0;
};
static std::unordered_map<Ped, ReconHealthCapacityReadback> g_reconHealthCapacities;

static ReconHealthCapacityReadback reconHealthCapacity(Ped target,
	bool playerHorse, DWORD now) {
	// Current health/core must remain live for the visible radial, but maximum
	// capacity is not a per-frame value. Bound both capacity natives to one read
	// per two seconds per
	// visible target and cap the cache against recycled ped handles.
	if (g_reconHealthCapacities.size() > 64) g_reconHealthCapacities.clear();
	ReconHealthCapacityReadback& cached = g_reconHealthCapacities[target];
	if (now >= cached.nextRefresh) {
		cached.entityMax = (std::max)(1,
			ENTITY::GET_ENTITY_MAX_HEALTH(target, TRUE));
		cached.horseCapacity = playerHorse ? (std::max)(1, (std::min)(100,
			GET_ATTRIBUTE_BASE_RANK(target, 16))) : 100;
		cached.nextRefresh = now + 2000;
	}
	return cached;
}

static void drawReconMarker(Ped target, ReconDisposition disposition, Ped playerPed,
	bool playerHorse, int opacity = 255, bool showDistance = true) {
	if (reconOverlaySuppressed()) return;
	float x = 0.0f, y = 0.0f;
	if (!reconMarkerScreenAnchor(target, &x, &y)) return;
	if (x < -0.08f || x > 1.08f || y < -0.08f || y > 1.08f) return;

	const Vector3 playerPos = ENTITY_COORDS(playerPed);
	const Vector3 targetPos = ENTITY_COORDS(target);
	const float scaleMultiplier = reconTagScaleMultiplier(playerPos, targetPos);
	const float radius = 0.018f * scaleMultiplier;
	int screenWidth = 0, screenHeight = 0;
	GRAPHICS::GET_SCREEN_RESOLUTION(&screenWidth, &screenHeight);
	const float pixelY = screenHeight > 0 ? 1.0f / (float)screenHeight : 1.0f / 1080.0f;
	const DWORD markerNow = GetTickCount();
	const ReconHealthCapacityReadback capacity =
		reconHealthCapacity(target, playerHorse, markerNow);
	const int health = (std::max)(0, ENTITY::GET_ENTITY_HEALTH(target));
	const int maxHealth = capacity.entityMax;
	// Horse health capacity is attribute 16 in Rockstar's player_horse.c
	// func_652 (horse stat 0 -> attribute 16). Its base rank is 0..100 and is the
	// fillable portion of the radial; the rest must remain transparent. GET_CORE
	// is the live horse-health-core readback used by the HUD-facing core systems;
	// entity HP is retained only as a diagnostic because it produced the reported
	// tiny false sliver when scaled through the ped-health floor.
	const int horseCapacity = capacity.horseCapacity;
	const int horseCore = playerHorse ? (std::max)(0, GET_CORE(target, 0)) : -1;
	// Tag Head Gap is authored in world metres in both modes. Projecting the same
	// vertical world distance makes its apparent screen-space gap shrink naturally
	// with range instead of remaining a fixed pixel offset.
	const float ringBase = y - radius - reconProjectedWorldGap(target);
	// #2: this is now Rockstar's own authored core art, in the reference mod's
	// own draw order and concentric scales (fortification_hud.cpp:26-47):
	//   rpg_textures/rpg_background   at 0.90 - the BLACK CIRCLE BACKGROUND
	//                                          Lexer said was missing
	//   grey rpg_meter_<capacity>                  - fillable maximum
	//   <tag glyph>                                - the tag's identity
	//   white rpg_meter_<current>             - current health
	//                                          anti-aliased arc, drawn last
	//                                          because its centre is transparent
	// No custom texture dictionary and no hand-composited arc is involved, so
	// the "white squares" failure mode cannot recur here.
	const bool coreDiscReady = invoke<BOOL>(0x54D6900929CCF162, kReconCoreDiscDict) != 0;
	const bool meterReady = invoke<BOOL>(0x54D6900929CCF162, kReconMeterDict) != 0;
	// One core box, sized like the reference mod's calibrated core but scaled to
	// this marker's radius. 0.5625 = 9/16 keeps the box square on a 16:9 screen,
	// the same correction drawReconDisc() applies.
	const float coreWidth = radius * 2.0f * 0.5625f;
	const float coreHeight = radius * 2.0f;
	// Each of the three layers is drawn only if ITS OWN dictionary is loaded and
	// its own INI switch is on. History here is bad enough (the "white squares"
	// were once blamed on rpg_meter being an opaque mask - fuckups.txt entry 12
	// later showed the real fault was drawing rpg_meter_N out of `rpg_textures`)
	// that one layer misbehaving must not be able to take the whole tag with it,
	// and must be answerable by editing the INI rather than by another rebuild.
	if (coreDiscReady && g_reconCachedSettings.coreBackground)
		GRAPHICS::DRAW_SPRITE(kReconCoreDiscDict, kReconCoreDiscTexture, x, ringBase,
			coreWidth * 0.90f, coreHeight * 0.90f, 0.0f, 0, 0, 0, opacity, FALSE);

	// Center icon is the tag's chosen identity, exactly as requested.
	const bool spritesReady = invoke<BOOL>(0x54D6900929CCF162, kBlipTextureDict) != 0;
	auto drawTagSprite = [&](const char* name, float scale) {
		GRAPHICS::DRAW_SPRITE(kBlipTextureDict, name, x, ringBase,
			radius * scale, radius * scale * 1.78f, 0.0f, 255, 255, 255, opacity, FALSE);
	};
	if (playerHorse) {
		// Requesting the dictionary and testing it in the SAME call can never
		// succeed on the first frames, and the letter "H" fallback then became the
		// permanent visual - Lexer asked for the horse minimap icon, not a letter.
		// reconEnsureBlipTextures() now requests this every frame from the update
		// loop so it actually streams; draw nothing extra until it does, rather
		// than substituting text.
		if (spritesReady)
			GRAPHICS::DRAW_SPRITE(kBlipTextureDict, "blip_horse_owned", x, ringBase,
				radius * 0.72f, radius * 1.28f, 0.0f, 255, 255, 255, opacity, FALSE);
	} else if (spritesReady) {
		// All four are present in GameplayTweaks/icons/vanilla/png/blips/, the
		// 321-sprite extraction of the resident `blips` dictionary:
		//   blip_ambient_bounty_target.png  blip_animal.png
		//   blip_ambient_companion.png      blip_ambient_npc.png
		const ReconHumanRole role = reconHumanRole(target);
		// #297: role glyphs use the exact resident `blips` sprites named by
		// Rockstar's authored law/bounty linkages. Keep these white: there is no
		// safe conditional-color readback for the separate HUD overlay sprite.
		const char* sprite = !PED::IS_PED_HUMAN(target) ? "blip_animal" :
			role == ReconHumanRole::Law ? "blip_ambient_law" :
			role == ReconHumanRole::BountyHunter ? "blip_ambient_bounty_hunter" :
			disposition == ReconDisposition::Enemy ? "blip_ambient_bounty_target" :
			disposition == ReconDisposition::Ally  ? "blip_ambient_companion" :
			                                         "blip_ambient_npc";
		drawTagSprite(sprite, 0.72f);
	} else {
		// Dictionary still streaming. Draw nothing rather than a letter - the
		// stray "H" fallback taught us those become permanent.
	}
	// #102: ordinary targets use fixed-value authored health layers. One complete
	// layer always means HealthPerRing HP; higher-health targets overlay the next
	// historical color on the same Rockstar meter. This deliberately does NOT
	// normalize every target's own maximum into one full white ring. The owned
	// horse keeps its separate vanilla-like white/grey/clear core-capacity path.
	if (meterReady) {
		const float scale = 1.05f;
		char texture[32] = {};
		if (playerHorse) {
			const int capacityFrame = (std::max)(0, (std::min)(99, horseCapacity));
			const int currentFrame = (std::max)(0, (std::min)(capacityFrame, horseCore));
			if (g_reconCachedSettings.coreTrack && capacityFrame > 0) {
				sprintf_s(texture, "rpg_meter_%d", capacityFrame);
				GRAPHICS::DRAW_SPRITE(kReconMeterDict, texture, x, ringBase,
					coreWidth * scale, coreHeight * scale, 0.0f,
					109, 109, 109, opacity, FALSE);
			}
			if (currentFrame > 0) {
				sprintf_s(texture, "rpg_meter_%d", currentFrame);
				GRAPHICS::DRAW_SPRITE(kReconMeterDict, texture, x, ringBase,
					coreWidth * scale, coreHeight * scale, 0.0f,
					229, 229, 229, opacity, FALSE);
			}
		} else {
			// Keep the exact historical four-layer palette that originally made
			// additional 100-HP chunks legible: red, gold, blue, white. Drawing
			// partial authored meters in order lets the next color overlay only its
			// filled arc, leaving the previous complete layer visible behind it.
			static const int colors[][3] = {
				{ 214, 56, 48 }, { 242, 193, 62 },
				{ 65, 158, 230 }, { 225, 225, 225 }
			};
			const int hpPerRing = (std::max)(1, g_reconCachedSettings.healthPerRing);
			const int layers = (std::max)(1, (maxHealth + hpPerRing - 1) / hpPerRing);
			if (g_reconCachedSettings.coreTrack) {
				strcpy_s(texture, "rpg_meter_99");
				GRAPHICS::DRAW_SPRITE(kReconMeterDict, texture, x, ringBase,
					coreWidth * scale, coreHeight * scale, 0.0f,
					109, 109, 109, opacity, FALSE);
			}
			const int renderedLayers = (std::min)(layers, (int)_countof(colors));
			for (int i = 0; i < renderedLayers; ++i) {
				const int amount = (std::max)(0, (std::min)(hpPerRing, health - i * hpPerRing));
				if (amount <= 0) continue;
				const int frame = (std::max)(1, (std::min)(99,
					(int)std::lround(99.0f * amount / (float)hpPerRing)));
				sprintf_s(texture, "rpg_meter_%d", frame);
				GRAPHICS::DRAW_SPRITE(kReconMeterDict, texture, x, ringBase,
					coreWidth * scale, coreHeight * scale, 0.0f,
					colors[i][0], colors[i][1], colors[i][2], opacity, FALSE);
			}
		}
		static DWORD nextHealthDiagnosticAt = 0;
		if (markerNow >= nextHealthDiagnosticAt) {
			nextHealthDiagnosticAt = markerNow + 2000;
			char healthLine[256] = {};
			const int hpPerRing = (std::max)(1, g_reconCachedSettings.healthPerRing);
			const int layers = playerHorse ? 1 :
				(std::max)(1, (maxHealth + hpPerRing - 1) / hpPerRing);
			sprintf_s(healthLine,
				"tag health ped=%d horse=%d entity=%d/%d core=%d capacity=%d hpPerRing=%d layers=%d",
				(int)target, playerHorse ? 1 : 0, health, maxHealth, horseCore,
				horseCapacity, hpPerRing, layers);
			reconLog(healthLine);
		}
	}

	if (showDistance && g_reconCachedSettings.showDistanceText) {
		char distance[32];
		sprintf_s(distance, "%dm", (int)std::lround(reconDistance(
			ENTITY_COORDS(playerPed), ENTITY_COORDS(target))));
		const int distanceFontSize = (std::max)(6, (int)std::lround(18.0f * scaleMultiplier));
		drawReconTextStyled(distance, x, ringBase - radius -
			g_reconCachedSettings.distanceTextGapPixels * pixelY * scaleMultiplier,
			opacity, g_reconCachedSettings.distanceTextShadow != 0, distanceFontSize);
	}
}

static void updateReconPrompt(Ped playerPed, Ped target, float progress, bool studied) {
	if (!target || studied || !ENTITY::DOES_ENTITY_EXIST(target) ||
		reconOverlaySuppressed()) return;
	const float fill = (std::max)(0.0f, (std::min)(1.0f, progress));
	// This is automatic acquisition progress, not a button prompt. Replace the
	// rejected dotted ring and "Studying" label with the real final tag fading
	// in. The eased curve stays restrained during the dwell; completion swaps to
	// the normal fully opaque tag, deliberately making the final state obvious.
	const float eased = std::pow(fill, 2.4f);
	const int opacity = 20 + (int)std::lround(eased * 135.0f);
	drawReconMarker(target, reconDispositionFor(playerPed, target), playerPed,
		false, opacity, false);
}

static bool isReconTagged(Ped target) {
	for (const ReconTarget& tag : g_reconTargets) if (tag.ped == target) return true;
	return false;
}

static bool reconTaggedOnlyMinimapEnabled() {
	// #94: the player-facing switch belongs under Misc. Keep the old
	// ReconTagging value as the fallback so an existing INI does not silently
	// change behaviour until the integrator adds the renamed setting.
	// Cached (see ReconCachedSettings): this is consulted per blip per frame.
	if (g_reconCachedSettings.taggedOnlyMinimap < 0) return g_reconMarkedOnlyMinimap;
	return g_reconCachedSettings.taggedOnlyMinimap != 0;
}

// #176: Rockstar owns the animal InfoBox. short_update.c:1273-1308 reads
// player UI-prompt type 35, and its event-30/type-35 branch at 5715-5718
// toggles the Story-owned state and calls _SET_SHOW_INFO_CARD. The same script
// then launches SHOP_BROWSING and builds the InfoBox data binding at
// 31865-32045. Do not duplicate that transaction or write its global.
//
// Our quick binocular path disabled every contextual action while the scope was
// active. That included the three actions from which Rockstar can build and
// operate the targeted-animal prompt. Release only those actions after the
// authored scope is up and recon has a real nonhuman ped under the reticle.
// Story still decides whether prompt type 35 is active and whether to show the
// card. The reads below distinguish input/prompt failure from app/data failure.
static void updateReconAnimalInfoBoxBridge(Player player, Ped target,
	bool binocularActive, DWORD now) {
	static Ped lastTarget = 0;
	static int lastPrompt = -1;
	static int lastApp = -1;
	static int lastBinding = -1;
	static DWORD nextPoll = 0;
	static DWORD nextHeartbeat = 0;
	const bool eligible = binocularActive && target &&
		ENTITY::DOES_ENTITY_EXIST(target) && ENTITY::IS_ENTITY_A_PED(target) &&
		!PED::IS_PED_HUMAN(target) &&
		!PED::IS_PED_DEAD_OR_DYING(target, TRUE);
	// #292: Rockstar cannot create/update its Study interaction target while our
	// binocular path is still suppressing the contextual actions which own that
	// target. Release those actions as soon as the authored scope is active;
	// requiring Recon to have already selected a ped creates a circular gate.
	if (binocularActive) {
		static const Hash kStoryAnimalPromptActions[] = {
			joaat("INPUT_INTERACT_LOCKON"),
			joaat("INPUT_CONTEXT"),
			joaat("INPUT_CONTEXT_SECONDARY"),
		};
		for (Hash action : kStoryAnimalPromptActions) {
			PAD::ENABLE_CONTROL_ACTION(0, action, TRUE);
			PAD::ENABLE_CONTROL_ACTION(2, action, TRUE);
		}
	}
	const bool targetChanged = target != lastTarget;
	if (!targetChanged && now < nextPoll) return;
	nextPoll = now + 100;

	const int promptActive = eligible ?
		(invoke<BOOL>(0x51BEA356B1C60225, player, 35) ? 1 : 0) : 0;
	const int appActive = UIAPPS::_IS_APP_ACTIVE_BY_HASH(
		joaat("SHOP_BROWSING")) ? 1 : 0;
	const Any infoBox = DATABINDING::_DATABINDING_GET_DATA_CONTAINER_FROM_PATH(
		reinterpret_cast<Any>(static_cast<const char*>("InfoBox")));
	const int bindingValid = infoBox &&
		DATABINDING::_DATABINDING_IS_DATA_ID_VALID(infoBox) ? 1 : 0;
	const bool changed = target != lastTarget || promptActive != lastPrompt ||
		appActive != lastApp || bindingValid != lastBinding;
	if (changed || (eligible && now >= nextHeartbeat)) {
		char line[224] = {};
		sprintf_s(line,
			"animal infobox target=%d eligible=%d prompt35=%d shopBrowsing=%d infoBox=%d bridge=contextual-actions",
			(int)target, eligible ? 1 : 0, promptActive, appActive,
			bindingValid);
		reconLog(line);
		nextHeartbeat = now + 2000;
	}
	lastTarget = target;
	lastPrompt = promptActive;
	lastApp = appActive;
	lastBinding = bindingValid;
}

// #292: use Rockstar's interaction target for the animal Study path instead of
// trying to reconstruct it from screen centre, projected size or Recon range.
// GET_PLAYER_INTERACTION_TARGET_ENTITY (0x3EE1F7A8C32F24E1) is the engine-owned
// target used by entity prompt groups. Prompt type 35 is the Story Study prompt
// already read by short_update; requiring both keeps generic horse/NPC
// interaction targets out of this bypass. Only identity/liveness is validated
// here: the fact that Story selected the animal is the aim/range/LOS authority.
static Ped reconRockstarStudyTarget(Player player, bool binocularActive, DWORD now) {
	static Ped lastTarget = 0;
	static int lastPrompt = -1;
	static DWORD nextHeartbeat = 0;
	if (!binocularActive) {
		lastTarget = 0;
		lastPrompt = 0;
		return 0;
	}

	const int promptActive = invoke<BOOL>(0x51BEA356B1C60225, player, 35) ? 1 : 0;
	Entity interactionEntity = 0;
	const bool hasInteractionTarget = invoke<BOOL>(0x3EE1F7A8C32F24E1,
		player, &interactionEntity, TRUE, TRUE) != FALSE;
	Ped target = 0;
	if (promptActive && hasInteractionTarget && interactionEntity &&
		ENTITY::DOES_ENTITY_EXIST(interactionEntity) &&
		ENTITY::IS_ENTITY_A_PED(interactionEntity)) {
		const Ped candidate = (Ped)interactionEntity;
		if (!PED::IS_PED_HUMAN(candidate) &&
			!PED::IS_PED_DEAD_OR_DYING(candidate, TRUE))
			target = candidate;
	}

	if (target != lastTarget || promptActive != lastPrompt || now >= nextHeartbeat) {
		char line[224] = {};
		sprintf_s(line,
			"study target prompt35=%d interactionAccepted=%d entity=%d animal=%d source=rockstar-interaction",
			promptActive, hasInteractionTarget ? 1 : 0,
			(int)interactionEntity, (int)target);
		reconLog(line);
		nextHeartbeat = now + 2000;
	}
	lastTarget = target;
	lastPrompt = promptActive;
	return target;
}

static const Hash kReconHiddenBlipModifier = joaat("BLIP_MODIFIER_HIDDEN");
static std::unordered_set<Blip> g_reconSuppressedHostileBlips;

static void restoreSuppressedReconBlip(Blip blip) {
	if (!blip || !MAP::DOES_BLIP_EXIST(blip)) {
		g_reconSuppressedHostileBlips.erase(blip);
		return;
	}
	if (!g_reconSuppressedHostileBlips.erase(blip)) return;
	invoke<Void>(0xB059D7BD3D78C16F, blip, kReconHiddenBlipModifier);
}

static void restoreAllSuppressedReconBlips() {
	for (Blip blip : g_reconSuppressedHostileBlips)
		if (blip && MAP::DOES_BLIP_EXIST(blip))
			invoke<Void>(0xB059D7BD3D78C16F, blip, kReconHiddenBlipModifier);
	g_reconSuppressedHostileBlips.clear();
}

static void suppressUnmarkedHostileBlips(Ped playerPed, DWORD now) {
	static bool policeRadarSuppressed = false;
	// Freeze bisect switch: [ReconTagging] PartMinimap=0 removes this whole
	// subsystem (the per-ped sweep, the blip modifiers and the police-radar
	// override) while leaving the rest of recon running.
	const bool enabled = reconTaggedOnlyMinimapEnabled() &&
		g_reconCachedSettings.partMinimap != 0;
	if (!enabled) {
		// SET_POLICE_RADAR_BLIPS is persistent, so relinquish the layer when the
		// player turns marked-only mode off. This restores vanilla's own hostile
		// awareness dots without touching recon-created tagged blips.
		if (policeRadarSuppressed) PLAYER::SET_POLICE_RADAR_BLIPS(TRUE);
		policeRadarSuppressed = false;
		restoreAllSuppressedReconBlips();
		return;
	}

	// Do not delete Rockstar-owned blips. The owning scripts immediately replace
	// deleted handles as actors enter the camera frustum, which was the observed
	// look-at-them/reappear loop. BLIP_MODIFIER_HIDDEN suppresses the existing
	// durable handle instead; reassert it every frame so newly created hostile
	// handles cannot become camera-dependent red dots between 100 ms scans.
	// FREEZE FIX 2026-08-07. This whole sweep used to run EVERY FRAME: up to 160
	// peds, each costing DOES_ENTITY_EXIST + IS_PED_HUMAN + IS_PED_DEAD_OR_DYING
	// + GET_BLIP_FROM_ENTITY + a disposition test, and then ADD_BLIP_MODIFIER was
	// re-applied to every hostile blip on every single frame. That is ~1000
	// natives per frame, and re-adding the same modifier endlessly is unbounded
	// work on an engine-owned object. GameplayTweaks.log showed the game wedging
	// shortly after tagging, with our own script thread still ticking - i.e. we
	// were wedging the GAME, not ourselves, which is what native spam looks like.
	//
	// Reassertion still happens (new hostile handles do appear as peds enter the
	// frustum), just on a 250 ms cadence rather than per frame. That is the same
	// cadence the recon scan itself uses, so nothing becomes camera-dependent.
	static DWORD nextHostileSweep = 0;
	if (now < nextHostileSweep) return;
	nextHostileSweep = now + 250;

	// Fort Wallace's hostile dots are not all durable entity blips. Reassert the
	// engine-owned police layer only on the same 4 Hz ownership cadence as the
	// handle sweep below. The previous implementation still called this native
	// every frame after the sweep itself was rate-limited, reproducing the same
	// engine tug-of-war that froze #14. Rockstar calls it on transitions rather
	// than per frame (mob2.c:18609; restore at mob2.c:73159).
	PLAYER::SET_POLICE_RADAR_BLIPS(FALSE);
	policeRadarSuppressed = true;

	const Ped saddleHorse = PLAYER::_GET_SADDLE_HORSE_FOR_PLAYER(
		PLAYER::PLAYER_ID());
	int peds[160] = {};
	const int count = sharedWorldPedSnapshot(peds, 160);
	for (int i = 0; i < count; ++i) {
		const Ped other = peds[i];
		if (!other || other == playerPed || !ENTITY::DOES_ENTITY_EXIST(other) ||
			other == saddleHorse || PED::IS_PED_DEAD_OR_DYING(other, TRUE)) continue;
		const bool human = PED::IS_PED_HUMAN(other) != FALSE;
		Blip blip = MAP::GET_BLIP_FROM_ENTITY(other);
		if (isReconTagged(other)) {
			restoreSuppressedReconBlip(blip);
			continue;
		}
		if (reconDispositionFor(playerPed, other) != ReconDisposition::Enemy) continue;
		if (!blip || !MAP::DOES_BLIP_EXIST(blip)) continue;
		// Only apply the modifier to a blip we have not already suppressed.
		// Re-adding it every sweep was the unbounded part.
		if (g_reconSuppressedHostileBlips.count(blip)) continue;
		ADD_BLIP_MODIFIER(blip, kReconHiddenBlipModifier);
		if (g_reconSuppressedHostileBlips.insert(blip).second) {
			char line[192];
			sprintf_s(line,
				"minimap hid untagged hostile ped=%d blip=%d human=%d disposition=%d existsAfter=%d",
				(int)other, (int)blip, human ? 1 : 0,
				(int)reconDispositionFor(playerPed, other),
				MAP::DOES_BLIP_EXIST(blip) ? 1 : 0);
			reconLog(line);
		}
	}

	for (auto it = g_reconSuppressedHostileBlips.begin();
		it != g_reconSuppressedHostileBlips.end();) {
		if (!*it || !MAP::DOES_BLIP_EXIST(*it)) it = g_reconSuppressedHostileBlips.erase(it);
		else ++it;
	}
}

static bool readReconCompendiumIdentity(Ped target,
	ReconCompendiumStudy& identity, const char*& reason) {
	if (!target || !ENTITY::DOES_ENTITY_EXIST(target) ||
		PED::IS_PED_DEAD_OR_DYING(target, TRUE)) {
		reason = "invalid-ped";
		return false;
	}
	if (PED::IS_PED_HUMAN(target)) {
		reason = "human-no-animal-entry";
		return false;
	}
	const Hash model = ENTITY_MODEL(target);
	const Hash animalType = ENTITY::_GET_PED_ANIMAL_TYPE(target);
	const Hash shortDescription = invoke<Hash>(0x6C5E5D48E48B4C65, target);
	if (!model || !animalType || !shortDescription) {
		reason = "missing-animal-identity";
		return false;
	}
	Hash discoverableType = 0;
	const Hash discoverableName = invoke<Hash>(0x0139637A3BFF8B6D, target,
		&discoverableType);
	if (!discoverableName || !discoverableType) {
		reason = "not-discoverable";
		return false;
	}
	// This is Rockstar's own gate immediately before the compendium transaction
	// in short_update.c:8911-8945. Passing an animal type alone is not enough;
	// mounted targets and transient peds must resolve to a valid discoverable
	// name/type pair for this player before recon may write anything.
	if (!invoke<BOOL>(0x0772F87D7B07719A, PLAYER::PLAYER_ID(),
		discoverableType, discoverableName)) {
		reason = "discovery-gate-rejected";
		return false;
	}
	identity.ped = target;
	identity.model = model;
	identity.animalType = animalType;
	identity.discoverableName = discoverableName;
	identity.discoverableType = discoverableType;
	reason = "validated";
	return true;
}

static void queueReconCompendiumStudy(Ped target, DWORD now) {
	for (const ReconCompendiumStudy& pending : g_reconCompendiumStudies)
		if (pending.ped == target) return;

	ReconCompendiumStudy pending;
	const char* reason = nullptr;
	if (!readReconCompendiumIdentity(target, pending, reason)) {
		char line[192];
		sprintf_s(line, "compendium skipped ped=%d reason=%s", (int)target,
			reason ? reason : "unknown");
		reconLog(line);
		return;
	}
	if (invoke<BOOL>(0x23B5E9C5160BC04F, target)) {
		char line[192];
		sprintf_s(line,
			"compendium already-observed ped=%d type=0x%08x name=0x%08x",
			(int)target, (unsigned int)pending.animalType,
			(unsigned int)pending.discoverableName);
		reconLog(line);
		return;
	}
	// Do not write compendium state inside the same frame that creates/configures
	// the recon blip. The failure trace ended in that combined transaction. The
	// delayed pass revalidates the exact entity/model/discovery identity, yields
	// to Rockstar's own short_update first, and checks observed state again.
	pending.readyAt = now + 300;
	g_reconCompendiumStudies.push_back(pending);
	char line[224];
	sprintf_s(line,
		"compendium queued ped=%d model=0x%08x type=0x%08x name=0x%08x readyInMs=300",
		(int)target, (unsigned int)pending.model, (unsigned int)pending.animalType,
		(unsigned int)pending.discoverableName);
	reconLog(line);
}

static void updateReconCompendiumStudies(DWORD now) {
	for (size_t i = 0; i < g_reconCompendiumStudies.size();) {
		ReconCompendiumStudy& pending = g_reconCompendiumStudies[i];
		const DWORD gate = pending.writeIssued ? pending.verifyAt : pending.readyAt;
		if (now < gate) {
			++i;
			continue;
		}

		ReconCompendiumStudy live;
		const char* reason = nullptr;
		if (!readReconCompendiumIdentity(pending.ped, live, reason) ||
			live.model != pending.model || live.animalType != pending.animalType ||
			live.discoverableName != pending.discoverableName ||
			live.discoverableType != pending.discoverableType) {
			char line[224];
			sprintf_s(line, "compendium cancelled ped=%d reason=%s identityChanged=%d",
				(int)pending.ped, reason ? reason : "identity-changed",
				reason && strcmp(reason, "validated") == 0 ? 1 : 0);
			reconLog(line);
			g_reconCompendiumStudies.erase(g_reconCompendiumStudies.begin() + i);
			continue;
		}

		const bool observed = invoke<BOOL>(0x23B5E9C5160BC04F, pending.ped) != 0;
		if (pending.writeIssued) {
			char line[224];
			sprintf_s(line,
				"compendium readback ped=%d observed=%d type=0x%08x name=0x%08x",
				(int)pending.ped, observed ? 1 : 0,
				(unsigned int)pending.animalType,
				(unsigned int)pending.discoverableName);
			reconLog(line);
			g_reconCompendiumStudies.erase(g_reconCompendiumStudies.begin() + i);
			continue;
		}
		if (observed) {
			char line[192];
			sprintf_s(line, "compendium completed-by-game ped=%d type=0x%08x",
				(int)pending.ped, (unsigned int)pending.animalType);
			reconLog(line);
			g_reconCompendiumStudies.erase(g_reconCompendiumStudies.begin() + i);
			continue;
		}

		const bool horse = invoke<BOOL>(0x772A1969F649E902, pending.model) != 0;
		if (horse)
			COMPENDIUM::COMPENDIUM_HORSE_OBSERVED(pending.ped, FALSE);
		else
			COMPENDIUM::COMPENDIUM_ANIMAL_OBSERVED_BY_STAT_NAME(
				pending.animalType, FALSE);
		pending.writeIssued = true;
		pending.verifyAt = now + 300;
		char line[224];
		sprintf_s(line,
			"compendium write-issued ped=%d horse=%d type=0x%08x name=0x%08x",
			(int)pending.ped, horse ? 1 : 0, (unsigned int)pending.animalType,
			(unsigned int)pending.discoverableName);
		reconLog(line);
		++i;
	}
}

static void markReconTarget(Ped playerPed, Ped target, DWORD now) {
	if (isReconTagged(target)) return;
	{
		char begin[160];
		sprintf_s(begin, "mark begin ped=%d kind=%d parts=minimap:%d,markers:%d,blips:%d,plants:%d",
			(int)target, (int)reconDispositionFor(playerPed, target),
			g_reconCachedSettings.partMinimap, g_reconCachedSettings.partMarkers,
			g_reconCachedSettings.partBlips, g_reconCachedSettings.partPlants);
		reconLog(begin);
	}
	// If this entity had a vanilla hostile blip before being tagged, explicitly
	// remove our hidden modifier before creating/configuring its recon marker.
	restoreSuppressedReconBlip(MAP::GET_BLIP_FROM_ENTITY(target));
	if ((int)g_reconTargets.size() >= g_reconMaxTags) {
		removeReconTarget(g_reconTargets.front());
		g_reconTargets.erase(g_reconTargets.begin());
	}
	ReconTarget tag;
	tag.ped = target;
	tag.disposition = reconDispositionFor(playerPed, target);
	tag.enemyLatched = tag.disposition == ReconDisposition::Enemy;
	tag.markedAt = now;
	if (g_reconBlipsEnabled && g_reconCachedSettings.partBlips != 0) {
		tag.blip = MAP::_BLIP_ADD_FOR_ENTITY(reconBlipStyle(target, tag.disposition), target);
		if (tag.blip && MAP::DOES_BLIP_EXIST(tag.blip)) {
			configureReconBlip(tag.blip, target, tag.disposition);
		}
		char blipResult[112];
		sprintf_s(blipResult, "mark blip ped=%d handle=%d exists=%d",
			(int)target, (int)tag.blip,
			tag.blip && MAP::DOES_BLIP_EXIST(tag.blip) ? 1 : 0);
		reconLog(blipResult);
	}
	g_reconTargets.push_back(tag);
	// One completed Study combines the session tag with a compendium observation
	// when the target has a genuine entry. The write is queued rather than issued
	// in this blip-creation transaction; humans and non-discoverable entities are
	// logged and remain valid tag-only targets.
	queueReconCompendiumStudy(target, now);
	// This pair is used by vanilla free-roam scripts and does not depend on a
	// shop sound bank already being active.
	AUDIO::PLAY_SOUND_FRONTEND("SELECT", "HUD_SHOP_SOUNDSET", TRUE, 0);
	char log[192];
	sprintf_s(log, "marked ped=%d kind=%d compendium=validated-queue blip=%d exists=%d distance=%.1f hp=%d/%d", (int)target,
		(int)tag.disposition, (int)tag.blip,
		tag.blip && MAP::DOES_BLIP_EXIST(tag.blip) ? 1 : 0,
		reconDistance(ENTITY_COORDS(playerPed), ENTITY_COORDS(target)),
		ENTITY::GET_ENTITY_HEALTH(target), ENTITY::GET_ENTITY_MAX_HEALTH(target, TRUE));
	reconLog(log);
}

static void ensurePlayerHorseReconTarget(Ped playerPed, DWORD now) {
	const Ped horse = PLAYER::_GET_SADDLE_HORSE_FOR_PLAYER(PLAYER::PLAYER_ID());
	for (size_t i = 0; i < g_reconTargets.size();) {
		if (g_reconTargets[i].playerHorse && g_reconTargets[i].ped != horse) {
			removeReconTarget(g_reconTargets[i]);
			g_reconTargets.erase(g_reconTargets.begin() + i);
		} else {
			++i;
		}
	}
	if (!horse || !ENTITY::DOES_ENTITY_EXIST(horse) || PED::IS_PED_DEAD_OR_DYING(horse, TRUE))
		return;
	for (ReconTarget& tag : g_reconTargets) {
		if (tag.ped == horse) {
			tag.playerHorse = true;
			tag.disposition = reconDispositionFor(playerPed, horse);
			return;
		}
	}
	ReconTarget tag;
	tag.ped = horse;
	tag.disposition = reconDispositionFor(playerPed, horse);
	tag.markedAt = now;
	tag.playerHorse = true;
	g_reconTargets.push_back(tag);
}

// Resolve the entity under the binocular reticle with one asynchronous camera
// ray. The previous implementation enumerated up to 6,144 global pool entries
// every 75 ms while binoculars were active; sustained use drove the game into
// ERROR:FFFFFFFF. Shape-test handles are the one engine object intentionally
// carried across frames, and the returned entity is consumed only on the frame
// its result resolves.
static Entity updateReconReticleProbe(Ped playerPed, bool active, DWORD now) {
	static int probe = 0;
	Entity resolvedEntity = 0;
	if (probe) {
		BOOL hit = FALSE;
		Vector3 end = {}, normal = {};
		Entity entity = 0;
		const int status = SHAPE_RESULT(probe, &hit, &end, &normal, &entity);
		if (status != 1) {
			probe = 0;
			if (status == 2 && hit) {
				g_reconReticleHit = end;
				g_reconReticleHitValid = true;
				g_reconReticleHitAt = now;
				if (entity) resolvedEntity = entity;
			} else {
				g_reconReticleHitValid = false;
			}
		}
	}
	if (!active) g_reconReticleHitValid = false;
	if (active && !probe && playerPed) {
		const Vector3 start = CAM::GET_GAMEPLAY_CAM_COORD();
		const Vector3 rotation = CAM::GET_GAMEPLAY_CAM_ROT(2);
		const float pitch = rotation.x * 0.0174532925199433f;
		const float yaw = rotation.z * 0.0174532925199433f;
		const Vector3 direction = {
			-sinf(yaw) * cosf(pitch),
			 cosf(yaw) * cosf(pitch),
			 sinf(pitch)
		};
		const Vector3 end = {
			start.x + direction.x * g_reconMaxDistance,
			start.y + direction.y * g_reconMaxDistance,
			start.z + direction.z * g_reconMaxDistance
		};
		probe = START_LOS_PROBE(start, end, 511, playerPed);
	}
	return resolvedEntity;
}

// #96 PLANT SELECTION VIA THE ENGINE'S OWN TYPED SCENARIO-POINT INDEX.
//
// The bulk nearby-scenario native is forbidden here: its undocumented Any*
// buffer ABI caused a reproducible /GS stack-cookie failure in this function.
// Instead, search each shipped WB_ harvestable TYPE around the reticle ray's
// world hit using Rockstar's one-result native. A 250 ms typed-query cadence
// bounds native traffic; the selected point is revalidated and returned from a
// cache between scans so the Study dwell remains continuous.
//
// It deliberately does not walk either the global object pool or an engine
// output buffer, the two paths already proven unsafe under sustained use.
static int selectReconPlantScenarioPoint(const Vector3& playerPos, DWORD now,
	ReconPlantScanStats& stats) {
	static int cachedPoint = 0;
	static DWORD nextTypedScan = 0;
	if (!g_reconReticleHitValid || now - g_reconReticleHitAt > 300) {
		cachedPoint = 0;
		return 0;
	}

	auto evaluatePoint = [&](int point, float& screenDistance) -> bool {
		if (!point) return false;
		// TASK::_DOES_SCENARIO_POINT_EXIST 0x841475AC96E794D1 natives.h:7284
		if (!TASK::_DOES_SCENARIO_POINT_EXIST(point)) return false;
		++stats.existing;
		// TASK::_GET_SCENARIO_POINT_TYPE 0xA92450B5AE687AAF natives.h:7394
		const Hash type = TASK::_GET_SCENARIO_POINT_TYPE(point);
		if (!isKnownPlantScenarioType(type)) {
			if (!stats.nearestRejectedType) stats.nearestRejectedType = type;
			return false;
		}
		++stats.typedPlant;
		if (isReconObjectTagged(point)) { ++stats.alreadyTagged; return false; }
		// TASK::_GET_SCENARIO_POINT_COORDS 0xA8452DD321607029 natives.h:7289
		const Vector3 coords = TASK::_GET_SCENARIO_POINT_COORDS(point, TRUE);
		if (reconDistance(playerPos, coords) > g_reconMaxDistance) return false;
		++stats.inRange;
		float sx = 0.0f, sy = 0.0f;
		if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(coords.x, coords.y,
			coords.z + reconPlantMarkerLift(), &sx, &sy)) return false;
		++stats.projected;
		const float dx = sx - 0.5f, dy = sy - 0.5f;
		screenDistance = std::sqrt(dx * dx + dy * dy);
		stats.nearestScreen = (std::min)(stats.nearestScreen, screenDistance);
		if (screenDistance > g_reconAimRadius) {
			++stats.radiusRejected;
			return false;
		}
		++stats.withinReticle;
		// A plant sits on the ground and is routinely occluded by its own
		// foliage, so a strict entity LOS test would reject the thing the player
		// is plainly looking at. Range plus reticle plus the study dwell is the
		// same deliberateness gate the ped path uses.
		return true;
	};

	if (cachedPoint && now < nextTypedScan) {
		float cachedScreen = 999.0f;
		if (evaluatePoint(cachedPoint, cachedScreen)) return cachedPoint;
		cachedPoint = 0;
		nextTypedScan = 0;
	}
	if (now < nextTypedScan) return 0;
	nextTypedScan = now + 250;

	int bestPoint = 0;
	float bestScreen = 999.0f;
	std::unordered_set<int> seenPoints;
	for (Hash type : g_plantModels) {
		// TASK::_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE
		// 0xF533D68FF970D190, natives.h:7337. Unlike the rejected bulk call,
		// this returns one int and writes through no caller-owned buffer.
		const int point = TASK::_FIND_CLOSEST_ACTIVE_SCENARIO_POINT_OF_TYPE(
			g_reconReticleHit.x, g_reconReticleHit.y, g_reconReticleHit.z,
			type, 3.0f, 0, FALSE);
		if (!point || !seenPoints.insert(point).second) continue;
		++stats.enumerated;
		float screenDistance = 999.0f;
		if (evaluatePoint(point, screenDistance) && screenDistance < bestScreen) {
			bestScreen = screenDistance;
			bestPoint = point;
		}
	}
	cachedPoint = bestPoint;
	return bestPoint;
}

// Prefer the actual reticle-hit plant visual. Live #96 traces resolved
// 0xF234A5A8 (`s_inv_huckleberry01x`) and 0xD7063479 (`blackcurrant_p`), both
// present in Rockstar's lootable-herb metadata above. The short cache bridges
// asynchronous shape-test frames; every use revalidates existence and model so
// a picked/replaced plant cannot retain the old tag.
static ReconPlantCandidate selectReconPlant(Entity reticleEntity,
	const Vector3& playerPos, DWORD now, ReconPlantScanStats& stats) {
	static Entity cachedEntity = 0;
	static Hash cachedModel = 0;
	static DWORD cachedAt = 0;

	auto evaluateEntity = [&](Entity entity, Hash expectedModel,
		ReconPlantCandidate& result) -> bool {
		if (!entity || !ENTITY::DOES_ENTITY_EXIST(entity) ||
			!ENTITY::IS_ENTITY_AN_OBJECT(entity)) return false;
		++stats.visualCandidates;
		const Hash model = ENTITY_MODEL(entity);
		if ((expectedModel && model != expectedModel) || !isKnownPlantVisualModel(model))
			return false;
		++stats.visualModels;
		if (isReconObjectTagged(0, entity)) {
			++stats.alreadyTagged;
			return false;
		}
		const Vector3 coords = ENTITY_COORDS(entity);
		if (reconDistance(playerPos, coords) > g_reconMaxDistance) return false;
		++stats.inRange;
		float sx = 0.0f, sy = 0.0f;
		if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(coords.x, coords.y,
			coords.z + reconPlantMarkerLift(), &sx, &sy)) return false;
		++stats.projected;
		const float dx = sx - 0.5f, dy = sy - 0.5f;
		const float screenDistance = std::sqrt(dx * dx + dy * dy);
		stats.nearestScreen = (std::min)(stats.nearestScreen, screenDistance);
		if (screenDistance > g_reconAimRadius) {
			++stats.radiusRejected;
			return false;
		}
		++stats.withinReticle;
		result.entity = entity;
		result.model = model;
		result.coords = coords;
		return true;
	};

	ReconPlantCandidate direct;
	if (evaluateEntity(reticleEntity, 0, direct)) {
		cachedEntity = direct.entity;
		cachedModel = direct.model;
		cachedAt = now;
		return direct;
	}
	if (cachedEntity && now - cachedAt <= 300) {
		ReconPlantCandidate cached;
		if (evaluateEntity(cachedEntity, cachedModel, cached)) return cached;
	}
	cachedEntity = 0;
	cachedModel = 0;
	cachedAt = 0;

	ReconPlantCandidate fallback;
	fallback.scenarioPoint = selectReconPlantScenarioPoint(playerPos, now, stats);
	if (fallback.scenarioPoint) {
		fallback.scenarioType = TASK::_GET_SCENARIO_POINT_TYPE(fallback.scenarioPoint);
		fallback.coords = TASK::_GET_SCENARIO_POINT_COORDS(fallback.scenarioPoint, TRUE);
	}
	return fallback;
}

struct ReconPedObservation {
	Ped ped = 0;
	float progress = 0.0f;
	DWORD lastSeenAt = 0;
	DWORD updatedAt = 0;
};

static void advanceReconStudyProgress(float& progress, DWORD& updatedAt,
	DWORD lastSeenAt, DWORD now, bool visible) {
	if (!updatedAt) { updatedAt = now; return; }
	if (now <= updatedAt) return;
	const DWORD elapsedMs = now - updatedAt;
	if (visible) {
		progress += (float)elapsedMs / (float)(std::max)(1, g_reconObserveMs);
	} else if (now > lastSeenAt + 150 &&
		g_reconCachedSettings.studyProgressDecayPercentPerSecond > 0.0f) {
		const DWORD decayFrom = (std::max)(updatedAt, lastSeenAt + 150);
		if (now > decayFrom) {
			const float seconds = (float)(now - decayFrom) / 1000.0f;
			progress -= seconds *
				g_reconCachedSettings.studyProgressDecayPercentPerSecond / 100.0f;
		}
	}
	progress = (std::max)(0.0f, (std::min)(1.0f, progress));
	updatedAt = now;
}

static float reconPedStudyProgress(const std::vector<ReconPedObservation>& observations, Ped ped) {
	for (const ReconPedObservation& item : observations)
		if (item.ped == ped) return item.progress;
	return 0.0f;
}

static void updateReconTagging(Ped playerPed, DWORD now, bool unavailable) {
	// Refresh the cached INI values once per 2 s, before anything draws. The
	// draw paths below must never touch the INI themselves; that is what froze
	// the game once a tag existed.
	reconRefreshCachedSettings(now);
	static Ped observed = 0;
	static DWORD observedAt = 0;
	static ReconPlantCandidate observedPlant;
	static float observedPlantProgress = 0.0f;
	static DWORD observedPlantLastSeenAt = 0;
	static DWORD observedPlantUpdatedAt = 0;
	static std::vector<ReconPedObservation> pedObservations;
	static Ped animalInfoTarget = 0;
	static DWORD lastScan = 0;
	static DWORD lastDiagnostic = 0;
	static bool booted = false;
	if (!booted) {
		booted = true;
		GtLogStream("recon", GT_INFO) << "Recon tagging session started\n";
	}
	// #96 IDLE HEARTBEAT. Every early return below used to be silent, so an empty
	// recon log could mean "the scan found nothing" OR "the scan never ran" - and
	// the previous #96 attempt read `plantobj=0` as the former when it may have
	// been the latter. The heartbeat makes silence provable: if no line appears
	// at all, this module is not executing.
	static DWORD lastHeartbeat = 0;
	auto heartbeat = [&](const char* state) {
		if (now - lastHeartbeat < 5000) return;
		lastHeartbeat = now;
		char line[288];
		sprintf_s(line, "idle state=%s enabled=%d unavailable=%d ped=%d bino=%d"
			" plantTypes=%d pedTags=%d plantTags=%d"
			" parts=minimap:%d,markers:%d,blips:%d,plants:%d",
			state, g_reconTaggingEnabled ? 1 : 0, unavailable ? 1 : 0,
			playerPed ? 1 : 0, g_binocularsActive ? 1 : 0,
			(int)g_plantModels.size(), (int)g_reconTargets.size(),
			(int)g_reconObjectTargets.size(),
			g_reconCachedSettings.partMinimap, g_reconCachedSettings.partMarkers,
			g_reconCachedSettings.partBlips, g_reconCachedSettings.partPlants);
		reconLog(line);
	};

	if (!g_reconTaggingEnabled || unavailable || !playerPed) {
		observed = 0; observedAt = 0;
		observedPlant = {};
		observedPlantProgress = 0.0f;
		observedPlantLastSeenAt = 0;
		observedPlantUpdatedAt = 0;
		pedObservations.clear();
		animalInfoTarget = 0;
		updateReconAnimalInfoBoxBridge(PLAYER::PLAYER_ID(), 0, false, now);
		heartbeat(!g_reconTaggingEnabled ? "disabled" :
			unavailable ? "unavailable" : "noplayer");
		updateReconPrompt(playerPed, 0, 0.0f, false);
		if (!g_reconTaggingEnabled) clearReconTargets();
		return;
	}
	// Rockstar commits weapon-wheel/horse selections after the visible wheel
	// closes. Do not create/remove/rotate blips, scan scenarios or draw overlays
	// anywhere inside that transaction. The exact remaining crash captures were
	// in this state, and recon has no player-facing work that belongs there.
	if (weaponWheelTransactionBusy(now)) {
		observed = 0;
		observedAt = 0;
		observedPlant = {};
		observedPlantProgress = 0.0f;
		observedPlantLastSeenAt = 0;
		observedPlantUpdatedAt = 0;
		pedObservations.clear();
		animalInfoTarget = 0;
		updateReconAnimalInfoBoxBridge(PLAYER::PLAYER_ID(), 0, false, now);
		updateReconPrompt(playerPed, 0, 0.0f, false);
		heartbeat("weaponwheel");
		return;
	}
	updateReconCompendiumStudies(now);
	reconEnsureBlipTextures(now);
	if (!g_plantModelsLoaded) loadPlantModels();
	static DWORD nextHorseRefresh = 0;
	if (now >= nextHorseRefresh) {
		nextHorseRefresh = now + 1000;
		ensurePlayerHorseReconTarget(playerPed, now);
	}
	const bool reconBlipsActive = g_reconBlipsEnabled &&
		g_reconCachedSettings.partBlips != 0;
	static DWORD nextTagMaintenance = 0;
	const bool maintainTags = now >= nextTagMaintenance;
	if (maintainTags) nextTagMaintenance = now + 250;
	const Vector3 playerPos = ENTITY_COORDS(playerPed);

	// Cull dead/despawned peds and draw every remaining marker every frame.
	for (size_t i = 0; i < g_reconTargets.size();) {
		ReconTarget& tag = g_reconTargets[i];
		if (!ENTITY::DOES_ENTITY_EXIST(tag.ped) || PED::IS_PED_DEAD_OR_DYING(tag.ped, TRUE)) {
			removeReconTarget(tag);
			g_reconTargets.erase(g_reconTargets.begin() + i);
			continue;
		}
		if (maintainTags) {
			const int relation = PED::GET_RELATIONSHIP_BETWEEN_PEDS(tag.ped, playerPed);
			const bool inCombat = PED::IS_PED_IN_COMBAT(tag.ped, playerPed) != 0;
			const ReconDisposition observedDisposition =
				reconDispositionFromObservation(relation, inCombat);
			if (observedDisposition == ReconDisposition::Enemy) tag.enemyLatched = true;
			else if (observedDisposition == ReconDisposition::Ally) tag.enemyLatched = false;
			const ReconDisposition stableDisposition =
				tag.enemyLatched ? ReconDisposition::Enemy : observedDisposition;
			if (!tag.playerHorse && stableDisposition != tag.disposition) {
				const ReconDisposition previousDisposition = tag.disposition;
				tag.disposition = stableDisposition;
				// A blip's style is fixed at creation. Recreate only after the
				// stable, hostility-latched state really changes; transient combat
				// task dropouts no longer alternate red and grey at range.
				removeReconTarget(tag);
				++tag.blipRecreateCount;
				char dispositionLine[224] = {};
				sprintf_s(dispositionLine,
					"blip disposition ped=%d previous=%d observed=%d stable=%d relation=%d combat=%d enemyLatched=%d recreates=%d",
					(int)tag.ped, (int)previousDisposition,
					(int)observedDisposition, (int)stableDisposition, relation,
					inCombat ? 1 : 0, tag.enemyLatched ? 1 : 0,
					tag.blipRecreateCount);
				reconLog(dispositionLine);
			}
		}
		if (maintainTags && tag.blip && !MAP::DOES_BLIP_EXIST(tag.blip)) {
			tag.blip = 0;
		}
		if (maintainTags && reconBlipsActive && !tag.blip && !tag.playerHorse) {
			tag.blip = MAP::_BLIP_ADD_FOR_ENTITY(reconBlipStyle(tag.ped, tag.disposition), tag.ped);
			if (tag.blip && MAP::DOES_BLIP_EXIST(tag.blip)) {
				configureReconBlip(tag.blip, tag.ped, tag.disposition);
			}
		}
		if (maintainTags && !reconBlipsActive && tag.blip) removeReconTarget(tag);
		const int displayOpacity = reconTagDisplayOpacity(
			playerPos, ENTITY_COORDS(tag.ped));
		if (displayOpacity > 0 &&
			!(tag.playerHorse && PED::GET_MOUNT(playerPed) == tag.ped))
			drawReconMarker(tag.ped, tag.disposition, playerPed,
				tag.playerHorse, displayOpacity);
		++i;
	}
	// PartPlants is a complete kill switch for the scenario-point half. Remove
	// existing plant state too, so a hot reload cannot leave stale markers or
	// blips behind and muddy the isolation result.
	if (g_reconCachedSettings.partPlants == 0 && !g_reconObjectTargets.empty()) {
		for (ReconObjectTarget& tag : g_reconObjectTargets)
			if (tag.blip && MAP::DOES_BLIP_EXIST(tag.blip)) MAP::REMOVE_BLIP(&tag.blip);
		g_reconObjectTargets.clear();
	}
	// #113(d): keep plant tags alive and drawn on the same terms as ped tags.
	for (size_t i = 0; i < g_reconObjectTargets.size();) {
		ReconObjectTarget& tag = g_reconObjectTargets[i];
		// Entity-backed tags require the same model to remain on the same live
		// handle. Scenario fallback tags require the point to remain live. Either
		// condition removes a plant immediately after it is picked/replaced.
		const bool liveEntity = tag.entity && ENTITY::DOES_ENTITY_EXIST(tag.entity) &&
			ENTITY_MODEL(tag.entity) == tag.model;
		const bool liveScenario = tag.scenarioPoint &&
			TASK::_DOES_SCENARIO_POINT_EXIST(tag.scenarioPoint);
		if (!liveEntity && !liveScenario) {
			if (tag.blip && MAP::DOES_BLIP_EXIST(tag.blip)) MAP::REMOVE_BLIP(&tag.blip);
			g_reconObjectTargets.erase(g_reconObjectTargets.begin() + i);
			continue;
		}
		tag.coords = liveEntity ? ENTITY_COORDS(tag.entity) :
			TASK::_GET_SCENARIO_POINT_COORDS(tag.scenarioPoint, TRUE);
		if (tag.blip && !MAP::DOES_BLIP_EXIST(tag.blip)) tag.blip = 0;
		if (reconBlipsActive && !tag.blip)
			// A plant has no durable entity handle, so the minimap marker is a
			// coord blip. MAP::_BLIP_ADD_FOR_COORD 0x554D9D53F696D002
			// natives.h:2809. BLIP_PLANT is the vanilla plant blip style,
			// declared in MyOverhaul/blipdata.ymt.
			tag.blip = MAP::_BLIP_ADD_FOR_COORD(joaat("BLIP_PLANT"),
				tag.coords.x, tag.coords.y, tag.coords.z);
		if (!reconBlipsActive && tag.blip && MAP::DOES_BLIP_EXIST(tag.blip))
			MAP::REMOVE_BLIP(&tag.blip);
		const int displayOpacity = reconTagDisplayOpacity(playerPos, tag.coords);
		if (displayOpacity > 0)
			drawReconObjectMarker(tag.coords, displayOpacity);
		++i;
	}
	suppressUnmarkedHostileBlips(playerPed, now);

	Hash heldWeapon = 0;
	WEAPON::GET_CURRENT_PED_WEAPON(playerPed, &heldWeapon, TRUE, 0, FALSE);
	const bool binocularWeapon = heldWeapon &&
		WEAPON::_IS_WEAPON_BINOCULARS(heldWeapon);
	// Forced aim becomes true during the authored binocular draw. Recon must not
	// start fading a tag in until the scope camera is genuinely up; ordinary gun
	// aiming remains available outside binocular mode.
	const bool aiming = !binocularWeapon &&
		(PLAYER::IS_PLAYER_FREE_AIMING(PLAYER::PLAYER_ID()) ||
			CAM::IS_AIM_CAM_ACTIVE());
	const Entity reticleEntity = updateReconReticleProbe(playerPed,
		g_binocularsActive || aiming, now);
	if (!g_binocularsActive && !aiming) {
		observed = 0; observedAt = 0;
		for (size_t i = 0; i < pedObservations.size();) {
			ReconPedObservation& item = pedObservations[i];
			advanceReconStudyProgress(item.progress, item.updatedAt, item.lastSeenAt, now, false);
			if (item.progress <= 0.0f || !ENTITY::DOES_ENTITY_EXIST(item.ped)) {
				pedObservations.erase(pedObservations.begin() + i); continue;
			}
			++i;
		}
		if (observedPlant.valid()) {
			advanceReconStudyProgress(observedPlantProgress, observedPlantUpdatedAt,
				observedPlantLastSeenAt, now, false);
			if (observedPlantProgress <= 0.0f) {
				observedPlant = {}; observedPlantLastSeenAt = observedPlantUpdatedAt = 0;
			}
		}
		animalInfoTarget = 0;
		updateReconAnimalInfoBoxBridge(PLAYER::PLAYER_ID(), 0, false, now);
		heartbeat("notaiming");
		updateReconPrompt(playerPed, 0, 0.0f, false);
		return;
	}
	// Selection is intentionally throttled, but prompt fill is not. Updating the
	// prompt only on the old 75 ms scan cadence made a 900 ms Study appear as
	// twelve conspicuous chunks.
	updateReconAnimalInfoBoxBridge(PLAYER::PLAYER_ID(), animalInfoTarget,
		g_binocularsActive, now);
	if (now - lastScan < 75) {
		if (observed) {
			const bool tagged = isReconTagged(observed);
			const float progress = tagged ? 1.0f : reconPedStudyProgress(pedObservations, observed);
			updateReconPrompt(playerPed, observed, progress, tagged);
		}
		if (!observed && observedPlant.valid() && now - observedPlantLastSeenAt <= 150) {
			const float eased = std::pow((std::max)(0.0f,
				(std::min)(1.0f, observedPlantProgress)), 2.4f);
			drawReconObjectMarker(observedPlant.coords,
				20 + (int)std::lround(eased * 135.0f));
		}
		return;
	}
	lastScan = now;

	// #292: once Story owns a genuine Study target, inject that exact animal
	// directly into Recon's observation set. Do not send it through considerPed:
	// that helper is intentionally the ordinary Recon path and therefore keeps
	// its distance/projected-size/LOS/screen-radius gates for every other ped.
	const Ped studyTarget = reconRockstarStudyTarget(PLAYER::PLAYER_ID(),
		g_binocularsActive, now);
	const float fov = (std::max)(5.0f, CAM::GET_GAMEPLAY_CAM_FOV());
	Ped best = 0;
	float bestScreen = 999.0f;
	float nearestPedScreen = 999.0f;
	int pedRadiusRejected = 0;
	std::vector<std::pair<Ped, float>> visiblePeds;
	if (studyTarget) {
		visiblePeds.push_back({ studyTarget, 0.0f });
		nearestPedScreen = 0.0f;
		if (!isReconTagged(studyTarget)) {
			best = studyTarget;
			bestScreen = 0.0f;
		}
	}
	auto considerPed = [&](Ped candidate, float forcedScreenDistance) {
		if (!candidate || candidate == playerPed || PED::IS_PED_A_PLAYER(candidate) ||
			!ENTITY::DOES_ENTITY_EXIST(candidate) ||
			PED::IS_PED_DEAD_OR_DYING(candidate, TRUE)) return;
		const float distance = reconDistance(playerPos, ENTITY_COORDS(candidate));
		if (distance > g_reconMaxDistance ||
			reconProjectedExtent(candidate) < g_reconMinProjectedExtent ||
			!ENTITY::HAS_ENTITY_CLEAR_LOS_TO_ENTITY(playerPed, candidate, 17)) return;
		float screenDistance = forcedScreenDistance;
		if (screenDistance < 0.0f) {
			const Vector3 anchor = reconAnchor(candidate);
			float sx = 0.0f, sy = 0.0f;
			if (!GRAPHICS::GET_SCREEN_COORD_FROM_WORLD_COORD(anchor.x, anchor.y,
				anchor.z, &sx, &sy)) return;
			const float dx = sx - 0.5f, dy = sy - 0.5f;
			screenDistance = std::sqrt(dx * dx + dy * dy);
		}
		nearestPedScreen = (std::min)(nearestPedScreen, screenDistance);
		if (screenDistance > g_reconAimRadius) {
			++pedRadiusRejected;
			return;
		}
		for (const auto& seen : visiblePeds)
			if (seen.first == candidate) return;
		visiblePeds.push_back({ candidate, screenDistance });
		if (!isReconTagged(candidate) && screenDistance < bestScreen) {
			best = candidate;
			bestScreen = screenDistance;
		}
	};
	Entity aimedEntity = 0;
	PLAYER::GET_ENTITY_PLAYER_IS_FREE_AIMING_AT(PLAYER::PLAYER_ID(), &aimedEntity);
	if (!aimedEntity) aimedEntity = reticleEntity;
	if (aimedEntity && ENTITY::IS_ENTITY_A_PED(aimedEntity))
		considerPed((Ped)aimedEntity, 0.0f);
	int nearby[65] = {}; nearby[0] = 64;
	const int count = NEARBY_PEDS(playerPed, nearby);
	for (int i = 0; i < count && i < 64; ++i) {
		const Ped candidate = nearby[i + 1];
		considerPed(candidate, -1.0f);
	}
	// Keep the vanilla animal UI target independent of recon tag state. `best`
	// deliberately excludes an already-tagged ped, but Rockstar's InfoBox must
	// continue to work when the same animal is viewed again.
	Ped resolvedAnimalInfoTarget = 0;
	float resolvedAnimalInfoScreen = 999.0f;
	for (const auto& visible : visiblePeds) {
		if (!PED::IS_PED_HUMAN(visible.first) &&
			visible.second < resolvedAnimalInfoScreen) {
			resolvedAnimalInfoTarget = visible.first;
			resolvedAnimalInfoScreen = visible.second;
		}
	}
	animalInfoTarget = g_binocularsActive ? resolvedAnimalInfoTarget : 0;
	updateReconAnimalInfoBoxBridge(PLAYER::PLAYER_ID(), animalInfoTarget,
		g_binocularsActive, now);
	// Every valid ped inside the reticle owns an independent dwell clock. Rider
	// and mount (or a tight group) can therefore acquire together instead of the
	// nearest one monopolising the sole observation slot until it finishes.
	for (const auto& visible : visiblePeds) {
		const Ped candidate = visible.first;
		if (isReconTagged(candidate)) continue;
		auto it = std::find_if(pedObservations.begin(), pedObservations.end(),
			[candidate](const ReconPedObservation& item) {
				return item.ped == candidate;
			});
		if (it == pedObservations.end()) {
			pedObservations.push_back({ candidate, 0.0f, now, now });
		} else {
			advanceReconStudyProgress(it->progress, it->updatedAt, it->lastSeenAt, now, true);
			it->lastSeenAt = now;
			if (it->progress >= 1.0f)
				markReconTarget(playerPed, candidate, now);
		}
	}
	for (size_t i = 0; i < pedObservations.size();) {
		ReconPedObservation& item = pedObservations[i];
		if (item.lastSeenAt != now)
			advanceReconStudyProgress(item.progress, item.updatedAt, item.lastSeenAt, now, false);
		if (!ENTITY::DOES_ENTITY_EXIST(item.ped) || isReconTagged(item.ped) || item.progress <= 0.0f) {
			pedObservations.erase(pedObservations.begin() + i);
			continue;
		}
		++i;
	}
	// #113(d): plants and other world pickups. Only searched when no ped won
	// the reticle, so animals and people keep priority.
	// #96: plants are scenario points, so they are selected from the engine's
	// scenario index rather than from any entity pool. Only searched when no ped
	// won the reticle, so animals and people keep priority.
	ReconPlantCandidate bestPlant;
	ReconPlantScanStats plantStats;
	if (!best && g_reconTagPickups && g_reconCachedSettings.partPlants != 0)
		bestPlant = selectReconPlant(aimedEntity, playerPos, now, plantStats);
	if (now - lastDiagnostic >= 1000) {
		lastDiagnostic = now;
		// The scan line names every entity class it consulted and, for plants,
		// how many candidates survived each individual gate. A rejected species
		// reports its scenario-type hash, so a genuinely missing WB_ entry can be
		// identified from the log instead of guessed at.
		char log[640];
		sprintf_s(log,
			"scan active=1 bino=%d aim=%d classes=ped,plant_visual,scenario_point"
			" peds=%d aimed=%d aimedModel=0x%08x bestPed=%d"
			" pedNearestScreen=%.6f pedBestScreen=%.6f pedRadiusRejected=%d"
			" plantVisuals=%d visualModels=%d"
			" plantPoints=%d exist=%d typed=%d inRange=%d projected=%d"
			" reticle=%d plantNearestScreen=%.6f plantRadiusRejected=%d"
			" alreadyTagged=%d rejectedType=0x%08x bestPlant=%d"
			" plantsOnly=%d fov=%.1f apparent=%.3f radius=%.3f",
			g_binocularsActive ? 1 : 0, aiming ? 1 : 0, count,
			aimedEntity ? 1 : 0, aimedEntity ? ENTITY_MODEL(aimedEntity) : 0,
			best ? 1 : 0,
			nearestPedScreen < 998.0f ? nearestPedScreen : -1.0f,
			bestScreen < 998.0f ? bestScreen : -1.0f, pedRadiusRejected,
			plantStats.visualCandidates, plantStats.visualModels,
			plantStats.enumerated, plantStats.existing, plantStats.typedPlant,
			plantStats.inRange, plantStats.projected, plantStats.withinReticle,
			plantStats.nearestScreen < 998.0f ? plantStats.nearestScreen : -1.0f,
			plantStats.radiusRejected,
			plantStats.alreadyTagged, plantStats.nearestRejectedType,
			bestPlant.valid() ? 1 : 0, g_reconPlantsOnly ? 1 : 0,
			fov, g_reconMinProjectedExtent, g_reconAimRadius);
		reconLog(log);
	}
	if (best != observed) {
		observed = best;
		auto it = std::find_if(pedObservations.begin(), pedObservations.end(),
			[best](const ReconPedObservation& item) { return item.ped == best; });
		observedAt = now;
		updateReconPrompt(playerPed, best, 0.0f, best && isReconTagged(best));
		return;
	}
	if (best) {
		const bool tagged = isReconTagged(best);
		const float progress = tagged ? 1.0f : reconPedStudyProgress(pedObservations, best);
		updateReconPrompt(playerPed, best, progress, tagged);
	} else {
		updateReconPrompt(playerPed, 0, 0.0f, false);
	}
	// #96: same reticle, same dwell, same feedback. Prefer the validated visual
	// entity and fall back to a typed scenario point only when no visual resolves.
	auto samePlant = [](const ReconPlantCandidate& a,
		const ReconPlantCandidate& b) {
		return (a.entity && b.entity && a.entity == b.entity && a.model == b.model) ||
			(a.scenarioPoint && b.scenarioPoint &&
				a.scenarioPoint == b.scenarioPoint);
	};
	if ((!bestPlant.valid() || best) && observedPlant.valid()) {
		advanceReconStudyProgress(observedPlantProgress, observedPlantUpdatedAt,
			observedPlantLastSeenAt, now, false);
		if (observedPlantProgress <= 0.0f) {
			observedPlant = {}; observedPlantLastSeenAt = observedPlantUpdatedAt = 0;
		}
	}
	if (!best && bestPlant.valid()) {
		if (!samePlant(bestPlant, observedPlant)) {
			observedPlant = bestPlant;
			observedPlantProgress = 0.0f;
			observedPlantLastSeenAt = now;
			observedPlantUpdatedAt = now;
		} else {
			advanceReconStudyProgress(observedPlantProgress, observedPlantUpdatedAt,
				observedPlantLastSeenAt, now, true);
			observedPlantLastSeenAt = now;
		}
		if (observedPlantProgress >= 1.0f &&
			(int)g_reconObjectTargets.size() < g_reconMaxTags) {
			ReconObjectTarget tag;
			tag.entity = bestPlant.entity;
			tag.model = bestPlant.model;
			tag.scenarioPoint = bestPlant.scenarioPoint;
			tag.scenarioType = bestPlant.scenarioType;
			tag.coords = bestPlant.coords;
			tag.markedAt = now;
			if (reconBlipsActive)
				tag.blip = MAP::_BLIP_ADD_FOR_COORD(joaat("BLIP_PLANT"),
					tag.coords.x, tag.coords.y, tag.coords.z);
			g_reconObjectTargets.push_back(tag);
			AUDIO::PLAY_SOUND_FRONTEND("SELECT", "HUD_SHOP_SOUNDSET", TRUE, 0);
			observedPlant = {};
			observedPlantProgress = 0.0f;
			observedPlantLastSeenAt = observedPlantUpdatedAt = 0;
			char log[256];
			sprintf_s(log, "marked plant entity=%d model=0x%08x scenarioPoint=%d type=0x%08x blip=%d distance=%.1f",
				(int)tag.entity, tag.model, tag.scenarioPoint, tag.scenarioType, (int)tag.blip,
				reconDistance(playerPos, tag.coords));
			reconLog(log);
		}
	} else if (!bestPlant.valid() && observedPlantProgress <= 0.0f) {
		observedPlant = {};
		observedPlantProgress = 0.0f;
		observedPlantLastSeenAt = observedPlantUpdatedAt = 0;
	}
}
