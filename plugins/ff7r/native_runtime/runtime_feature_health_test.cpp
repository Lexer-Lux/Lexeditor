#include "RuntimeFeatureHealth.hpp"

using namespace lexeditor::ff7r;

int main() {
    FeatureHealth health;
    if (health.active || health.consecutiveFailures != 0) {
        return 1;
    }

    if (!health.observe(true) || !health.active || health.consecutiveFailures != 0) {
        return 2;
    }
    if (health.observe(true) || !health.active) {
        return 3;
    }

    for (std::uint32_t failure = 1; failure < kFeatureFailureThreshold; ++failure) {
        if (health.observe(false) || !health.active
                || health.consecutiveFailures != failure) {
            return 4;
        }
    }
    if (!health.observe(false) || health.active
            || health.consecutiveFailures != kFeatureFailureThreshold) {
        return 5;
    }

    if (!health.observe(true) || !health.active || health.consecutiveFailures != 0) {
        return 6;
    }
    if (!health.deactivate() || health.active || health.consecutiveFailures != 0) {
        return 7;
    }
    if (health.deactivate()) {
        return 8;
    }

    return 0;
}
