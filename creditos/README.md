# Créditos — AkynoLeyend

AkynoLeyend é o nome desta adaptação e de seu launcher. A base técnica e suas contribuições têm os autores abaixo. O novo nome não altera a autoria nem as licenças dos componentes herdados.

| Autor/projeto | Contribuição utilizada ou estudada |
|---|---|
| [NotRexed / Hookshot](https://github.com/NotRexed/Hookshot) e colaboradores | Lifter ARM64, runtime, renderizador, ferramentas e interface WPF de origem; base inicial MIT com componentes sob outras licenças |
| [evilmfkr / EvilOOT](https://github.com/evilmfkr/Hookshot), comentários EvilBoyce | Folhagem, iluminação, sincronização de filme; PR296 sobre espera da escrita de resultados da GPU antes da leitura pela CPU |
| [SkippySteve](https://github.com/SkippySteve) | Otimizações de consulta de textura, streams de vértices, estado dinâmico e hazards de render pass: PR300, PR327, PR362 e PR416 |
| [duck-paradise](https://github.com/duck-paradise) | PR593: referência da retenção seletiva de pequenas texturas finalizadas escritas pela GPU |
| [AyyBeeDee20738](https://github.com/AyyBeeDee20738) | PR252: referência de correções seletivas de dispatch/culling, sem afirmar solução completa da folhagem |
| [YunaraDebugs](https://github.com/YunaraDebugs) | Mitigação candidata de compilação task/mesh AMD (PR430) preservada da integração 0.4.1 |
| [pelicanux](https://github.com/pelicanux) | PR759: correção das colisões de marcadores do tradutor e regressão sintética de 89 casos, em trabalho ainda não publicado |
| BlueHeisenberg e colaboradores do Hookshot v2.0.6 | PR849 e integração de resolução de saída e recursos associados, adaptadas nesta cópia de trabalho |
| [AMD GPUOpen / FidelityFX-FSR](https://github.com/GPUOpen-Effects/FidelityFX-FSR) | Headers MIT oficiais do FSR 1, EASU e RCAS; wrappers e integração Vulkan locais |
| Eden, suyu, yuzu, Sirit e Orchid | Tradutor de shaders e componentes herdados; avisos preservados nos arquivos e pastas correspondentes |
| a64-kit, Opus e ZBIC | Ferramentas/runtime e bibliotecas incluídas na base; licenças nas respectivas pastas |
| [ProfMPPDias / Eglantine NX2](https://github.com/ProfMPPDias/eglantine_NX2_forkMDias) e Lichii | Referência de estudo do pipeline gráfico e do tratamento de memória/consultas; adaptações AMD anteriores documentadas em `docs/origem.md` |
| Dark e demais autores dos patches de emulador | Dynamic FPS e Max Resolution estudados como referência. Nenhum IPS desses patches foi transplantado para o EXE recompilado |
| AlfaDev23 e colaboradores citados nas releases externas | Correções Intel consideradas no estudo; não é atribuída a esta entrega a implementação de todo o conjunto externo |
| Microsoft, Python Software Foundation, LLVM/LLVM-MinGW, FFmpeg, Khronos, GPUOpen e SDL | Runtime .NET/WPF, Python, compiladores, codecs, headers Vulkan/SPIR-V, VMA e controles; avisos e fontes correspondentes preservados |
| Akyno e colaboradores/testadores | Direção da adaptação, identidade visual AkynoLeyend e relatos em AMD/NVIDIA que orientaram a investigação |

As mudanças locais incluem a orquestração, os controles do launcher, a migração com backup, o cache limitado de leituras capturadas, a coleta de diagnóstico e a integração dos backports. O relatório identifica o que foi incorporado e o que permanece pendente.

O jogo e as marcas Zelda pertencem aos seus respectivos titulares; esta distribuição não contém dados ou recursos do jogo. Os detalhes geométricos do launcher e o ícone desta adaptação foram desenhados para o projeto.

Os TXT de atualização anteriores e documentos de continuidade antigos estão em `historico/`. O texto histórico descreve a versão da época; o estado atual está em `../README.md` e `../docs/Relatorio-AkynoLeyend-0.4.2.md`.

`LICENSE`, `THIRD_PARTY_NOTICES.md`, avisos nos fontes e diretórios de licença das bibliotecas continuam aplicáveis conforme cada componente. O conjunto não deve ser apresentado como inteiramente original ou inteiramente MIT.
