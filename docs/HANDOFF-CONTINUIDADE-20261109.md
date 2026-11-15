# AkynoLeyend — relatório de continuidade para Claude e colaboradores

**Data:** 09/11/2026. **Base Windows entregue:** 0.4.3-test.3.
**Trabalho posterior nos fontes:** correção de extração NUP 1.
**Estado:** versão de teste; ainda sem validação física completa do jogo na RX 6600.

Este documento reúne os pedidos do usuário, alterações efetivamente presentes,
erros encontrados, evidências, arquivos e o ponto de continuação. Compilar os
fontes, validar SPIR-V e testar a orquestração não demonstram, por si, que as
cores, a vegetação, o áudio ou os FPS estejam resolvidos no jogo.

## 1. O que o usuário pediu e o que foi entregue

| Pedido | O que realmente foi colocado | Estado e limite |
|---|---|---|
| Corrigir `Lifter.after` na criação | Correção do lifter e aplicador específico para o 0.4.2, com verificação dos seis locais de oclusão | Presente nos fontes e coberto pelos testes anteriores; não remover a análise de registradores/flags associada |
| Vegetação correta | REGMAP em duas passagens, topologia de pontos/PointCoord, cadeia CAS e manutenção do workaround de oclusão | Implementado e auditado; vegetação integral ainda não confirmada fisicamente |
| AMD FSR selecionável | FSR 1 oficial AMD com passes EASU e RCAS; seleção em launcher, CLI e menu | Implementado; não é FSR 3 temporal/3.1 nem LSFG |
| FSR ativado no perfil AMD | Perfil explícito **AMD básico · Full HD + FSR** | Implementado quando o usuário escolhe o perfil; seleção automática por detectar uma GPU AMD não foi implementada |
| Full HD para PC fraco | Saída real 1920×1080 no host, patches, CLI, launcher e menu; funciona também com portátil | Implementado; exige runtime atualizado e reinício quando a saída muda |
| Melhor imagem em 2K/4K / Max Resolution | Saídas 2560×1440 e 3840×2160; escala interna separada; pools/heaps de render target crescem juntos | Implementado e conferido por âncoras; resolução/HUD/filmes/VRAM no jogo ainda precisam de teste |
| Monitor 2560×1600 | Janela/apresentação podem ocupar a tela; seletor de saída entregue oferece os modos acima | Não há comprovação de saída interna nativa 2560×1600 no seletor entregue |
| Aumentar FPS | Redução de invalidações de bindings, gerações de bancos, deduplicação de barreiras vazias, cache de samplers e fusão de cópias adjacentes | Código e fixtures presentes; nenhum ganho de FPS medido na mesma rota antes/depois |
| Compilador/cache de shaders melhor | Cobertura de mais contêineres, banco em disco, CAS, REGMAP, chave por GPU/driver, preparação e progresso | Implementado; não foram mesclados integralmente os compiladores de todos os projetos |
| Preparar shaders ao clicar Jogar | Preparação automática, progresso encaminhado ao launcher, conferência do banco e reutilização quando inalterado | Implementado; primeira preparação ainda pode demorar e pipelines inéditos podem pausar durante o jogo |
| Menu em teclado 60% | Mouse, clique, arraste de nitidez, WASD e Ctrl+M; Insert/F1 e setas continuam válidos | Implementado; a janela/menu real não foi inspecionada neste host Linux |
| Perfis AMD fraco, fluidez, equilibrado e qualidade | Quatro presets explícitos; tabela abaixo | Implementado; perfis não garantem um FPS mínimo |
| Contador de FPS | Opção no launcher e variável encaminhada ao código nativo, além do controle de menu | Implementado; visibilidade/interação precisam de confirmação no Windows |
| Atualizar build pelo launcher | Importação de ZIP, validação de hashes, staging, fechamento da GUI, instalação e reversão | Implementado para pacote local; não existe feed de atualização online configurado |
| Não recompilar tudo a cada atualização | Manutenção de hosts conhecidos com `--reuse-game-objects`; atualiza host e religa EXE | Implementado para as revisões explicitamente reconhecidas; objetos/ABI incompatíveis bloqueiam o fluxo |
| Instalação adaptada ao hardware | Jobs por RAM livre/commit/CPU e chunks novos de tamanho adaptado, preservando limites antigos | Implementado; detecção completa de ISA e fluxo PGO do novo anexo não foram integrados |
| Limpeza de arquivos/caminhos | Remoção auditada de 250 arquivos, 2.824.542 bytes; 22 comandos opcionais movidos para suporte | Concluído nos fontes; `work`, saves, objetos, licenças e headers compartilhados foram preservados |
| Cutscene travando e áudio atrasado | NV12 com conversão RGBA sob demanda, tratamento de EOS e recuperação limitada entre chamadas | Implementado no Teste 3; sincronismo no PC afetado ainda não confirmado |
| Cores corrompidas na RX 6600 | Correção CAS e ASTC→BC3 com uma camada por execução; diagnóstico e opções de comparação | Correções candidatas presentes; não há prova de que resolvam toda a imagem recebida |
| OpenGL | O backend funcional continua Vulkan | Não implementado; a opção aceita pelo parser não representa um backend OpenGL disponível |
| Novo erro de extração `.bgyml.part` | Caminhos Win32 estendidos, temporário exclusivo curto, diagnóstico, aplicador com backup/probe/reversão | Corrigido nos fontes e em pacote separado; teste real no Windows ainda necessário |

### Presets entregues

| Perfil | Saída | Escala interna | Portátil | Upscale | FPS | Geração de quadros |
|---|---|---:|---|---|---|---|
| AMD básico | 1920×1080 | 50% | Ligado | FSR 1 | Ligado | Desligada |
| Fluidez | 1920×1080 | 67% | Desligado | FSR 1 | Ligado | Desligada |
| Equilibrado | 1920×1080 | 75% | Desligado | FSR 1 | Ligado | Desligada |
| Qualidade | 1920×1080 | 100% | Desligado | FSR 1 | Ligado | Desligada |

Todos usam nitidez 10%, pacing ligado, velocidade em tempo real e cache
equilibrado. A eficácia do EASU depende de haver ampliação na apresentação;
FSR 1 a escala igual não equivale a reconstrução temporal.

## 2. Erros e evidências recebidas

### 2.1 Criação interrompida em `Lifter.after`

O 0.4.2 chamava `oot_occlusion.install(L, img)`, que acessava `lifter.after`,
ausente naquele lifter. A correção inclui armazenamento dos hooks e participação
no processamento/análise do texto emitido. Não basta criar um dicionário para
calar a exceção. Verificar `tools/reparar_lift.py`, `tests/test_lift_repair.py`,
`third_party/a64-kit/lift/a64_lift.py` e `nx2/oot_occlusion.py`.

### 2.2 RX 6600: imagem multicolorida, brilho persistente e cerca de 22–23 FPS

O `diagnosticos.zip` analisado contém oito sessões do **Teste 1**, com RX 6600
8 GB e driver AMD 26.10.1. Não são testes físicos do Teste 3.

* Uma sessão chegou a 4.633 MB usados de 7.379 MB permitidos. Não aparece estouro
  desse orçamento nem `VK_ERROR_DEVICE_LOST` nesse conjunto.
* Duas sessões chamadas diagnóstico-crash terminaram com código zero; o nome
  do arquivo não prova crash. Uma preparação foi encerrada externamente.
* Uma preparação concluiu 38.809 programas, com 177 falhas em 191 s. Seis falhas
  eram `Invalid number of arguments 3 in StorageAtomicCompareExchange32`.
* Na entrada do mapa, 338 pipelines somaram 149.625 ms de criação; houve amostra
  de 0,8 FPS durante a pausa e, depois, 23 FPS.
* Uma imagem posterior, com portátil ligado, escala 100%, FSR e nitidez 70%,
  mostra cores normais. O relato associado informa 22 FPS e dois objetos com
  brilho persistente. Não é uma comparação controlada do reparo.
* O vídeo AV1 usa Media Foundation síncrono. Os logs antigos não habilitavam o
  relógio de vídeo necessário para medir o desvio de áudio.

Não atribuir automaticamente tudo a VRAM, BC3, FSR ou NaN. Há hipóteses distintas
e a comparação deve mudar uma opção por vez.

### 2.3 Build de 2h23

O `message(1).txt` registra:

| Fase | Tempo |
|---|---:|
| Entrada/extração | 1.399,7 s |
| Lift | 293,3 s |
| Split | 3,3 s |
| Compilação/link | 6.880,7 s |
| Publicação | 8,3 s |

Foram 393 unidades, um processo, 8,4 GiB disponíveis e zero objetos aproveitados.
É um build completo, não uma atualização incremental. A recomendação fixa de
três jobs do anexo não deve ser aplicada cegamente a esse estado de memória.

### 2.4 Extração de 09/11: `FileNotFoundError` em `.bgyml.part`

O log é do **0.4.2-Candidato**, não do Teste 3. A extração do NUP de 25,02 GB
parou após 15.000 arquivos, com 548 GB livres, em:

```text
work\inputs\extract-hmlgseey\game\romfs\Event\EventSetting\EventSettingComponent\ActorStateSetting\IgnoreDissentPlayEventAndStartInterval.engineeventActorStateSetting.bgyml.part
```

O caminho completo transcrito tem **257 unidades UTF-16**. Está perto do limite
tradicional de 260, mas isso não demonstra que o ultrapassou. A mensagem também
não comprova NUP corrompido. Disponibilidade da unidade S:, acesso e eventual
remoção do diretório permanecem hipóteses se o erro persistir.

O reparo NUP 1 usa `\\?\`/UNC no I/O, mantém root e destinos na mesma forma
normalizada e grava um temporário curto `.nup-*.part` no diretório de destino.
Só renomeia após a entrada completa. O novo erro informa pai existente,
comprimento, errno/winerror e a falha original. A proteção contra traversal
permanece. Não altera EXE, DLL, objetos ou dados do NUP.

O aplicador é específico para o leitor de hash conhecido e para a extração que
falhou antes do primeiro build concluído. Recusa uma instalação com manifesto
de jogo pronto para não invalidar a identidade dos fontes sem migração.

## 3. Acertos técnicos demonstrados

* **REGMAP:** no primeiro banco, 313 colisões em 43 estágios passaram a zero;
  a regressão sintética upstream passou de 11 falhas em 89 casos para zero.
* **Cobertura de lowering:** no banco de 42.856 estágios, base e referência
  aceitaram os mesmos 42.771 e rejeitaram os mesmos 85, sem diferenças de
  status/saída de lowering. Isso não é emissão de todos os SPIR-V ou renderização.
* **CAS:** a cadeia ARM64/Maxwell→IR→SSBO→SPIR-V foi completada; o reparo posterior
  do Teste 3 preserva comparator e replacement na reescrita global→storage.
  O defeito exato foi reproduzido antes; seis módulos SPIR-V passaram depois.
* **Pontos/mesh:** topologia NVN2 1→SPIR-V 0 e PointCoord foram adaptados; os
  quatro mesh reais encontrados ainda não foram renderizados neste ambiente.
* **Census:** nos seis arquivos Shader fornecidos, a coleta produziu os mesmos
  15.504 programas e 14.726 estágios da referência para aquele subconjunto.
* **FSR:** onze grupos com os SPIR-V usados pela DLL passaram em llvmpipe,
  com validação Vulkan/sincronização e zero erros/hazards. Não houve swapchain
  real nem GPU AMD/NVIDIA física.
* **Culling/partes:** 35.313 RuntimeIds únicos das cinco partes correspondem
  aos 35.313 registros dos 51 Boxes, sem ID faltando ou extra. É cobertura dos
  dados recebidos, não validação da visibilidade no jogo.
* **Atualização:** pacote real do Teste 3 aplicado sobre staging do Teste 2,
  com SDK preservado e recibos/fontes correspondentes. A manutenção com os
  objetos reais do jogo do usuário ainda não foi executada aqui.
* **Extração NUP 1:** 25 testes passaram; o ZIP real foi aplicado ao leitor
  original exato por processo Python isolado. Inputs, objeto sentinela e save
  ficaram idênticos; backup e reversão foram verificados.

### Contagens de shader: comparação correta

O banco novo analisado tem 38.809 programas, 42.856 estágios únicos e 4.128
compute. A barra **116.427 = 38.809 × 3** corresponde às tentativas de variantes
de atributos descritas no estudo. Não significa 116.427 programas únicos.
Outras telas de progresso contam conjuntos diferentes. Aumentar o contador
não comprova qualidade, cobertura visual ou desempenho.

## 4. O que ainda não ficou resolvido ou não foi colocado

1. Ganho real de FPS/frametime na mesma rota, com logs antes/depois.
2. Vegetação completa e ausência de desaparecimento/flicker no jogo.
3. Causa completa da imagem arco-íris e dos objetos brilhando na RX 6600.
4. Sincronismo de áudio/vídeo e travas dentro de uma chamada síncrona ao decoder.
5. FSR 3/3.1 temporal, integração LSFG e SDK DLSS independentes.
6. Backend OpenGL funcional.
7. Atualização online automática do launcher/build por um feed publicado.
8. Detecção automática de GPU para selecionar o perfil AMD na primeira entrada.
9. Fluxo PGO novo do anexo, detecção completa de ISA e reescrita de instruções.
10. Inspeção da janela WPF e do menu no Windows real.
11. Extração completa do NUP de 25 GB no volume S: com o reparo novo.

O workaround de oclusão continua: os contadores atuais usam amostras sintéticas
por draw. Desligá-lo para reduzir draws pode esconder novamente a vegetação.
Não considerar esse ponto resolvido pela auditoria de arquivos de culling.

## 5. Análise dos anexos novos

### integrated / integrated(1) / integrated(2)

Os três ZIPs são idênticos:
`f4a28eaf856a9ae7d54d4779b1f3e8e3c82e2d887e62ede4645590bda23afa90`.
Não são três revisões diferentes. Há ideias úteis para fases/PGO/packaging,
mas o anexo não é uma integração pronta desta base:

* Caminho absoluto de outro PC em `PathConfig`.
* Invocação direta de `akynoleyend/cli.py -I`, sem o bootstrap de `manage.py`.
* Argumentos como `--output`, `--folder` e `--renderer-from-source` divergem de
  `--out` e `--renderer-source` da CLI atual.
* Jobs calculados por RAM total e teto de CPU aumentado para NVMe.
* CPUID incompleto e inferências de ISA por nomes/banco de modelos.
* Reescrita ISA é placeholder que gera cabeçalho com zero entradas.
* CMake espera SDL3 e dependências/árvores não incluídas; o runtime usa SDL2.
* Filtragem de patches por título/build ainda é futura no módulo recebido.

Não foram ativados automaticamente esses scripts, PGO ou patches do anexo.
O backend herdado já contém um caminho técnico `RX_PGO` para código quente;
isso não equivale a ter entregue o novo fluxo PGO integrado e validado na GUI.

### Nova pasta.zip — catálogo Fritchii/Eden

SHA-256: `e64386d9275658826757f8308ee711eae96f920cddf007cc544a922f08f82868`.
Há dez categorias: thread split, cache assíncrono, submissão/draw, framegen,
queries/fences, scheduler, compilador de shaders, host shaders, utilitários e
documentação. Não foi incorporada a árvore inteira ao runtime.

O compilador tem parentesco com a base Eden ativa: 19 arquivos com correspondência
única são iguais após normalizar CRLF, e 20 diferem. **O `ReplaceAtomic` recebido
ainda usa três argumentos**, reintroduzindo o defeito CAS que o Teste 3 corrigiu
naquele caminho. Não sobrescrever o passe atual pelo arquivo do catálogo.

O upscale temporal em `vk_fsr3_upscaler.cpp` exige profundidade, vetores de
movimento, jitter e reset. Onze headers SPIR-V gerados e os fontes desses passes
não vieram no catálogo. LSFG depende de `lsfg_shaders.h`, também ausente.
`dlss_network_probe.comp` mede a saúde da rede do próprio jogo; não é o SDK DLSS.
O componente chamado `fsr3_frame_gen` implementa optical flow/interpolação
bilateral; o nome sozinho não prova equivalência ao SDK de framegen da AMD.

O relatório `docs/ANALISE-ANEXOS-20261109.md` detalha a avaliação por categoria.

## 6. Arquivos para continuar

### Pacote de continuidade

`AkynoLeyend-Handoff-Claude-Amigo-20261109.zip` reúne:

| Pasta/arquivo | Conteúdo |
|---|---|
| `LEIA-PRIMEIRO.md` | Este relatório completo |
| `fontes/AkynoLeyend-0.4.3-work/` | Fontes atuais, com correção NUP 1; sem SDKs/dados do jogo |
| `fontes/CHECKPOINT-NAO-E-RELEASE.json` | Estado estruturado, limites e identidades |
| `verification/` | Registros anteriores e provas da correção NUP |
| `windows/AkynoLeyend-0.4.3-Teste-3-Atualizacao.zip` | Pacote de teste já entregue, com GUI/DLL; sem SDKs |
| `windows/AkynoLeyend-Correcao-Extracao-1.zip` | Aplicador pequeno para a falha de primeira extração |
| `referencias/integrated.zip` | Uma cópia dos três anexos idênticos |
| `referencias/Nova-pasta-Fritchii.zip` | Catálogo recebido, sem alteração de conteúdo |
| `relatorios/` | Análise dos anexos, RX 6600 e notas do reparo |
| `INVENTARIO-SHA256.json` | Inventário e hashes dos arquivos do pacote |

Os fontes estão mais adiantados no extrator que os ZIPs imutáveis do Teste 3.
**Não sobrepor toda a árvore de desenvolvimento a um jogo pronto e esperar
que a identidade continue igual.** O reparo pequeno atende a extração falhada;
uma próxima release deve receber versão/identidades e migração compatível próprias.

### Downloads já existentes

* [Teste 3 completo para Windows, com SDKs](https://chatgpt.com/library?file_id=libfile_56c5c3e6c5708191ab087ca8a1fda3a9&account_id=personal).
* [Teste 3 de atualização](https://chatgpt.com/library?file_id=libfile_0937a0915a5c81918acf8d1e6ff3bb95&account_id=personal).
* [Checkpoint de fontes atualizado](https://chatgpt.com/library?file_id=libfile_903d840fba808191bfd2e289b1524d66&account_id=personal).

Para o Claude e o amigo, encaminhar o ZIP de continuidade. Para instalação sem
SDKs existentes, baixar também o pacote Windows completo. A árvore de fontes
isolada não é um instalador.

### Onde estão as mudanças

| Área | Arquivos principais |
|---|---|
| Entrada/extração | `nx2/nup.py`, `akynoleyend/build.py`, `tools/reparar_extracao.py`, `tests/test_nup*.py` |
| Lifter/oclusão | `third_party/a64-kit/lift/a64_lift.py`, `nx2/oot_occlusion.py`, `tools/reparar_lift.py` |
| CAS/IR | `gpu/vk/eden/shader_recompiler/ir_opt/global_memory_to_storage_buffer_pass.cpp` e cadeia frontend/IR/SPIR-V associada |
| Texturas | `gpu/vk/vk_texture.cpp` |
| Vídeo | `host/nn_video.c` |
| Saída/Full HD | `host/nn_applet.c`, patches de saída no lifter e opções gráficas |
| Menu/mouse | `gpu/vk/vk_menu.cpp`, `gpu/vk/menu_pointer.h`, `host/display.c` |
| Shaders/progresso | `akynoleyend/shader_prepare.py`, `gpu/vk/vk_main.cpp`, `vk_shader.cpp`, `vk_draw.cpp` |
| Hardware/jobs | `akynoleyend/hardware.py`, `config.py`, `nx2/build.py` |
| Atualização | `akynoleyend/maintenance.py`, `updater.py`, `coherence.py`, `build_support.py`, `nx2/build.py` |
| GUI | `builder/AkynoLeyendBuilder/`, `builder/RunnerChecks/` |
| Empacotamento/identidade | `akynoleyend/release.py`, `prebuilt.py`, `builder/launcher-build.json`, `ferramentas/prebuilt/renderer.json` na distribuição |
| Auditoria/limpeza | `docs/limpeza-043.json`, `docs/origem.md`, `patches/` e `verification/` |

### Entradas recebidas e disponibilidade

As referências `integrated(2).zip` e `Nova pasta.zip` estão incluídas no pacote.
As identidades dos dados examinados anteriormente estão nos JSONs de verificação:

* `new-input-identities043.json`: logs Hookshot, Shader, Pack, banco privado,
  ExeFS, TableParam, AnimationEvent, Boxes e cinco partes de RuntimeId.
* `input-identities-test2.json`: optimizer e referências daquela etapa.
* `input-identities-test3.json`: `diagnosticos.zip`, `message(1).txt` e capturas.

Os RuntimeIds já foram reunidos e comparados com os Boxes; as partes substituíram
os arquivos grandes antigos para essa análise. Não há motivo para pedir de novo
o mesmo RuntimeId só por ter sido dividido.

O NUP completo, ExeFS, shaders privados, código C gerado, objetos do jogo e saves
não fazem parte do pacote de fontes/continuidade. Ficam no PC do usuário. Os
arquivos antigos recebidos por links Discord não foram novamente baixados nesta
rodada; o acesso atual a cada URL antigo não foi comprovado.

Há entradas posteriores que **não foram usadas como validação concluída deste
checkpoint** e precisam ser revistas antes de novas conclusões:

* [diagnosticos (1).zip](https://chatgpt.com/library?file_id=libfile_ed09127109608191b675c521d831024d&account_id=personal).
* [Desktop 2026.11.09 - 15.27.02.04.mp4](https://chatgpt.com/library?file_id=libfile_e2f0d3a0cbd88191a8833ccce058c1d0&account_id=personal).

Não afirmar que esses dois arquivos foram integralmente analisados por conterem
nome semelhante a entradas antigas.

## 7. Validação e identidades

| Verificação | Resultado | O que não prova |
|---|---|---|
| Suite completa Teste 3 | 205 descobertos: 196 passaram, 9 omitidos, 0 falhas | Os nove casos dependentes não foram executados |
| Runner C# | 12 checks passaram | Janela WPF não executada/inspecionada |
| DLL Vulkan Windows | 182 unidades compiladas e link concluído | Sem jogo/driver físico |
| Host alterado Teste 3 | `nn_video.c`, `nn_applet.c`, `display.c` compilaram | Headers auxiliares sintéticos; não foi ligado o EXE completo do jogo |
| CAS | 70 unidades reais de produção, seis módulos SPIR-V validados | Sem execução GPU desses módulos |
| FSR | 11 grupos em Vulkan por software, zero erros/hazards | Sem imagem no jogo/monitor físico |
| Atualização | Staging real Teste 2→3 e testes de reversão | Manutenção com objetos reais do usuário ainda pendente |
| NUP 1 | 25 testes dirigidos passaram; ZIP real aplicado por CLI Python isolada | Host Linux; CMD/Win32/NUP completo do usuário ainda não executados |

Os 25 testes dirigidos se sobrepõem a testes da suite anterior; não somar os
números como se fossem todos casos diferentes de uma nova suite completa.

| Artefato | SHA-256 |
|---|---|
| Teste 3 Atualização, 78.314.101 bytes | `e17847242c618a76c5071bf64550d2c99e012dc575a5b8cd29afd361935137d9` |
| Teste 3 Windows, 204.097.358 bytes | `34a5ee377cc81bab6c771eab9f2c81b82a3dfdac4c04f0cac6d2e1eced038d9e` |
| Builder Teste 3 | `52cb8154358cd39b47cf1f0166dc6842234cbb893dea0e4e51668cd0d5407f10` |
| DLL Teste 3 | `cdb5306d7ac90524c0d9295aa09892e756991920220cde1951776d85a1d202bc` |
| Leitor NUP original, normalizado LF | `aabc240ecde5084ddba80c53a49b55a871be188cf31c03d3c5bf1a8b82b650a1` |
| Leitor NUP corrigido 1, normalizado LF | `c1b9fb6f9bb6a6548d77d7a773a36fc852a37b40ba3c5285d27a1d8bcaef4374` |

O cache stamp de shader do Teste 3 é `ad137a62c8c44901`; o Teste 1/2 usava
`48efaca57aa305ab`. A correção do CAS mudou o tradutor; por isso uma preparação
nova é esperada uma vez. O reparo de extração NUP não altera shaders ou a DLL.

Registros mais importantes: `docs/validacao-teste-0.4.3-test3.json`,
`tests-final-test3.log`, `runner-test3.log`, `native-renderer-test3.log`,
`real-package-update-smoke-test3.json` e `extraction-hotfix/validation.json`.
Documentos de versões anteriores são históricos; seus totais não substituem os
registros específicos do Teste 3/reparo atual.

## 8. Continuação sem perder o build

### Regras de preservação

* Manter a pasta `work` inteira: `inputs`, `sa/gen`, `sa/build`, `sa/image`,
  helpers, limites/chunks, logs e `build-request.json`.
* Manter a pasta `jogo`, saves, opções e SDKs locais.
* Não mover/renomear essas pastas sem revisar os caminhos absolutos dos manifestos.
* Não alterar chunks, flags, `-march` ou otimização em um reparo que pretende
  reutilizar os mesmos objetos; a chave do cache considera a configuração.
* Não editar C gerado à mão nem apagar shader caches para tentar melhorar FPS
  sem uma mudança de tradutor/driver que justifique a invalidação.

### Instalação que falhou na extração

Fechar jogo/Builder, extrair o reparo pequeno na pasta do Builder e executar
`Corrigir-Extracao.cmd`. Aguardar `CORRECAO CONFIRMADA` e repetir Criar com a mesma
entrada/destino. Não é necessário apagar `work`. A extração anterior pode ter
perdido seu staging temporário; não prometer retomada exata do arquivo 15.001.
Se for instalar as funções novas do Teste 3, usar essa versão antes do primeiro
build bem-sucedido, evitando compilar primeiro uma versão antiga sem as funções.

### Quem já tem Teste 1 ou 2 compilado

Usar o ZIP de atualização do Teste 3 dentro da instalação existente e executar
`suporte/Atualizar-AkynoLeyend.cmd`. O processo exige fontes/ABI reconhecidos e
objetos válidos. Não repete extração/lift e não inicia uma recompilação completa
silenciosa quando faltam objetos. Ao jogar, shaders são preparados automaticamente.

### Atenção para a próxima release

`coherence.py` reconhece explicitamente fontes dos Testes 1 e 2. O Teste 3 já
pronto não é uma origem genericamente autorizada para quaisquer fontes futuros.
Ao criar a próxima versão, adicionar a origem Teste 3 auditada e conferir os
dois fingerprints de ordenação de paths, mantendo a checagem de ABI/objetos.
Não remover a conferência de identidade para fazer a atualização passar.

Fingerprints dos fontes publicados do Teste 3:

```text
POSIX:   6c67d2ebcd8918a39253aacaf9421cb36661076a814e787847c5ec42ae886384
Windows: 9b71fcc98444139a9c1388ca6d575ef5fa8cd1083693a450142e2a09b40c1e7a
HOST_REVISION: directory304-early-texels-regmap759-output849-v2
```

### Comandos corretos da base

Executar na pasta que contém `manage.py`, usando o Python incluído:

```powershell
.\ferramentas\python\python.exe -I -X utf8 .\manage.py hardware
.\ferramentas\python\python.exe -I -X utf8 .\manage.py doctor
.\ferramentas\python\python.exe -I -X utf8 .\manage.py maintain-build --out .\jogo --work .\work --tools .\ferramentas
.\ferramentas\python\python.exe -I -X utf8 .\manage.py prepare-shaders --out .\jogo --work .\work
```

O comando de manutenção só se aplica aos builds compatíveis reconhecidos. A
preparação explícita fica disponível para diagnóstico; o Jogar já a faz.
Para desenvolver, os testes principais são:

```text
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_nup*.py" -v
dotnet run --project builder/RunnerChecks/RunnerChecks.csproj -c Release
python tools/test_fsr_present.py
```

O teste FSR requer loader/headers Vulkan e dispositivo compatível, inclusive ICD
por software. Os SDKs usados anteriormente foram .NET 8.0.427, LLVM-MinGW
20261020 e SPIRV-Tools 2025.1. Não há um comando de compilação ainda rodando aqui.
O próximo passo concreto é o teste Windows do reparo e, depois, a comparação física.

## 9. Prioridade para Claude e amigo

1. Aplicar/provar a correção de extração no PC afetado; guardar
   `work/logs/reparo-extracao.json` e o novo `extract.log` se falhar.
2. Conferir a versão/identidade do pacote em teste e preservar `work` antes de
   qualquer nova manutenção. Não misturar capturas 0.4.2/Teste 1 com Teste 3.
3. Testar RX 6600 com o perfil AMD básico, cena e save fixos, geração de quadros
   desligada, medindo FPS/frametime e observando cutscene, cores e vegetação.
4. Coletar diagnóstico com trace de vídeo/áudio quando houver desvio, sem
   concluir pelo nome de um ZIP ou por uma única imagem.
5. Separar investigação de cor/textura, oclusão e pausas de pipeline. Alterar uma
   opção por comparação. Depois repetir a rota numa GPU NVIDIA.
6. Preparar próxima versão incremental com pin do Teste 3 e recibos corretos.
7. Adaptar FSR temporal/thread split/PGO em mudanças pequenas, com recursos
   faltantes, vida útil, sincronização e testes definidos antes de alegar ganho.

## 10. Origem/licenças e cuidados técnicos

A base usa Hookshot e Eden, com avisos preservados. Referência Hookshot 2.0.10:
commit `7f9daf06d902588476102d6650c600bb84f02ce5`, GPL-3.0. FSR 1 usa os headers
AMD MIT do commit `a21ffb8f6c13233ba336352bdff293894c706575`.
Nenhuma adição reservada do NX2navi foi copiada. O catálogo recebido mantém avisos
GPL-3.0-or-later. O arquivo `docs/origem.md` registra os portes locais.

O write-back diff e a apresentação em fila separada da referência não foram
ligados como otimização geral: havia regressões NVIDIA e a referência posterior
desligou a opção por padrão. Não ativar indiscriminadamente para prometer os 25%
de uma nota de release de outro hardware/rota.

**Mensagem para a próxima IA:** continue destes fontes e provas, preserve os
dados locais, trate as medições físicas como pendentes e não considere uma
feature pronta só pelo nome do arquivo ou pelo sucesso da compilação.
