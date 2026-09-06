static void near(float a,float b) { assert(std::abs(a-b)<0.001f); }
static std::uint32_t native_row(std::uint8_t *,std::uint32_t,std::uint32_t,int) {
    g_hp_row->right=300;
    g_hp_row->hp_visible=g_hp_row->atb_visible=true;
    return 71;
}
static void word(void *p,unsigned offset,std::uint16_t n) {std::memcpy(static_cast<std::uint8_t *>(p)+offset,&n,2);}
int main() {
    assert(mmap(reinterpret_cast<void *>(0x1CFF000),0x2000,PROT_READ|PROT_WRITE,
        MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0)!=MAP_FAILED);
    g_battle_row_renderer=&native_row;
    for(int i=0;i<3;++i) {
        const int gf=15-i;
        save_map.chars[i].gfs=1U<<gf;
        save_map.gfs[gf].exists=1;save_map.gfs[gf].HPs=4000;
        *reinterpret_cast<std::uint16_t *>(0x1CFF61A+gf*12)=8000;
        std::uint8_t row[0x6C]{};
        row[0x48]=i;word(row,8,122);word(row,10,171+i*15);
        word(row,0x1C,6000);word(row,0x1E,3000);
        assert(battle_row_hook(row,0,0,0)==71);
        assert(g_hp_rows[i].gf_current==4000 && g_hp_rows[i].gf_maximum==8000);
        assert(g_hp_rows[i].current==3000 && g_hp_rows[i].maximum==6000);
    }
    // Exercise real drawing code with different native viewport transforms.
    for(float scale:{1.0f,2.0f,1.5f}) {
        for(auto &row:g_hp_rows) {row.viewport.scale_x=scale;row.viewport.scale_y=scale;row.viewport.offset_x=7;row.viewport.offset_y=11;}
        draw_list.rectangles.clear();draw_battle_hp();assert(draw_list.rectangles.size()==12);
        for(int i=0;i<3;++i) {
            auto hp=draw_list.rectangles[i*4+1],gf=draw_list.rectangles[i*4+3];
            near(hp.lo.y,(171+i*15+14)*scale+11);near(hp.hi.y-hp.lo.y,scale);
            near(gf.lo.y,(171+i*15+1)*scale+11);near(gf.hi.y-gf.lo.y,scale);
            near(hp.hi.x,300*scale+7);near(gf.lo.x,122*scale+7);
            near(hp.hi.x-hp.lo.x,178*scale*6000/9999/2);
            near(gf.hi.x-gf.lo.x,178*scale*8000/9999/2);
            assert(hp.color==IM_COL32(224,32,32,255));assert(gf.color==IM_COL32(48,128,255,255));
        }
    }
    // Live charging values supersede saved GF values, including zero HP.
    auto *st=reinterpret_cast<std::uint8_t *>(&stats[0]);st[0x1C]=1;st[0x1D]=0x4F;
    word(st,0x18,1000);word(st,0x1A,8000);
    HpCapture live{};capture_gf_hp(0,live);assert(live.gf_current==1000 && live.gf_maximum==8000);
    word(st,0x18,0);live={};capture_gf_hp(0,live);assert(live.gf_current==0 && live.gf_maximum==8000);
    // Aggregate distinct junctioned GFs; exclude ones not present; clamp HP.
    save_map.chars[0].gfs|=1;
    save_map.gfs[0].exists=1;save_map.gfs[0].HPs=9999;
    *reinterpret_cast<std::uint16_t *>(0x1CFF61A)=2000;
    live={};capture_gf_hp(0,live);assert(live.gf_current==2000 && live.gf_maximum==10000);
    save_map.gfs[0].exists=0;live={};capture_gf_hp(0,live);assert(live.gf_maximum==8000);
    save_map.chars[0].gfs=0;live={};capture_gf_hp(0,live);assert(live.gf_current==0 && live.gf_maximum==0);
    // Independent switches, empty data, hidden rows and mode transitions.
    enable_ff8_hp_bars=false;draw_list.rectangles.clear();draw_battle_hp();assert(draw_list.rectangles.size()==6);
    enable_ff8_gf_hp_bars=false;draw_list.rectangles.clear();draw_battle_hp();assert(draw_list.rectangles.empty());
    assert(!lexeditor_ff8_bars_enabled());
    enable_ff8_hp_bars=true;enable_ff8_gf_hp_bars=true;
    g_hp_rows[1].atb_visible=false;draw_list.rectangles.clear();draw_battle_hp();assert(draw_list.rectangles.size()==8);
    mode.driver_mode=MODE_MENU;draw_list.rectangles.clear();draw_battle_hp();assert(draw_list.rectangles.empty());
    mode.driver_mode=MODE_BATTLE;lexeditor_ff8_bars_draw();assert(!g_hp_rows[0].atb_visible);
    std::puts("PASS: compiled production bar capture/draw: all slots, native geometry/scaling, opposite fill directions, live GF damage, multiple GFs, independent toggles and stale-frame clearing.");
}
