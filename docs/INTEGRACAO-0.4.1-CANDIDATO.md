> HISTÓRICO: este documento descreve uma revisão anterior. O estado atual está em `../README.md` e `Relatorio-AkynoLeyend-0.4.2.md`.

# AkynoLeyend — integração candidata 0.4.1 (8/11/2026)

**Pacote único do projeto Windows.** Esta distribuição parte exatamente de `AkynoLeyend-Builder-0.4.0-windows.zip` (SHA-256 do ZIP original: `d188142f0ae49dbdbcf6c713a896c5154a472b8b67554100b4ebad6aa5637512`). Contém todos os componentes de distribuição originais e fontes modificados. **O executável `AkynoLeyendBuilder.exe` e a DLL Vulkan `ferramentas/prebuilt/AkynoLeyend.dll` permanecem binários da 0.4.0**; não foram recompilados no Linux. Não é uma build de jogo pronta. Não contém ROM, jogo, saves ou caches privados.

## Melhorias efetivamente implementadas nos fontes

1. **Vegetação / arquivos** (`host/nn_fs.c`, `host/nn_fs_directory_entry.h`): layout de `nn::fs::DirectoryEntry` alterado de `type` no deslocamento incorreto `0x302` para `0x304`, preservando `size` em `0x308`, para as entradas normais e para o overlay de mods. Estrutura com três `static_assert` de ABI e teste C executável. Motivação: fix de folhagem do Hookshot 2.0.5. **Exige recompilar o EXE do host; trocar somente a DLL não aplica isto.**
2. **Compilação task/mesh na AMD** (`gpu/vk/vk_draw.cpp`): backport limitado do comportamento da PR430 de NotRexed/Hookshot: desliga a otimização de *graphics pipelines* apenas para estágios task/mesh em GPU `vendorID=0x1002`, com contagem de mensagens limitada. `RX_VK_MESH_OPT=1` restaura comportamento anterior. Pode mitigar o `device lost` do driver em programas de vegetação; não é correção comprovada para a RX 9060 XT. **Exige nova compilação da DLL.**
3. **Escala experimental 125% e 150%** (`akynoleyend/graphics.py`): reutiliza `HOS_RES_SCALE` da rota fixa já implementada no host, com `HOS_DYNRES=0` e `AKYNO_RESOLUTION=1`. `Jogar-MaxResolucao-125.cmd` e `Jogar-MaxResolucao-150.cmd` permitem testá-la com o launcher existente; fontes WPF também aceitam esses valores após compilação da GUI. **Não transplanta o patch IPS do emulador, não ativa DLSS/FSR, nem garante saída 4K.** O menu Insert da DLL 0.4.0 ainda mostra a opção base `100%` enquanto `HOS_RES_SCALE` determina a escala. Mais pixels podem estourar orçamento de memória ou falhar em render targets do jogo: opção experimental, desligada no Original.
4. **Cache `equilibrado`** (`akynoleyend/environment.py`): opção opt-in, entre o fluxo Original e o Streaming; reutiliza os limites já codificados no Vulkan, com janela de leitura 32 MiB, 4 compiladores, preparação até 192 programas / 384 pipelines e até 10 admissões por segundo. Não há benchmark que garanta FPS ou menos stutter; pode consumir mais RAM/CPU. `Jogar-Cache-Equilibrado.cmd` ativa o perfil. O Original permanece intocado.
5. **Threads de compilação configuráveis** (`akynoleyend/cli.py`, `launch.py`, `shader_prepare.py`): `run --shader-workers N` e `prepare-shaders --shader-workers N`, de 1 a 8, passam `RX_VK_COMPILE_THREADS` diretamente; valores herdados do shell continuam filtrados. Não modifica o compilador Ampere/SPIR-V; controla seus workers já existentes.
6. **Preparação repetida mais econômica** (`akynoleyend/shader_prepare.py`): se o arquivo de shader bank já publicado possui tamanho e SHA-256 correspondentes ao banco privado validado, deixa de regravar gigabytes. Em arquivo ausente, adulterado ou diferente, continua a publicação em staging com verificação criptográfica. A economia é de cópia/IO de disco repetido, **não de tempo de tradução inicial**.

## Comparação detalhada do `analise_catalogo.rar`

| Referência recebida | Situação na base | Decisão |
|---|---|---|
| `shaders_glsl/fragment/temporal_upscale.frag` | Vulkan já possui `gpu/vk/shaders/taau_upscale.comp` com histórico temporal, parâmetros e SPIR-V vinculado ao pipeline. O shader do emulador precisa de motion vectors, jitter e históricos nos bindings próprios. | Não copiado; trocar um shader sem os recursos compatíveis quebra a renderização. |
| `rendering/frame_generation/lossless_dll.*` | Já existe o próprio `gpu/vk/vk_framegen.cpp` com fluxo de imagens, motion estimation e interpolação opt-in. LSFG possui dependências e ABI próprias. | Não incluído; não anunciar LSFG/FSR3 sem integração real. |
| `gpu_otimizacao/thread_split/gpu_split.*` | Divide o processamento de registradores/macros GPFIFO de um emulador. AkynoLeyend usa tradução AArch64 para código nativo e NVN replay, sem esse mesmo frontend de emulação. | Estudado; transplantar a fila SPSC diretamente é incompatível. |
| `configuracao/switches/nx2_switches.txt` | As variáveis `EDEN_NX2_*` não são automaticamente aceitas pelo host do AkynoLeyend. As opções equivalentes de Vulkan são `RX_VK_*`. | Não aplicar variáveis inertes como otimizações reais. |
| `configuracao/settings/settings.h` | `ResolutionScalingInfo` pertence ao frontend do outro emulador. Aqui já existe `HOS_RES_SCALE` no host. | Reutilizado o caminho real, como experimento limitado. |
| `max_resolution_mod/shader_environment.cpp` | O arquivo recebido possui rejeição por endereço `EDEN_NX2_REJECT`; **não confirmou a implementação `EDEN_NX2_REJECT_HASH` alegada no catálogo**. Os seis hashes aparecem num patch de texto como workaround opt-in, não provam que os shaders foram introduzidos pelo mod. | Não rejeitar programas de iluminação/neblina/grama: pode fazer geometria desaparecer. |
| `shaders_glsl/compute/fsr3_*` | Os dois GLSL dependem de imagens, motion vectors e etapas específicas; não são a biblioteca AMD FSR 3.1 completa nem uma integração para o renderer atual. | Não chamar esses arquivos de FSR3 funcional. |
| `shaders_glsl/compute/vulkan_vertex_repack.comp` | GPU Vulkan já traduz e faz uploads/repack quando necessário; layouts não equivalentes exigem integração e validação em draw calls. | Não transplantado sem perfil e testes. |
| `fidelityfx_fsr.frag` | O arquivo precisa de includes `ffx_a.h` e `ffx_fsr1.h` e de dois estágios reais EASU/RCAS com bindings corretos. Os includes não vieram nesse catálogo. | FSR original permanece **não implementado**. |

Em particular, o catálogo mistura observações sobre **Mario Kart World/Title 1** e **Ocarina**; o efeito de cada patch precisa ser confirmado para a base compatível. Não usar o material como prova de benchmark no AkynoLeyend. Os números "+54%" e "1.46×" se referem aos cenários e ao emulador que mediu a divisão em duas threads, não a este runtime.

## Uso integrado

- Extraia este ZIP em **uma pasta nova**. Abra `AkynoLeyendBuilder.exe`, selecione sua entrada local válida e **recompile com Criar**. Como os fontes `gpu/` mudaram, o prebuilt da DLL antiga será automaticamente recusado por hash e o renderizador será compilado dos fontes no Windows. O EXE do jogo também precisa ser recompilado para receber a correção de diretórios.
- Para investigar a vegetação use `Jogar.cmd --resolution 100 --upscaling off --framegen 0`, compare exatamente a mesma cena antes e depois. Os ajustes novos de resolução não são uma correção de folhagem.
- Para 125% e 150%, use os scripts `Jogar-MaxResolucao-125.cmd` ou `Jogar-MaxResolucao-150.cmd`. Volte para `Jogar.cmd` se surgirem telas pretas ou VRAM excessiva. Não execute essas opções como padrão na RX 9060 XT durante a investigação do crash.
- Cache equilibrado: `Jogar-Cache-Equilibrado.cmd`. Personalização: `Jogar.cmd --shader-workers 2` ou `Preparar-Shaders.cmd --shader-workers 2` (as flags são repassadas ao Python).
- Recompilar apenas a DLL e aplicar `Atualizar-Renderizador.cmd` **não** incorpora a correção de vegetação, pois ela altera `host/nn_fs.c`.
- Para recompilar o launcher WPF atualizado com as opções gráficas na lista, é necessário .NET SDK 8 para Windows; até lá o **EXE WPF incluído continua 0.4.0** e os `.cmd`/CLI acima fornecem as novas opções.

## Validação executada, limitações

- Arquivos do RAR lidos passivamente via libarchive, sem executar instaladores ou DLLs de terceiros; fontes Hookshot, NX2navi e fork MDias comparados.
- Correção de DiretoryEntry verificada por fixture C real (`-std=c11 -Wall -Wextra -Werror`) e verificação textual dos dois caminhos de `ReadDirectory`.
- Testes Python da CLI, tipos, cache e reuso da preparação passaram; executada a suíte maior no Linux. Dois módulos de testes NUP não puderam ser importados porque falta a biblioteca **`zstandard`** no Python do ambiente de análise; falha de ambiente, não prova de defeito no código. Dez testes dependem de PowerShell/Windows e foram omitidos.
- O novo trecho C++ do driver AMD **não foi compilado nem executado neste Linux**. Seus parâmetros foram conferidos contra a versão correspondente do Hookshot. O jogo, a DLL, a GUI e uma GPU física não foram executados; renderização, FPS, vegetação por proximidade e device lost permanecem **pendentes de teste real**.
- Ainda não incorporados: FSR nativo verdadeiro, frame generation LSFG/FSR3, shaders compute do NX2, patch ARM64 Max Resolution/Dynamic FPS do emulador, GPU thread split, OpenGL e as demais alterações extensas de culling da versão recente do Hookshot. Não seriam seguros de copiar automaticamente.

## Créditos e documentação

Derivado da base AkynoLeyend 0.4.0 / Hookshot (licenças e atribuições originais preservadas). Referências analisadas: NotRexed/Hookshot v2.0.5, PR430 (YunaraDebugs), PR de correção de diretórios para folhagem; `NX2navi-0.5.0`, `eglantine_NX2_forkMDias_v6`, `analise_catalogo.rar` fornecidos pelo usuário. Não foram copiados componentes não compatíveis ou códigos de plugins proprietários.
