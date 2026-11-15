# Integracao AMD e iluminacao — 0.3.2-dev.1

## Alteracoes aplicadas ao motor

- **Iluminacao de inicio:** host/display.c publica um evento apos iniciar o renderizador; host/nvn_native.c aguarda esse evento antes da primeira submissao de comandos. Evita perder as primeiras tarefas GPU durante a preparacao dos shaders. Falhas ao criar evento/thread ou iniciar o Vulkan encerram com erro explicito.
- **Neblina e exposicao:** workaround de formato IR do Hookshot/Orchid ativo por padrao, com fog 0.08 e exposicao 0.65. Ele reduz a neblina branca; nao resolve a causa original nem reproduz necessariamente todos os ambientes com exatidao.
- **Filmes AMD:** shader movie_upscale.comp e SPIR-V correspondente incluidos e usados pelo backend. Substitui o blit que podia produzir preto por leitura amostrada e escrita em storage image. Mantem a alternativa anterior quando recursos/criacoes Vulkan falham.
- **Custo dos filmes:** politica do Hookshot ignora determinadas redes de upscale em GPUs fora do caminho adequado e amplia linearmente a imagem decodificada. A qualidade pode diferir do upscale neural. O decoder AV1 continua sendo o Media Foundation do Windows; esta entrega nao adiciona um decoder AV1 novo.
- **Subgrupos:** consulta suporte real a subgroup-size control e solicita 32 lanes nos estagios suportados. O tradutor recebe o tamanho observado e o maximo do dispositivo. Nao e forcado um recurso indisponivel.
- **Matrizes:** fallback automatico no shader quando a extensao/layout de cooperative matrix nao serve, herdado do Hookshot novo. Software MMA aqui significa shader na GPU, nao decoder ou renderizacao na CPU.
- **Picos de memoria:** novo default de mirrors equivalente a um quarto da VRAM, limitado a 3 GiB; configuracoes explicitas continuam possiveis. Isso nao limita toda a VRAM do processo. Atualizacoes de textura, transferencias, framegen e task/mesh foram integradas como conjunto.
- **Flashes:** protecao herdada contra NaN/Inf em saidas float de fragmentos antes da propagacao pelo bloom.
- **Perfil AMD do emulador:** offset de texture gather para AMD e workaround de Position SPIR-V para o driver AMD proprietario, com identificacao de driver consultada no Vulkan.
- **Cache:** o stamp considera tradutor e identidade da GPU/driver/subgrupos/MMA. Evita transportar SPIR-V especifico de NVIDIA para AMD sem regeneracao.
- **Link:** comandos opcionais de captura do backend WebGPU nao referenciam quatro funcoes ausentes no build exclusivamente Vulkan. O comando de synclog continua; comandos indisponiveis geram mensagem. Nenhuma operacao de jogo foi substituida por stub para fechar o link.

O caminho experimental de reescrita de mesh indirect do novo Hookshot permanece desativado por padrao, como no pacote recebido. Nao foram ativadas variaveis de diagnostico, compilacao sincrona extra ou validacao Vulkan no perfil Original.

## Tempo de compilacao

O automatico deixa de ter um teto artificial de quatro processos: permite ate oito quando CPU e RAM livre comportam. Preserva 2 GiB para o sistema e estima 3.5 GiB por compilador. Exemplos: 16 GiB livres -> quatro; 24 GiB -> seis; 32 GiB -> oito, sujeitos aos nucleos. A interface oferece 1–8 manualmente; o automatico e preferivel para respeitar memoria.

A atualizacao nao altera as flags O1/O2 das unidades traduzidas, mantendo a elegibilidade dos objetos ja compilados no mesmo caminho. Um teste adicional verifica por processo externo que a segunda compilacao e a recuperacao do cache nao invocam o compilador, enquanto uma mudanca real de flags o invoca. Nao foi medido o primeiro build real com o jogo nesta versao.

## Fontes e evidencia

Comparacao por bytes entre HookshotBuilder (1)(1).zip e HookshotBuilder (2).zip: seis arquivos existentes alterados e dois novos shaders; todos os arquivos relevantes de iluminacao e filmes foram integrados. As alteracoes AMD anteriores do primeiro pacote tambem estao incluidas. Os hashes de origem ficam em upstream.json; o diff da integracao em patches/amd-0.3.2.patch.

O emulador eglantine_NX2_forkMDias-Eglantine_Litchii_forkMDias_v4.zip foi inspecionado em fonte. Apenas workarounds encontrados no codigo foram adaptados; promessas de FPS, correcao de fog e suporte tensor do README nao foram usadas como prova de implementacao ou benchmark.

## Verificacao e limites

Foi executado o pipeline real nx2/build.py com LLVM-MinGW 20261020, alvo Windows x64, headers/runtime gerados genericos e unidades de jogo vazias sinteticas: 352 unidades C/C++ compilaram e o host EXE e a DLL Vulkan fecharam o link sem simbolos ausentes. O fixture verifica o fechamento do runtime, nao o codigo traduzido real do jogo. Os binarios sinteticos nao sao distribuidos.

A interface WPF foi publicada para Windows x64 com o SDK .NET 8.0.427, sem executar a janela neste host Linux. Resultados completos em resultado-native-amd.txt e resultado-testes.txt.

Nao houve jogo executado, GPU AMD fisica, validacao de SPIR-V em driver nem benchmark desta adaptacao. Os 60 FPS informados pelo usuario referem-se ao pacote Hookshot recebido. Pools acima de limites do driver, exaustao global de memoria, device lost e crash na troca de foco ainda precisam ser verificados em execucao; nao foram escondidos descartando operacoes adicionais.

## Atualizar e comparar

Extraia a atualizacao na instalacao existente, preserve work e use a mesma entrada/destino ao clicar Criar. O lifter pode ser repetido, mas objetos com conteudo/flags/headers identicos continuam elegiveis ao cache. O host e o backend alterados serao recompilados.

Teste Original na mesma resolucao e cena do Hookshot que atingiu 60 FPS. Compare personagens, neblina, transicao do filme para gameplay e depois a troca de foco. Registre GPU/driver e guarde execucao.json, saida.log e erros.log da mesma tentativa. A pasta de diagnosticos fica no destino do jogo. Somente depois compare o perfil 8 GB experimental.
