"""Changes to the lifted C for Ocarina of Time, applied by lift.py after it writes the code (and by hand: python -I nx2/oot_patches.py).

Each is a runtime switch where it can be, so the game's own path stays reachable.

- Dynamic resolution (Lichii's built-in "Max Resolution" patch, main+0x805BD0): the engine's config flag at +0x94 picks the path that
  follows the GPU-time controller; with hos_fixed_resolution set it takes the other path, the 3D at full scale. The controller made
  a new set of render targets at each size, ~11 images a frame at times, and held the GPU near its budget.
"""
import glob
import os
import sys

DECL = "extern volatile int hos_fixed_resolution;\nextern volatile int hos_dynres_runs;\nextern volatile uint32_t hos_fixed_scale_bits;\n"
OLD = "if (!((c->x[8] >> 0) & 1)) { goto L_8082640c; }"
NEW = "if (hos_fixed_resolution || !((c->x[8] >> 0) & 1)) { goto L_8082640c; }\n    hos_dynres_runs++;"
LABEL = "L_8082640c:;"
SCALE_OLD = "c->x[9] = 0x3f800000ULL;"
SCALE_NEW = "c->x[9] = hos_fixed_scale_bits;"   # (the fixed path's scale, 1.0 as shipped)



# Fixed-scale refresh from Hookshot v2.0.6, GPL-3.0.
DECL2 = "extern volatile int hos_fixed_resolution;\nextern volatile uint64_t hos_res_module;\nextern volatile uint32_t hos_fixed_scale_bits;\n"

APPLY_OLD = "L_831f3efc:;\n    c->x[9]=recomp_load32(c,c->x[20] + 3628);"

APPLY_NEW = "L_831f3efc:;\n    if (hos_fixed_resolution) {   /* (only while +0xe5c is not the chosen scale: a recompute every frame remade the targets) */\n        union { uint32_t u; float f; } now = {(uint32_t)recomp_load32(c,c->x[20] + 3676)}, want = {hos_fixed_scale_bits},\n            e50 = {(uint32_t)recomp_load32(c,c->x[20] + 3664)}, e58 = {(uint32_t)recomp_load32(c,c->x[20] + 3672)};\n        const float d = now.f - (e50.f != 0 ? want.f * e58.f / e50.f : want.f);\n        if (d > 1e-4f || d < -1e-4f) c->x[8] |= 8;\n    }\n    c->x[9]=recomp_load32(c,c->x[20] + 3628);"

FLAGS_OLD = "L_831f3f08:;\n    c->x[8]=recomp_load64(c,c->x[20] + 3616);\n"

FLAGS_NEW = FLAGS_OLD + "    hos_res_module = c->x[20];\n    if (hos_fixed_resolution) c->x[8] &= ~0x18ULL;\n"

def fixed_scale(t):
    """The fixed path's scale reaching the 3D (the Resolution row). (t, 1) when applied here"""
    if APPLY_OLD not in t or FLAGS_OLD not in t:
        return t, 0
    t = t.replace(APPLY_OLD, APPLY_NEW, 1).replace(FLAGS_OLD, FLAGS_NEW, 1)
    return t.replace('#include "a64.h"\n', '#include "a64.h"\n' + DECL2, 1), 1


# (AkynoLeyend r9, from Hookshot v2.1.0, GPL-3.0) The frame's real time in place of the nominal rate, for a Game frame rate cap
# above 60 (host/nn_vi.c hos_frame_seconds_bits; 0, as at a cap of 60: the game's own divide, nothing changes). The engine has
# two places where its integer nominal rate (+0x2c8 of the graphics module) becomes a time step, both a float divide
# "base / nominal":
# - f_80706be0: the frame's step, base 60.0 (30.0 in the half-rate mode), added to the game clock and handed on as the frame's
#   seconds;
# - f_83b6ea90: the global step (60.0 / nominal, a float in .data) the rest of the engine reads.
# The engine's own rate is never above 60, and its controller puts 60 back over a higher value written from outside before
# either divide runs: above 60 fps every frame still stepped 1/60 s and the game ran fps / 60 times too fast. With the host's
# measured frame time the step is base * seconds, whatever the rate. hos_step_probe: f_80706be0's x19, which tells the host the
# hook is in this build (without it the host keeps the cap at 60).
STEP_SITES = (("void f_80706be0(Ctx *__restrict A64_NOESC c) {\n", 8, "\n    hos_step_probe = c->x[19];"),
              ("void f_83b6ea90(Ctx *__restrict A64_NOESC c) {\n", 0, ""))
STEP_OLD = "    _v=a64_fpx_div32_div32(c,_a,_b);\n    a64_vset64(c->vreg[%d],_v);}"
STEP_HOOK = ("    _v=a64_fpx_div32_div32(c,_a,_b);\n"
             "    { const uint32_t _hs = hos_frame_seconds_bits; if (_hs) { float _base, _secs; uint32_t _w; memcpy(&_base,&_a,4); "
             "memcpy(&_secs,&_hs,4); _base *= _secs; memcpy(&_w,&_base,4); _v = _w; } }   /* (base * the frame's seconds: nx2/oot_patches.py) */\n"
             "    a64_vset64(c->vreg[%d],_v);}")
STEP_MARK = "hos_frame_seconds_bits; if (_hs)"   # (once per divide with the hook)
STEP_DECL = "extern volatile uint32_t hos_frame_seconds_bits;\nextern volatile uint64_t hos_step_probe;\n"


def patch_frame_seconds(s):
    """The host's frame time at the step divides of f_80706be0 and f_83b6ea90: (s, the sites patched here). A site whose
    function is not in the file, is patched already, or whose code differs (another game version) is left as it is."""
    done = 0
    for head_text, reg, extra in STEP_SITES:
        head = s.find(head_text)
        if head < 0:
            continue
        end = s.find("\nvoid f_", head + len(head_text))
        body = s[head:end if end >= 0 else len(s)]
        old, new = STEP_OLD % reg, STEP_HOOK % reg + extra
        if new in body or body.count(old) != 1 or body.count("a64_fpx_div32_div32") != 1:
            continue
        at = head + body.index(old)
        s = s[:at] + new + s[at + len(old):]
        done += 1
    if done and STEP_DECL not in s:
        s = s.replace('#include "a64.h"\n', '#include "a64.h"\n' + STEP_DECL, 1)
    return s, done


def unpatch_frame_seconds(s):
    """s without the hook, as the lift wrote it: for a lift where only one of the two divides was found (apply)"""
    for _, reg, extra in STEP_SITES:
        s = s.replace(STEP_HOOK % reg + extra, STEP_OLD % reg)
    return s if STEP_MARK in s else s.replace(STEP_DECL, "", 1)


# (AkynoLeyend r13, from Hookshot v2.1.0, commit 8ef84611, GPL-3.0) Three hooks of its nx2/oot_patches.py, as it wrote them:
# patch_text_speed, patch_mouse_camera and patch_camera_centering. The host's side: host/nn_vi.c (hos_text_scale),
# host/oot_text_size.c and host/mouse_native.c.
#
# Text speed (the F1 panel's "Velocidade do texto"): f_80b1e140 (main+0xafe140) steps a text pane's letter animation, the
# LetterAnimControl of the panes with "LetterAnimOn" user data (dialogue, Navi, signs). Its time argument (s0) moves the letters'
# clock (+0x60 += rate +0x4c * time, the rate from the message's speed tag) and the pauses' timer (+0x58 -= time); hos_text_scale
# multiplies it, 1.0 as shipped. The auto-advance timer (+0x5c, before) keeps the game's time. A huge scale shows a page at once
# (one frame per pause), as the game's own skip on A (+0x72 = 2, f_80794b00) without its flags. Text size: the same place hands
# the control to hos_oot_text_pane.
TEXT_DECL = "extern volatile float hos_text_scale;\nextern void hos_oot_text_pane(Ctx *c, uint64_t anim);\n"
TEXT_HEAD = "void f_80b1e140(Ctx *__restrict A64_NOESC c) {"
# (the letters' block: past the early returns, the auto-advance timer and the hidden / no-text checks; reached once a call)
TEXT_OLD = ("L_80b1e1b4:;\n"
            "    c->x[9]=recomp_load16(c,c->x[19] + 110);\n"
            "if ((uint32_t)c->x[9] == 0) { goto L_80b1e18c; }\n")
# (the same block in a build with interrupt polls: nx2/poll.py puts the poll before each backward goto, as a block)
TEXT_OLD_POLLED = TEXT_OLD.replace("{ goto L_80b1e18c; }", "{ { A64_POLL(c); goto L_80b1e18c; } }")
TEXT_ADD = ("    if (hos_text_scale != 1.0f) { float _t; uint32_t _u; memcpy(&_t,c->vreg[0],4); _t *= hos_text_scale; "
            "memcpy(&_u,&_t,4); a64_vset64(c->vreg[0],_u); }   /* (nx2/oot_patches.py: text speed) */\n"
            "    hos_oot_text_pane(c, c->x[19]);   /* (nx2/oot_patches.py: text size; x19 the LetterAnimControl) */\n")
TEXT_MARK = "hos_oot_text_pane(c, c->x[19]);"


def patch_text_speed(s):
    """The scale at the head of the letters' block of f_80b1e140 (Text speed), and the call to hos_oot_text_pane after it
    (Text size: host/oot_text_size.c); None when the file has no such function, s unchanged when the
    function is there but its code differs (another game version)."""
    head = s.find(TEXT_HEAD)
    if head < 0:
        return None
    end = s.find("\nvoid f_", head + len(TEXT_HEAD))
    body = s[head:end if end >= 0 else len(s)]
    for old in (TEXT_OLD_POLLED, TEXT_OLD):   # (with the interrupt poll before the block's backward goto, or without: --no-polls)
        if old + TEXT_ADD in body:   # (applied already: a second run)
            return s
        if body.count(old) == 1:
            break
    else:
        return s
    if body.count("goto L_80b1e1b4;") != 1:
        return s
    at = head + body.index(old)
    s = s[:at] + old + TEXT_ADD + s[at + len(old):]
    return s.replace('#include "a64.h"\n', '#include "a64.h"\n' + TEXT_DECL, 1)


# Native mouse look (host/mouse_native.c): the player camera's update, f_80644c80 (a virtual method, the camera in x0), hands
# its camera to the host before anything else, on the game's thread, once a frame; with the panel's Mouse camera on the mouse's
# motion turns the camera's yaw (+0x1a4) and pitch (+0x18c) there, before the camera reads its input.
CAM_HEAD = "void f_80644c80(Ctx *__restrict A64_NOESC c) {\n"
CAM_MARK = "hos_mouse_camera(c->x[0]);"


def patch_mouse_camera(source):
    start = source.find(CAM_HEAD)
    if start < 0:
        return None
    if CAM_MARK in source:   # (made before: a lift patched again)
        return source
    at = start + len(CAM_HEAD)
    source = source[:at] + "    hos_mouse_camera(c->x[0]);   /* (nx2/oot_patches.py: native mouse look) */\n" + source[at:]
    return source.replace('#include "a64.h"\n', '#include "a64.h"\nextern void hos_mouse_camera(uint64_t camera);\n', 1)


# The camera's state-3 yaw follow: after f_80642c80's authored heading override (the branch to 0x806492c4), the block at
# 0x8064720c derives a heading from Link's movement and eases yaw (+0x1a4) through f_80642410 at 0x806475e4. Skip only
# the movement path, restoring x25's parameter base as that path does, and join the other yaw paths at 0x80645ad8.
# State 4's stick, state 2's explicit recenter and authored heading overrides stay intact; pitch and collision follow.
CAM_FOLLOW_ANCHOR = "L_8064720c:;\nif (!c->z) { goto L_806492c4; }\n"
CAM_FOLLOW_JOIN = "L_80645ad8:;"
CAM_FOLLOW_HOOK = ("    if (hos_disable_camera_centering()) { c->x[25] = c->x[26]; goto L_80645ad8; }"
                   "   /* (nx2/oot_patches.py: disable camera centering) */\n")


def patch_camera_centering(source):
    start = source.find(CAM_HEAD)
    if start < 0:
        return None
    end = source.find("\n}", start)
    if end < 0:
        return None
    body = source[start:end]
    if body.count(CAM_FOLLOW_ANCHOR) != 1 or body.count(CAM_FOLLOW_JOIN) != 1:
        return None
    if CAM_FOLLOW_HOOK in body:
        return source
    body = body.replace(CAM_FOLLOW_ANCHOR, CAM_FOLLOW_ANCHOR + CAM_FOLLOW_HOOK, 1)
    return (source[:start] + body + source[end:]).replace(
        '#include "a64.h"\n', '#include "a64.h"\nextern int hos_disable_camera_centering(void);\n', 1)


# (AkynoLeyend r13, from Hookshot v2.1.0's nx2/oot_wide.py, commit 8ef84611, GPL-3.0) Ultrawide's HUD, movies and save picture.
# That file's sites and what each does come from NX2navi's recomp/patches-v111.txt, where they are credited to Ivan0xFF (MIT,
# "The matrix-update, UI and movie sites: Copyright (c) 2026 Ivan0xFF"); the save picture's site is Hookshot's own (its issue
# 952). Hookshot adds C after eleven instructions while it lifts (Lifter.after). Three are taken here, each as Hookshot wrote
# it: the ones that read only the picture's ratio, the HUD's squeeze or its margin (host/hos_main.c), which hold whatever the
# picture's size. This base keeps its own picture (the Output resolution row, nx2/oot_output_size.py: 16:9, stretched to an
# ultrawide window) and its camera ratio (the one constant host/hos_main.c writes), so the three size sites and the five ratio
# sites are not taken. With these three the HUD and, by the panel's Ultrawide menus row, the menus keep their 16:9 shape in
# the middle of that stretched picture instead of stretching with it; movies play in the middle 16:9; a save's picture shows
# the middle 16:9. Every one reads host globals that stay 0 for a 16:9 window: the game runs as shipped then.
WIDE_MAIN = 0x80020000   # (main's base in this image: nx2/eden_image.py)
WIDE_UI_M00, WIDE_UI_M11 = "(2.0f / 3840.0f)", "(2.0f / 2160.0f)"   # (the UI's full-screen orthographic projection, 3840x2160 grid)
# (the screens whose UI keeps the whole picture: the item-wheel and pause / system menu backgrounds redraw a capture of
# the whole picture; the event and loading fades cover it. Bit k of host/hos_main.c's hos_wide_keep_mask keeps screen k
# whole; the Insert menu's Ultrawide menus row clears the menus' bits 1 and 3 (vk_framegen.cpp): their layout then
# keeps its 16:9 shape in the middle, as the HUD's does, instead of being stretched over the whole picture. Bit 0, the
# item wheel's background (the last frame of play, blurred, HUD and all), and bit 2, the fades, keep covering it all: bit 0
# cleared, that capture went into the middle at twice its width)
WIDE_KEEP_VTABLES = (WIDE_MAIN + 0x4bed098, WIDE_MAIN + 0x4be4fb0, WIDE_MAIN + 0x4be61c8, WIDE_MAIN + 0x4be7b30)

WIDE_HUD = ("{ extern volatile float hos_wide_squeeze; const float _q = hos_wide_squeeze; if (_q > 0.0f) { float _m00, _m11; "
       "memcpy(&_m00, c->vreg[1], 4); memcpy(&_m11, (const uint8_t *)c->vreg[4] + 4, 4); "
       "if (_m00 == %s && _m11 == %s) { const uint64_t _vt = recomp_load64(c, c->x[0] - 0x1b8); "
       "extern volatile uint32_t hos_wide_keep_mask; const uint32_t _kb = %s; "
       "if (!(_kb & hos_wide_keep_mask)) { float _row[4]; memcpy(_row, c->vreg[1], 16); for (int _k = 0; _k < 4; _k++) _row[_k] *= _q; "
       "memcpy(c->vreg[1], _row, 16); } } } }   /* (nx2/oot_wide.py: HUD in the middle 16:9) */"
       % (WIDE_UI_M00, WIDE_UI_M11, " : ".join("_vt == 0x%xULL ? %du" % (v, 1 << k) for k, v in enumerate(WIDE_KEEP_VTABLES)) + " : 0u"))

WIDE_MOVIE = ("{ extern volatile float hos_wide_margin; const float _m = hos_wide_margin; if (_m > 0.0f) { "
         "const uint64_t _vp = c->x[29] - 40; uint32_t _ua = (uint32_t)recomp_load32(c, _vp + 8), _ub = (uint32_t)recomp_load32(c, _vp + 16); "
         "float _a, _b; memcpy(&_a, &_ua, 4); memcpy(&_b, &_ub, 4); const float _in = (_b - _a) * _m; _a += _in; _b -= _in; "
         "memcpy(&_ua, &_a, 4); memcpy(&_ub, &_b, 4); recomp_store32(c, _vp + 8, _ua); recomp_store32(c, _vp + 16, _ub); } }"
         "   /* (nx2/oot_wide.py: movies in the middle 16:9) */")

# The save's picture (issue 952): the pause menu draws the whole picture into a 543 x 306 texture, the save's JPEG, through the
# game's viewport-and-scissor helper (f_802a46e0: SetScissor, then SetViewport(x, y, w, h) in w1-w4 from [x8], called by blr x8).
# Wider than 16:9, the whole picture was squeezed into it. That one viewport is made wider than the texture by the picture's
# ratio over 16:9, centred: the middle 16:9 fills the texture (the scissor keeps the texture's), as a 16:9 window would show.
# Narrower than 16:9 (4:3, 16:10) it is made taller instead, by 16:9 over the picture's ratio: the picture's middle band fills
# the texture at its own shape, neither squeezed nor with bars.
WIDE_THUMB = ("{ extern volatile float hos_wide_ratio; const float _r = hos_wide_ratio; if (_r > 0.0f && (uint32_t)c->x[1] == 0 "
         "&& (uint32_t)c->x[2] == 0 && (uint32_t)c->x[3] == 543 && (uint32_t)c->x[4] == 306) { "
         "if (_r > 16.0f / 9.0f) { const int _w = (int)(543.0f * _r / (16.0f / 9.0f) + 0.5f); "
         "c->x[1] = (uint32_t)((543 - _w) / 2); c->x[3] = (uint32_t)_w; } "
         "else { const int _h = (int)(306.0f * (16.0f / 9.0f) / _r + 0.5f); "
         "c->x[2] = (uint32_t)((306 - _h) / 2); c->x[4] = (uint32_t)_h; } } }"
         "   /* (nx2/oot_wide.py: the save's picture, the middle 16:9) */")


# Where each goes: after the lifted text of the instruction Hookshot's SITES names (main+0x774368 ldp q1, q4, [x2];
# main+0x3b5c758 ldp x9, x8, [x19, #0x18]; main+0x284824 ldr x8, [x8] before its blr x8), found by text inside its function.
# This base's lift makes that text; another game version, or a lift that words it otherwise, leaves the hook out, said so.
WIDE_HUD_HEAD = "void f_80794330(Ctx *__restrict A64_NOESC c) {\n"
WIDE_HUD_AT = ("    { uint64_t _b=c->x[2]; int64_t _o=0; recomp_ldp64(c,(_b+_o),&c->vreg[1][0],&c->vreg[1][1]); "
               "recomp_ldp64(c,(_b+_o)+16,&c->vreg[4][0],&c->vreg[4][1]); }\n")
WIDE_HUD_MARK = "/* (nx2/oot_wide.py: HUD in the middle 16:9) */"
WIDE_MOVIE_HEAD = "void f_83b7c710(Ctx *__restrict A64_NOESC c) {\n"
WIDE_MOVIE_AT = ("c->x[30] = 0x83b7c758ULL; f_809ec020(c);\n"
                 "    { uint64_t _b=c->x[19]; int64_t _o=24; { uint64_t _p0,_p1; recomp_ldp64(c,(_b+_o),&_p0,&_p1); "
                 "c->x[9]=_p0; c->x[8]=_p1; } }\n")
WIDE_MOVIE_MARK = "/* (nx2/oot_wide.py: movies in the middle 16:9) */"
WIDE_THUMB_HEAD = "void f_802a46e0(Ctx *__restrict A64_NOESC c) {\n"
WIDE_THUMB_AT = "    c->x[8]=recomp_load64(c,c->x[8] + 0);\n"
WIDE_THUMB_NEXT = "{ uint64_t _t = c->x[8]; c->x[30] = 0x802a482cULL; A64_ICALL(c, _t); }"
WIDE_THUMB_MARK = "/* (nx2/oot_wide.py: the save's picture, the middle 16:9) */"


def _wide_site(source, head, at, text, mark, then=""):
    """text on a line of its own after at (followed by then, when given) inside the function at head; None when the function
    is not in this file or at is not there exactly once"""
    start = source.find(head)
    if start < 0:
        return None
    end = source.find("\n}", start)
    if end < 0:
        return None
    body = source[start:end]
    if mark in body:   # (made before: a lift patched again)
        return source
    if body.count(at + then) != 1:
        return None
    assert text.endswith(mark), mark
    return source[:start] + body.replace(at + then, at + "    " + text + "\n" + then, 1) + source[end:]


def patch_wide_hud(source):
    return _wide_site(source, WIDE_HUD_HEAD, WIDE_HUD_AT, WIDE_HUD, WIDE_HUD_MARK)


def patch_wide_movie(source):
    return _wide_site(source, WIDE_MOVIE_HEAD, WIDE_MOVIE_AT, WIDE_MOVIE, WIDE_MOVIE_MARK)


def patch_wide_thumb(source):
    return _wide_site(source, WIDE_THUMB_HEAD, WIDE_THUMB_AT, WIDE_THUMB, WIDE_THUMB_MARK, WIDE_THUMB_NEXT)


# (AkynoLeyend 0.4.5-test.1, unified) Render distance (the F1 panel's "Distancia de renderizacao"): the far plane the engine's
# perspective projections make their matrix with. sead::PerspectiveProjection::doUpdateMatrix reads the near and far planes
# together from +0x98 and +0x9c (ldp s4, s3), then makes the depth row (-1 under it). Two copies of it in this game:
# - f_834a5cc0 (main+0x3485cc0), the virtual one, on x0; not reached in Kokiri;
# - f_8035a8c0 (main+0x33a8c0), the camera's update with the same code inlined on x2: the main camera's matrix (near 0.1, far
#   about 25000 in Kokiri; found with HOS_WATCH on that matrix, its only writer). Once a frame.
# The host (host/nn_vi.c hos_render_far_clamp) answers the far plane the matrix is made with: the game's own (no limit set, or
# a far plane within it), or the limit, for the matrix and the projection's far field. A site whose code differs is left alone.
FAR_SITES = (("void f_834a5cc0(Ctx *__restrict A64_NOESC c) {", 0),
             ("void f_8035a8c0(Ctx *__restrict A64_NOESC c) {", 2))
FAR_HEAD = FAR_SITES[0][0]   # (nx2/upgrade_output.py: the files to look in)
FAR_HEADS = tuple(head for head, _ in FAR_SITES)
FAR_LOAD = ("    { uint64_t _b=c->x[%d]; int64_t _o=152; { uint64_t _p0,_p1; recomp_ldp32(c,(_b+_o),&_p0,&_p1); "
            "a64_vset64(c->vreg[4],_p0); a64_vset64(c->vreg[3],_p1); }}\n")
FAR_OLD = FAR_LOAD % 0
# The far plane is also written back into the projection (+0x9c): the game's culling reads it there, not from the matrix
# (a limit only on the matrix cut the picture and left the draws as they were). The host keeps the game's own value per
# projection and gives it back when the limit is lifted.
FAR_ADD = ("    { float _n, _f, _g; uint32_t _u; memcpy(&_n,c->vreg[4],4); memcpy(&_f,c->vreg[3],4); "
           "_g = hos_render_far_site(c->x[%d] + 156ULL, _n, _f); if (_g != _f) { memcpy(&_u,&_g,4); "
           "recomp_store32(c,(c->x[%d] + 156ULL),_u); a64_vset64(c->vreg[3],_u); } }"
           "   /* (nx2/oot_patches.py: render distance; s4 the near plane, s3 the far, kept at +0x9c) */\n")
FAR_MARK = "hos_render_far_site(c->x["
FAR_DECL = "extern float hos_render_far_site(uint64_t at, float near_plane, float far_plane);\n"
# (the hook of the v4 works: the matrix only; replaced where found)
FAR_ADD_V4 = ("    { float _n, _f; uint32_t _u; memcpy(&_n,c->vreg[4],4); memcpy(&_f,c->vreg[3],4); "
              "_f = hos_render_far_clamp(_n, _f); memcpy(&_u,&_f,4); a64_vset64(c->vreg[3],_u); }"
              "   /* (nx2/oot_patches.py: render distance; s4 the near plane, s3 the far) */\n")
FAR_DECL_V4 = "extern float hos_render_far_clamp(float near_plane, float far_plane);\n"


def patch_render_distance(s):
    """The host's far plane after each FAR_SITES function loads the near and far planes; None when the file has none of
    them, s unchanged where one is there but its code differs (another game version) or the hook is in already."""
    found = False
    for head_text, reg in FAR_SITES:
        head = s.find(head_text)
        if head < 0:
            continue
        found = True
        end = s.find("\nvoid f_", head + len(head_text))
        body = s[head:end if end >= 0 else len(s)]
        old = FAR_LOAD % reg
        if body.count(old + FAR_ADD_V4) == 1:
            s = s[:head] + body.replace(old + FAR_ADD_V4, old + FAR_ADD % (reg, reg)) + s[head + len(body):]
            continue
        # (the one load of both planes on that register, then the depth row's -1 within the same stretch)
        if FAR_MARK in body or body.count(old) != 1:
            continue
        after = body.index(old) + len(old)
        if "0xbf800000ULL" not in body[after:after + 6000]:
            continue
        at = head + after
        s = s[:at] + FAR_ADD % (reg, reg) + s[at:]
    if not found:
        return None
    if FAR_DECL_V4 in s and FAR_ADD_V4 not in s:
        s = s.replace(FAR_DECL_V4, "")
    return s if FAR_MARK not in s or FAR_DECL in s else s.replace('#include "a64.h"\n', '#include "a64.h"\n' + FAR_DECL, 1)


# (name, the patch, the text that says its hook is in a file). Each stands alone: a hook whose place is not found (another game
# version) leaves its panel row without effect and the others as they are.
PANEL_HOOKS = (("text speed and size", patch_text_speed, TEXT_MARK),
               ("mouse camera", patch_mouse_camera, CAM_MARK),
               ("camera centering", patch_camera_centering, CAM_FOLLOW_HOOK),
               ("ultrawide HUD", patch_wide_hud, WIDE_HUD_MARK),
               ("ultrawide movies", patch_wide_movie, WIDE_MOVIE_MARK),
               ("ultrawide save picture", patch_wide_thumb, WIDE_THUMB_MARK),
               ("render distance", patch_render_distance, FAR_MARK))


def patch_panel_hooks(s):
    """The r13 hooks made in s: (s, the names of the hooks s holds now). The lift (apply) and an update of a work lifted
    before them (nx2/upgrade_output.py) both go through here."""
    held = []
    for name, patch, mark in PANEL_HOOKS:
        patched = patch(s)
        if patched is not None:
            s = patched
        if mark in s:
            held.append(name)
    return s, held


def apply(gen):
    done, refreshed = 0, 0
    step_sites, step_files = 0, []
    panel_hooks = set()
    for path in sorted(glob.glob(os.path.join(glob.escape(os.fspath(gen)), "code_*.c"))):
        with open(path, encoding="utf-8", newline="") as f:
            s = f.read()
        original = s
        if OLD in s:
            s = s.replace(OLD, NEW, 1)
            at = s.index(LABEL)
            scale = s.index(SCALE_OLD, at)
            s = s[:scale] + SCALE_NEW + s[scale + len(SCALE_OLD):]
            s = s.replace('#include "a64.h"\n', '#include "a64.h"\n' + DECL, 1)
        if NEW in s:
            done += 1
        s, changed = fixed_scale(s)
        refreshed += bool(changed or (APPLY_NEW in s and FLAGS_NEW in s))
        s, _ = patch_frame_seconds(s)
        if STEP_MARK in s:   # (made now, or by an earlier run over this file)
            step_sites += s.count(STEP_MARK)
            step_files.append(path)
        s, held = patch_panel_hooks(s)
        panel_hooks.update(held)
        if s != original:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(s)
    if step_sites != len(STEP_SITES):
        # (both or neither: with one divide timed and the other stepping 1/60 s the game's two clocks would run apart.
        # Without the hook the host keeps the cap at 60: host/nn_vi.c, hos_step_probe)
        for path in step_files:
            with open(path, encoding="utf-8", newline="") as f:
                t = f.read()
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(unpatch_frame_seconds(t))
        print("oot_patches: WARNING: the frame's time was found at %d of %d step divides, none patched (the Game frame "
              "rate cap stays at 60)" % (step_sites, len(STEP_SITES)))
    else:
        print("oot_patches: the frame's time at both step divides (Game frame rate cap)")
    for name, _, _ in PANEL_HOOKS:
        print("oot_patches: %s%s" % ("" if name in panel_hooks else "WARNING: no place found for the hook of ", name))
    if done != 1 or refreshed != 1:
        raise ValueError("resolution guards incomplete: dynamic=%d cached=%d" % (done, refreshed))
    import oot_output_size
    oot_output_size.apply(gen)
    print("oot_patches: dynamic, cached scale and output-size guards verified")



if __name__ == "__main__":
    apply(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "sa", "gen"))
