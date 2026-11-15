## Teste 3 (09/11/2026)

Hookshot 2.0.10, GPL-3.0: ASTC→BC3 usa uma camada de scratch por vez (#956).
Reparo local: CAS rastreado para storage mantém comparador e substituição.
O menu Windows recebe mouse/WASD/Ctrl+M, Full HD e FPS do launcher. ABI pública
Vulkan preservada. O tradutor mudou: novo stamp, sem reaproveitar SPIR-V incompatível.

# Test 2 selected CPU backports — 2026-11-09

Hookshot v2.0.10 commit 7f9daf06d902588476102d6650c600bb84f02ce5 supplied the
sampler generation/cache wrapper and contiguous capture-copy helper/regression.
Adapted in vk_bank.cpp, vk_draw.cpp and vk_memory.cpp; existing sampler creation
and AMD depth-comparison behavior retained. These additions remain under GPL-3.0;
see ../licenses/Hookshot-GPL-3.0.txt and ../docs/origem.md. No write-back diff,
separate present queue or reserved NX2navi additions were imported. Shader translator,
public host ABI and FSR shaders are unchanged in this maintenance update.

# Current source layout — AkynoLeyend graphics work 2026-11-09

The active renderer/compiler is `vk/` (Vulkan + Eden + Sirit). Unused WebGPU
implementation files, the duplicate Suyu shader compiler and the obsolete offline
shadertool have been removed. `render/` retains only `rx.h`, `rx_nvn.h` and
`nvn_api.h`, required shared ABI headers. Texture decoders and required support
libraries, per-file notices and license texts remain. See `../docs/limpeza-043.json`.

Selected Hookshot snapshot fa439391aae6f3bf104340ea36c6ea993b38534e backports
include REGMAP allocation, point-mesh coordinates, per-stage binding generations,
empty-barrier reuse, and the complete limited 32-bit ATOMG.CAS IR/backend chain.
The existing component licenses apply; this is not an import of the entire newer
compiler. Generic FSR1 headers come unmodified from GPUOpen-Effects/FidelityFX-FSR
commit a21ffb8f6c13233ba336352bdff293894c706575 under MIT, in `vk/shaders/ffx/`.
Local wrappers/presentation and bounded seed reading are described in `../docs/origem.md`.

## Historical provenance (paths below describe the former upstream layout)

# gpu/: the standalone build's renderer

`render/`, `compat/` and `third_party/suyu/` are TOTKPort's renderer (`a64-kit/gpu/`, commit `e88744a`,
2026-10-31): the native NVN layer's replay on WebGPU (wgpu-native on the PC), its texture, buffer, pipeline and
present code, and suyu's shader recompiler with TOTKPort's WGSL backend. `host/nvn_native.c` and `host/display.c`
are the API side and the window, from the same commit (see `host/PROVENANCE.md`).

Licensing as in TOTKPort's `NOTICE.md`: suyu's parts are GPL-2.0-or-later / GPL-3.0-or-later per file (texts in
`third_party/suyu/`); `render/nvn_api.h` (h1k421, as adapted by jhaizhou), the NVN layer's design (jhaizhou's
d2r-mobile / MacNativeGames) and the FSR 1 port in `render/rx_present_fx.cpp` are MIT; `render/renderdoc_app.h` is
RenderDoc's MIT header. wgpu-native (MIT or Apache-2.0) is not vendored: `nx2/build.py` takes TOTKPort's build of it
(`WGPU_NATIVE` for another).

mkw-recomp's changes, for the Switch 2:
- **Ampere shaders.** `third_party/suyu/shader_recompiler/frontend/ampere/` is Eglantine's Ampere-to-Maxwell
  lowering (header-only; Eden Emulator Project, GPL-3.0-or-later, from the `work/eg` clone). `environment.h` gains
  `TranslateProgramAddress` and the control flow passes indirect branch targets through it, as in Eglantine.
- **NVN2 shader packages** (`render/rx_shader.cpp` `read_nvn_code`): the control section's layout (magic
  `0x98761234`, code length `+0x38`, c1 constants `+0x40..+0x44`, stage `+0x56`, workgroup `+0x58`), the 128-byte
  graphics program header, and the lowering before the Maxwell frontend.
- **The Switch 2's GOB swizzle** (the Tegra X1's with offset bits 5 and 6 swapped, from Eglantine's native tiling):
  `third_party/suyu/video_core/textures/decoders.h` (the CPU swizzle masks), the two WGSL unswizzles in
  `render/rx_texture_gpu.cpp`, and `bl_offset` in `render/rx_nvn.cpp`.
- **The 64-bit guest window**: per-page tables in `render/rx_buffer.cpp` are committed untouched (`PageTable`).
- **The window crop** (`rx_present_crop`): MKW renders at a dynamic size into a 3840x2160 window texture and crops
  it; the crop is copied out and presented.

`mkw_gpu.cpp` / `mkw_gpu.h` / `build-gpu.bat` are the earlier Vulkan stand-in (a window and a swapchain; no longer
loaded). `shadertool.cpp` runs dumped NVN2 programs through Eglantine's recompiler offline (SPIR-V; it prints what
each program reads from the constant banks).
