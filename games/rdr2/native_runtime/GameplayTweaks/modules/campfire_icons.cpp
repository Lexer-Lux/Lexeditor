// GameplayTweaks feature module: authored-campsite state icons (#12).
//
// An activated campsite uses Rockstar's simple burning-campfire glyph. The
// inactive state uses Lexer's edit of that same glyph with the flame blacked
// out, so the pair differs only by whether the fire is visibly lit.

static bool campsiteIconTexturesReady() {
	// Use the same proven lifetime owner as the other custom map icons. Merely
	// requesting this non-resident dictionary once while creating a campsite is
	// racy: loading is asynchronous, and the already-created blip remains a
	// black square until its icon is assigned again after the dictionary loads.
	invoke<Void>(0xC1BA29DF5631B0F8, "INVENTORY_ITEMS_MP", FALSE);
	return invoke<BOOL>(0x54D6900929CCF162, "INVENTORY_ITEMS_MP") != 0;
}

static Hash campsiteStateBlipIcon(bool activated) {
	if (activated) return joaat("BLIP_CAMPFIRE");
	// Never expose an unresolved custom linkage. The campsite updater replaces
	// this temporary vanilla fallback as soon as lex_blips reports loaded.
	if (!campsiteIconTexturesReady()) return joaat("BLIP_CAMPFIRE");
	return joaat("LEX_BLIP_CAMPFIRE_INACTIVE");
}
