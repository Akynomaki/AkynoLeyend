"""Compile the lifted game (work/gen, from `lift.py --write`) into work/build/AkynoLeyend_game.dll (or a static library).

The flags are a64-kit's for lifted code (its build.py, cmd_native): -O1, LoopRotate's header copies capped (most of
the compile time in goto-dense giant functions otherwise), capture tracking past LLVM's 100 uses (the context
parameter is A64_NOESC), one section per function. The guest model is the 64-bit window (rtgen.py), shadowing the
vendored rt/, with the loop-header interrupt polls on (A64_POLLING, nx2/poll.py). Incremental: an object is rebuilt
only when its source or the flags changed.

AkynoLeyend_game.dll = the lifted chunks + a64-kit's tables and runtime + nx2/rt/eden_shim.c (the emulator ABI, mkw_host.h)
+ mkw_info.c (the image base and main's build id, generated here from work/image/image.json). Linking it is also the
check that the whole lifted game closes over itself: any unresolved symbol fails the link.

Heavy: 44 chunks of ~25 MB, ~100-200 s and ~2-3.5 GB each at -O1. The PC is shared with games: run it when the
machine is idle, and keep --jobs low otherwise.

--standalone builds work/sa/build/AkynoLeyend.exe instead: the standalone lift (work/sa/gen, `lift.py --standalone --write`)
+ the native runtime in host/ (TOTKPort's hos/, adapted). Objects are cached by their key in work/objcache, shared by
both builds: the two lifts share their chunk boundaries, so every chunk without a hooked function is the same source
and is not compiled twice.

Usage:  python -I nx2/build.py [--jobs 1] [--only 0,7] [--opt O1] [--no-polls] [--dll] [--lib] [--standalone]
  --only: just these code_NNN.c chunks (to measure); --dll: link AkynoLeyend_game.dll; --lib: archive AkynoLeyend_game.lib
"""
import argparse
import queue
import hashlib
import json
import os
import subprocess
import sys
import time
import threading
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import kit
import rtgen
import toolchain
from akynoleyend.build_support import object_key, link_options, video_libraries, is_mingw, shader_cache_stamp
from akynoleyend.config import compile_jobs
from akynoleyend import compile_plan
from akynoleyend.files import write_json
from akynoleyend.prebuilt import renderer_prebuilt
from akynoleyend.power import no_throttle

NX2_RT = os.path.join(kit.HERE, "rt")
HOST = os.path.join(kit.HERE, "..", "host")
OPUS = os.path.join(kit.HERE, "..", "third_party", "opus")
OBJ_CACHE = os.path.join(kit.WORK, "objcache")
COMPILE_COUNTS = Counter()
COMPILE_COUNTS_LOCK = threading.Lock()
# (0.4.5) akynoleyend/compile_plan.py: a unit starts when its expected peak fits in the free memory
GATE = compile_plan.MemoryGate(1 << 62, None)
UNIT_SECONDS = {}
UNIT_TIMES = {}
UNIT_PEAKS = {}


def note_compile(status):
    with COMPILE_COUNTS_LOCK:
        COMPILE_COUNTS[status] += 1
# (hookshot) work/hot_order.txt: the functions that run, hottest first (sampled), packed together by the linker; RX_NO_ORDER=1: off
PGO = os.environ.get("RX_PGO", "")


def HOT_ORDER():
    p = os.path.join(kit.WORK, "hot_order.txt")
    return ["-Wl,/order:@" + p.replace("\\", "/"), "-Wl,/ignore:4037"] if not is_mingw() and os.path.exists(p) and not os.environ.get("RX_NO_ORDER") else []


HOST_LIBS = ["-luser32", "-lwinmm", "-ladvapi32", "-lole32", "-lshell32", "-lgdi32", "-ldbghelp"]
GPU = os.path.join(kit.HERE, "..", "gpu")
# FFmpeg (libavcodec's VP8/VP9 decoders, swscale) for nn::codec's video decoders (host/nn_video.c): the static build
# in the Eglantine clone's package cache
FFMPEG = None   # (found in the CPM caches below, once cpm_dirs is defined)
def tree_headers(*roots, skip=()):
    """Every header under these folders, as one dependency blob (suyu's headers sit in many folders); folders named
    in skip are left out"""
    h = hashlib.sha1()
    for root in roots:
        found = []
        # (the walk pruned as it goes: sorting the whole walk first, as this once did, made skip do nothing, and every
        # gpu/vk header change rebuilt the WebGPU renderer)
        for d, dirs, files in os.walk(root):
            dirs[:] = sorted(x for x in dirs if x not in skip)
            found += [os.path.join(d, f) for f in files if f.endswith((".h", ".hpp", ".inc"))]
        for path in sorted(found):
            h.update(os.path.basename(path).encode() + open(path, "rb").read())
    return h.hexdigest().encode()


NGX_SDK_DIR = os.path.join(kit.ROOT, "third_party", "nvidia-dlss-sdk")
NGX_LIB = os.path.join(NGX_SDK_DIR, "lib", "nvsdk_ngx_s.lib")


def ngx_link():
    """What AkynoLeyend.dll's link adds for NVIDIA DLSS (Hookshot 2.1.0's ngx_link): NVIDIA's static NGX loader and the
    registry calls it makes, without Microsoft's C++ runtime it names (gpu/vk/vk_ngx_msvc_rt.cpp has what it needs of it).
    Nothing when NVIDIA's SDK is not in third_party/nvidia-dlss-sdk: the DLL is then built without DLSS"""
    if not os.path.isfile(NGX_LIB):
        return []
    # (its objects name Microsoft's C and C++ runtimes as default libraries: llvm-mingw has the UCRT's functions and
    # vk_ngx_msvc_rt.cpp the rest, as Hookshot 2.1.0's toolchain.native_link and ngx_link leave them out)
    return [NGX_LIB, "-ladvapi32"] + ["-Wl,-Xlink=/nodefaultlib:" + name
                                      for name in ("libcpmt", "libcmt", "oldnames", "libvcruntime", "msvcrt")]


def vk_sources():
    """The Vulkan back end (AkynoLeyend.dll, gpu/vk/vk_api.h): Eden's shader recompiler with its SPIR-V back end
    (gpu/vk/eden), sirit with Eden's mesh shader patch (gpu/vk/sirit) and the back end itself (gpu/vk/*.cpp)"""
    vk = os.path.join(GPU, "vk")
    out = []
    for sub in ("eden", os.path.join("sirit", "src")):
        for d, _, files in os.walk(os.path.join(vk, sub)):
            out += [os.path.join(d, f) for f in files if f.endswith(".cpp")]
    out += [os.path.join(vk, f) for f in os.listdir(vk) if f.endswith(".cpp")]
    vc = os.path.join(GPU, "third_party", "suyu", "video_core")
    out += [os.path.join(vc, "textures", f) for f in ("decoders.cpp", "astc.cpp")]   # (the WebGPU back end's unswizzle)
    return sorted(out)


def cpm_package(name):
    """Pinned dependencies in this distribution; never probe another project's checkout."""
    root = os.environ.get("OCARINA_DEPS", os.path.join(kit.ROOT, "ferramentas", "deps"))
    folder = {"vulkanheaders": "vulkan", "spirv-headers": "spirv", "vulkanmemoryallocator": "vma", "ffmpeg": "ffmpeg"}[name]
    path = os.path.join(root, folder)
    return path if os.path.isdir(path) else None


def cache_put(obj, key):
    """Hard-link a built object into the cache under its key (a copy across volumes)"""
    os.makedirs(OBJ_CACHE, exist_ok=True)
    dst = os.path.join(OBJ_CACHE, key + ".o")
    if os.path.exists(dst):
        return
    try:
        os.link(obj, dst)
    except OSError:
        import shutil
        shutil.copyfile(obj, dst)


FFMPEG = cpm_package("ffmpeg")


# the soft write watch (rt/a64.h A64_MARK): lifted stores mark their 4 KB page, and the renderer reads the marks
# instead of Windows' write watch (GetWriteWatch over the 6 GB MKW's GPU sees took ~20 ms a scan, in one thread or
# four: the race's replay waited ~12 ms a frame for it). RX_SOFT_WRITE_WATCH=0: Windows' write watch (a full rebuild)
WRITE_TRACK = [] if os.environ.get("RX_SOFT_WRITE_WATCH") == "0" else ["-DA64_WRITE_TRACK"]

# (hookshot) the host CPU the lifted game and the runtime are built for: x86-64-v3 (AVX2, FMA, BMI1/2, LZCNT,
# MOVBE; Haswell and Zen 1 on). With FMA the FPX1 fast paths cover double-precision FMA (RECOMP_FPX_FMA64; it took
# the exact software body on baseline x86-64) and the bit counts are single instructions. No contraction, so a C
# expression is rounded as written (the exact bodies and FPX1's proofs assume it). RX_MARCH=x86-64: the old baseline
CPU = ["-march=" + os.environ.get("RX_MARCH", "x86-64-v3"), "-ffp-contract=off"]


def flags(gen, rt64, opt, polls):
    return toolchain.native_target() + CPU + [
        "-I" + rt64, "-I" + gen, "-I" + os.path.join(kit.KIT, "rt"), "-I" + NX2_RT, "-Wno-everything",
        "-fno-strict-aliasing", "-mcx16", "-" + opt, "-g0", "-mllvm", "-rotation-max-header-size=0",
        "-ffunction-sections", "-mllvm", "-capture-tracking-max-uses-to-explore=5000"] + \
        (["-DA64_POLLING"] if polls else []) + WRITE_TRACK


def write_info(out):
    meta = json.load(open(os.path.join(kit.WORK, "image", "image.json")))
    mods = {m["name"]: m for m in meta["modules"]}
    path = os.path.join(out, "mkw_info.c")
    text = ('/* Generated by nx2/build.py from work/image/image.json. */\n#include <stdint.h>\n'
            'const uint64_t mkw_image_base = 0x%xULL;\nconst char mkw_main_build_id[] = "%s";\n'
            % (meta["base"], mods["main"]["build_id"]))
    if not os.path.exists(path) or open(path).read() != text:
        open(path, "w", newline="\n").write(text)
    return path


def compile_one(job):
    cc, src, obj, fl, deps = job
    key = object_key(cc, src, fl, deps)
    stamp = obj + ".sha256"
    if os.path.exists(obj) and os.path.exists(stamp) and Path(stamp).read_text() == key:
        note_compile("local_hits")
        return src, 0.0, None
    cached = os.path.join(OBJ_CACHE, key + ".o")
    if os.path.exists(cached):   # (the same source and flags built for the other target)
        if os.path.exists(obj):
            os.remove(obj)
        try:
            os.link(cached, obj)
        except OSError:
            import shutil
            shutil.copyfile(cached, obj)
        Path(stamp).write_text(key)
        note_compile("shared_hits")
        return src, 0.0, None
    t = time.time()
    temporary = obj + ".building"
    with subprocess.Popen([cc] + fl + ["-c", src, "-o", temporary],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace") as child:
        no_throttle(getattr(child, "_handle", None))
        print("  iniciando %s (PID %s)" % (os.path.basename(src), child.pid), flush=True)
        while True:
            try:
                stdout, stderr = child.communicate(timeout=15)
                break
            except subprocess.TimeoutExpired:
                print("  aguardando %s (PID %s, %.0fs nesta unidade)" %
                      (os.path.basename(src), child.pid, time.time() - t), flush=True)
    r = subprocess.CompletedProcess(child.args, child.returncode, stdout, stderr)
    if r.returncode:
        note_compile("failed")
        if os.path.exists(temporary):
            os.remove(temporary)
        return src, time.time() - t, r.stderr[-4000:]
    os.replace(temporary, obj)
    Path(stamp).write_text(key)
    cache_put(obj, key)
    note_compile("compiled")
    seconds = time.time() - t
    with COMPILE_COUNTS_LOCK:
        UNIT_SECONDS[os.path.basename(src)] = seconds
    return src, seconds, None


def main():
    kit.wait_for_quiet('the compile')
    p = argparse.ArgumentParser()
    p.add_argument("--jobs", type=int, default=None)
    p.add_argument("--only", default="")
    p.add_argument("--opt", default="O1")
    p.add_argument("--no-polls", action="store_true")
    p.add_argument("--dll", action="store_true")
    p.add_argument("--lib", action="store_true")
    p.add_argument("--standalone", action="store_true")
    p.add_argument("--reuse-game-objects", action="store_true")
    p.add_argument("--reuse-game-from", default="", help="Raiz anterior somente em leitura para validacao em copia isolada")
    a = p.parse_args()
    if a.reuse_game_from and (not a.reuse_game_objects or not a.standalone):
        p.error("--reuse-game-from exige --standalone --reuse-game-objects")
    vk_only = bool(os.environ.get("RX_VK_ONLY"))
    a.jobs = compile_jobs(a.jobs)
    sa = os.path.join(kit.WORK, "sa")
    gen = os.path.join(sa if a.standalone else kit.WORK, "gen")
    out = os.path.join(sa if a.standalone else kit.WORK, "build")
    obj_dir = os.path.join(out, "obj")
    os.makedirs(obj_dir, exist_ok=True)
    rt64 = os.path.join(out, "rt64") if vk_only else rtgen.write(os.path.join(out, "rt64"))
    cc = toolchain.need(toolchain.find("clang"))
    fl = flags(gen, rt64, a.opt, not a.no_polls)
    # (the lifted chunks include only the guest model: the emulator ABI header is a dependency of the shim alone)
    deps = b"" if vk_only else b"".join(
        open(os.path.join(d, f), "rb").read()
        for d in (gen, rt64) for f in sorted(os.listdir(d)) if f.endswith(".h")
    )
    shim_deps = deps + open(os.path.join(NX2_RT, "mkw_host.h"), "rb").read()
    chunks = [] if vk_only else sorted(f for f in os.listdir(gen) if f.startswith("code_") and f.endswith(".c"))
    if a.only:
        want = {"code_%03d.c" % int(n) for n in a.only.split(",")}
        chunks = [c for c in chunks if c in want]
    srcs = [os.path.join(gen, c) for c in chunks]
    host_srcs = []
    if not a.only and not vk_only:
        srcs += [os.path.join(gen, f) for f in ("a64_table.c", "a64_hooks.c", "a64_suyu.c")] + \
                [os.path.join(rt64, "a64_rt.c")]
        if a.standalone:
            srcs += [os.path.join(gen, f) for f in ("a64_stubs.c", "hos_image.c", "nvn2_exports.c")]
            host_srcs = sorted(os.path.join(HOST, f) for f in os.listdir(HOST) if f.endswith(".c") and f != "rx_webgpu_unavailable.c" and (f != "pgo_rt.c" or PGO == "gen"))
        else:
            srcs += [os.path.join(NX2_RT, "eden_shim.c"), write_info(out)]
    # biggest first, so the long ones do not end up alone at the end
    srcs.sort(key=lambda s: -os.path.getsize(s))
    # (hookshot) code_hot.c, the lift's hot functions together (A64_HOT_FUNCS + A64_HOT_CHUNK=1): at RX_HOT_OPT
    # (default O2), so the hot callees inline into their hot callers
    hot_fl = [("-" + os.environ.get("RX_HOT_OPT", "O2")) if f == "-" + a.opt else f for f in fl]
    # (hookshot) RX_PGO=gen: code_hot.c counts its branches (host/pgo_rt.c writes them; -O1 builds much sooner, and the counters are
    # placed before the optimiser, so a profile from it fits the -O2 build). RX_PGO=<merged .prof>: built with that profile
    if PGO == "gen":
        hot_fl = [f if f != "-O2" else "-O1" for f in hot_fl] + ["-fprofile-instr-generate", "-mllvm", "-disable-vp=true"]
    elif PGO:
        hot_fl = hot_fl + ["-fprofile-instr-use=" + PGO]
    jobs = [(cc, s, os.path.join(obj_dir, os.path.basename(s)[:-2] + ".o"),
             hot_fl if os.path.basename(s).startswith("code_hot") else fl,
             shim_deps if os.path.dirname(s) == NX2_RT else deps) for s in srcs]
    # the runtime: ordinary C at -O2, with its own headers (any host/*.h change rebuilds all of it)
    if a.reuse_game_from:
        from akynoleyend.object_reuse import isolated_game_jobs
        jobs = isolated_game_jobs(jobs, root=kit.ROOT, work=kit.WORK, previous_root=a.reuse_game_from)
    if a.reuse_game_objects:
        from akynoleyend.build_support import require_cached_game_objects
        require_cached_game_objects(jobs, OBJ_CACHE)
        print("Atualizacao: objetos traduzidos conferidos; nenhuma unidade do jogo sera recompilada.", flush=True)
    host_fl = toolchain.native_target() + CPU + ["-I" + HOST, "-I" + rt64, "-I" + gen, "-Wno-everything", "-O2", "-g0",
                                           "-mcx16", "-DA64_POLLING", "-DOCARINA_VULKAN_ONLY"] + WRITE_TRACK
    host_deps = deps + tree_headers(HOST, os.path.join(GPU, "render")) + open(os.path.join(GPU, "vk", "vk_api.h"), "rb").read()
    from nx2.oot_output_size import extended_output_emitted
    output_sites = bool(host_srcs) and extended_output_emitted(gen)
    jobs += [(cc, s, os.path.join(obj_dir, "host_" + os.path.basename(s)[:-2] + ".o"),
              host_fl + ["-I" + os.path.join(OPUS, "include")] +
              (["-DAKYNO_EXTENDED_OUTPUTS"] if output_sites and os.path.basename(s) == "nn_applet.c" else []) +
              (["-I" + os.path.join(FFMPEG, "include")] if FFMPEG else []), host_deps) for s in host_srcs]
    # libopus 1.5.2 (third_party/opus, from TOTKPort): nn::codec's hardware Opus decoder (host/nn_codec.c)
    if host_srcs:
        oflags = toolchain.native_target() + ["-O2", "-g0", "-Wno-everything", "-DOPUS_BUILD", "-DUSE_ALLOCA",
                                              "-DHAVE_LRINTF", "-DHAVE_LRINT"] +             ["-I" + os.path.join(OPUS, d) for d in ("include", "celt", "silk", "silk/float", "src")]
        for rel in open(os.path.join(OPUS, "sources.txt")).read().split():
            jobs.append((cc, os.path.join(OPUS, rel), os.path.join(obj_dir, "opus_" + rel.replace("/", "_")[:-2] + ".o"),
                         oflags, b"opus-1.5.2"))
    if a.standalone and not a.only and not vk_only:
        jobs.append((cc, os.path.join(HOST, "rx_webgpu_unavailable.c"),
                     os.path.join(obj_dir, "host_rx_webgpu_unavailable.o"), host_fl, host_deps))
    # the Vulkan back end, a DLL of its own (RX_BACKEND=vulkan): built when the Vulkan headers are in the CPM cache
    vk_jobs = []
    ready_renderer = None
    vk_headers, spirv_headers = cpm_package("vulkanheaders"), cpm_package("spirv-headers")
    if a.standalone and not a.only and not (vk_headers and spirv_headers and cpm_package("vulkanmemoryallocator") and FFMPEG):
        raise SystemExit("Missing Vulkan/SPIR-V/VMA/FFmpeg dependencies; run manage.py doctor first")
    if a.standalone and not a.only:
        deps_root = Path(os.environ.get("OCARINA_DEPS", os.path.join(kit.ROOT, "ferramentas", "deps")))
        ready_renderer = renderer_prebuilt(Path(kit.ROOT), deps_root,
            Path(os.environ.get("OCARINA_PREBUILT_DIR", str(deps_root.parent / "prebuilt"))), os.environ)
    if a.standalone and not a.only and not ready_renderer and vk_headers and spirv_headers:
        cxx = toolchain.need(toolchain.find("clang++"))
        vk = os.path.join(GPU, "vk")
        # (what the shader caches are good for: what translates shaders, not the whole DLL, so a build that changes something else
        # keeps them)
        stamp = shader_cache_stamp(Path(vk))
        vflags = toolchain.native_target() + CPU + [   # (hookshot: the replay is the frame's limit now)
            "-DHOOKSHOT_SHADER_STAMP=0x%sull" % stamp,
            "-std=c++20", "-O2", "-g0", "-DNDEBUG", "-Wno-everything", "-DVK_NO_PROTOTYPES", "-DMKWVK_BUILDING",
            *(["-DHOOKSHOT_RELEASE"] if os.environ.get("RX_RELEASE") == "1" else []),   # (the shaders precompiled before the game)
            # (Eden's recompiler before suyu's root: suyu has its own shader_recompiler/ headers, and a Shader::Info
            # of the other layout in some objects is what crashed the descriptor walk. MKWVK_INCLUDES changes the
            # object keys, which leave the include folders out, when this order changes)
            "-DMKWVK_INCLUDES=2",
            "-I" + os.path.join(vk, "compat"), "-I" + os.path.join(GPU, "compat"), "-I" + os.path.join(vk, "eden"),
            "-I" + os.path.join(GPU, "third_party", "suyu"),
            "-I" + os.path.join(vk, "sirit", "include"), "-I" + os.path.join(vk, "sirit", "src"),
            "-I" + os.path.join(spirv_headers, "include"), "-I" + os.path.join(spirv_headers, "include", "spirv", "unified1"),
            "-I" + os.path.join(vk_headers, "include"), "-I" + vk] +             (["-I" + os.path.join(cpm_package("vulkanmemoryallocator"), "include")] if cpm_package("vulkanmemoryallocator") else [])
        # (Eden's recompiler and sirit see only their own headers: a change to the back end's vk_*.h does not
        # rebuild their ~500 files; the back end itself depends on everything, suyu's texture decoders included)
        vk_lib_deps = tree_headers(os.path.join(vk, "eden"), os.path.join(vk, "sirit"), os.path.join(vk, "compat"),
                                   os.path.join(GPU, "compat"), os.path.join(spirv_headers, "include"),
                                   os.path.join(vk_headers, "include"))
        vdeps = vk_lib_deps + tree_headers(vk, os.path.join(GPU, "render"), os.path.join(GPU, "compat"),
                             os.path.join(cpm_package("vulkanmemoryallocator"), "include"),
                             os.path.join(GPU, "third_party", "suyu", "video_core", "textures"),
                             os.path.join(kit.ROOT, "third_party", "amd-fsr-sdk"))
        # (NVIDIA DLSS: NVIDIA's NGX SDK in third_party/nvidia-dlss-sdk, never distributed (NVIDIA's license; scripts/ngx_sdk.py
        # fetches it). vk_fsr_sdk.cpp and vk_ngx_msvc_rt.cpp include its headers by path when they are there: only those two
        # objects depend on it, so the other objects' keys stay as they were)
        ngx_deps = vdeps + b"ngx:" + (tree_headers(os.path.join(NGX_SDK_DIR, "include")) if os.path.isfile(NGX_LIB) else b"none")
        for src in vk_sources():
            name = os.path.relpath(src, vk).replace(os.sep, "_")[:-4]
            lib = os.path.relpath(src, vk).split(os.sep)[0] in ("eden", "sirit")
            ngx = name in ("vk_fsr_sdk", "vk_ngx_msvc_rt")
            vk_jobs.append((cxx, src, os.path.join(obj_dir, "vk_" + name + ".o"), vflags,
                            vk_lib_deps if lib else ngx_deps if ngx else vdeps))
        jobs += vk_jobs
    if vk_only:
        jobs = list(vk_jobs)
    print("%d files, %d jobs, %s" % (len(jobs), a.jobs, " ".join(f for f in fl if f.startswith("-D") or f.startswith("-O"))),
          flush=True)
    # (0.4.5) longest first by the times known (this PC's, else nx2/compile_hint.json), and the memory gate
    times_file = Path(kit.WORK) / "logs/compile-units.json"
    hint = Path(kit.HERE) / "compile_hint.json"
    times = compile_plan.load_times(hint, times_file)
    UNIT_TIMES.update(times)
    UNIT_PEAKS.update(compile_plan.load_peaks(hint))
    sizes = {j[1]: os.path.getsize(j[1]) for j in jobs}
    rank = {src: i for i, src in enumerate(compile_plan.order([j[1] for j in jobs], sizes, times))}
    jobs.sort(key=lambda j: rank[j[1]])
    global GATE
    GATE = compile_plan.gate_from_environment(report=lambda line: print(line, flush=True))
    print("memoria para compilar: %.1f GiB (%.1f GiB ficam para o sistema); ordem pelos tempos de %d unidades" %
          (GATE.budget / compile_plan.GIB, compile_plan.RESERVE / compile_plan.GIB, len(times)), flush=True)
    UNIT_SECONDS.clear()
    t0, failed = time.time(), 0
    COMPILE_COUNTS.clear()
    # (0.4.5) a slot that is free takes the first unit of the plan that fits in memory (compile_plan.MemoryGate.take);
    # before, each of the --jobs threads took the next unit first and then compiled it, whatever it weighed
    pending = [(compile_plan.unit_peak(j[1], sizes[j[1]], hot=os.path.basename(j[1]).startswith("code_hot"),
                                       seconds=UNIT_TIMES.get(os.path.basename(j[1])),
                                       measured=UNIT_PEAKS.get(os.path.basename(j[1]))), j) for j in jobs]
    finished = queue.Queue()

    def slot():
        while True:
            picked = GATE.take(pending, label=lambda job: os.path.basename(job[1]))
            if picked is None:
                return
            need, job = picked
            try:
                finished.put(compile_one(job))
            except BaseException as error:   # (raised again below, as the executor's result() did)
                finished.put(error)
            finally:
                GATE.release(need)

    slots = [threading.Thread(target=slot, name="compilador-%d" % i, daemon=True) for i in range(a.jobs)]
    for thread in slots:
        thread.start()

    def results():
        for _ in range(len(jobs)):
            item = finished.get()
            if isinstance(item, BaseException):
                raise item
            yield item

    # (as each ends, not in order: the builder app shows progress from these lines, and the longest unit comes first)
    for src, secs, err in results():
        size = os.path.getsize(src) >> 20
        if err:
            failed += 1
            print("FAILED %s (%d MB, %.0fs):\n%s" % (os.path.basename(src), size, secs, err), flush=True)
        else:
            print("  %-16s %4d MB  %6.0fs  (%.0fs)" % (os.path.basename(src), size, secs, time.time() - t0), flush=True)
    print("compiled in %.0fs, %d failed" % (time.time() - t0, failed), flush=True)
    if UNIT_SECONDS:
        try:
            compile_plan.save_times(times_file, {k: v for k, v in UNIT_SECONDS.items()
                                                 if k.startswith("code_") or k == "a64_table.c"})
        except OSError as error:
            print("tempos por unidade nao gravados: %s" % error, flush=True)
    print("agendador: ate %d compiladores ao mesmo tempo; %d esperas por memoria" %
          (GATE.peak_running, GATE.waits), flush=True)
    counts = {key: COMPILE_COUNTS[key] for key in ("local_hits", "shared_hits", "compiled", "failed")}
    write_json(Path(kit.WORK) / "logs/compile-summary.json",
               {"schema": 1, "units": len(jobs), "jobs": a.jobs, "most_at_once": GATE.peak_running,
                "memory_waits": GATE.waits,
                "renderer_prebuilt": bool(ready_renderer),
                "compile_seconds": round(time.time() - t0, 3), **counts})
    print("cache: %d objetos locais, %d compartilhados; %d compilados, %d falhas" %
          tuple(counts.values()), flush=True)
    if failed:
        return 1
    vk_objs = {j[2] for j in vk_jobs}
    if ready_renderer:
        import shutil
        shutil.copyfile(ready_renderer, os.path.join(out, "AkynoLeyend.dll"))
    objs = [j[2] for j in jobs if j[2] not in vk_objs]
    rsp = os.path.join(out, "objs.rsp")
    if not vk_only:
        open(rsp, "w").write("\n".join('"%s"' % o.replace("\\", "/") for o in objs))
    if a.lib:
        lib = os.path.join(out, "AkynoLeyend_game.lib")
        subprocess.run([toolchain.lld_link(), "/lib", "/out:" + lib, "@" + rsp], check=True)
        print("wrote %s (%d objects, %d MB)" % (lib, len(objs), os.path.getsize(lib) >> 20))
    if a.standalone and not a.only and not vk_only:
        exe = os.path.join(out, "AkynoLeyend.exe")   # (+ AkynoLeyend.map: crash offsets -> f_<guest address>)
        t = time.time()
        r = subprocess.run([cc] + toolchain.native_target() + toolchain.native_link() +
                           ["-o", exe, "@" + rsp] + link_options(exe[:-4] + ".map", stack=True, windowed=os.environ.get("RX_RELEASE") == "1") + HOT_ORDER() + HOST_LIBS +
                           (["-Wl,/nodefaultlib:clang_rt.profile.lib"] if PGO == "gen" else []) +
                           ([os.path.join(kit.ROOT,"assets","AkynoLeyend.res")] if os.path.exists(os.path.join(kit.ROOT,"assets","AkynoLeyend.res")) else []) +   # (nx2/make_icon.py)
                           (video_libraries(FFMPEG) if FFMPEG else []),
                           capture_output=True, text=True)
        undefined = sorted({l.strip() for l in (r.stdout + r.stderr).splitlines() if "undefined symbol" in l})
        if r.returncode:
            print("link FAILED (%.0fs), %d undefined symbols" % (time.time() - t, len(undefined)))
            print("\n".join(undefined[:60]) if undefined else (r.stdout + r.stderr)[-3000:])
            return 1
        print("linked %s: %d MB (%.0fs)" % (exe, os.path.getsize(exe) >> 20, time.time() - t))
        # (hookshot) SDL2.dll beside it: host/pad_sdl.c's controllers (DualSense, DualShock 4, Switch Pro ...)
        # (AkynoLeyend r12, as Hookshot v2.1.0: SDL2.dll is sdl2-compat, which runs on SDL3.dll beside it)
        for sdl_name in ("SDL2.dll", "SDL3.dll"):
            sdl = os.path.join(kit.HERE, "..", "third_party", "sdl2", sdl_name)
            sdl_dst = os.path.join(out, sdl_name)
            if os.path.exists(sdl) and (not os.path.exists(sdl_dst) or open(sdl, "rb").read() != open(sdl_dst, "rb").read()):
                import shutil
                shutil.copyfile(sdl, sdl_dst)
    if vk_jobs:   # (AkynoLeyend.dll beside the exe: loaded by host/rx_backend.c with RX_BACKEND=vulkan)
        vdll = os.path.join(out, "AkynoLeyend.dll")
        vrsp = os.path.join(out, "vk_objs.rsp")
        open(vrsp, "w").write("\n".join('"%s"' % j[2].replace("\\", "/") for j in vk_jobs))
        t = time.time()
        r = subprocess.run([cxx] + toolchain.native_target() + toolchain.native_link() +
                           ["-shared", "-o", vdll, "@" + vrsp, "-luser32", "-lgdi32"] + link_options(vdll[:-4] + ".map") +
                           ngx_link(),
                           capture_output=True, text=True)
        if r.returncode:
            undefined = sorted({l.strip() for l in (r.stdout + r.stderr).splitlines() if "undefined symbol" in l})
            print("AkynoLeyend.dll link FAILED, %d undefined symbols" % len(undefined))
            print("\n".join(undefined[:60]) if undefined else (r.stdout + r.stderr)[-3000:])
            return 1
        print("linked %s: %d MB (%.0fs)" % (vdll, os.path.getsize(vdll) >> 20, time.time() - t))
    if a.dll and not a.only:
        dll = os.path.join(out, "AkynoLeyend_game.dll")   # (+ AkynoLeyend_game.map: crash offsets -> f_<guest address>)
        t = time.time()
        r = subprocess.run([cc] + toolchain.native_target() + toolchain.native_link() +
                           ["-shared", "-o", dll, "@" + rsp] + link_options(dll[:-4] + ".map"),
                           capture_output=True, text=True)
        undefined = sorted({l.strip() for l in (r.stdout + r.stderr).splitlines() if "undefined symbol" in l})
        if r.returncode:
            print("link FAILED (%.0fs), %d undefined symbols" % (time.time() - t, len(undefined)))
            print("\n".join(undefined[:40]) if undefined else (r.stdout + r.stderr)[-3000:])
            return 1
        print("linked %s: %d MB, no undefined symbols (%.0fs)" % (dll, os.path.getsize(dll) >> 20, time.time() - t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
