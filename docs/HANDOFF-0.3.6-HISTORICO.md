# Ocarina Builder / Hookshot — passagem de trabalho 0.3.6

Data: 07/11/2026. Versao dos fontes/orquestracao/motor: **0.3.6-dev.1**. A interface WPF continua sendo o executavel publicado na 0.3.2; nao foi republicada nesta entrega. O nome antigo da pasta do usuario nao identifica a versao efetivamente executada.

## Objetivo e estado real

O usuario quer um pacote Windows completo, simples de usar, com codigo organizado, incorporando melhorias verificaveis do Hookshot e da base local. Prioridades: corrigir crash ao abrir pelo launcher, reduzir tempo de compilacao e pausas, melhorar AMD/NVIDIA, audio, iluminacao, folhagem e artefatos ao mover a camera. Quer continuar a base existente e preservar seu trabalho de compilacao.

Este projeto e uma **recompilacao estatica ARM64 para C/Windows x64** com runtime Horizon/NVN e backend Vulkan. Nao e Ryujinx/Suyu, nem o endereco da falha indica um JIT. Nomes internos TOTK/MKW/RX sao heranca do codigo; nao provam que o programa executa Tears of the Kingdom. O build de jogo suportado e `e0f3ccfa`; a entrada local e identificada antes da traducao.

O pacote nao inclui jogo, chaves, executavel gerado do jogo, ROMFS, saves ou caches. O codigo gerado fica somente em `work/` no computador do usuario. Preserve licencas e avisos da base. O projeto completo precisa ser compilado com a copia local do usuario.

## Origem e integracao desta entrega

Base historica Hookshot-Release/pointer-lighting-2 e ajustes locais. A entrega final 0.3.6 incorpora duas etapas verificadas, nesta ordem:

1. **movie-sync**, commit `44abdcdc58fc5a3ec347cad6f5a43eedab1bd530`: anexo HookshotBuilder(4).zip, asset oficial HookshotBuilder.zip, SHA-256 `dd6bd3d19e6106db05da612b860d24b961fc31110d583d3c3b1ead497b04b79c`. Hash igual ao da API oficial; publicada em07/11/2026 16:15:37UTC.
2. **foliage-linux-updater**, commit `170ce53ca3d69309b3f5151a334136be8b4c38d6`: anexo de FONTES Hookshot-foliage-linux-updater.zip, SHA-256 `b8ac23a1afaacf5b9d7aaeafc03a0d31cc887f509beeba9769af8d03b7460362`. Foram conferidos951 blobs identicos ao tree oficial; um BAT adicional coincide apos normalizar CRLF/LF. O ZIP de fontes nao e o asset binario Windows; nao confundir seus hashes. Release publicada em07/11/2026 19:11:06UTC.

Referencias: [movie-sync](https://github.com/NotRexed/Hookshot/releases/tag/movie-sync) e [foliage-linux-updater](https://github.com/NotRexed/Hookshot/releases/tag/foliage-linux-updater). O alvo e esse commit final, sem acompanhar main/Latest automaticamente.

O merge de host/GPU foi feito em tres vias, preservando os ajustes locais. Nao foram importados a GUI/orquestracao MSVC, helpers do jogo ou a leitura oculta de hookshot_env.txt. O ambiente continua controlado e registrado pelo launcher local. O leitor NUP e seus reparos compactados foram preservados; as restricoes novas de extracao da origem nao foram integradas nesta rodada.

**Escopo Windows:** a origem agora tem Linux/AppImage e atualizador automatico. Esta distribuicao continua Windows x64; os fontes POSIX sao referencia herdada, sem AppImage local montado/testado. O atualizador oficial nao foi integrado: ele depende do Builder original e poderia substituir esta adaptacao. O usuario atualiza pelo pacote completo. Nao anunciar suporte Linux nem atualizacao pelo jogo nesta entrega.

## Implementado e por que

| Mudanca | Local principal | Efeito e limite |
|---|---|---|
| Folhagem e iluminacao EvilOOT | `gpu/vk/` e Eden | Integra mudancas de culling/streams/compute e a iluminacao/neblina da origem; resultado no video do usuario ainda precisa de teste |
| Backoff de imports de memoria | `gpu/vk/import_hold.h`, `vk_memory.cpp` | Faixas cuja importacao falhou aguardam antes de tentar de novo; metadados limitados e teste C++ real |
| Velocidade em tempo real | `gpu/vk/vk_menu.cpp`, `host/nn_vi.c` | Padrao Real time com migracao das configuracoes antigas; nao confundir velocidade de simulacao com FPS |
| Rumble e filme apos Load | `host/nn_hid.c`, `pad_sdl.c`, `nn_video.c` | Integra mapeamento de vibracao e correcao de lock; SDL2 generica incluida com licenca, sem teste fisico de controle |
| Frame generation/menu | `gpu/vk/vk_menu.cpp` e framegen | Opcao da origem ate8x e textos de ajuda; nao e recomendada como forma de esconder queda de FPS base |
| Sincronizacao dos filmes | `host/nn_video.c` | Usa clock/PTS e descarta imagens atrasadas para reduzir descompasso com audio abaixo de 60 FPS; nao e aumento de FPS nem teste de som fisico |
| Solicitacao de GPU dedicada | `host/gpu_preference.c` | Exports NVIDIA Optimus/AMD PowerXpress; preferencias do Windows/usuario podem prevalecer |
| Mudancas cumulativas de renderizacao | `gpu/vk/`, Eden/Sirit e host | Inclui mudancas de depth mode, mesh/task/push constants e acompanhamento de memoria da release; imagem final ainda exige teste |
| Workaround antigo de neblina/exposicao desligado por padrao | `gpu/vk/vk_shader.cpp`, `oot_visual` | So roda com `RX_VK_OOT_VISUAL` explicito e diferente de zero; exposicao alternativa padrao agora 1.0. Evita manter automaticamente o ajuste antigo de 0.65, mas nao comprova correcao da cena |
| Duas janelas de paginas guest | `gpu/vk/vk_memory.cpp` | Mantida extensao da origem, junto de flush local para memoria nao coerente |
| UTF-8 em todas as etapas Python | `manage.py`, `ocarina/process.py`, `nx2/build.py` | `-X utf8` funciona mesmo com `-I`; decodificacao dos logs explicita, sem mudar a code page global do Windows |
| Paralelismo escolhido perto da compilacao | `ocarina/build.py` | Automatico consulta RAM depois de extrair/traduzir; registra memoria, CPUs, modo e jobs. Nao forca quatro processos quando so cabe um |
| Compilacao com mensagens de espera | `nx2/build.py` | Mostra unidade/PID ao iniciar e a cada 15 s enquanto nao termina; nao prova que o processo esta usando CPU, nem interrompe o compilador |
| Raiz RomFS | `ocarina/romfs.py`, build/launch | Exige pastas System/Pack antes do trabalho caro ou da execucao; nao certifica todos os arquivos |
| Auditoria de recursos | `Auditar-RomFS.cmd` | Sonda caminhos vistos no crash sem abrir jogo, alterar dados ou recompilar |
| Coleta incompleta | `ocarina/crash_report.py`, launch | Recusa tentativa sem status e sem CRASH; permite CRASH com status ausente, marcado parcial. Registra PID do filho |

Preservado das entregas anteriores:

- Filesystem Win32 UTF-16/caminhos longos, buffers explicitos e rejeicao de truncamento.
- WASAPI compartilhado, alternativa waveOut, reconexao e HLE de volume; sem modificar volume/dispositivo padrao do Windows.
- Verificacao por hashes de EXE/DLL/imagem; publicacao do manifesto por ultimo.
- Cache de objetos com identidade do compilador, flags, headers e escrita temporaria, sem corromper objetos antigos numa falha.
- Perfis Original, 8gb experimental e Nitido; limpeza de variaveis experimentais herdadas.
- Cache Streaming opt-in: 16 MiB de reservas de leitura antecipada, oito pendentes, indice limitado, historico de prewarm limitado, dois workers, token bucket e I/O de arquivo em ate 64 KiB; snapshot Vulkan ate 128 MiB em arquivo separado.

Os limites de Streaming nao sao teto global de RAM/VRAM. Uma pipeline em compilacao nao e interrompida em 2 ms; faltas essenciais ainda podem bloquear. Nenhum shader generico foi usado para substituir arbitrariamente compute/desenhos. A mudanca de IR/Shader::Info/push constants desta versao exige nova identidade do cache de programas; nao reutilizar artificialmente o stamp da 0.3.5. Primeira abertura apos a mudanca pode reconstruir programas/preparacao.

## Evidencias recebidas: manter as tentativas separadas

### Crash com mapa validado no TXT

`diagnostico-crash.txt` e `diagnostico-crash(1).txt` registram launcher **0.3.4-dev.1**, perfil Original, status `3221225477 / 0xC0000005`. A raiz original e curta, 23 caracteres; a segunda tentativa usa alias `Z:\`.

Ponto reportado: `hookshot.exe+0x17627691`, simbolo anterior `f_8572f300+0x31`; chamador `f_80c4afa0+0x97`, seguido por `f_83bb6eb0`, `f_83b7b340` e outros. O relatorio afirma que o executavel ao lado do mapa corresponde ao crash. Isso localiza a falha, mas nao identifica sozinho a semantica original da funcao ou a origem do ponteiro nulo.

O trace informa falha Win32 3 e arquivo nao encontrado nas sondagens:

- `System/HeapSize/Product.Nin_Ounce_NVN2.HeapDef.byml.zs` e alternativa Default.
- `System/RegionLangMask.txt`.
- `System/GameRomConfig/Product.game__RomConfig.bgyml`.
- `System/AddressTable/All.dev.Nin_Ounce_NVN2.atbl.byml.zs`.

Ha evidencia concreta de problema de acesso/layout/extracao. O alias curto nao resolveu essa tentativa. Nem todo probe isolado e obrigatorio em todo dump; verificar existencia e estrutura real antes de concluir qual arquivo causou o NULL. A nova auditoria nao inventa arquivos nem corrige conteudo ausente.

Interpretacao correta do endereco: `A64_HOST_BASE = 0x100000000000` e a base virtual host usada pelo runtime. A mensagem **guest 0** significa acesso ao offset zero dessa janela. Nao e uma tentativa de alocar 16 TB de RAM nem comparavel diretamente ao endereco guest do heap `0x1000000000`. Esse ultimo valor representa 64 GiB no espaco guest; a razao numerica entre as bases e 256, nao 16. O handler preserva a protecao de null; nao mapear a pagina zero para deixar o jogo continuar.

Os imports `ProtectRelro` e `SetDisplay120HzRefreshRateCapability` aparecem como nao implementados, mas o log nao prova que causaram o crash. Nao inventar retornos, no-ops ou flags de Ryujinx para mascarar o sintoma. A mensagem de camada NVN nativa e normal para esta arquitetura; nao prova que a GPU dedicada foi desligada.

### ZIP de outra tentativa

`20261107-153029-039925-66020.zip` e **outra tentativa**: perfil Nitido, caminho original longo em C:, sem `exit_code`/fim registrado e sem linha CRASH no trecho. Nao juntar seu mapa e metadados com o crash Original em outra pasta.

Ele comprova: motor/launcher 0.3.4, **jobs=1**, build total `8063.43 s` (aproximadamente 2h14). Isso confirma serializacao, mas nao esclarece se foi selecao manual, RAM insuficiente ou politica automatica. A nova metadata distingue o modo. Esse numero inclui o build total, nao somente o compilador.

### Video atual

`Hookshot 2026-11-07 15-15-09.mp4`: 58.129 s, 1920x1080, H.264 com faixa AAC. Frames amostrados mostram contadores entre cerca de 30 e 59 FPS, folhagem ausente, areas muito escuras e artefatos/bordas durante movimento. A taxa do arquivo de video nao e um benchmark do motor. A presenca de AAC nao comprova audio correto/sincronizado do jogo.

Nao ha hash da build/settings/log temporal associado ao video para atribuir tudo ao mesmo executavel. Nao declarar que a 0.3.6 ja corrigiu sua imagem.

### Comparacao visual enviada depois do video

O usuario identificou as duas primeiras capturas como referencias de como o jogo deve aparecer e a terceira como a nossa execucao. Sao referencias fornecidas por ele, sem certificacao de origem, configuracao ou versao. Arquivos recebidos:

| Captura | Dimensoes | Observacao visivel |
|---|---|---|
| `image(20261107-193203).png`, referencia interior | 1324x900 | Hera nas paredes, vegetacao no chao e detalhes do personagem; iluminacao quente no interior |
| `image(20261107-193246).png`, referencia exterior | 1360x900 | Copas com folhas, samambaias/vegetacao densa, personagens iluminados e neblina clara com profundidade |
| `image(20261107-193405).png`, nossa captura | 2047x994 | Copas e parte da vegetacao ausentes, Link escuro, aparencia mais amarela/marrom e contrastada; contador mostra 44 naquele instante |

As cameras, enquadramentos e cenas nao sao identicos; nao calcular uma diferenca quantitativa de exposicao ou desempenho a partir dessas imagens. O contador de um quadro nao e media de FPS nem medida de frametime. A neblina tambem esta presente na referencia: remover toda neblina nao e o alvo.

A prioridade e recuperar a cobertura da vegetacao e a iluminacao coerente, comparando depois neblina e exposicao. Folhas ausentes nao sao corrigidas por brilho global. Culling, caminho mesh/task/compute, streams e estado/descritores sao pontos de investigacao no renderizador, nao causas comprovadas pelas capturas. Para Link/objetos escuros, conferir iluminacao ambiente/difusa e acessos dos shaders antes de compensar com gamma.

O codigo 0.3.6 incorporou as mudancas de folhagem/iluminacao da origem e deixa `oot_visual` desligado sem opt-in. O comentario upstream explica que a exposicao 0.65 antiga escurecia cenas depois de corrigir os acessos de memoria; o padrao alternativo agora e 1.0. Conferir o ambiente efetivo e a identidade dos shaders ao comparar. Isso descreve o codigo integrado, nao prova que a captura nova ja veio dessa versao ou que o defeito foi resolvido.

Proximo teste: usar o mesmo save, posicao/camera e resolucao, perfil Original, registrar opcoes de frame generation/resolucao dinamica e hashes do EXE/DLL, e capturar interior e exterior. Registrar separadamente folhas/grama, Link/NPCs, neblina e artefatos durante movimento. So depois comparar o custo e os frametimes em primeira/segunda visita. Estas imagens nao estabelecem a causa do audio ausente, de crash ou das pausas.

### Caso RX580 externo e relato RTX4090

O log RX580 veio de outra build, nao da nossa. RX580 2048SP: mesh shaders ausentes, sem pipeline libraries, prewarm de 183422 ms, aproximadamente 1.1 GB de VRAM reportada para 7.4 GB permitidos; draws omitidos e pausas ate 3920.8 ms. Nao demonstrou esgotamento de VRAM. O relato RTX4090 a 30–40 FPS nao veio acompanhado de log/CPU/resolucao para determinar a causa. Ver `caso-rx580-build-externa.md`.

## O que continua pendente

1. **Crash no guest zero:** confirmar arquivos/raiz da tentativa Original, coletar log completo apos termino e preservar EXE/mapa correspondente. Depois rastrear o ponteiro na funcao/chamador indicados. Nao atribuir o NULL automaticamente ao primeiro import nao implementado.
2. **Compilacao lenta:** comparar `build-request.json`, `compile.log`, memoria disponivel, uso de CPU/disco e unidade mais demorada. A nova escolha tardia de jobs/heartbeat precisa ser testada no PC real. Preservar `work/objcache` e os limites estaveis dos chunks. Nao reduzir O2/O1 ou alterar semantica silenciosamente para anunciar um tempo melhor.
3. **Folhas/grama e iluminacao:** a solucao upstream foliage-linux-updater foi integrada, mas ainda precisa de comparacao real nesta adaptacao. Priorizar floresta Kokiri, placas/samambaias/Link e lago. A origem ainda relata flashes escuros de um frame, flicker de fog e device lost ao carregar save em alguns PCs. Nao tratar integracao como prova de imagem correta nem ajustar apenas gamma para esconder defeitos.
4. **Bordas/rastros de camera:** comparar Original e Nitido, mesma resolucao/cena, com frame generation registrado. O Nitido usa substituicao espacial existente e pode aumentar serrilhado/custo; nao e uma correcao universal de TAA.
5. **Pausas e FPS:** medir frametimes/CPU/GPU e primeira/segunda visita. Streaming troca parte do trabalho inicial por possiveis compilacoes durante o jogo; avaliar acertos de leitura antes de aumentar limites.
6. **Segunda abertura preta:** [issue195](https://github.com/NotRexed/Hookshot/issues/195) ainda em investigacao na origem. Se reproduzir, fazer comparacao com caches especificos guardados separadamente; nao apagar saves ou caches globais do driver automaticamente.
7. **Compatibilidade GPU:** RX580/GTX10xx/RX5000 sem mesh shaders nao ganham esse recurso por variavel. Um caminho alternativo de geometria exigiria projeto/testes proprios. Exports de GPU dedicada nao garantem a escolha pelo SO.
8. **Imports/servicos HLE e audio:** implementar somente com assinatura, ABI e comportamento comprovados. Testar saida/dispositivo e filme em hardware real; nao assumir que todo stub de log e fatal.

## Como continuar e verificar

Leia `AGENTS.md`, `README.md`, `docs/arquitetura.md`, `docs/validacao.md` e `upstream.json`. Nao incluir codigo gerado, dados do jogo, caches ou saves na distribuicao. Nao enviar mensagens/issues a terceiros sem autorizacao do usuario.

No Windows, a partir da pasta que contem `manage.py`:

```powershell
.\Verificar.cmd
.\ferramentas\python\python.exe -m unittest discover -s tests -v
.\Auditar-RomFS.cmd --romfs "E:\SuaPasta\romfs"
.\Compilar.cmd -Jogo "D:\SuaCopia.nup"
.\Jogar.cmd
.\Jogar-Streaming.cmd
.\Jogar-Suporte.cmd --cache-mode streaming
.\Coletar-Crash.cmd
```

Para entradas em pastas, usar `Compilar.cmd -Exefs ... -Romfs ...`; destinos personalizados usam `-Destino` no build e `--out` nos atalhos de jogo/coleta. Preserve a mesma pasta de trabalho/caminhos para favorecer cache. Em maquinas com pouca memoria, mantenha Automatico ou um job. Jobs manuais sao uma escolha explicita, sem garantia de caberem.

Trate uma mudanca por vez. Associe cada teste ao hash do EXE/DLL, versao, perfil, cache mode e opcoes. Preserve o mapa antes de um novo link. Para funcoes geradas, altere o gerador/HLE/patch explicito, nunca o C gerado manualmente como solucao final.

## Validacao efetivamente realizada

- **76 testes descobertos: 69 passaram e sete de PowerShell ignorados** por falta desse runtime no host Linux. Fixtures sinteticos, arquivos reais temporarios e processos filhos reais onde aplicavel.
- DLL Vulkan completa ligada para Windows x64, conjunto de **182 unidades**, zero falhas no fechamento incremental.
- Quinze unidades host alteradas compiladas separadamente com header a64 generico/declaracoes sinteticas; `gpu_preference.c` ligado num EXE generico e ambos os exports conferidos no PE.
- O teste C++ real de backoff de importacao confirma cooldown, expiracao e limite de metadados.
- Python compilado com compileall. O transporte cache manteve seus headers testados com ASan/UBSan na 0.3.5; nao foi alegado teste de jogo por esse motivo.
- Nao houve execucao do jogo, GPU/driver fisico AMD/NVIDIA, audio fisico ou janela WPF neste ambiente. O conjunto de356 unidades fechou o EXE host sintetico e a DLL Vulkan. O fixture nao possui corpos de codigo/dados do jogo. Nenhuma afirmacao de FPS/zero stutter e demonstrada por compilar.

Registros: `resultado-testes.txt`, `resultado-native-0.3.6.txt` e `validacao-0.3.6.json`. Os ZIPs entregues devem ser fechados e ter CRC/conteudo conferidos antes de disponibilizar. O pacote Windows completo inclui os fontes para a outra IA; ela tambem precisa das entradas privadas locais para reproduzir o jogo.
