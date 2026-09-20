// GitHub #126 - one structured log for every GameplayTweaks subsystem.
//
// Why this exists, concretely. On 2026-08-07 a freeze took several hours to
// narrow because the evidence was scattered across 47 separate files. Working
// out "what ran last before the game died" meant opening five of them and
// hand-aligning their timestamps - and they did not even share a clock:
// wanted-trace.log was stamped 77359 while map-recenter.log was at 424281 in
// the same session. Two facts that solved earlier bugs (focusWrites beside
// frames; owned=1 on every heartbeat) were only visible because those two
// numbers happened to live in the same file. Anything spanning two subsystems
// was effectively invisible.
//
// Contract:
//   - ONE file, GameplayTweaks.log, truncated once per launch after a
//     `session` record naming the build.
//   - Every line: tick, elapsed ms, subsystem, severity, then the event text.
//   - One monotonic clock (GetTickCount) for all subsystems, so ordering across
//     subsystems is real and needs no correlation.
//   - Bounded. Hard byte cap with rotation to .1 so it cannot fill the disk.
//   - Two verbosity levels. TRACE is off unless [Logging] Verbose=1, so
//     per-tick spam does not drown the record, but INFO/WARN/ERROR always land.
//
// Modules call gtLog(...) instead of opening their own ofstream. Existing
// per-subsystem files are being retired; do not add new ones.

enum GtLogLevel { GT_TRACE = 0, GT_INFO = 1, GT_WARN = 2, GT_ERROR = 3 };

static std::string g_gtLogPath;
static bool  g_gtLogStarted = false;
static bool  g_gtLogVerbose = false;
static DWORD g_gtLogSessionStart = 0;
static unsigned long long g_gtLogBytes = 0;

// 8 MB, then rotate. A full session of INFO sits far under this; verbose
// sessions rotate rather than growing without bound (the old reserve.log
// reached 5.8 MB on its own by never truncating at all).
static const unsigned long long kGtLogMaxBytes = 8ull * 1024ull * 1024ull;

static const char* gtLogLevelName(GtLogLevel level) {
	switch (level) {
		case GT_TRACE: return "TRACE";
		case GT_INFO:  return "INFO ";
		case GT_WARN:  return "WARN ";
		default:       return "ERROR";
	}
}

static void gtLogRotate() {
	if (g_gtLogPath.empty()) return;
	const std::string previous = g_gtLogPath + ".1";
	DeleteFileA(previous.c_str());
	MoveFileA(g_gtLogPath.c_str(), previous.c_str());
	g_gtLogBytes = 0;
}

// Safe before initialization: calls made before gtLogInit simply return, so a
// module logging during static setup cannot crash or create a stray file.
static void gtLog(const char* subsystem, GtLogLevel level, const std::string& event) {
	if (g_gtLogPath.empty() || !g_gtLogStarted) return;
	if (level == GT_TRACE && !g_gtLogVerbose) return;

	const DWORD now = GetTickCount();
	std::ostringstream line;
	line << now << " +" << (now - g_gtLogSessionStart) << "ms "
		<< gtLogLevelName(level) << " [" << (subsystem ? subsystem : "?") << "] "
		<< event << "\r\n";
	const std::string text = line.str();

	if (g_gtLogBytes + text.size() > kGtLogMaxBytes) gtLogRotate();

	HANDLE file = CreateFileA(g_gtLogPath.c_str(), FILE_APPEND_DATA,
		FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS,
		FILE_ATTRIBUTE_NORMAL, nullptr);
	if (file == INVALID_HANDLE_VALUE) return;
	DWORD written = 0;
	WriteFile(file, text.data(), (DWORD)text.size(), &written, nullptr);
	CloseHandle(file);
	g_gtLogBytes += written;
}

static void gtLogInit(const std::string& moduleDir, bool verbose, const char* buildLabel) {
	g_gtLogPath = moduleDir + "\\GameplayTweaks.log";
	g_gtLogVerbose = verbose;
	g_gtLogSessionStart = GetTickCount();
	g_gtLogBytes = 0;
	// One truncation per launch. Everything after this belongs to this session,
	// which is what makes "the log is silent" positive evidence.
	DeleteFileA(g_gtLogPath.c_str());
	g_gtLogStarted = true;
	gtLog("core", GT_INFO, std::string("session start build=") +
		(buildLabel ? buildLabel : "unknown") +
		" verbose=" + (verbose ? "1" : "0") +
		" date=" __DATE__ " " __TIME__);
}
