# AkynoLeyend — continuidade de controles e write-back, 10/11/2026

Checkpoint `controls-wbdiff-20261110`, NÃO lançado. Base: Windows 0.4.3 Teste 3.
A versão histórica dos fontes/Builder continua Teste 3; nenhum instalador novo foi produzido.
Este documento substitui as tarefas de medição/implementação anteriores que já foram concluídas.
ChatGPT/Codex coordena; as instruções abaixo são para continuar localmente no Claude.

## 1. Resultado entregue em código

| Pedido | Estado real | Arquivos principais |
|---|---|---|
| Aba Atualizações com prévia de novidades/correções | Implementada e WPF compilado; falta validar janela Windows e empacotar release | `MainWindow.xaml/.cs`, `UpdatePreview.cs`, `akynoleyend/updater.py` |
| Reuso em pasta candidata independente | Implementado com prova de C/headers/flags/chave e origem somente leitura; teste real pendente | `akynoleyend/object_reuse.py`, `maintenance.py`, `nx2/build.py` |
| Ícones Auto/Switch/Xbox/PS4/PS5/Steam Deck | Implementados; falta validar arte do dump e menu no jogo Windows | `host/prompts.c`, `prompt_face.h`, `nx2/prompt_assets.py`, `prompt_faces.py`, `prompt_draw.py` |
| Ícones seguem remapeamento real | Implementado para botões de gamepad; fontes, texturas e layouts gerados do RomFS local | `host/control_bindings.c`, `nn_hid.c`, `pad_sdl.c`, `gpu/vk/control_editor.h` |
| Editor por mouse/teclado | Implementado na página Controls: preset Nintendo/Xbox, ação, gamepad, duas teclas/mouse | `gpu/vk/vk_menu.cpp` |
| Prioridade de ButtonPrompts mod | Implementado; arquivo de mod prevalece sobre o gerado. Uma ResourceSizeTable de mod impede substituição da fonte que poderia excedê-la | `host/mods.c`, `prompts.c`, remoção dos stubs em `mkw_glue.c` |
| Preparação de ícones ao Jogar | Implementada, com cache próprio, geração em staging e publicação/rollback. Sem download no Jogar. Falta validar o SDK Windows | `akynoleyend/prompts.py`, `launch.py` |
| Redução do write-back | Port diferencial implementado, experimental: `RX_VK_WB_DIFF=1`; desligado por padrão | `gpu/vk/vk_memory.cpp`, `shaders/wb_diff.comp`, `wb_diff_split.h` |
| Cronômetros por draw e carimbo GPU_PROFILE | Já implementados no checkpoint anterior; preservados | `vk_internal.h`, `vk_shader.cpp` |
| FSR 1 EASU/RCAS | Existente, preservado; NÃO é FSR 3 | shaders/headers FSR 1 e apresentação |
| FSR temporal e AMD Frame Generation | Não integrados. T05 abaixo define a integração e o que falta | referência Hookshot + SDK oficial |
| GPU recorder/thread split | Não transplantado. O catálogo recebido não é plugável no replay NVN | T06 abaixo |

### Uso do editor

Ctrl+M, Insert ou F1 abrem o menu. Graphics → Controls, ou Tab, muda de página.
Mouse e WASD/setas navegam; Enter/click inicia captura. Solte o botão que abriu a
captura antes de atribuí-lo. Esc cancela, Delete remove; perder foco cancela.
O preset altera botões de gamepad, preservando teclas. Uma tecla atribuída é retirada
da ação anterior. Botões duplicados são trocados, para preservar a outra ação.
Configuração em `jogo/AkynoLeyend_opts.ini`, escrita por temporário e substituição
atômica. Teclas funcionam imediatamente; a arte lida pelo jogo pode exigir reinício.
Auto usa o nome do controle SDL, com fallback XInput. Sem assets completos, o menu
indica `(original)` e o jogo usa os ícones originais. Não mostra um estilo como ativo
se o host ainda não preparou a arte.

Os assets vêm do dump do próprio usuário, não estão neste pacote. Kenney Input
Prompts é CC0 e suas três fontes/licença estão nos fontes. O gerador requer as
versões de `nx2/prompt_requirements.txt`, além de numpy e zstandard já existentes.
O pacote de continuidade inclui wheels Windows CPython 3.14 x64 para as cinco
novas dependências. Download/compatibilidade de tags foi conferido; importação
nativa dessas DLLs no Windows ainda não. Não executar pip automaticamente no Jogar.

### ABI e atualização incremental

**EXE do jogo e DLL precisam ser atualizados juntos.** A API do renderer passou
1→2, com quatro callbacks de bindings/controle no fim da tabela. Não é a API 11
da referência Hookshot, que tem outros recursos não incorporados.

Não mudamos o ABI do código traduzido, gerador de instruções, flags nem compilador.
Os objetos `code_*` existentes devem ser aproveitados sem mudar a semântica; host precisa recompilar e o
EXE precisa de link, além do renderer. `--reuse-game-objects` permanece obrigatório
na manutenção: ausência/incompatibilidade de um objeto interrompe a tarefa, em vez
de disparar uma compilação completa. Não troque o compilador do SDK da instalação.

O novo registro exato de compatibilidade conserva o stamp `4cdbb0029868040b` do
checkpoint de fontes v7. Só `vk_api.h` mudou entre os inputs dessa identidade: enum
E callbacks de controles. Eden/Sirit/compat, formatos de programas e tradução são
idênticos ao checkpoint v7; write-back usa SPIR-V interno independente. Isso NÃO
promete manter o cache do Teste 3 instalado: os backports de tradução anteriores
podem exigir uma preparação única. Nunca force um stamp arbitrário para evitar isso.

## 2. O que o perfil demonstra e o que não demonstra

O retorno T02 novo foi lido. RTX 5070 Ti Laptop / Core Ultra 9 275HX, NÃO RX 6600.
Em cenas de 1.100–1.400 draws, write-back normal: 30,1 FPS; desligado: 58,8 FPS.
Em 2.800–3.000: 24,6 e 40,7 FPS. A imagem amarela torna `NO_WRITEBACK` impróprio
como correção. Não tratamos 58 FPS como ganho medido desta implementação, nem
como teto de uma correção correta: o diagnóstico também mudou dependências/overlap.

O port usa o caminho diferencial do Hookshot 2.0.14. Um shadow de VRAM acompanha
as páginas conhecidas. O compute compara mirror/shadow e publica os blocos alterados
na RAM e no shadow. Escritas CPU coletadas, páginas capturadas, writes explícitos e
palavras CPU-owned invalidam o shadow correspondente. Mantidos cortes de palavras
CPU-owned, publicação por submissão, barriers, valores de timeline e herança de pools.
Submissões com pools aposentados/aliases mantêm todas as cópias completas na ordem
original e invalidam os shadows dos trechos; shadows aposentados só são destruídos após
a conclusão do GPU. Uma alocação/tabela/capacidade indisponível recua para cópia completa.

Limite de shadow: 1/8 do orçamento de VRAM, no máximo 512 MiB; pressão de memória
impede novos shadows e pode devolvê-los. `RX_VK_WB_SHADOW_MB` pode reduzir o teto
(0–512). O contador de bytes compara volume elegível, não mede bytes realmente
transferidos pelo shader; não usar esse número como tráfego PCIe efetivo.

Não aplicamos cópia só no fim do quadro nem excluímos buffers de vídeo por suposição.
O CPU traduzido lê RAM diretamente; a declaração de invalidação não prova capturar
todas essas leituras. Cor, vídeo, água, partículas e leitura no meio do quadro devem
ser conferidos antes de habilitar a otimização por padrão.

## 3. Validação e limites

A validação final está em `validacao/controles-wb/` do pacote de continuidade e em
`CHECKPOINT-NAO-E-RELEASE.json` do ZIP de fontes. 255 testes: 246 passaram, nove omitidos; 13 verificações C# Runner passaram e WPF
compilou com zero avisos/erros (.NET SDK 8.0.427). A suite executa código de produção:
remapeamento XInput/SDL físico, presets, captura por bordas, classificação de faces,
fontes CFF sintéticas nos cinco estilos, cmap customizado R3, prioridade de mods,
cache incompleto/externo, geração interrompida e fila limitada de páginas dirty.
O renderer Windows x64 foi compilado/ligado, e nove unidades host foram compiladas
com os headers gerados originais. Não houve link do EXE completo: os objetos privados
do jogo não estão neste ambiente. Não houve WPF, jogo, GPU física ou áudio físico.
Nenhum resultado do teste do usuário é atribuído à DLL candidata sem executá-la lá.

## 4. Instrução para Claude — T03/T04 no Windows

**Modelo: Opus 5.5, esforço Alto**, para preparar/validar a atualização de host,
controles e SDK. **Fable 5.2, esforço Alto**, para a revisão de sincronização e A/B
do write-back. Usar os nomes disponíveis na conta do usuário; não exigir troca de
modelo no meio de uma coleta que já está em andamento.

Ação autorizada pelo usuário: continuar código e testes numa cópia isolada.
Não pedir novamente aprovação para esses passos rotineiros. Não publicar uma release
nem trocar a instalação estável antes do retorno com evidência.

1. Ler este documento e os quatro arquivos T02 novos de `evidencias/`. Não repetir
   a investigação já feita. Não repetir alternância de GPU_PROFILE nem o teste
   `NO_WRITEBACK`, que já mostrou imagem errada. O cache instalado voltou ao normal.
2. Conferir a raiz atual por leitura. A última raiz confirmada/restaurada foi
   `C:\Users\mayco\Downloads\AkynoLeyend-0.4.3-Teste-1-Windows\AkynoLeyend-0.4.3-Teste-1`.
   Os nomes são históricos: a instalação é Teste 3 completo. O último comando de
   build terminou; não há uma compilação interrompida a retomar.
3. Preservar instalação estável, `work`, os 393 objetos, `objcache`, NUP, image,
   saves e SDK/compilador. Não Criar, clean, reinstalar, mudar flags ou mover a raiz.
4. Extrair os fontes num diretório novo e curto. Criar uma área candidata independente
   para jogo/work. Copiar apenas a árvore gerada, objetos/stamps e metadados necessários
   à manutenção; reutilizar RomFS como ENTRADA somente leitura, sem extrair/copiar
   novamente os 26 GB. Nada de hardlinks graváveis de objetos/saves/cache para a estável.
   Se o espaço não comportar a cópia independente dos arquivos necessários, informar
   bytes e opções concretas antes de alterar o original.
5. O problema de caminhos `-I` nas chaves foi tratado com `--reuse-game-from <raiz-estavel>`.
   O modo foi implementado e testado: somente jobs traduzidos da candidata, C e
   closure de headers iguais, compilador/flags/deps incluídos na chave exata antiga.
   Os includes antigos ficam nos jobs de REUSO; os arquivos antigos só são lidos.
   Objetos são copiados por temporário para arquivos independentes da candidata;
   links com o objeto original são recusados. Host usa fontes/headers novos. A
   guarda `--reuse-game-objects` continua obrigatória. Conferir o primeiro objeto
   real e os logs antes de prosseguir. O modo espera a instalação anterior em
   `<raiz-estavel>/jogo` e `<raiz-estavel>/work`; para outro layout, parar e registrar
   os caminhos, sem contornar a prova. Não é necessário reescrever o adaptador.

6. Copiar os saves para a candidata. Rebasing de `build-request.json`, output e caminhos
   só nos JSONs da candidata, conferindo hash da image e build id. O SDK original pode
   ser usado para compilar em leitura. Para os ícones, testar as dependências em cópia
   do Python do SDK, ou em outro Python compatível, sem substituir o compilador.
   Wheels estão em `sdk-wheels/windows-cp314/`. Confirmar versão/arquitetura real antes
   de instalar. Testar `import fontTools,PIL,astc_encoder,texture2ddecoder,archspec` com
   o mesmo Python que o launcher usa. Manter licenças e dist-info ao empacotar.
7. Executar, com o Python do SDK, os testes e `manage.py maintain-build --out <jogo-candidato>
   --work <work-candidato> --tools <SDK-existente> --reuse-game-from <raiz-estavel>`. Conferir a CLI real antes de compor
   o comando. O plano e os objetos precisam corresponder. Se a verificação de cache
   recusar, registrar a primeira chave divergente; não remover a guarda, não editar
   código C gerado e não iniciar o pipeline de extração/lift para contornar a recusa.
8. Confirmar zero recompilações de unidades traduzidas, contar host/renderer recompilados,
   conferir EXE+DLL novos/API 2, metadados `controller-prompts-v1` e hashes. Build deve
   conservar saves e excluir recursos gerados pelo usuário do pacote público.
9. Abrir a candidata com write-back COMPLETO, mesmo save/local/configuração. Validar
   menu em 720p/1080p/1440p/4K, mouse/WASD/Ctrl+M/Tab, captura/cancelamento/foco,
   persistência e o seu GameSir G7 Pro/XInput. Testar pelo menos um remapeamento real
   com seu ícone em diálogo/ocarina/menu. Faces manuais restantes podem ser validadas
   com o mesmo controle; Auto por hardware só declarar para os dispositivos disponíveis.
10. Comparar candidata completa → diferencial → completa com os mesmos binários,
   driver, modo de energia, resolução, foco, framegen desligado e cache aquecido.
   Única variável entre rodadas: `RX_VK_WB_DIFF=0` / `1`. Reconstruir cada ambiente
   do mesmo baseline; não acumular flags. O launcher limpa variáveis RX_* herdadas:
   se testar diretamente, derive o comando/ambiente do registro normal e acrescente
   a variável apenas no processo filho. Não prometer que setá-la no PowerShell afeta Jogar.
11. Coletar 60 s parado e 60 s andando no mesmo local por rodada, com faixa de draws,
    mediana/p95/p99 de frametime, tempo GPU, VRAM e contadores de refill/shadow.
    Verificar imagem normal, água, cutscene/áudio, transição de área e ausência de
    flashes/crash. RenderDoc/WPR/VS não são necessários para esta primeira validação.
    Para partes de jogo que exigem ação do usuário, abrir e entregar instrução curta.
12. Se houver amarelo, flicker, corrupt texture ou crash: voltar somente na candidata
    a `RX_VK_WB_DIFF=0`, conservar logs/mapa, localizar a primeira divergência. Não
    alterar NaN/barriers/async ao mesmo tempo para mascarar o resultado.
13. Devolver um ZIP pequeno de logs, hashes, diff final e relatório de 8 pontos:
    tarefa/modelo, resultado, arquivos, comandos, preservado/impacto, como aplicar,
    o que excluir, pendências/próximo passo. Separar claramente testes físicos dos
    sintéticos. O teste atual autoriza medir, não declarar que todas as GPUs funcionam.

## 5. Instrução para Claude — T05 AMD FSR temporal e Frame Generation

**Modelo: Fable 5.2, esforço Alto.** Começar DEPOIS de devolver o A/B do write-back.
O pedido está autorizado, mas esta tarefa ainda não foi implementada neste checkpoint.

Correções da tabela enviada:
- FSR 1 espacial EASU/RCAS não tem versão 3.1.6. Upscale temporal precisa de novas entradas.
- Não é obrigatório instalar FSR 2 primeiro para integrar FSR 3.1.
- FSR 3.1 desacopla Frame Generation do upscaler; FG pode usar outro upscaler.
- No SDK 2.4 atual, Upscaling 4.1.2 também suporta RX 6000; FG 4 exige RX 9000,
  com fallback analítico 3.x. Verificar as capacidades Vulkan reais e o driver do PC.
- Os MB adicionais dependem da versão, resolução e recursos/contextos. Não tratar
  124/214/457 MB como orçamento total fixo de toda a integração.

Referências oficiais conferidas em 10/11/2026:
- Repositório solicitado: https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK
- Tag v2.4.0: `7539ae8b6568ad29ed78a753404351daf3b5cca7` (git ls-remote).
- https://gpuopen.com/learn/amd-fsr-sdk-2-4-rx-6000-ryzen-apus/
- https://gpuopen.com/manuals/fsr_sdk/techniques/super-resolution-upscaler/
- https://gpuopen.com/manuals/fsr_sdk/techniques/frame-interpolation-swap-chain/

A referência local `referencias/Hookshot-2.0.14.zip` contém um caminho funcional de
FSR 3.1.4 a partir dos shaders MIT do SDK 1.1.4. NÃO anunciá-lo como SDK 2.4 ou FSR4.
Ela fornece um exemplo de adaptação ao jogo, não uma atualização automática do nosso
renderer: tem API/estado diferentes e movimento de câmera sem todos os vetores de atores.

Inventário concreto para estudar:
| Ponto | Referência Hookshot | Adaptação necessária nesta base |
|---|---|---|
| Jitter em 3 cargas de projeção de OoT 1.1.1 | `nx2/oot_jitter.py`, `host/rx_backend.c`, `gpu/vk/dlss_math.h` | Hooks ausentes no EXE atual. Confirmar palavras originais e implementar no gerador; não escrever C gerado à mão. Quantificar chunks alterados antes de relift/rebuild. |
| Cor/depth/motion e câmera | `vk_fsr3_inputs.cpp/.h`, `shaders/fsr3_prep.comp`, `fsr3_math.h` | Ligar draws e dispatches certos, leitura capturada da câmera, orientação/escala/profundidade reversa, reset e validade por frame. Não usar alvo de sombra, HUD ou reflexo como cena principal. |
| Upscale | `vk_fsr3.cpp/.h`, `scripts/fsr3_shaders.py`, `third_party/fidelityfx-sdk` | Se usar API SDK 2.4, integrar contexto Vulkan/runtime/recursos corretos. Se usar fonte 1.1.4, identificar versão honestamente. Evitar SDK/headers sem ligação ao frame. |
| FG | `vk_fsr3fi.cpp/.h`, optical flow/fi SPIR-V | Integrar apresentação, fences/semaphores, HUD fora do optical flow, timestamps, resize/minimize/foco e fallback sem FG. O FG antigo do nosso menu não deve ser renomeado para AMD FG. |
| UI/caps | `upscaler_rows.h`, `vk_menu.cpp` e opções host da referência | Só mostrar opção habilitada com backend/entradas válidos, explicar fallback. FSR 1 continua disponível. |

Primeira entrega T05: identificar e validar no jogo as entradas temporais, tamanhos
reais e pontos de reset, com um diff pequeno. Depois integrar/medir upscale; só então
FG. Câmera estática, giro, Link andando, água/transparências, Navi, sombras, mudança
1080p↔1440p, área nova, cutscene, menu e retomada de foco precisam de teste. FSR4/FG4
não substituem o trabalho de extrair essas entradas. Não prometer 60 FPS com base em
requisitos de hardware. Para RX 6600, solicitar apenas log/manifesto e teste dessa
candidata: os arquivos T02 atuais são exclusivamente do notebook NVIDIA.

## 6. GPU Thread Split: por que não foi copiado e como continuar

**Modelo: Fable 5.2, esforço Alto**, após medir o caminho restante.
`Nova pasta/01_GPU_Thread_Split` tem `gpu_split.h`, `puller.cpp/.h` e notas para os
engines Maxwell/GPFIFO de um emulador. O nosso fluxo é gravação NVN nativa em
`host/nvn_native.c` → replay em `gpu/vk/vk_replay.cpp`. Essa fronteira não tem aqueles
objetos/filas. Há modos async/paralelo existentes com seus próprios riscos de dados;
não ligar por padrão nem acrescentar um SPSC sem tratar ponteiros, captures, fences,
retorno de queries, shutdown e pressão de memória. Os ganhos do catálogo são de
outro programa e não foram medidos aqui.

A pasta MIT dkb `01_Recorder_Thread/vk_rec.c/.h` citada não foi localizada entre os
arquivos locais recuperados desta sessão. Não inventar esses fontes. Primeiro
localizar no acervo do usuário; se continuar ausente, informar o nome exato necessário.
Não exigir Ghidra para portar fontes que já existem. Se a implementação depender de
um trecho apenas binário, usar o MCP local em leitura e registrar programa/hash/endereço.

## 7. Empacotar como atualização do launcher

**Modelo: Opus 5.5 / Alto.** O usuário pediu uma aba Atualizações ao lado de
Gráficos/Ferramentas e quer ver claramente novidades e correções. Isso já está
implementado no WPF. Não entregar outro conjunto de arquivos para troca manual.

- O atalho da Home abre a página Atualizações. As ações de atualização saíram de
  Ferramentas para essa página; shader prep e diagnóstico continuam em Ferramentas.
- Selecionar um ZIP chama stage-update e confere os arquivos. A interface então
  exibe versão e notas, sem fechar nem aplicar nada. Instalar é um clique explícito
  posterior; o updater espera o launcher fechar, atualiza/religa host+renderer e
  reabre. O rollback existente é preservado.
- O índice `update-package.json` aceita `notes` com listas `new`, `fixes`,
  `experimental`, `known_issues`. Texto simples, limites de tamanho e tipos
  conferidos. O plano preserva as notas verificadas. Pacote antigo sem notas tem
  indicação explícita; não inventa a lista. Ver `docs/notas-proxima-atualizacao.json`.
- Não anunciar FSR 3/4 ou AMD Frame Generation como concluídos nessas notas.
  Write-back é experimental/desligado; gráficos e controles têm validação física
  pendente. Notas de candidato não são promessa de desempenho medido.
- Depois dos testes, atribuir uma NOVA versão de teste coerente ao VERSION,
  __version__/projeto WPF/metadata e índice. Não republicar o Builder antigo com
  o nome de uma versão nova. Gerar Builder win-x64 self-contained e DLL/source
  metadata correspondentes; payload precisa conter todos os fontes/módulos novos.
- Empacotar as dependências de prompt com o Python do SDK validado. O atualizador
  normal protege o SDK e permite apenas ferramentas/prebuilt nessa árvore; não
  mandar um ZIP que tente sobrescrever ferramentas/python e espere que passe.
  Se for distribuir dependências privadas fora do SDK, implementar/carimbar a
  procura explícita desse diretório no gerador antes de empacotar. Não foi feita
  essa distribuição alternativa neste checkpoint.
- Entrega final desejada: UM `AkynoLeyend-Atualizacao-<versao>.zip` com índice real,
  hashes, notas e fluxo incremental. Não incluir work, saves, dump nem assets de
  prompts gerados do dump. Testar primeiro numa cópia, abrindo a versão anterior,
  selecionando ZIP, lendo as notas e aplicando. Provar zero recompilações `code_*`.
- O pacote de CONTINUIDADE anexado agora contém fontes/evidências, **não é o ZIP
  instalável**. Não selecioná-lo no launcher. A validação completa/empacotamento
  Windows ainda deve ser concluída no PC com objetos reais.

## 8. Organização e aplicação

- Este é pacote para desenvolvimento/Claude. **Não colar estes fontes sobre a instalação
  estável e não trocar apenas a DLL.** Não contém um novo Builder pronto.
- Para Claude: extrair o pacote de continuidade em uma pasta de desenvolvimento; usar
  o ZIP inteiro de fontes dentro de `fontes/`. A pasta `referencias/` é consulta, nunca
  substituir a nossa árvore por ela. Os fontes já incluem todas as mudanças anteriores.
- Ainda não excluir a instalação, `work`, SDK ou pacotes anteriores que sejam o único
  backup. A entrega mantém um único checkpoint atual e identifica os registros históricos.
- Depois de validar/publicar uma atualização compatível, aplicar apenas o pacote de
  atualização próprio via launcher sobre a instalação existente. Atualizar EXE+DLL,
  manifesto e ferramentas Python necessários, conservando `work`, saves e settings.
- Depois de conferir hashes/retorno dos testes e guardar o relatório, pode excluir a
  pasta TEMPORÁRIA da candidata, a extração das referências e os wheels soltos usados
  para preparar o SDK. Não excluir o Python/site-packages já instalado nem recursos
  gerados de prompts em uso. O ZIP atual contém instruções para reconstruir a área de teste.
