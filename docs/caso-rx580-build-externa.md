# RX580: analise de uma build externa

O usuario informou que este teste foi feito em outra build do Hookshot, recebida de uma terceira pessoa. O arquivo analisado foi `hookshot_log(1).txt`, com 534925 bytes. Nao ha identidade/hash suficientes para identifica-la como nossa 0.3.4 ou 0.3.5. O relato de RTX4090 a 30–40 FPS e outro caso, sem log correspondente. As duas imagens mostram folhagem muito clara e corrupcao multicolorida; nao foi demonstrado qual GPU produziu cada imagem.

## Evidencias do log

| Registro | Observado | Interpretacao sustentada |
|---|---|---|
| Dispositivo | AMD Radeon RX580 2048SP, Vulkan 1.3, driver 0x800117 | Nao deduzir a versao comercial Adrenalin apenas desse hexadecimal |
| Recursos | Mesh shaders: nao; pipeline libraries: nao; subgrupo 64; sem cooperativa de matrizes | Recursos importantes do caminho graﬁco estao ausentes; software MMA nao substitui todos eles |
| Inicializacao | 740 programas, 918 pipelines graficas e 109 compute em 183422 ms | Cerca de tres minutos apenas nesse pre-aquecimento |
| Cache de programas | 21930 chaves, 3706813 KB | Cerca de 3.5 GiB no arquivo; nao e medicao de RAM residente |
| Cache de pipelines | 17651 KB | Cache de driver em disco, separado do banco de programas |
| VRAM reportada | Aproximadamente 994–1118 MB usados, 7402 MB permitidos | Nao registra esgotamento de VRAM nessa tentativa |
| Texturas | Cerca de 91 MB no trecho final | Nao prova que toda a cena esteja desenhada corretamente |
| Renderizacao | Cerca de 19 draws e 12 omitidos por frame no trecho jogavel | Investigar os motivos das omissoes; FPS sozinho pode ocultar imagem incompleta |
| Programas | Dez falhas registradas, com mensagens de rede omitida nessa placa | Caminho neural/compute sem suporte; nao sao dez crashes demonstrados |
| Picos | Dispatch com 990.5 ms e outro com 3920.8 ms na selecao de programa | Ha pausas graves na CPU/caminho de selecao, nao so custo de desenho da GPU |
| Trecho final | 4560 presents, 38.7 FPS; contador VI proximo de 39 FPS | Medicoes locais; o inicio tambem mostra 60 FPS em outros trechos |
| GPU no trecho final | Cerca de 4.1 ms por frame; espera GPU-bound perto de 0.1 ms | Nao basta para concluir GPU saturada; refere-se ao trabalho efetivamente submetido |
| Resolucao | Texturas de janela 2560x1440; swapchain 1280x720; crop 1536x864 | Resolucao de saida nao equivale a todo o custo interno |
| Encerramento | Janela fechada, saindo | Nao ha DEVICE_LOST/crash fatal demonstrado no fim desse arquivo |

O boot declara 9809 MB de memoria para o guest e heap de 6894 MB; esses numeros nao medem diretamente a RAM fisica residente do processo. O primeiro contador de 0.6 FPS inclui o longo startup e nao representa desempenho constante da cena.

## O que isso muda no nosso trabalho

A RX580 deste log nao oferece mesh shaders, exigidos por partes da base atual. Compatibilidade completa nessa placa precisaria de um caminho alternativo de geometria e verificacao de imagem; reduzir o cache nao cria esse recurso. Nao habilitar Wave32 ou pipeline libraries a forca.

O pre-aquecimento longo sustenta testar a nova politica limitada. O log tambem alterna continuamente o intervalo de apresentacao 1/4 com backtraces. No nosso codigo o registro foi limitado em execucao normal; o trace explicito continua disponivel. O intervalo pedido pelo jogo e a chamada de pacing permanecem iguais. Nao inferir 15 FPS apenas do numero 4: o runtime tem sua propria implementacao de sincronizacao.

As cores anormais, luzes saturadas e folhas faltando exigem investigar traducao de shaders, formatos, descritores, recursos omitidos e sincronizacao. Nao foi aplicada uma reducao arbitraria de gamma/exposicao para mascarar esses sintomas. O relato semelhante numa RTX4090 torna uma causa compartilhada do backend uma hipotese util, mas nao confirma que seja exatamente o mesmo defeito da RX580.

Para a RTX4090 faltam: hash/versao da build, CPU, driver, resolucao interna, opcoes e logs da tentativa. Uma GPU mais forte nao elimina automaticamente trabalho serial de CPU, compilacao ou erro de renderizacao.

## Comparacao necessaria

Na mesma maquina e build identificada, comparar Original e Streaming na mesma cena e resolucao, primeira e segunda abertura. Registrar frametimes, cache hits/misses, tempo de precompile, memoria do processo e draws omitidos. Manter os logs de cada GPU separados. Resultados desta outra build nao validam a correcao ou o FPS da nossa.

O pacote nao inclui o log original, imagens, dados do jogo ou caminhos pessoais do teste.
