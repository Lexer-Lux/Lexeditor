// GitHub #57: sell cigarette-card duplicates only after their set is mailed.
//
// shop_post_office.c commits a persistent per-set bit to Global_40.f_12019
// after accepting a DOCUMENT_CIG_CARD_*_SET parcel.  That Story state is the
// authority: inventory absence cannot distinguish mailing from other removal,
// and a private mod file cannot discover sets mailed before the mod existed.
namespace DuplicateCigaretteCards {

struct CardSet {
	const char* code;
	unsigned mailedMask;
	Hash duplicate;
	Hash cards[12];
};

static CardSet g_sets[] = {
	{ "ACT",    1u, 0, {} },
	{ "AML",    4u, 0, {} },
	{ "ART",    8u, 0, {} },
	{ "GRL",   16u, 0, {} },
	{ "GUN",   32u, 0, {} },
	{ "HOR",   64u, 0, {} },
	{ "INV",  128u, 0, {} },
	{ "LND",  256u, 0, {} },
	{ "PAM",    2u, 0, {} },
	{ "PLT",  512u, 0, {} },
	{ "SPT", 1024u, 0, {} },
	{ "VEH", 2048u, 0, {} },
};

static bool g_initialized = false;

static void initialize() {
	if (g_initialized) return;
	for (CardSet& set : g_sets) {
		char id[64] = {};
		sprintf_s(id, "LEX_DUPLICATE_CIG_CARD_%s", set.code);
		set.duplicate = joaat(id);
		for (int card = 0; card < 12; ++card) {
			sprintf_s(id, "DOCUMENT_CIG_CARD_%s_%d", set.code, card + 1);
			set.cards[card] = joaat(id);
		}
	}
	g_initialized = true;
}

// Keep conversion recoverable across native/cap failures.  The original is
// removed only after the resale record is visibly in inventory; if removal
// does not take, the provisional resale record is rolled back.
static bool convertOne(Hash original, Hash duplicate) {
	const int originalBefore = INVENTORY_ITEM_COUNT(original);
	const int duplicateBefore = INVENTORY_ITEM_COUNT(duplicate);
	if (originalBefore <= 0 || !INVENTORY_ADD(duplicate, 1) ||
		INVENTORY_ITEM_COUNT(duplicate) != duplicateBefore + 1)
		return false;

	if (!INVENTORY_REMOVE(original, 1) ||
		INVENTORY_ITEM_COUNT(original) != originalBefore - 1) {
		INVENTORY_REMOVE(duplicate, 1);
		return false;
	}
	return true;
}

static void update(bool enabled) {
	if (!enabled) return;
	initialize();
	const unsigned mailedSets = static_cast<unsigned>(
		static_cast<int>(*getGlobalPtr(40 + 12019)));

	for (const CardSet& set : g_sets) {
		if ((mailedSets & set.mailedMask) == 0) continue;
		for (Hash card : set.cards) {
			// Every original record remaining after turn-in is a later copy.  The
			// loop also migrates copies acquired before this build was installed.
			while (INVENTORY_ITEM_COUNT(card) > 0) {
				if (!convertOne(card, set.duplicate)) break;
			}
		}
	}
}

} // namespace DuplicateCigaretteCards
