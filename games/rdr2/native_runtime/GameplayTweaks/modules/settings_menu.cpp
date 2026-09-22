// GameplayTweaks feature module: #18 in-game editor for GameplayTweaks.ini.
//
// The menu reads current values from the INI at open time, but its presentation
// comes from the same generated settings_schema.json model as LEXEDITOR.  This
// prevents a second hard-coded taxonomy from drifting in category, subcategory,
// labels, booleans, lifecycle, validation, or alphabetical order.
//
// Renderer portions are adapted from RDR2 Native Menu Base:
// Copyright (c) 2021 Halen84, licensed under the MIT License.
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to inclusion of this copyright and permission
// notice. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO MERCHANTABILITY, FITNESS FOR
// A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
// COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY.

#include <cctype>
#include <cstdlib>
#include <cstring>
#include "settings_menu_schema.generated.h"

struct SettingsMenuEntry {
	std::string section;
	std::string key;
	std::string subcategory;
	std::string label;
	std::string value;
	std::string help;
	std::string unit;
	std::string constBoundary;
	std::vector<std::string> choiceValues;
	std::vector<std::string> choiceLabels;
	bool booleanValue = false;
	bool developerValue = false;
	bool constValue = false;
	bool hasRange = false;
	double minimum = 0.0;
	double maximum = 0.0;
	double step = 0.0;
};

struct SettingsMenuSection {
	std::string name;
	std::vector<SettingsMenuEntry> entries;
};

static std::vector<SettingsMenuSection> g_settingsMenuSections;
static bool g_settingsMenuOpen = false;
static bool g_settingsMenuEditing = false;
static bool g_settingsMenuAtSections = true;
static int g_settingsMenuSection = 0;
static int g_settingsMenuSelection = 0;
static bool g_settingsMenuF8WasDown = false;
static DWORD g_settingsMenuNextInputAt = 0;

static std::string settingsMenuTrim(const std::string& text) {
	size_t first = text.find_first_not_of(" \t\r\n");
	if (first == std::string::npos) return "";
	size_t last = text.find_last_not_of(" \t\r\n");
	return text.substr(first, last - first + 1);
}

static std::string settingsMenuHumanize(const std::string& key) {
	std::string out;
	for (size_t i = 0; i < key.size(); ++i) {
		const char c = key[i];
		const char prev = i ? key[i - 1] : 0;
		const char next = i + 1 < key.size() ? key[i + 1] : 0;
		const bool boundary = i && c != '_' && (
			(std::isupper((unsigned char)c) && (std::islower((unsigned char)prev) || std::isdigit((unsigned char)prev))) ||
			(std::isupper((unsigned char)c) && std::isupper((unsigned char)prev) && std::islower((unsigned char)next)) ||
			(std::isdigit((unsigned char)c) && std::isalpha((unsigned char)prev)) ||
			(std::isalpha((unsigned char)c) && std::isdigit((unsigned char)prev)));
		if ((c == '_' || boundary) && !out.empty() && out.back() != ' ') out.push_back(' ');
		if (c != '_') out.push_back(c);
	}
	return out;
}

static std::vector<std::string> settingsMenuSplitSchemaList(const char* packed) {
	std::vector<std::string> values;
	std::string current;
	for (const unsigned char* cursor = (const unsigned char*)packed; *cursor; ++cursor) {
		if (*cursor == 0x1f) { values.push_back(current); current.clear(); }
		else current.push_back((char)*cursor);
	}
	if (!current.empty()) values.push_back(current);
	return values;
}

struct SettingsMenuIniValue {
	std::string section;
	std::string key;
	std::string value;
	std::string help;
	bool consumed = false;
};

static SettingsMenuIniValue* settingsMenuFindIni(std::vector<SettingsMenuIniValue>& values,
	const char* section, const char* key) {
	for (SettingsMenuIniValue& value : values)
		if (value.section == section && value.key == key) return &value;
	return nullptr;
}

static bool settingsMenuReadIni() {
	std::ifstream input(g_iniPath);
	if (!input) return false;
	std::vector<SettingsMenuIniValue> values;
	std::string section;
	std::string comments;
	std::string line;
	while (std::getline(input, line)) {
		line = settingsMenuTrim(line);
		if (line.empty()) { comments.clear(); continue; }
		if (line[0] == ';' || line[0] == '#') {
			std::string comment = settingsMenuTrim(line.substr(1));
			if (!comment.empty()) {
				if (!comments.empty()) comments += " ";
				comments += comment;
			}
			continue;
		}
		if (line.front() == '[' && line.back() == ']') {
			section = line.substr(1, line.size() - 2);
			comments.clear();
			continue;
		}
		const size_t equals = line.find('=');
		if (section.empty() || equals == std::string::npos) continue;
		const std::string key = settingsMenuTrim(line.substr(0, equals));
		SettingsMenuIniValue* existing = settingsMenuFindIni(values, section.c_str(), key.c_str());
		SettingsMenuIniValue parsed{section, key, settingsMenuTrim(line.substr(equals + 1)), comments};
		if (existing) *existing = parsed;
		else values.push_back(parsed);
		comments.clear();
	}

	// The generated table is sorted category / subcategory / label, so creating
	// sections in this pass makes the in-game order exactly match LEXEDITOR's
	// current schema instead of raw INI section order.
	g_settingsMenuSections.clear();
	for (size_t index = 0; index < kSettingsMenuSchemaCount; ++index) {
		const SettingsMenuSchemaRow& schema = kSettingsMenuSchema[index];
		SettingsMenuIniValue* parsed = settingsMenuFindIni(values, schema.section, schema.key);
		if (!parsed) continue;
		parsed->consumed = true;
		if (schema.hidden || (schema.developerValue && !developmentModeActive())) continue;
		SettingsMenuSection* category = nullptr;
		for (SettingsMenuSection& existing : g_settingsMenuSections)
			if (existing.name == schema.category) { category = &existing; break; }
		if (!category) {
			g_settingsMenuSections.push_back({schema.category, {}});
			category = &g_settingsMenuSections.back();
		}
		SettingsMenuEntry setting;
		setting.section = schema.section;
		setting.key = schema.key;
		setting.subcategory = schema.subcategory;
		setting.label = schema.label;
		setting.value = parsed->value;
		setting.help = schema.help[0] ? schema.help : parsed->help;
		setting.unit = schema.unit;
		setting.constBoundary = schema.constBoundary;
		setting.choiceValues = settingsMenuSplitSchemaList(schema.choiceValues);
		setting.choiceLabels = settingsMenuSplitSchemaList(schema.choiceLabels);
		setting.booleanValue = schema.booleanValue;
		setting.developerValue = schema.developerValue;
		setting.constValue = schema.constBoundary[0] != '\0';
		setting.hasRange = schema.hasRange;
		setting.minimum = schema.minimum;
		setting.maximum = schema.maximum;
		setting.step = schema.step;
		// Never present a stored value the engine will not actually use. The
		// write path already clamps to the schema range, but the read path did
		// not, so an out-of-range INI value survived and was displayed as if it
		// applied - `[HumanMovement] BaseMoveRate=2` was shown as 2 against a
		// 1.15 native ceiling. Clamp on load as well and say so in the log.
		if (setting.hasRange && !setting.booleanValue && setting.choiceValues.empty()) {
			char* end = nullptr;
			const double stored = std::strtod(setting.value.c_str(), &end);
			if (end != setting.value.c_str() && *end == '\0' && std::isfinite(stored)) {
				const double clamped =
					(std::max)(setting.minimum, (std::min)(setting.maximum, stored));
				if (clamped != stored) {
					std::ostringstream corrected;
					corrected << std::setprecision(8) << clamped;
					GtLogStream("settings", GT_WARN)
						<< "stored value out of range section=" << setting.section
						<< " key=" << setting.key
						<< " stored=" << setting.value
						<< " shown=" << corrected.str()
						<< " min=" << setting.minimum
						<< " max=" << setting.maximum << "\n";
					setting.value = corrected.str();
				}
			}
		}
		category->entries.push_back(setting);
	}

	// A newly-added INI key remains reachable before the generator is rerun. It
	// gets a neutral fallback category, while the parity verifier makes schema
	// drift fail loudly in development.
	for (SettingsMenuIniValue& parsed : values) {
		if (parsed.consumed) continue;
		std::string categoryName = settingsMenuHumanize(parsed.section);
		SettingsMenuSection* category = nullptr;
		for (SettingsMenuSection& existing : g_settingsMenuSections)
			if (existing.name == categoryName) { category = &existing; break; }
		if (!category) {
			g_settingsMenuSections.push_back({categoryName, {}});
			category = &g_settingsMenuSections.back();
		}
		SettingsMenuEntry setting;
		setting.section = parsed.section;
		setting.key = parsed.key;
		setting.label = settingsMenuHumanize(parsed.key);
		setting.value = parsed.value;
		setting.help = parsed.help;
		setting.booleanValue = parsed.key == "Enabled";
		category->entries.push_back(setting);
	}
	std::sort(g_settingsMenuSections.begin(), g_settingsMenuSections.end(),
		[](const SettingsMenuSection& left, const SettingsMenuSection& right) {
			return left.name < right.name;
		});
	for (SettingsMenuSection& category : g_settingsMenuSections)
		std::sort(category.entries.begin(), category.entries.end(),
			[](const SettingsMenuEntry& left, const SettingsMenuEntry& right) {
				if (left.subcategory != right.subcategory) return left.subcategory < right.subcategory;
				return left.label < right.label;
			});
	return !g_settingsMenuSections.empty();
}

static bool settingsMenuNormalizeValue(const SettingsMenuEntry& setting,
	const std::string& input, std::string& output) {
	if (!setting.choiceValues.empty()) {
		for (const std::string& allowed : setting.choiceValues)
			if (input == allowed) { output = input; return true; }
		return false;
	}
	if (!setting.hasRange) { output = input; return true; }
	char* end = nullptr;
	double value = std::strtod(input.c_str(), &end);
	if (end == input.c_str() || *end != '\0' || !std::isfinite(value)) return false;
	value = (std::max)(setting.minimum, (std::min)(setting.maximum, value));
	std::ostringstream formatted;
	formatted << std::setprecision(8) << value;
	output = formatted.str();
	return true;
}

static void settingsMenuWrite(SettingsMenuEntry& setting, const std::string& value) {
	std::string normalized;
	if (!settingsMenuNormalizeValue(setting, value, normalized)) return;
	if (WritePrivateProfileStringA(setting.section.c_str(), setting.key.c_str(),
		normalized.c_str(), g_iniPath.c_str())) {
		setting.value = normalized;
		loadConfig();
	}
}

enum class SettingsMenuTextAlign { Left, Center, Right };

// Focused port of Halen84's MIT-licensed RDR2 Native Menu Base renderer.
// These are the same native dictionaries, fonts and widgets that make that
// library's menus look like part of RDR2 rather than a generic debug overlay.
static void settingsMenuDrawSprite(const char* dictionary, const char* texture,
	float x, float y, float width, float height, int r = 255, int g = 255,
	int b = 255, int a = 255) {
	GRAPHICS::DRAW_SPRITE(dictionary, texture, x, y, width, height, 0.0f,
		r, g, b, a, FALSE);
}

static std::string settingsMenuEscapeMarkup(const std::string& text) {
	std::string out;
	out.reserve(text.size());
	for (char c : text) {
		if (c == '&') out += "&amp;";
		else if (c == '<') out += "&lt;";
		else if (c == '>') out += "&gt;";
		else out.push_back(c);
	}
	return out;
}

static void settingsMenuDrawText(const std::string& text, float x, float y,
	int pixelSize, SettingsMenuTextAlign alignment = SettingsMenuTextAlign::Left,
	bool titleFont = false, int r = 245, int g = 245, int b = 245, int a = 255) {
	const char* align = alignment == SettingsMenuTextAlign::Center ? "Center" :
		alignment == SettingsMenuTextAlign::Right ? "Right" : "Left";
	const char* font = titleFont ? "title" : "body";
	const int rightMargin = alignment == SettingsMenuTextAlign::Right ?
		(int)(1920.0f - x * 1920.0f) : 0;
	std::ostringstream formatted;
	formatted << "<TEXTFORMAT RIGHTMARGIN='" << rightMargin << "'><P ALIGN='" << align
		<< "'><FONT FACE='$" << font << "' SIZE='" << pixelSize << "'>~s~"
		<< settingsMenuEscapeMarkup(text) << "</FONT></P></TEXTFORMAT>";
	HUD::_SET_TEXT_COLOR(r, g, b, a);
	const float drawX = alignment == SettingsMenuTextAlign::Center ? -1.0f + x * 2.0f :
		alignment == SettingsMenuTextAlign::Right ? 0.0f : x;
	HUD::_DISPLAY_TEXT(MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", formatted.str().c_str()), drawX, y);
}

static bool settingsMenuPressed(Hash control) {
	return PAD::IS_DISABLED_CONTROL_JUST_PRESSED(0, control) ||
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, control);
}

static void settingsMenuDisableControls() {
	static const char* controls[] = {
		"INPUT_GAME_MENU_UP", "INPUT_GAME_MENU_DOWN", "INPUT_GAME_MENU_LEFT",
		"INPUT_GAME_MENU_RIGHT", "INPUT_GAME_MENU_ACCEPT", "INPUT_GAME_MENU_CANCEL",
		"INPUT_FRONTEND_UP", "INPUT_FRONTEND_DOWN", "INPUT_FRONTEND_LEFT",
		"INPUT_FRONTEND_RIGHT", "INPUT_FRONTEND_ACCEPT", "INPUT_FRONTEND_CANCEL",
		"INPUT_OPEN_SATCHEL_MENU", "INPUT_OPEN_WHEEL_MENU", "INPUT_INTERACTION_MENU"
	};
	for (const char* name : controls) {
		PAD::DISABLE_CONTROL_ACTION(0, joaat(name), FALSE);
		PAD::DISABLE_CONTROL_ACTION(2, joaat(name), FALSE);
	}
}

static void settingsMenuBeginEdit(SettingsMenuEntry& setting) {
	MISC::DISPLAY_ONSCREEN_KEYBOARD(4,
		MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", setting.label.c_str()),
		MISC::_CREATE_VAR_STRING(10, "LITERAL_STRING", setting.unit.empty() ? "Enter value" : setting.unit.c_str()),
		setting.value.c_str(), "", "", "", 64);
	g_settingsMenuEditing = true;
}

static void settingsMenuDraw() {
	// Keep the panel in the right safe area. Arthur's cores and minimap own the
	// lower-left HUD; no menu row or value is allowed to share that region.
	static constexpr float kCenterX = 0.815f;
	static constexpr float kMenuWidth = 0.310f;
	static constexpr float kTextLeft = kCenterX - kMenuWidth * 0.5f + 0.012f;
	static constexpr float kTextRight = kCenterX + kMenuWidth * 0.5f - 0.012f;
	// Row values need more breathing room than footer/pagination text. The old
	// value edge was only about 23 reference pixels inside the panel border.
	static constexpr float kValueRight = kTextRight - 0.018f;
	static constexpr float kRowHeight = 0.047f;
	static constexpr float kFirstRowY = 0.247f;
	static constexpr int kVisibleRows = 11;

	invoke<Void>(0xC1BA29DF5631B0F8, "generic_textures", FALSE);
	invoke<Void>(0xC1BA29DF5631B0F8, "menu_textures", FALSE);
	// Rockstar uses order 7 for top-level error/benchmark overlays. This menu
	// owns the screen while open and must sit above ordinary HUD components.
	invoke<Void>(0xCFCC78391C8B3814, 7); // SET_SCRIPT_GFX_DRAW_ORDER
	settingsMenuDrawSprite("generic_textures", "inkroller_1a", kCenterX, 0.505f,
		0.355f, 0.95f, 0, 0, 0, 230);
	settingsMenuDrawSprite("generic_textures", "menu_header_1a", kCenterX, 0.105f,
		kMenuWidth, 0.102f);
	// _DISPLAY_TEXT's Y is the top of the text box, not its baseline. Centre the
	// 44 px title in the 0.102-high header instead of pinning it near the top.
	settingsMenuDrawText("LEXER'S MOD SETTINGS", kCenterX, 0.083f, 44,
		SettingsMenuTextAlign::Center, true);
	const std::string subtitle = g_settingsMenuAtSections ? "SETTINGS" : g_settingsMenuSections[g_settingsMenuSection].name;
	settingsMenuDrawText(settingsMenuHumanize(subtitle), kCenterX, 0.169f, 22,
		SettingsMenuTextAlign::Center, true);

	const int count = g_settingsMenuAtSections ? (int)g_settingsMenuSections.size() :
		(int)g_settingsMenuSections[g_settingsMenuSection].entries.size();
	const int first = (std::max)(0,
		(std::min)(g_settingsMenuSelection - 5, (std::max)(0, count - kVisibleRows)));
	const int visibleCount = (std::min)(count, kVisibleRows);

	settingsMenuDrawSprite("menu_textures", "scroller_left_top", kCenterX - 0.078f,
		0.214f, 0.134f, 0.023f);
	settingsMenuDrawSprite("menu_textures", "scroller_right_top", kCenterX + 0.078f,
		0.214f, 0.134f, 0.023f);
	settingsMenuDrawSprite("menu_textures", first > 0 ? "scroller_arrow_top" : "scroller_line_up",
		kCenterX, 0.2255f, 0.021f, 0.023f);

	for (int row = 0; row < kVisibleRows && first + row < count; ++row) {
		const int index = first + row;
		const float centerY = kFirstRowY + row * kRowHeight;
		// Body text is about 25/1080 screen units tall; half of that is 0.0116.
		// Use the row centre rather than the old arbitrary -0.016 offset.
		const float textY = centerY - 0.0115f;
		const bool developerRow = !g_settingsMenuAtSections &&
			g_settingsMenuSections[g_settingsMenuSection].entries[index].developerValue;
		const bool constRow = !g_settingsMenuAtSections &&
			g_settingsMenuSections[g_settingsMenuSection].entries[index].constValue;
		const bool mixedLifecycleRow = developerRow && constRow;
		settingsMenuDrawSprite("generic_textures", "selection_box_bg_1c", kCenterX,
			centerY, kMenuWidth, kRowHeight,
			mixedLifecycleRow ? 82 : constRow ? 92 : developerRow ? 68 : 50,
			(developerRow || constRow) ? 38 : 50,
			mixedLifecycleRow ? 75 : developerRow ? 92 : constRow ? 42 : 50,
			(developerRow || constRow) ? 180 : 110);
		if (index == g_settingsMenuSelection) {
			settingsMenuDrawSprite("menu_textures", "crafting_highlight_l", kCenterX - kMenuWidth * 0.5f - 0.002f,
				centerY, 0.010f, kRowHeight + 0.004f, 204, 0, 0);
			settingsMenuDrawSprite("menu_textures", "crafting_highlight_r", kCenterX + kMenuWidth * 0.5f + 0.002f,
				centerY, 0.010f, kRowHeight + 0.004f, 204, 0, 0);
			settingsMenuDrawSprite("menu_textures", "crafting_highlight_t", kCenterX,
				centerY - kRowHeight * 0.5f, kMenuWidth + 0.006f, 0.020f, 204, 0, 0);
			settingsMenuDrawSprite("menu_textures", "crafting_highlight_b", kCenterX,
				centerY + kRowHeight * 0.5f, kMenuWidth + 0.006f, 0.020f, 204, 0, 0);
		}
		if (g_settingsMenuAtSections) {
			const SettingsMenuSection& section = g_settingsMenuSections[index];
			settingsMenuDrawText(section.name, kTextLeft, textY, 25);
			settingsMenuDrawText(std::to_string(section.entries.size()), kValueRight, textY, 23,
				SettingsMenuTextAlign::Right, false, 190, 178, 154);
		} else {
			const SettingsMenuEntry& setting = g_settingsMenuSections[g_settingsMenuSection].entries[index];
			std::string lifecycle;
			if (setting.developerValue) lifecycle += "DEV ";
			if (setting.constValue) lifecycle += "CONST ";
			const bool grouped = !setting.subcategory.empty();
			if (grouped)
				settingsMenuDrawText(setting.subcategory, kTextLeft, centerY - 0.019f, 14,
					SettingsMenuTextAlign::Left, false, 170, 156, 136);
			settingsMenuDrawText(lifecycle + setting.label, kTextLeft,
				grouped ? centerY - 0.003f : textY, grouped ? 22 : 25,
				SettingsMenuTextAlign::Left, false,
				setting.constValue ? 255 : setting.developerValue ? 226 : 255,
				setting.constValue ? 205 : setting.developerValue ? 201 : 255,
				setting.constValue ? 205 : 255);
			if (setting.booleanValue) {
				const float checkboxX = kValueRight - 0.006f;
				settingsMenuDrawSprite("generic_textures", "tick_box", checkboxX, centerY, 0.016f, 0.028f);
				if (setting.value != "0")
					settingsMenuDrawSprite("generic_textures", "tick", checkboxX, centerY, 0.016f, 0.028f);
			} else {
				std::string value = setting.value;
				if (!setting.unit.empty()) value += " " + setting.unit;
				if (value.size() > 23) value = value.substr(0, 20) + "...";
				if (index == g_settingsMenuSelection) value = "< " + value + " >";
				settingsMenuDrawText(value, kValueRight, textY, 23,
					SettingsMenuTextAlign::Right, false, 222, 205, 172);
			}
		}
	}
	const float scrollerBottomY = kFirstRowY + visibleCount * kRowHeight - 0.012f;
	settingsMenuDrawSprite("menu_textures", "scroller_left_bottom", kCenterX - 0.078f,
		scrollerBottomY, 0.134f, 0.023f);
	settingsMenuDrawSprite("menu_textures", "scroller_right_bottom", kCenterX + 0.078f,
		scrollerBottomY, 0.134f, 0.023f);
	settingsMenuDrawSprite("menu_textures",
		(first + visibleCount < count) ? "scroller_arrow_bottom" : "scroller_line_down",
		kCenterX, scrollerBottomY + 0.0115f, 0.021f, 0.023f);
	settingsMenuDrawText(std::to_string(g_settingsMenuSelection + 1) + " of " + std::to_string(count),
		kTextRight, scrollerBottomY + 0.025f, 18, SettingsMenuTextAlign::Right,
		false, 155, 155, 155, 230);
	settingsMenuDrawSprite("generic_textures", "menu_bar", kCenterX, 0.875f,
		kMenuWidth, 0.003f, 255, 255, 255, 175);
	if (!g_settingsMenuAtSections && count) {
		const SettingsMenuEntry& selected = g_settingsMenuSections[g_settingsMenuSection].entries[g_settingsMenuSelection];
		std::string help = selected.help.empty() ? selected.section + " / " + selected.key : selected.help;
		if (help.size() > 100) help = help.substr(0, 97) + "...";
		settingsMenuDrawText(help, kCenterX, 0.810f, 18,
			SettingsMenuTextAlign::Center, false, 190, 180, 164);
		settingsMenuDrawText(selected.booleanValue ? "ENTER toggle   BACK sections   F8 close" :
			"ENTER type value   LEFT/RIGHT adjust   BACK sections   F8 close",
			kCenterX, 0.889f, 17, SettingsMenuTextAlign::Center, false, 220, 205, 180);
	} else {
		settingsMenuDrawText("ENTER open section   BACK/F8 close", kCenterX, 0.889f, 17,
			SettingsMenuTextAlign::Center, false, 220, 205, 180);
	}
}

static void settingsMenuAdjust(SettingsMenuEntry& setting, int direction) {
	if (!setting.choiceValues.empty()) {
		size_t index = 0;
		for (size_t i = 0; i < setting.choiceValues.size(); ++i)
			if (setting.choiceValues[i] == setting.value) { index = i; break; }
		index = direction > 0 ? (index + 1) % setting.choiceValues.size() :
			(index + setting.choiceValues.size() - 1) % setting.choiceValues.size();
		settingsMenuWrite(setting, setting.choiceValues[index]);
		return;
	}
	char* end = nullptr;
	const double current = std::strtod(setting.value.c_str(), &end);
	if (end == setting.value.c_str() || *end != '\0') return;
	const bool decimal = setting.value.find_first_of(".eE") != std::string::npos;
	const double magnitude = std::fabs(current);
	const double step = setting.hasRange && setting.step > 0.0 ? setting.step :
		decimal ? (magnitude >= 10.0 ? 1.0 : magnitude >= 1.0 ? 0.1 : 0.01) : 1.0;
	std::ostringstream formatted;
	if (decimal) formatted << std::fixed << std::setprecision(step < 0.1 ? 2 : step < 1.0 ? 1 : 0);
	formatted << current + direction * step;
	settingsMenuWrite(setting, formatted.str());
}

// Integration-owned script.cpp calls this once per frame. The menu is F8 on
// keyboard, or LB+RB on controller. It returns true while open so the dispatcher
// can optionally suppress unrelated feature hotkeys for that frame.
static bool updateInGameSettingsMenu() {
	const bool f8Down = (GetAsyncKeyState(VK_F8) & 0x8000) != 0;
	const bool controllerOpen = PAD::IS_DISABLED_CONTROL_PRESSED(2, joaat("INPUT_FRONTEND_LB")) &&
		PAD::IS_DISABLED_CONTROL_JUST_PRESSED(2, joaat("INPUT_FRONTEND_RB"));
	if ((f8Down && !g_settingsMenuF8WasDown) || controllerOpen) {
		if (g_settingsMenuOpen) {
			g_settingsMenuOpen = false;
			g_settingsMenuEditing = false;
		} else if (settingsMenuReadIni()) {
			g_settingsMenuOpen = true;
			g_settingsMenuAtSections = true;
			g_settingsMenuSelection = 0;
		}
	}
	g_settingsMenuF8WasDown = f8Down;
	if (!g_settingsMenuOpen) return false;

	settingsMenuDisableControls();
	if (g_settingsMenuEditing) {
		const int state = MISC::UPDATE_ONSCREEN_KEYBOARD();
		if (state == 1) {
			const char* result = MISC::GET_ONSCREEN_KEYBOARD_RESULT();
			if (result && *result && !g_settingsMenuAtSections)
				settingsMenuWrite(g_settingsMenuSections[g_settingsMenuSection].entries[g_settingsMenuSelection], result);
			g_settingsMenuEditing = false;
		} else if (state == 2 || state == 3) {
			g_settingsMenuEditing = false;
		}
		return true;
	}

	settingsMenuDraw();
	const DWORD now = GetTickCount();
	if (now < g_settingsMenuNextInputAt) return true;
	const bool up = settingsMenuPressed(joaat("INPUT_FRONTEND_UP")) || settingsMenuPressed(joaat("INPUT_GAME_MENU_UP"));
	const bool down = settingsMenuPressed(joaat("INPUT_FRONTEND_DOWN")) || settingsMenuPressed(joaat("INPUT_GAME_MENU_DOWN"));
	const bool left = settingsMenuPressed(joaat("INPUT_FRONTEND_LEFT")) || settingsMenuPressed(joaat("INPUT_GAME_MENU_LEFT"));
	const bool right = settingsMenuPressed(joaat("INPUT_FRONTEND_RIGHT")) || settingsMenuPressed(joaat("INPUT_GAME_MENU_RIGHT"));
	const bool accept = settingsMenuPressed(joaat("INPUT_FRONTEND_ACCEPT")) || settingsMenuPressed(joaat("INPUT_GAME_MENU_ACCEPT"));
	const bool cancel = settingsMenuPressed(joaat("INPUT_FRONTEND_CANCEL")) || settingsMenuPressed(joaat("INPUT_GAME_MENU_CANCEL"));
	const int count = g_settingsMenuAtSections ? (int)g_settingsMenuSections.size() :
		(int)g_settingsMenuSections[g_settingsMenuSection].entries.size();
	if (up && count) g_settingsMenuSelection = (g_settingsMenuSelection + count - 1) % count;
	if (down && count) g_settingsMenuSelection = (g_settingsMenuSelection + 1) % count;
	if ((up || down) && count) g_settingsMenuNextInputAt = now + 115;
	if (cancel) {
		if (g_settingsMenuAtSections) g_settingsMenuOpen = false;
		else { g_settingsMenuAtSections = true; g_settingsMenuSelection = g_settingsMenuSection; }
		g_settingsMenuNextInputAt = now + 180;
	} else if (accept && count) {
		if (g_settingsMenuAtSections) {
			g_settingsMenuSection = g_settingsMenuSelection;
			g_settingsMenuAtSections = false;
			g_settingsMenuSelection = 0;
		} else {
			SettingsMenuEntry& setting = g_settingsMenuSections[g_settingsMenuSection].entries[g_settingsMenuSelection];
			if (setting.booleanValue) settingsMenuWrite(setting, setting.value == "0" ? "1" : "0");
			else if (!setting.choiceValues.empty()) settingsMenuAdjust(setting, 1);
			else settingsMenuBeginEdit(setting);
		}
		g_settingsMenuNextInputAt = now + 180;
	} else if (!g_settingsMenuAtSections && count && (left || right)) {
		SettingsMenuEntry& setting = g_settingsMenuSections[g_settingsMenuSection].entries[g_settingsMenuSelection];
		if (setting.booleanValue) settingsMenuWrite(setting, setting.value == "0" ? "1" : "0");
		else settingsMenuAdjust(setting, right ? 1 : -1);
		g_settingsMenuNextInputAt = now + 100;
	}
	return true;
}
