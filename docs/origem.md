# Origem e escopo

## Base principal

Os fontes vieram de `Hookshot-Release.zip`, fornecido pelo usuario. Esse ZIP nao contem metadados Git suficientes para afirmar um commit exato da release. Sua identidade e registrada por SHA-256 em `upstream.json`; referencias a commits dentro da documentacao original descrevem a historia do projeto, sem substituir essa identificacao.

O motor em `host/`, o pipeline em `nx2/`, o renderizador e o tradutor em `gpu/` mantem a organizacao e as interfaces do Hookshot. Os avisos de autoria e as licencas foram preservados. README e notas de desenvolvimento originais estao em `docs/upstream/`.

## Material do Ocarina anterior

O pacote `Ocarina-Setup-0.2.1-windows.zip` foi usado como origem de ferramentas genericas: Python, LLVM-MinGW e headers Vulkan/VMA. O runtime, o tradutor de shaders, os lancadores e os arquivos gerados daquele projeto nao foram incorporados ao motor desta base. O binario `totk_xlate.exe` tambem nao faz parte da nova distribuicao.

Da investigacao anterior vieram os requisitos de verificacao de dependencias, hashes dos arquivos executados, perfis separados e logs por tentativa. Os antigos bloqueios de pools/pipelines invalidos nao foram copiados para o Hookshot.

## Alteracoes locais

- Menu F1 em preto e dourado com escolha do upscaler e leitura do modo efetivo por quadro. A seleção do provedor FSR 4 consulta o AMD FSR SDK 2.4 conforme a referência `NX2navi-app-0.8.0.zip` (`runtime/vk_ffx4.cpp`). A implementação usa a captura e a apresentação do AkynoLeyend r7, com as duas DLLs AMD da r7 conferidas contra o pacote de referência.
- Pacote `ocarina/`, CLI e lancadores Windows.
- Compilacao com dependencias locais declaradas, alvo LLVM-MinGW, cache com identidade do compilador e saidas temporarias.
- Retirada do caminho de build WebGPU desta distribuicao e erro explicito se o Vulkan nao iniciar.
- Inclusoes de `<cstdlib>` / `<cstdio>` requeridas pela toolchain em tres arquivos do backend.
- Helpers de traducao/descompressao podem ser gravados em `work/helpers`, sem sujar as pastas de fontes durante o fluxo normal.
- Extracao NUP recusa caminhos que escapem da pasta escolhida.
- Interface de build antiga delega ao fluxo unico novo.

O diff dos arquivos herdados esta em `patches/base-portabilidade.patch`. Modulos novos ficam separados, com responsabilidades descritas em `docs/arquitetura.md`. As bibliotecas e versoes distribuidas estao registradas em `ferramentas/dependencias.json`.

## Interface 0.3.1

A interface WPF foi adaptada dos fontes `builder/HookshotBuilder` do mesmo ZIP Hookshot-Release fornecido. Tema, controles e traducoes existentes foram preservados. A adaptacao usa o nome Ocarina Builder e a CLI unica desta base; remove a execucao direta do jogo e a procura do Python do sistema, acrescenta progresso, perfil, paralelismo e propagacao de erros/cancelamento.

O leitor NUP agora fecha o arquivo quando falha durante a inicializacao e confere os limites da tabela antes de le-la. A verificacao da GUI nao extrai nem executa dados do jogo. O inventario `upstream.json` e o patch de portabilidade foram atualizados para registrar essas mudancas.

O executavel inclui o runtime Microsoft.NETCore.App e Microsoft.WindowsDesktop.App 8.0.33, obtidos dos pacotes oficiais NuGet. Os avisos estao em `licenses/dotnet/`. O SDK de compilacao e a adaptacao temporaria do host de build nao fazem parte da distribuicao.

## Correcao de chunks na instalacao limpa

`nx2/chunks.py` passa a criar o diretorio de metadados compartilhados ao salvar, mantendo o local previsto pelo Hookshot. As leituras dos limites e dos arquivos C gerados sao fechadas explicitamente. A mudanca responde ao FileNotFoundError de work/image/chunks.txt recebido nos logs do usuario e tem tres testes de regressao com entradas sinteticas.

## Suplemento HookshotBuilder(1).zip

O suporte a wrappers Zstandard e a recuperacao de modulos no leitor NUP foram adaptados do pacote fornecido. A lista hot_funcs.txt foi incorporada como metadado do build e0f3ccfa. python-zstandard 0.25.0 para CPython 3.14 Windows x64 foi copiado com seus metadados e licenca. A orquestracao passou a selecionar a lista, condicionar a divisao a uma fonte atual e migrar caches de extracao pela identidade do leitor. O restante do motor permanece na base previamente identificada; detalhes em docs/atualizacao-split-nup.md.

## Integracao 0.3.2

Atualizacao de host/GPU a partir dos pacotes HookshotBuilder (1)(1).zip e HookshotBuilder (2).zip. O segundo fornece a sincronizacao da primeira submissao, ajuste de fog 0.08 e o shader movie_upscale. Perfil AMD de gather/Position adaptado do codigo Vulkan do emulador Eglantine/Lichii v4 fornecido. Mantidos os avisos Hookshot, Eden, Sirit e Orchid em seus arquivos. Adaptacoes locais: fechamento do link Vulkan-only, verificacao de erros no startup/upscale e cache por dispositivo. Escopo e limites em atualizacao-amd.md; hashes e inventario em upstream.json.

## Integracao 0.3.3

Renderizador e parser de idioma atualizados do HookshotBuilder(3).zip da release pointer-lighting-2, cujo hash coincide com o asset da API oficial. Mantidos os avisos Hookshot/Eden/Lichii. Energia e saida do build adaptadas a orquestracao local, sem a dependencia de MSVC do builder original. Acrescentados flush da tabela, coleta de crash e teste opcional de alias RomFS. Escopo e limites em atualizacao-0.3.3.md.

## Alteracoes locais 0.3.4

Adaptadores Win32 UTF-16/caminhos estendidos, backend de audio WASAPI compartilhado, recuperacao waveOut e HLE de volume foram escritos para esta base a partir dos diagnosticos recebidos. Nao vieram de outro emulador nem de uma nova release Hookshot. As APIs de som/caminhos foram conferidas na documentacao Microsoft; a interface de volume tambem foi conferida nas referencias de audio NXNative/Switchbrew.

O perfil Nitido apenas seleciona o stand-in espacial preexistente de gpu/vk/vk_draw.cpp. O registro de frames lentos foi corrigido sem trocar a traducao de shaders ou os defaults visuais. O patch local, os componentes mantidos e os hashes estao registrados em upstream.json. Nao foram incorporados jogo, saves, caches ou simbolos do jogo nos pacotes.

## Alteracoes locais 0.3.5

Politica limitada de cache, leitor de fundo, parser defensivo, token bucket e teste nativo foram escritos para esta base. Nao sao um novo driver nem codigo de outra release Hookshot. Mantida a base verificada pointer-lighting-2 e os avisos anteriores. Comparadas 244 entradas de Eden/Sirit/compat e headers ABI com a 0.3.4, sem diferencas; o transporte de cache mudou sem alterar o wire format do writer ou a semantica do IR. O registro por fingerprint exato preserva o stamp anterior para essa combinacao auditada.

O log externo da RX580 motivou limites de pre-aquecimento e a reducao de backtraces repetidos de apresentacao. Nao foi incorporada uma correcao visual deduzida somente das imagens. NVIDIA 621.14 e AMD26.10.1 foram consultados em documentacao oficial; nenhum binario de driver foi incorporado. Delta em `patches/0.3.5-cache-streaming.patch`; limites e origem em `cache-streaming.md` e `drivers-amd-nvidia.md`.

## Integracao 0.3.6 / movie-sync

HookshotBuilder(4).zip foi conferido contra o asset oficial movie-sync, SHA-256 dd6bd3d19e6106db05da612b860d24b961fc31110d583d3c3b1ead497b04b79c, commit44abdcdc58fc5a3ec347cad6f5a43eedab1bd530. Merge de tres vias contra os fontes oficiais pointer-lighting-2; conflitos em push constants, paginas guest, chave de cache e espera do renderer resolvidos preservando as verificacoes locais.

Mantidos WASAPI, caminhos Win32 longos, identidade por GPU/driver e Streaming opt-in. Nao foram importados a GUI/binarios/ferramentas MSVC da origem nem hookshot_env.txt, para que o ambiente efetivo continue controlado e registrado pelo launcher. O leitor NUP local e seus reparos compactados foram preservados; as mudancas novas de extracao da origem nao foram incorporadas. UTF-8 foi aplicado no transporte local. A nova validacao de raiz, auditoria, escolha tardia de jobs e coleta parcial sao locais, motivadas pelos anexos.

## Complemento final 0.3.6 / foliage-linux-updater

Integrados host/GPU do commit170ce53ca3d69309b3f5151a334136be8b4c38d6, apos movie-sync. Anexo de fontes conferido por blobs Git (951 exatos e um BAT normalizado CRLF), incluindo alteracoes EvilOOT de folhagem/iluminacao, lock de video, import backoff, simulacao em tempo real e rumble. SDK SDL2 generica do asset movie-sync inclui licenca zlib. Atualizador oficial/hos_update.c e rx_nowgpu.c nao foram incorporados; permanecem o fluxo local Windows e seu stand-in WebGPU explicito. Fontes POSIX herdados nao equivalem a AppImage construido ou suporte Linux validado.

## Integracao 0.3.7

Estudo dos ports TotK/Savage Wind e Ocarina 0.2.4/0.2.5. Implementacoes locais: alvo menor de blocos novos com limites existentes preservados; DLL Vulkan generica pronta com identidade verificada; politica de mirrors da classe de 12 GiB; diagnostico de acesso negado; tempos e contadores reais de cache. Nenhum arquivo de implementacao dos forks Ocarina 0.2.4/0.2.5 foi copiado. Detalhes e referencias em HANDOFF-OUTRA-IA.md.

## Alteracoes locais 0.3.8

Tratamento de erros de acesso no lancador, coleta Win32 somente de leitura, modos ASTC explicitos, atualizacao isolada de DLL e banco de shaders indexado foram escritos para esta base. Preservados os avisos e o formato HKSEED01 de nx2/shader_census.py. O arquivo astc_analysis.rar fornecido foi estudado passivamente: quatro trechos Eden/Yuzu, incluindo renderer OpenGL e configuracoes. Nenhum desses quatro arquivos foi copiado para o renderizador Vulkan nem anunciado como conserto das luzes. A tela Preparing shaders ja existia nos fontes herdados; foi ligado o fluxo local que gera/publica seu banco e limitado o transporte de pacotes, alem de corrigida a abertura/fechamento da console de progresso. A traducao e o formato de cache de programas permanecem iguais ao conjunto auditado 0.3.7.

## Correcao de acesso 0.3.8-dev.2

Motivada pelo ZIP real 20261107-205245-647183-1124.zip: tres arquivos regulares com WinError5, inclusive na consulta de ACLs, manifesto legivel. A hipotese TemporaryDirectory/elevacao/OWNER RIGHTS foi conferida no relato primario CPython#157876 e na documentacao Microsoft de heranca e movimentacao. O wrapper de staging explicita o SID do usuario sem ampliar acesso a Everyone; o reparo pontual usa ferramentas Windows e registra ACL/dono/resultado. Nenhuma nova implementacao grafica ou fonte de shader foi incorporada.

## Backports seletivos 0.3.9

HookshotBuilder(6).zip foi comparado ao snapshot NotRexed/Hookshot 9bb52a94d8a542d37edeaf86e4a128a9848fb261. Integrados: tabela de paginas ordenada, protecao de palavras de reports contra writebacks, cargas globais 8/16 bits e cache de lacunas de atualizacoes uniformes (c3459dc2 e alteracoes anteriores correspondentes). Preservado o flush local de memoria nao coerente. Ocarina-Setup-0.2.7 foi estudado como referencia de instalacao/cache/NOOPT; seu runtime nao foi transplantado. Tratamento terminal e classificacao de falha sao locais. Preservadas as licencas upstream.

## AkynoLeyend 0.4.0

Base local Ocarina 0.3.9 fornecida pelo usuario; nome publico e pacote de orquestracao migrados para AkynoLeyend/akynoleyend.
Incorporados seletivamente PR296 de evilmfkr/EvilBoyce e PR300/327/362/416 de SkippySteve, por arquivos da API oficial;
commits exatos e hashes em upstream.json. Mudancas nativas em patches/0.4.0-native.patch.
Locais: GUI preto/dourado, argumentos graficos, persistencia, migracao reversivel de nomes, cache de leituras capturadas,
diagnostico limitado de CPU e perfil Compatibilidade. Estudos MDias/Max Resolution/Dynamic FPS nao resultaram em transplante
de IPS nem em backend OpenGL. Autores e avisos preservados em creditos/README.md e nos fontes.
O crash AMD recebido e os defeitos visuais nao foram declarados resolvidos por estes testes sinteticos.


## Integracao candidata 0.4.1 (fonte sobre a distribuicao Windows 0.4.0)

Correção da ABI `nn::fs::DirectoryEntry` em `host/nn_fs.c` (tipo no offset 0x304),
com testes C e Python; mitigação seletiva do compilador AMD task/mesh adaptada da
PR430 de YunaraDebugs/Hookshot 2.0.5. Reutilizado o controle existente
`HOS_RES_SCALE` para candidatos 125 e 150%, sem importar o patch IPS ARM64 de outro emulador.
Cache equilibrado, configuração de workers e reutilização da publicação de shader bank
são modificações locais. Biblioteca LSFG, FSR3 e shader recompilers externos **não copiados**.
Teste real no jogo, Windows e GPU ainda pendentes. Lista e limites em
`docs/INTEGRACAO-0.4.1-CANDIDATO.md`.

## Consolidação 0.4.2-rc.1

Entrada: candidato Visual 0.4.1 fornecido, SHA-256 registrado em upstream.json. Preservados os patches visuais candidatos e republicados o launcher e a DLL genérica Windows. Os reparos de posse do read-ahead, taxa global de pré-aquecimento e coerência host/renderer/distribuição são locais. A retenção de texturas é relacionada à PR593 de duck-paradise; o despacho indireto e rastreamento seletivo têm referência na PR252 de AyyBeeDee20738. O estudo não transforma essas referências em prova de correção desta GPU. Créditos e licenças preservados; não houve incorporação de dados ou código gerado do jogo. Relatório atual: Relatorio-AkynoLeyend-0.4.2.md.

## Correção local do lifter 0.4.2 (09/11/2026)

Os logs `extract(2).log` e `lift(2).log` fornecidos mostram a extração concluída e a interrupção
em `oot_occlusion.install`, por ausência de `Lifter.after`. O a64-kit distribuído agora
registra os acréscimos por endereço e os inclui no texto da instrução antes da análise
de registradores/flags e da emissão de C. A implementação é local; os seis endereços e
a conferência das palavras ARM64 de `nx2/oot_occlusion.py` foram preservados.
Os créditos e as licenças herdadas permanecem. Não houve mudança no renderer, runtime
ou launcher binários. Validação e instruções em `CORRECAO-LIFT-0.4.2.md`.

O aplicador `tools/reparar_lift.py` e `Aplicar-Correcao-Lift.cmd` são locais e respondem
à repetição do mesmo AttributeError em `lift(3).log`. Eles verificam o caminho importado,
a origem conhecida dos bytes e os seis sítios sintéticos; preservam backup e revertem
a substituição se a conferência falhar. Não incorporam dados ou caches do jogo.

## Estudo gráfico de 09/11/2026 — trabalho não publicado

Comparada a release oficial Hookshot v2.0.6 no commit
`fa439391aae6f3bf104340ea36c6ea993b38534e`. O fingerprint de fontes calculado pelo
próprio `nx2/version.py` é `9b541c9c`, exatamente o indicado na captura do usuário.
Esse número é um fingerprint, não um commit Git. O SHA-256 do HookshotBuilder.exe
fornecido coincide com o asset oficial; ele é o instalador Win32 que baixa as partes,
não contém o motor completo. Foi inspecionado passivamente, sem execução.

Integrado o reparo de alocação dos marcadores REGMAP de pelicanux, PR759, merge
`deaf4ff59c36b49d0e539084701151cb1858a07d`, com sua regressão sintética. O código
continua sob os avisos GPL do componente Eden. O suporte ATOMG CAS foi inicialmente separado desse reparo. Na continuação, sua
cadeia de 32 bits foi adaptada junto com o IR/backend, conforme o registro abaixo.

Também adaptados seletivamente de Hookshot v2.0.6: leitores BAHS/NDSR/NDVE e locais
de shaders, alcance de uniform buffers para as tabelas geradas, refresh da escala
fixa, intervalo de apresentação em tempo real e conjunto de tamanho de saída/pools
da PR849. O conjunto de saída tem oito guardas de texto antes de aplicar as mudanças;
as funções envolvidas mantêm registradores no Ctx para os patches explícitos. A
configuração local usa `AkynoLeyend_opts.ini`; o override bruto HOS_RT_POOL_MB não
foi disponibilizado neste candidato. Créditos upstream foram preservados.

O FSR 1 usa `ffx_a.h` e `ffx_fsr1.h` oficiais da AMD, sem alterações, do commit
`a21ffb8f6c13233ba336352bdff293894c706575` de GPUOpen-Effects/FidelityFX-FSR, sob
MIT. A licença fica em `gpu/vk/shaders/ffx/LICENSE.txt`. Wrappers GLSL e integração
Vulkan locais; EASU e RCAS separados. Os headers SPIR-V genéricos são reconstruídos
por `tools/build_fsr_shaders.py` e não contêm bytecode do jogo.

Os RARs de análise, Fritchii e NX2navi da etapa anterior permanecem referências de
estudo; a integração restrita por LICENSE-ADDITIONS do NX2navi não foi copiada. A
coleta ampliada mantém o spool e o leitor limitado locais, sem transplante de caches
binários de outro renderizador. Não é afirmada a fusão integral de todos os compiladores.

O banco privado fornecido foi auditado em separado, sem entrar nos fontes ou em
distribuição: todos os 13.773 estágios passaram pelo lowering antes/depois. As 313
colisões de mapeamento detectadas caíram para zero. Isso comprova o defeito do
tradutor nesse banco e seu reparo; não equivale a uma execução do jogo completo.

O trabalho não foi publicado como release e os ZIPs 0.4.2 foram preservados.
Estado, hashes e pendências em `ESTUDO-GRAFICO-20261109.md` e `validacao-grafica-043.json`.

Na continuação, adaptado também do mesmo Hookshot v2.0.6 o conjunto da issue 302:
topologia NVN2 de pontos e coordenadas do point sprite nos generics não escritos
pelo mesh. Inclui `vk_shader.cpp`, `RuntimeInfo`, declaração do builtin e emissão
dos atributos no backend SPIR-V, com avisos GPL originais preservados. Não incorpora
o fallback de mesh inteiro nem o novo passe geral de memória.

Mudanças locais na apresentação: recorte limitado comum, ligação explícita da view
no caminho direto, inicialização independente dos filtros e descarte de recursos
parcialmente criados. Os testes Vulkan usam imagens sintéticas e os shaders genéricos
FSR; o verificador de topologia registra somente metadados do banco privado.


## Continuação: desempenho, CAS e organização — 09/11/2026

O log v2.0.7 recebido mostra o mesmo fingerprint 9b541c9c da referência acima.
Adaptados seletivamente desse snapshot: gerações por estágio dos bancos driver,
bindings idênticos sem invalidação, marcação de trabalho Vulkan e deduplicação de
barreiras vazias. O marcador local inclui reinício/reuso de command buffers,
consultas e eventos; o replay paralelo preserva as barreiras.

ATOMG.CAS de 32 bits foi portado pela cadeia completa de 15 arquivos Eden:
Ampere→Maxwell, visitor, IR, efeitos laterais, passes e SPIR-V. As tabelas de
opcodes passam a 541. Preservados os avisos GPL de cada componente; não é um
transplante do passe geral de ponteiros do novo Hookshot. O override TLS do
controle compute e seus testes são adaptações locais.

A implementação WebGPU e o compilador Suyu redundante foram retirados do build
Vulkan; mantidos três headers NVN, decodificadores e bibliotecas ativas, avisos,
licenças e créditos históricos. O manifesto `limpeza-043.json` identifica os 250
arquivos retirados e os 22 comandos movidos. A origem histórica dos componentes
continua registrada mesmo quando seus antigos caminhos já não existem.

Dados privados recebidos foram usados em auditoria separada. A árvore não contém
os bancos, módulos do jogo, culling, vídeo nem o C gerado durante a conferência.
Não houve benchmark do jogo ou teste de GPU física. Registros atuais no estudo
gráfico e em `validacao-grafica-043.json`; nenhuma release foi publicada.


## Pacote Windows de teste 0.4.3-test.1

A pedido do usuário, foi preparado um pacote executável de teste com as ferramentas
genéricas da base, launcher republicado dos fontes e DLL já conferida. Não contém
jogo, ExeFS, RomFS, saves ou bancos privados. O host é gerado localmente pelo usuário.
A publicação de teste permite a validação física que não foi feita neste ambiente.


## Teste 2 — adaptação de hardware, acesso ao FSR e CPU do renderer

Analisados os arquivos de teste do usuário, build_optimizer.zip e Hookshot v2.0.10,
commit 7f9daf06d902588476102d6650c600bb84f02ce5. Adaptados somente o cache de samplers
com geração dos registros e a união de cópias consecutivas de capturas, incluindo
sua regressão sintética. Código Hookshot sob GPL-3.0; texto em
licenses/Hookshot-GPL-3.0.txt. Preservados os avisos originais e o caminho AMD local.

Detecção de hardware, fila limitada do preview de logs, controles separados de
saída/escala, preset FSR e conferência de atualização por host exato são adaptações
locais. Não foi copiada a geração de comandos do otimizador. NX2navi 0.6.1 foi
consultado com seus avisos; adições reservadas por LICENSE-ADDITIONS não foram copiadas.
Não foram habilitados o write-back diff ou a fila separada de apresentação da
referência, desativados por padrão no snapshot recebido. Nenhum ganho de FPS foi
medido localmente. Relatório em ANALISE-OPTIMIZER-REFERENCIAS-TESTE2.md.


## Teste 3 — RX 6600, vídeo e atualização

Do mesmo Hookshot v2.0.10 (7f9daf06d902588476102d6650c600bb84f02ce5, GPL-3.0),
adaptados a execução de uma camada por vez em ASTC→BC3 (#956), o armazenamento de
NV12 sem RGBA antecipado e o processamento de EOS antes de esvaziar a fila.
Os limites de recuperação de vídeo, a preservação do quarto operando do CAS
global→storage, Full HD, controles simplificados por mouse/WASD, perfis e o
atualizador local são mudanças desta integração. Avisos das bases preservados.
Não foi importada a ABI de ponteiro do menu novo do Hookshot: a integração Windows
usa as funções de cursor e o evento da janela, sem alterar vk_api.h.


## 09/11/2026 — reparo de extracao NUP 1

Mudanca local em nx2/nup.py: caminhos Win32 estendidos, temporario curto exclusivo, publicacao atomica e diagnostico. Aplicador com hashes, backup, probe e reversao em tools/reparar_extracao.py. Dados, objetos e binarios do jogo preservados. Referencias integrated(2).zip e Nova pasta.zip inspecionadas; nenhum codigo desses anexos incorporado neste reparo. Detalhes: CORRECAO-EXTRACAO-1.md e ANALISE-ANEXOS-20261109.md.
## Checkpoint 10/11/2026 — Hookshot 2.0.13 e 2.0.14

Adaptações limitadas a partir de Hookshot GPL-3.0, tags v2.0.13
(`fbcde13bf1e121f2607bb0a2a0f686c513b31164`) e v2.0.14
(`7f70b922ebdb2bd3d2fb5cf8b6c0f5f0d1ba7124`): menu que cabe na janela,
escala independente do contador FPS, escape de caminhos literais com colchetes,
LEA.HI constante sem carry, seleção de core rápido e afinidade de replay.
Reúso conservador de targets após conclusão na GPU e orçamento de texturas para
6–8 GB adaptados ao lifetime local. Avisos/licenças preservados; fixture LEA
derivada do teste upstream, com atribuição no arquivo.

A exclusão exata de GPU_PROFILE do carimbo, a medição específica de write-back
e o controle opt-in de cronômetros detalhados são adaptações locais motivadas
pelo perfil T02 do usuário. Não foi copiado código reservado do NX2navi 0.7.1.

O código completo aberto de Button prompts foi analisado como referência; o
recurso ainda não foi integrado. FSR3 temporal, write-back diferencial/lazy,
texture detail por mip, HDR e hooks de relógio acima de 60 FPS também não estão
declarados implementados. A validação é de fontes/fixtures/compilação, sem teste
de FPS ou de GPU física. Ver CONTINUACAO-UPSTREAM-20261110.md.


## Candidato controles/write-back, 10/11/2026 (não lançado)

Adaptados seletivamente de Hookshot v2.0.14, commit 7f70b922ebdb2bd3d2fb5cf8b6c0f5f0d1ba7124,
GPL-3.0: runtime prompts/mods, bloco de bindings, gerador de assets e compute de
write-back diferencial. Mantida a procedência MIT indicada pelo upstream para o
indexador RomFS derivado do Skybound. Kenney Input Prompts 1.5 é CC0, com licença
em third_party/kenney_input. As fontes de controle redistribuídas são Kenney; os
assets do jogo são gerados apenas a partir do dump local, não redistribuídos.

Locais: editor/captura de bindings com callbacks API 2, adaptadores XInput/SDL,
configuração Unicode/long paths e publicação atômica, orquestração de assets com
staging/cache, invalidação dirty bounded e teto de shadows de 512 MiB. Otimização
write-back permanece opt-in até validar cor e sincronização. O bloco upstream com
números de desempenho é evidência de OUTRO projeto, não deste candidato.

SDK AMD v2.4.0 foi conferido como referência oficial para a tarefa temporal/FG;
não foi incorporado nem anunciado como integrado. Não incorporado código reservado
NX2navi, catálogo GPFIFO/thread split ou shader translator diferente. O carimbo
registrado conserva apenas a identidade exata auditada da tradução v7; trocar a
tradução novamente exige nova identidade. Estado e tarefas no documento de continuidade.

Adendo do launcher: aba Atualizações, preview de notas verificadas antes de aplicar,
validação tipada/limitada das notas e reuso explícito de objetos com flags originais
em área isolada foram escritos localmente. C# compilado e fixtures reais de
Runner/objetos/notas executados; pacote Windows instalável não foi publicado.


## Revisões r4–r6 da 0.4.3-test.4, 10–11/11/2026 (não lançadas)

r4/r5 (locais, motivadas pelos diagnósticos de Kokiri de um testador): parada controlada quando o Windows recusa
commit (`host/mkw_glue.c`), flush da tabela de páginas em intervalos e sem escritas sobrepostas
(`gpu/vk/vk_table_runs.h`, `gpu/vk/vk_memory.cpp`), linhas `mem:` e aviso de memória virtual no launcher.

Revisão r6. De Hookshot v2.1.0 (tag `v2.1.0`, commit `8ef84611049f4fc31835a0b12793cf074ed49c3c`, GPL-3.0; arquivo
de fontes `Hookshot-2.1.0.zip`, SHA-256 `1ea427bed19105b6a19e775c1f172bbb5082834204bbadcd4a40ec00939e0c56`),
dois arquivos do host tomados inteiros, porque os locais só diferiam deles por estas mudanças:

- `host/nn_os_sync.c`: WaitAny acordado apenas por objetos que um multi-wait observa (`poke_multiwait(Obj *)`,
  tabela `mw_watched`, `obj_nockpt`, `event_peek`); `HOS_MW_WAKE=all` volta ao comportamento anterior.
- `host/hos_thread.c`: registro gravado em lotes por thread própria também para arquivos
  (`HOS_LOG_BATCH_MS`, `HOS_LOG_SYNC=1`), núcleos do maior L3 em CPUs X3D de dois CCDs (`HOS_CACHE_CORES=0`) e
  OptimizeChangeBank em prioridade baixa (`HOS_OCB_NORMAL=1`).

Os números de desempenho citados nos comentários desses arquivos são medições do projeto Hookshot, não deste.

Locais na r6: heap do jogo commitado sob demanda quando o commit livre do Windows é menor que o heap mais 12 GB
(`hos_heap_on_demand`, `hos_commit_for_host` em `host/mkw_glue.c`; chamadas em `host/hos_mem.c`, `host/nn_fs.c`,
`host/nvn_native.c`; `HOS_LAZY_HEAP=0/1`), aviso de pouca memória antes de iniciar (`akynoleyend/runtime_failure.py`,
`akynoleyend/launch.py`; a ideia do aviso é do Hookshot v2.1.0, texto e números são locais) e identidade r5 em
`akynoleyend/coherence.py`. Não portado do v2.1.0: renderizador (81 arquivos em `gpu/vk` contra 48 locais),
DLSS, FSR 3.1, HDR, limite de FPS, menu ImGui e as otimizações do lifter (exigem recompilar o jogo).
Medido apenas na cena de demonstração do PC de desenvolvimento; sem gameplay.

Revisao da r6. A descarga do log usa a ordem unica escrita → fila em `host/hos_thread.c`, com regressao em `tests/test_table_runs_043.py`. A compatibilidade reconhece a identidade dos fontes Windows da r6 para reutilizar os objetos traduzidos.

## AMD FSR SDK 2.4

A candidata adapta os hooks de projecao, a matematica e o preparo dos vetores de camera do Hookshot v2.0.14 (GPL-3.0). O despacho Vulkan usa o loader e o provedor FSR 3.1.6 do SDK AMD 2.4 enviado pelo usuario. Headers, avisos, licencas e os hashes das duas DLLs estao em `third_party/amd-fsr-sdk`.

## Memoria virtual curta (r8)

Medido em Kokiri a 1080p (handoff/scripts/memmap.py): o processo confirma cerca de 21 GB e usa de fato cerca de 10 GB; cerca de 9 GB sao confirmados e nunca tocados fora da janela do jogo, acompanhando a VRAM em uso. `gpu/vk/texture_budget.h` (`commit_limited_budget`) e `gpu/vk/vk_texture.cpp` reduzem o orcamento de texturas enquanto o Windows tem menos de 3 GB de memoria virtual livre; `akynoleyend/runtime_failure.py` avisa antes de jogar quando a cena nao cabe. Codigo deste projeto; sem teste em PC com pouca memoria virtual.

## Painel F1 Akyno sobre a r8

O desenho e a navegação em Tela, Ampliação e Controles foram refeitos em
`gpu/vk/vk_menu.cpp` com a paleta e a marca de
`builder/AkynoLeyendBuilder/App.xaml` e `MainWindow.xaml`. O menu usa o
estado dos provedores já integrados à r8 e mantém as chaves do INI. A
atualização substitui o renderizador com a ABI existente. O cache de shaders
continua identificado pelo carimbo `4cdbb0029868040b`.

## Candidata de desempenho e F1, 11/11/2026

Referência Hookshot v2.1.0 (tag `8ef8461`, GPL-3.0). O Akyno mantém o
tradutor, o launcher e os modos de ampliação da r8. Os PRs
[#1762](https://github.com/NotRexed/Hookshot/pull/1762) e
[#1375](https://github.com/NotRexed/Hookshot/pull/1375) orientaram a adaptação
das leituras capturadas. O cache de palavras evita o lock nos acertos,
com invalidação pela geração da captura, e quatro páginas recentes
evitam novas buscas no mapa. Os ponteiros para as capturas só são usados
sob o lock.

O limite experimental de write-back por binding reproduz a opção do
[#1629](https://github.com/NotRexed/Hookshot/pull/1629). A apresentação
ignora filtragem espacial em 1:1 com nitidez zero, e ajusta o retângulo
Vulkan à proporção da imagem. O painel F1 usa organização do menu de
referência com tema do launcher Akyno. Os ganchos locais derivados de
PR849 foram estendidos para observar altura e largura da saída, com
modos 1280×720 e 2560×1600 e aspecto 16:10 para o último.

## Linhas do menu do Hookshot v2.1.0 no painel F1 (r9)

Base: a candidata "4K, F1 e resolucao" aplicada sobre a r8 (hashes de `ajuste-210/arquivos.json` conferidos). As linhas
abaixo vem do menu do Hookshot v2.1.0 (`gpu/vk/vk_menu.cpp`, GPL-3.0); os textos em portugues, o desenho do painel e a
ligacao com este motor sao deste projeto. `gpu/vk/vk_api.h` nao mudou: o carimbo de shaders continua `4cdbb0029868040b`.

- `gpu/vk/menu_option_ids.h` (novo): ids 64 a 71 que o host pergunta ao renderizador por `rx_option` (o Hookshot usa 4 a
  28 no `vk_api.h`; aqui 4 a 6 ja sao o jitter dos modos temporais), e a conta de cada linha (zona morta, vibracao, curva
  do volume, taxas do limite de FPS), de `host/nn_hid.c`, `host/pad_sdl.c` e `host/nn_audio.c` do Hookshot.
- `gpu/vk/boot_options.h` (novo): linhas lidas do `AkynoLeyend_opts.ini` antes de o painel carregar o arquivo.
- Limite de FPS do jogo (`frame_rate_cap`, 60/90/120/144/165/240, ao reiniciar): `host/nn_vi.c` (`fps_max`: ritmo de
  apresentacao, limitador do jogo em +0xfc, evento de vsync) e `nx2/oot_patches.py` (`STEP_SITES`: o passo de tempo dos
  dois divisores `f_80706be0` e `f_83b6ea90` vira base * segundos do quadro). O limite so passa de 60 depois que o codigo
  traduzido registra `hos_step_probe`; sem o gancho fica em 60. O ajuste do contador de quadros dos filmes
  (`hos_movie_frames`, issue 1742 do Hookshot) nao foi trazido: acima de 60 a narracao de cenas com filme pode adiantar.
- Filtro anisotropico (`anisotropic_filtering`, ao reiniciar): `vk_draw.cpp` `aniso_override`; `RX_VK_ANISO` por cima.
- Placa de video (`gpu_device`, ao reiniciar) e Buffers robustos (`robust_buffers`, ao reiniciar): `vk_main.cpp`.
- Predefinicao (`quality_preset`): ajusta escala, filtro, nitidez e perfil no painel; os limites de memoria
  (`preset_vram_mb`, `preset_mirror_mb`) so reduzem os orcamentos e valem ao reiniciar (`vk_texture.cpp`, `vk_memory.cpp`).
- Volume e Silenciar em segundo plano: `host/nn_audio.c`, ganho em rampa por quadro de audio, lido a cada 100 ms.
- Controle em segundo plano, Inverter mouse vertical, Inverter camera X/Y, Zona morta do analogico: `host/nn_hid.c` e
  `host/pad_sdl.c`. Forca da vibracao: `host/pad_sdl.c` (controles lidos pelo SDL).
- Tamanho do menu: um passo inteiro de escala a menos ou a mais no painel e no contador de FPS, quando a janela comporta.
- Paginas do painel: Tela, Ampliacao, Audio, Jogo, Controles. Linhas lidas so na abertura mostram "reinicie" enquanto o
  valor salvo difere do valor em uso.

Nao trazidas nesta rodada, por dependerem de partes do motor 2.1.0 que esta base nao tem: HDR, NVIDIA Reflex, AMD Anti-Lag 2,
modelo do DLSS, menus em ultrawide, Mesh shaders (esta base nao tem o caminho por compute), saida de audio 5.1, velocidade e
tamanho do texto, microfone, status no Discord, camera nativa pelo mouse, sensibilidade do mouse pelo painel, controles de
movimento (giroscopio), atalho do menu e as ferramentas de depuracao.

## Correção incremental da r9

- Os guardas de largura e altura de `nx2/oot_output_size.py` mantêm o backport do Hookshot PR849.
- A manutenção da r9 valida os oito pontos já emitidos e atualiza os dois guardas que só comparavam largura. Recompila apenas os blocos afetados e os componentes nativos alterados.
- A janela Win32 usa proporção 16:10 no modo 2560×1600. O launcher respeita a escala explícita com o filtro temporal correspondente.
- O Builder inclui as duas saídas, as opções de FSR 4.1 e a sincronização das escolhas do F1. A DLL Vulkan é a da r9, com o identificador de cache de shaders `4cdbb0029868040b`.


## r10: atualizador e mais linhas do menu do Hookshot v2.1.0

- Atualizador (`akynoleyend/updater.py`): pastas `atualizacoes/pendente-*` conferidas e nunca instaladas (sem `anterior/`)
  ficavam para sempre, com o pacote inteiro; o `stage-update` seguinte as remove (`clear_abandoned`) e mantem as que guardam
  arquivos para reverter. `apply-update` grava `ultima-atualizacao.log` desde o primeiro passo (antes so o `maintain-build`
  o abria, e uma falha anterior deixava apenas a caixa de mensagem e o log da vez passada). A remocao da pasta temporaria e
  a reabertura do launcher vem depois de os arquivos estarem no lugar e nao fazem mais uma atualizacao instalada aparecer
  como interrompida.
- Limite de FPS depois de atualizar por ZIP: a atualizacao nunca traduz o jogo de novo, e a `work` traduzida antes da r9 nao
  tem o gancho de `nx2/oot_patches.py`; o limite ficava em 60 sem aviso. `nx2/upgrade_output.py` (`step_edits`, `--step-only`)
  aplica o mesmo patch do lifter nas duas divisoes, as duas ou nenhuma, e recompila so esses blocos com o cache de objetos;
  `akynoleyend/maintenance.py` pede isso enquanto a `work` nao tem o marcador `akyno-frame-step-v1`.
- Linhas novas no F1, do `vk_menu.cpp` do Hookshot v2.1.0: Modelo do DLSS (`dlss_model`: Automatico, K, M, L, padrao da
  NVIDIA; `vk_fsr_sdk.cpp` `dlss_preset`, ao reiniciar; `AKYNO_DLSS_PRESET` por cima), Sensibilidade do mouse
  (`mouse_sensitivity`: as teclas - e = como antes, ou 25% a 300%; `host/nn_hid.c`) e Atalho do menu (`menu_shortcut`: F1,
  Insert ou Ctrl+M; so F1; ou tambem Esc, que so abre).

Ainda nao trazidas: HDR, NVIDIA Reflex, AMD Anti-Lag 2, menus em ultrawide, Mesh shaders, audio 5.1, microfone, velocidade e
tamanho do texto, camera nativa pelo mouse, giroscopio e ferramentas de depuracao.
## r11: ruido colorido na GTX 1650 e Reflex / Anti-Lag 2 do Hookshot v2.1.0

Origem: Hookshot v2.1.0, github.com/NotRexed/Hookshot, tag v2.1.0, commit 8ef84611049f4fc31835a0b12793cf074ed49c3c
(GPL-3.0, a mesma licenca deste projeto; avisos e creditos preservados nos arquivos copiados).

- Ruido colorido com o HUD limpo (GTX 1650, Teste 4 r3, Diagnostico(1).zip): a rede de ampliacao do perfil portatil
  (`0775215f8da720e6`) fica de fora em placas sem matrizes cooperativas, e o `upscale_stub` de `gpu/vk/vk_draw.cpp` a trocava
  por um blit linear da entrada. A entrada e a cor da cena em RGB9E5 (NVN 0x40) escrita sobre uma imagem criada R11G11B10F
  (vk 122): o blit lia as palavras 9E5 como floats 11/11/10. O defeito nasce antes do FSR 1 (`vk_framegen.cpp`): aparece com e
  sem ele. `rgb9e5_upscale` amostra a entrada pela vista RGB9E5 do proprio descritor e desfaz a raiz quadrada da rede com o
  shader do substituto do TAAU (`shaders/taau_upscale.comp`, sem historico). `RX_VK_NO_9E5_STUB=1`: o blit como antes.
  Reproduzido e corrigido na RTX 5070 Ti com `RX_VK_NO_F16=1` (o mesmo caminho da GTX), perfil portatil, 1080p, 50%, com
  FSR 1 ligado e desligado; nao executado numa GTX 1650.
- NVIDIA Reflex e AMD Anti-Lag 2: `gpu/vk/vk_reflex.{h,cpp}` e `gpu/vk/vk_antilag.{h,cpp}` copiados sem mudanca; chamadas em
  `vk_main.cpp` (extensoes, cadeia de features, criacao do dispositivo e da swapchain) e `vk_replay.cpp` (marcadores, id do
  present, sono do driver depois do present, estagios do Anti-Lag), como no `vk_main.cpp` e `vk_replay.cpp` do Hookshot.
  Linhas do F1 `NVIDIA Reflex` e `AMD Anti-Lag 2` (sem reiniciar; "Indisponivel nesta placa" sem a extensao).
- Modelo do DLSS (r10): validado na RTX 5070 Ti com o runtime oficial baixado pelo launcher: DLSS Performance com K e DLAA
  com L aparecem no log ao criar o recurso do DLSS.

Ainda nao trazidos: SDL2/SDL3 (giroscopio, audio 5.1, microfone; o download do sdl2-compat 2.32.74 e do SDL 3.4.20 nao foi
feito), camera nativa pelo mouse, velocidade e tamanho do texto, HDR, menus em ultrawide, Mesh shaders por compute e as
ferramentas de depuracao.
## r12: SDL do Hookshot v2.1.0 (controles, giroscopio, microfone)

Origem: Hookshot v2.1.0, commit 8ef84611049f4fc31835a0b12793cf074ed49c3c (GPL-3.0). SDL baixado das fontes oficiais com a
autorizacao do usuario: sdl2-compat 2.32.74 (`SDL2.dll`) e SDL 3.4.20 (`SDL3.dll`), win32-x64, SHA-256 dos ZIPs conferidos
contra os publicados pelo GitHub (94a0184b...1cc0 e 368bed8b...4752); licenca zlib em `third_party/sdl2/LICENSE.txt`.

- Antes: `third_party/sdl2` tinha so a licenca. O `SDL2.dll` nunca ia ao lado do jogo e so controles XInput funcionavam
  ("SDL2.dll not found next to the exe"). Agora `nx2/build.py`, `akynoleyend/build.py` e `akynoleyend/maintenance.py`
  publicam `SDL2.dll` e `SDL3.dll`.
- Copiados sem mudanca: `host/hos_sdl.c/.h` (SDL3 ou SDL2 por tras de uma interface), `host/hos_motion.h` (filtro de
  Mahony do Eden), `host/hd_rumble.h`. `host/pad_sdl.c` da 2.1.0 com uma unica adaptacao: os numeros de opcao do Hookshot
  (`HOS_OPT_GYRO*`, 9, 11, 16, 17) viram os do painel (`gpu/vk/menu_option_ids.h`), e a zona morta usa `akyno_stick_axis`
  (r9). `vk_api.h` nao muda.
- `host/nn_hid.c`: `GetSixAxisSensorHandles` (tres handles: o OoT so liga o caminho de movimento com tres) e
  `GetSixAxisSensorStates` da 2.1.0, alimentados por `hos_sdl_motion_history`; `hos_sdl_rumble_hd` na vibracao.
- `host/nn_audio_in.c` da 2.1.0 (os fluxos de entrada de audio da ocarina) com `hos_mic_follow_panel` no fim: a linha
  Microfone do F1 (Desligado / Padrao do sistema) por `rx_option`. Escolher um microfone pelo nome usa no Hookshot funcoes
  novas da interface do renderizador e nao foi trazido. `hos_guest_range` de `host/hos.h` da 2.1.0.
- Os stubs de import (`a64_stubs.c`, codigo gerado) sao refeitos pelo proprio gerador da traducao (`nx2/standalone.py`
  `stubs_text`) a partir de `work/sa/image/image.json` quando o host passa a definir um import que eles ainda cobrem; a
  atualizacao recompila so esse arquivo (`nx2/upgrade_output.py` `stub_edits`).
- Linhas do F1: Controles por movimento, Sensibilidade X/Y, Inverter X/Y, Zona morta do movimento (Controles) e Microfone
  (Audio).

Nao trazido: audio 5.1. O 5.1 do Hookshot e feito sobre a saida waveOut; esta base usa saida WASAPI propria
(`host/audio_wasapi.h`), e o caminho de saida precisa ser refeito e testado com caixas 5.1.

## r13: camera do mouse, texto, HDR e menus em ultrawide do Hookshot v2.1.0

Origem: Hookshot v2.1.0, commit 8ef84611049f4fc31835a0b12793cf074ed49c3c (GPL-3.0). Cada porte e feito por um script que
copia os arquivos do Hookshot e confere que cada adaptacao se aplica uma vez: `next/scripts/port_r13_hooks.py`,
`port_r13_hdr.py`, `port_r13_wide.py` e `port_r13_wide_host.py` (fora de `s/`, na pasta de trabalho).

- Ganchos no codigo traduzido, pelo gerador (`nx2/oot_patches.py` `PANEL_HOOKS`): velocidade e tamanho do texto
  (`f_80b1e140`), camera nativa pelo mouse (`f_80644c80`), desativar a centralizacao da camera e os tres pontos de
  ultrawide (HUD em `f_80794330`, filmes em `f_83b7c710`, imagem do save em `f_802a46e0`), com o texto C do Hookshot.
  Os de ultrawide vem do `nx2/oot_wide.py` do Hookshot, que os credita a Ivan0xFF (MIT, via NX2navi
  `recomp/patches-v111.txt`); o credito esta no gerador. No Hookshot eles entram durante a traducao (`Lifter.after`);
  aqui sao colocados por texto no C traduzido, o que tambem permite que uma atualizacao os aplique a um `work` antigo:
  `nx2/upgrade_output.py` `hook_edits` recompila so os blocos afetados (stamp `akyno-panel-hooks-r13-v2`). Dos onze
  pontos do Hookshot, os tres de tamanho da imagem e os cinco de proporcao da camera ficaram de fora: esta base mantem a
  propria resolucao de saida (`nx2/oot_output_size.py`) e a constante de proporcao (`host/hos_main.c`).
- Host: `host/mouse_native.c` e `host/oot_text_size.c` copiados (opcoes pelos ids de `gpu/vk/menu_option_ids.h`, 80 a
  86); velocidade do texto em `host/nn_vi.c`; `host/nn_hid.c` escolhe entre o mouse como analogico e o mouse nativo e
  avisa quando a roda de habilidades esta aberta; `hos_wide_ratio/squeeze/margin/keep_mask` em `host/hos_main.c`;
  `QueryDisplayHdrStatus`/`QueryDisplayHdrPaperWhite` respondem HDR10 so com a linha HDR em Nativo.
- Renderizador: `shaders/hdr_encode.comp` e o cabecalho compilado copiados; `framegen_hdr` com as imagens da base;
  superficie HDR10 (`VK_EXT_swapchain_colorspace`) so com a linha ligada e listada pela tela; o swapchain e refeito ao
  mudar a linha. O painel F1 e o contador de FPS sao pixels da CPU copiados sobre a imagem da janela: numa imagem HDR10
  sao codificados por `gpu/vk/hdr10_pixels.h` (a mesma curva do shader, sem a expansao dos realces). Para os menus em
  ultrawide, o `fg_scale.comp` do Hookshot (com o cabecalho compilado) foi copiado como `wide_sides.comp` e roda como
  passagem propria depois do filtro da base; o mundo desenhado e detectado pelas mesmas chaves de programa do Hookshot
  (`vk_draw.cpp`). A pergunta do host ao renderizador e a exportacao `akyno_wide_menus`, como `akyno_before_exit`:
  `vk_api.h` nao muda e o stamp de shaders continua `4cdbb0029868040b`.
- Linhas do F1: Velocidade e Tamanho do texto (Jogo); Camera do mouse e Desativar centralizacao da camera
  (Controles); HDR, HDR: branco de papel, HDR: brilho de pico e Menus em ultrawide (Tela). Todas valem na hora.

Testado no jogo (RTX 5070 Ti Laptop, tela 2560x1600 SDR, copia dos saves): texto em 125% e 175%, Instantaneo e volta a
Original com o dialogo aberto; camera nativa com movimentos aplicados; centralizacao desligada; Esc solta o mouse;
21:9 por `HOS_ASPECT=2.3889` numa janela (HUD e menus em 16:9 no meio, as tres opcoes da linha); saida 2560x1600. A
passagem HDR foi conferida forcando-a numa tela SDR (`RX_VK_HDR_PREVIEW=1`): os codigos PQ batem com a formula do shader
(mediana 1,5 de 255). Sem tela HDR, nem monitor ultrawide fisico.

Nao trazidos nesta rodada: as ferramentas de depuracao e o audio 5.1.

### r13b: Mesh shaders por compute (Hookshot v2.1.0, issue 640)

Origem: o mesmo commit 8ef84611. Scripts: `next/scripts/port_r13_mesh_eden.py`, `port_r13_mesh_emitter.py`,
`port_r13_mesh_renderer.py`, `port_r13_mesh_draw.py` e `port_r13_mesh_menu.py`; aplicados as fontes da instalacao com r13
reproduzem `gpu/vk` byte a byte.

- Tradutor (Eden): `RuntimeInfo::mesh_fallback`, `mesh_fallback_vertex`, `_task`, `_task_threads` e `_capacity`;
  `MeshInfo::Corners()`; as constantes `MESH_FALLBACK_*` (bloco de push depois do bloco comum, cabecalho e registros);
  os programas de task e mesh viram compute que gravam os vertices num buffer, e um estagio de vertice gerado le esses
  registros. Todo codigo novo roda so com essas flags; do `emit_spirv_mesh.cpp` do Hookshot foram trazidos apenas os
  ramos do fallback, nao as mudancas do caminho nativo.
- Renderizador: `vk_main.cpp` escolhe o caminho ao criar o dispositivo (linha do F1, `mesh_shaders=` em
  `AkynoLeyend_opts.ini`; `RX_VK_FORCE_MESH_FALLBACK`, `RX_VK_NO_MESH_FALLBACK` e `RX_VK_TASK_MESH_FALLBACK` para teste;
  task + mesh por compute em Navi 22 no Windows, issue 996). Um programa do fallback tem `mesh = false` e e desenhado
  como programa grafico comum depois dos dispatches (`vk_draw.cpp`); so o layout dele tem o bloco de push maior. O
  cache de programas grava os campos do fallback apenas nos registros dele, e uma GPU no caminho por compute tem arquivo
  proprio (`disk_stamp` inclui o modo so quando o fallback esta em uso).
- Linha do F1: Mesh shaders (Tela): Automatico, Nativos ou Compute; vale ao reiniciar.
- Diferencas do Hookshot: os pipelines compute do fallback sao compilados no primeiro desenho (sem precompilacao nem
  compilacao assincrona deles), o que pode dar travadas curtas na primeira vez que cada um aparece.

Stamp de shaders: as fontes do tradutor mudaram, mas o stamp `4cdbb0029868040b` foi mantido pelo registro
`profiles/shader-cache-compatible.json`. Conferido numa RTX 5070 Ti: os 46638 programas da seed traduzidos pelas fontes
novas contra o cache feito pelas anteriores, 90278 conjuntos (chave, estagio), 0 modulos SPIR-V diferentes (task 1167,
mesh 1295, compute 4087, vertex 41206, fragment 42381). Sem o registro o stamp seria `3d504e04486d53a4` e todo cache
existente seria traduzido de novo.

Testado no jogo (RTX 5070 Ti Laptop, copia dos saves): Automatico usa os mesh shaders da placa, com 46607 programas do
cache aproveitados e 0 novos; Compute forcado desenha folhagem, arvores e grama (0 desenhos pulados, cerca de 2440
desenhos por quadro contra 2451 no nativo, FPS igual), com 40 pipelines compute compilados entre 51 e 713 ms. Seis
programas de mesh falham na traducao nos dois caminhos, como antes. Sem teste numa GPU sem mesh shaders (GTX 10xx,
RX 5000) nem numa Navi 22.

### r13c: cache de programas por caminho de mesh e pacote conferido ao preparar

Dois defeitos da r13b achados em revisao, corrigidos por `next/scripts/fix_r13c_mesh_cache.py`:

- Nativo, Compute e o caminho misto (Navi 22) tem carimbos de cache diferentes (`disk_stamp`), mas usavam os mesmos
  `AkynoLeyend_programs.bin`, `AkynoLeyend_pipeline_keys.bin` e `AkynoLeyend_prepared.bin`: cada troca da linha Mesh shaders
  recomecava esses arquivos e perdia o cache nativo. Agora `program_cache_file` mantem os nomes atuais no caminho nativo e
  usa `_compute` e `_mixed` antes de `.bin` nos outros. O cache de pipelines do driver (`AkynoLeyend_pipelines.bin`) continua
  um so: ele e conferido por dispositivo e guarda pipelines dos dois caminhos.
- O indice do arquivo aceitava so os tipos de registro 0 a 3, e o fallback grava 4 e 12: cada abertura em Compute traduzia
  esses programas de novo. Gravador, indice e leitor usam agora a mesma codificacao (`record_kind`, `kRecordKinds`).

Nada disso muda a traducao; o registro do stamp passou para a identidade nova das fontes com o mesmo `4cdbb0029868040b`.

Atualizador (`akynoleyend/updater.py`): ao preparar um pacote, o jogo instalado e conferido contra a lista de revisoes
conhecidas do `coherence.py` do pacote (lido como texto, sem rodar codigo dele). Um pacote mais antigo que a revisao
instalada era recusado so depois de o launcher fechar e de todos os arquivos serem trocados, com uma mensagem que nao dizia
o motivo; agora e recusado antes, sem mudar nada. Depois de uma reversao completa, as copias em `anterior/` sao apagadas, e
a pasta pendente sai na proxima preparacao (antes ficava para sempre).

### r13d: registro da perda de dispositivo e caches por GPU

Caso analisado: sessao `20261112-111211` de um notebook com RTX 5070 Ti Laptop e Intel(R) Graphics (Core Ultra 9 275HX),
codigo 70. A linha Placa de video do F1 estava em `gpu_device=2`, a Intel integrada (`vk: device 1 chosen`). O cache de
programas da RTX foi descartado (`0 program keys kept`), 46536 programas foram traduzidos de novo em 1797,8 s e o jogo
perdeu o dispositivo cerca de 30 s depois, logo apos o primeiro ASTC decodificado na GPU (`slow upload 508.3 ms`). A causa
da perda na Intel nao ficou registrada; os dois defeitos abaixo vieram dessa sessao.

- Log (`host/rx_backend.c`, executavel): o renderizador encerra com `std::_Exit` (70 na perda de dispositivo, 0 ou 71 no fim
  da preparacao), que nao roda o `atexit` que grava a fila assincrona do log (`host/hos_thread.c`). A linha `GPU_FATAL`, os
  checkpoints e `PREPARE_COMPLETE` nunca chegavam ao `erros.log`. A partir da primeira linha `GPU_FATAL`, `vk: device lost`,
  `PREPARE_FAILED` ou `PREPARE_COMPLETE`, cada linha do renderizador e gravada na hora (`hos_log_flush`). A API do
  renderizador nao mudou.
- Launcher (`akynoleyend/launch.py`): saida 70 sem a linha no log passa a ser registrada como `runtime_failure` de perda de
  dispositivo, porque 70 so vem de `check_device_result` (`gpu/vk/vk_replay.cpp`).
- Caches (`gpu/vk`): o carimbo dos programas e o cabecalho do cache do driver incluem o dispositivo, mas o nome do arquivo
  nao. Escolher outra GPU zerava `AkynoLeyend_programs.bin` (5,8 GB na RTX), as notas de pipeline, o marcador de preparacao
  e o cache do driver, e a volta para a GPU anterior traduzia tudo de novo. `device_file_tag()` (`vk_main.cpp`) e vazio para
  o dispositivo que o Automatico escolhe, entao os arquivos atuais continuam validos. Outro dispositivo usa
  `_gpu<fabricante><dispositivo>` em hexadecimal antes de `.bin`, por exemplo `AkynoLeyend_programs_gpu8086xxxx.bin` para uma Intel (fabricante 0x8086).

Stamp de shaders: so `program_cache_file` mudou em `vk_shader.cpp`; no registro `profiles/shader-cache-compatible.json` o stamp
`4cdbb0029868040b` passa da identidade `b81c50bf` (r13c) para a nova `a40b759f`.

DLL generica (`ferramentas/prebuilt`): compilada com `nx2/build.py --standalone`, `RX_VK_ONLY=1`, `RX_RELEASE=1`,
windows-gnu, x86-64-v3, clang 23.1.4 do LLVM-MinGW incluido e o NVIDIA DLSS SDK v310.9.16 (github.com/NVIDIA/DLSS, commit
`9981c635`, `lib/Windows_x86_64/x64/nvsdk_ngx_s.lib` em `third_party/nvidia-dlss-sdk`, fora dos pacotes). Antes, os fontes
r13c foram compilados do mesmo modo e pela mesma raiz da DLL r13c (`C:\Users\mayco\akdev\s`): o resultado difere da DLL
publicada `18de8b2f` so no TimeDateStamp e no carimbo do `.buildid` (6 bytes), entao o ambiente reproduz aquela DLL. A DLL
r13d (`2e47fbf8`, 6245376 bytes) tem os mesmos 17 imports e o mesmo carregador NGX; `renderer.json` leva a identidade de
fontes `c80866a7`. Nao foi executada com o jogo nem testada numa GPU.

Atualizador: `coherence.py` passa a listar a identidade da r13c instalada (`aeef577d`, a do manifesto da sessao do codigo 70
e a dos fontes r13c); sem ela o pacote r13d seria recusado em toda instalacao r13c.

Criar da r13c numa instalacao nova (12/11/2026, RTX 3060 Ti, 6 nucleos): a extracao do `.nup` terminou (186592 arquivos,
26,27 GB, ZBIC do main convertido), mas a fase `inputs` falhou logo depois (`build-timings.json`: failed, 936,8 s); a pasta
temporaria foi limpa e a mensagem ficou so na tela do launcher. Entre a extracao e a publicacao restam `verify_version`, a
escrita de `input.json` e `stage.replace` da pasta inteira. Causa nao determinada; repetir guardando a mensagem. A causa da perda de dispositivo na Intel integrada continua sem
diagnostico: com esta revisao, a proxima ocorrencia deixa a operacao Vulkan e os checkpoints no log.

### r13e: controle de VRAM

Caso analisado: sessao `20261112-134859` da instalacao Teste-1 atualizada para r13d (RTX 3060 Ti 8 GB, driver 616.92, Ryzen 5
3500X de 6 nucleos, 16 GB de RAM, 6,5 GB livres no inicio). FPS base mediano 18; envios e uploads de 0,4 a 4 s. `vk: memory
heaps`: 8003 MB usados de 7090 permitidos na VRAM, 6,2 GB no heap do sistema; o processo chegou a 21,3 GB privados com 4,5 GB
de working set e 726 MB de commit livre. Na VRAM: texturas de 2,8-3,3 GB contra um orcamento de 0,8-1,6 GB (as usadas em 8
quadros eram 2-2,4 GB e o despejo so tirava as sem uso ha 60), 1,4-2,9 GB livres dentro dos blocos do VMA (o driver conta o
bloco inteiro enquanto houver uma imagem nele; `vram_pressure.h` ja anotava isso para as sombras), ASTC decodificado em RGBA8
1,3-1,85 GB, espelhos 1,3 GB.

- `gpu/vk/vram_policy.h` (novo, testado compilado): niveis pela contagem do driver (90% pressionado, 97% critico, acima do
  permitido), classe de placas ate 8 GB (com folga de 512 MB), escolha dos blocos a esvaziar.
- `vk_vma.cpp`: o pool de imagens conta o que esta alocado em cada bloco (`create_image`/`destroy_image`) e loga
  `vk: image pool: N blocos, imagens, buracos`. Blocos de 64 MB em placas ate 8 GB (128 MB acima; `RX_VK_IMAGE_BLOCK_MB`).
- `vk_texture.cpp`, `texture_frame`: o nivel e logado quando muda (`vk: VRAM pressure ...`). Critico ou acima, com mais de 256 MB
  de buracos: compactacao, no maximo a cada 60 apresentacoes, ate 90% do permitido. Esvazia so blocos em que toda imagem e
  textura que a memoria do jogo refaz (enviada, nunca escrita pela GPU, nao esparsa, fora do pool de render targets, sem uso
  ha 8 apresentacoes e ja lida pelo trabalho gravado), menos bytes primeiro (`vk: VRAM compaction ...`; `RX_VK_NO_COMPACT=1`
  desliga). Do critico em diante o despejo comum aceita texturas sem uso ha 8 apresentacoes em vez de 60.
- ASTC de blocos finos (4x4, 5x5) vira BC3 a partir de 8 MB em placas ate 8 GB, em vez de 64 MB (`RX_VK_ASTC_BC_FINE_MB`).
- `vk_memory.cpp`: acima do permitido nenhum espelho novo e criado; os existentes ficam (sem eles placas de 8 GB liam a memoria
  do jogo pelo PCIe). A regra de 90% (`RX_VK_MIRROR_TIGHT`) continua opcional.
- `coherence.py` lista a r13d instalada (`7f647493`).

Shader stamp inalterado (`4cdbb0029868040b`: nenhum arquivo da identidade do tradutor mudou). DLL generica `3561653d`
(6269440 bytes), mesmo processo e SDK da r13d, NGX presente; `renderer.json` com identidade `9535ecb3`. Nao foi executada com
o jogo: o efeito nas travadas ainda precisa ser medido na mesma rota, comparando `vk: memory heaps`, `vk: image pool` e o FPS
base com a sessao `20261112-134859`.

Medido na sessao `20261112-143434` (r13e, mesma rota e opcoes): FPS base mediano 19,7 (era 18,0), p90 28,4 (26,1), uploads
lentos 14 (46); uma travada de 9,6 s numa troca de area com 723 MB de RAM livre. A compactacao esvaziou 1 bloco por vez, 5
vezes (quase todo bloco guarda uma imagem que nao pode sair); 0,5-1,3 GB de buracos no pool de imagens; o nivel oscilou entre
critico e acima do permitido a cada poucos quadros. O processo chegou a 20,8 GB privados e 12 GB de working set.

### r13f: mesh shaders que desenham pontos

Caso: as arvores sem chao da captura de 12/11/2026 (RTX 3060 Ti, caminho nativo de mesh shaders). Em toda sessao, 2 desenhos
por quadro saem por `vk_draw.cpp` "a draw without a program": os programas de mesh `02ee95fb` e `b0b3b402` (fragmentos
`d7fb6538`/`ed01e3e8` e `91d8621e`/`644dba7a`), recusados com `Mesh output topology 0 (SET_MESH_SHADER_A 0x00040200)`; a
sessao do RTX 5070 Ti mostrou quatro programas assim (`b93e0f0c`, `ed83a335` tambem), os quatro mesh de pontos do banco
anotados em `ESTUDO-GRAFICO-20261109.md`.

O backport da issue 302 (Hookshot v2.0.6, acima) trouxe a topologia NVN2 1 como pontos (`mesh_registers_of`) e as
coordenadas do point sprite nos generics nao escritos, mas nao a aceitacao no Eden: `translate_program.cpp` so tomava linhas e
triangulos, e a emissao escolhia so entre esses dois. Portado do Hookshot v2.1.0 (`8ef84611`, GPL-3.0, a mesma base):

- `frontend/maxwell/translate_program.cpp`: topologia 0 aceita.
- `backend/spirv/emit_spirv.cpp`: `OutputPoints`, `OutputLinesEXT` ou triangulos por `MeshInfo::Corners()`.
- `backend/spirv/spirv_emit_context.cpp`: mapa de `4 + Corners() * primitivos` bytes; `PrimitivePointIndicesEXT` para pontos.
- `backend/spirv/emit_spirv_mesh.cpp`: indices por `Corners()`, o de um ponto escrito como escalar.
- Acrescimo local: um programa de pontos que nao escreve `PointSize` escreve 1,0 em cada vertice
  (`mesh_point_size_default`), como os vertex shaders recebem (`fixed_state_point_size`); sem `VK_KHR_maintenance5`, que o
  dispositivo nao liga, uma saida de pontos precisa escrever o tamanho.

Shader stamp mantido (`4cdbb0029868040b`): `Corners()` da 2 para a topologia 1 e 3 para a 4, como as expressoes trocadas, e
um programa de topologia 0 era recusado, entao nenhum esta em cache (`program_cache_save` so roda com sucesso). Garantia por
construcao, nao medida modulo a modulo; o registro passa da identidade `a40b759f` para `ddcef176`. Os quatro programas sao
traduzidos na primeira abertura e entram no cache. O comentario do Hookshot diz que esses pontos sao sprites de sombra da
grama: que sejam o chao que falta sob as arvores ainda nao esta comprovado; comparar a mesma vista antes e depois e conferir
que "a draw without a program" sumiu do log.

DLL generica `3bf04225` (6269952 bytes), mesmo processo e SDK da r13d; `renderer.json` com identidade `2183e188`.
`coherence.py` lista a r13e instalada (`eb9fe478`). Nao foi executada com o jogo.

Sessao `20261112-152648` (r13f): nenhum "a draw without a program" e nenhum "Mesh output topology 0", mas a linha Mesh shaders
do F1 estava em Compute desde a sessao de 14:34 (`mesh_shaders=2`): o caminho por compute, 8826 programas traduzidos (41 s,
cache `_compute`), travadas de 35 e 42 s; o caminho nativo da r13f nao foi exercitado. As arvores sem chao aparecem nos dois
caminhos, entao nao vem dos mesh de pontos.

### r13g: finalizacao por objeto de textura, nivel de VRAM com margem

Causa provavel das arvores sem chao (nao corrigida aqui): o workaround de oclusao (`AKYNO_OCCLUSION_OFF=1`,
`nx2/oot_occlusion.py`) desliga as consultas de oclusao do jogo e todo objeto candidato e desenhado; o renderizador nao tem
contagem real (16 amostras por desenho). O outro porte do mesmo jogo (OoT 1.1.1, NX2navi) registra que o jogo faz centenas de
relatorios de oclusao por quadro e que um relatorio errado "descartou chao e arvores visiveis": a visibilidade deles depende
da oclusao, e o porte conta com consultas de oclusao do Vulkan entre o RESET e o REPORT. Sem codigo copiado (as adicoes dele
nao tem licenca); a implementacao propria fica para a proxima revisao, depois do teste A/B com `--visual-mode comparison`.

- `vk_texture.cpp` `texture_released`: a finalizacao de uma textura marcava por endereco toda imagem escrita pela GPU naquela
  memoria. O jogo inicializa o proximo objeto na memoria do anterior antes de finalizar o anterior (render targets da
  resolucao dinamica, a cascata de sombra), e a imagem que o novo acabara de desenhar recebia por cima o que a CPU tinha na
  memoria: 37-72 "upload over a drawn image ... finalized" por sessao (960x540, 240x135, o DEPTH16 1600x1600 da sombra),
  imagens piscando. Agora `texture_initialized` (chamada em `texture_created_of`, na thread do jogo) guarda o objeto mais novo
  por endereco, pelo serial (um por inicializacao, crescente: `nvn_native.c new_serial`); a finalizacao de um mais velho deixa
  a imagem de mesmo formato do mais novo como esta. Os registros do banco ja eram por serial (`vk_bank.cpp`).
  `RX_VK_RELEASE_BY_ADDRESS=1`: como antes.
- `vram_policy.h` `vram_level_held`: o nivel sobe na hora e so desce 2% abaixo da linha do nivel (98, 95, 88%); na r13e ele
  oscilava entre critico e acima do permitido a cada poucos quadros.
- ASTC de blocos finos em BC3 a partir de 2 MB em placas ate 8 GB (era 8 MB): quase todo ASTC comprimido, como o outro porte
  faz abaixo de 20 GiB de VRAM.
- `coherence.py` lista a r13f instalada (`08ae7037`).

Shader stamp inalterado (nada da identidade do tradutor mudou).

### r13h: amostras passadas por consultas de oclusao

O contador de amostras passadas do NVN (`NVN_COUNTER_TYPE_SAMPLES_PASSED`) passa a ser contado pela GPU, e o modo visual
padrao (`patched`) liga de novo as consultas de oclusao do proprio jogo (`AKYNO_OCCLUSION_OFF=0`). O modo `sem-oclusao`
guarda o comportamento antigo (`Jogar.cmd --visual-mode sem-oclusao`); `RX_VK_OCCLUSION=0` volta a contagem antiga (16 por
desenho) no renderizador. Implementacao propria, a partir da semantica do contador do NVN e da especificacao do Vulkan; do
outro porte (NX2navi) vieram so a constatacao de que este jogo descarta chao e arvores pelas contagens e o desenho geral
(consultas entre RESET e REPORT, contagem gravada depois da GPU, condicao pendente renderiza), sem codigo.

- `gpu/vk/vk_occlusion.cpp` (novo): pool de 16384 consultas `VK_QUERY_TYPE_OCCLUSION` (precisas se o dispositivo tem
  `occlusionQueryPrecise`), zeradas pelo host (`hostQueryReset`). Depois do primeiro RESET, o primeiro desenho de cada passe
  abre uma consulta, que fecha no fim do passe ou no proximo RESET/REPORT. As consultas fechadas e o RESET ou REPORT formam
  uma entrada na fila, em ordem, com o valor da linha do tempo da submissao. `occlusion_collect` (a cada gravacao e nas
  esperas do jogo, `wait`) toma as entradas cujo valor ja passou: soma os resultados, zera no RESET e grava
  `{contagem, timestamp}` no REPORT. Um desenho que devia contar e ficou de fora (pipeline nao pronto, anel cheio) faz o
  relatorio valer pelo menos 1, para nao esconder o que nao foi testado (`occlusion_count.h`, testado compilado).
- `vk_draw.cpp`: `occlusion_draw_in_pass` logo depois de `begin_pass` no desenho do jogo; `occlusion_pass_end` antes de
  `vkCmdEndRendering`. Toda gravacao termina com `end_pass` antes de ser submetida, entao nenhuma consulta cruza command
  buffers.
- `vk_replay.cpp`: REPORT de amostras vai para o modulo (as palavras continuam do replay: `memory_cpu_owned`, sem
  write-back por cima); RESET tambem; os quatro desenhos contam como perdidos quando o desenho foi pulado; uma condicao de
  render que le um relatorio de amostras ainda nao gravado renderiza. Os relatorios de timestamp seguem gravados na ordem do
  stream, como antes. So o replay serial: com `RX_VK_PARALLEL` fica a contagem antiga.
- `coherence.py` lista a r13g instalada (`6cb74d1d`).

Riscos: a contagem e feita na resolucao interna (o jogo so compara com 0); o jogo pode passar a descartar algo que deveria
aparecer se uma contagem sair 0 por engano (o modo `sem-oclusao` volta ao antigo). Nao executado com o jogo.

### r13i: sono curto em CPU de ate 6 nucleos, arvores sem chao, descarte so do excesso de VRAM

Tres mudancas adaptadas do Hookshot (GPL-3.0, a base), escolhidas pelo diagnostico de 12/11/2026 (Ryzen 5 3500X de 6
nucleos sem SMT, RTX 3060 Ti 8 GB): a Cidade do Castelo com 6-17 FPS de base, a CPU em 85-94% e a GPU esperada 0,1 ms por
quadro; esperas de ate 250 ms por um nucleo virtual; o cache de texturas indo de 2936 a 2562 MB e voltando; e as arvores
no ar.

- Hookshot PR 2263 (`host/hos_thread.c`): com 6 processadores logicos ou menos na mascara do processo, os sonos de menos
  de 1 ms do proprio jogo (`SleepThread` do nn::os e do kernel, por `hos_sleep_logged`) esperam no timer de alta
  resolucao, em vez de ceder a vez em laco. Os trabalhadores ociosos do jogo dormem 20 us e olham a fila de novo (~7600
  vezes por segundo em Hyrule); cada laco desses ocupava um nucleo que o quadro precisava. Os sonos do host (limitador de
  quadros, audio) continuam cedendo a vez. `HOS_SHORT_SLEEP_TIMER`: nao definido, pela contagem; `1`, o timer para todos
  (o que a chave fazia antes); `0`/`off`/`false`/`no`/vazio, ceder a vez para todos. Antes qualquer valor ligava o timer.
  A parte de espera ativa do PR 2709 nao entrou: o proprio Hookshot mediu que com 6 processadores ou menos ela nao poupa CPU
  e mantem 20 us.
- Hookshot PR 1334 (`gpu/vk/eden/.../spirv_emit_context.cpp`): a funcao auxiliar de leitura da memoria global e emitida
  `Inline` nos estagios de tarefa e de malha (os de compute seguem `DontInline`, pelos 41 s de compilacao do NVIDIA).
  Sem isso, o compilador do NVIDIA dava ao programa de tarefa das arvores (`3cb76827`) o endereco errado na terceira
  leitura; a leitura dava 0 e cada celula visivel virava 256 arvores, desenhadas no ar. `EDEN_NX2_GM_INLINE=0` volta ao
  antigo (chave `EDEN_`, entra no stamp).
- Cache de programas (`gpu/vk/vk_shader.cpp`): o stamp `4cdbb0029868040b` fica (o registro move o conjunto de fontes
  `ddcef176` para `cef27234`), porque compute, vertice e fragmento traduzem igual. Os registros de tarefa e malha passam a
  levar o tipo 16 (`kKindMeshLoadsInlined`); um registro de tarefa ou malha sem ele fica fora do indice
  (`stale_mesh_record`), e so esses programas sao traduzidos de novo, uma vez. A marca de preparacao
  (`program_prepared_stamp`) difere da r13h, entao a primeira abertura prepara de novo e faz isso antes do jogo. Um leitor
  anterior a r13i ve o tipo 16 como desconhecido e deixa o registro no disco.
- Hookshot PR 2826 (`gpu/vk/vram_policy.h` `evict_target`, `vk_texture.cpp`): quando a regra dos 90%, o limite do driver
  (97%) ou a regra de commit baixam o orcamento de texturas, o descarte tira o excesso e mais 64 MB, nao um oitavo do cache.
  O tamanho do orcamento (padrao da placa, `RX_VK_VRAM_MB` ou o preset) continua pedindo 7/8. `RX_VK_EVICT_EXCESS=0`: como
  antes.
- `coherence.py` lista a r13h instalada (`3cd96182`). Teste: `tests/test_r13i_p0.py` (a escolha do sono, a regra dos
  registros e o alvo do descarte compilados e executados).

Riscos: os sonos do jogo ficam ~0,5 ms mais longos em CPU de ate 6 nucleos (o Hookshot mediu ganho la; aqui nao foi
medido). A primeira abertura retraduz os programas de tarefa e malha.

Instalada no Teste-1 em 12/11/2026 (Ryzen 5 3500X, RTX 3060 Ti 8 GB) e relatada funcionando pelo jogador; o
diagnostico dessa sessao ainda nao foi conferido (FPS, arvores, descartes). O pacote final acrescenta so a identidade
dessa instalacao (`23bc5eab`) ao `coherence.py`.

### r13j: nivel x86-64 escolhido pela CPU, e o codigo 0xC000001D explicado

Um PC de teste (RX 590, Teste 4 r3) fechava na abertura com `0xC000001D` (`STATUS_ILLEGAL_INSTRUCTION`): os registradores
do jogo todos em zero, a falha no codigo de inicio do host. O jogo, o host e o renderizador eram sempre compilados para
x86-64-v3 (`nx2/build.py`: AVX2, FMA, BMI1/2, LZCNT, MOVBE), e uma CPU sem essas instrucoes para na primeira delas. A DLL
pronta do pacote tambem e x86-64-v3 (9711 usos de registradores `ymm`; a mesma DLL compilada para x86-64 nao tem nenhum).

Como o Lichii e o Fritchii (GPL-3.0) tratam isso: os binarios de release sao genericos (x86-64 com SSE4.1 e CX16
obrigatorios; `YUZU_BUILD_PRESET` generic/v3/zen2/zen4/native no CMakeLists.txt) e o JIT (dynarmic) escolhe as instrucoes
em tempo de execucao. Uma recompilacao estatica nao tem JIT, mas e compilada no PC que a executa: a ideia reaproveitada e
o preset por CPU, escolhido automaticamente. Nenhum codigo deles foi copiado.

- `akynoleyend/cpu.py` (novo): uma sonda C compilada com o clang do pacote (sem `-march`, roda em qualquer CPU) le CPUID e
  XGETBV; `choose_march` da x86-64-v3 com tudo de v3 e o AVX ativo no Windows, senao x86-64-v2 (CX16, LAHF, POPCNT, SSE3,
  SSSE3, SSE4.1/4.2), senao x86-64. Nunca acima de v3. Sem a sonda (sem clang), nada muda: v3 como antes.
- `build.py` (Criar): poe `RX_MARCH` antes da traducao e da compilacao, registra `cpu_features` e `march` em
  `build-request.json` e `march` no manifesto. Abaixo de v3 a DLL pronta nao corresponde (`prebuilt.py` ja confere o
  `march`) e o `nx2/build.py` compila o renderizador dos fontes, sem NVIDIA DLSS (o SDK nao vem no pacote).
- `maintenance.py` (atualizacao): mantem o nivel do build (os objetos do jogo sao reaproveitados). Abaixo de v3 compila o
  renderizador dos fontes em vez de exigir a DLL pronta; em v3 numa CPU sem AVX2 avisa para usar Criar.
- `shader_prepare.py`: um build abaixo de v3 mantem o seu renderizador (nao recebe a DLL pronta x86-64-v3).
- `launch.py` (Jogar): antes de abrir, se a CPU nao tem o nivel do build, recusa com a explicacao e o que fazer (Criar).
  O caso comum e instantaneo (`IsProcessorFeaturePresent` com AVX e AVX2); senao, a sonda. Depois de uma saida
  `0xC000001D`, a tela de jogo encerrado diz o que falta (`@@error`) e o `execucao.json` guarda `runtime_failure`
  `illegal_instruction` com as instrucoes. `manage.py doctor` mostra o alvo para este processador.
- Conferido aqui: o host (38 arquivos), dois blocos grandes do codigo traduzido e a DLL do renderizador compilam e ligam em
  `-march=x86-64`; o FFmpeg do pacote ja e x86_64 generico (`--disable-asm`). Teste: `tests/test_r13j_cpu.py`.
- `coherence.py` lista o pacote final da r13i (`235ade6f`).

Riscos: x86-64-v2/x86-64 sao mais lentos (o FMA de precisao dupla do FPX1 usa o corpo exato em software sem FMA) e numa
CPU sem AVX2 o jogo deve rodar bem abaixo do que roda num Ryzen. Nao executado numa CPU sem AVX2: so a compilacao e a sonda
foram conferidas. Atualizar uma instalacao v3 nessa CPU nao basta: e preciso Criar (o launcher diz isso).

## Ramo Intel (paralelo a r13d-r13j, a partir da r13c)

Outro ramo de desenvolvimento partiu da mesma r13c e fez a sua propria r13d e r13e (`AkynoLeyend-Atualizacao-0.4.3-test.4-r13e.zip`, SHA-256 `7d9ab673...`). As secoes abaixo sao as notas desse ramo, como vieram no seu `docs/origem.md`; o que entrou na 0.4.4 e como esta na secao 0.4.4.

### Ramo Intel r13d: GPU integrada da Intel (Core Ultra 9 275HX)

Na Intel integrada (driver Vulkan 101.9150) o jogo saia com codigo 70 (`VK_ERROR_DEVICE_LOST`) e, quando chegava a floresta,
a cena aparecia com luz estourada, silhuetas pretas e o Link sem textura. Reproduzido aqui com o build de desenvolvimento,
numa pasta separada (`next/intel/jogo`), escolhendo a Intel pelo F1 e com Buffers robustos ligados.

Correcoes da traducao trazidas do Hookshot v2.1.0, que esta base nao tinha (`next/scripts/port_r13d_intel.py`):

- Limite de 1024 tentativas nos lacos de compare-exchange (Hookshot issue 17). Um endereco fora do buffer nunca devolve o valor
  esperado e o laco nao terminava; a Intel perdia o dispositivo no compute `499dbfd0721d2858`, ainda na tela de titulo.
- `gl_Position` com `Invariant` (o passe de cor repete a geometria do pre-passe de profundidade com teste EQUAL).
- Saidas de cor sem NaN nem infinito (um NaN se espalha pelo bloom).

No Hookshot as duas ultimas valem para placas que nao sao NVIDIA e para todas, respectivamente. Aqui as tres valem so para
placas que nao sao NVIDIA (`coopmat_init`), para a RTX gerar o mesmo SPIR-V. `RX_VK_NO_CAS_CAP=1`, `RX_VK_NO_INVARIANT=1` e
`RX_VK_NO_NAN_GUARD=1` desligam cada uma. O carimbo do cache de programas so muda quando alguma esta ligada.

Snapshot de uniformes por padrao na Intel sem espelho de VRAM (`next/scripts/fix_r13d_ub_snapshot.py`, como no PR 2464 do
Hookshot, posterior a v2.1.0): sem ele a Intel ainda perdia o dispositivo no compute `4b03b3040d7cf076`, que le memoria por uma
tabela de enderecos. `RX_VK_UB_SNAPSHOT=0` desliga e `=1` liga em qualquer placa.

Stamp de shaders: `4cdbb0029868040b` mantido pelo registro. Conferido numa RTX 5070 Ti com a seed traduzida de novo (46604
programas) contra o cache da r13c: 90276 pares (chave, estagio), 90133 modulos iguais e 143 em que o modulo novo e uma das duas
variantes que o arquivo antigo guardava, ou seja 0 modulos SPIR-V diferentes.

Testado no jogo, build de desenvolvimento, saida 1440p, Buffers robustos ligados, saves copiados:

- Intel antes das correcoes: codigo 70 ainda na tela de titulo (`499dbfd0721d2858`). So com as tres correcoes da traducao,
  codigo 70 mais adiante (`4b03b3040d7cf076`). Com elas e o snapshot de uniformes, duas partidas chegaram a floresta (a
  segunda a Kokiri) e fecharam com codigo 0, a 3-4 FPS. Sem o snapshot, com Mesh shaders em Compute ou com o espelho de VRAM
  forcado (`RX_VK_MIRROR=1`), a Intel ainda perdeu o dispositivo.
- RTX 5070 Ti com a DLL nova: nenhuma das correcoes liga, mesma imagem em Kokiri.

Ainda nao resolvido na Intel: o veu de luz em Kokiri (ceu estourado, objetos proximos pretos, Link escuro). Pelo despejo do
mesmo quadro nas duas placas (`RX_VK_DUMP_FILE`), a primeira diferenca clara e o compute `ee7764a6b1ef459c` (dispersao do
sol): na Intel sai uniforme e cerca de 34 vezes mais claro; o mapa de sombras 1600x1600 que ele le sai igual nas duas. A
partir do primeiro passe iluminado (`489438d734e2463a`) a cena fica cerca de 8 vezes mais clara. As camaras dos dois
despejos nao ficaram iguais, entao isso e pista, nao causa provada. Tambem nao foi testado com Buffers robustos desligados.

### Ramo Intel r13e: fim dos storage buffers na Intel e motivos de saida no launcher

Fim de um storage buffer na busca por endereco dos shaders (`next/scripts/fix_r13e_ssbo_end.py`). O back end vincula cada
storage buffer a partir do endereco arredondado para baixo no alinhamento da placa (`minStorageBufferOffsetAlignment`) e soma a
diferenca ao tamanho (`vk_draw.cpp build_descriptors`). A busca por endereco dos shaders (`spirv_emit_context.cpp define_body`),
porem, terminava o buffer em `arredondado + tamanho`. Os ultimos `endereco - arredondado` bytes nao eram encontrados nele e iam
para a tabela de paginas do guest, que le 0 onde nao mapeia nada. Na NVIDIA (alinhamento 16) e na AMD (4) um endereco do guest
nao perde nada; na Intel integrada (64) perdia ate 48 bytes por buffer. A correcao fica atras de uma flag
(`mma_layout.h ssbo_end_unaligned`) ligada so quando o alinhamento passa de 16; o carimbo do cache de programas ganha o bit 16
quando ela esta ligada. `RX_VK_SSBO_END_ALIGNED=1` volta ao comportamento anterior.

Stamp de shaders: `4cdbb0029868040b` mantido pelo registro. Conferido numa RTX 5070 Ti com a seed traduzida de novo (46604
programas) contra o cache da r13d: 90272 pares (chave, estagio), 90179 modulos iguais e 93 em que o modulo novo e uma das duas
variantes que o arquivo antigo guardava, ou seja 0 modulos SPIR-V diferentes. A DLL final reaproveitou o cache da r13d nessa
RTX (46607 programas mantidos, sem preparar de novo) e Kokiri apareceu como antes.

Testado na Intel (build de desenvolvimento, 1440p, Buffers robustos ligados, saves copiados): com a correcao, Link, Saria e os
objetos proximos aparecem iluminados e com textura em Kokiri; antes eram silhuetas pretas. Sem otimizacao do driver
(`RX_VK_NOOPT=1`) a imagem nao muda.

Ainda na Intel: das 7 partidas com essa correcao, uma perdeu o dispositivo ainda na tela de titulo, no mesmo compute
`4b03b3040d7cf076` da r13d (le memoria por uma tabela de enderecos), com a copia dos uniformes ligada. As outras 6 chegaram
a floresta ou a Kokiri e fecharam com codigo 0. A falha e intermitente e a causa nao foi encontrada.

O veu de luz na Intel ainda nao foi resolvido. O compute `ee7764a6b1ef459c` (dispersao do sol) continua uniforme e cerca de 30
vezes mais claro que na RTX, e sua saida R8G8 sai constante (4/255, verde 0). Testes que excluem causas:

- Nao e o otimizador do driver: igual com `RX_VK_NOOPT=1`.
- Nao e a copia dos uniformes: na Intel sem ela (`RX_VK_UB_SNAPSHOT=0`) o compute sai igual. Nessa partida, com a correcao do
  fim dos buffers, a Intel chegou a Kokiri sem perder o dispositivo, mas foi uma partida so; a copia continua ligada por padrao.
- A copia, porem, nao e neutra: forcada na RTX, o mesmo compute perde os feixes de luz (saida R8G8 constante, como na Intel), embora
  a imagem final mude pouco. Deixar de copiar os intervalos que a GPU escreve nao mudou isso, e a tentativa foi descartada
  (`next/scripts/descartado-r13e_ub_gpu_written.py`).

Launcher (`akynoleyend/hardware.py`, `launch.py`):

- Codigo 0xC000001D (instrucao ilegal): a interface explica que o pacote exige x86-64-v3 (AVX2, BMI2, FMA) e mostra o
  processador. Antes de abrir, se o Windows diz que nao ha AVX2 (`IsProcessorFeaturePresent`), o console avisa; isso nunca
  impede a partida, porque Windows anteriores ao 10 respondem nao para essas consultas. Visto na maquina de um testador
  (pacote r3). Uma versao para processadores sem AVX2 exigiria compilar o jogo com `RX_MARCH=x86-64` e nao foi feita.
- Codigo 0xC000013A (console fechado ou processo cancelado): a interface diz que nao e uma falha do jogo.
- Antes de preparar shaders com menos de 6 GB de RAM livre, o console avisa que a preparacao vai usar 1 worker e pode levar
  horas. Visto aqui: com um Hookshot de 16 GB aberto ao lado, a preparacao na Intel fez 4722 de 116427 programas em 30 minutos;
  com memoria livre, a mesma preparacao terminou em 30 minutos.

## 0.4.4: r13j unida ao ramo Intel

A 0.4.4 junta os dois ramos que partiram da r13c: o deste documento (r13d a r13j: perda de dispositivo registrada, caches
por GPU, controle de VRAM, pontos de mesh shader, finalizacao por textura, oclusao real, sono curto em CPU de 6 nucleos,
arvores no ar, descarte so do excesso de VRAM, nivel x86-64 pela CPU) e o ramo Intel (r13d e r13e acima). Base comum
conferida: a r13c do pacote `AkynoLeyend-Atualizacao-0.4.3-test.4-r13c.zip` tem a identidade `aeef577d`, a mesma do
`coherence.py`. Mesclagem de tres vias (`git merge-file`, base r13c) sem conflito de texto em `spirv_emit_context.cpp`,
`vk_draw.cpp`, `vk_internal.h`, `vk_memory.cpp` e `vk_shader.cpp`; os arquivos que so o ramo Intel mudou vieram como estao.

Do ramo Intel, entrou:

- As tres correcoes de traducao do Hookshot v2.1.0 para placas que nao sao NVIDIA (`mma_layout.h`, `vk_coopmat.cpp`): limite
  de 1024 tentativas no compare-exchange, `gl_Position` invariante e saidas de cor sem NaN. Na AMD (por exemplo a RX 590)
  passam a valer tambem: o Hookshot as tem para essas placas (a do NaN para todas). Custo: poucas instrucoes por saida de cor
  e a posicao sem reordenacao; nenhum na NVIDIA, onde ficam desligadas.
- O fim dos storage buffers a partir do endereco nao arredondado quando o alinhamento passa de 16 (so a Intel integrada).
- A copia dos uniformes por padrao na Intel sem espelho de VRAM (as notas do ramo mostram que ela nao e neutra numa RTX:
  continua so na Intel).
- No launcher: a explicacao do 0xC000013A (console fechado ou cancelado) e o aviso de pouca RAM antes de preparar shaders.
- `tests/test_r13d_intel.py`, `tests/test_r13e_ssbo_end.py` e `tests/test_r13e_exit_reasons.py` (este ajustado, abaixo); a
  linha do Hookshot no `THIRD_PARTY_NOTICES.md`.

Do ramo Intel, nao entrou:

- O texto do 0xC000001D ("este pacote exige x86-64-v3") e o aviso de AVX2 antes de toda partida (`cpu_lacks_avx2`): desde a
  r13j o Criar compila para o nivel que a CPU executa, o Jogar recusa um build que a CPU nao roda e a explicacao diz o que
  falta pela CPUID (`akynoleyend/cpu.py`). O texto do ramo ficaria errado num build x86-64-v2. `hardware.exit_explanation`
  trata so o 0xC000013A, e o teste do ramo foi ajustado para isso.

Nenhuma mudanca de um ramo desfaz a do outro: as quatro flags do ramo Intel ficam desligadas na NVIDIA (o SPIR-V e o mesmo,
como o ramo mediu numa RTX 5070 Ti: 0 modulos diferentes em 90272), e quando ligadas entram no `disk_stamp`, separando os
programas dessas placas. O tipo de registro 16 e a marca de preparacao da r13i (arvores) valem nos dois casos. Na RTX 3060 Ti
do Teste-1 o cache de programas continua valendo (stamp `4cdbb0029868040b`, registro movido para `ef25851c`).

Versao: `0.4.4` em `akynoleyend/__init__.py`, `VERSION`, no projeto do launcher (republicado) e na DLL (`renderer.json`). O
`HOST_REVISION` e o ABI do codigo gerado nao mudam: uma instalacao 0.4.3-test.4 conhecida (qualquer revisao dos dois ramos,
listadas no `coherence.py`) atualiza sem traduzir o jogo de novo. As analises feitas ate aqui estao em
`docs/analises-0.4.4.md`.

Atualizador avulso (`builder/AkynoLeyendUpdater`, o mesmo do `AkynoLeyend-Atualizador-Teste4.exe`): passa a ir de
0.4.3-test.4 (Teste 4, qualquer revisao dos dois ramos) para 0.4.4, como `AkynoLeyend-Atualizador-0.4.4.exe`, com o ZIP de
atualizacao 0.4.4 embutido e o SHA-256 dele conferido ao rodar. Ele nao troca arquivos sozinho: confere o pacote contra o
indice e entrega a `stage-update` e `apply-update` da propria instalacao (que confere a revisao instalada pelo
`coherence.py` do pacote, guarda copia e reverte em falha), depois faz `run --dry-run`. Registro em
`atualizacoes/atualizador-0.4.4.log`.

Ferramentas > EXPORTAR SAVES (depois do primeiro pacote da 0.4.4): traz o save do Ocarina de um emulador para o port.
`akynoleyend/saves.py` e adaptado do `scripts/oot_saves.py` do Hookshot (GPL-3.0; o guia e o `docs/saves.md` de la): os
emuladores e o port guardam os mesmos arquivos (`account.sav`, `option.sav`, `slot_NN/progress.sav` e `caption.sav`, com o
mesmo cabecalho; conferido aqui entre o Eden do PokeDinner e o Teste-1), entao o save e copiado, nao convertido.

- Emuladores: Fritz (Fritchii) e PokeDinner em `%APPDATA%\eden`; Lichii em `%APPDATA%\lichii` (build 150 em diante) e
  `%APPDATA%\eden` antes; MDias e um build do Lichii (`lichii.exe` no pacote dele), entao como o Lichii. Depois
  `nand\user\save\0000000000000000\<perfil>\0400486024DEC000` (ou `nand\user\save\account\<perfil>\0400486024DEC000\0`).
  So conta um perfil que tem save: o emulador mantem vazia a pasta do perfil 000...0 (era o caso aqui; o save estava no
  perfil `39B517F1...`). Com mais de um perfil com save, vai o salvo por ultimo (`--profile` escolhe outro).
- Destino: `<jogo>\user\save\5a3c9e1f0b7d24680000000000000001` (o usuario do host, `nn_applet.c`/`nn_fs.c`).
- Sem corromper: a pasta do emulador so e lida (um link nela e recusado). Os arquivos vao primeiro para uma pasta ao lado,
  cada um conferido por SHA-256 contra o original (lido de novo depois da copia); so entao o save do port vai para
  `<jogo>\user\save-backups\<data>-antes-de-<emulador>` e a pasta nova toma o lugar dele, por renomeacao no mesmo disco.
  Uma falha antes disso deixa o save do port como estava. Recusa com o jogo ou o emulador abertos.
- Launcher: botao EXPORTAR SAVES ao lado de "Baixar DLSS da NVIDIA", uma janela para escolher o emulador, e o resultado no
  painel de execucao (`manage.py export-saves --emulator fritz|mdias|pokedinner|lichii --out <jogo>`, com `--dry-run`,
  `--profile` e `--from` para uma pasta `user` de emulador portatil). Teste: `tests/test_saves_export.py`.

## 0.4.5 (em preparo): criacao do jogo mais rapida

O log da r13c num Ryzen 5 3500X (6 threads, 16 GB) levou 2 h 21 min: 20 min para extrair o .nup, 6 min de traducao e 115 min
de compilacao com **um processo** (`compile_jobs` reservava 3,5 GiB por compilador; com 7,7 GiB livres sobrava 1). Medido
aqui, um bloco comum de 6 MiB usa 0,3 GiB e o mais pesado (`code_087`) 2,56 GiB. Mudou:

- `akynoleyend/compile_plan.py` (novo) e `nx2/build.py`: um compilador por thread (ate 8) enquanto a memoria der, e um
  despachante no lugar do `ThreadPoolExecutor`: a vaga livre pega a primeira unidade do plano que cabe na memoria agora (o
  pico estimado de cada uma pelo tempo conhecido, ou o pico medido em `nx2/compile_hint.json` com 15% de margem; 1 GiB fica
  para o sistema; se outro programa toma memoria, a proxima espera). A ordem e pelos tempos: as mais longas primeiro
  (`compile_hint.json`, medido no log da r13c; depois os tempos deste PC em `work/logs/compile-units.json`). Uma unidade
  leve so passa a frente de uma longa que espera quando nao ocupa o espaco que a longa vai usar. `RX_MEMORY_GATE=0` desliga
  a espera por memoria. Os objetos sao os mesmos da compilacao em serie (conferido byte a byte, fora o carimbo de hora do
  COFF, que muda a cada compilacao).
- `nx2/nup.py`: cada arquivo novo e gravado com o proprio nome (antes: nome temporario e renomeacao, um terco do tempo no
  Windows), o caminho e conferido uma vez por pasta, e um `.zs` embrulhado e descomprimido uma vez (antes, duas). Bytes
  identicos aos do leitor anterior (conferido em 18 mil arquivos). Threads (`NUP_WORKERS`) ficaram mais lentas no SSD SATA
  daqui e nao sao o padrao. `akynoleyend/build.py` aceita a extracao do leitor anterior (`c1b9fb6f`) sem repara-la.
- `akynoleyend/build.py` `nup_identity`: o SHA-256 do .nup (193 s) fica em `work/inputs/nup-identity.json` com caminho,
  tamanho e data; so e reaproveitado com os tres iguais.
- `tests/fixtures/nup_reader_c1b9fb6f.py`: o leitor que a ferramenta de reparo `tools/reparar_extracao.py` instala, para o
  teste dela. `nx2/build.py` entra na identidade do renderizador pronto: a DLL generica precisa ser republicada.

Testes: `tests/test_045_build_speed.py`; ajustados `test_adaptive_043`, `test_workflow`, `test_hot_pipeline`,
`test_nup_paths` e `test_nup_repair`. Medidas em `docs/analises-0.4.5.md`.

## 0.4.5-test.1: geracao de quadros dinamica e ritmo novo

Versao de teste sobre a 0.4.5 (a 0.4.6 sera a definitiva). O jogo criado e o mesmo: so mudam o renderizador, o launcher e
a opcao na linha de comando. Ideias do MFG-Unlocker (github.com/dashdogy/MFG-Unlocker, MIT); nada das partes NVIDIA/Intel.

- `gpu/vk/fg_dynamic_count.h` (novo): `source/native/xess/xefg_dynamic_count.h` do MFG-Unlocker, copiado sem mudancas
  abaixo do aviso MIT (SHA-256 do original `6b9fec52...83e8`, conferido por `tests/test_0451_framegen.py`). A cada quadro
  do jogo escolhe quantos quadros gerar para o total mostrado ficar perto de um alvo; ignora travadas isoladas, espera antes
  de subir ou descer, desfaz uma troca que piorou e aprende o custo de cada quadro gerado.
- `gpu/vk/fg_dynamic.h` (novo, proprio): o alvo (linha Alvo, ou em Monitor `floor(Hz - Hz^2/3600)`: 138 em 144 Hz, 59 em
  60 Hz, como o `xemfg_dynamic.h` deles), maximo de 2x a 6x, 1x permitido. O tempo que o jogo dorme no host (`nn_vi.c`) nao e
  conhecido aqui: entra como trabalho (`waitMs` 0).
- `gpu/vk/fg_pacer.h` (novo, proprio): o ritmo da thread de exibicao, sem chamadas ao Windows. Mantem a linha do Hookshot
  e acrescenta tres regras: quadro isolado 2,5 vezes mais longo que a media (ate dois seguidos) fica fora da media; o limite
  de atraso soma o tempo medido da GPU para fazer o lote e meio quadro mostrado; o primeiro quadro de cada lote puxa a linha
  um quarto da espera para mais perto (sem isso a linha so andava para tras: ate 16 ms a mais no modelo).
- `gpu/vk/vk_framegen.cpp`: valor 9 da linha Geracao de quadros (Dinamica). Os conjuntos sao alocados uma vez para o maximo
  e o numero de quadros muda a cada quadro sem `vkDeviceWaitIdle`. Cada conjunto ganhou um `VkEvent` que a GPU marca ao
  terminar; a thread de exibicao espera por ele antes do primeiro quadro do lote (dormindo enquanto o previsto estiver
  longe; `RX_VK_FG_READY=0` desliga) e o rearme espera a GPU se ela passou de 100 ms. Le a taxa do monitor da janela a
  cada segundo (`MonitorFromWindow`, `EnumDisplaySettingsW`). O log de 5 s ganhou o atraso medido da GPU e, na Dinamica,
  quantos lotes de cada multiplicador; cada troca do multiplicador e registrada (ate 300). `RX_VK_FG_TRACE=<csv>`: uma
  linha por quadro mostrado; `tools/fg_trace_summary.py` resume.
- `gpu/vk/vk_loader.h`: `vkCreateEvent`, `vkDestroyEvent`, `vkCmdSetEvent`, `vkGetEventStatus`, `vkResetEvent`.
- `gpu/vk/vk_menu.cpp`/`.h`: Geracao de quadros vai ate Dinamica; linhas novas Geracao dinamica: maximo (`framegen_maximum`,
  padrao 4x) e alvo (`framegen_target`, Monitor). `AKYNO_FRAMEGEN` aceita 9.
- Launcher (`LaunchOptions.cs`, `MainWindow.xaml`), `akynoleyend/graphics.py` e `cli.py`: opcao Dinamica (`--framegen 9`).
  `builder/RunnerChecks` confere que sai como `--framegen 9` e que 10 e recusado.
- `akynoleyend/coherence.py`: a identidade da 0.4.5 instalada (`87dc43b5...`) e aceita para atualizar sem recompilar o jogo.
  Os fontes de shader nao mudaram: o carimbo `4cdbb0029868040b` continua.
- `THIRD_PARTY_NOTICES.md` e `licenses/mfg-unlocker/LICENSE.txt`: aviso MIT do MFG-Unlocker.

Testes: `tests/test_0451_framegen.py` (com `tests/native/fg_dynamic_test.cpp` e `fg_pacer_test.cpp`: jogos e GPU simulados;
o ritmo novo e comparado ao da 0.4.5 em espacamento, quadros colados e atraso). Nada disso foi visto numa partida.

## 0.4.5-test.2: gravacao sem o nucleo virtual e medicao de desempenho

O FPS nao mudava com a resolucao (720p a 4K, escala de 50% a 150%: 16 a 37 FPS em jogo) num Ryzen 5 3500X (6 nucleos, sem
SMT) com RTX 3060 Ti. Nas 19 sessoes de 13/11/2026 o tempo de cada quadro acompanhou a soma da gravacao dos desenhos
(10 a 36 ms, 8 a 18 us por desenho) com o tempo de GPU (11 a 19 ms), nao os pixels. No codigo: com `RX_VK_ASYNC` desligado (o
padrao do Hookshot no OoT, por causa de quadros brancos) cada `nvnQueueSubmitCommands` e gravado na thread que envia, a
Presentation Thread do jogo, que segura o nucleo virtual 0 o tempo todo (codigo do host nao tem checkpoint). A
sead::MainThread, a BaseProcExecutor0 e a PlayReporter so podem usar o nucleo 0 e esperavam (os logs:
"sead::MainThread (priority 16) ran without a core after 250.2 ms: core 0: Presentation Thread (17) asked").

- `host/nvn_native.c`: `replay_submit` solta o nucleo virtual (`hos_vcore_away`) durante a gravacao de cada envio e o
  retoma antes de voltar ao codigo do jogo, como `nvnSyncWait`, `nvnQueueFinish` e a apresentacao ja faziam. Vale para
  `nvnQueueSubmitCommands` e para os envios segurados (`held_flush`). `HOS_SUBMIT_KEEP_CORE=1`: como antes. A cada 5 s:
  "nvn: submits in 5 s: N replayed ... in X ms, M of them with the core given up". Risco conhecido: a thread principal
  passa a rodar durante a gravacao do quadro (como no console, onde a GPU le os comandos depois do envio); os quadros
  brancos que o `RX_VK_ASYNC` mostrava vinham de gravar ate dois quadros atrasado, o que nao acontece aqui.
- `host/mkw_glue.c`: com `HOS_MEM_MAP=1`, a cada 30 s a linha de memoria e o mapa (`hos_memory_map_log`, que o renderizador
  Vulkan nunca chamava), 120 vezes no maximo.
- `akynoleyend/environment.py`: `MEASURE` (`HOS_PROFILE=5`, `HOS_MEM_MAP=1`, `RX_VK_PROF_ALL=1`) e `EXPERIMENTS`
  (`nucleo-preso`: `HOS_SUBMIT_KEEP_CORE=1`; `gravacao-paralela`: `RX_VK_PARALLEL=3`), por cima de qualquer perfil; um
  experimento exige a medicao. `launch.py` grava os tempos de quadro em `quadros.bin` na pasta da execucao
  (`AKYNO_FRAMETIMES`) e registra `measure`/`experiment` no `execucao.json`. CLI: `run --measure [--experiment ...]`.
- Launcher: "Teste de desempenho" ao lado do perfil (Desligado, Medir, Medir com nucleo preso, Medir com gravacao em 3
  threads), `Measurement.Arguments` em `LaunchOptions.cs`; nao e salvo nos ajustes. Os presets continuam com a geracao de
  quadros desligada (conferido pelo RunnerChecks); quem quer a Dinamica escolhe "Usar opcao salva" ou "Dinamica".
- `tools/resumo_medicao.py` (novo): le `quadros.bin` e `erros.log` de uma execucao e resume FPS mediano, pior 1%, quadros
  acima de 50/100/250 ms, CPU por thread, gravacao por fase, espera pela GPU, esperas por nucleo virtual e memoria.
- A DLL do renderizador e a mesma da test.1 (nenhum fonte de `gpu/` mudou; `renderer.json` so troca a versao). O carimbo de
  shaders `4cdbb0029868040b` continua. `akynoleyend/coherence.py`: a test.1 instalada (`df76cd9c...`) e a arvore dela
  (`e8a1da01...`) atualizam sem recompilar o jogo.

Testes: `tests/test_0452_measure.py`. Nada disso foi visto numa partida: o ganho de FPS precisa da medicao do jogador.

## 0.4.5-test.3: texturas e alvos de render em grupos separados, nucleo preso de novo, amostras da gravacao

Medido numa partida da test.2 (Ryzen 5 3500X, RTX 3060 Ti 8 GB, 16 GB; 5 minutos por teste no Campo de Hyrule, geracao de
quadros desligada; `tools/resumo_medicao.py --depois 60`):

| | nucleo solto | nucleo preso | gravacao em 3 threads |
| --- | ---: | ---: | ---: |
| FPS mediano | 22,6 | 22,2 | 21,1 |
| pior 1% | 0,4 | 0,8 | 1,0 |
| quadros acima de 250 ms | 94 | 131 | 155 |
| gravacao por quadro | 34 ms | 21 ms | 18 ms |
| GPU por quadro | 14 ms | 16 ms | 20 ms |

A sead::MainThread usou 12 a 18% de um nucleo: nao era ela que segurava o quadro, e soltar o nucleo deixou a gravacao mais
lenta. A Presentation Thread ficou perto de 100% nos trechos de jogo. Ao entrar no campo o processo foi de 10 para 20,5 GB
reservados em 30 s (RAM livre 700 MB, commit livre 270-800 MB); a VRAM ficou em 7,5-7,8 GB usados de 7,1 permitidos, com
1,3-2,1 GB de buracos nos 3,0-3,4 GB de blocos do grupo de imagens; "target pool: 2 reused, 3919 new"; a compactacao da r13e
nao rodou nenhuma vez (so esvazia blocos em que toda imagem e uma textura descartavel, e todo bloco tinha um alvo).

- `gpu/vk/vk_vma.cpp`, `vk_internal.h`: dois grupos VMA do mesmo tipo de memoria e tamanho de bloco: `ImagePool::Textures`
  (as texturas que a memoria do jogo refaz) e `ImagePool::Other` (alvos de render e as imagens do proprio renderizador, o
  padrao de `create_image`). Cada bloco guarda o grupo; a linha "vk: image pool" mostra blocos e buracos de cada um.
  `RX_VK_IMAGE_POOLS=1`: um grupo, como antes.
- `gpu/vk/vk_texture.cpp`: `create` pede o grupo das texturas quando a imagem nao e feita para um alvo (`for_target`).
- O DLL foi recompilado (SHA-256 `1b5e3f6b...0c8e`, 6.310.912 bytes); o carimbo de shaders `4cdbb0029868040b` continua.
- `host/nvn_native.c`: o nucleo fica preso de novo durante a gravacao; `HOS_SUBMIT_FREE_CORE=1` solta (como a test.2).
- `akynoleyend/environment.py` `EXPERIMENTS`: `amostrar` (`HOS_SAMPLE=Presentation Thread`: o ponteiro de instrucao da thread
  de gravacao a cada milissegundo, os lugares mais frequentes a cada 5 s), `nucleo-solto`, `pool-unico`, `gravacao-paralela`;
  sai `nucleo-preso`, que voltou a ser o padrao. Launcher: as mesmas opcoes em Teste de desempenho.
- `tools/resumo_medicao.py`: soma as linhas "prof-sample" e da nome as funcoes pelos simbolos COFF do EXE e do DLL
  (`llvm-nm`/`llvm-readobj` do LLVM incluido); `--sem-simbolos` mostra modulo+deslocamento.
- `akynoleyend/coherence.py`: a test.2 instalada (`081373...`, igual a arvore) atualiza sem recompilar o jogo.

Testes: `tests/test_0453_pools.py`; `tests/test_0452_measure.py` ajustado aos padroes novos. Nada disso foi visto numa partida.

## 0.4.5-test.4: alvos de render reaproveitados com a VRAM cheia, amostras de duas threads com a cadeia de chamadas

Medido numa partida da test.3 (Ryzen 5 3500X, RTX 3060 Ti 8 GB, 16 GB; Campo de Hyrule, geracao de quadros desligada;
`tools/resumo_medicao.py --depois 60`), contra a test.2 com o nucleo preso:

| | test.2 | amostrar | nucleo solto | 3 threads |
| --- | ---: | ---: | ---: | ---: |
| FPS mediano | 22,2 | 26,1 | 26,8 | 26,1 |
| quadros acima de 250 ms por minuto | 25,9 | 19,9 | 12,2 | 12,8 |
| quadros acima de 100 ms por minuto | 56 | 48 | 41 | 24 |
| compactacoes da VRAM | 0 | 2 | 6 | 2 |

A compactacao da r13e passou a esvaziar blocos (1 a 5 por partida), mas "target pool: 0 reused, 8131 new" em 7 minutos e
400-640 MB de buracos nos blocos do grupo dos alvos: `target_put` recusava tudo com `target_pool_pressed` (VRAM acima de 90%
do permitido), e o `target_trim` apagava o que havia; numa placa de 8 GB e quase a partida inteira. As amostras da
Presentation Thread: 55% em `hos_cv_sleep`, 35% em `replay_submit`; nenhuma thread perto de 100%, e o jogo esperando a GPU
170-200 ms por segundo. O que segura o quadro e espera, mas as amostras nao diziam de quem.

- `gpu/vk/vk_texture.cpp`: `target_pool_pressed_cap` (`RX_VK_TARGET_POOL_PRESSED_MB`, 64 por padrao, 0 = como antes) e
  `target_pool_cap_now`: sob pressao o grupo aceita alvos ate esse limite e os guarda por 8 quadros (120 sem pressao); acima
  do limite do momento sai o que houver, de qualquer idade. O DLL foi recompilado; o carimbo de shaders `4cdbb0029868040b`
  continua.
- `host/mkw_glue.c` (amostrador do `HOS_SAMPLE`): varias threads (`a|b`, um amostrador cada, tabelas proprias), toda linha
  com o nome da thread (`prof-sample leaf (N samples) [nome]:`), e a linha `chain`: as 6 primeiras funcoes do exe a partir
  da folha (`exe+a<+b<+c`), as 20 mais frequentes a cada 5 s.
- `akynoleyend/environment.py`: `amostrar` amostra `Presentation Thread|sead::MainThread`; novo `alvos-como-antes`
  (`RX_VK_TARGET_POOL_PRESSED_MB=0`). Launcher: "Medir · amostrar a gravacao e o jogo" e "Medir · alvos sem reaproveitar
  (como na test.3)"; RunnerChecks confere a nova opcao.
- `tools/resumo_medicao.py`: amostras por thread (uma linha sem thread e da Presentation Thread, como na test.3), cadeias com
  nomes de funcao, alvos reaproveitados/novos, compactacoes da VRAM; a saida e UTF-8 (com o console ou um arquivo em cp1252
  o relatorio parava nos nomes de thread em japones).
- `akynoleyend/coherence.py`: a test.3 instalada (`d168e3be...`) atualiza sem recompilar o jogo.

Ainda nao tratado: a queda 0xC0000005 em `n_nvnMemoryPoolGetFlags` (thread OptimizeChangeBanc, a mesma pilha do jogo nas 10
vezes desde 13/11: `f_80905130` cria um buffer num grupo nulo porque a reserva em `f_80522050`, chamada de `f_804566e0`,
falhou e o jogo seguiu).

Testes: `tests/test_0454_targets.py`; `tests/test_upstream_2013_043.py` fixa o teste do grupo de alvos no comportamento
anterior (`RX_VK_TARGET_POOL_PRESSED_MB=0`); `tests/test_0453_pools.py` ajustado as amostras por thread. Nada disso foi
visto numa partida.

## 0.4.5-test.5: medicao das esperas da thread principal do jogo

Medido na test.4 (Teste-1, Campo de Hyrule, `tools/resumo_medicao.py --depois 60`): Medir 26,0 FPS mediano, alvos sem
reaproveitar 25,6, amostrar 27,5; quadros acima de 250 ms ~32, ~34 e ~39 por minuto (a test.3 dava 11-13 no mesmo modo:
outro trecho do mapa, nao a mudanca). Alvos de render: 1.841 reaproveitados e 5.873 novos contra 0 e 9.286 sem reaproveitar;
sem efeito no FPS. Nenhuma queda 0xC0000005 nas 4 partidas.

As amostras: a Presentation Thread 57% em `hos_cv_sleep` (`queue_get` < `ReceiveLightMessageQueue` < `f_834a3060`: sem
trabalho) e 31% em `replay_submit`; a `sead::MainThread` ~23% em `sleep_away` < `SleepThread` < `f_800998a0` <
`f_8007fe60` < `f_80070b20` (chamada de `f_80706be0`, o passo do quadro) e ~35% em `WaitLightEvent` no mesmo caminho.
`f_800998a0` entrega tarefas as threads BaseProcExecutor e dorme ate que terminem; nenhuma thread passa de 44% de um nucleo
e a GPU leva 11-13 ms por quadro. As threads esperam umas as outras.

- `akynoleyend/environment.py`: `esperas` = `HOS_SAMPLE=sead::MainThread|BaseProcExecutor0|BaseProcExecutor1` e
  `HOS_SLEEP_LOG=1` (o registro dos sonos do jogo por chamador de `host/hos_thread.c`, que ja existia). Launcher: "Medir ·
  esperas do jogo (sonos e tarefas)"; RunnerChecks confere a opcao.
- `tools/resumo_medicao.py`: soma as linhas `sleep: lr` por chamador (chamadas, pedido, dormido) e mostra as 12 com mais
  tempo dormido.
- `akynoleyend/coherence.py`: a test.4 instalada (`8c0c9073...`) atualiza sem recompilar o jogo. Sem mudanca no C do host
  nem no renderizador (`renderer.json`: so a versao; identidade dos fontes `c281215a...` conferida igual).

Testes: `tests/test_0455_waits.py`; `tests/test_0454_targets.py` sem a conferencia da versao (esta no teste novo). Nada disso
foi visto numa partida.

O mod "Zelda OoT Dynamic FPS v1.0" (um .ips de 48 bytes em main+0x6e6c98, 0x80706c98 aqui) foi lido para comparar e nao
entra: troca a divisao do passo de `f_80706be0` pelo tempo do quadro anterior, o que o host ja faz (`host/nn_vi.c`, a taxa
medida em +0x2c8 abaixo de 60 e `hos_frame_seconds_bits` acima), e os patches de exefs nao se aplicam ao codigo compilado.

## 0.4.5-test.6: a thread principal do jogo sem o timer nas esperas curtas

Medido na test.5 (Teste-1, Ryzen 5 3500X, Campo de Hyrule, "Medir · esperas do jogo", 243 s): 25,3 FPS mediano, 96 quadros
acima de 250 ms, GPU 11,5 ms por quadro. `HOS_SLEEP_LOG`: no chamador `lr 0x8009a478` 800.305 sonos de 20 us pedidos e ~537
us dormidos (16 s pedidos, 430 s dormidos); `0x8007e90c`, `0x8009aff0` e `0x800747ac` iguais (20 us -> ~520 us); os sonos
longos (100 ms em `0x80df26c0` e outros) quase exatos. As amostras: a `sead::MainThread` ~30% em `sleep_away` <
`hos_sleep_logged` < `SleepThread` < `f_800998a0` (entrega as tarefas do quadro e confere a cada 20 us se terminaram) e ~31%
em `WaitLightEvent`; BaseProcExecutor0 e 1 ~80% paradas em `queue_get` (sem trabalho). A causa e a regra da r13i (Hookshot
PR 2263): com 6 processadores logicos ou menos, os sonos do jogo abaixo de 1 ms esperam no timer de alta resolucao, que acorda
~0,5 ms atrasado. A regra existe pelas threads ociosas (ModuleSystemWorker*, OptimizeChangeBanc), que dormem 20 us e olham a
fila de novo; mas tambem pega a thread principal quando ela espera as tarefas.

- `host/hos_thread.c`: com a escolha 1 (so os sonos do jogo no timer), os sonos do jogo abaixo de 1 ms na thread
  `sead::MainThread` cedem a vez em laco ate a hora, como os do host (`hos_short_sleep_main_yields`, pelo nome da thread). As
  outras threads continuam no timer. `HOS_SHORT_SLEEP_MAIN_TIMER=1`: a thread principal no timer tambem, como na test.5;
  `HOS_SHORT_SLEEP_TIMER` continua valendo para todas. A linha do registro diz "the game's (but sead::MainThread's)".
- `akynoleyend/environment.py`: `esperas-como-antes` (= `esperas` + `HOS_SHORT_SLEEP_MAIN_TIMER=1`) e `esperas-todas-cedem`
  (= `esperas` + `HOS_SHORT_SLEEP_TIMER=0`), com as mesmas amostras e o mesmo registro dos sonos. Launcher: "Medir · esperas,
  thread principal no timer (como na test.5)" e "Medir · esperas, todas as threads sem timer"; RunnerChecks confere as duas.
- `akynoleyend/coherence.py`: a test.5 instalada (`d79a9a71...`) atualiza no lugar; so os objetos do host sao refeitos, os do
  jogo ficam. Renderizador sem mudanca (`renderer.json`: so a versao; identidade dos fontes `c281215a...` conferida igual).

Testes: `tests/test_0456_main_sleep.py` (a escolha compilada e rodada, os modos, a versao); `tests/test_r13i_p0.py` segue a
condicao nova; `tests/test_0455_waits.py` sem a conferencia da versao. Custo esperado: a thread principal ocupa um processador
enquanto espera as tarefas (cede a vez a cada volta). Nada disso foi visto numa partida.

## 0.4.5-test.7: esperas curtas girando no relogio

Ideias do NX2navi (port do mesmo jogo, `E:\Games\NX2navi`, 0.9.2), lidas no binario com o REA e reescritas aqui, sem codigo
copiado: os sonos do jogo de ate 1 ms giram no relogio com pausa (`SLEEP_SPIN_NS`), e quem espera um nucleo gira 250 us antes
de dormir (`AP_FIRST_NS`). No PC do Teste-1 o NX2navi registra 42-50 FPS medios no jogo e "16803 waits ended in the first
spin" a cada 600 quadros; o AkynoLeyend fica em ~26 FPS. A test.6 (thread principal cedendo a vez nos sonos curtos) foi
instalada mas ainda nao medida; a test.7 a contem como modo de comparacao.

- `host/hos_thread.c`, `sleep_ns`: `hos_short_sleep_spin(HOS_SHORT_SLEEP_SPIN)`. Nao definido (1): os sonos abaixo de 1 ms da
  `sead::MainThread` que antes cediam a vez (`SwitchToThread`) giram no relogio com `_mm_pause`, sem ceder o processador;
  `SwitchToThread` entrega o processador a uma thread pronta nele, e a principal so volta a conferir as tarefas depois do
  quantum dela. `all` (2): todos os sonos abaixo de 1 ms giram, os do jogo, os do host e os que iam para o timer. `0`: nenhum,
  como na test.6. A escolha de r13i/test.6 (timer ou ceder) fica igual e e lida antes. Linha nova no registro: "sleep: ...
  under a millisecond spin on the clock".
- `host/hos_thread.c`, `vc_acquire`: sem nucleo livre, depois do pedido ao pior dono (`vc_kick`), o esperador solta `vc_lock`
  e gira ate `HOS_VCORE_SPIN_US` (padrao 150, 0 a 1000; `vc_spin_ns`) olhando o proprio `vc_held`; `vc_grant` o marca sob a
  trava antes do `WakeConditionVariable`, entao quem ve `vc_held` ja tem o nucleo. Uma vez por espera; depois dorme na
  variavel de condicao como antes. A linha "vcores:" ganha "N waits ended in the spin" no fim (`tools/resumo_medicao.py` le o
  comeco, igual).
- `akynoleyend/environment.py`: `esperas-como-test6` (= `esperas` + `HOS_SHORT_SLEEP_SPIN=0` + `HOS_VCORE_SPIN_US=0`) e
  `esperas-todas-giram` (= `esperas` + `HOS_SHORT_SLEEP_SPIN=all`); os dois modos da test.6 (`esperas-como-antes`,
  `esperas-todas-cedem`) ganham `HOS_SHORT_SLEEP_SPIN=0` e `HOS_VCORE_SPIN_US=0` e continuam medindo o que mediam. Launcher:
  "Medir · esperas sem giro (como na test.6)" e "Medir · esperas, todos os sonos curtos girando"; RunnerChecks confere os dois.
- `akynoleyend/coherence.py`: a test.6 instalada (`83a595c1...`) atualiza no lugar; so os objetos do host sao refeitos.
  Renderizador sem mudanca (`renderer.json`: so a versao; identidade dos fontes `c281215a...` conferida igual).

Testes: `tests/test_0457_spin.py` (as duas escolhas compiladas e rodadas, a ordem no `sleep_ns` e no `vc_acquire`, a linha
"vcores:" ainda lida pelo resumo, os modos, a versao); `tests/test_0456_main_sleep.py` e `tests/test_r13i_p0.py` seguem a
condicao reescrita em duas linhas. Custo esperado: mais uso de processador (a principal gira enquanto espera as tarefas; cada
espera por nucleo gira ate 150 us). O modo `esperas-todas-giram` pode piorar com 6 processadores: a r13i (Hookshot PR 2263) mediu
que threads ociosas cedendo a vez em laco tiram tempo das do quadro. Nada disso foi visto numa partida.

Fica para depois (plano da analise do NX2navi): test.8, acordar so quem espera o objeto sinalizado (`host/nn_os_sync.c` usa
`WakeAllConditionVariable`) e prioridade alta para a thread que grava os comandos; test.9, heranca de prioridade, desligavel;
uma versao do renderizador com o vies de mip das texturas com DLSS/FSR, a mascara de rastro e os modos do DLSS com nome.

## 0.4.5-test.8: todos os sonos curtos girando e a gravacao com prioridade alta

Medido na test.7 (Teste-1, Ryzen 5 3500X, Campo de Hyrule; `tools/resumo_medicao.py --depois 60`): padrao (so a thread
principal gira) 23,0 FPS mediano em 305 s, 34% dos quadros acima de 50 ms; sem giro (test.6) 24,4 FPS em 462 s, 26%; todos os
sonos curtos girando 25,9 FPS em 217 s, 18%. As partidas tiveram duracoes diferentes e a terceira teve GPU de 12,9 ms por
quadro contra 18-19 ms, entao parte da diferenca pode ser o trecho. O que nao depende do trecho: o sono de 20 us em `lr
0x8009a478` durou 118 us (so a principal girando), 112 us (test.6) e 21 us (todos girando); ele e usado por mais threads que a
principal. A `sead::MainThread` passa ~25% em `WaitLightEvent` dentro de `f_8007fe60`, esperando tarefas que as
ModuleSystemWorker pegam entre sonos de 20 us (`0x8007e90c`: ~443 us no timer). BaseProcExecutor0 e 1 ficam ~92% paradas. O
giro na espera por nucleo terminou 84% das esperas (235.445 de 280.558). A ultima partida fechou com o 0xC0000005 da
OptimizeChangeBanc em `AkynoLeyend.exe+0x1a35a64d`, o mesmo da test.5; as tres partidas da test.6 (13:58-14:10, 75-116 FPS, de
2 a 3 minutos, outro trecho) mostram o mesmo no sono de 20 us: so `esperas-todas-cedem` o deixou exato (22 us).

- `host/hos_thread.c`, `hos_short_sleep_spin`: sem `HOS_SHORT_SLEEP_SPIN`, 2 (todos os sonos abaixo de 1 ms giram no relogio
  com pausa); `main` ou `1`: so os da thread principal, como na test.7; `0`: nenhum.
- `host/hos_thread.c`, `hos_thread_pin`: a thread do jogo "Presentation Thread", que grava os comandos da GPU
  (`replay_submit`, 17-22 ms de gravacao por quadro na test.7), vai para `THREAD_PRIORITY_HIGHEST` quando e criada ou nomeada
  (`hos_present_thread_high`). Depois de `HOS_PRIO` e da regra da OptimizeChangeBank; `HOS_PRESENT_NORMAL=1`: prioridade
  normal, como antes. Ideia do NX2navi (a thread que grava em prioridade alta), reescrita aqui.
- `akynoleyend/environment.py`: `esperas-como-test7` (= `esperas` + `HOS_SHORT_SLEEP_SPIN=main` + `HOS_PRESENT_NORMAL=1`); os
  modos anteriores (`esperas-como-antes`, `esperas-todas-cedem`, `esperas-como-test6`, `esperas-todas-giram`) ganham
  `HOS_PRESENT_NORMAL=1` e medem o que mediam; `esperas-todas-giram` passa a ser a test.8 sem a prioridade nova. Launcher:
  "Medir · esperas, gravação em prioridade normal" (`esperas-todas-giram`) e "Medir · esperas como na test.7 (só a thread
  principal gira)"; RunnerChecks confere o novo.
- `akynoleyend/coherence.py`: a test.7 instalada (`edf749fc...`) atualiza no lugar; so os objetos do host sao refeitos.
  Renderizador sem mudanca (`renderer.json`: so a versao; identidade dos fontes `c281215a...` conferida igual).

Testes: `tests/test_0458_record_priority.py` (as escolhas compiladas e rodadas, a ordem em `hos_thread_pin`, os modos, a
versao); `tests/test_0457_spin.py` e `tests/test_0456_main_sleep.py` seguem o padrao novo e a prioridade antiga nos modos
deles. Custo esperado: as cinco ModuleSystemWorker girando, ~28% de um nucleo cada na test.7. Nada disso foi visto numa
partida com a prioridade nova.

Fica para depois: acordar so quem espera o objeto sinalizado (`host/nn_os_sync.c` usa `WakeAllConditionVariable`; antes,
conferir se uma thread acordada a toa pega um nucleo virtual); heranca de prioridade, desligavel; a versao do renderizador
(vies de mip com DLSS/FSR, mascara de rastro, modos do DLSS com nome).

## 0.4.6: versao final das esperas, sem o Teste de desempenho

Medido na test.8 (Teste-1, Ryzen 5 3500X, Campo de Hyrule; `tools/resumo_medicao.py --depois 60`; as tres partidas fecharam
com codigo 0): padrao da test.8 (todos os sonos curtos girando, gravacao em prioridade alta) 25,8 FPS mediano em 243 s, 13,5%
dos quadros acima de 50 ms; sem a prioridade 26,2 FPS em 119 s, 12,4%; como na test.7 (so a principal gira) 25,5 FPS em 104 s,
10,9%. O sono de 20 us em `lr 0x8009a478`: 21 us com todos girando, 117 us so com a principal. Na test.7, com todos girando,
33,4 FPS contra 26,4 (so a principal) e 27,1 (sem giro), 9,7% acima de 50 ms contra 21,7% e 19,2%. As partidas nao tiveram a
mesma duracao nem o mesmo trecho.

- Fica: todos os sonos abaixo de 1 ms girando no relogio (`hos_short_sleep_spin`, padrao 2, da test.8) e o giro de 150 us
  na espera por nucleo virtual (`HOS_VCORE_SPIN_US`, da test.7): os sonos ficam exatos e as duas versoes de teste deram o
  mesmo ou mais FPS com eles.
- Sai: a prioridade mais alta da "Presentation Thread" (`hos_present_thread_high`, `HOS_PRESENT_NORMAL`), sem ganho medido
  (25,8 com, 26,2 sem). A thread volta a prioridade normal. `akynoleyend/environment.py`: os modos de medicao perdem
  `HOS_PRESENT_NORMAL`; `esperas-como-test7` = `esperas` + `HOS_SHORT_SLEEP_SPIN=main`.
- Launcher: sai a escolha "Teste de desempenho" (`MeasureBox`, classe `Measurement` em `LaunchOptions.cs`, as conferencias
  dela no RunnerChecks). A medicao continua pela linha de comando: `manage.py run --measure [--experiment ...]`.
- `akynoleyend/coherence.py`: a test.8 instalada (`b7e6521f...`) atualiza no lugar; so o `hos_thread.c` e refeito.
  Renderizador sem mudanca (`renderer.json`: so a versao; identidade dos fontes `c281215a...` conferida igual).

Testes: `tests/test_046_final.py` (a escolha dos sonos compilada e rodada, a prioridade fora, o launcher sem a medicao, a
versao) no lugar de `tests/test_0458_record_priority.py`; os testes da 0.4.5-test.2 a test.7 deixam de conferir os itens do
launcher. Custo: as cinco ModuleSystemWorker girando, ~25-28% de um nucleo cada.

## 0.4.7: o visual novo do launcher

O launcher redesenhado numa copia da 0.4.5 (`E:\AkynoLeyend-dist-0.4.5\AkynoLeyend-0.4.5`, que se dizia 0.4.6) entra por
cima da 0.4.6. So o launcher: host, renderizador, Python e o jogo como na 0.4.6.

- `builder/AkynoLeyendBuilder/App.xaml` e `Strings.cs`: copiados da redesenhada (aqui iguais aos da 0.4.5). Tema preto e
  dourado, estilos, barra de rolagem, fundos abstratos; subtitulos sem o nome do jogo nos idiomas.
- `MainWindow.xaml`, `MainWindow.xaml.cs` e `AkynoLeyendBuilder.csproj`: merge de tres vias (base 0.4.5, a redesenhada, a
  0.4.6), sem conflitos. Entram navegacao lateral, banners ("Sua próxima jornada", "A imagem do seu jeito", "Tudo pronto
  para jogar"), `ToggleMaximize`, o seletor de saves com barra propria, fundo desfocado (restaurado em `finally`) e Cancelar
  fixo. Ficam da 0.4.6: sem o Teste de desempenho e os modos dele.
- O botao "EXPORTAR SAVES" passa a "Exportar Save".
- Nao entram: `analysis/`, `.codex/`, `bin/`, `obj/`, a pasta `Assets` (vazia), o executavel e os recibos da copia. Icones
  iguais aos nossos.
- `akynoleyend/coherence.py`: a 0.4.6 instalada (`01dd7fee...`) atualiza no lugar. Renderizador sem mudanca
  (`renderer.json`: so a versao; identidade dos fontes `c281215a...` conferida igual).

Testes: `tests/test_047_launcher.py` (o visual novo, o texto do botao, o que fica da 0.4.6, a versao);
`tests/test_saves_export.py` procura o botao pelo texto novo. A janela nao foi aberta aqui.

## 0.4.7 unificada: o ramo da 0.4.5-test.1 unificada dentro da 0.4.7

Em paralelo a test.2-0.4.7 (esperas, grupos de imagens, alvos, launcher novo), outro ramo partiu da 0.4.5-test.1 e foi
distribuido como `AkynoLeyend-Atualizacao-Unificada-0.4.5-test.1.zip` (14/11/2026, 17:39): candidatas Render Compute e Render
VRAM, politica de VRAM por placa da r13k/r13l, dimensoes de saida do inicializador e a Distancia de renderizacao no F1. Como a
0.4.6 e a 0.4.7 ainda nao foram distribuidas, o ramo entra na 0.4.7 antes da publicacao.

Mesclagem de tres vias com base na 0.4.5-test.1 original (`AkynoLeyend-Atualizacao-0.4.5-test.1.zip` de
`E:\AkynoLeyend-dist-0.4.5-test.1`, a arvore `e8a1da01...`), a 0.4.7 da linha principal e a unificada:

- 38 arquivos mudados so na unificada e 2 novos dela vieram como estao: `gpu/vk` (`vk_memory.cpp`, `vk_draw.cpp`,
  `vk_shader.cpp`, `vk_main.cpp`, `vk_menu.cpp`/`.h`, `vk_replay.cpp`, `vk_coopmat.cpp`, `vram_policy.h`, `wb_diff_split.h`,
  `menu_option_ids.h`), Eden e Sirit (`OpAtomicFAddEXT`), `host/nn_vi.c`, `nx2/lift.py`, `nx2/oot_output_size.py`,
  `nx2/oot_patches.py`, `nx2/upgrade_output.py`, `akynoleyend/hardware.py`, `akynoleyend/maintenance.py`,
  `profiles/shader-cache-compatible.json` e os testes deles (`test_0451_render_distance.py`, `test_r13k_igpu_memory.py`).
- `git merge-file` sem conflito de texto em `akynoleyend/coherence.py`, `akynoleyend/launch.py`, `gpu/vk/vk_internal.h`,
  `gpu/vk/vk_texture.cpp`, `gpu/vk/vk_vma.cpp` e `tests/test_r13i_p0.py`. Lidos um a um: na VRAM, a linha principal separa os
  grupos de imagens (test.3) e guarda alvos sob pressao (test.4); a unificada so muda a classe de memoria da integrada
  (`device_heap_bytes`, `device_integrated`, `astc_bc_fine_bytes`). Os blocos de 64 MB da integrada valem para os dois grupos.
- `coherence.py`: a mesclagem deixou duas chaves `"0.4.5-test.1"` (uma por ramo); no dicionario a segunda apagaria a
  primeira, e uma instalacao da unificada seria recusada. Agora e uma chave so, com as identidades dos dois ramos e as da
  arvore unificada distribuida (`4062b0cf...` na ordem do Windows, `ee6953d7...` POSIX). Chave nova `"0.4.7"`: a 0.4.7 sem a
  unificada instalada no Teste-1 (`bc8ecd3c...`, do `jogo/AkynoLeyend-build.json`; a mesma conta sobre os fontes dela da
  `bc8ecd3c...`, o que confere o calculo) e a ordem POSIX (`18d4b5bd...`).
- `maintenance.py`: a migracao das dimensoes de saida (`akyno-output-sites-v3`) vale tambem para trabalhos da linha principal
  (0.4.5-test.2 a 0.4.7). Os ganchos da Distancia de renderizacao (`akyno-panel-hooks-r13-v5`) entram pela atualizacao dos
  ganchos que ja existia; a test.8/0.4.6/0.4.7 do Teste-1 tem a v2. Recompila so os blocos dos ganchos; o jogo nao e
  traduzido de novo.
- Documentos em conflito (`origem.md`, `LEIA-PRIMEIRO.txt`, `notas-atualizacao.json`) refeitos: as notas do ramo ficam
  abaixo; as notas do pacote e o LEIA-PRIMEIRO passam a descrever a 0.4.7 (os da linha principal ainda eram da test.8).
- O `HOST_REVISION` e o ABI do codigo gerado nao mudam. O carimbo de shaders `4cdbb0029868040b` continua (os dois ramos o
  mantem; os programas da soma atomica nativa sao marcados a parte pela unificada).
- DLSS: a nota da unificada ("DLL sem o SDK NGX") nao valia nem para ela (a DLL dela tem o carregador NGX estatico). A DLL
  da 0.4.7 unificada e compilada com o SDK NGX de `third_party/nvidia-dlss-sdk`, como a da linha principal; o SDK continua
  fora dos pacotes.
- DLL generica recompilada dos fontes fundidos (`nx2/build.py --standalone`, `RX_VK_ONLY=1`, `RX_RELEASE=1`, windows-gnu,
  x86-64-v3, clang 23.1.4 do LLVM-MinGW incluido, SDK NGX v310.9.16 local): 187 unidades, 0 falhas; SHA-256 `ce09a576...`,
  6.321.152 bytes; identidade dos fontes `3967e938...` (era `c281215a...`). Os mesmos 16 imports da DLL da 0.4.7 e o
  carregador NGX. O carimbo de shaders calculado por `shader_cache_stamp` e `4cdbb0029868040b` nas duas arvores.
  `verify_windows_release` ok.
- Launcher sem mudanca (identidade `256cd72e...` igual ao recibo da 0.4.7; `verify_launcher` ok); RunnerChecks 16/16 com o
  Python incluido. Atualizador avulso republicado com o .NET SDK 10.0.404 e o ZIP de atualizacao 0.4.7 embutido.
- Conferido: o ZIP de atualizacao passa por `inspect_package`, nao tem o SDK NGX nem dados do jogo, e a coherence dele aceita
  as 11 instalacoes deste disco (0.4.5, 0.4.5-test.1 a test.8 e 0.4.6 dos backups do Teste-1, a 0.4.7 do Teste-1) e as duas
  identidades da unificada.

Testes: `tests/test_047_unified.py` (novo). Suite com o Python incluido: 593 testes, 12 falhas, 56 omitidos. Com a DLL nova,
`test_r13d_device_lost` passa e ficam as 11 de ambiente de sempre: headers MSVC com `-Werror`, `-lm`, `setenv`, `<memory>`
numa fixture. A janela do launcher, o jogo e uma GPU nao foram executados aqui.

Notas do ramo unificado, como vieram:


#### Candidata de renderização e memória Vulkan

- `nx2/oot_output_size.py` sincroniza as dimensões de saída e a referência do ampliador no inicializador de vídeo. Os
  dois pares de instruções vêm de `nx2/oot_wide.py` do Hookshot no commit
  [8ef8461](https://github.com/NotRexed/Hookshot/tree/8ef84611049f4fc31835a0b12793cf074ed49c3c).
  A manutenção usa o código traduzido e recompila os blocos que contêm os ganchos. A migração usa o carimbo v3.
- `gpu/vk/vk_memory.cpp` reutiliza uma união dos intervalos de captura para cada coleta de páginas alteradas.
  A liberação de imports aposentados na NVIDIA para Windows segue o
  [Hookshot #1057](https://github.com/NotRexed/Hookshot/issues/1057). O buffer e a alocação vão embora após a
  substituição e a conclusão do uso pela GPU. O nó conserva seu endereço para as referências do replay.
  Falhas de criação e vínculo do buffer retornam o erro Vulkan e deixam a tabela sem o import inválido.
- O log distingue os alvos reais de cor e profundidade, as dimensões da imagem apresentada e sua região de origem.
  O carimbo de shaders continua `4cdbb0029868040b`.

#### Candidata 0.4.5-test.1 Render Compute

- AkynoLeyend r13l, parte 2: restaurado o uso de OpAtomicFAddEXT em buffers quando o
  Vulkan oferece os dois recursos float32 exigidos. O cache marca só os programas
  afetados e recusa código de outro caminho. O build para NVIDIA conserva a tradução anterior.
- Hookshot v2.1.0, commit 8ef84611049f4fc31835a0b12793cf074ed49c3c, vk_draw.cpp,
  precompile_run: adaptada a preparação de pipelines de malha por Compute ao
  histórico limitado da base. As variantes inéditas continuam preparadas no uso.
- vk_memory.cpp registra os resultados publicados por região de 2 MiB com páginas
  de 4 KiB. Os endereços, a ordem e o volume de cópias permanecem os mesmos.
  A consulta ainda retorna a última submissão do intervalo, inclusive se já concluída.
- O histórico anterior de 1080p da RTX 3060 Ti registra aproximadamente 61 MB de
  write-back por quadro em partida. O ganho em jogo em 720p e a imagem em GPUs
  antigas exigem teste físico. O teste isolado da tabela mede código de CPU.

#### Candidata 0.4.5-test.1 Render VRAM

O log da RTX 3060 Ti mostrava o descarte dos auxiliares de write-back sob pressão
e a retomada das cópias inteiras. A alocação dos auxiliares passa do pool inteiro
para regiões de 2 MiB com pelo menos 256 KiB de dados na submissão. Regiões sem
espaço de comparação e imports que se sobrepõem mantêm a publicação completa.
A VRAM em uso até o término da GPU permanece contabilizada no limite auxiliar.
A manutenção reutiliza as fontes das candidatas anteriores listadas no registro.

#### 0.4.5-test.1 unificada: Render Compute + Render VRAM e distância de renderização

A árvore une as candidatas Render Compute e Render VRAM sobre a 0.4.5 e traz do ramo
r13l a política de VRAM (vram_policy.h, vk_vma.cpp, vk_texture.cpp, device_integrated)
e o aviso de RAM livre do launcher (hardware.py, launch.py).

- Linha nova no F1, Tela: "Distância de renderização" (jogo, 2500, 1200, 700, 400,
  250, 150, 100 e 60 m). Aplica-se ao vivo e fica em AkynoLeyend_opts.ini;
  AKYNO_RENDER_DISTANCE a sobrepõe.
- nx2/oot_patches.py patch_render_distance: gancho depois de sead::PerspectiveProjection
  carregar near e far (+0x98/+0x9c). São dois lugares, f_834a5cc0 (virtual) e
  f_8035a8c0 (cópia inline da câmera principal, achada com HOS_WATCH). O far limitado
  vai para a matriz e para o campo +0x9c. O culling do jogo lê o campo: só com a matriz
  a imagem era cortada e os draws continuavam os mesmos. host/nn_vi.c
  hos_render_far_site guarda o far do jogo por projeção e o devolve quando o limite
  sai ou sobe. Carimbo dos ganchos: akyno-panel-hooks-r13-v5; a v4 (só matriz) é trocada.
- Medição na RTX 5070 Ti Laptop, Kokiri em 1080p, câmera parada, alternando pelo F1
  na mesma sessão: 60 m ~2440 draws a 38,5 FPS; jogo ~2890 draws a 36,2 FPS; 60 m de
  novo ~2430 draws. O ganho em CPUs antigas e em outras áreas ainda não foi medido.
- AKYNO_FAR_PROBE=1 registra as projeções vistas pelo gancho (diagnóstico).

## 0.4.8: pré-carregamento de shaders e pipelines a cada início

Pedido: pré-carregar shaders e pipelines sempre que o jogo inicia, como o NX2navi
(`E:\Games\NX2navi` 0.9.2, referência `E:\NX2navi-ref`), e aumentar a quantidade de
shaders. Do NX2navi veio a ideia (a descrição do boot em `docs/architecture.md`
dele: pipelines gravados montados na ordem em que apareceram, no máximo 20 s de
espera, o resto em segundo plano com prioridade baixa); nenhum código dele foi
copiado, como nas etapas anteriores (LICENSE-ADDITIONS).

O que havia: a cada início o renderizador já lia as anotações de pipelines
(`AkynoLeyend_pipeline_keys*.bin`) e montava o que elas pediam (`precompile_run`).
Nos modos Streaming e Equilibrado os limites eram 64/96 MiB, 128/192 programas e
256/384 anotações, e os programas eram escolhidos pela posição no disco, junto com
todos os de compute guardados. No Teste-1 (14/11/2026, partidas das 17:38 e 19:13):
"bounded warmup: 128 variants, 10 MiB", "precompile: 128 programs, 256 graphics
notes, 11 graphics and 117 compute pipelines built" — de 3.759 anotações gráficas
(2.535 programas) no arquivo do caminho com mesh shaders e 46.611 programas no cache.

Mudanças:
- `gpu/vk/vk_shader.cpp` `program_cache_load_some`: os programas das anotações, na
  ordem das anotações, alternados com os de compute guardados (por posição no disco);
  um limite que acaba cedo deixa parte para os dois. A linha do log passou a ser
  "vk: preload: N variants of N named and N compute programs ...".
- `gpu/vk/vk_draw.cpp` `precompile_run`: os pipelines de compute e os de malha por
  Compute ficam prontos antes do jogo (um dispatch nunca é pulado: esperaria). Os
  gráficos são montados na ordem das anotações; o início espera por eles no máximo
  `RX_VK_PRELOAD_WAIT_MS` (20000; 0 espera todos, como antes; a preparação espera
  todos). Os trabalhadores continuam depois que o jogo abre: `RX_VK_PRELOAD_THREADS`
  (2) deles, em `THREAD_PRIORITY_LOWEST`. Eles nunca tocam no mapa `pipelines` (é do
  replay): entregam o pipeline em `preloaded`, sob `preload_mu`, e
  `graphics_pipeline` o adota na primeira vez que um desenho pede aquela chave
  (`preload_take`). Uma chave que um desenho pediu antes fica marcada, e o
  pré-carregamento descarta o que montou para ela (`preload_give`). O marcador
  `.running` continua cobrindo só a parte que o início espera: uma queda no jogo com
  o resto montando atrás não apaga as anotações. Linhas novas no log: "vk: preload:
  ... workers before play" e "vk: preload: the background part is done ...";
  `tools/analisar_log_shaders.py` lê as duas (`preload_background`).
- `gpu/vk/cache_policy.h`: tetos de `RX_VK_PREWARM_MB` 4096, `RX_VK_PREWARM_PROGRAMS`
  e `RX_VK_PREWARM_PIPELINES` 65536. `akynoleyend/environment.py`: Streaming 256 MiB,
  2.048 programas, 4.096 anotações; Equilibrado 512 MiB, 4.096 e 8.192. A preparação
  (`preparacao`) herda os do Streaming.
- Carimbo de shaders: `vk_shader.cpp` e `vk_shader.h` entram na impressão digital dos
  fontes de tradução. Eden, sirit, compat, `vk_state.h` e `vk_api.h` são os da 0.4.7
  byte a byte; a impressão nova (`241790bd…`) foi registrada em
  `profiles/shader-cache-compatible.json` com o carimbo `4cdbb0029868040b`, e as
  traduções guardadas continuam valendo.
- Versão 0.4.8 em `VERSION`, `__init__.py`, nos dois `.csproj`, em `Core.cs` (`From`
  ganha "0.4.7") e em `make_distribution.py`. `coherence.py["0.4.7"]` ganha a
  identidade da 0.4.7 unificada instalada (`7661e6c9…`, POSIX `b3c7d8cb…`).
  `tests/test_048_preload.py` confere tudo isso nos fontes; a conferência da versão
  saiu de `test_047_launcher.py`.

Shaders do NX2navi: a semente dele (`seed-programs.bin`, 42.142 estágios) e a da
AkynoLeyend (`AkynoLeyend_shaders.bin`, 42.856 estágios, 38.809 programas) têm quase
os mesmos shaders do jogo; as diferenças de chave vêm do corte do código (o NX2navi
guarda o código até o fim das constantes c1). Só 127 estágios do NX2navi (104 de
fragmento, 13 de vértice, 9 de compute, 1 de tarefa) não estão na nossa semente. As
traduções dele (SPIR-V do tradutor do Ryujinx, `shader-cache`) e o cache de pipelines
dele (`pipeline-cache.bin`, do driver, com o layout de descritores dele) não servem ao
nosso renderizador (tradutor do Eden, outro layout), e são dados derivados do jogo do
jogador: não entram nos fontes nem nos pacotes.

Os 127 estágios foram procurados em toda a RomFS e na ExeFS da cópia do jogo do Teste-1 com os leitores do
nosso censo (`nx2/shader_census.py`, `nx2/shader_containers.py`; a ExeFS descomprimida pelo `nso.py` do a64-kit:
nenhum BNSH nem seção de controle NVN), e nenhum foi achado. Não vêm dos arquivos do jogo que a AkynoLeyend lê
(provavelmente outra versão do jogo ou outro leitor), então o censo não mudou e o banco continua o mesmo. Um
carimbo da preparação com o tamanho do banco chegou a ser escrito e foi retirado: sem shader novo, ele só faria
todos repassarem a preparação inteira uma vez depois da atualização.
