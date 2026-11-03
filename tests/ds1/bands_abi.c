/* Only calling-convention adapters. No game code or data is included. */
typedef int (__attribute__((ms_abi)) *class_fn)(float, float, int, int);
typedef float (__attribute__((ms_abi)) *rate_fn)(float, float, int, int);
typedef float (__attribute__((ms_abi)) *fraction_fn)(float, float);
int bands_class(void *function, float weight, float capacity, int special, int forced) {
    return ((class_fn)function)(weight, capacity, special, forced);
}
float bands_rate(void *function, float weight, float capacity, int special, int forced) {
    return ((rate_fn)function)(weight, capacity, special, forced);
}
float bands_fraction(void *function, float weight, float capacity) {
    return ((fraction_fn)function)(weight, capacity);
}
