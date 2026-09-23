// GitHub #37 -- Premium Cigarette card rework.
//
// Authoritative Story behavior:
// - main.c's inventory-acquisition switch grants a random card when
//   CONSUMABLE_CIGARETTE_BOX is acquired.
// - generic_smoking_item.c applies one cigarette's effects on animation event
//   442509369.  That authored consume event, not an inventory-count decrease,
//   is the only event allowed to roll the replacement card chance here.
//
// updatePremiumCigaretteCards must run every frame so the authored animation
// event cannot be missed. Inventory/card readbacks remain rate-limited to 10 Hz.

namespace PremiumCigaretteCards {

static const DWORD kInventoryPollMs = 100;
static const DWORD kConfigPollMs = 2000;
static const DWORD kHeartbeatMs = 30000;
static const DWORD kVanillaGrantWindowMs = 3000;
static const Hash kConsumeAnimEvent = 442509369;
static const char* kCardSets[] = {
	"ACT", "AML", "ART", "GRL", "GUN", "HOR",
	"INV", "LND", "PAM", "PLT", "SPT", "VEH"
};

static std::vector<Hash> s_cards;
static std::vector<std::string> s_cardNames;
static std::vector<int> s_cardCounts;
static int s_premiumPackCount = -1;
static int s_pendingVanillaCards = 0;
static DWORD s_pendingUntil = 0;
static DWORD s_nextInventoryPoll = 0;
static DWORD s_nextConfigPoll = 0;
static DWORD s_nextHeartbeat = 0;
static bool s_consumeEventWasFired = false;
static bool s_configWasRead = false;
static float s_chancePercent = 20.0f;
static unsigned s_rng = 0x6C657843u;
static const char* s_lastOutcome = "not-executed";

static unsigned nextRandom() {
	s_rng ^= s_rng << 13;
	s_rng ^= s_rng >> 17;
	s_rng ^= s_rng << 5;
	return s_rng;
}

static void initialize() {
	if (!s_cards.empty()) return;
	for (size_t setIndex = 0;
		setIndex < sizeof(kCardSets) / sizeof(kCardSets[0]); ++setIndex) {
		for (int number = 1; number <= 12; ++number) {
			char name[64];
			sprintf_s(name, "DOCUMENT_CIG_CARD_%s_%d", kCardSets[setIndex], number);
			s_cards.push_back(joaat(name));
			s_cardNames.push_back(name);
			s_cardCounts.push_back(INVENTORY_ITEM_COUNT(s_cards.back()));
		}
	}
	s_premiumPackCount = INVENTORY_ITEM_COUNT(joaat("CONSUMABLE_CIGARETTE_BOX"));
	s_rng ^= GetTickCount();
	gtLog("premium-cigarette-cards", GT_INFO,
		"initialized cards=144 inventoryPollMs=100 consumeEvent=442509369");
}

static void reloadConfig(DWORD now) {
	if (s_nextConfigPoll && now < s_nextConfigPoll) return;
	s_nextConfigPoll = now + kConfigPollMs;
	const float configured = readF("PremiumCigaretteCards", "ChancePercent", 20.0f);
	const float clamped = (std::max)(0.0f, (std::min)(100.0f, configured));
	if (!s_configWasRead || clamped != s_chancePercent || configured != clamped) {
		std::ostringstream line;
		line << "config ChancePercent=" << clamped;
		if (configured != clamped) line << " clampedFrom=" << configured;
		line << " reloadMs=" << kConfigPollMs;
		gtLog("premium-cigarette-cards", GT_INFO, line.str());
	}
	s_chancePercent = clamped;
	s_configWasRead = true;
}

static int refreshCardCounts(bool suppressVanillaGrant, DWORD now) {
	int ownedUnique = 0;
	for (size_t i = 0; i < s_cards.size(); ++i) {
		int live = INVENTORY_ITEM_COUNT(s_cards[i]);
		if (suppressVanillaGrant && live > s_cardCounts[i] &&
			s_pendingVanillaCards > 0 && now <= s_pendingUntil) {
			const int increase = live - s_cardCounts[i];
			const int requested = (std::min)(increase, s_pendingVanillaCards);
			const int before = live;
			const bool removeCalled = INVENTORY_REMOVE(s_cards[i], requested);
			live = INVENTORY_ITEM_COUNT(s_cards[i]);
			const int removed = (std::max)(0, before - live);
			s_pendingVanillaCards -= (std::min)(removed, s_pendingVanillaCards);
			std::ostringstream line;
			line << "pack grant suppression card=" << s_cardNames[i]
				<< " requested=" << requested << " removed=" << removed
				<< " call=" << (removeCalled ? 1 : 0)
				<< " pending=" << s_pendingVanillaCards;
			gtLog("premium-cigarette-cards",
				removed == requested ? GT_INFO : GT_ERROR, line.str());
		}
		s_cardCounts[i] = live;
		if (live > 0) ++ownedUnique;
	}
	return ownedUnique;
}

static bool grantSmokingCard() {
	// Refresh at the actual roll so cards collected or mailed since the last
	// 10 Hz inventory poll are respected by the unowned-first selection.
	refreshCardCounts(false, GetTickCount());
	std::vector<size_t> unowned;
	for (size_t i = 0; i < s_cards.size(); ++i)
		if (s_cardCounts[i] <= 0) unowned.push_back(i);
	const bool duplicatesAllowed = unowned.empty();
	const size_t index = duplicatesAllowed
		? nextRandom() % s_cards.size()
		: unowned[nextRandom() % unowned.size()];
	const int before = INVENTORY_ITEM_COUNT(s_cards[index]);
	const bool addCalled = INVENTORY_ADD(s_cards[index], 1);
	const int after = INVENTORY_ITEM_COUNT(s_cards[index]);
	s_cardCounts[index] = after;
	std::ostringstream line;
	line << "grant card=" << s_cardNames[index]
		<< " selection=" << (duplicatesAllowed ? "duplicate-after-144" : "unowned")
		<< " before=" << before << " after=" << after
		<< " call=" << (addCalled ? 1 : 0);
	const bool granted = after > before;
	gtLog("premium-cigarette-cards", granted ? GT_INFO : GT_ERROR, line.str());
	return granted;
}

static void rollForConsumedCigarette() {
	// Basis points preserve decimal percentages from the INI without biasing
	// whole-number values. 100.0 always grants; 0.0 never grants.
	const unsigned roll = nextRandom() % 10000u;
	const unsigned threshold = (unsigned)(s_chancePercent * 100.0f + 0.5f);
	const bool won = roll < threshold;
	std::ostringstream line;
	line << "smoke consume event=442509369 roll=" << roll
		<< " threshold=" << threshold
		<< " chancePercent=" << s_chancePercent
		<< " result=" << (won ? "won" : "miss");
	gtLog("premium-cigarette-cards", GT_INFO, line.str());
	if (!won) {
		s_lastOutcome = "executed-miss";
		return;
	}
	s_lastOutcome = grantSmokingCard() ? "executed-granted" : "executed-grant-failed";
}

static void update(Ped ped, DWORD now) {
	initialize();
	reloadConfig(now);

	const Hash premium = joaat("CONSUMABLE_CIGARETTE_BOX");
	const Hash openedPremium = joaat("CONSUMABLE_CIGARETTE_BOX_USED");
	const bool interactionRunning = ITEM_INTERACTION_RUNNING(ped);
	const Hash interactionItem = interactionRunning ? ITEM_INTERACTION_ITEM(ped) : 0;
	const bool premiumInteraction =
		interactionItem == premium || interactionItem == openedPremium;
	const bool consumeEventFired = premiumInteraction &&
		ENTITY::HAS_ANIM_EVENT_FIRED(ped, kConsumeAnimEvent);
	if (consumeEventFired && !s_consumeEventWasFired)
		rollForConsumedCigarette();
	s_consumeEventWasFired = consumeEventFired;

	if (!s_nextInventoryPoll || now >= s_nextInventoryPoll) {
		s_nextInventoryPoll = now + kInventoryPollMs;
		const int currentPackCount = INVENTORY_ITEM_COUNT(premium);
		if (s_premiumPackCount >= 0 && currentPackCount > s_premiumPackCount) {
			// Rockstar's acquisition handler grants one card per acquisition
			// transaction, even when the catalog transaction adds ten cigarettes.
			++s_pendingVanillaCards;
			s_pendingUntil = now + kVanillaGrantWindowMs;
			std::ostringstream line;
			line << "premium pack acquired before=" << s_premiumPackCount
				<< " after=" << currentPackCount
				<< " suppressionPending=" << s_pendingVanillaCards;
			gtLog("premium-cigarette-cards", GT_INFO, line.str());
		}
		s_premiumPackCount = currentPackCount;
		if (s_pendingVanillaCards > 0 && now > s_pendingUntil) {
			std::ostringstream line;
			line << "suppression expired pending=" << s_pendingVanillaCards;
			gtLog("premium-cigarette-cards", GT_WARN, line.str());
			s_pendingVanillaCards = 0;
		}
		refreshCardCounts(s_pendingVanillaCards > 0, now);
	}

	if (!s_nextHeartbeat || now >= s_nextHeartbeat) {
		s_nextHeartbeat = now + kHeartbeatMs;
		int ownedUnique = 0;
		for (size_t i = 0; i < s_cardCounts.size(); ++i)
			if (s_cardCounts[i] > 0) ++ownedUnique;
		std::ostringstream line;
		line << "heartbeat state=running chancePercent=" << s_chancePercent
			<< " ownedUnique=" << ownedUnique << "/144"
			<< " packCount=" << s_premiumPackCount
			<< " pendingSuppression=" << s_pendingVanillaCards
			<< " lastSmoke=" << s_lastOutcome;
		gtLog("premium-cigarette-cards", GT_INFO, line.str());
	}
}

} // namespace PremiumCigaretteCards

static void updatePremiumCigaretteCards(Ped ped, DWORD now) {
	PremiumCigaretteCards::update(ped, now);
}
