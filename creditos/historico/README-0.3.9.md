# Atualizacao 0.3.9-dev.1

Esta entrega corrige o caminho de sincronizacao associado ao device lost do shader 53caac5f nos logs enviados, preserva contadores de iluminacao escritos pela CPU e implementa leituras globais de 8/16 bits antes ausentes. Tambem evita consultas repetidas a lista de uniformes e identifica perda do dispositivo como falha, sem continuar exibindo apenas FPS sobre tela preta.

**Na instalacao 0.3.8 atual: aplique os arquivos e use Atualizar-Renderizador.cmd; nao recompile o jogo inteiro.** Depois execute Preparar-Shaders.cmd uma vez e Jogar.cmd. O preparador agora termina apos salvar o cache, antes da partida. O cache traduzido e renovado porque o tradutor mudou; work, EXE, imagem e saves permanecem.

Leia [LEIA-ME-0.3.9.txt](LEIA-ME-0.3.9.txt) e [o relatorio de continuidade](docs/HANDOFF-OUTRA-IA.md). A interface WPF publicada continua na versao 0.3.2. A nova DLL passou pela compilacao Windows e pelos testes sinteticos; o resultado visual ainda deve ser confirmado no PC do usuario. Abaixo fica o historico anterior.

# Ocarina Hookshot — base independente

Versao **0.3.8-dev.2**, construida a partir dos fontes de `Hookshot-Release.zip` enviados pelo usuario. Mantem o lifter ARM64, o runtime e o renderizador Vulkan desse projeto como um conjunto. A orquestracao de compilacao, os perfis e os registros desta versao ficam no pacote Python `ocarina/`.

Esta e uma base de desenvolvimento experimental. A compilacao do renderizador para Windows foi verificada; o jogo completo ainda precisa ser compilado e testado no PC de destino. Nao ha promessa de FPS, de consumo fixo de VRAM ou de resolucao de todos os crashes. O status do projeto original esta arquivado em `docs/upstream/`.

## Correcao de acesso 0.3.8-dev.2

O novo diagnostico mostrou WinError5 nos tres arquivos publicados, inclusive ao consultar suas ACLs. A publicacao a partir de pastas temporarias protegidas sob UAC corresponde a um problema documentado do Python. Os cinco pontos de publicacao agora concedem acesso ao SID real do criador, mantendo a pasta privada, sem depender somente de OWNER RIGHTS.

Para reparar uma instalacao ja afetada, aplique a correcao e abra `Reparar-Acesso.cmd` normalmente. Ele pede elevacao somente para ajustar os arquivos nomeados; depois verifica leitura/hashes como usuario normal. Preserve work/jogo. Leia `LEIA-ME-REPARO-ACESSO.txt`. A causa e o sucesso no PC ainda devem ser confirmados pelo registro do reparo; nao houve alteracao grafica nesta correcao.

## Atualizacao 0.3.8: acesso, preparacao e comparacao ASTC

A falha de acesso ao EXE antes de jogar passa a produzir uma mensagem direta e um ZIP de diagnostico, mantendo a conferencia SHA-256. `Diagnosticar-Acesso.cmd` funciona mesmo sem conseguir validar o build; consulta leitura, tipo do arquivo, erro Win32 e permissoes sem muda-las. O bloqueio real do Windows ainda depende do resultado dessa coleta.

`Atualizar-Renderizador.cmd` atualiza somente a DLL generica de builds locais 0.3.6/0.3.7/0.3.8 cuja ABI foi conferida. `Preparar-Shaders.cmd` faz essa atualizacao, monta um banco privado a partir da RomFS e inicia a preparacao com progresso. Nao recompila o C do jogo. O banco fica no disco, com indice em RAM, entradas brutas simultaneas de ate16MiB, I/O de ate64KiB e dois workers por padrao. Sao limites dessas categorias, nao de toda a memoria do driver/jogo.

`Testar-Luzes.cmd` registra flashes grandes e exposicao sem gravar cada frame. `Jogar-Sem-BC3.cmd` e `Jogar-ASTC-CPU.cmd` oferecem comparacoes explicitas, registradas no log. O material `astc_analysis.rar` contem configuracoes/trechos OpenGL do Eden/Yuzu e nao comprova uma correcao das piscadas no Vulkan. **A causa visual continua pendente de teste A/B na mesma cena**; nao foi anunciada como resolvida.

Para atualizar, copie o conteudo desta pasta para a instalacao existente, substituindo os fontes e preservando `work`/`jogo`; o nome antigo da pasta pode continuar. Nao mova a RomFS registrada no manifesto. Consulte `LEIA-ME-0.3.8.txt` e `docs/HANDOFF-OUTRA-IA.md`.

## Atualizacao 0.3.7: instalacao e memoria

Instalacoes novas usam alvo de 6 MiB por bloco normal de C; limites existentes sao preservados para manter o cache. O pacote completo inclui a DLL Vulkan generica pronta, conferida por hashes dos fontes/dependencias/binario. Fontes alterados ou configuracao diferente usam compilacao local; `manage.py build --renderer-source` a solicita explicitamente. A copia pronta nao contem dados do jogo.

Placas da classe de 12 GiB passam a usar no maximo 1 GiB para mirrors por padrao. A politica de 8 GiB foi preservada; o perfil experimental 8gb continua disponivel. Esse limite nao e um teto global de VRAM nem uma garantia de FPS. A auditoria distingue acesso negado de ausencia e recusa cache incompleto antes de repetir uma extracao grande.

Tempos observados ficam em `work/build-timings.json`; acertos reais do cache em `work/logs/compile-summary.json`. O tradutor de shaders preserva a identidade da 0.3.6. A interface WPF continua na publicacao 0.3.2. Leia `LEIA-ME-0.3.7.txt` e `docs/HANDOFF-OUTRA-IA.md` para instalacao, estudo e limitacoes.

## Atualizacao 0.3.6: folhagem, iluminacao e diagnostico

Integra `foliage-linux-updater` (commit `170ce53`), incluindo `movie-sync` (commit `44abdcd`), preservando os ajustes locais de audio, caminhos e cache Streaming. Inclui folhagem/iluminacao de EvilOOT, backoff de importacao de memoria, tempo real por padrao, rumble, sincronizacao do filme e solicitacao de GPU dedicada. SDL2 Windows esta incluida. A imagem e o desempenho ainda precisam de teste real. O atualizador oficial e o AppImage Linux nao foram integrados nesta distribuicao Windows. O launcher e suas etapas usam UTF-8 explicitamente, inclusive com Python isolado.

O build escolhe o paralelismo automatico apos a traducao e informa RAM/processos no log. Cada unidade em compilacao mostra seu PID e mensagens de espera a cada 15 segundos. Isso melhora a escolha e a visibilidade; nao garante build em 40 minutos. As opcoes manuais continuam sendo respeitadas.

A pasta RomFS precisa conter `System` e `Pack`; uma raiz sem essa estrutura falha antes da compilacao/execucao. Use `Auditar-RomFS.cmd` para sondar os caminhos sem abrir o jogo. Coletas sem encerramento nem CRASH passam a mostrar erro explicito. Leia **LEIA-ME-0.3.6.txt** e **docs/HANDOFF-OUTRA-IA.md**.

Os fontes/ABI do tradutor mudaram: o cache de programas/pipelines preparadas pode precisar ser regenerado. Nao use o stamp de compatibilidade da 0.3.5 nesta versao.

## Atualizacao 0.3.5: cache Streaming

Para atualizar a 0.3.4, extraia somente o ZIP de atualizacao na pasta existente, preserve `work`/`jogo` e clique **Criar** com a mesma entrada e destino. Depois use **Jogar-Streaming.cmd**. O botao Jogar da interface continua no cache Original; nao ha nova publicacao WPF nesta versao.

O backend agora oferece janela de leitura antecipada de 16 MiB, indice e pre-aquecimento limitados, dois workers, token bucket e I/O de arquivos em ate 64 KiB. O snapshot do cache do driver tem teto de 128 MiB e arquivo separado. Esses limites nao sao um teto global de RAM/VRAM nem promessa de zero stutter. Dados de programas e pipelines continuam compativeis quando GPU/driver/opcoes e identidade do tradutor conferem.

Leia `LEIA-ME-ATUALIZACAO-0.3.5.txt`, [cache-streaming.md](docs/cache-streaming.md), [drivers-amd-nvidia.md](docs/drivers-amd-nvidia.md) e a [analise do log externo RX580](docs/caso-rx580-build-externa.md). Folhagem/iluminacao e suporte completo a placas sem mesh shaders continuam pendentes. Resultados dos testes desta entrega estao em `docs/validacao-0.3.5.json`.

## Comecar no Windows

1. Extraia **todo** o pacote Windows para uma pasta nova e curta, por exemplo `C:\OcarinaHookshot`. Mantenha `ferramentas`, `manage.py` e `OcarinaBuilder.exe` juntos.
2. Abra **OcarinaBuilder.exe**. A interface inicia em portugues, com o tema escuro do Hookshot Builder.
3. Selecione sua copia local `.nup`, ou as pastas `romfs` e `exefs`. Tambem pode arrastar os arquivos para a janela. O build suportado continua sendo `e0f3ccfa`.
4. Escolha a pasta de destino e clique em **Criar**. O modo automatico ajusta o numero de processos a RAM disponivel; tambem e possivel escolher de um a oito.
5. Acompanhe as etapas. A porcentagem da compilacao conta arquivos concluidos; as outras etapas mostram atividade sem inventar porcentagens. **Mostrar detalhes** abre o registro, que aparece automaticamente em caso de falha.
6. Ao terminar, use **Jogar** ou **Abrir pasta**. O perfil inicial e **Original**. **8 GB (experimental)** serve para comparar a mesma cena; ele nao garante um teto global de VRAM.

Para abrir um build existente, escolha sua pasta de destino: o botao **Jogar** aparece quando ha um manifesto. A integridade dos arquivos e conferida pelo Python antes de iniciar. O jogo e executado com a pasta `romfs` registrada e os logs de diagnostico.

Os atalhos de terminal continuam disponiveis: `Verificar.cmd`, `Compilar.cmd`, `Jogar.cmd` e `Jogar-8GB.cmd`. Os destinos padrao da interface e dos atalhos sao a mesma pasta `jogo`, ao lado do projeto.

Use a mesma pasta extraida nas proximas compilacoes para aproveitar o cache. Os fontes e caches da instalacao antiga do Ocarina nao sao copiados para esta base.

### Entradas em pastas

```powershell
.\Compilar.cmd -Exefs "D:\MeuJogo\exefs" -Romfs "D:\MeuJogo\romfs"
```

O programa trabalha sobre uma copia privada dos modulos quando precisa descomprimir ZBIC. A pasta `romfs` e lida em seu local original, sem copiar dezenas de gigabytes. Mantenha esse local disponivel ao jogar. A compilacao recusa uma pasta de saida desconhecida que ja contenha arquivos.

### Parametros uteis

```powershell
.\Compilar.cmd -Jogo "D:\Jogos\meu-jogo.nup" -Jobs 1
.\Compilar.cmd -Destino "D:\OcarinaHookshot\jogo" -Trabalho "D:\OcarinaHookshot\work"
.\Jogar.cmd --out "D:\OcarinaHookshot\jogo" --dry-run
.\Jogar-8GB.cmd --out "D:\OcarinaHookshot\jogo"
```

Sem `-Jobs`, o programa considera a memoria **disponivel**, reserva margem para o sistema e permite ate oito processos de compilacao. O calculo e uma estimativa; use `-Jobs 1` quando houver pouca folga.

## O que mudou

- Um fluxo de build em `ocarina/build.py`, com validacao da entrada antes da traducao.
- Dependencias locais explicitas e conferidas antes da compilacao longa.
- LLVM-MinGW portatil e FFmpeg minimo para VP8/VP9, sem depender dos caminhos de desenvolvimento do autor original.
- Cache de objetos com identidade do compilador, flags e headers. Compilacao interrompida nao sobrescreve um objeto valido.
- Publicacao conferida por SHA-256. O lancador recusa executavel, DLL ou imagem de outra compilacao.
- Logs por tentativa, com perfil, hashes e codigo de encerramento.
- Perfis explicitos; variaveis experimentais herdadas de outras tentativas sao retiradas do processo filho.
- Build apenas Vulkan. Uma falha de carregamento do renderizador produz um erro explicito, em vez de prosseguir com uma alternativa grafica ausente.

O menu grafico do jogo e a logica de traducao do Hookshot foram preservados. Nao foram transportados os patches do runtime C do Ocarina anterior que omitiam pools/desenhos invalidos.

## Requisitos do jogo

- Windows 10/11 x64 e driver Vulkan compativel com os recursos exigidos pelo Hookshot, incluindo mesh/task shaders.
- CPU com o conjunto x86-64-v3 usado pela base (AVX2/FMA/BMI); Ryzen 3500X e 5700X fazem parte da classe de CPUs alvo.
- RAM e armazenamento suficientes para o build e a execucao. O projeto original indica pelo menos 16 GB de RAM e cerca de 60 GB livres durante a compilacao; isso nao garante bom funcionamento em qualquer maquina.
- As introducoes AV1 usam Media Foundation, como no Hookshot original. Se o Windows nao disponibilizar um decoder AV1, o log informa a falta; o codec do sistema ainda pode ser necessario.
- SDL2 Windows esta incluida com sua licenca; o build publica a DLL ao lado do jogo para os controles/rumble que usam essa camada. Teclado/mouse e XInput continuam disponiveis.

O ZIP Windows inclui a interface, seu runtime .NET e as ferramentas locais. Nao e necessario instalar Python ou .NET para usa-lo. Ele nao contem jogo, chaves, saves, caches ou executavel recompilado do jogo.

## Diagnostico

Cada tentativa cria `jogo\diagnosticos\DATA-HORA-PID\` com `saida.log`, `erros.log` e `execucao.json`. Compartilhe os tres arquivos da mesma tentativa quando investigar um problema.

```powershell
.\Jogar.cmd --diagnostic
```

Esse modo solicita a camada Khronos de validacao, que deve estar instalada separadamente. Ele tem custo e pode falhar ao iniciar se a camada estiver ausente. Para medir desempenho, use o modo normal. Detalhes dos perfis e a conferencia das nove variaveis sugeridas anteriormente: `docs/perfis.md`.

## Desenvolvimento

```powershell
.\ferramentas\python\python.exe -I .\manage.py doctor
.\ferramentas\python\python.exe -m unittest discover -s tests -v
```

O ZIP de fontes separado usa a pasta `ferramentas` do pacote Windows, ou `--tools` apontando para ela. Os testes sinteticos de fluxo nao exigem o jogo. Testes diferenciais do lifter original continuam em `nx2/` e precisam das entradas locais apropriadas.

Leia `docs/arquitetura.md`, `docs/validacao.md` e `docs/origem.md`. As licencas originais foram preservadas em `LICENSE`, nos componentes e em `THIRD_PARTY_NOTICES.md`.

## Interface e atualizacao

A interface chama `manage.py` e usa a mesma implementacao dos atalhos. `check` confere o cabecalho e a versao sem extrair dados; `build` executa as etapas; `run` verifica o resultado e registra a partida. A interface nao executa `hookshot.exe` diretamente.

O pacote de atualizacao da interface deve ser extraido **dentro da pasta existente** que contem `Compilar.cmd` e `ferramentas`. Autorize a substituicao dos arquivos correspondentes e abra `OcarinaBuilder.exe`. Ele nao inclui as ferramentas grandes. Para uma instalacao nova, use o pacote Windows completo.

Os arquivos intermediarios continuam em `work` ao lado do projeto. O espaco livre exibido corresponde a esse disco; a pasta de saida pode estar em outro disco. Mantenha a pasta e os arquivos de entrada disponiveis, especialmente `romfs` quando usado diretamente.

A versao 0.3.1 inclui a correcao do erro `Join-Path ... Path ... empty string` em `compilar.ps1`. Os caminhos padrao sao calculados no corpo do script, depois da vinculacao dos parametros. Abrir `Jogar.cmd` antes de concluir o build agora mostra uma orientacao direta sobre a etapa que falta.

Para recompilar a interface a partir dos fontes, com o SDK .NET 8 instalado:

```powershell
dotnet publish .\builder\OcarinaBuilder\OcarinaBuilder.csproj -c Release -r win-x64 --self-contained true -o .\dist\interface
Copy-Item .\dist\interface\OcarinaBuilder.exe .\OcarinaBuilder.exe
```

O pacote apenas de fontes omite o executavel da interface e as ferramentas, mas contem seu projeto completo.

## Falha ao salvar work/image/chunks.txt

A correcao de `nx2/chunks.py` incluida neste pacote cria o diretorio dos limites compartilhados na primeira geracao standalone. Para uma instalacao ja extraida, aplique apenas `Ocarina-Builder-0.3.1-correcao-chunks.zip`, mantenha a pasta `work` e repita **Criar** com a mesma entrada e destino. A extracao completa e reaproveitada; a etapa do lifter e repetida. Detalhes em `docs/correcao-chunks.md`.

## Atualizacao de split_hot e NUP compactado

A correcao cumulativa `Ocarina-Builder-0.3.1-correcao-split-nup.zip` inclui a lista de otimizacao do pacote novo, a selecao condicional da etapa split e o leitor NUP com Zstandard. Copie seu conteudo para a instalacao existente, mantenha work e repita Criar. O programa confere a extracao privada antiga e repara arquivos compactados quando necessario. Os arquivos normais continuam validos quando nao ha funcoes separadas. Escopo e testes em `docs/atualizacao-split-nup.md`.

## Atualizacao 0.3.2: iluminacao, videos e AMD

Esta versao incorpora os fontes do HookshotBuilder (2).zip fornecido, incluindo a espera do renderizador antes da primeira submissao GPU, o ajuste de neblina 0.08 e o upscale de filmes por compute shader. As correcoes sao automaticas no perfil Original; nao e preciso ativar um perfil AMD.

Para atualizar 0.3.1, feche o programa, extraia o conteudo de Ocarina-Builder-0.3.2-atualizacao-AMD.zip na mesma pasta que possui OcarinaBuilder.exe e aceite substituir. Preserve work, ferramentas e jogo. Abra a interface, selecione a mesma entrada/destino e clique Criar. O renderizador precisa ser recompilado; os objetos de jogo que mantiverem a mesma identidade podem ser reaproveitados. Use Original no primeiro teste.

Detalhes, escolhas de qualidade e limites em docs/atualizacao-amd.md. O resultado de 60 FPS informado pelo usuario pertence ao Hookshot fornecido, nao a um benchmark desta adaptacao.

O automatico agora permite ate oito compiladores, condicionado a RAM livre e aos nucleos. Mantem a reserva de 2 GiB e o orcamento estimado de 3.5 GiB por processo: com 24 GiB livres escolhe seis; com 16 GiB livres continua em quatro. Isso pode reduzir o primeiro build em PCs com folga, sem prometer um tempo fixo ou reduzir a otimizacao do codigo do jogo.

## Atualizacao 0.3.3 — pointer-lighting-2

Integracao dos fontes do HookshotBuilder(3).zip, com identidade conferida contra o asset oficial. Corrige o escopo de leituras indiretas dos shaders, permite cache estavel entre inicios e incorpora o fallback de imagens/pools, o parser de idioma e as melhorias de energia/progresso do build.

Aplique Ocarina-Builder-0.3.3-atualizacao.zip na instalacao 0.3.2 existente e repita Criar com a mesma entrada/destino. Preserve work e jogo/user/save. Depois use Jogar-Teste-Crash.cmd para testar o caminho curto de RomFS e reunir diagnosticos. Coletar-Crash.cmd reune a ultima execucao sem abrir o jogo. Veja LEIA-ME-ATUALIZACAO-0.3.3.txt e docs/atualizacao-0.3.3.md.

A integracao nao comprova correcao do ultimo crash de CPU 0xC0000005. O mapa e os novos logs permitem verificar sua origem. A interface WPF e mantida; os fontes e o motor foram atualizados.

## Atualizacao 0.3.4 — caminhos longos, audio e comparacao de movimento

O novo log permitiu reproduzir um defeito concreto: a raiz de extracao tinha 160 caracteres e arquivos de iluminacao ultrapassavam o buffer antigo de 260 bytes. O filesystem nativo agora usa buffers de 4096 bytes, rejeita overflow e chama APIs Windows UTF-16 com caminhos estendidos. Isso trata a diferenca entre abrir pelo launcher e pelo script que abrevia RomFS; ainda precisa ser confirmado no jogo apos recompilar.

O audio usa WASAPI compartilhado com conversao de formato pelo Windows, fallback waveOut e reconexao. GetAudioDeviceOutputVolume deixou de ser um stub e devolve o float no registrador correto. As mudancas valem para AMD e NVIDIA, pois pertencem ao host Windows.

Aplique Ocarina-Builder-0.3.4-atualizacao.zip na instalacao 0.3.2/0.3.3 existente, mantenha work e jogo, e repita Criar com a mesma entrada/destino. Teste primeiro pelo botao Jogar. Jogar-Nitido.cmd oferece uma comparacao sem a rede temporal de gameplay, a 100% de resolucao; pode mostrar mais serrilhado. Jogar-Suporte.cmd registra audio e pausas, sem ativar validacao Vulkan ou trace de todos os arquivos.

Folhas ausentes, iluminacao incorreta e sombras piscando continuam pendentes de validacao/correcao do renderizador. O modo Nitido nao e apresentado como conserto desses problemas. A identidade do tradutor de shaders desta atualizacao e igual a 0.3.3: os caches existentes continuam elegiveis na mesma GPU/driver/perfil. Areas novas ainda podem apresentar stutter de compilacao. Veja LEIA-ME-ATUALIZACAO-0.3.4.txt e docs/atualizacao-0.3.4.md.
