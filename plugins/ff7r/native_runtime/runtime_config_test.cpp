#include "RuntimeConfig.hpp"

#include <cassert>
#include <cmath>
#include <string>

using lexeditor::ff7r::RuntimeConfigError;
using lexeditor::ff7r::parseRuntimeConfig;

namespace {

template <typename Callback>
bool throwsConfigError(Callback&& callback) {
    try {
        callback();
    } catch (const RuntimeConfigError&) {
        return true;
    }
    return false;
}

} // namespace

int main() {
    const std::string canonical = R"json(
    {
      "schemaVersion": 1,
      "cutsceneSpeed": {
        "enabled": true,
        "baseMultiplier": 1.5,
        "r2Behavior": "multiply-native"
      },
      "minimap": {
        "enabled": true,
        "holdMilliseconds": 425,
        "persistChosenState": false,
        "tapBehavior": "open-map",
        "holdBehavior": "toggle-minimap"
      },
      "hpRebalance": {
        "enabled": true,
        "hpMultiplier": 0.5
      },
      "betterSprint": {
        "enabled": true,
        "speedMultiplier": 1.25
      }
    }
    )json";

    const auto config = parseRuntimeConfig(canonical);
    assert(config.schemaVersion == 1);
    assert(config.cutsceneSpeed.enabled);
    assert(std::abs(config.cutsceneSpeed.baseMultiplier - 1.5) < 0.000001);
    assert(config.minimap.enabled);
    assert(config.minimap.holdMilliseconds == 425);
    assert(!config.minimap.persistChosenState);
    assert(config.hpRebalance.enabled);
    assert(std::abs(config.hpRebalance.multiplier - 0.5) < 0.000001);
    assert(config.betterSprint.enabled);
    assert(std::abs(config.betterSprint.multiplier - 1.25) < 0.000001);

    const auto defaults = parseRuntimeConfig(R"json({
        "schemaVersion":1,
        "cutsceneSpeed":{},
        "minimap":{},
        "hpRebalance":{},
        "betterSprint":{}
    })json");
    assert(!defaults.cutsceneSpeed.enabled);
    assert(std::abs(defaults.cutsceneSpeed.baseMultiplier - 1.25) < 0.000001);
    assert(!defaults.minimap.enabled);
    assert(defaults.minimap.holdMilliseconds == 350);
    assert(defaults.minimap.persistChosenState);
    assert(!defaults.hpRebalance.enabled);
    assert(std::abs(defaults.hpRebalance.multiplier - 0.5) < 0.000001);
    assert(!defaults.betterSprint.enabled);
    assert(std::abs(defaults.betterSprint.multiplier - 1.0) < 0.000001);

    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({"schemaVersion":2})json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({"schemaVersion":1,"unknown":true})json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({"schemaVersion":1,"schemaVersion":1})json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "cutsceneSpeed":{"enabled":true,"baseMultiplier":1.0,"r2Behavior":"multiply-native"}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "cutsceneSpeed":{"r2Behavior":"replace-native"}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "minimap":{"holdMilliseconds":149}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "minimap":{"holdMilliseconds":1501}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "minimap":{"tapBehavior":"toggle-minimap"}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "hpRebalance":{"hpMultiplier":0}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({
          "schemaVersion":1,
          "betterSprint":{"speedMultiplier":-1}
        })json");
    }));
    assert(throwsConfigError([] {
        (void)parseRuntimeConfig(R"json({"schemaVersion":1} trailing)json");
    }));

    return 0;
}
