// SPDX-License-Identifier: MIT
#pragma once
#define LIBRA_RUNTIME_D3D11
#include <librashader.h>
#include "settings.hpp"
#include <d3d11.h>
#include <wrl/client.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace lexer_crt {
using Microsoft::WRL::ComPtr;
inline void check(libra_error_t error) {
    if (!error) return;
    char* message = nullptr;
    libra_error_write(error, &message);
    std::string text = message ? message : "Shader runtime error";
    if (message) libra_error_free_string(&message);
    libra_error_free(&error);
    throw std::runtime_error(text);
}
// A lookup that may legitimately find nothing: false instead of an exception.
inline bool found(libra_error_t error) {
    if (!error) return true;
    libra_error_free(&error);
    return false;
}
inline void check(HRESULT hr) {
    if (FAILED(hr)) throw std::runtime_error("DirectX 11 error: " + std::to_string(hr));
}

// Record into a separate context. ExecuteCommandList(TRUE) restores the game's
// complete immediate-context state, including slots this shader does not use.
class Renderer {
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> deferred;
    ComPtr<ID3D11Texture2D> input;
    ComPtr<ID3D11ShaderResourceView> source;
    libra_d3d11_filter_chain_t chain = nullptr;
    size_t frame = 0;
    D3D11_TEXTURE2D_DESC previous = {};

    // Every tunable parameter of the chain, in the order the passes declare
    // them, with the original preset's value and the wrapper's saved value.
    void load_params(libra_shader_preset_t* shader, const std::string& preset) {
        libra_preset_param_list_t list = {};
        check(libra_preset_get_runtime_params(shader, &list));
        std::vector<Param> loaded;
        for (uint64_t i = 0; i < list.length; ++i) {
            const auto& raw = list.parameters[i];
            Param param;
            param.name = raw.name;
            param.label = raw.description && *raw.description ? raw.description : raw.name;
            param.minimum = raw.minimum;
            param.maximum = raw.maximum;
            param.step = raw.step;
            // "initial" already includes this preset's overrides: it is the live value.
            param.value = param.saved = param.base = raw.initial;
            loaded.push_back(param);
        }
        libra_preset_free_runtime_params(list);
        // The original chain's effective values come from the referenced preset,
        // loaded on its own, so saving never mistakes an override for a default.
        auto wrapper = read_wrapper(std::filesystem::u8path(preset));
        if (!wrapper.reference.empty()) {
            auto original = std::filesystem::u8path(preset).parent_path() / std::filesystem::u8path(wrapper.reference);
            libra_shader_preset_t source = nullptr;
            if (found(libra_preset_create(original.u8string().c_str(), &source))) {
                libra_preset_param_list_t originals = {};
                if (found(libra_preset_get_runtime_params(&source, &originals))) {
                    for (uint64_t i = 0; i < originals.length; ++i)
                        for (auto& param : loaded)
                            if (param.name == originals.parameters[i].name) param.base = originals.parameters[i].initial;
                    libra_preset_free_runtime_params(originals);
                }
                libra_preset_free(&source);
            }
        }
        const auto order = parameter_order(std::filesystem::u8path(preset));
        auto rank = [&](const Param& param) {
            auto at = std::find(order.begin(), order.end(), param.name);
            return at == order.end() ? order.size() : size_t(at - order.begin());
        };
        std::stable_sort(loaded.begin(), loaded.end(), [&](const Param& a, const Param& b) { return rank(a) < rank(b); });
        for (auto& param : loaded) param.label = trim(param.label);
        params = std::move(loaded);
    }
public:
    std::vector<Param> params;

    Renderer(ID3D11Device* dev, ID3D11DeviceContext* immediate, const std::string& preset) : device(dev) {
        check(device->CreateDeferredContext(0, &deferred));
        libra_shader_preset_t shader = nullptr;
        check(libra_preset_create(preset.c_str(), &shader));
        try { load_params(&shader, preset); } catch (...) { libra_preset_free(&shader); throw; }
        filter_chain_d3d11_opt_t options = {};
        options.version = LIBRASHADER_CURRENT_VERSION;
        try {
            check(libra_d3d11_filter_chain_create_deferred(&shader, device.Get(), deferred.Get(), &options, &chain));
            submit(immediate);
        } catch (...) {
            if (shader) libra_preset_free(&shader);
            if (chain) libra_d3d11_filter_chain_free(&chain);
            throw;
        }
    }
    Renderer(const Renderer&) = delete;
    Renderer& operator=(const Renderer&) = delete;
    ~Renderer() { if (chain) libra_d3d11_filter_chain_free(&chain); }
    void set(const Param& param) { check(libra_d3d11_filter_chain_set_param(&chain, param.name.c_str(), param.value)); }
    float get(const std::string& name) const {
        float value = 0;
        check(libra_d3d11_filter_chain_get_param(&chain, name.c_str(), &value));
        return value;
    }
    void submit(ID3D11DeviceContext* immediate) {
        ComPtr<ID3D11CommandList> commands;
        check(deferred->FinishCommandList(FALSE, &commands));
        immediate->ExecuteCommandList(commands.Get(), TRUE);
    }
    void render(ID3D11DeviceContext* immediate, ID3D11RenderTargetView* output, unsigned delta_ms) {
        ComPtr<ID3D11Resource> resource;
        output->GetResource(&resource);
        ComPtr<ID3D11Texture2D> texture;
        check(resource.As(&texture));
        D3D11_TEXTURE2D_DESC desc;
        texture->GetDesc(&desc);
        if (desc.SampleDesc.Count != 1 || desc.ArraySize != 1)
            throw std::runtime_error("Unsupported multisample or array output");
        if (!input || desc.Width != previous.Width || desc.Height != previous.Height || desc.Format != previous.Format) {
            source.Reset(); input.Reset(); previous = desc;
            desc.Usage = D3D11_USAGE_DEFAULT;
            desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
            desc.CPUAccessFlags = desc.MiscFlags = 0;
            check(device->CreateTexture2D(&desc, nullptr, &input));
            D3D11_SHADER_RESOURCE_VIEW_DESC view = {};
            D3D11_RENDER_TARGET_VIEW_DESC target;
            output->GetDesc(&target);
            view.Format = target.Format;
            view.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
            view.Texture2D.MipLevels = 1;
            check(device->CreateShaderResourceView(input.Get(), &view, &source));
            frame = 0;
        }
        deferred->CopyResource(input.Get(), texture.Get());
        frame_d3d11_opt_t options = {};
        options.version = LIBRASHADER_CURRENT_VERSION;
        options.clear_history = frame == 0;
        options.frame_direction = 1;
        options.total_subframes = options.current_subframe = 1;
        options.frames_per_second = delta_ms ? 1000.0f / delta_ms : 60.0f;
        options.frametime_delta = delta_ms;
        options.brightness_nits = 200;
        check(libra_d3d11_filter_chain_frame(&chain, deferred.Get(), frame++, source.Get(), output, nullptr, nullptr, &options));
        submit(immediate);
    }
};
}
