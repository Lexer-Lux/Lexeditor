// Issue #22: unified crafting presentation and runtime-defined custom recipes.
//
// Vanilla recipes are a read-only
// snapshot used for the unified list; selecting one hands control back to the
// already-running Rockstar crafting app so vanilla crafting logic, challenges,
// animations and recipe data remain untouched.  Custom rows transact directly
// against inventory with validation and rollback.

#include <cctype>
#include <map>

struct CustomCraftingPart {
	std::string itemName;
	Hash item = 0;
	int quantity = 1;
};

struct CustomCraftingRecipe {
	std::string id;
	std::string category;
	std::string title;
	std::string description;
	std::string station;
	std::string outputName;
	Hash output = 0;
	int outputQuantity = 1;
	std::vector<CustomCraftingPart> ingredients;
	std::string unlock;
	bool vanilla = false;
};

static std::vector<CustomCraftingRecipe> g_customCraftingRecipes;
static std::map<std::string, std::string> g_customCraftingItemLabels;
static bool g_customCraftingMenuOpen = false;
static bool g_customCraftingBypassVanilla = false;
static int g_customCraftingSelection = 0;
static DWORD g_customCraftingNextInputAt = 0;
static DWORD g_customCraftingNextReloadAt = 0;
static DWORD g_customCraftingReadySince = 0;
static std::string g_customCraftingNotice;
static DWORD g_customCraftingNoticeUntil = 0;
static DWORD g_customCraftingNextHeartbeatAt = 0;
static bool g_customCraftingLastAppActive = false;
static bool g_customCraftingLastAppReady = false;
static bool g_customCraftingConflictChecked = false;
static bool g_customCraftingConflictingMenuLoaded = false;
static bool g_customCraftingThreadsPaused = false;
static bool g_customCraftingInputArmed = false;
static bool g_customCraftingHandoffPending = false;
static std::string g_customCraftingHandoffReason;
static unsigned long long g_customCraftingDiscardedVanillaEvents = 0;
static DWORD g_customCraftingNextDrainWarningAt = 0;

// #126: routed to the unified GameplayTweaks.log under subsystem "crafting".
static void customCraftingTrace(GtLogLevel level, const std::string& event) {
	gtLog("crafting", level, event);
}

static std::string customCraftingHumanize(const std::string& value) {
	std::string result, word;
	auto flush = [&]() {
		if (word.empty()) return;
		if (!result.empty()) result += " ";
		for (size_t i = 0; i < word.size(); ++i) {
			char c = (char)std::tolower((unsigned char)word[i]);
			if (i == 0) c = (char)std::toupper((unsigned char)c);
			result += c;
		}
		word.clear();
	};
	for (char c : value) { if (c == '_') flush(); else word += c; }
	flush();
	return result.empty() ? value : result;
}

static std::string customCraftingItemLabel(const std::string& item) {
	const auto found = g_customCraftingItemLabels.find(item);
	return found == g_customCraftingItemLabels.end() ?
		customCraftingHumanize(item) : found->second;
}

static std::string customCraftingCategoryLabel(const std::string& category) {
	static const std::map<std::string, std::string> labels = {
		{ "CI_CATEGORY_AMMO", "Ammunition" }, { "CI_CATEGORY_AMMO_LONGARM", "Longarm Ammunition" },
		{ "CI_CATEGORY_AMMO_SIDEARM", "Sidearm Ammunition" }, { "CI_CATEGORY_MATERIALS", "Materials" },
		{ "CI_CATEGORY_PROVISION", "Provisions" }, { "CI_CATEGORY_WARDROBE_BOOTS", "Boots" },
		{ "CI_CATEGORY_WARDROBE_GLOVES", "Gloves" }, { "CI_CATEGORY_WARDROBE_HAT", "Hats" },
		{ "CI_CATEGORY_WARDROBE_VEST", "Vests" },
	};
	const auto found = labels.find(category);
	return found == labels.end() ? customCraftingHumanize(category) : found->second;
}

static std::string customCraftingStationLabel(const std::string& station) {
	static const std::map<std::string, std::string> labels = {
		{ "CUSTOM_ANY", "Anywhere" }, { "COST_CRAFTING", "Portable crafting" },
		{ "COST_CRAFTING_2", "Portable crafting" }, { "COST_CRAFTING_3", "Portable crafting" },
		{ "COST_CRAFTING_4", "Portable crafting" }, { "COST_CRAFTING_FIRE", "Campfire" },
		{ "COST_CRAFTING_GRILL", "Grill" }, { "COST_CRAFTING_KNIFE", "Campfire" },
		{ "COST_CRAFTING_TRAPPER", "Trapper" }, { "COST_CRAFTING_FENCE", "Fence" },
		{ "COST_CRAFTING_PEARSON", "Pearson" },
	};
	const auto found = labels.find(station);
	return found == labels.end() ? customCraftingHumanize(station) : found->second;
}

static std::string customCraftingTrim(const std::string& value) {
	const size_t first = value.find_first_not_of(" \t\r\n");
	if (first == std::string::npos) return "";
	const size_t last = value.find_last_not_of(" \t\r\n");
	return value.substr(first, last - first + 1);
}

static std::string customCraftingEllipsis(const std::string& value, size_t limit) {
	if (value.size() <= limit) return value;
	if (limit <= 3) return value.substr(0, limit);
	return value.substr(0, limit - 3) + "...";
}

static std::string customCraftingFriendlyKey(const std::string& value, size_t limit) {
	std::string result = value;
	static const char* prefixes[] = { "CI_CATEGORY_", "COST_CRAFTING_", "COST_CRAFTING", "PROVISION_", "CONSUMABLE_" };
	for (const char* prefix : prefixes) {
		const size_t length = std::strlen(prefix);
		if (result.compare(0, length, prefix) == 0) {
			result.erase(0, length);
			break;
		}
	}
	for (char& character : result) if (character == '_') character = ' ';
	return customCraftingEllipsis(result, limit);
}

static std::vector<std::string> customCraftingSplit(const std::string& value, char delimiter) {
	std::vector<std::string> result;
	std::string current;
	std::istringstream stream(value);
	while (std::getline(stream, current, delimiter)) result.push_back(customCraftingTrim(current));
	if (!value.empty() && value.back() == delimiter) result.push_back("");
	return result;
}

static bool customCraftingPositiveInt(const std::string& value, int* out) {
	if (!out || value.empty()) return false;
	char* end = nullptr;
	const long parsed = std::strtol(value.c_str(), &end, 10);
	if (!end || *end || parsed < 1 || parsed > 1000000) return false;
	*out = (int)parsed;
	return true;
}

static Hash customCraftingHash(const std::string& value) {
	// OpenIV exports unresolved catalog, cost and unlock identifiers as literal
	// 0x######## keys. Hashing that text produces a different identifier and
	// made dozens of otherwise valid vanilla rows show the wrong owned/output
	// state. Symbolic names still use JOAAT.
	if (value.size() == 10 && value[0] == '0' && (value[1] == 'x' || value[1] == 'X')) {
		char* end = nullptr;
		const unsigned long parsed = std::strtoul(value.c_str() + 2, &end, 16);
		if (end && *end == '\0') return (Hash)parsed;
	}
	return joaat(value.c_str());
}

static bool customCraftingReadFile(const std::string& path, bool vanilla,
	std::vector<CustomCraftingRecipe>* destination, std::string* error) {
	std::ifstream input(path);
	if (!input) {
		if (!vanilla) return true; // optional when LEXEDITOR has not created it yet
		if (error) *error = "Missing vanilla recipe snapshot";
		return false;
	}
	std::string line;
	if (!std::getline(input, line)) return true;
	const std::vector<std::string> header = customCraftingSplit(line, '\t');
	static const char* expected[] = { "recipe_id", "category", "title", "description",
		"station", "output_item", "output_quantity", "ingredients", "unlock" };
	if (header.size() != 9) {
		if (error) *error = "Recipe table has the wrong number of columns";
		return false;
	}
	for (size_t i = 0; i < 9; ++i) if (header[i] != expected[i]) {
		if (error) *error = "Recipe table header mismatch";
		return false;
	}
	int row = 1;
	while (std::getline(input, line)) {
		++row;
		if (customCraftingTrim(line).empty()) continue;
		const std::vector<std::string> fields = customCraftingSplit(line, '\t');
		if (fields.size() != 9) {
			if (error) *error = "Malformed recipe row " + std::to_string(row);
			return false;
		}
		CustomCraftingRecipe recipe;
		recipe.id = fields[0]; recipe.category = fields[1]; recipe.title = fields[2];
		recipe.description = fields[3]; recipe.station = fields[4];
		recipe.outputName = fields[5]; recipe.output = customCraftingHash(fields[5]);
		recipe.unlock = fields[8]; recipe.vanilla = vanilla;
		if (recipe.id.empty() || recipe.title.empty() || recipe.outputName.empty() ||
			!customCraftingPositiveInt(fields[6], &recipe.outputQuantity)) {
			if (error) *error = "Invalid recipe row " + std::to_string(row);
			return false;
		}
		for (const std::string& encoded : customCraftingSplit(fields[7], ';')) {
			if (encoded.empty()) continue;
			const size_t star = encoded.rfind('*');
			CustomCraftingPart part;
			part.itemName = customCraftingTrim(encoded.substr(0, star));
			if (star == std::string::npos || part.itemName.empty() ||
				!customCraftingPositiveInt(encoded.substr(star + 1), &part.quantity)) {
				if (error) *error = "Invalid ingredient on row " + std::to_string(row);
				return false;
			}
			part.item = customCraftingHash(part.itemName);
			recipe.ingredients.push_back(part);
		}
		if (recipe.ingredients.empty()) {
			if (error) *error = "Recipe row " + std::to_string(row) + " has no ingredients";
			return false;
		}
		destination->push_back(recipe);
	}
	return true;
}

static void customCraftingReadLabels(const std::string& path) {
	std::ifstream input(path);
	if (!input) return;
	std::map<std::string, std::string> replacement;
	std::string line;
	if (!std::getline(input, line) || customCraftingTrim(line) != "item_id\tdisplay_name")
		return;
	while (std::getline(input, line)) {
		const size_t tab = line.find('\t');
		if (tab == std::string::npos) continue;
		const std::string key = customCraftingTrim(line.substr(0, tab));
		const std::string label = customCraftingTrim(line.substr(tab + 1));
		if (!key.empty() && !label.empty()) replacement[key] = label;
	}
	if (!replacement.empty()) g_customCraftingItemLabels.swap(replacement);
}

static void customCraftingReload(DWORD now) {
	if (now < g_customCraftingNextReloadAt) return;
	g_customCraftingNextReloadAt = now + 2000;
	std::vector<CustomCraftingRecipe> replacement;
	std::string error;
	const bool vanilla = customCraftingReadFile(g_moduleDir + "\\vanilla_crafting_recipes.tsv",
		true, &replacement, &error);
	const bool custom = vanilla && customCraftingReadFile(g_moduleDir + "\\custom_crafting_recipes.tsv",
		false, &replacement, &error);
	if (!vanilla || !custom) {
		g_customCraftingNotice = error;
		g_customCraftingNoticeUntil = now + 5000;
		return; // keep the last known-good complete pair
	}
	g_customCraftingRecipes.swap(replacement);
	customCraftingReadLabels(g_moduleDir + "\\custom_crafting_item_labels.tsv");
	if (g_customCraftingSelection >= (int)g_customCraftingRecipes.size())
		g_customCraftingSelection = (std::max)(0, (int)g_customCraftingRecipes.size() - 1);
}

static void customCraftingText(const std::string& text, float x, float y, float scale,
	int r = 245, int g = 245, int b = 245, int a = 255) {
	HUD::SET_TEXT_SCALE(scale, scale);
	HUD::_SET_TEXT_COLOR(r, g, b, a);
	HUD::SET_TEXT_CENTRE(FALSE);
	HUD::SET_TEXT_DROPSHADOW(1, 0, 0, 0, 220);
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", text.c_str()), x, y);
}

static void customCraftingWrappedText(const std::string& text, float x, float y,
	float scale, size_t width, int maximumLines, int r, int g, int b) {
	std::istringstream words(text);
	std::string word, line;
	int row = 0;
	while (words >> word && row < maximumLines) {
		if (!line.empty() && line.size() + 1 + word.size() > width) {
			customCraftingText(line, x, y + row * 0.032f, scale, r, g, b);
			line.clear();
			++row;
		}
		if (row >= maximumLines) break;
		if (!line.empty()) line += " ";
		line += word;
	}
	if (!line.empty() && row < maximumLines)
		customCraftingText(line, x, y + row * 0.032f, scale, r, g, b);
}

static bool customCraftingPressed(Hash control) {
	return PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, control) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, control) ||
		PAD::IS_CONTROL_JUST_PRESSED(0, control) ||
		PAD::IS_CONTROL_JUST_PRESSED(2, control);
}

static bool customCraftingCancelPressed() {
	if (customCraftingPressed(joaat("INPUT_FRONTEND_CANCEL")) ||
		customCraftingPressed(joaat("INPUT_GAME_MENU_CANCEL")) ||
		customCraftingPressed(joaat("INPUT_FRONTEND_KEYMAPPING_CANCEL")) ||
		customCraftingPressed(joaat("INPUT_FRONTEND_PAUSE_ALTERNATE")) ||
		(GetAsyncKeyState(VK_ESCAPE) & 1) || (GetAsyncKeyState(VK_BACK) & 1))
		return true;
	static bool padLatch = false;
	const bool padDown = padButtonDown(XINPUT_GAMEPAD_B);
	const bool pressed = padDown && !padLatch;
	padLatch = padDown;
	return pressed;
}

static void customCraftingDisableControls() {
	static const char* controls[] = {
		"INPUT_GAME_MENU_UP", "INPUT_GAME_MENU_DOWN", "INPUT_GAME_MENU_LEFT",
		"INPUT_GAME_MENU_RIGHT", "INPUT_GAME_MENU_ACCEPT", "INPUT_GAME_MENU_CANCEL",
		"INPUT_FRONTEND_UP", "INPUT_FRONTEND_DOWN", "INPUT_FRONTEND_LEFT",
		"INPUT_FRONTEND_RIGHT", "INPUT_FRONTEND_ACCEPT", "INPUT_FRONTEND_CANCEL",
		"INPUT_FRONTEND_KEYMAPPING_CANCEL", "INPUT_FRONTEND_PAUSE_ALTERNATE",
		"INPUT_CRAFTING_CRAFT", "INPUT_CRAFTING_EAT"
	};
	for (const char* control : controls) for (int group = 0; group < 3; ++group)
		PAD::DISABLE_CONTROL_ACTION(group, joaat(control), FALSE);
}

static bool customCraftingOwnedInputDown() {
	static const char* controls[] = {
		"INPUT_GAME_MENU_ACCEPT", "INPUT_GAME_MENU_CANCEL",
		"INPUT_FRONTEND_ACCEPT", "INPUT_FRONTEND_CANCEL",
		"INPUT_FRONTEND_KEYMAPPING_CANCEL", "INPUT_FRONTEND_PAUSE_ALTERNATE",
		"INPUT_CRAFTING_CRAFT", "INPUT_CRAFTING_EAT"
	};
	for (const char* control : controls) for (int group = 0; group < 3; ++group) {
		const Hash hash = joaat(control);
		if (PAD::IS_CONTROL_PRESSED(group, hash) ||
			PAD::IS_DISABLED_CONTROL_PRESSED(group, hash)) return true;
	}
	return (GetAsyncKeyState(VK_RETURN) & 0x8000) != 0 ||
		(GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0 ||
		(GetAsyncKeyState(VK_BACK) & 0x8000) != 0 ||
		padButtonDown(XINPUT_GAMEPAD_A) || padButtonDown(XINPUT_GAMEPAD_B);
}

static bool customCraftingDrainRockstarEvents(DWORD now) {
	// All three Story owners drain this exact CRAFTING event channel:
	// simple_crafting.c:743-764, interactive_campfire.c:18119-18140 and
	// player_camp.c:28532-28553. While those script threads are paused, this
	// replacement owns and discards the queue so overlay navigation/accept can
	// never become a delayed vanilla craft after ownership is returned.
	static const Hash kCraftingEventChannel = (Hash)-813979060;
	int drained = 0;
	while (drained < 64 && UIEVENTS::_EVENT_MANAGER_IS_EVENT_PENDING(kCraftingEventChannel)) {
		Any eventData = 0;
		if (!UIEVENTS::_EVENT_MANAGER_PEEK_EVENT(kCraftingEventChannel, &eventData))
			break;
		UIEVENTS::_EVENT_MANAGER_POP_EVENT(kCraftingEventChannel);
		++drained;
	}
	g_customCraftingDiscardedVanillaEvents += (unsigned long long)drained;
	const bool empty = !UIEVENTS::_EVENT_MANAGER_IS_EVENT_PENDING(kCraftingEventChannel);
	if (!empty && now >= g_customCraftingNextDrainWarningAt) {
		g_customCraftingNextDrainWarningAt = now + 2000;
		customCraftingTrace(GT_WARN,
			"isolation queue still pending after bounded drain; ownership retained");
	}
	return empty;
}

static bool customCraftingAcquireIsolation(DWORD now) {
	if (!g_customCraftingThreadsPaused) {
		// SDK natives.h:192-193 defines this native as pausing every script
		// thread except its caller. Rockstar uses the same balanced true/false
		// ownership in camera_photomode.c:1899-1905 and camera_item.c:2288-2294.
		ANIMSCENE::_PAUSE_SCRIPT_THREADS(TRUE);
		g_customCraftingThreadsPaused = true;
		customCraftingTrace(GT_INFO,
			"isolation acquired threadsPaused=1 callerContinued=1");
	}
	return customCraftingDrainRockstarEvents(now);
}

static bool customCraftingReleaseIsolation(DWORD now, const char* reason) {
	if (!g_customCraftingThreadsPaused) return true;
	// Never resume Story while a UI event created under replacement ownership is
	// still queued. A failed/busy bounded drain retains ownership for next frame.
	if (!customCraftingDrainRockstarEvents(now)) return false;
	ANIMSCENE::_PAUSE_SCRIPT_THREADS(FALSE);
	g_customCraftingThreadsPaused = false;
	customCraftingTrace(GT_INFO, std::string("isolation released reason=") + reason +
		" threadsPaused=0 discardedEvents=" +
		std::to_string(g_customCraftingDiscardedVanillaEvents));
	return true;
}

static void customCraftingBeginHandoff(const char* reason) {
	g_customCraftingHandoffPending = true;
	g_customCraftingHandoffReason = reason;
	g_customCraftingNotice = "Release the button to return to Rockstar crafting";
	g_customCraftingNoticeUntil = GetTickCount() + 3000;
	customCraftingTrace(GT_INFO, std::string("handoff armed reason=") + reason +
		" threadsPaused=" + (g_customCraftingThreadsPaused ? "1" : "0"));
}

static bool customCraftingUnlocked(const CustomCraftingRecipe& recipe) {
	if (recipe.unlock.empty()) return true;
	for (const std::string& unlock : customCraftingSplit(recipe.unlock, ';'))
		if (!unlock.empty() && !UNLOCKED(customCraftingHash(unlock))) return false;
	return true;
}

static int customCraftingAvailable(const CustomCraftingRecipe& recipe) {
	std::map<Hash, int> required;
	for (const CustomCraftingPart& part : recipe.ingredients)
		required[part.item] += part.quantity;
	int count = INT_MAX;
	for (const auto& part : required)
		count = (std::min)(count, INVENTORY_ITEM_COUNT(part.first) / part.second);
	return count == INT_MAX ? 0 : count;
}

static void customCraftingRestoreCount(Hash item, int target) {
	// Inventory natives can return false despite a delayed or partial mutation.
	// Rollback therefore restores the observed count, never merely the calls we
	// think succeeded. Bound the retries so a malformed catalog record cannot
	// stall the script thread.
	for (int attempt = 0; attempt < 4; ++attempt) {
		const int current = INVENTORY_ITEM_COUNT(item);
		if (current == target) return;
		if (current < target) INVENTORY_ADD(item, target - current);
		else INVENTORY_REMOVE(item, current - target);
	}
}

static bool customCraftingExecute(const CustomCraftingRecipe& recipe, std::string* notice) {
	if (!customCraftingUnlocked(recipe)) {
		if (notice) *notice = "Recipe not learned";
		return false;
	}
	std::map<Hash, int> required;
	std::map<Hash, std::string> names;
	for (const CustomCraftingPart& part : recipe.ingredients) {
		required[part.item] += part.quantity;
		names[part.item] = part.itemName;
	}
	for (const auto& part : required) if (INVENTORY_ITEM_COUNT(part.first) < part.second) {
		if (notice) *notice = "Missing " + names[part.first];
		return false;
	}
	std::map<Hash, int> before;
	for (const auto& part : required) before[part.first] = INVENTORY_ITEM_COUNT(part.first);
	const int outputBefore = INVENTORY_ITEM_COUNT(recipe.output);
	std::ostringstream beginProof;
	beginProof << "custom transaction begin id=" << recipe.id
		<< " threadsPaused=" << (g_customCraftingThreadsPaused ? 1 : 0)
		<< " outputBefore=" << outputBefore << " ingredients=";
	for (const auto& part : required)
		beginProof << part.first << ":" << before[part.first] << "/" << part.second << ",";
	customCraftingTrace(GT_INFO, beginProof.str());
	std::vector<Hash> touched;
	for (const auto& part : required) {
		INVENTORY_REMOVE(part.first, part.second);
		if (INVENTORY_ITEM_COUNT(part.first) != before[part.first] - part.second) {
			for (Hash item : touched) customCraftingRestoreCount(item, before[item]);
			customCraftingRestoreCount(part.first, before[part.first]);
			if (notice) *notice = "Inventory changed; ingredients restored";
			return false;
		}
		touched.push_back(part.first);
	}
	INVENTORY_ADD(recipe.output, recipe.outputQuantity);
	if (INVENTORY_ITEM_COUNT(recipe.output) != outputBefore + recipe.outputQuantity) {
		customCraftingRestoreCount(recipe.output, outputBefore);
		for (Hash item : touched) customCraftingRestoreCount(item, before[item]);
		if (notice) *notice = "No room for output; ingredients restored";
		return false;
	}
	if (notice) *notice = "Crafted " + recipe.title + " x" + std::to_string(recipe.outputQuantity);
	std::ostringstream successProof;
	successProof << "custom transaction committed id=" << recipe.id
		<< " outputAfter=" << INVENTORY_ITEM_COUNT(recipe.output) << " ingredientsAfter=";
	for (const auto& part : required)
		successProof << part.first << ":" << INVENTORY_ITEM_COUNT(part.first) << ",";
	customCraftingTrace(GT_INFO, successProof.str());
	return true;
}

static void customCraftingDraw(DWORD now) {
	// Keeping Rockstar's app alive preserves its exact station/context and lets
	// its Story script finish normally. The replacement must use the highest
	// script layer; the default layer is underneath the opaque vanilla page.
	invoke<Void>(0xCFCC78391C8B3814, 7); // SET_SCRIPT_GFX_DRAW_ORDER
	GRAPHICS::DRAW_RECT(0.5f, 0.5f, 1.0f, 1.0f, 12, 10, 8, 255, FALSE, FALSE);
	GRAPHICS::DRAW_RECT(0.5f, 0.065f, 1.0f, 0.13f, 76, 17, 12, 255, FALSE, FALSE);
	customCraftingText("CRAFTING", 0.055f, 0.035f, 0.55f);
	customCraftingText("VANILLA + CUSTOM RECIPES", 0.055f, 0.090f, 0.24f, 215, 192, 154);
	if (g_customCraftingRecipes.empty()) {
		customCraftingText("No recipes loaded", 0.055f, 0.18f, 0.34f);
		customCraftingText("ESC / BACK / B exit", 0.055f, 0.910f, 0.24f, 225, 205, 170);
		return;
	}
	const int count = (int)g_customCraftingRecipes.size();
	const int first = (std::max)(0, (std::min)(g_customCraftingSelection - 6, count - 13));
	for (int row = 0; row < 13 && first + row < count; ++row) {
		const int index = first + row;
		const CustomCraftingRecipe& recipe = g_customCraftingRecipes[index];
		const float y = 0.155f + row * 0.052f;
		if (index == g_customCraftingSelection)
			GRAPHICS::DRAW_RECT(0.287f, y + 0.014f, 0.48f, 0.046f, 115, 25, 17, 235, FALSE, FALSE);
		customCraftingText(customCraftingEllipsis(recipe.title, 34), 0.055f, y, 0.275f,
			customCraftingUnlocked(recipe) ? 245 : 135, customCraftingUnlocked(recipe) ? 245 : 135,
			customCraftingUnlocked(recipe) ? 245 : 135);
		const std::string badge = recipe.vanilla ? "VANILLA" : "CUSTOM";
		customCraftingText(badge, 0.455f, y, 0.205f, recipe.vanilla ? 180 : 220, 185, 145);
	}
	const CustomCraftingRecipe& selected = g_customCraftingRecipes[g_customCraftingSelection];
	GRAPHICS::DRAW_RECT(0.775f, 0.52f, 0.39f, 0.76f, 28, 24, 19, 250, FALSE, FALSE);
	customCraftingText(customCraftingEllipsis(selected.title, 36), 0.605f, 0.165f, 0.34f);
	customCraftingText(customCraftingCategoryLabel(selected.category) + " / " +
		customCraftingStationLabel(selected.station), 0.605f, 0.215f, 0.215f, 190, 174, 146);
	customCraftingText("Makes " + customCraftingEllipsis(
		customCraftingItemLabel(selected.outputName), 29) + " x" +
		std::to_string(selected.outputQuantity),
		0.605f, 0.270f, 0.25f, 225, 202, 160);
	customCraftingText("INGREDIENTS", 0.605f, 0.330f, 0.23f, 190, 174, 146);
	for (size_t i = 0; i < selected.ingredients.size() && i < 8; ++i) {
		const CustomCraftingPart& part = selected.ingredients[i];
		const int owned = INVENTORY_ITEM_COUNT(part.item);
		customCraftingText(customCraftingEllipsis(customCraftingItemLabel(part.itemName), 29) + "  " +
			std::to_string(owned) + "/" + std::to_string(part.quantity),
			0.605f, 0.370f + (float)i * 0.042f, 0.22f,
			owned >= part.quantity ? 225 : 225, owned >= part.quantity ? 220 : 90,
			owned >= part.quantity ? 205 : 80);
	}
	if (!selected.description.empty()) {
		std::string description = selected.description;
		if (description.size() > 150) description = description.substr(0, 147) + "...";
		customCraftingWrappedText(description, 0.605f, 0.735f, 0.205f,
			42, 3, 190, 184, 170);
	}
	const std::string action = selected.vanilla
		? "ENTER continue with Rockstar crafting"
		: (customCraftingAvailable(selected) > 0 ? "ENTER craft" : "Missing ingredients");
	customCraftingText(action + "   ESC / BACK / B exit", 0.055f, 0.910f, 0.24f, 225, 205, 170);
	customCraftingText(std::to_string(g_customCraftingSelection + 1) + " / " + std::to_string(count),
		0.470f, 0.910f, 0.22f, 175, 165, 150);
	if (now < g_customCraftingNoticeUntil)
		customCraftingText(g_customCraftingNotice, 0.605f, 0.860f, 0.23f, 235, 190, 115);
}

// Returns true while the custom presentation owns frontend input.
static bool updateCustomCraftingMenu(DWORD now) {
	customCraftingReload(now);
	if (!g_customCraftingConflictChecked) {
		g_customCraftingConflictChecked = true;
		g_customCraftingConflictingMenuLoaded = GetModuleHandleA("UCMO.asi") != nullptr;
		if (g_customCraftingConflictingMenuLoaded)
			customCraftingTrace(GT_ERROR, "disabled: UCMO.asi is also loaded");
	}
	// UCMO is another complete crafting-menu owner. Two ASIs consuming the same
	// controls and crafting lifecycle is not a supported composition; declining
	// ownership preserves Rockstar's script instead of creating another race.
	if (g_customCraftingConflictingMenuLoaded) return false;
	const Hash craftingApp = joaat("CRAFTING");
	const bool vanillaActive = UIAPP_ACTIVE(craftingApp);
	const bool vanillaReady = vanillaActive &&
		UISTATEMACHINE::_0xF7C180F57F85D0B8(craftingApp);
	const DWORD nowSeen = GetTickCount();
	if ((vanillaActive || g_customCraftingMenuOpen) && nowSeen >= g_customCraftingNextHeartbeatAt) {
		g_customCraftingNextHeartbeatAt = nowSeen + 2000;
		customCraftingTrace(GT_INFO,
			std::string("owner heartbeat app=") + (vanillaActive ? "1" : "0") +
			" ready=" + (vanillaReady ? "1" : "0") +
			" overlay=" + (g_customCraftingMenuOpen ? "1" : "0") +
			" threadsPaused=" + (g_customCraftingThreadsPaused ? "1" : "0") +
			" inputArmed=" + (g_customCraftingInputArmed ? "1" : "0") +
			" handoff=" + (g_customCraftingHandoffPending ? "1" : "0") +
			" bypass=" + (g_customCraftingBypassVanilla ? "1" : "0") +
			" conflict=" + (g_customCraftingConflictingMenuLoaded ? "1" : "0") +
			" drawOrder=7 recipes=" + std::to_string(g_customCraftingRecipes.size()) +
			" discardedEvents=" + std::to_string(g_customCraftingDiscardedVanillaEvents));
	}
	if (vanillaActive != g_customCraftingLastAppActive ||
		vanillaReady != g_customCraftingLastAppReady) {
		customCraftingTrace(GT_INFO, std::string("app active=") + (vanillaActive ? "1" : "0") +
			" ready=" + (vanillaReady ? "1" : "0"));
		g_customCraftingLastAppActive = vanillaActive;
		g_customCraftingLastAppReady = vanillaReady;
	}
	if (g_customCraftingBypassVanilla) {
		if (g_customCraftingThreadsPaused &&
			!customCraftingReleaseIsolation(nowSeen, "bypass repair")) return true;
		if (!vanillaActive) {
			g_customCraftingBypassVanilla = false;
			g_customCraftingReadySince = 0;
		}
		return false;
	}
	if (!vanillaActive && g_customCraftingThreadsPaused) {
		if (!customCraftingReleaseIsolation(nowSeen, "owner app disappeared")) return true;
		g_customCraftingMenuOpen = false;
		g_customCraftingInputArmed = false;
		g_customCraftingHandoffPending = false;
		g_customCraftingReadySince = 0;
		return false;
	}
	if (!g_customCraftingMenuOpen) {
		// CRAFTING becomes active while simple_crafting is still in state 8 and
		// disabling every control. A transient active frame is not a usable menu.
		// Wait until its state machine reports ready and remains ready long enough
		// for the owning script to advance to its interactive state 10.
		if (!vanillaReady) {
			if (g_customCraftingThreadsPaused &&
				!customCraftingReleaseIsolation(nowSeen, "owner no longer ready"))
				return true;
			g_customCraftingReadySince = 0;
			return false;
		}
		if (!g_customCraftingReadySince) {
			g_customCraftingReadySince = nowSeen;
			return false;
		}
		if (nowSeen - g_customCraftingReadySince < 100) return false;
		if (!customCraftingAcquireIsolation(nowSeen)) return true;
		g_customCraftingMenuOpen = true;
		g_customCraftingInputArmed = false;
		g_customCraftingSelection = 0;
		g_customCraftingNextInputAt = nowSeen + 180;
		customCraftingTrace(GT_INFO, "overlay opened after stable ready state threadsPaused=1 drawOrder=7 recipes=" +
			std::to_string(g_customCraftingRecipes.size()));
	}
	if (!vanillaActive) {
		// A close initiated by the owning script is authoritative. Never try to
		// resurrect or unwind its scenario from this presentation layer.
		g_customCraftingMenuOpen = false;
		g_customCraftingInputArmed = false;
		customCraftingReleaseIsolation(nowSeen, "owner app disappeared");
		g_customCraftingReadySince = 0;
		return false;
	}
	customCraftingDisableControls();
	if (!customCraftingDrainRockstarEvents(nowSeen)) return true;
	customCraftingDraw(now);
	// The CRAFTING app is opened by a held prompt. The returned live log proved
	// that reading cancel on the acquisition frame immediately closed this
	// replacement: open and handoff were logged at the same timestamp. Keep all
	// Story threads paused and accept no custom input until every input source
	// owned by this menu is physically released. customCraftingOwnedInputDown()
	// also samples the three explicit keyboard fallbacks, which clears any
	// stale GetAsyncKeyState edge before arming.
	if (!g_customCraftingInputArmed) {
		if (customCraftingOwnedInputDown()) return true;
		g_customCraftingInputArmed = true;
		g_customCraftingNextInputAt = nowSeen + 100;
		customCraftingTrace(GT_INFO,
			"input armed after all owned controls released threadsPaused=1 queueEmpty=1");
		return true;
	}
	if (g_customCraftingHandoffPending) {
		if (customCraftingOwnedInputDown()) return true;
		if (!customCraftingReleaseIsolation(nowSeen, g_customCraftingHandoffReason.c_str()))
			return true;
		g_customCraftingHandoffPending = false;
		g_customCraftingMenuOpen = false;
		g_customCraftingInputArmed = false;
		g_customCraftingBypassVanilla = true;
		g_customCraftingReadySince = 0;
		return false;
	}
	// Cancel arms a release-gated handoff. The Story owner remains paused and
	// its event queue is drained until every accept/cancel source is physically
	// released, so this press cannot become a delayed vanilla craft.
	if (customCraftingCancelPressed()) {
		customCraftingBeginHandoff("cancel");
		g_customCraftingNextInputAt = now + 180;
		return true;
	}
	if (now < g_customCraftingNextInputAt) return true;
	const bool up = customCraftingPressed(joaat("INPUT_FRONTEND_UP")) || customCraftingPressed(joaat("INPUT_GAME_MENU_UP"));
	const bool down = customCraftingPressed(joaat("INPUT_FRONTEND_DOWN")) || customCraftingPressed(joaat("INPUT_GAME_MENU_DOWN"));
	const bool accept = customCraftingPressed(joaat("INPUT_FRONTEND_ACCEPT")) || customCraftingPressed(joaat("INPUT_GAME_MENU_ACCEPT"));
	const int count = (int)g_customCraftingRecipes.size();
	if (up && count) g_customCraftingSelection = (g_customCraftingSelection + count - 1) % count;
	if (down && count) g_customCraftingSelection = (g_customCraftingSelection + 1) % count;
	if (up || down) g_customCraftingNextInputAt = now + 110;
	if (accept && count) {
		const CustomCraftingRecipe& recipe = g_customCraftingRecipes[g_customCraftingSelection];
		if (recipe.vanilla) {
			customCraftingTrace(GT_INFO, "accept vanilla selection=" +
				std::to_string(g_customCraftingSelection) + " id=" + recipe.id +
				" threadsPaused=1 queueEmpty=1");
			customCraftingBeginHandoff("vanilla selection");
		} else {
			customCraftingTrace(GT_INFO, "accept custom selection=" +
				std::to_string(g_customCraftingSelection) + " id=" + recipe.id +
				" threadsPaused=1 queueEmpty=1");
			customCraftingExecute(recipe, &g_customCraftingNotice);
			g_customCraftingNoticeUntil = now + 3000;
		}
		g_customCraftingNextInputAt = now + 180;
	}
	return true;
}
