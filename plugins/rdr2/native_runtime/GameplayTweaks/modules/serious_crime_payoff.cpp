// GitHub #24: replace surrender with an immediate full-bounty payoff for
// serious crimes.
//
// "Serious" is not a mod-authored dollar threshold. crimeinformation.meta
// gives every Story Mode crime a Severity, and this module checks the engine's
// registered-crime list for a reported Severity=High record.  The integration
// owner includes this module and calls updateSeriousCrimePayoff() once per
// frame before other feature input handlers.

struct SeriousCrimeRecord {
	Any crimeType;
	Any fields[9];
	Any reported;
};

static_assert(sizeof(SeriousCrimeRecord) == sizeof(Any) * 11,
	"registered crime record must match Rockstar's 11-slot script struct");

static Prompt g_seriousCrimePayPrompt = 0;
static int g_seriousCrimeLastBounty = -1;
static int g_seriousCrimeLastCash = -1;

static bool isHighSeverityStoryCrime(Hash crime) {
	static const Hash high[] = {
		joaat("CRIME_ASSAULT"), joaat("CRIME_ASSAULT_LAW"),
		joaat("CRIME_TRAMPLE"), joaat("CRIME_TRAMPLE_LAW"),
		joaat("CRIME_BANK_ROBBERY"), joaat("CRIME_JAIL_BREAK"),
		joaat("CRIME_KIDNAPPING"), joaat("CRIME_KIDNAPPING_LAW"),
		joaat("CRIME_RESIST_ARREST"), joaat("CRIME_LAW_IS_THREATENED"),
		joaat("CRIME_MURDER"), joaat("CRIME_MURDER_LAW"),
		joaat("CRIME_STAGECOACH_ROBBERY"), joaat("CRIME_TRAIN_ROBBERY"),
		joaat("CRIME_ACCOMPLICE")
	};
	for (Hash candidate : high) if (crime == candidate) return true;
	return false;
}

static bool hasReportedHighSeverityCrime(Player player) {
	// Rockstar scripts enumerate indices 0..23 oldest-to-newest and treat slot
	// 10 as the reported flag. Unreported witness suspicions are deliberately
	// not a criminal record for this feature.
	for (int index = 0; index < 24; ++index) {
		SeriousCrimeRecord record = {};
		if (!invoke<BOOL>(0x532C5FDDB986EE5C, player, index, &record)) continue;
		if (record.reported && isHighSeverityStoryCrime((Hash)record.crimeType))
			return true;
	}
	return false;
}

static void seriousCrimePromptState(bool visible, bool enabled) {
	if (!g_seriousCrimePayPrompt) return;
	invoke<Void>(0x71215ACCFDE075EE, g_seriousCrimePayPrompt,
		visible ? TRUE : FALSE);
	invoke<Void>(0x8A0FB4D03A630D21, g_seriousCrimePayPrompt,
		enabled ? TRUE : FALSE);
}

static void ensureSeriousCrimePrompt() {
	if (g_seriousCrimePayPrompt) return;
	g_seriousCrimePayPrompt = invoke<int>(0x04F97DE45A519419);
	invoke<Any>(0xB5352B7494A08258, g_seriousCrimePayPrompt,
		joaat("INPUT_INTERACT_OPTION1"));
	invoke<Void>(0xCC6656799977741B, g_seriousCrimePayPrompt, TRUE);
	invoke<Void>(0xF7AA2696A22AD8B9, g_seriousCrimePayPrompt);
	seriousCrimePromptState(false, false);
}

static void setSeriousCrimePromptText(int bounty, int cash) {
	if (bounty == g_seriousCrimeLastBounty && cash == g_seriousCrimeLastCash)
		return;
	g_seriousCrimeLastBounty = bounty;
	g_seriousCrimeLastCash = cash;
	char label[128];
	if (cash >= bounty) {
		sprintf_s(label, "Pay bounty  $%d.%02d", bounty / 100, bounty % 100);
	} else {
		const int shortfall = bounty - cash;
		sprintf_s(label, "Pay bounty  $%d.%02d  (short $%d.%02d)",
			bounty / 100, bounty % 100, shortfall / 100, shortfall % 100);
	}
	invoke<Void>(0x5DD02A8318420DD7, g_seriousCrimePayPrompt,
		invoke<const char*>(0xFA925AC00EB830B9, 10, "LITERAL_STRING", label));
}

static void clearPaidSeriousCrime(Player player) {
	// Keep the persistent regional table synchronized with SET_BOUNTY, as the
	// confirmed partial-bounty implementation does.
	const int state = (int)*getGlobalPtr(1934266 + 4);
	if (state >= 0 && state < 6)
		*getGlobalPtr(40 + 359 + state * 12) = 0;
	SET_BOUNTY_VALUE(player, 0);
	invoke<Void>(0xBCC6DC59E32A2BDC, player); // CLEAR_PLAYER_PAST_CRIMES
	invoke<Void>(0x062B4A4A3396351D, player); // CLEAR_WANTED_SCORE
	invoke<Void>(0x07E8B8B20570271C, player); // SP incident cleanup companion
	invoke<Void>(0x55F37F5F3F2475E1);         // clear active law/BH pursuit
}

static void updateSeriousCrimePayoff(Player player, Ped ped, bool blocked) {
	ensureSeriousCrimePrompt();
	const Hash hudCrime = invoke<Hash>(0x259CE340A8738814, player);
	const int wantedScore = invoke<int>(0xDD5FD601481F648B, player);
	const Hash dispatch = invoke<Hash>(0x148E7AC8141C9E64, player);
	const bool lawIncident = wantedScore > 0 || hudCrime != 0 || dispatch != 0;
	const bool serious = lawIncident && hasReportedHighSeverityCrime(player);
	if (!serious || blocked || !ped || ENTITY::IS_ENTITY_DEAD(ped)) {
		seriousCrimePromptState(false, false);
		return;
	}

	// The game can offer surrender from either lawmen or bounty hunters. Disable
	// only that action while a serious incident is live; combat inputs remain.
	PAD::DISABLE_CONTROL_ACTION(0, joaat("INPUT_SURRENDER"), TRUE);
	if (invoke<BOOL>(0xC8183AE963C58374, player, TRUE))
		invoke<Void>(0x12917931C31F1750, player); // cancel the pre-busted arrest phase

	const int bounty = (std::max)(0, GET_BOUNTY_VALUE(player));
	const int cash = (std::max)(0, CASH_BALANCE());
	const bool affordable = bounty > 0 && cash >= bounty;
	setSeriousCrimePromptText(bounty, cash);
	seriousCrimePromptState(bounty > 0, affordable);
	if (!affordable || !invoke<BOOL>(0xC92AC953F0A982AE,
		g_seriousCrimePayPrompt)) return;

	// No pursuit state changes before the cash transaction succeeds.
	if (!REMOVE_CASH(bounty)) return;
	clearPaidSeriousCrime(player);
	seriousCrimePromptState(false, false);
	invoke<Void>(0xDC6C55DFA2C24EE5, g_seriousCrimePayPrompt);
	char confirmation[96];
	sprintf_s(confirmation, "Bounty paid: $%d.%02d", bounty / 100, bounty % 100);
	CASING_FEED(confirmation, "", 0);
}
