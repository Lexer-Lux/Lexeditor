/* Authored native-code patch for issue #902. No game code or assets are copied.
 * Compiled as freestanding x64 COFF; deployed by ammunition_controls.py, not a DLL.
 * All game addresses are RIP-relative to the linker-provided `game` symbol.
 * The only mutable storage is the explicitly extended .data tail (scratch).
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef long long i64;

extern u8 game[];
typedef struct {
    void *player, *data, *assembly;
    int weapon, hand, kind, slot;
    u32 previous, armed, saw_busy, held_key;
    int pending;
    void *hud_root, *hud_children[2];
    u8 hud_visible[2];
} ShotState;
extern ShotState scratch;
_Static_assert(sizeof(ShotState) <= 128, "Reserved state allocation");

#define AT(t, p, o) (*(t *)((u8 *)(p) + (o)))
#define NATIVE(t, o) ((t)(game + (o)))
typedef void (*VoidOne)(void *);
typedef void *(*ChildFn)(void *, const u16 *);
typedef void (*VisibleFn)(void *, u8);
typedef void (*TextFn)(void *, const u16 *);
typedef int (*VarFn)(int);
typedef void (*ParamFn)(void *, int);

typedef struct {
    int id, pad;
    void *param;
    int base_id, pad2;
    int reinforce_id, pad3;
    void *reinforce;
} WeaponRef;

static void *param(int id) {
    WeaponRef ref;
    /* The native resolver initializes all fields, including the reinforcement
       sub-reference. Negative item IDs return a null parameter. */
    NATIVE(ParamFn, 0x532b20)(&ref, id);
    return ref.param;
}
static void *player_data(void) {
    void *manager = AT(void *, game, 0x1c8a530);
    return manager ? AT(void *, manager, 0x10) : (void *)0;
}
static void *local_player(void) {
    void *world = AT(void *, game, 0x1c77e50);
    return world ? AT(void *, world, 0x68) : (void *)0;
}
static int equipment(void *assembly, int slot) {
    return assembly && (unsigned)slot < 20 ? AT(int, assembly, 0x24 + 4 * slot) : -1;
}
/* R1/R2 operate the right hand, or the left weapon when it is two-handed.
   A ranged left weapon in a normal two-weapon stance never commandeers R1. */
static int weapon(void *assembly, int *hand, int *kind) {
    if (!assembly) return -1;
    int stance = AT(int, assembly, 8);
    if (stance < 1 || stance > 3) return -1;
    *hand = stance == 2 ? 0 : 1;
    int selected = AT(int, assembly, *hand ? 0x10 : 0xc);
    if ((unsigned)selected > 1) return -1;
    int id = equipment(assembly, selected * 2 + *hand);
    void *p = id >= 0 ? param(id) : (void *)0;
    if (!p) return -1;
    *kind = AT(u8, p, 0xe2);
    return *kind == 10 || *kind == 11 ? id : -1;
}
static int quantity(void *equip, int slot) {
    int index = AT(int, equip, 0x24 + 4 * slot);
    int count = AT(int, equip, 0x130), split = AT(int, equip, 0x140);
    if (index < 0 || index >= count || count > 1000000 ||
        split < 0 || split > 1000000) return -1;
    void *table = AT(void *, equip, index < split ? 0x150 : 0x158);
    if (!table) return -1;
    int value = AT(int, table, (u64)(unsigned)index * 0x1c + 8);
    return value >= 0 ? value : -1;
}
static int selection_offset(int hand, int kind) {
    return (kind == 10 ? 0x14 : 0x1c) + hand * 4;
}
static void clear_shot(void) {
    scratch.player = 0;
    scratch.previous = scratch.armed = scratch.saw_busy = scratch.held_key = 0;
    scratch.pending = -1;
}
static int ui_allows(void) {
    u64 flags = NATIVE(u64 (*)(void), 0x71ac10)() & 0xffffffff7ffff77full;
    if (flags && (flags != 8 || !NATIVE(u8 (*)(void), 0x681ee0)())) return 0;
    void *menu = AT(void *, game, 0x1c7b648);
    return !menu || AT(float, menu, 0xc2c) <= 0.0f;
}
/* This is the right-action admission test at 3972A7..397309, not an arbitrary
   timeout or an approximation based on how long an animation usually lasts. */
static int right_admitted(void *ctrl, void *player) {
    if (AT(u8, player, 0x525) & 1) return 0;
    if (!(AT(u8, ctrl, 0x100) & 4)) return 1;
    void *context = AT(void *, ctrl, 0x48);
    return context && ((AT(u32, context, 0x1dc) & 0x80000) ||
           AT(u8, context, 0x1a0) || AT(u8, context, 0x127) ||
           AT(u8, context, 0x12c));
}
static int desired(u32 mask) { return mask & 1 ? 0 : mask & 2 ? 1 : -1; }

/* Called once after native input admission and gesture handling, before the
   native held-duration loop and the character state machine consume the pad.
   `stack` points at the original 396860 frame, not our bridge's shadow space. */
void ammo_route(void *ctrl, void *pad, u8 *stack) {
    void *player = ctrl ? AT(void *, ctrl, 0x10) : (void *)0;
    if (!player || player != local_player()) return;
    void *data = player_data(), *assembly = AT(void *, player, 0x840);
    int hand = 1, kind = 0;
    void *context = AT(void *, ctrl, 0x48);
    if (!data || !context || (AT(u32, context, 0xa4) & 0x08000000)) {
        clear_shot(); return;
    }
    int id = weapon(assembly, &hand, &kind);
    if (id < 0 || AT(int, player, 0x3f8) <= 0 ||
        !ui_allows() || (AT(u8, player, 0x525) & 1)) {
        clear_shot();
        return;
    }
    void *saved = (u8 *)data + 0x300;
    int saved_hand = 1, saved_kind = 0;
    if (weapon(saved, &saved_hand, &saved_kind) != id ||
        saved_hand != hand || saved_kind != kind) {
        /* Do not route through a half-completed equipment/character swap. */
        clear_shot();
        return;
    }
    u32 raw = (stack[0x3b] != 0) | ((u32)(stack[0x3c] != 0) << 1);
    u32 accepted = (AT(u8, pad, 0x84) != 0) | ((u32)(AT(u8, pad, 0x89) != 0) << 1);
    int busy = (AT(u8, ctrl, 0x100) & 4) != 0;
    if (scratch.player != player || scratch.data != data || scratch.assembly != assembly ||
        scratch.weapon != id || scratch.hand != hand || scratch.kind != kind) {
        clear_shot();
        scratch.player = player; scratch.data = data; scratch.assembly = assembly;
        scratch.weapon = id; scratch.hand = hand; scratch.kind = kind;
        scratch.slot = AT(int, assembly, selection_offset(hand, kind)) == 1 ? 1 : 0;
        /* A newly loaded/changed weapon while an action is already in progress
           retains its native selected ammunition until that action finishes. */
        scratch.armed = scratch.saw_busy = (u32)busy;
    }
    u32 rising = raw & ~scratch.previous;
    scratch.previous = raw;
    int queued = AT(int, pad, 0x224);
    if (queued == 0 || queued == 5) {
        scratch.pending = queued == 5 ? 1 : 0;
        AT(int, pad, 0x224) = -1;
    }
    int admitted = right_admitted(ctrl, player);
    if (scratch.armed && rising)
        scratch.pending = desired(rising); /* one bounded latest-request buffer */
    if (scratch.armed) {
        if (busy) scratch.saw_busy = 1;
        if (!busy && (scratch.saw_busy || raw == 0)) {
            /* Do not unlock on the first decrement: Avelyn consumes several
               bolts in one action. A completed/cancelled native action unlocks. */
            scratch.armed = scratch.saw_busy = 0;
            scratch.held_key = 0;
        }
    }
    u8 fire = 0;
    if (!scratch.armed && admitted) {
        int next = scratch.pending >= 0 ? scratch.pending : desired(accepted & raw);
        if (next >= 0) {
            int offset = selection_offset(hand, kind);
            /* Keep game-data quantity/consumption and actor projectile lookups
               on the same slot. Never swap inventory entries or decrement them. */
            AT(int, saved, offset) = next;
            AT(int, assembly, offset) = next;
            scratch.slot = next;
            scratch.armed = 1; scratch.saw_busy = (u32)busy;
            scratch.held_key = 1u << next; scratch.pending = -1;
            fire = 1;
        }
    } else if (scratch.armed && admitted) {
        /* Holding either logical input behaves like holding the native weak
           attack. The other button cannot change a drawn or multi-bolt shot. */
        fire = (u8)((accepted & raw & scratch.held_key) != 0);
    }
    AT(u8, pad, 0x84) = fire;
    AT(u8, pad, 0x8b) = fire;
    AT(u8, pad, 0x89) = 0;
    AT(u8, pad, 0x1c4) |= fire;
}

/* HUD callbacks stay on the native widget update path and never retain a
   widget pointer. The original manager owns creation, transforms and teardown. */
static void *hud_assembly(int *id, int *hand, int *kind) {
    void *data = player_data();
    void *assembly = data ? (u8 *)data + 0x300 : (void *)0;
    *id = weapon(assembly, hand, kind);
    return *id >= 0 ? assembly : (void *)0;
}
static int ranged_active(void) {
    int id = -1, hand = 1, kind = 0;
    return hud_assembly(&id, &hand, &kind) != 0;
}
static void *child(void *root, const u16 *name) {
    return root ? NATIVE(ChildFn, 0xed6020)(root, name) : (void *)0;
}
static void show_child(void *root, const u16 *name, u8 visible) {
    void *c = child(root, name);
    if (c) NATIVE(VisibleFn, 0xedbdb0)(c, visible);
}
static void text_child(void *root, const u16 *name, const u16 *text, u8 visible) {
    void *c = child(root, name);
    if (c) {
        NATIVE(TextFn, 0xedbd90)(c, text);
        NATIVE(VisibleFn, 0xedbdb0)(c, visible);
    }
}
static void format_count(u16 *out, int value) {
    /* Bounded decimal conversion into 12 UTF-16 units, including INT_MAX.
       No native allocator, temporary string object or locale-dependent ABI. */
    if (value < 0) { out[0] = '-'; out[1] = 0; return; }
    u16 reverse[10];
    unsigned n = 0, v = (unsigned)value;
    do { reverse[n++] = (u16)(48 + v % 10); v /= 10; } while (v && n < 10);
    unsigned i = 0;
    while (n) out[i++] = reverse[--n];
    out[i] = 0;
}
void ammo_hud_arrow(void *widget, u8 right) {
    int id = -1, hand = 1, kind = 0;
    void *assembly = hud_assembly(&id, &hand, &kind);
    if (!assembly) {
        NATIVE(void (*)(void *, u8), 0x678500)(widget, right);
        return;
    }
    int slot = (kind == 11 ? 5 : 4) + (right ? 0 : 2);
    int ammo = assembly ? equipment(assembly, slot) : -1;
    void *p = ammo >= 0 ? param(ammo) : (void *)0;
    int icon = p ? (int)AT(u16, p, 0xba) : -1;
    int count = ammo >= 0 ? quantity((u8 *)assembly - 0x80, slot) : -1;
    u8 active = assembly != 0;
    /* Each of the existing arrow instances has its own cached icon and count.
       Visibility is refreshed even when equal-valued items replace each other. */
    if (AT(int, widget, 0x214) != ammo || AT(int, widget, 0x22c) != icon) {
        void *c = child(widget, (const u16 *)(game + 0x13a1bf0)); /* icon */
        if (c) {
            struct { int value, pad, type, pad2; } v = {icon, 0, 2, 0};
            void **vt = AT(void **, c, 0);
            ((void (*)(void *, int, void *))vt[0xd8 / 8])(c, 0x1388, &v);
        }
        AT(int, widget, 0x214) = ammo;
        AT(int, widget, 0x22c) = icon;
    }
    show_child(widget, (const u16 *)(game + 0x13a1bd0), active && icon >= 0);
    show_child(widget, (const u16 *)(game + (right ? 0x13b01e8 : 0x13b0218)), active);
    u16 number[12];
    format_count(number, count);
    text_child(widget, (const u16 *)(game + (right ? 0x13b0248 : 0x13b0270)), number, active);
    AT(int, widget, 0x230) = count;
    /* No cached "wrong weapon"/empty warning from the former hand binding. */
    show_child(widget, (const u16 *)(game + 0x13b01a8), 0);
    show_child(widget, (const u16 *)(game + 0x13ae108), active && (count <= 0 || !p));
}
void ammo_hud_visibility(void *widget) {
    int k = AT(int, widget, 0x208);
    if ((k == 4 || k == 5) && ranged_active()) {
        /* Runs after the native shortcut update, whose unavailable-ammo mask
           still uses the old hand binding. Replace only that final mask. */
        int id = -1, hand = 1, kind = 0;
        void *a = hud_assembly(&id, &hand, &kind);
        if (a) {
            int slot = (kind == 11 ? 5 : 4) + (k == 4 ? 0 : 2);
            show_child(widget, (const u16 *)(game + 0x13ae108),
                       equipment(a, slot) < 0 || quantity((u8 *)a - 0x80, slot) <= 0);
        }
        NATIVE(VisibleFn, 0xed83c0)(widget, 1);
        return;
    }
    /* The two independent slots replace the old single precision-ammo widget.
       Keep all other shortcut and spell/weapon visibility native. */
    if (k == 6 && ranged_active()) {
        NATIVE(VisibleFn, 0xed83c0)(widget, 0);
        return;
    }
    NATIVE(VoidOne, 0x677990)(widget);
}
void ammo_hud_shortcut(void *widget) {
    int k = AT(int, widget, 0x208);
    int id = -1, hand = 1, kind = 0;
    if (hud_assembly(&id, &hand, &kind) &&
        (k == 6 || k == (hand ? 4 : 5))) return;
    NATIVE(VoidOne, 0x676e80)(widget);
}
int ammo_hud_mode(int id) {
    int value = NATIVE(VarFn, 0x71abd0)(id);
    /* Only the three patched presentation call sites use this function.
       Do not change global UI variables, input modes or camera/aim flags. */
    return value == 1 && (id == 0x78 || id == 0x79) && ranged_active() ? 0 : value;
}
void ammo_reticle(void *gauge) {
    void *root = AT(void *, gauge, 0x4f8);
    /* Undo only our prior mask, using newly looked-up children. Never
       dereference a retained widget pointer after a menu reload. */
    if (root && root == scratch.hud_root) {
        for (unsigned i = 0; i < 2; ++i) {
            void *c = child(root, (const u16 *)(i ? u"category_r2" : u"F20-01_arrow"));
            if (c && c == scratch.hud_children[i])
                NATIVE(VisibleFn, 0xedbdb0)(c, scratch.hud_visible[i]);
        }
    }
    scratch.hud_root = 0;
    NATIVE(VoidOne, 0x67bb20)(gauge);
    if (!ranged_active()) return;
    root = AT(void *, gauge, 0x4f8);
    if (!root) return;
    scratch.hud_root = root;
    /* Keep targetsite/reticle native; hide only the obsolete selected-ammo
       count and switch prompt. Restore before the next native update. */
    for (unsigned i = 0; i < 2; ++i) {
        void *c = child(root, (const u16 *)(i ? u"category_r2" : u"F20-01_arrow"));
        scratch.hud_children[i] = c;
        if (c) {
            scratch.hud_visible[i] = (AT(u8, c, 0x28) & 2) != 0;
            NATIVE(VisibleFn, 0xedbdb0)(c, 0);
        }
    }
}
