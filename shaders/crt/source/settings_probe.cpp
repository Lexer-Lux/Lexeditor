// SPDX-License-Identifier: MIT
// Offscreen check of the settings plumbing behind the Lexer CRT overlay:
//   settings_probe <copy of LexerCRT folder> <wrapper, e.g. PS1.slangp>
// Loads the chain's parameters, changes one live and confirms the frame
// changes, saves it to the wrapper and confirms a fresh chain loads it back.
// Run it on a copy: it rewrites the wrapper.
#include "renderer.hpp"
#include <cstdio>
#include <cstring>
#include <vector>
using namespace lexer_crt;

// Mega Bezel animates every frame (grain, interlacing, flicker), so nearly
// every pixel moves a little between identical settings. Compare the average
// change per channel instead of counting changed pixels.
static double mean_difference(const std::vector<unsigned char>& a, const std::vector<unsigned char>& b) {
    double total = 0;
    for (size_t i = 0; i < a.size(); i += 4)
        for (int c = 0; c < 3; ++c) total += std::abs(int(a[i + c]) - int(b[i + c]));
    return total / (a.size() / 4 * 3);
}

static std::vector<unsigned char> frame(ID3D11Device* d, ID3D11DeviceContext* ctx, Renderer& renderer) {
    const UINT width = 640, height = 480;
    std::vector<unsigned char> pixels(width * height * 4);
    for (UINT y = 0; y < height; y++)
        for (UINT x = 0; x < width; x++) {
            auto i = (y * width + x) * 4;
            pixels[i] = x * 255 / width; pixels[i + 1] = y * 255 / height;
            pixels[i + 2] = ((x / 20 + y / 20) % 2) * 255; pixels[i + 3] = 255;
        }
    D3D11_TEXTURE2D_DESC desc = {};
    desc.Width = width; desc.Height = height; desc.ArraySize = desc.MipLevels = desc.SampleDesc.Count = 1;
    desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM; desc.BindFlags = D3D11_BIND_RENDER_TARGET;
    D3D11_SUBRESOURCE_DATA initial = {pixels.data(), width * 4, 0};
    ComPtr<ID3D11Texture2D> target; check(d->CreateTexture2D(&desc, &initial, &target));
    ComPtr<ID3D11RenderTargetView> out; check(d->CreateRenderTargetView(target.Get(), nullptr, &out));
    for (int i = 0; i < 12; i++) {  // enough frames for afterglow to settle
        ctx->UpdateSubresource(target.Get(), 0, nullptr, pixels.data(), width * 4, 0);
        renderer.render(ctx, out.Get(), 16);
    }
    desc.BindFlags = 0; desc.Usage = D3D11_USAGE_STAGING; desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    ComPtr<ID3D11Texture2D> read; check(d->CreateTexture2D(&desc, nullptr, &read));
    ctx->CopyResource(read.Get(), target.Get());
    D3D11_MAPPED_SUBRESOURCE mapped; check(ctx->Map(read.Get(), 0, D3D11_MAP_READ, 0, &mapped));
    std::vector<unsigned char> result(width * height * 4);
    for (UINT y = 0; y < height; y++)
        std::memcpy(&result[y * width * 4], (unsigned char*)mapped.pData + y * mapped.RowPitch, width * 4);
    ctx->Unmap(read.Get(), 0);
    return result;
}

int main(int argc, char** argv) {
    if (argc < 3) return 64;
    try {
        const auto folder = std::filesystem::u8path(argv[1]);
        const auto wrapper_path = folder / std::filesystem::u8path(argv[2]);
        ComPtr<ID3D11Device> d; ComPtr<ID3D11DeviceContext> ctx;
        check(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &d, nullptr, &ctx));

        Renderer renderer(d.Get(), ctx.Get(), wrapper_path.u8string());
        size_t headings = 0, settings = 0, overridden = 0;
        for (const auto& p : renderer.params) {
            headings += p.heading(); settings += p.setting();
            overridden += p.setting() && std::fabs(p.saved - p.base) > 1e-6f;
        }
        std::printf("%zu parameters: %zu settings, %zu section headings, %zu overridden by the wrapper\n",
                    renderer.params.size(), settings, headings, overridden);
        if (!overridden) throw std::runtime_error("the wrapper's own overrides were not recognised");
        if (renderer.params.size() < 50) throw std::runtime_error("expected the full chain's parameters");
        std::printf("first entries in chain order:\n");
        for (size_t i = 0; i < renderer.params.size() && i < 14; ++i)
            std::printf("  %s%s [%g..%g step %g] = %g\n", renderer.params[i].heading() ? "== " : "",
                        renderer.params[i].label.c_str(), renderer.params[i].minimum, renderer.params[i].maximum,
                        renderer.params[i].step, renderer.params[i].value);

        // A setting whose effect is certain: a real brightness control.
        Param* target = nullptr;
        for (auto& p : renderer.params)
            if (p.setting() && p.maximum - p.minimum >= 1 && p.label.find("Brightness") != std::string::npos) { target = &p; break; }
        if (!target) throw std::runtime_error("no brightness setting found");
        const auto before = frame(d.Get(), ctx.Get(), renderer);
        const auto steady = frame(d.Get(), ctx.Get(), renderer);
        const double drift = mean_difference(before, steady);
        std::printf("unchanged settings: frames differ by %.2f levels on average (animation)\n", drift);
        const float original = target->value;
        target->value = original > (target->minimum + target->maximum) / 2 ? target->minimum : target->maximum;
        renderer.set(*target);
        if (std::fabs(renderer.get(target->name) - target->value) > 1e-6f) throw std::runtime_error("set_param did not take");
        const auto after = frame(d.Get(), ctx.Get(), renderer);
        const double change = mean_difference(steady, after);
        std::printf("live change %s (%s): %g -> %g moved the frame %.2f levels on average\n", target->name.c_str(),
                    target->label.c_str(), original, target->value, change);
        if (change < drift * 4 + 2) throw std::runtime_error("changing a parameter did not change the frame");

        auto wrapper = read_wrapper(wrapper_path);
        const auto reference = wrapper.reference;
        store(wrapper, renderer.params);
        write_wrapper(wrapper_path, wrapper);
        Renderer reloaded(d.Get(), ctx.Get(), wrapper_path.u8string());
        const Param* back = nullptr;
        for (const auto& p : reloaded.params) if (p.name == target->name) back = &p;
        if (!back || std::fabs(back->value - target->value) > 1e-4f) throw std::runtime_error("saved value did not load back");
        if (std::fabs(back->base - target->base) > 1e-6f) throw std::runtime_error("original value changed on save");
        const auto saved = read_wrapper(wrapper_path);
        if (saved.reference != reference) throw std::runtime_error("#reference line lost");
        for (const auto& p : renderer.params)
            if (p.setting() && std::fabs(p.saved - p.base) > 1e-6f && !saved.overrides.count(p.name))
                throw std::runtime_error("an existing override was dropped on save: " + p.name);
        std::printf("saved and reloaded: %s = %g (original still %g)\n", back->name.c_str(), back->value, back->base);
        check(d->GetDeviceRemovedReason());
        std::puts("settings probe passed");
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
