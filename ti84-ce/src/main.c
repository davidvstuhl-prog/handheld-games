/*
 * Balloon Blitz CE - a balloon-popping tower defense game for the
 * TI-84 Plus CE. A smaller version of Balloon Blitz for the handheld.
 *
 * Build with the CE C toolchain: run `make` in the ti84-ce folder.
 *
 * Keys:  arrows = move cursor     [2nd] = build / tower menu / OK
 *        [alpha] = back           [y=] / [window] = pick tower to build
 *        [enter] = next round     [graph] = fast forward
 *        [mode] or [clear] = pause menu
 */
#include <graphx.h>
#include <keypadc.h>
#include <fileioc.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* ------------------------------------------------------------------ layout */
#define SCR_W 320
#define TILE 20
#define COLS 16
#define ROWS 10
#define HUD_H 12
#define MAP_Y HUD_H                     /* play field: 320 x 200 */
#define PANEL_Y (MAP_Y + ROWS * TILE)   /* 212: bottom panel */
#define FPS 30
#define WIN_ROUND 30
#define START_MONEY 650

#define MAX_BALLOONS 200
#define MAX_PROJ 60
#define MAX_TOWERS 48
#define MAX_FX 32
#define MAX_PATH 1400
#define SPEED_SHIFT 4                   /* balloon distance is in 1/16 pixels */

/* ------------------------------------------------------------------ colors */
enum {
    C_TRANS, C_BLACK, C_WHITE, C_GRASS, C_GRASS2, C_PATH, C_PATH2, C_WATER, C_WATER2,
    C_ROCK, C_ROCK2, C_HUD, C_PANEL, C_YELLOW, C_RED, C_BLUE, C_GREEN, C_PINK, C_GRAY,
    C_DGRAY, C_BROWN, C_TAN, C_ORANGE, C_PURPLE, C_LBLUE, C_CAMO, C_CAMO2, C_LIME,
    C_DIM, C_NAVY, C_GOLD, C_DGREEN, C_HILITE, NUM_COLORS
};
static const uint8_t rgb[NUM_COLORS][3] = {
    {255, 0, 255}, {0, 0, 0}, {255, 255, 255}, {88, 166, 72}, {70, 140, 58},
    {214, 186, 130}, {160, 125, 80}, {80, 150, 230}, {60, 120, 200}, {135, 128, 120},
    {95, 90, 85}, {30, 34, 48}, {38, 42, 58}, {255, 220, 60}, {225, 45, 45},
    {45, 125, 235}, {60, 195, 60}, {250, 125, 185}, {150, 150, 160}, {70, 70, 80},
    {175, 105, 45}, {215, 150, 80}, {255, 140, 30}, {140, 70, 200}, {170, 225, 255},
    {70, 100, 40}, {110, 130, 60}, {170, 230, 60}, {160, 165, 180}, {45, 85, 175},
    {205, 165, 45}, {40, 90, 40}, {70, 90, 140},
};

/* ------------------------------------------------------------------ balloons */
enum { B_RED, B_BLUE, B_GREEN, B_YELLOW, B_PINK, B_BLACK, B_WHITE, B_ZEBRA, B_LEAD,
       B_RAINBOW, B_CERAMIC, B_BLIMP, NUM_BTYPES };

/* damage types; a balloon is immune when (its immunity & damage type) != 0 */
#define D_NORMAL 0
#define D_SHARP 1   /* blocked by lead */
#define D_BOOM 2    /* blocked by black and zebra */
#define D_COLD 4    /* blocked by white and zebra */

typedef struct {
    uint8_t color, r, speed;   /* speed: 1/16 pixels per tick */
    uint8_t hp, imm, nkids;
    uint8_t kids[4];
} btype_t;

static const btype_t BT[NUM_BTYPES] = {
    {C_RED,    5, 22,   1, 0,                0, {0}},
    {C_BLUE,   5, 30,   1, 0,                1, {B_RED}},
    {C_GREEN,  6, 39,   1, 0,                1, {B_BLUE}},
    {C_YELLOW, 6, 50,   1, 0,                1, {B_GREEN}},
    {C_PINK,   6, 56,   1, 0,                1, {B_YELLOW}},
    {C_BLACK,  4, 39,   1, D_BOOM,           2, {B_PINK, B_PINK}},
    {C_WHITE,  4, 44,   1, D_COLD,           2, {B_PINK, B_PINK}},
    {C_WHITE,  6, 39,   1, D_BOOM | D_COLD,  2, {B_BLACK, B_WHITE}},
    {C_GRAY,   6, 22,   1, D_SHARP,          2, {B_BLACK, B_BLACK}},
    {C_PURPLE, 7, 41,   1, 0,                2, {B_ZEBRA, B_ZEBRA}},
    {C_BROWN,  7, 44,  10, 0,                2, {B_RAINBOW, B_RAINBOW}},
    {C_NAVY,  11, 22, 200, 0,                4, {B_CERAMIC, B_CERAMIC, B_CERAMIC, B_CERAMIC}},
};
static uint16_t rbe[NUM_BTYPES];   /* lives lost if one gets through */

typedef struct {
    uint8_t type, camo, alive;
    uint8_t frozen, glue, slow, acid, acid_t;
    int hp;
    int dist;                 /* along the track, in 1/16 pixels */
    int x, y;
    uint8_t speed_now;
    uint16_t id;
} balloon_t;

/* ------------------------------------------------------------------ towers */
enum { T_DART, T_TACK, T_BOMB, T_FROST, T_SNIPER, T_NINJA, T_GLUE, T_WIZARD, NUM_TTYPES };
enum { S_RANGE, S_RATE, S_DMG, S_PIERCE, S_SPEED, S_COUNT, S_FLAGS, S_BLAST,
       S_FREEZE, S_SLOW, S_BM, S_CHAIN, NUM_STATS };
#define F_CAMO 1     /* can see camo balloons */
#define F_LEAD 2     /* attacks pop lead (normal damage) */
#define F_HOMING 4   /* shots chase balloons */
#define F_ACID 8     /* glue slowly pops balloons */
#define F_WHITE 16   /* frost can freeze white and zebra */
enum { OP_ADD, OP_PCT, OP_SET, OP_OR };
#define NONE 255

typedef struct {
    const char *name;
    uint16_t cost;
    const char *desc;
    uint8_t stat, op; int16_t val;
    uint8_t stat2, op2; int16_t val2;
} upg_t;

typedef struct {
    const char *name;
    uint16_t cost;
    uint8_t color, color2, dtype;
    const char *desc;
    int16_t base[NUM_STATS];
    upg_t upg[2][2];
} ttype_t;

/*               range rate dmg pierce speed count flags blast freeze slow bm chain */
static const ttype_t TT[NUM_TTYPES] = {
    {"Dart Tower", 200, C_BROWN, C_TAN, D_SHARP, "Throws darts",
     {60, 20, 1, 2, 8, 1, 0, 0, 0, 0, 1, 0},
     {{{"Sharp Darts", 140, "+1 pierce", S_PIERCE, OP_ADD, 1, NONE, 0, 0},
       {"Triple Shot", 330, "3 darts at once", S_COUNT, OP_SET, 3, S_PIERCE, OP_ADD, 1}},
      {{"Long Range", 90, "+15 range", S_RANGE, OP_ADD, 15, NONE, 0, 0},
       {"Eagle Eye", 260, "Sees camo, faster", S_FLAGS, OP_OR, F_CAMO, S_RATE, OP_PCT, 70}}}},
    {"Tack Shooter", 280, C_GRAY, C_DGRAY, D_SHARP, "Tacks in all directions",
     {42, 27, 1, 1, 6, 8, 0, 0, 0, 0, 1, 0},
     {{{"Quick Spin", 150, "Shoots 25% faster", S_RATE, OP_PCT, 75, NONE, 0, 0},
       {"Blade Ring", 600, "12 blades, pierce 3", S_COUNT, OP_SET, 12, S_PIERCE, OP_ADD, 2}},
      {{"Long Reach", 100, "+10 range", S_RANGE, OP_ADD, 10, NONE, 0, 0},
       {"Ring of Fire", 900, "Fire: +1 dmg, pops lead", S_FLAGS, OP_OR, F_LEAD, S_DMG, OP_ADD, 1}}}},
    {"Bomb Tower", 500, C_DGRAY, C_BLACK, D_BOOM, "Blasts groups, pops lead",
     {62, 40, 1, 18, 6, 1, 0, 22, 0, 0, 1, 0},
     {{{"Bigger Bombs", 250, "Bigger blasts", S_BLAST, OP_ADD, 8, NONE, 0, 0},
       {"Blimp Buster", 900, "+1 dmg, 3x vs blimps", S_DMG, OP_ADD, 1, S_BM, OP_SET, 3}},
      {{"Long Fuse", 200, "+12 range", S_RANGE, OP_ADD, 12, NONE, 0, 0},
       {"Radar Reload", 380, "Sees camo, faster", S_FLAGS, OP_OR, F_CAMO, S_RATE, OP_PCT, 75}}}},
    {"Frost Tower", 350, C_LBLUE, C_WHITE, D_COLD, "Freezes nearby balloons",
     {36, 66, 0, 0, 0, 0, 0, 0, 36, 0, 1, 0},
     {{{"Deep Freeze", 150, "Freezes longer", S_FREEZE, OP_ADD, 18, NONE, 0, 0},
       {"Shatter", 320, "Freezing pops a layer", S_DMG, OP_SET, 1, NONE, 0, 0}},
      {{"Wide Chill", 120, "+10 range", S_RANGE, OP_ADD, 10, NONE, 0, 0},
       {"Cold Snap", 500, "Freezes white, sees camo", S_FLAGS, OP_OR, F_WHITE | F_CAMO, NONE, 0, 0}}}},
    {"Sniper", 350, C_DGREEN, C_CAMO2, D_SHARP, "Hits anything, anywhere",
     {999, 48, 2, 1, 0, 1, 0, 0, 0, 0, 1, 0},
     {{{"Full Metal", 350, "4 damage, pops lead", S_DMG, OP_SET, 4, S_FLAGS, OP_OR, F_LEAD},
       {"Deadeye", 1800, "10 damage, 3x blimps", S_DMG, OP_SET, 10, S_BM, OP_SET, 3}},
      {{"Night Scope", 300, "Sees camo balloons", S_FLAGS, OP_OR, F_CAMO, NONE, 0, 0},
       {"Semi-Auto", 1500, "Shoots 2.5x faster", S_RATE, OP_PCT, 40, NONE, 0, 0}}}},
    {"Ninja", 400, C_NAVY, C_RED, D_SHARP, "Fast stars, sees camo",
     {58, 16, 1, 2, 9, 1, F_CAMO, 0, 0, 0, 1, 0},
     {{{"Keen Stars", 300, "+2 pierce", S_PIERCE, OP_ADD, 2, NONE, 0, 0},
       {"Homing Stars", 500, "Stars chase balloons", S_FLAGS, OP_OR, F_HOMING, NONE, 0, 0}},
      {{"Quick Hands", 350, "Throws 25% faster", S_RATE, OP_PCT, 75, NONE, 0, 0},
       {"Star Storm", 1400, "3 stars at once", S_COUNT, OP_SET, 3, NONE, 0, 0}}}},
    {"Glue Gunner", 275, C_LIME, C_DGREEN, D_NORMAL, "Glue slows balloons",
     {54, 30, 0, 1, 6, 1, 0, 0, 0, 50, 1, 0},
     {{{"Sticky Glue", 200, "Slows even more", S_SLOW, OP_SET, 68, NONE, 0, 0},
       {"Acid Glue", 450, "Glue pops layers", S_FLAGS, OP_OR, F_ACID, NONE, 0, 0}},
      {{"Glue Spray", 220, "Glue hits 2 more", S_PIERCE, OP_ADD, 2, NONE, 0, 0},
       {"Fast Squirt", 400, "Shoots 40% faster", S_RATE, OP_PCT, 60, NONE, 0, 0}}}},
    {"Wizard", 400, C_PURPLE, C_YELLOW, D_NORMAL, "Magic pops every type",
     {56, 33, 1, 3, 5, 1, 0, 0, 0, 0, 1, 0},
     {{{"Arcane Blast", 300, "+1 damage", S_DMG, OP_ADD, 1, NONE, 0, 0},
       {"Lightning", 1200, "Zaps 6 balloons", S_CHAIN, OP_SET, 6, S_RATE, OP_PCT, 80}},
      {{"Guided Magic", 250, "Bolts chase balloons", S_FLAGS, OP_OR, F_HOMING, NONE, 0, 0},
       {"Wizard Sight", 300, "Sees camo, +10 range", S_FLAGS, OP_OR, F_CAMO, S_RANGE, OP_ADD, 10}}}},
};

static const char *const TARGET_NAMES[4] = {"First", "Last", "Strong", "Close"};

typedef struct {
    uint8_t type, col, row, lv[2], target, cool, alive;
    int x, y;
    int16_t st[NUM_STATS];
    unsigned spent, pops;
    int8_t aimx, aimy;        /* where the barrel points */
} tower_t;

enum { P_DART, P_TACK, P_BOMB, P_STAR, P_GLUE, P_BOLT };
typedef struct {
    int x, y, vx, vy;         /* 8.8 fixed point */
    uint8_t kind, life, pierce, dmg, dtype, blast, bm, flags, alive, nhit;
    uint8_t tower;
    uint16_t hit[6];
} proj_t;

enum { FX_POP, FX_RING, FX_LINE, FX_TEXT };
typedef struct {
    uint8_t kind, t, color, r;
    int x, y, x2, y2;
    const char *text;
} fx_t;

/* ------------------------------------------------------------------ maps */
typedef struct { int8_t c, r; } pt_t;
typedef struct {
    const char *name, *level;
    uint8_t npts;
    pt_t pts[10];
    uint8_t nblock;
    pt_t block[12];        /* water / rock tiles */
    uint8_t block_kind;    /* 0 = water, 1 = rocks */
} map_t;

#define NUM_MAPS 4
static const map_t MAPS[NUM_MAPS] = {
    {"Meadow", "Easy", 7, {{-1, 1}, {13, 1}, {13, 4}, {2, 4}, {2, 7}, {13, 7}, {13, 10}}, 0, {{0, 0}}, 0},
    {"Lake Loop", "Easy", 7, {{-1, 8}, {14, 8}, {14, 1}, {1, 1}, {1, 6}, {10, 6}, {10, 10}},
     10, {{5, 3}, {6, 3}, {7, 3}, {8, 3}, {9, 3}, {6, 2}, {7, 2}, {8, 2}, {6, 4}, {8, 4}}, 0},
    {"Crossroads", "Medium", 7, {{-1, 5}, {12, 5}, {12, 1}, {4, 1}, {4, 8}, {14, 8}, {14, 10}}, 0, {{0, 0}}, 0},
    {"Rapids", "Hard", 6, {{8, -1}, {8, 3}, {14, 3}, {14, 7}, {2, 7}, {2, 10}},
     6, {{4, 2}, {11, 5}, {6, 9}, {1, 4}, {12, 9}, {5, 5}}, 1},
};

typedef struct { const char *name; uint8_t lives; uint8_t cost_pct; uint8_t speed_pct; } diff_t;
static const diff_t DIFFS[3] = {{"Easy", 200, 80, 90}, {"Normal", 150, 100, 100}, {"Hard", 100, 108, 105}};

/* ------------------------------------------------------------------ rounds */
/* type, count, ticks between, start delay (in 4-tick steps), camo */
typedef struct { uint8_t type, count, spacing, delay, camo; } group_t;
typedef struct { uint8_t n; group_t g[3]; } round_t;
static const round_t ROUNDS[WIN_ROUND] = {
    {1, {{B_RED, 20, 27, 0, 0}}},
    {1, {{B_RED, 30, 21, 0, 0}}},
    {2, {{B_RED, 15, 18, 0, 0}, {B_BLUE, 8, 30, 30, 0}}},
    {2, {{B_RED, 25, 15, 0, 0}, {B_BLUE, 15, 24, 22, 0}}},
    {2, {{B_BLUE, 25, 21, 0, 0}, {B_RED, 10, 15, 45, 0}}},
    {2, {{B_BLUE, 20, 18, 0, 0}, {B_GREEN, 6, 36, 37, 0}}},
    {2, {{B_BLUE, 25, 15, 0, 0}, {B_GREEN, 12, 27, 30, 0}}},
    {2, {{B_GREEN, 20, 21, 0, 0}, {B_BLUE, 20, 9, 60, 0}}},
    {1, {{B_GREEN, 30, 16, 0, 0}}},
    {1, {{B_BLUE, 80, 7, 0, 0}}},
    {2, {{B_GREEN, 20, 15, 0, 0}, {B_YELLOW, 10, 30, 30, 0}}},
    {2, {{B_YELLOW, 20, 21, 0, 0}, {B_GREEN, 15, 12, 37, 0}}},
    {3, {{B_GREEN, 30, 10, 0, 0}, {B_YELLOW, 15, 18, 30, 0}, {B_PINK, 6, 30, 75, 0}}},
    {2, {{B_PINK, 15, 24, 0, 0}, {B_YELLOW, 25, 12, 22, 0}}},
    {2, {{B_BLACK, 12, 24, 0, 0}, {B_WHITE, 12, 24, 37, 0}}},
    {3, {{B_YELLOW, 20, 15, 0, 0}, {B_PINK, 15, 18, 30, 0}, {B_GREEN, 8, 24, 60, 1}}},
    {2, {{B_LEAD, 8, 45, 0, 0}, {B_YELLOW, 25, 12, 15, 0}}},
    {2, {{B_PINK, 30, 12, 0, 0}, {B_BLACK, 10, 21, 45, 0}}},
    {2, {{B_ZEBRA, 10, 30, 0, 0}, {B_PINK, 20, 12, 22, 0}}},
    {3, {{B_ZEBRA, 8, 24, 0, 0}, {B_LEAD, 10, 30, 30, 0}, {B_PINK, 8, 24, 45, 1}}},
    {2, {{B_ZEBRA, 15, 21, 0, 0}, {B_RAINBOW, 5, 45, 45, 0}}},
    {2, {{B_RAINBOW, 10, 30, 0, 0}, {B_LEAD, 8, 24, 37, 0}}},
    {3, {{B_CERAMIC, 3, 75, 0, 0}, {B_ZEBRA, 15, 15, 22, 0}, {B_BLACK, 8, 18, 60, 1}}},
    {2, {{B_RAINBOW, 14, 24, 0, 0}, {B_CERAMIC, 3, 60, 45, 0}}},
    {2, {{B_CERAMIC, 4, 45, 0, 0}, {B_BLIMP, 1, 30, 75, 0}}},
    {2, {{B_ZEBRA, 12, 18, 0, 1}, {B_CERAMIC, 6, 36, 45, 0}}},
    {2, {{B_LEAD, 15, 15, 0, 0}, {B_CERAMIC, 8, 30, 30, 0}}},
    {2, {{B_CERAMIC, 12, 24, 0, 0}, {B_BLIMP, 1, 30, 75, 0}}},
    {3, {{B_CERAMIC, 6, 27, 0, 1}, {B_CERAMIC, 6, 27, 45, 0}, {B_BLIMP, 2, 120, 75, 0}}},
    {2, {{B_BLIMP, 3, 75, 0, 0}, {B_CERAMIC, 10, 18, 30, 0}}},
};

/* ------------------------------------------------------------------ game state */
static uint8_t tiles[ROWS][COLS];        /* 0 grass, 1 track, 2 water, 3 rock */
static uint8_t tower_at[ROWS][COLS];     /* tower index + 1, or 0 */
static int16_t path_x[MAX_PATH];
static uint8_t path_y[MAX_PATH];
static int path_len;                     /* in pixels */

static balloon_t balloons[MAX_BALLOONS];
static tower_t towers[MAX_TOWERS];
static proj_t projs[MAX_PROJ];
static fx_t fxs[MAX_FX];
static uint8_t num_towers;

static uint8_t map_idx, diff_idx = 1;   /* Normal */
static long money;
static int lives;
static uint8_t round_num;
static bool round_active, fast, auto_start, won;
static unsigned round_tick;
static uint16_t next_id;
static int hp_pct;                       /* freeplay balloons get tougher */
static uint8_t auto_wait;

/* the current round's spawn list, built when the round starts */
static uint8_t spawn_type[600], spawn_camo[600];
static uint16_t spawn_at[600];
static int spawn_n, spawn_i;

static uint8_t cur_c = 7, cur_r = 5;    /* cursor tile */
static uint8_t shop;                     /* selected tower type to build */
enum { M_NORMAL, M_MENU };
static uint8_t mode, menu_row, sel;
enum { O_NONE, O_PAUSE, O_OVER, O_WIN };
static uint8_t overlay, over_row;
static char toast_buf[32];
static uint8_t toast_t;

/* save data (appvar BBLITZSV) */
static struct { uint8_t best[NUM_MAPS][3]; uint8_t auto_start; } save;

/* sprites */
static gfx_sprite_t *bspr[NUM_BTYPES][2];   /* [type][camo] */
static gfx_sprite_t *blimp_h, *blimp_v;

/* ------------------------------------------------------------------ small helpers */
static const int16_t COS24[24] = {256, 247, 222, 181, 128, 66, 0, -66, -128, -181, -222, -247,
                                  -256, -247, -222, -181, -128, -66, 0, 66, 128, 181, 222, 247};
#define SIN24(i) COS24[((i) + 18) % 24]

static unsigned isqrt(unsigned long v) {
    unsigned long r = 0, bit = 1UL << 30;
    while (bit > v) bit >>= 2;
    while (bit) {
        if (v >= r + bit) { v -= r + bit; r = (r >> 1) + bit; }
        else r >>= 1;
        bit >>= 2;
    }
    return (unsigned)r;
}

static char *utoa_(char *out, unsigned long v) {
    char tmp[12];
    int n = 0;
    do { tmp[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    while (n) *out++ = tmp[--n];
    *out = 0;
    return out;
}

static void text(const char *s, int x, int y, uint8_t color) {
    gfx_SetTextFGColor(color);
    gfx_PrintStringXY(s, x, y);
}

static void text_center(const char *s, int y, uint8_t color) {
    text(s, (SCR_W - (int)gfx_GetStringWidth(s)) / 2, y, color);
}

static void toast(const char *s) {
    strncpy(toast_buf, s, sizeof toast_buf - 1);
    toast_t = 45;
}

static unsigned cost_of(unsigned base) {
    return (unsigned)(((unsigned long)base * DIFFS[diff_idx].cost_pct / 100 + 2) / 5 * 5);
}

static void add_fx(uint8_t kind, int x, int y, int x2, int y2, uint8_t color, uint8_t r, uint8_t t) {
    uint8_t i;
    for (i = 0; i < MAX_FX; i++) {
        if (!fxs[i].t) {
            fx_t *f = &fxs[i];
            f->kind = kind; f->x = x; f->y = y; f->x2 = x2; f->y2 = y2;
            f->color = color; f->r = r; f->t = t;
            return;
        }
    }
}

/* ------------------------------------------------------------------ saving */
static void load_save(void) {
    uint8_t h = ti_Open("BBLITZSV", "r");
    memset(&save, 0, sizeof save);
    if (h) {
        ti_Read(&save, sizeof save, 1, h);
        ti_Close(h);
    }
}

static void write_save(void) {
    uint8_t h = ti_Open("BBLITZSV", "w");
    if (h) {
        ti_Write(&save, sizeof save, 1, h);
        ti_SetArchiveStatus(true, h);   /* keep it safe in flash */
        ti_Close(h);
    }
}

/* ------------------------------------------------------------------ map + track */
static int tile_cx(int c) { return c * TILE + TILE / 2; }
static int tile_cy(int r) { return MAP_Y + r * TILE + TILE / 2; }

static void build_map(void) {
    const map_t *m = &MAPS[map_idx];
    uint8_t i;
    memset(tiles, 0, sizeof tiles);
    path_len = 0;
    for (i = 0; i + 1 < m->npts; i++) {
        int x = tile_cx(m->pts[i].c), y = tile_cy(m->pts[i].r);
        int x1 = tile_cx(m->pts[i + 1].c), y1 = tile_cy(m->pts[i + 1].r);
        int dx = (x1 > x) - (x1 < x), dy = (y1 > y) - (y1 < y);
        while ((x != x1 || y != y1) && path_len < MAX_PATH) {
            int c = x / TILE, r = (y - MAP_Y) / TILE;
            if (x >= 0 && c < COLS && y >= MAP_Y && r < ROWS) tiles[r][c] = 1;
            path_x[path_len] = (int16_t)x;
            path_y[path_len] = (uint8_t)(y < 0 ? 0 : y > 255 ? 255 : y);
            path_len++;
            x += dx;
            y += dy;
        }
    }
    for (i = 0; i < m->nblock; i++)
        tiles[m->block[i].r][m->block[i].c] = (uint8_t)(2 + m->block_kind);
}

/* ------------------------------------------------------------------ balloons */
static balloon_t *spawn_balloon(uint8_t type, int dist, uint8_t camo) {
    uint8_t i;
    for (i = 0; i < MAX_BALLOONS; i++) {
        balloon_t *b = &balloons[i];
        if (!b->alive) {
            memset(b, 0, sizeof *b);
            b->type = type;
            b->camo = camo;
            b->alive = 1;
            b->hp = BT[type].hp > 1 ? (int)((long)BT[type].hp * hp_pct / 100) : 1;
            b->dist = dist < 0 ? 0 : dist;
            b->x = path_x[b->dist >> SPEED_SHIFT];
            b->y = path_y[b->dist >> SPEED_SHIFT];
            b->id = ++next_id;
            return b;
        }
    }
    return NULL;   /* too many balloons on screen */
}

static void damage(balloon_t *b, int dmg, uint8_t dtype, proj_t *p, tower_t *t);

static void pop(balloon_t *b, int leftover, uint8_t dtype, proj_t *p, tower_t *t) {
    const btype_t *bt = &BT[b->type];
    balloon_t *first = NULL;
    uint8_t k;
    b->alive = 0;
    money++;
    if (t) t->pops++;
    add_fx(FX_POP, b->x, b->y, 0, 0, bt->color, bt->r, 4);
    for (k = 0; k < bt->nkids; k++) {
        balloon_t *c = spawn_balloon(bt->kids[k], b->dist - k * 96, b->camo);
        if (!c && k == 0) {   /* screen full: this balloon becomes its first kid */
            c = b;
            c->alive = 1;
            c->type = bt->kids[0];
            c->hp = 1;
            c->id = ++next_id;
        }
        if (!c) break;
        if (!first) first = c;
        if (p && p->nhit < 6) p->hit[p->nhit++] = c->id;   /* don't hit the kids with the same shot */
    }
    if (leftover > 0 && first) damage(first, leftover, dtype, p, t);
}

static void damage(balloon_t *b, int dmg, uint8_t dtype, proj_t *p, tower_t *t) {
    if (!b->alive || dmg <= 0) return;
    if (BT[b->type].imm & dtype) {
        add_fx(FX_RING, b->x, b->y, 0, 0, C_GRAY, 5, 3);   /* "clink" */
        return;
    }
    b->hp -= dmg;
    if (b->hp <= 0) pop(b, -b->hp, dtype, p, t);
}

static unsigned rbe_left(const balloon_t *b) {
    const btype_t *bt = &BT[b->type];
    unsigned n = (unsigned)b->hp;
    uint8_t k;
    for (k = 0; k < bt->nkids; k++) n += rbe[bt->kids[k]];
    return n;
}

/* ------------------------------------------------------------------ rounds */
static void start_round(void) {
    uint8_t gi, k;
    round_num++;
    spawn_n = 0;
    spawn_i = 0;
    if (round_num <= WIN_ROUND) {
        const round_t *rd = &ROUNDS[round_num - 1];
        for (gi = 0; gi < rd->n; gi++) {
            const group_t *g = &rd->g[gi];
            for (k = 0; k < g->count && spawn_n < 600; k++) {
                spawn_type[spawn_n] = g->type;
                spawn_camo[spawn_n] = g->camo;
                spawn_at[spawn_n] = (uint16_t)(g->delay * 4 + k * g->spacing);
                spawn_n++;
            }
        }
    } else {   /* freeplay */
        int f = round_num - WIN_ROUND;
        int nc = 15 + 3 * f, nb = 1 + f / 2, sp = 15 - f / 3;
        if (sp < 6) sp = 6;
        for (k = 0; k < nc && spawn_n < 600; k++) {
            spawn_type[spawn_n] = B_CERAMIC; spawn_camo[spawn_n] = (uint8_t)(f & 1);
            spawn_at[spawn_n++] = (uint16_t)(k * sp);
        }
        for (k = 0; k < nb && spawn_n < 600; k++) {
            spawn_type[spawn_n] = B_BLIMP; spawn_camo[spawn_n] = 0;
            spawn_at[spawn_n++] = (uint16_t)(150 + k * 60);
        }
    }
    /* sort spawns by time (small insertion sort) */
    {
        int i, j;
        for (i = 1; i < spawn_n; i++) {
            uint16_t at = spawn_at[i]; uint8_t ty = spawn_type[i], cm = spawn_camo[i];
            for (j = i - 1; j >= 0 && spawn_at[j] > at; j--) {
                spawn_at[j + 1] = spawn_at[j]; spawn_type[j + 1] = spawn_type[j]; spawn_camo[j + 1] = spawn_camo[j];
            }
            spawn_at[j + 1] = at; spawn_type[j + 1] = ty; spawn_camo[j + 1] = cm;
        }
    }
    hp_pct = round_num > WIN_ROUND ? 100 + 6 * (round_num - WIN_ROUND) : 100;
    round_tick = 0;
    round_active = true;
    auto_wait = 0;
}

static void end_round(void) {
    char *p;
    unsigned bonus = 140 + 4 * round_num;
    round_active = false;
    money += bonus;
    if (round_num > save.best[map_idx][diff_idx]) {
        save.best[map_idx][diff_idx] = round_num;
        write_save();
    }
    p = toast_buf;
    strcpy(p, "Round ");
    p = utoa_(p + 6, round_num);
    strcpy(p, " done! +$");
    utoa_(p + 9, bonus);
    toast_t = 45;
    if (round_num == WIN_ROUND && !won) {
        won = true;
        overlay = O_WIN;
        over_row = 0;
    }
    if (auto_start) auto_wait = 60;
}

/* ------------------------------------------------------------------ towers */
static void recalc(tower_t *t) {
    const ttype_t *tt = &TT[t->type];
    uint8_t p, i;
    memcpy(t->st, tt->base, sizeof t->st);
    for (p = 0; p < 2; p++) {
        for (i = 0; i < t->lv[p]; i++) {
            const upg_t *u = &tt->upg[p][i];
            uint8_t k;
            for (k = 0; k < 2; k++) {
                uint8_t s = k ? u->stat2 : u->stat, op = k ? u->op2 : u->op;
                int16_t v = k ? u->val2 : u->val;
                if (s == NONE) continue;
                if (op == OP_ADD) t->st[s] += v;
                else if (op == OP_PCT) t->st[s] = (int16_t)((long)t->st[s] * v / 100);
                else if (op == OP_SET) t->st[s] = v;
                else t->st[s] |= v;
            }
        }
    }
    if (t->st[S_RATE] < 2) t->st[S_RATE] = 2;
}

static bool can_see(const tower_t *t, const balloon_t *b) {
    return !b->camo || (t->st[S_FLAGS] & F_CAMO);
}

static long dist2(int x0, int y0, int x1, int y1) {
    long dx = x1 - x0, dy = y1 - y0;
    return dx * dx + dy * dy;
}

static balloon_t *find_target(const tower_t *t) {
    balloon_t *best = NULL;
    long bestv = 0;
    int range = t->st[S_RANGE];
    uint8_t i;
    for (i = 0; i < MAX_BALLOONS; i++) {
        balloon_t *b = &balloons[i];
        long v, d2, rr;
        if (!b->alive || !can_see(t, b)) continue;
        if (b->y < MAP_Y || b->x < 0 || b->x >= SCR_W || b->y >= PANEL_Y) continue;
        d2 = dist2(t->x, t->y, b->x, b->y);
        rr = range + BT[b->type].r;
        if (range < 900 && d2 > rr * rr) continue;
        switch (t->target) {
            case 0: v = b->dist; break;
            case 1: v = -(long)b->dist; break;
            case 2: v = (long)b->type * 100000L + b->dist; break;
            default: v = -d2; break;
        }
        if (t->type == T_GLUE && (b->glue || b->type == B_BLIMP)) v -= 10000000L;
        if (!best || v > bestv) { best = b; bestv = v; }
    }
    return best;
}

static void fire(tower_t *t, int tx, int ty, int dirx, int diry, uint8_t kind) {
    uint8_t i;
    for (i = 0; i < MAX_PROJ; i++) {
        proj_t *p = &projs[i];
        if (!p->alive) {
            memset(p, 0, sizeof *p);
            p->alive = 1;
            p->kind = kind;
            p->x = tx << 8;
            p->y = ty << 8;
            p->vx = dirx * t->st[S_SPEED];
            p->vy = diry * t->st[S_SPEED];
            p->life = (uint8_t)((t->st[S_RANGE] + 16) / (t->st[S_SPEED] ? t->st[S_SPEED] : 1) + 1);
            p->pierce = (uint8_t)t->st[S_PIERCE];
            p->dmg = (uint8_t)t->st[S_DMG];
            p->dtype = (t->st[S_FLAGS] & F_LEAD) ? D_NORMAL : TT[t->type].dtype;
            p->blast = (uint8_t)t->st[S_BLAST];
            p->bm = (uint8_t)t->st[S_BM];
            p->flags = (uint8_t)t->st[S_FLAGS];
            p->tower = (uint8_t)(t - towers);
            return;
        }
    }
}

/* unit direction (x256) from (x0,y0) toward (x1,y1) */
static void aim(int x0, int y0, int x1, int y1, int *dx, int *dy) {
    long ddx = x1 - x0, ddy = y1 - y0;
    unsigned d = isqrt((unsigned long)(ddx * ddx + ddy * ddy));
    if (!d) d = 1;
    *dx = (int)(ddx * 256 / (long)d);
    *dy = (int)(ddy * 256 / (long)d);
}

static void lightning(tower_t *t, balloon_t *b, uint8_t jumps) {
    uint16_t hit[8];
    uint8_t n = 0, i;
    int x0 = t->x, y0 = t->y;
    while (b && n < jumps && n < 8) {
        balloon_t *next = NULL;
        long best = 30L * 30L;
        hit[n++] = b->id;
        add_fx(FX_LINE, x0, y0, b->x, b->y, C_LBLUE, 0, 3);
        x0 = b->x; y0 = b->y;
        damage(b, t->st[S_DMG], D_NORMAL, NULL, t);
        for (i = 0; i < MAX_BALLOONS; i++) {
            balloon_t *c = &balloons[i];
            uint8_t k; bool seen = false;
            long d2;
            if (!c->alive) continue;
            for (k = 0; k < n; k++) if (hit[k] == c->id) seen = true;
            if (seen) continue;
            d2 = dist2(x0, y0, c->x, c->y);
            if (d2 < best) { best = d2; next = c; }
        }
        b = next;
    }
}

static bool frost_pulse(tower_t *t) {
    int range = t->st[S_RANGE];
    bool any = false;
    uint8_t i, pass;
    for (pass = 0; pass < 2; pass++) {   /* pass 0: anything to freeze? pass 1: freeze */
        for (i = 0; i < MAX_BALLOONS; i++) {
            balloon_t *b = &balloons[i];
            long rr = range + BT[b->type].r;
            if (!b->alive || !can_see(t, b)) continue;
            if (dist2(t->x, t->y, b->x, b->y) > rr * rr) continue;
            if ((BT[b->type].imm & D_COLD) && !(t->st[S_FLAGS] & F_WHITE)) continue;
            if (!pass) { any = true; break; }
            if (b->frozen < t->st[S_FREEZE]) b->frozen = (uint8_t)t->st[S_FREEZE];
            if (t->st[S_DMG]) damage(b, t->st[S_DMG], D_NORMAL, NULL, t);
        }
        if (!any) return false;
    }
    add_fx(FX_RING, t->x, t->y, 0, 0, C_LBLUE, (uint8_t)range, 6);
    return true;
}

static void update_tower(tower_t *t) {
    balloon_t *b;
    int dx, dy;
    if (t->cool) { t->cool--; return; }
    if (t->type == T_FROST) {
        t->cool = frost_pulse(t) ? (uint8_t)t->st[S_RATE] : 3;
        return;
    }
    b = find_target(t);
    if (!b) { t->cool = 2; return; }
    t->cool = (uint8_t)t->st[S_RATE];
    if (t->type == T_SNIPER) {
        aim(t->x, t->y, b->x, b->y, &dx, &dy);
        t->aimx = (int8_t)(dx / 32); t->aimy = (int8_t)(dy / 32);
        add_fx(FX_LINE, t->x, t->y, b->x, b->y, C_YELLOW, 0, 2);
        damage(b, t->st[S_DMG] * (b->type == B_BLIMP ? t->st[S_BM] : 1),
               (t->st[S_FLAGS] & F_LEAD) ? D_NORMAL : D_SHARP, NULL, t);
        return;
    }
    if (t->type == T_TACK) {
        uint8_t n = (uint8_t)t->st[S_COUNT], step = (uint8_t)(24 / n), i;
        for (i = 0; i < 24; i += step) fire(t, t->x, t->y, COS24[i], SIN24(i), P_TACK);
        return;
    }
    {
        /* aim where the balloon will be when the shot gets there */
        int spd = t->st[S_SPEED] ? t->st[S_SPEED] : 1;
        int d = (int)isqrt((unsigned long)dist2(t->x, t->y, b->x, b->y));
        int future = b->dist + (int)b->speed_now * (d / spd);
        int ax = b->x, ay = b->y;
        uint8_t kind = t->type == T_BOMB ? P_BOMB : t->type == T_NINJA ? P_STAR :
                       t->type == T_GLUE ? P_GLUE : t->type == T_WIZARD ? P_BOLT : P_DART;
        uint8_t n = (uint8_t)t->st[S_COUNT], i;
        if ((future >> SPEED_SHIFT) < path_len) {
            ax = path_x[future >> SPEED_SHIFT];
            ay = path_y[future >> SPEED_SHIFT];
        }
        aim(t->x, t->y, ax, ay, &dx, &dy);
        t->aimx = (int8_t)(dx / 32); t->aimy = (int8_t)(dy / 32);
        for (i = 0; i < n; i++) {
            int s = (int)i - (int)(n - 1) / 2;   /* spread extra shots sideways */
            int ex = dx - dy * s / 4, ey = dy + dx * s / 4;
            fire(t, t->x, t->y, ex, ey, kind);
        }
        if (t->type == T_WIZARD && t->st[S_CHAIN]) lightning(t, b, (uint8_t)t->st[S_CHAIN]);
    }
}

static void explode(proj_t *p) {
    int bx = p->x >> 8, by = p->y >> 8, r = p->blast;
    uint8_t i, n = 0;
    for (i = 0; i < MAX_BALLOONS && n < p->pierce; i++) {
        balloon_t *b = &balloons[i];
        long rr = r + BT[b->type].r;
        if (b->alive && dist2(bx, by, b->x, b->y) <= rr * rr) {
            damage(b, p->dmg * (b->type == B_BLIMP ? p->bm : 1), D_BOOM, NULL, &towers[p->tower]);
            n++;
        }
    }
    add_fx(FX_RING, bx, by, 0, 0, C_ORANGE, (uint8_t)r, 5);
}

static void apply_glue(balloon_t *b, tower_t *t) {
    if (b->type == B_BLIMP) return;
    b->glue = 240;
    b->slow = (uint8_t)t->st[S_SLOW];
    b->acid = (t->st[S_FLAGS] & F_ACID) ? 1 : 0;
    b->acid_t = 40;
}

/* ------------------------------------------------------------------ one game tick */
static void tick(void) {
    uint8_t i, j;
    if (round_active) {
        while (spawn_i < spawn_n && spawn_at[spawn_i] <= round_tick) {
            spawn_balloon(spawn_type[spawn_i], 0, spawn_camo[spawn_i]);
            spawn_i++;
        }
        round_tick++;
    }

    for (i = 0; i < MAX_BALLOONS; i++) {
        balloon_t *b = &balloons[i];
        int sp;
        if (!b->alive) continue;
        sp = BT[b->type].speed * DIFFS[diff_idx].speed_pct / 100;
        if (b->frozen) {
            b->frozen--;
            sp = b->type == B_BLIMP ? sp / 2 : 0;
        }
        if (b->glue) {
            b->glue--;
            sp = sp * (100 - b->slow) / 100;
            if (b->acid && --b->acid_t == 0) {
                b->acid_t = 40;
                damage(b, 1, D_NORMAL, NULL, NULL);
                if (!b->alive) continue;
            }
        }
        b->speed_now = (uint8_t)sp;
        b->dist += sp;
        if ((b->dist >> SPEED_SHIFT) >= path_len) {
            b->alive = 0;
            lives -= (int)rbe_left(b);
        } else {
            b->x = path_x[b->dist >> SPEED_SHIFT];
            b->y = path_y[b->dist >> SPEED_SHIFT];
        }
    }

    for (i = 0; i < num_towers; i++)
        if (towers[i].alive) update_tower(&towers[i]);

    for (i = 0; i < MAX_PROJ; i++) {
        proj_t *p = &projs[i];
        int px, py;
        if (!p->alive) continue;
        if (p->flags & F_HOMING) {   /* steer toward the nearest balloon */
            balloon_t *near = NULL;
            long best = 40L * 40L;
            for (j = 0; j < MAX_BALLOONS; j++) {
                balloon_t *b = &balloons[j];
                long d2;
                if (!b->alive) continue;
                d2 = dist2(p->x >> 8, p->y >> 8, b->x, b->y);
                if (d2 < best) { best = d2; near = b; }
            }
            if (near) {
                int dx, dy, spd = towers[p->tower].st[S_SPEED];
                aim(p->x >> 8, p->y >> 8, near->x, near->y, &dx, &dy);
                p->vx = dx * spd;
                p->vy = dy * spd;
            }
        }
        p->x += p->vx;
        p->y += p->vy;
        px = p->x >> 8;
        py = p->y >> 8;
        if (!p->life-- || px < -8 || px > SCR_W + 8 || py < MAP_Y - 8 || py > PANEL_Y + 8) {
            p->alive = 0;
            if (p->kind == P_BOMB) explode(p);
            continue;
        }
        for (j = 0; j < MAX_BALLOONS && p->alive; j++) {
            balloon_t *b = &balloons[j];
            int r = BT[b->type].r + 3, dx, dy;
            uint8_t k; bool seen = false;
            if (!b->alive) continue;
            dx = b->x - px; dy = b->y - py;
            if (dx > r || dx < -r || dy > r || dy < -r) continue;
            if ((long)dx * dx + (long)dy * dy > (long)r * r) continue;
            for (k = 0; k < p->nhit; k++) if (p->hit[k] == b->id) seen = true;
            if (seen) continue;
            if (p->kind == P_BOMB) { p->alive = 0; explode(p); break; }
            if (p->nhit < 6) p->hit[p->nhit++] = b->id;
            if (p->kind == P_GLUE) apply_glue(b, &towers[p->tower]);
            else damage(b, p->dmg * (b->type == B_BLIMP ? p->bm : 1), p->dtype, p, &towers[p->tower]);
            if (--p->pierce == 0) p->alive = 0;
        }
    }

    if (lives <= 0) {
        lives = 0;
        round_active = false;
        overlay = O_OVER;
        over_row = 0;
        return;
    }
    if (round_active && spawn_i >= spawn_n) {
        for (i = 0; i < MAX_BALLOONS; i++) if (balloons[i].alive) return;
        end_round();
    }
}

/* ------------------------------------------------------------------ keys */
enum { K_UP = 1, K_DOWN = 2, K_LEFT = 4, K_RIGHT = 8, K_2ND = 16, K_ALPHA = 32, K_ENTER = 64,
       K_MODE = 128, K_CLEAR = 256, K_YEQU = 512, K_WINDOW = 1024, K_GRAPH = 2048 };
static unsigned keys_prev, keys_press, keys_rep;
static uint8_t hold[4];

static void read_keys(void) {
    unsigned k = 0;
    uint8_t i;
    kb_Scan();
    if (kb_IsDown(kb_KeyUp)) k |= K_UP;
    if (kb_IsDown(kb_KeyDown)) k |= K_DOWN;
    if (kb_IsDown(kb_KeyLeft)) k |= K_LEFT;
    if (kb_IsDown(kb_KeyRight)) k |= K_RIGHT;
    if (kb_IsDown(kb_Key2nd)) k |= K_2ND;
    if (kb_IsDown(kb_KeyAlpha)) k |= K_ALPHA;
    if (kb_IsDown(kb_KeyEnter)) k |= K_ENTER;
    if (kb_IsDown(kb_KeyMode)) k |= K_MODE;
    if (kb_IsDown(kb_KeyClear)) k |= K_CLEAR;
    if (kb_IsDown(kb_KeyYequ)) k |= K_YEQU;
    if (kb_IsDown(kb_KeyWindow)) k |= K_WINDOW;
    if (kb_IsDown(kb_KeyGraph)) k |= K_GRAPH;
    keys_press = k & ~keys_prev;
    keys_rep = keys_press;
    for (i = 0; i < 4; i++) {   /* arrows repeat when held */
        unsigned bit = 1u << i;
        if (!(k & bit)) { hold[i] = 0; continue; }
        if (hold[i] < 255) hold[i]++;
        if (hold[i] > 8 && (hold[i] - 8) % 3 == 0) keys_rep |= bit;
    }
    keys_prev = k;
}

/* ------------------------------------------------------------------ drawing */
static void draw_map(void) {
    uint8_t r, c;
    for (r = 0; r < ROWS; r++) {
        for (c = 0; c < COLS; c++) {
            int x = c * TILE, y = MAP_Y + r * TILE;
            uint8_t t = tiles[r][c];
            if (t == 1) {
                gfx_SetColor(C_PATH);
                gfx_FillRectangle_NoClip(x, (uint8_t)y, TILE, TILE);
                gfx_SetColor(C_PATH2);   /* edges next to grass */
                if (!r || tiles[r - 1][c] != 1) gfx_HorizLine(x, y, TILE);
                if (r == ROWS - 1 || tiles[r + 1][c] != 1) gfx_HorizLine(x, y + TILE - 1, TILE);
                if (!c || tiles[r][c - 1] != 1) gfx_VertLine(x, y, TILE);
                if (c == COLS - 1 || tiles[r][c + 1] != 1) gfx_VertLine(x + TILE - 1, y, TILE);
            } else {
                gfx_SetColor(((r * 7 + c * 3) % 5) ? C_GRASS : C_GRASS2);
                gfx_FillRectangle_NoClip(x, (uint8_t)y, TILE, TILE);
                if (t == 2) {
                    gfx_SetColor(C_WATER);
                    gfx_FillRectangle_NoClip(x, (uint8_t)y, TILE, TILE);
                    gfx_SetColor(C_WATER2);
                    gfx_HorizLine(x + 4, y + 7, 6);
                    gfx_HorizLine(x + 10, y + 13, 6);
                } else if (t == 3) {
                    gfx_SetColor(C_ROCK2);
                    gfx_FillCircle(x + 10, y + 11, 8);
                    gfx_SetColor(C_ROCK);
                    gfx_FillCircle(x + 10, y + 9, 7);
                } else {
                    gfx_SetColor(C_GRASS2);   /* a tuft of grass */
                    gfx_VertLine(x + 4 + (r * 5 + c * 11) % 12, y + 6 + (r * 3 + c) % 8, 3);
                }
            }
        }
    }
    {   /* the track's end, if it's inside the field, is a hole */
        const map_t *m = &MAPS[map_idx];
        pt_t e = m->pts[m->npts - 1];
        if (e.c >= 0 && e.c < COLS && e.r >= 0 && e.r < ROWS) {
            gfx_SetColor(C_BLACK);
            gfx_FillCircle(tile_cx(e.c), tile_cy(e.r), 7);
        }
    }
}

static void draw_tower(const tower_t *t) {
    const ttype_t *tt = &TT[t->type];
    int x = t->x, y = t->y;
    uint8_t p, k;
    gfx_SetColor(C_BLACK);
    gfx_FillCircle(x, y, 8);
    gfx_SetColor(tt->color);
    gfx_FillCircle(x, y, 7);
    gfx_SetColor(tt->color2);
    switch (t->type) {
        case T_TACK:
            for (k = 0; k < 24; k += 3)
                gfx_SetPixel(x + COS24[k] * 5 / 256, y + SIN24(k) * 5 / 256);
            gfx_FillCircle(x, y, 2);
            break;
        case T_FROST:
            gfx_Line(x - 5, y, x + 5, y);
            gfx_Line(x - 3, y - 4, x + 3, y + 4);
            gfx_Line(x - 3, y + 4, x + 3, y - 4);
            break;
        case T_NINJA:
            gfx_FillRectangle(x - 6, y - 2, 13, 3);
            break;
        case T_WIZARD:
            gfx_FillTriangle(x - 5, y + 3, x + 5, y + 3, x + 1, y - 7);
            break;
        case T_GLUE:
            gfx_FillCircle(x - 1, y + 1, 3);
            break;
        default:
            gfx_FillCircle(x, y, 3);
            break;
    }
    if (t->type == T_DART || t->type == T_BOMB || t->type == T_SNIPER || t->type == T_GLUE) {
        int len = t->type == T_SNIPER ? 3 : 2;
        gfx_SetColor(t->type == T_DART ? C_BROWN : C_BLACK);
        gfx_Line(x, y, x + t->aimx * len, y + t->aimy * len);
        if (t->type == T_BOMB) gfx_Line(x + 1, y, x + 1 + t->aimx * len, y + t->aimy * len);
    }
    for (p = 0; p < 2; p++)       /* upgrade pips */
        for (k = 0; k < 2; k++) {
            gfx_SetColor(k < t->lv[p] ? (p ? C_BLUE : C_ORANGE) : C_DGRAY);
            gfx_FillRectangle(x - 7 + p * 9 + k * 3, y + 7, 2, 2);
        }
}

static void draw_balloons(void) {
    uint8_t i;
    for (i = 0; i < MAX_BALLOONS; i++) {
        const balloon_t *b = &balloons[i];
        if (!b->alive) continue;
        if (b->type == B_BLIMP) {
            int k = b->dist >> SPEED_SHIFT;
            int nk = k + 4 < path_len ? k + 4 : path_len - 1;
            bool vertical = path_x[nk] == path_x[k];
            gfx_sprite_t *s = vertical ? blimp_v : blimp_h;
            gfx_TransparentSprite(s, b->x - s->width / 2, b->y - s->height / 2);
            {   /* health bar */
                int w = (int)((long)b->hp * 20 / (BT[B_BLIMP].hp * hp_pct / 100));
                gfx_SetColor(C_BLACK);
                gfx_FillRectangle(b->x - 11, b->y - 15, 22, 4);
                gfx_SetColor(w > 10 ? C_GREEN : C_RED);
                gfx_FillRectangle(b->x - 10, b->y - 14, w < 0 ? 0 : w, 2);
            }
        } else {
            gfx_sprite_t *s = bspr[b->type][b->camo];
            gfx_TransparentSprite(s, b->x - s->width / 2, b->y - BT[b->type].r - 1);
        }
        if (b->frozen) {
            gfx_SetColor(C_LBLUE);
            gfx_Circle(b->x, b->y, BT[b->type].r + 2);
        }
        if (b->glue) {
            gfx_SetColor(C_LIME);
            gfx_FillCircle(b->x, b->y - 2, BT[b->type].r / 2 + 1);
        }
    }
}

static void draw_projs(void) {
    uint8_t i;
    for (i = 0; i < MAX_PROJ; i++) {
        const proj_t *p = &projs[i];
        int x = p->x >> 8, y = p->y >> 8;
        if (!p->alive) continue;
        switch (p->kind) {
            case P_DART:
                gfx_SetColor(C_BROWN);
                gfx_Line(x - (p->vx >> 9), y - (p->vy >> 9), x, y);
                break;
            case P_TACK:
                gfx_SetColor(p->dtype == D_NORMAL ? C_ORANGE : C_WHITE);
                gfx_FillRectangle(x - 1, y - 1, 3, 3);
                break;
            case P_BOMB:
                gfx_SetColor(C_BLACK);
                gfx_FillCircle(x, y, 3);
                break;
            case P_STAR:
                gfx_SetColor(C_WHITE);
                gfx_Line(x - 2, y - 2, x + 2, y + 2);
                gfx_Line(x - 2, y + 2, x + 2, y - 2);
                break;
            case P_GLUE:
                gfx_SetColor(C_LIME);
                gfx_FillCircle(x, y, 2);
                break;
            default:
                gfx_SetColor(C_PURPLE);
                gfx_FillCircle(x, y, 3);
                gfx_SetColor(C_WHITE);
                gfx_FillRectangle(x, y, 1, 1);   /* clipped, unlike gfx_SetPixel */
                break;
        }
    }
}

static void draw_fx(void) {
    uint8_t i;
    for (i = 0; i < MAX_FX; i++) {
        fx_t *f = &fxs[i];
        if (!f->t) continue;
        gfx_SetColor(f->color);
        if (f->kind == FX_POP) {
            int r = f->r + 5 - f->t;
            gfx_Line(f->x - r, f->y, f->x - r / 2, f->y);
            gfx_Line(f->x + r / 2, f->y, f->x + r, f->y);
            gfx_Line(f->x, f->y - r, f->x, f->y - r / 2);
            gfx_Line(f->x, f->y + r / 2, f->x, f->y + r);
        } else if (f->kind == FX_RING) {
            gfx_Circle(f->x, f->y, f->r);
        } else if (f->kind == FX_LINE) {
            gfx_Line(f->x, f->y, f->x2, f->y2);
        }
        f->t--;
    }
}

static void draw_hud(void) {
    char buf[24];
    gfx_SetColor(C_HUD);
    gfx_FillRectangle_NoClip(0, 0, SCR_W, HUD_H);
    gfx_SetColor(C_RED);
    gfx_FillCircle(5, 6, 3);
    utoa_(buf, (unsigned long)lives);
    text(buf, 12, 2, C_WHITE);
    gfx_SetColor(C_YELLOW);
    gfx_FillCircle(62, 6, 4);
    buf[0] = '$';
    utoa_(buf + 1, (unsigned long)money);
    text(buf, 70, 2, C_WHITE);
    if (auto_start) text("AUTO", 150, 2, C_GREEN);
    if (fast) text(">>", 190, 2, C_YELLOW);
    strcpy(buf, "Round ");
    utoa_(buf + 6, round_num ? round_num : 1);
    if (round_num <= WIN_ROUND) strcat(buf, "/30");
    text(buf, SCR_W - (int)gfx_GetStringWidth(buf) - 4, 2, C_WHITE);
}

static void draw_panel(void) {
    const ttype_t *tt = &TT[shop];
    char buf[40];
    unsigned c = cost_of(tt->cost);
    gfx_SetColor(C_PANEL);
    gfx_FillRectangle_NoClip(0, PANEL_Y, SCR_W, 240 - PANEL_Y);
    /* the tower you'd build, with a little icon */
    {
        tower_t icon;
        memset(&icon, 0, sizeof icon);
        icon.type = shop; icon.x = 10; icon.y = PANEL_Y + 9; icon.aimx = 4; icon.aimy = -4;
        draw_tower(&icon);
    }
    strcpy(buf, tt->name);
    strcat(buf, "  $");
    utoa_(buf + strlen(buf), c);
    text(buf, 22, PANEL_Y + 2, money >= (long)c ? C_GREEN : C_RED);
    text("<y=  window>", SCR_W - 100, PANEL_Y + 2, C_DIM);
    text(tt->desc, 22, PANEL_Y + 11, C_WHITE);
    if (mode == M_MENU) text("arrows:choose 2nd:OK alpha:close", 4, PANEL_Y + 20, C_DIM);
    else if (round_active) text("2nd:build/menu graph:speed mode:pause", 4, PANEL_Y + 20, C_DIM);
    else text("2nd:build/menu  ENTER:go  mode:pause", 4, PANEL_Y + 20, C_DIM);
}

static void draw_box(int x, int y, int w, int h) {
    gfx_SetColor(C_HUD);
    gfx_FillRectangle(x, y, w, h);
    gfx_SetColor(C_DIM);
    gfx_Rectangle(x, y, w, h);
}

static void draw_menu(void) {
    tower_t *t = &towers[sel];
    const ttype_t *tt = &TT[t->type];
    char buf[40];
    int y0 = t->row < ROWS / 2 ? PANEL_Y - 76 : MAP_Y + 4;
    uint8_t row;
    const char *desc = "";
    draw_box(4, y0, SCR_W - 8, 72);
    strcpy(buf, tt->name);
    strcat(buf, "  popped ");
    utoa_(buf + strlen(buf), t->pops);
    text(buf, 10, y0 + 4, C_YELLOW);
    for (row = 0; row < 4; row++) {
        int y = y0 + 24 + row * 11;
        uint8_t col = C_WHITE;
        if (row < 2) {
            if (t->lv[row] >= 2) {
                strcpy(buf, row ? "Path B: MAX" : "Path A: MAX");
                col = C_DIM;
                if (row == menu_row) desc = "Fully upgraded";
            } else {
                const upg_t *u = &tt->upg[row][t->lv[row]];
                unsigned c = cost_of(u->cost);
                strcpy(buf, u->name);
                strcat(buf, "  $");
                utoa_(buf + strlen(buf), c);
                col = money >= (long)c ? C_GREEN : C_RED;
                if (row == menu_row) desc = u->desc;
            }
        } else if (row == 2) {
            if (t->type == T_FROST) {
                strcpy(buf, "Freezes all in range");
            } else {
                strcpy(buf, "Target: < ");
                strcat(buf, TARGET_NAMES[t->target]);
                strcat(buf, " >");
            }
            if (row == menu_row) desc = "Which balloon to shoot";
        } else {
            strcpy(buf, "Sell  +$");
            utoa_(buf + 8, t->spent * 7 / 10);
            col = C_ORANGE;
            if (row == menu_row) desc = "Get 70% of your money back";
        }
        if (row == menu_row) {
            gfx_SetColor(C_HILITE);
            gfx_FillRectangle(8, y - 2, SCR_W - 16, 11);
        }
        text(buf, 14, y, col);
    }
    text(desc, 10, y0 + 13, C_DIM);
}

static const char *overlay_item(uint8_t i) {
    if (overlay == O_PAUSE) {
        static const char *const items[4] = {"Resume", "Auto-start: OFF", "Restart", "Quit to title"};
        if (i == 1) return auto_start ? "Auto-start: ON" : "Auto-start: OFF";
        return items[i];
    }
    if (overlay == O_WIN) return i ? "Quit to title" : "Keep playing";
    return i ? "Quit to title" : "Try again";
}

static uint8_t overlay_count(void) { return overlay == O_PAUSE ? 4 : 2; }

static void draw_overlay(void) {
    char buf[32];
    uint8_t i;
    draw_box(60, 50, 200, 130);
    gfx_SetTextScale(2, 2);
    text_center(overlay == O_PAUSE ? "Paused" : overlay == O_WIN ? "You Win!" : "Game Over", 60, C_YELLOW);
    gfx_SetTextScale(1, 1);
    strcpy(buf, "Round ");
    utoa_(buf + 6, round_num);
    text_center(buf, 82, C_WHITE);
    for (i = 0; i < overlay_count(); i++) {
        int y = 102 + i * 16;
        if (i == over_row) {
            gfx_SetColor(C_HILITE);
            gfx_FillRectangle(70, y - 3, 180, 13);
        }
        text_center(overlay_item(i), y, i == over_row ? C_YELLOW : C_WHITE);
    }
}

static void draw_game(void) {
    gfx_SetClipRegion(0, MAP_Y, SCR_W, PANEL_Y);
    draw_map();
    {
        uint8_t i;
        for (i = 0; i < num_towers; i++) if (towers[i].alive) draw_tower(&towers[i]);
    }
    draw_balloons();
    draw_projs();
    draw_fx();
    {   /* cursor + range circle */
        uint8_t ti = tower_at[cur_r][cur_c];
        int x = cur_c * TILE, y = MAP_Y + cur_r * TILE;
        if (mode == M_MENU) {
            tower_t *t = &towers[sel];
            gfx_SetColor(C_WHITE);
            if (t->st[S_RANGE] < 900) gfx_Circle(t->x, t->y, t->st[S_RANGE]);
        } else {
            int range = ti ? towers[ti - 1].st[S_RANGE] : TT[shop].base[S_RANGE];
            bool ok = ti || (!tiles[cur_r][cur_c] && money >= (long)cost_of(TT[shop].cost));
            gfx_SetColor(ok ? C_WHITE : C_RED);
            if (range < 900) gfx_Circle(x + TILE / 2, y + TILE / 2, range);
            gfx_SetColor(C_YELLOW);
            gfx_Rectangle(x, y, TILE, TILE);
            gfx_Rectangle(x + 1, y + 1, TILE - 2, TILE - 2);
        }
    }
    gfx_SetClipRegion(0, 0, SCR_W, 240);
    if (auto_wait && !round_active && !overlay) text_center("Next round soon...", MAP_Y + 24, C_YELLOW);
    if (toast_t) {
        int w = (int)gfx_GetStringWidth(toast_buf);
        draw_box((SCR_W - w) / 2 - 6, MAP_Y + 4, w + 12, 13);
        text_center(toast_buf, MAP_Y + 7, C_WHITE);
        toast_t--;
    }
    draw_hud();
    draw_panel();
    if (mode == M_MENU) draw_menu();
    if (overlay) draw_overlay();
}

/* ------------------------------------------------------------------ sprites */
static gfx_sprite_t *grab(int w, int h) {
    gfx_sprite_t *s = gfx_MallocSprite(w, h);
    gfx_GetSprite(s, 0, 0);
    return s;
}

static void make_sprites(void) {
    uint8_t t, camo;
    gfx_SetDrawBuffer();
    for (t = 0; t < B_BLIMP; t++) {
        for (camo = 0; camo < 2; camo++) {
            const btype_t *bt = &BT[t];
            int r = bt->r, w = 2 * r + 2, h = 2 * r + 4, c = r + 1;
            gfx_SetColor(C_TRANS);
            gfx_FillRectangle(0, 0, 40, 40);
            gfx_SetColor(C_DGRAY);
            gfx_FillTriangle(c - 2, 2 * r + 3, c + 2, 2 * r + 3, c, 2 * r);   /* knot */
            gfx_SetColor(t == B_WHITE || t == B_ZEBRA ? C_GRAY : C_BLACK);
            gfx_FillCircle(c, c, r);
            gfx_SetColor(bt->color);
            gfx_FillCircle(c, c, r - 1);
            if (t == B_RAINBOW) {
                gfx_SetColor(C_RED);    gfx_FillCircle(c, c, r - 1);
                gfx_SetColor(C_YELLOW); gfx_FillCircle(c, c, r - 3);
                gfx_SetColor(C_GREEN);  gfx_FillCircle(c, c, r - 4);
                gfx_SetColor(C_BLUE);   gfx_FillCircle(c, c, r - 5);
            } else if (t == B_ZEBRA) {
                gfx_SetColor(C_BLACK);
                gfx_HorizLine(c - r + 2, c - 2, 2 * r - 3);
                gfx_HorizLine(c - r + 2, c + 2, 2 * r - 3);
            } else if (t == B_CERAMIC) {
                gfx_SetColor(C_TAN);
                gfx_Circle(c, c, r - 3);
            }
            if (camo) {
                gfx_SetColor(C_CAMO);
                gfx_FillCircle(c - 2, c + 1, 2);
                gfx_SetColor(C_CAMO2);
                gfx_FillCircle(c + 2, c - 2, 2);
                gfx_SetColor(C_CAMO);
                gfx_Circle(c, c, r);
            }
            gfx_SetColor(C_WHITE);
            gfx_SetPixel(c - r / 2, c - r / 2);
            gfx_SetPixel(c - r / 2 + 1, c - r / 2);
            bspr[t][camo] = grab(w, h);
        }
    }
    /* the blimp, sideways and upright */
    gfx_SetColor(C_TRANS);
    gfx_FillRectangle(0, 0, 40, 40);
    gfx_SetColor(C_BLACK);
    gfx_FillEllipse(13, 7, 12, 6);
    gfx_SetColor(C_NAVY);
    gfx_FillEllipse(13, 7, 11, 5);
    gfx_SetColor(C_WHITE);
    gfx_VertLine(18, 3, 9);
    gfx_SetColor(C_BLACK);
    gfx_FillTriangle(0, 1, 5, 7, 0, 13);
    blimp_h = grab(26, 15);
    gfx_SetColor(C_TRANS);
    gfx_FillRectangle(0, 0, 40, 40);
    gfx_SetColor(C_BLACK);
    gfx_FillEllipse(7, 13, 6, 12);
    gfx_SetColor(C_NAVY);
    gfx_FillEllipse(7, 13, 5, 11);
    gfx_SetColor(C_WHITE);
    gfx_HorizLine(3, 18, 9);
    gfx_SetColor(C_BLACK);
    gfx_FillTriangle(1, 0, 7, 5, 13, 0);
    blimp_v = grab(15, 26);
}

/* ------------------------------------------------------------------ game flow */
static void new_game(void) {
    uint8_t i;
    memset(balloons, 0, sizeof balloons);
    memset(towers, 0, sizeof towers);
    memset(projs, 0, sizeof projs);
    memset(fxs, 0, sizeof fxs);
    memset(tower_at, 0, sizeof tower_at);
    num_towers = 0;
    build_map();
    money = START_MONEY;
    lives = DIFFS[diff_idx].lives;
    round_num = 0;
    round_active = fast = won = false;
    auto_start = save.auto_start;
    auto_wait = 0;
    hp_pct = 100;
    mode = M_NORMAL;
    overlay = O_NONE;
    toast_t = 0;
    cur_c = 7; cur_r = 5;
    for (i = 0; i < 4; i++) hold[i] = 0;
}

static void open_menu_at_cursor(void) {
    sel = (uint8_t)(tower_at[cur_r][cur_c] - 1);
    mode = M_MENU;
    menu_row = 0;
}

static void try_build(void) {
    unsigned c = cost_of(TT[shop].cost);
    uint8_t i;
    tower_t *t = NULL;
    if (tiles[cur_r][cur_c]) { toast("Can't build there"); return; }
    if (money < (long)c) { toast("Not enough money"); return; }
    for (i = 0; i < MAX_TOWERS; i++) if (!towers[i].alive) { t = &towers[i]; break; }
    if (!t) { toast("Too many towers"); return; }
    memset(t, 0, sizeof *t);
    t->alive = 1;
    t->type = shop;
    t->col = cur_c; t->row = cur_r;
    t->x = tile_cx(cur_c); t->y = tile_cy(cur_r);
    t->spent = c;
    t->target = shop == T_SNIPER ? 2 : 0;
    t->aimy = -8;
    recalc(t);
    money -= c;
    if (i + 1 > num_towers) num_towers = (uint8_t)(i + 1);
    tower_at[cur_r][cur_c] = (uint8_t)(i + 1);
}

static void update_menu(void) {
    tower_t *t = &towers[sel];
    if (keys_rep & K_UP) menu_row = (uint8_t)((menu_row + 3) % 4);
    if (keys_rep & K_DOWN) menu_row = (uint8_t)((menu_row + 1) % 4);
    if (keys_press & K_ALPHA) { mode = M_NORMAL; return; }
    if (menu_row == 2 && t->type != T_FROST) {
        if (keys_rep & K_LEFT) t->target = (uint8_t)((t->target + 3) % 4);
        if ((keys_rep & K_RIGHT) || (keys_press & K_2ND)) t->target = (uint8_t)((t->target + 1) % 4);
    }
    if (!(keys_press & K_2ND)) return;
    if (menu_row < 2) {
        uint8_t p = menu_row;
        if (t->lv[p] >= 2) { toast("Already maxed out"); return; }
        {
            unsigned c = cost_of(TT[t->type].upg[p][t->lv[p]].cost);
            if (money < (long)c) { toast("Not enough money"); return; }
            money -= c;
            t->spent += c;
            t->lv[p]++;
            recalc(t);
            add_fx(FX_RING, t->x, t->y, 0, 0, C_YELLOW, 12, 6);
        }
    } else if (menu_row == 3) {
        money += t->spent * 7 / 10;
        t->alive = 0;
        tower_at[t->row][t->col] = 0;
        mode = M_NORMAL;
    }
}

/* returns false when the player quits to the title */
static bool update_game(void) {
    if (overlay) {
        uint8_t n = overlay_count();
        if (keys_rep & K_UP) over_row = (uint8_t)((over_row + n - 1) % n);
        if (keys_rep & K_DOWN) over_row = (uint8_t)((over_row + 1) % n);
        if (overlay == O_PAUSE && (keys_press & (K_ALPHA | K_MODE))) { overlay = O_NONE; return true; }
        if (overlay == O_PAUSE && (keys_press & K_CLEAR)) return false;
        if (!(keys_press & K_2ND)) return true;
        if (overlay == O_PAUSE) {
            if (over_row == 0) overlay = O_NONE;
            else if (over_row == 1) {
                auto_start = !auto_start;
                save.auto_start = auto_start;
                if (auto_start && round_num && !round_active) auto_wait = 60;
            } else if (over_row == 2) new_game();
            else return false;
        } else if (over_row == 0) {
            if (overlay == O_WIN) overlay = O_NONE;
            else new_game();
        } else return false;
        return true;
    }

    if (keys_press & (K_MODE | K_CLEAR)) { overlay = O_PAUSE; over_row = 0; return true; }
    if (keys_press & K_GRAPH) fast = !fast;
    if ((keys_press & K_ENTER) && !round_active) start_round();
    if (keys_rep & K_YEQU) shop = (uint8_t)((shop + NUM_TTYPES - 1) % NUM_TTYPES);
    if (keys_rep & K_WINDOW) shop = (uint8_t)((shop + 1) % NUM_TTYPES);

    if (mode == M_MENU) {
        update_menu();
    } else {
        if ((keys_rep & K_UP) && cur_r > 0) cur_r--;
        if ((keys_rep & K_DOWN) && cur_r < ROWS - 1) cur_r++;
        if ((keys_rep & K_LEFT) && cur_c > 0) cur_c--;
        if ((keys_rep & K_RIGHT) && cur_c < COLS - 1) cur_c++;
        if (keys_press & K_2ND) {
            if (tower_at[cur_r][cur_c]) open_menu_at_cursor();
            else try_build();
        }
    }

    if (auto_wait && !round_active && !overlay) {
        if (--auto_wait == 0 && auto_start) start_round();
    }
    tick();
    if (fast && !overlay) tick();
    return true;
}

/* ------------------------------------------------------------------ title screen */
static uint8_t title_row = 3;

static void draw_title(void) {
    static const char *const labels[6] = {"Map: ", "Mode: ", "Auto-start: ", "Start game", "How to play", "Quit"};
    char buf[40];
    uint8_t i, r, c;
    gfx_FillScreen(C_BLUE);
    gfx_SetTextScale(3, 3);
    text_center("BALLOON", 8, C_YELLOW);
    text_center("BLITZ", 34, C_RED);
    gfx_SetTextScale(1, 1);
    /* little map preview */
    build_map();
    for (r = 0; r < ROWS; r++)
        for (c = 0; c < COLS; c++) {
            uint8_t t = tiles[r][c];
            gfx_SetColor(t == 1 ? C_PATH : t == 2 ? C_WATER : t == 3 ? C_ROCK : C_GRASS);
            gfx_FillRectangle_NoClip(112 + c * 6, (uint8_t)(64 + r * 6), 6, 6);
        }
    gfx_SetColor(C_WHITE);
    gfx_Rectangle(111, 63, 98, 62);
    strcpy(buf, MAPS[map_idx].level);
    strcat(buf, " map - best round ");
    utoa_(buf + strlen(buf), save.best[map_idx][diff_idx]);
    text_center(buf, 130, C_WHITE);
    for (i = 0; i < 6; i++) {
        int y = 146 + i * 14;
        strcpy(buf, labels[i]);
        if (i == 0) { strcat(buf, "< "); strcat(buf, MAPS[map_idx].name); strcat(buf, " >"); }
        if (i == 1) { strcat(buf, "< "); strcat(buf, DIFFS[diff_idx].name); strcat(buf, " >"); }
        if (i == 2) strcat(buf, save.auto_start ? "< ON >" : "< OFF >");
        if (i == title_row) {
            gfx_SetColor(C_HILITE);
            gfx_FillRectangle(70, y - 3, 180, 13);
        }
        text_center(buf, y, i == title_row ? C_YELLOW : C_WHITE);
    }
    text_center("arrows + [2nd]      [clear] = quit", 230, C_LBLUE);
}

static void draw_help(void) {
    static const char *const lines[] = {
        "Pop the balloons before they escape!",
        "",
        "arrows     move the cursor",
        "[2nd]      build / open tower menu",
        "[y=] [window]   pick tower to build",
        "[alpha]    back",
        "[enter]    send the next round",
        "[graph]    fast forward",
        "[mode]     pause, auto-start, quit",
        "",
        "Lead: use bombs, fire or magic.",
        "Black ignores bombs, white ignores ice.",
        "Camo: Ninja, Eagle Eye, Night Scope...",
        "",
        "Press [2nd] or [alpha] to go back",
    };
    uint8_t i;
    gfx_FillScreen(C_HUD);
    for (i = 0; i < sizeof lines / sizeof lines[0]; i++)
        text(lines[i], 12, 10 + i * 14, i == 14 ? C_YELLOW : C_WHITE);
}

/* ------------------------------------------------------------------ main */
int main(void) {
    enum { ST_TITLE, ST_HELP, ST_GAME } state = ST_TITLE;
    uint8_t i, k;
    bool running = true;

    for (i = 0; i < NUM_BTYPES; i++) {   /* lives cost of each type (kids come earlier in the list) */
        rbe[i] = BT[i].hp;
        for (k = 0; k < BT[i].nkids; k++) rbe[i] += rbe[BT[i].kids[k]];
    }

    gfx_Begin();
    for (i = 0; i < NUM_COLORS; i++)
        gfx_palette[i] = gfx_RGBTo1555(rgb[i][0], rgb[i][1], rgb[i][2]);
    gfx_SetTransparentColor(C_TRANS);
    gfx_SetTextTransparentColor(C_TRANS);
    gfx_SetTextBGColor(C_TRANS);
    make_sprites();
    load_save();
    srand((unsigned)clock());

    while (running) {
        clock_t start = clock();
        read_keys();
        if (state == ST_TITLE) {
            int step = ((keys_rep & K_RIGHT) ? 1 : 0) - ((keys_rep & K_LEFT) ? 1 : 0);
            if (keys_rep & K_UP) title_row = (uint8_t)((title_row + 5) % 6);
            if (keys_rep & K_DOWN) title_row = (uint8_t)((title_row + 1) % 6);
            if (title_row == 0 && step) map_idx = (uint8_t)((map_idx + NUM_MAPS + step) % NUM_MAPS);
            if (title_row == 1 && step) diff_idx = (uint8_t)((diff_idx + 3 + step) % 3);
            if (title_row == 2 && (step || (keys_press & K_2ND))) save.auto_start = !save.auto_start;
            else if (keys_press & (K_2ND | K_ENTER)) {
                if (title_row <= 3) { new_game(); state = ST_GAME; }
                else if (title_row == 4) state = ST_HELP;
                else running = false;
            }
            if (keys_press & K_CLEAR) running = false;
            if (state == ST_TITLE) draw_title();
        } else if (state == ST_HELP) {
            if (keys_press & (K_2ND | K_ALPHA | K_CLEAR)) state = ST_TITLE;
            draw_help();
        } else {
            if (!update_game()) state = ST_TITLE;
            else draw_game();
        }
        gfx_SwapDraw();
        while ((clock_t)(clock() - start) < CLOCKS_PER_SEC / FPS) {}
    }

    write_save();
    gfx_End();
    return 0;
}
