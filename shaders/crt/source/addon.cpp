// SPDX-License-Identifier: MIT
#include "renderer.hpp"
// The overlay talks to ReShade's own Dear ImGui through its function table;
// imgui.h must be the exact version ReShade was built with (1.92.5 docking).
#define ImTextureID ImU64
#include <imgui.h>
#include <reshade.hpp>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <memory>
#include <unordered_map>
#include <chrono>

using namespace lexer_crt;
static std::filesystem::path base;
struct State {
    std::unique_ptr<Renderer> renderer;
    std::string preset;
    std::string error;
    bool failed = false;
    std::chrono::steady_clock::time_point last;
};
static std::unordered_map<reshade::api::effect_runtime*, State> states;

static void render(reshade::api::effect_runtime* runtime, reshade::api::command_list*, reshade::api::resource_view rtv, reshade::api::resource_view) {
    if (!runtime->get_effects_state() || !rtv.handle) return;
    auto technique = runtime->find_technique("LexerCRT.fx", "Lexer_CRT");
    if (!technique.handle || !runtime->get_technique_state(technique)) return;
    char preset_path[32768] = {};
    runtime->get_current_preset_path(preset_path);
    auto filename = std::filesystem::u8path(preset_path).filename().string();
    std::string preset;
    if (filename == "Lexer-PS1.ini") preset = "PS1.slangp";
    else if (filename == "Lexer-N64.ini") preset = "N64.slangp";
    else return;
    auto& state = states[runtime];
    if (state.preset != preset) {
        state.renderer.reset(); state.preset = preset; state.failed = false;
    }
    if (state.failed) return;
    try {
        if (runtime->get_device()->get_api() != reshade::api::device_api::d3d11)
            throw std::runtime_error("Lexer CRT requires DirectX 11.");
        auto device = reinterpret_cast<ID3D11Device*>(runtime->get_device()->get_native());
        ComPtr<ID3D11DeviceContext> context;
        device->GetImmediateContext(&context);
        if (!state.renderer) {
            reshade::log::message(reshade::log::level::info, ("Lexer CRT: compiling " + preset).c_str());
            state.renderer = std::make_unique<Renderer>(device, context.Get(), (base / "LexerCRT" / preset).u8string());
            state.last = std::chrono::steady_clock::now();
        }
        auto now = std::chrono::steady_clock::now();
        auto delta = std::chrono::duration_cast<std::chrono::milliseconds>(now - state.last).count();
        state.last = now;
        state.renderer->render(context.Get(), reinterpret_cast<ID3D11RenderTargetView*>(rtv.handle), static_cast<unsigned>(delta));
    } catch (const std::exception& error) {
        state.failed = true;
        state.error = error.what();
        reshade::log::message(reshade::log::level::error, error.what());
    }
}

static std::string lower(std::string text) {
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) { return char(std::tolower(c)); });
    return text;
}

static const char* number_format(float step) {
    if (step >= 1 || step <= 0) return step <= 0 ? "%.3f" : "%.0f";
    if (step >= 0.1f) return "%.1f";
    if (step >= 0.01f) return "%.2f";
    return "%.3f";
}

// Every parameter of the running chain as a live slider. Values apply on the
// next frame; Save writes the ones that differ from the original chain into the
// wrapper preset (PS1.slangp / N64.slangp), which RetroArch reads as well.
static void draw_settings(reshade::api::effect_runtime* runtime) {
    static char filter[128] = {};
    auto it = states.find(runtime);
    if (it == states.end() || !it->second.renderer) {
        if (it != states.end() && it->second.failed)
            ImGui::TextWrapped("Lexer CRT could not start %s: %s", it->second.preset.c_str(), it->second.error.c_str());
        else
            ImGui::TextWrapped("Turn on Lexer CRT and choose Lexer-PS1.ini or Lexer-N64.ini on the Home tab. "
                               "The chain's settings appear here once it is running.");
        return;
    }
    auto& state = it->second;
    auto& params = state.renderer->params;
    const auto preset = base / "LexerCRT" / std::filesystem::u8path(state.preset);
    size_t unsaved = 0, changed = 0;
    for (const auto& param : params) {
        if (!param.setting()) continue;
        unsaved += param.value != param.saved;
        changed += std::fabs(param.value - param.base) > 1e-6f;
    }
    const auto settings = std::count_if(params.begin(), params.end(), [](const Param& p) { return p.setting(); });
    ImGui::Text("%s: %zu settings, %zu changed from the original chain", state.preset.c_str(), size_t(settings), changed);
    ImGui::BeginDisabled(unsaved == 0);
    if (ImGui::Button("Save")) {
        try {
            auto wrapper = read_wrapper(preset);
            store(wrapper, params);
            write_wrapper(preset, wrapper);
            for (auto& param : params) param.saved = param.value;
        } catch (const std::exception& error) {
            reshade::log::message(reshade::log::level::error, error.what());
        }
    }
    ImGui::SameLine(0, -1);
    if (ImGui::Button("Revert")) {
        for (auto& param : params) {
            if (!param.setting() || param.value == param.saved) continue;
            param.value = param.saved;
            state.renderer->set(param);
        }
    }
    ImGui::EndDisabled();
    ImGui::SameLine(0, -1);
    if (ImGui::Button("Original")) {
        for (auto& param : params) {
            if (!param.setting() || param.value == param.base) continue;
            param.value = param.base;
            state.renderer->set(param);
        }
    }
    if (ImGui::IsItemHovered(0)) ImGui::SetTooltip("Every setting back to the original chain's value (not saved until Save).");
    if (unsaved) {
        ImGui::SameLine(0, -1);
        ImGui::TextDisabled("%zu unsaved", unsaved);
    }
    ImGui::SetNextItemWidth(-1);
    ImGui::InputText("##filter", filter, sizeof filter, 0, nullptr, nullptr);
    const auto needle = lower(filter);
    ImGui::BeginChild("settings", ImVec2(0, 0), 0, 0);
    for (size_t i = 0; i < params.size(); ++i) {
        auto& param = params[i];
        if (param.heading()) {
            if (needle.empty()) ImGui::SeparatorText(param.label.c_str());
            continue;
        }
        if (param.spacer()) continue;
        if (!needle.empty() && lower(param.label).find(needle) == std::string::npos &&
            lower(param.name).find(needle) == std::string::npos)
            continue;
        ImGui::PushID(int(i));
        float value = param.value;
        ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x * 0.45f);
        if (ImGui::SliderFloat(param.label.c_str(), &value, param.minimum, param.maximum,
                               number_format(param.step), ImGuiSliderFlags_AlwaysClamp)) {
            if (param.step > 0)
                value = param.minimum + std::round((value - param.minimum) / param.step) * param.step;
            value = (std::clamp)(value, (std::min)(param.minimum, param.maximum), (std::max)(param.minimum, param.maximum));
            if (value != param.value) {
                param.value = value;
                try { state.renderer->set(param); }
                catch (const std::exception& error) { reshade::log::message(reshade::log::level::error, error.what()); }
            }
        }
        if (ImGui::IsItemHovered(0))
            ImGui::SetTooltip("%s\nOriginal: %g", param.name.c_str(), param.base);
        if (std::fabs(param.value - param.base) > 1e-6f) {
            ImGui::SameLine(0, -1);
            ImGui::TextDisabled("*");
        }
        ImGui::PopID();
    }
    ImGui::EndChild();
}
static void destroy(reshade::api::effect_runtime* runtime) { states.erase(runtime); }
extern "C" __declspec(dllexport) const char* NAME = "Lexer CRT";
extern "C" __declspec(dllexport) const char* DESCRIPTION = "Original PS1 and N64 Mega Bezel presets through librashader, with every setting on the Lexer CRT tab. DirectX 11.";
BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        if (!reshade::register_addon(module)) return FALSE;
        wchar_t path[32768] = {};
        GetModuleFileNameW(module, path, 32768);
        base = std::filesystem::path(path).parent_path();
        reshade::register_event<reshade::addon_event::reshade_finish_effects>(render);
        reshade::register_event<reshade::addon_event::destroy_effect_runtime>(destroy);
        reshade::register_overlay("Lexer CRT", draw_settings);
    } else if (reason == DLL_PROCESS_DETACH) {
        reshade::unregister_overlay("Lexer CRT", draw_settings);
        reshade::unregister_addon(module);
    }
    return TRUE;
}
