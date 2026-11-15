# Componentes e licencas

Os avisos contidos nos fontes originais continuam aplicaveis. Este arquivo complementa `LICENSE` e os documentos PROVENANCE das pastas.

| Componente | Origem | Licenca / avisos |
|---|---|---|
| Hookshot, runtime e ferramentas de origem | `Hookshot-Release.zip`, NotRexed | Codigo proprio MIT; componentes abaixo mantem suas licencas |
| Eden e suyu | Fontes incluidos no Hookshot | GPL-3.0-or-later / GPL-2.0-or-later, conforme cada arquivo |
| Sirit | Copia incluida no Hookshot | BSD de tres clausulas, conforme pasta e arquivos |
| a64-kit e tradutor AArch64 | Copia incluida no Hookshot | Avisos em `third_party/a64-kit`; componentes suyu sob GPL |
| Opus e ZBIC | Fontes incluidos no Hookshot | Licencas e avisos nas respectivas pastas |
| CPython e LLVM-MinGW | Ferramentas do Setup 0.2.1 fornecido | Avisos mantidos na distribuicao e em `ferramentas/licenses` |
| NumPy, lz4, Capstone e Unicorn | Distribuicoes Python Windows | Licencas e metadados preservados nos pacotes e dist-info |
| Vulkan-Headers e VMA | Headers do Setup 0.2.1 fornecido | Avisos nos headers; licencas complementares em ferramentas/licenses |
| SPIRV-Headers | Khronos, tag vulkan-sdk-1.4.328.1 | Licencas do projeto preservadas em ferramentas/licenses |
| FFmpeg 8.0 | Tarball oficial; build minimo sem bibliotecas externas | LGPL-2.1-or-later; fonte correspondente em `third_party/ffmpeg-source` e configuracao do build em ferramentas/licenses |
| Interface WPF Hookshot Builder | `builder/HookshotBuilder` do ZIP original | MIT do codigo proprio; tema e traducoes preservados |
| .NET 8.0.33 / WPF | Pacotes oficiais Microsoft.NETCore.App e Microsoft.WindowsDesktop.App, win-x64 | MIT e avisos em `licenses/dotnet` |
| python-zstandard 0.25.0 | Pacote cp314 Windows x64 do HookshotBuilder(1).zip fornecido | BSD-3-Clause; avisos preservados no dist-info e licenses/zstandard |
| Lista de otimizacao de funcoes | work/hot_funcs.txt do mesmo pacote; build e0f3ccfa | Metadados de enderecos fornecidos com o Hookshot; sem corpos de funcoes |
| Hookshot atualizado, shaders de filmes e workaround visual | HookshotBuilder (1)(1).zip e HookshotBuilder (2).zip fornecidos | MIT do codigo proprio; Eden/Orchid GPL-3.0-or-later conforme avisos dos fontes |
| Perfil Vulkan AMD | Adaptacao dos workarounds verificados no emulador Eglantine/Lichii fornecido | GPL conforme arquivos de origem e componentes Eden; avisos preservados |
| Hookshot pointer-lighting-2 | HookshotBuilder(3).zip, asset oficial conferido por SHA-256 | MIT do codigo proprio; arquivos Eden/Lichii mantem avisos GPL e demais licencas |
| Orquestracao e lancadores novos | Esta adaptacao | MIT |

O build completo combina componentes GPL; a licenca MIT do codigo proprio do Hookshot nao transforma todos os componentes em MIT. Preserve estes avisos ao redistribuir fontes ou ferramentas.

| Hookshot foliage-linux-updater / EvilOOT | Fontes oficiais no commit170ce53; integracao local documentada | GPL e demais avisos conforme fontes e LICENSE |
| SDL Windows (r12) | SDL2.dll: sdl2-compat 2.32.74 (github.com/libsdl-org/sdl2-compat, release-2.32.74, win32-x64, SHA-256 do ZIP 94a0184b...1cc0); SDL3.dll: SDL 3.4.20 (github.com/libsdl-org/SDL, release-3.4.20, win32-x64, SHA-256 do ZIP 368bed8b...4752), as versoes que o Hookshot v2.1.0 fixa | zlib; licenca e versoes em third_party/sdl2/LICENSE.txt e VERSION.txt |
| Hookshot v2.1.0 (r11, r12, r13, r13b, r13d) | github.com/NotRexed/Hookshot, tag v2.1.0, commit 8ef84611049f4fc31835a0b12793cf074ed49c3c: vk_reflex, vk_antilag, hos_sdl, hos_motion, hd_rumble, pad_sdl, nn_audio_in, mouse_native, oot_text_size, shaders hdr_encode e fg_scale (como wide_sides), trechos de nn_hid.c, hos.h, nn_vi.c, vk_framegen.cpp e os ganchos de nx2/oot_patches.py e nx2/oot_wide.py; o fallback de mesh shaders por compute (issue 640): trechos de gpu/vk/eden/shader_recompiler (runtime_info.h, shader_info.h, backend/spirv/emit_spirv.cpp/.h, emit_spirv_mesh.cpp, emit_spirv_instructions.h, emit_spirv_context_get_set.cpp, spirv_emit_context.cpp/.h) e de vk_shader.cpp/.h, vk_draw.cpp, vk_main.cpp e vk_internal.h; na r13d, o limite dos lacos de compare-exchange (issue 17), a posicao invariante e a protecao contra NaN nas saidas de cor (mma_layout.h, spirv_emit_context.cpp, emit_spirv_context_get_set.cpp, vk_coopmat.cpp) e, do PR 2464 posterior a v2.1.0, o snapshot de uniformes por padrao na Intel (vk_draw.cpp) | GPL-3.0 (os arquivos do Eden mantem seus avisos SPDX do Eden e do yuzu) (LICENSE do repositorio); avisos preservados nos arquivos |
| Hookshot main, apos a v2.1.0 (r13i, 0.4.4) | github.com/NotRexed/Hookshot: PR 1334 (funcao de leitura da memoria global expandida nos estagios de tarefa e malha, as arvores no ar: spirv_emit_context.cpp), PR 2263 (sonos curtos do jogo no timer com ate 6 processadores logicos: host/hos_thread.c) e PR 2826 (o descarte de texturas tira so o excesso: vram_policy.h evict_target, vk_texture.cpp), adaptados; scripts/oot_saves.py e docs/saves.md (onde cada emulador guarda o save e a busca pelos perfis), adaptados em akynoleyend/saves.py (Ferramentas > EXPORTAR SAVES) | GPL-3.0; avisos preservados nos arquivos |
| Lichii e Fritchii (r13j, 0.4.4) | github.com/zortos293/Lichii e github.com/Frizti/Fritchii: so a ideia de compilar por preset de CPU (YUZU_BUILD_PRESET generic/v3); nenhum codigo copiado (akynoleyend/cpu.py e proprio) | GPL-3.0 (referencia) |
| Pontos de ultrawide do HUD, filmes e imagem do save (r13) | nx2/oot_wide.py do Hookshot v2.1.0, que os credita a NX2navi recomp/patches-v111.txt: "The matrix-update, UI and movie sites: Copyright (c) 2026 Ivan0xFF" | MIT (Ivan0xFF) dentro do Hookshot GPL-3.0; credito preservado em nx2/oot_patches.py |
| MFG-Unlocker (0.4.5-test.1) | github.com/dashdogy/MFG-Unlocker, ramo main em 13/11/2026: `source/native/xess/xefg_dynamic_count.h` copiado sem mudancas em `gpu/vk/fg_dynamic_count.h` (SHA-256 do original 6b9fec52a8c24faa80fc21fb88e1a0845a68e29d0d0498ecd2556de3bcd483e8); de `xemfg_dynamic.h` e `sdk_pacing_meter.h` so ideias (o alvo logo abaixo da taxa do monitor; quadros isolados longos fora da media do ritmo), codigo proprio em `gpu/vk/fg_dynamic.h` e `gpu/vk/fg_pacer.h`. Nada das partes NVIDIA/Intel (patches de driver, shaders, modelo, injecao de DLL) | MIT, Copyright (c) 2026 Michael Robles; texto em `licenses/mfg-unlocker/LICENSE.txt` e no topo de `gpu/vk/fg_dynamic_count.h` |
