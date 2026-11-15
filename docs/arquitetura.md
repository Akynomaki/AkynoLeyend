> Desenvolvimento 0.4.3: consulte `ESTUDO-GRAFICO-20261109.md` e `validacao-grafica-043.json`. As seções abaixo registram versões anteriores.

# Organizacao da base

## AkynoLeyend 0.4.0

A orquestracao ativa agora fica em `akynoleyend/`; a GUI em `builder/AkynoLeyendBuilder`.
`graphics.py` valida controles do launcher e produz variaveis ligadas a caminhos nativos.
`legacy.py` migra o build local com backup, sem alterar instrucoes traduzidas.
O perfil Compatibilidade e os breadcrumbs limitados da CPU ajudam a comparar a falha AMD; nao comprovam sua causa.
O backend continua Vulkan. Detalhes atuais e limites em `HANDOFF-OUTRA-IA.md`.

As secoes abaixo documentam a arquitetura herdada e podem usar nomes anteriores.

## Responsabilidades

| Local | Responsabilidade |
|---|---|
| `builder/OcarinaBuilder/` | Janela WPF, selecao de entradas e acompanhamento do processo Python |
| `builder/RunnerChecks/` | Testes executaveis do transporte de processos da interface |
| `ocarina/game.py`, `ocarina/progress.py` | Identificacao de entradas e progresso observado da compilacao |
| `ocarina/config.py` | Caminhos, idioma, build suportado e politica de paralelismo |
| `ocarina/preflight.py` | Verificacao da toolchain e das dependencias locais |
| `ocarina/build.py` | Entradas, etapas de traducao/compilacao e publicacao |
| `ocarina/process.py` | Processos filhos, saida e erros por etapa |
| `ocarina/files.py` | Hashes, JSON atomico e verificacao de sobreposicao de caminhos |
| `ocarina/build_support.py` | Identidade do cache de objetos e opcoes de link |
| `ocarina/environment.py` | Perfis e ambiente efetivo dos processos filhos |
| `ocarina/launch.py` | Conferencia do build e registros de execucao |
| `ocarina/cli.py`, `manage.py` | Interface publica unica |
| `nx2/` | Pipeline ARM64 do Hookshot; o antigo make_game delega a interface nova |
| `host/` | Runtime Horizon/NVN2 do Hookshot |
| `gpu/vk/` | Renderizador, Eden e Sirit do Hookshot |
| `gpu/render/`, `gpu/third_party/` | Tipos, decodificadores e fontes herdados; o backend WebGPU nao e compilado neste pacote |
| `ferramentas/` | Ferramentas genericas e bibliotecas; nao contem codigo do jogo |
| `work/` | Entradas privadas, helpers, codigo gerado, objetos e logs de build locais |
| `jogo/` | Resultado local, saves e diagnosticos; fora da distribuicao dos fontes |

## Fluxo

O programa valida caminhos e dependencias; identifica o build da entrada; prepara uma copia privada de exefs quando necessario; executa o lifter; divide a unidade de codigo quente; compila incrementalmente; confere os arquivos obrigatorios; e publica o manifesto por ultimo.

O lancador calcula os hashes antes de abrir o programa. Se uma recompilacao foi interrompida durante a atualizacao da pasta, um conjunto misto de arquivos falha nessa conferencia. A pasta romfs e referenciada pelo caminho local registrado, sem migrar dados para os fontes.

## Limites das mudancas

A versao 0.3.2 atualiza o host e o backend Vulkan a partir de HookshotBuilder (2).zip. Inclui a sincronizacao da primeira submissao, tratamento de subgrupos de 32 lanes, fallback MMA no shader, novo limite de mirrors e ajustes visuais/videoclipes. A integracao local acrescenta workarounds de perfil Vulkan verificados no emulador fornecido, identidade de cache por GPU/driver e verificacoes de falha na criacao do caminho de upscale.

A politica herdada troca o upscale neural de determinados filmes por amostragem linear em GPUs que nao executam aquelas redes adequadamente. Isso preserva a reproducao, mas nao equivale ao upscale neural original. A neblina reduzida e um workaround visual, com causa original ainda em aberto. Consulte docs/atualizacao-amd.md.

O historico ate 0.3.2 esta em `patches/base-portabilidade.patch`; a integracao seguinte esta em `patches/0.3.3-pointer-lighting.patch`. O inventario em `upstream.json` registra os hashes do ZIP de origem e as diferencas de fontes. Nomes internos herdados (MKW, TOTK, RX, HOS) permanecem onde fazem parte das interfaces; renomea-los sem necessidade tornaria a comparacao com o original mais dificil.

## Proximas alteracoes

Corrija um problema por vez e compare a mesma cena com o perfil original. Para uma mudanca no tradutor, valide o SPIR-V e a semantica dos programas afetados; para memoria, registre budgets, uso e vida util dos recursos na timeline. Uma pipeline omitida ou um limite menor de cache nao constitui prova de renderizacao correta.

## Interface Windows

`App.xaml` concentra o tema. `MainWindow` controla selecao, etapas e a navegacao; `Runner` controla o processo filho e drena stdout/stderr em paralelo. Os argumentos passam por `ProcessStartInfo.ArgumentList`, sem montar um comando de shell. O modo UTF-8 do Python e solicitado por `-X utf8`, pois `-I` ignora variaveis PYTHON do ambiente. O Python local e localizado a partir da pasta do executavel; nao ha fallback silencioso para uma instalacao do sistema.

A checagem de origem tem debounce, timeout e identificador de tentativa. Uma resposta antiga nao habilita o botao para outra entrada. Cancelar encerra a arvore do processo; retomar usa a mesma pasta `work` e seus objetos validos. Uma mensagem `@@done` so representa sucesso quando o processo tambem terminou com codigo zero e o manifesto existe. O botao Jogar usa a CLI, incluindo hashes, perfis e caminhos do runtime.

## Integracao 0.3.3

A tabela de paginas de memoria guest e usada somente nos shaders compute e seu endereco e enviado por push constants. ocarina/power.py concentra as solicitacoes Windows de energia para o build; windows_paths.py cria o alias DOS opt-in de RomFS. crash_report.py confere o hash do executavel junto do mapa antes de coletar simbolos e preserva o diagnostico anterior ao proximo build. O fluxo normal de execucao nao ativa o alias nem o trace; Jogar-Teste-Crash.cmd ativa ambos explicitamente.

## Correcao 0.3.4

host/win_path.c concentra I/O Win32 com caminhos UTF-16 estendidos; path_join.h recusa truncamento. O filesystem guest usa esses adaptadores com capacidade explicita de 4096 bytes. host/audio_wasapi.c pertence ao thread do mixer: inicializacao/uso/liberacao COM ficam nesse thread; nn_audio.c escolhe WASAPI/waveOut e aplica volume. O lancador preserva snapshots do arquivo de opcoes, e oferece trace de audio/frames separado da validacao Vulkan. O perfil Nitido seleciona uma alternativa de renderizacao ja existente e nao altera Original.

## Cache Streaming 0.3.5

`cache_policy.h` define limites; `cache_stream.h` implementa reservas/LRU/worker; `cache_io.h` limita chamadas de arquivo; `cache_reader.h` valida registros; `cache_rate.h` controla admissao do pre-aquecimento. `vk_shader.cpp` integra o indice/reader e seleciona historico limitado. `vk_draw.cpp` limita aquecimento e snapshots de driver. `vk_jobs.cpp` usa a concorrencia explicita. `ocarina/environment.py` separa modo de cache de perfil visual; CLI/launch registram a configuracao efetiva.

`profiles/shader-cache-compatible.json` registra apenas fontes exatos auditados que preservam ABI/IR/formato. `host/nvn_native.c` limita logs de alternancia do intervalo; nao muda a decisao de pacing. O modo Original preserva o aquecimento completo; o modo Streaming e opt-in via CMD/CLI.

## Integracao 0.3.6

Merge de host/GPU de movie-sync sobre pointer-lighting-2 e depois de foliage-linux-updater, com os ajustes locais mantidos. gpu_preference.c concentra os exports para drivers de notebook; nn_video.c usa clock/PTS e descarta imagens atrasadas. A tabela de paginas agora cobre as duas janelas guest da origem, preservando flush de memoria nao coerente. Layout de push constants e chave de cache seguem as mudancas de IR, sem stamp antigo.

A ultima integracao traz folhagem/iluminacao de EvilOOT, tempo real, rumble e backoff limitado de imports de memoria. O workaround oot_visual antigo fica desligado por padrao; as imagens de referencia e o teste visual ainda pendente estao em HANDOFF-OUTRA-IA.md. O pacote Windows nao integra o atualizador oficial nem o AppImage.

ocarina/romfs.py valida somente a estrutura basica e sonda caminhos. process.py insere -X utf8 em processos Python, inclusive isolados. O paralelismo automatico e medido depois de extrair/traduzir; nx2/build.py informa processos/unidades ainda em curso. crash_report.py distingue coleta parcial de uma tentativa ainda sem encerramento/crash.

## Integracao 0.3.7

prebuilt.py verifica identidade dos fontes/dependencias/regras de build e da DLL generica. chunks.py usa 6 MiB para novos limites e preserva os existentes, inclusive um bloco unico. mirror_policy.h concentra o orcamento da classe de 12 GiB. timing.py registra fases e nx2/build.py conta acertos reais. romfs.py distingue acesso negado e ausencia; build.py recusa cache privado incompleto antes de extrair novamente.

## Complemento 0.3.8

`ocarina/access.py` separa falhas de leitura da integridade/execucao, com consultas somente de leitura. `ocarina/shader_prepare.py` publica somente uma DLL ABI-compativel e o banco privado de shaders. `gpu/vk/shader_seed.h` indexa HKSEED01 sem manter o payload inteiro em RAM. O script de distribuicao exclui tambem diagnosticos de acesso.

## Staging 0.3.8-dev.2

workspace_stage() aplica a DACL privada de windows_acl.py antes de permitir criar/copiar os arquivos. O SID do token do processo entra explicitamente com heranca; o dono elevado Administrators nao e usado como substituto do usuario. Ha tres pontos em build.py e dois em shader_prepare.py. O reparo PowerShell de arquivos existentes e separado e verifica os hashes como usuario normal depois da etapa elevada.

## Integracao 0.3.9

A tabela guest usa atualizacoes no upload command buffer em ordem com as copias dos mirrors. REPORT_COUNTER registra palavras CPU para o recorte de writebacks. O tradutor implementa cargas globais estreitas e muda o stamp. O cache de faixas de uniformes e invalidado por epoch. runtime_failure.py classifica marcadores explicitos de device lost em leituras limitadas; o replay encerra em 70. O modo preparacao termina apos salvar o cache, antes da partida. ABI publica preservada para atualizacao isolada de DLL.
