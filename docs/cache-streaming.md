> Nota 0.3.6: os limites abaixo continuam disponiveis, mas a nova base foliage-linux-updater altera IR/ABI. A compatibilidade auditada da0.3.5 nao deve ser forçada; o cache de programas/preparacao pode ser reconstruido.

# Cache Streaming — 0.3.5-dev.1

O modo `streaming` implementa limites no backend Vulkan e pode ser combinado com os perfis visuais Original, 8gb ou Nitido. O cache Original permanece como comparacao. A janela WPF nao mudou: use `Jogar-Streaming.cmd` para ativar o modo novo.

```powershell
.\Jogar-Streaming.cmd
.\Jogar-Streaming.cmd --profile nitido --out "D:\MeuJogo"
.\Jogar-Suporte.cmd --cache-mode streaming
```

Recompile pela interface com a mesma entrada/pasta antes de testar. A atualizacao de Python sozinha nao modifica uma DLL ja compilada. Preserve `work` para aproveitar objetos validos; mudancas em headers/flags ainda exigem recompilar os objetos afetados.

## Tres limites separados

| Parte | Padrao Streaming | Alcance real |
|---|---:|---|
| Leitura antecipada | 16 MiB | Soma das reservas de registros na fila, em leitura e prontos; nao inclui o registro ja entregue ao consumidor |
| Fila de leitura | 8 pendentes, 128 entradas | Uma thread, handle de arquivo independente e prioridade abaixo do normal |
| Taxa de leitura antecipada | 64 MiB/s | Admissao das leituras de fundo, com uma leitura inicial; nao limita leituras urgentes |
| Indice | 65536 registros | Hashes, offsets e tamanhos; dados excedentes ficam no disco |
| Pre-aquecimento | 64 MiB de entrada, 128 variantes | Limita os registros selecionados, nao a memoria expandida do driver |
| Notas graficas | 256 | Notas de estado, que nao equivalem necessariamente a pipelines criadas |
| Workers | 2 | Limita concorrencia da traducao e do pre-aquecimento no modo Streaming |
| Admissao de compilacoes no pre-aquecimento | 5/s por worker | Token bucket de capacidade um; nao interrompe uma compilacao ja iniciada |
| I/O de arquivo | Ate 64 KiB por chamada | Leitura/gravação do cache de programas e dos snapshots de pipeline |
| Snapshot opaco Vulkan | Ate 128 MiB | Buffer de entrada/saida da aplicacao; nao limita RAM interna do driver |

As variaveis correspondentes estao em `ocarina/environment.py` e seus parsers/limites em `gpu/vk/cache_policy.h`. Um registro de programa individual tem limite defensivo de 64 MiB. Valores invalidos usam padroes; valores numericos sao limitados ao intervalo previsto.

O limite de 16 MiB cobre os bytes reservados de leitura antecipada. Metadados do indice, um registro demandado, SPIR-V desserializado, programas ativos, pipelines, memoria guest, texturas e alocacoes internas do driver estao fora dessa conta. Nao se promete RAM total constante ou soma de todos os buffers igual a 16 MiB.

## Fluxo implementado

O arquivo `hookshot_programs.bin` continua como banco binario indexado por hash. A inicializacao percorre cabecalhos e offsets sem carregar os corpos inteiros. O indice para no limite configurado; registros completos excedentes permanecem no arquivo. Uma cauda gravada pela metade pode ser removida ate o ultimo registro completo, como ja ocorria no backend.

Ao consumir um registro, o renderizador consulta a janela pronta sem esperar pela thread de leitura. Se faltar, mantem a leitura sob demanda e a traducao corretas. Em seguida solicita alguns registros seguintes na ordem do arquivo como heuristica de proximidade. Isso nao conhece antecipadamente todos os shaders da proxima cena e nao garante taxa de acerto. Entradas prontas podem ser descartadas por LRU; reservas em fila/em voo nao sao expulsas.

O leitor de fundo usa seu proprio handle e nao segura o mutex de I/O de demanda durante a leitura ou o throttling. A classe de janela tem encerramento/join testado. A instancia integrada e de vida do processo, assim como outros recursos deste backend, cuja API nao oferece hot-unload/shutdown. Nao adicionar unload da DLL sem encerrar esses recursos primeiro.

O pre-aquecimento seleciona um subconjunto do historico. O Streaming nao carrega/traduz toda a seed bank na inicializacao. Uma consulta com `FAIL_ON_PIPELINE_COMPILE_REQUIRED` e usada somente se `pipelineCreationCacheControl` estiver habilitado: um acerto pronto nao consome token; uma compilacao real aguarda admissao. Ha ate duas admissoes imediatas, uma por worker. Cinco admissoes/s nao significa cinco conclusoes/s, nem limite de 2 ms por frame.

## Dados do driver e compatibilidade

O cache opaco de pipeline recebe validacao de cabecalho, vendor, device e UUID antes da grande alocacao. Streaming grava `mkw_vk_pipelines_stream.bin`; o arquivo Original `mkw_vk_pipelines.bin` permanece separado. Se o arquivo Streaming nao existir, o Original pode servir de entrada quando cabe no teto. Um arquivo maior nao e cortado manualmente nem carregado inteiro nesse modo.

`vkGetPipelineCacheData` aceita um buffer menor e pode retornar `VK_INCOMPLETE` com dados validos, reutilizaveis como `pInitialData`. O backend aceita esse snapshot limitado, que pode cobrir menos pipelines. A API nao oferece um offset para concatenar supostos pedaços de um cache opaco. Os blocos de 64 KiB sao I/O de arquivo; o buffer requerido pela API continua alocado, ate 128 MiB.

O formato gravado de programas, o IR e o ABI dos shaders foram preservados. Um registro de compatibilidade reconhece apenas o fingerprint SHA-256 exato dos fontes auditados e mantem o stamp da 0.3.4. Alterar o tradutor ou os headers do ABI sai desse registro e recebe nova identidade. A chave de programas tambem continua dependente de dispositivo, driver e opcoes relevantes; nao compartilhar binarios de driver entre GPUs diferentes.

## Limites de desempenho e imagem

Menos pre-aquecimento troca trabalho inicial por possiveis pausas durante uma primeira visita. Mantenha mesma cena/configuracao e compare primeira e segunda abertura; use logs, picos de memoria do processo e frametimes. Um cache em disco de varios GiB nao prova que esses GiB estejam residentes na RAM.

Nao foi adicionado um placeholder generico para renderizacao arbitraria: compute pode produzir dados que os proximos passes exigem, e um shader substituto incompatível pode apagar geometria ou piorar a imagem. As esperas necessarias permanecem. O patch nao resolve por si so texturas/folhas faltando, iluminacao incorreta, ghosting temporal, recursos ausentes da GPU, audio ou corrupcao de imagem.

Nao foram implementados nesta entrega uma nova integracao de graphics pipeline libraries, pipeline binaries, deferred host operations ou NVAPI. O backend ja usa seus caminhos de extensao existentes conforme suporte consultado; isso e diferente de ativar recursos por marca de placa.

## Referencias primarias

- [Vulkan: vkGetPipelineCacheData](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPipelineCacheData.html).
- [Vulkan: pipeline creation flags](https://docs.vulkan.org/refpages/latest/refpages/source/VkPipelineCreateFlagBits.html).
- [Vulkan: graphics pipeline library](https://docs.vulkan.org/features/latest/features/proposals/VK_EXT_graphics_pipeline_library.html).
- [Vulkan: deferred host operations](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_deferred_host_operations.html).

Conferidas em 07/11/2026. Codigo e testes em `cache_*.h`, `vk_shader.cpp`, `vk_draw.cpp`, `vk_jobs.cpp` e `tests/test_shader_cache.py`.
