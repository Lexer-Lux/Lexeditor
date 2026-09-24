
#include "renderer.hpp"
#include <cstdio>
#include <vector>
using namespace lexer_crt;
int main(int argc,char**argv) {if(argc<3)return 64;try {
 ComPtr<ID3D11Device>d;ComPtr<ID3D11DeviceContext>ctx;check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,nullptr,0,D3D11_SDK_VERSION,&d,nullptr,&ctx));
 Renderer renderer(d.Get(),ctx.Get(),argv[1]);puts("DX11 chain compiled");fflush(stdout);
 UINT width=1280,height=720;if(argc>3){width=1920;height=1080;}
 std::vector<unsigned char> pixels(width*height*4);
 for(UINT y=0;y<height;y++)for(UINT x=0;x<width;x++) {auto i=(y*width+x)*4;pixels[i]=x*255/width;pixels[i+1]=y*255/height;pixels[i+2]=((x/20+y/20)%2)*255;pixels[i+3]=255;}
 D3D11_TEXTURE2D_DESC desc={};desc.Width=width;desc.Height=height;desc.ArraySize=desc.MipLevels=desc.SampleDesc.Count=1;desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.BindFlags=D3D11_BIND_RENDER_TARGET;
 D3D11_SUBRESOURCE_DATA initial={pixels.data(),width*4,0};ComPtr<ID3D11Texture2D>target;check(d->CreateTexture2D(&desc,&initial,&target));ComPtr<ID3D11RenderTargetView>out;check(d->CreateRenderTargetView(target.Get(),nullptr,&out));
 D3D11_VIEWPORT sentinel={3,5,81,91,0,1};ctx->RSSetViewports(1,&sentinel);
 for(int i=0;i<4;i++){ctx->UpdateSubresource(target.Get(),0,nullptr,pixels.data(),width*4,0);renderer.render(ctx.Get(),out.Get(),16);}
 D3D11_VIEWPORT actual={};UINT count=1;ctx->RSGetViewports(&count,&actual);if(actual.TopLeftX!=3||actual.Height!=91)throw std::runtime_error("Context state not restored");
 desc.BindFlags=0;desc.Usage=D3D11_USAGE_STAGING;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;ComPtr<ID3D11Texture2D>read;check(d->CreateTexture2D(&desc,nullptr,&read));ctx->CopyResource(read.Get(),target.Get());D3D11_MAPPED_SUBRESOURCE mapped;check(ctx->Map(read.Get(),0,D3D11_MAP_READ,0,&mapped));
 FILE*f=fopen(argv[2],"wb");fprintf(f,"P6\n%u %u\n255\n",width,height);size_t changed=0,nonzero=0;for(UINT y=0;y<height;y++)for(UINT x=0;x<width;x++){auto p=(unsigned char*)mapped.pData+y*mapped.RowPitch+x*4;fwrite(p,1,3,f);if(p[0]||p[1]||p[2])nonzero++;if(memcmp(p,&pixels[(y*width+x)*4],3))changed++;}fclose(f);ctx->Unmap(read.Get(),0);check(d->GetDeviceRemovedReason());printf("DX11 rendered: %zu nonzero, %zu changed; context restored\n",nonzero,changed);return changed&&nonzero?0:2;
 }catch(const std::exception&e){fprintf(stderr,"%s\n",e.what());return 1;}}
