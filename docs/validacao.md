> Checkpoint 10/11/2026: 230 testes (221 passaram, nove omitidos), renderer Windows x64 com 182 unidades e host hos_thread compilados. Não houve teste físico de FPS. Ver CONTINUACAO-UPSTREAM-20261110.md.

> Desenvolvimento 0.4.3: consulte `ESTUDO-GRAFICO-20261109.md` e `validacao-grafica-043.json`. As seções abaixo registram versões anteriores.

# Validacao desta entrega

## AkynoLeyend 0.4.0

124 testes descobertos: 115 passaram, 9 omitidos neste host, zero falhas. Sete checks C# passaram.
DLL Vulkan ligada para Windows x64 a partir de 182 unidades genericas; GUI WPF publicada com runtime incluido.
Ruff passou nos modulos ativos, teste 0.4.0 e empacotador. Registro em `validacao-0.4.0.json`.
O jogo, a janela WPF e uma GPU fisica nao foram executados neste host Linux. Nao houve benchmark de FPS.
O resultado visual dos flashes e o crash AMD seguem pendentes de reproducao na maquina afetada.

As secoes abaixo sao historicas e nao equivalem a novos testes de hardware.

## Verificado neste ambiente

- Testes sinteticos do fluxo: entrada/pasta protegida, copia privada de modulos, identificacao de versao, cache de objetos, perfis, logs, publicacao e deteccao de arquivos alterados. O resultado final fica em `docs/resultado-testes.txt`.
- Compilacao de **208 unidades C/C++ para Windows x64**, incluindo o backend Vulkan e o runtime host, usando LLVM-MinGW / Clang 23.1.5, em host Linux.
- Link da DLL Vulkan completa, com bibliotecas C++ estaticas. A DLL usada na verificacao fica fora do pacote: tem uma identidade sintetica de teste, sem caches ou dados do jogo.
- Compilacao do runtime ARM64 generico com as mesmas flags LLVM usadas pelo build dos arquivos traduzidos, usando headers sinteticos.
- Compilacao e link das bibliotecas FFmpeg 8.0 para Windows x64, limitadas a VP8/VP9, avcodec, avutil e swscale.
- Compilacao e link dos helpers genericos a64emit e ZBIC para Windows x64, sem dados do jogo.
- Execucao de 7 casos do lancador real no PowerShell 7.4.6 em Linux, com ferramenta filha sintetica: caminhos com espacos, diretorio atual diferente, valores padrao, entradas em pastas, argumentos explicitos, rejeicao de combinacoes invalidas e propagacao do codigo de falha. Isso nao e um teste do Windows PowerShell 5.1.
- Analise e formatacao do Python novo com Ruff; verificacao do conteudo dos ZIPs produzidos.

## Interface 0.3.1

- Publicacao WPF para Windows x64, em executavel unico e com runtime .NET 8.0.33 incluido, pelo SDK 8.0.427. Sem alteracoes no motor grafico nesta atualizacao.
- 33 testes Python passaram: 23 do fluxo/lancador, 7 da ponte grafica e 3 regressoes da primeira gravacao/retomada dos limites de chunks. Os testes usam entradas sinteticas e nao recompilam o jogo.
- 6 checks C# passaram no host Linux: integridade das mensagens dos idiomas, localizacao das ferramentas, argumentos com espacos/acentos/metacaracteres, UTF-8 no processo Python isolado, leitura simultanea das duas saidas, rejeicao de check com codigo nao zero e cancelamento antes/durante a execucao.
- Nao foi possivel executar ou inspecionar visualmente a janela WPF neste host Linux. A publicacao verifica XAML/C#, mas nao substitui teste de interacao no Windows.
- Registros: `docs/resultado-interface.txt`, `docs/resultado-testes.txt` e `docs/resultado-runner.txt`.

## O que esses checks nao demonstram

Nao houve execucao do jogo em Windows, teste de GPU, recompilacao dos dados do jogo ou validacao de uma cena renderizada. Nao foi ligado o executavel completo do jogo, pois os modulos e dados nao foram fornecidos neste ambiente.

O teste do host usa contexto e headers sinteticos. Ele verifica compatibilidade do codigo com o alvo Windows; nao comprova que as chamadas do jogo tenham semantica correta. A cobertura historica de testes do Hookshot nao foi reproduzida aqui.

O perfil 8gb e experimental. Corrigir a interpretacao das flags e limitar categorias de alocacao nao comprova um teto para o processo inteiro nem uma correcao de device lost. O ultimo log do Ocarina, recebido antes desta base, tambem tinha uma escrita invalida na GPU, alem da pressao de memoria.

## Proximo teste no computador de destino

1. Extraia em uma pasta nova e rode `Verificar.cmd`.
2. Compile a copia local suportada, sem reaproveitar codigo gerado do Ocarina anterior.
3. Use `Jogar.cmd` e observe a imagem ate a primeira cena jogavel. Registre uma tentativa sem trocar o foco.
4. Feche e repita com `Jogar-8GB.cmd`, mantendo cena, resolucao e opcoes.
5. Reproduza a troca de foco em uma tentativa separada e anote a acao exata.
6. Preserve `execucao.json`, `saida.log` e `erros.log` juntos.

Erros novos devem ser associados ao hash do build e ao perfil registrados. Evite comparar uma captura antiga do Ocarina com um log novo do Hookshot como se fossem a mesma execucao.

## Correcao de work/image/chunks.txt

Os tres testes de tests/test_chunks.py falharam com FileNotFoundError antes da mudanca e passaram depois. Foram conferidos o diretorio compartilhado ausente, a imagem standalone preservada e a reutilizacao dos limites de codigo ja gerado. Detalhes em docs/correcao-chunks.md.

## Atualizacao split/NUP

A suite atual terminou com 51 testes, zero erros, zero falhas e zero pulos. Inclui a passagem real da orquestracao por geracao, divisao opcional, compilacao sintetica e publicacao; leitura compactada com Zstandard; e extracao/migracao por processo Python real. O registro completo substitui docs/resultado-testes.txt. Nao foi recompilado ou executado o jogo.

## Integracao 0.3.2

O teste anterior que nao fechava o EXE completo foi ampliado: 352 unidades do runtime/backend foram compiladas e tanto o host EXE sintetico quanto a DLL Vulkan fecharam o link para Windows. Nao ha codigo real de jogo nesse fixture; a verificacao nao demonstra renderizacao correta. Foi publicada a GUI WPF 0.3.2-dev.1. Detalhes em docs/atualizacao-amd.md e resultado-native-amd.txt.

A suite atual tem 52 testes: 45 passaram na execucao portatil (sete checks PowerShell omitidos nessa execucao) e os sete checks do lancador passaram separadamente com PowerShell 7.4.6. Zero falhas. Inclui o teste de invocacoes do compilador na retomada e os novos limites de paralelismo por memoria.

## Integracao 0.3.3

- 352 unidades C/C++ compilaram com LLVM-MinGW 20261020 para Windows x64. O host EXE e a DLL Vulkan fecharam o link, zero falhas. O fixture inclui runtime generico e unidades de jogo vazias; nao inclui codigo do jogo. Registro em resultado-native-0.3.3.txt.
- 63 casos descobertos: 56 passaram e sete checks de PowerShell nao foram executados por falta desse runtime neste host. Inclui oito casos de caminho curto/coleta e tres de energia. Os novos comandos CMD nao foram executados no shell Windows.
- Testado o parser de mapa com o arquivo real do link LLVM-MinGW e o ImageBase do PE produzido, alem dos formatos MSVC/GNU sinteticos.
- Teste de lancamento usa processo filho real em Linux e API DOS simulada: alias permanece durante o filho, e removido apos saida ou falha; logs entram no ZIP e saves/binarios ficam de fora. Isso nao substitui teste de DefineDosDevice no Windows.
- Nao houve execucao do jogo, validacao de SPIR-V no driver, teste fisico AMD/NVIDIA ou benchmark. O ultimo crash de CPU do usuario ainda precisa do mapa correspondente/novo log para confirmar sua causa.

## Correcao 0.3.4

- 67 testes descobertos: 60 passaram; sete de PowerShell continuaram ignorados porque esse runtime nao esta instalado neste host. Incluem o construtor C de caminhos com a raiz de 160 bytes e o arquivo de iluminacao real, rejeicao de overflow, exclusao do import de volume do gerador de stubs, perfil de movimento, snapshots de opcoes e passagem dos parametros de audio/trace para um processo filho real.
- Fixture Windows de filesystem compilado e ligado com LLVM-MinGW 20261020, C11 e -Wall -Wextra -Werror. A parte Win32 do teste cobre criar, ler, enumerar, renomear e apagar um arquivo UTF-8 em caminho maior que 260 caracteres, mas NAO foi executada neste host Linux. O trecho portavel de montagem/rejeicao de caminhos foi executado.
- Build nativo incremental com 354 unidades configuradas fechou EXE e DLL para Windows x64, zero falhas. Inclui os adaptadores Win32 e WASAPI, o HLE de volume e o registro de frames lentos. Objetos inalterados foram reutilizados. O fixture continua com headers sinteticos e unidades de jogo vazias; nao e o executavel completo do jogo. O simbolo de volume implementado foi conferido no PE ligado.
- Comparadas 244 entradas que formam a identidade do tradutor com o pacote Windows 0.3.3: stamp 234d9fba458b54ba nas duas versoes. O cache de programas nao e invalidado por essas alteracoes de host/diagnostico ou pelo perfil Nitido.
- Python validado com compileall. Registros em resultado-testes.txt e resultado-native-0.3.4.txt. O arquivo de teste Windows pode ser recompilado e executado pelo unittest no computador de destino.
- A comparacao de caminhos/logs e o video do usuario sustentam os defeitos e os testes de comparacao, mas nao comprovam o resultado desta correcao. Nao houve execucao de audio fisico, jogo, GPU AMD/NVIDIA ou janela WPF neste ambiente. Folhagem, escuridao, sombras e pausas em novas areas continuam pendentes.

## Cache 0.3.5

- 70 testes descobertos: 63 passaram, sete checks PowerShell ignorados pela ausencia desse runtime. Inclui C++ executado com arquivo real, leitor em segundo plano, limites de bytes/fila, deduplicacao/LRU, encerramento, falha de leitura, registros truncados/contagens invalidas, token bucket e I/O em blocos. Teste por processo filho confere o modo Streaming e o limite efetivo nos logs.
- Fixture C++ tambem executado com AddressSanitizer/UBSan. LeakSanitizer nao opera sob o ptrace deste ambiente; essa parte foi desativada, sem alegar verificacao de vazamentos.
- 181 unidades do backend Vulkan configuradas para Windows x64, zero falhas no fechamento incremental e DLL completa ligada; export mkwvk_init conferido no PE. A primeira rodada compilou os objetos e a repeticao incremental confirmou o conjunto completo/link. Runtime alterado host/nvn_native.c compilado separadamente com header generico a64 e declaracoes sinteticas. Nao se repetiu o link do EXE sintetico completo nesta versao.
- 244 entradas do tradutor/ABI comparadas byte a byte com 0.3.4, sem diferencas. Cache stamp anterior reutilizado somente para o fingerprint SHA-256 exato auditado. O writer mantem o formato anterior; parser e transporte passaram a validar limites.
- Python validado com compileall; CLI registra --cache-mode e seu ambiente. A janela WPF e o executavel de interface continuam da publicacao 0.3.2, sem republicacao nesta versao.
- Nenhuma execucao do jogo, teste de driver AMD/NVIDIA, som fisico, frametime real ou comparacao visual foi feita neste ambiente. O novo log RX580 veio de outra build; o relato RTX4090 nao inclui log. Nao sao benchmarks da 0.3.5.
- Registros: resultado-testes.txt, resultado-native-0.3.5.txt, validacao-0.3.5.json. Detalhes de escopo: cache-streaming.md; caso externo: caso-rx580-build-externa.md.

## Integracao final 0.3.6 / foliage-linux-updater

76 testes descobertos:69 passaram, sete PowerShell ignorados. Novas regressoes: raiz errada/aninhada, sondagens ausentes/vazias/legiveis, Unicode sob Python-I, coleta sem encerramento e crash parcial; cooldown/limite de imports em fixture C++ real. Cenarios de build verificam consulta de memoria apos lift/split e quatro jobs para16GiB disponiveis.

356 unidades no conjunto host/renderer sintetico, zero falhas no fechamento; EXE host generico e DLL Vulkan completa ligados para Windows. Sao182 unidades Vulkan. Quinze unidades host alteradas tambem compilaram isoladamente. Os exports de preferencia GPU foram conferidos no EXE completo sintetico, sem dados/corpos do jogo.

Nao houve execucao do jogo, janela WPF, GPU ou som fisico. SDL2 generica foi incluida com a licenca do asset oficial. O video recebido nao e benchmark desta versao. Alteracoes movie-sync e foliage-linux-updater integradas com escopo/restricoes no HANDOFF-OUTRA-IA.md; registros em resultado-testes.txt e resultado-native-0.3.6.txt.

## Integracao 0.3.7

85 casos descobertos, 78 passaram e sete PowerShell nao executados. 182 unidades Vulkan compiladas para Windows e DLL ligada; repeticao com 182 acertos locais e zero recompilacoes. Politica C++ de mirrors executada em fixture. DLL pronta generica sem jogo, fontes e hash conferidos. Nao houve jogo/GPU/som fisico ou janela WPF local. Ver validacao-0.3.7.json e HANDOFF-OUTRA-IA.md.

## Integracao 0.3.8

97 testes descobertos:90 passaram, sete PowerShell nao executados. Testes novos cobrem negacao de leitura/stat sem executar o jogo, arquivo ausente/pasta com nome de EXE, integridade mantida, passagem das opcoes ao processo filho real, leitor C++ contra writer Python real, arquivos truncados/contagens/indices invalidos, limite concorrente16MiB, publicacao atomica, geracao BNSH/zstd por processo real, cache e reversao de DLL. Reader/budget executados com ASan/UBSan; LeakSanitizer desativado por limitacao do ambiente.

182 unidades Vulkan foram compiladas e a DLL Windows ligada. A alteracao final de preparacao foi recompilada incrementalmente:181 acertos locais e uma unidade compilada, zero falhas, DLL religada. Export mkwvk_init conferido. Nenhum jogo, GPU fisica, janela WPF ou reparo de permissoes do PC do usuario foi testado aqui. As piscadas nao estao declaradas como corrigidas. Detalhes em validacao-0.3.8.json e HANDOFF-OUTRA-IA.md.

## Correcao de acesso 0.3.8-dev.2

103 testes:94 passaram, nove nao executados (sete PowerShell existentes e dois testes Windows de DACL/parser). Inclui politica SDDL sem dependencia de OWNER RIGHTS, ordem do staging antes da escrita, bloqueio da publicacao se a DACL falhar e cobertura dos cinco pontos de publicacao. A suite de publicacao/hash/DLL/cache continua passando. WinAPI e reparo UAC nao executados neste host. C/C++/SPIR-V e DLL da 0.3.8 permanecem inalterados; nao se repetiu um build nativo desnecessario.

## Integracao 0.3.9

112 testes:103 passaram, nove omitidos por dependencia Windows/PowerShell. 182 unidades Vulkan compiladas e DLL Windows ligada, export mkwvk_init conferido. Fixtures executam trechos reais dos backports para tabela, contadores, leituras estreitas, faixas de uniformes e caminhos terminais; processo filho verifica classificacao de device lost apesar de exit0. Nao houve jogo/GPU fisica ou janela WPF neste ambiente. Detalhes em validacao-0.3.9.json e HANDOFF-OUTRA-IA.md.


## Candidato controles e write-back, 10/11/2026 (não lançado)

255 testes descobertos: 246 passaram, nove omitidos por dependência do ambiente,
nenhuma falha. As 13 novas regressões executam bindings reais, presets e captura,
classificação de controles, cinco fontes CFF sintéticas, cmap customizado R3,
prioridade de mods, staging/cache e filas dirty do write-back. Fixtures anteriores
foram adaptadas para o novo callback/arquivo Unicode, mantendo suas verificações.
A proteção de carimbo continua rejeitando qualquer conjunto diferente de tradução.

Renderer Windows x64: 182 unidades verificadas, DLL ligada por LLVM-MinGW 23.1.4.
Nove unidades host compiladas com rtgen/a64_rtgen originais e sem dump: hos_thread,
control_bindings, nn_hid, pad_sdl, prompts, mods, win_path, rx_backend e mkw_glue.
Os SPIR-V internos de write-back são os da referência Hookshot 2.0.14. Não houve
execução desse compute neste ambiente, nem link do EXE completo, jogo, GPU física,
áudio ou WPF. Wheels Windows CPython 3.14 x64 para o gerador foram obtidos e tiveram
metadados/hashes conferidos; suas extensões nativas não foram importadas no Windows.

Otimização diferencial desligada por padrão; o A/B e a avaliação de cor continuam
pendentes. Não são ganhos deste candidato os 58 FPS obtidos com NO_WRITEBACK no
notebook. FSR temporal, AMD Frame Generation e thread split não foram incorporados.
Instruções/modelos e organização em CONTINUIDADE-CONTROLES-WB-20261110.md.

A continuação inclui nove regressões do reuso isolado e três de notas do pacote.
O WPF com aba Atualizações compilou por .NET SDK 8.0.427, zero erros/avisos;
13 checks C# de Runner/config/preview passaram em Linux. Isso verifica compilação
e comportamento sem janela; não foi aberta a janela WPF no Windows.
