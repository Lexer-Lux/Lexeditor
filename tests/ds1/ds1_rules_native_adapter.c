/* Original test adapter. Calls isolated Microsoft-x64 game functions on x86-64 Linux. */
typedef float (__attribute__((ms_abi)) *rate_fn)(void *);
typedef int (__attribute__((ms_abi)) *tier_fn)(float, float, unsigned, unsigned);
typedef float (__attribute__((ms_abi)) *fraction_fn)(float, float);
float call_rate(void *fn, void *player) { return ((rate_fn)fn)(player); }
int call_tier(void *fn, float current, float maximum, unsigned special, unsigned forced) {
    return ((tier_fn)fn)(current, maximum, special, forced);
}
float call_fraction(void *fn, float current, float maximum) {
    return ((fraction_fn)fn)(current, maximum);
}
