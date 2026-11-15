# Drivers e ajustes: referencias para 0.3.5

As capturas enviadas foram tratadas como referencias de compatibilidade, nao como codigo-fonte de driver ou prova de ganho no Hookshot. Nenhum driver foi instalado ou embutido nesta entrega. Nao houve teste fisico AMD/NVIDIA.

| Referencia | O que foi conferido | Limite |
|---|---|---|
| NVIDIA Studio 621.14 WHQL | Pagina oficial, lancamento em 04/11/2026, variante para notebooks | Certificacao WHQL e fixes de outros programas nao comprovam estabilidade deste backend |
| AMD Adrenalin 26.10.1 WHQL | Notas oficiais de 20/10/2026; familias RDNA listadas, incluindo RX 9060 | RX580/Polaris nao aparece na lista de compatibilidade desse pacote |

As notas AMD registram crash/timeout em alguns jogos ao alternar outros overlays com o Performance Metrics Overlay ativo. Isso justifica uma comparacao controlada sem overlays no caso de troca de foco, mas nao prova a causa do nosso antigo acesso invalido `0xC0000005` nem do caso RTX4090.

## Ajustes que nao foram automatizados

- `DisableAsyncShaderCompile = 0`: nao foi encontrado contrato oficial suficiente para usar essa chave como controle geral de compilacao Vulkan. Nao escrever no Registro com essa suposicao.
- SAM/Resizable BAR: recurso da plataforma/driver, nao substitui gerencia de recursos ou sincronizacao. O programa nao altera BIOS nem garante ausencia de stutter por ativa-lo.
- Limpeza de DxCache/GLCache: apagar tudo provoca recompilacao; nao executar a cada inicio ou atualizacao deste projeto. `DxCache`/`DXCache` e documentacao de OpenGL ES no DRIVE OS nao definem o armazenamento interno do driver Vulkan Windows em todos os sistemas.
- Shader Cache Size NVIDIA: cota de disco, nao cota de RAM. Nao se afirma que 10 GB ou Unlimited resolva qualquer pausa.
- Threaded Optimization: a configuracao aparece como controle OpenGL no header oficial NVAPI; nao e um seletor geral para nosso backend Vulkan.
- Reflex/Low Latency: exigem caminhos e suporte apropriados; nao concluem compilacoes de shaders nem garantem alinhamento com um deadline de frame. Nenhum perfil global foi alterado.

## Correcoes de arquitetura relevantes

RDNA suporta Wave32 e Wave64; GCN/Polaris nao deve receber uma exigencia Wave32 por simples variavel. Infinity Cache foi introduzido em RDNA2, nao em toda a familia RDNA1. Recursos RT/IA e caches das GPUs mais recentes nao removem o custo de compilar uma pipeline na CPU/driver. NVIDIA tambem possui agendamento de warps em hardware; nao e correto tratar sua GPU como agendada majoritariamente pelo sistema operacional.

`VK_KHR_pipeline_library` fornece infraestrutura; `VK_EXT_graphics_pipeline_library` define a separacao de partes graficas. Nao sao alternativas exclusivas AMD/NVIDIA. O suporte deve ser consultado no dispositivo. `VK_KHR_deferred_host_operations` nao torna `vkCreateGraphicsPipelines` e `vkCreateComputePipelines` automaticamente diferiveis; comandos precisam de permissao especifica em outra extensao.

NVAPI pode manipular certos perfis documentados, mas nao oferece a equivalencia presumida entre cota de cache em disco, buffer de I/O da aplicacao e RAM interna do driver. Os limites desta versao sao implementados dentro do backend, de forma explicita e por processo.

## Referencias oficiais

- [NVIDIA Studio 621.14, notebooks](https://www.nvidia.com/en-us/drivers/details/283967/).
- [AMD Adrenalin 26.10.1: notas e produtos compativeis](https://www.amd.com/en/resources/support-articles/release-notes/RN-RAD-WIN-26-10-1.html).
- [AMD RDNA: comparacao entre geracoes](https://www.amd.com/en/technologies/rdna.html).
- [GPUOpen: RDNA performance guide](https://gpuopen.com/learn/rdna-performance-guide/).
- [NVAPI: Driver Settings header](https://docs.nvidia.com/nvapi/_nv_api_driver_settings_8h_source.html).
- [NVIDIA Control Panel: Manage 3D Settings](https://www.nvidia.com/content/Control-Panel-Help/vLatest/en-gb/mergedProjects/nv3dENG/Manage_3D_Settings_%28reference%29.htm).
- [NVIDIA DRIVE OS: Automatic Shader Cache](https://developer.nvidia.com/docs/drive/drive-os/6.0.8/public/drive-os-linux-sdk/common/topics/graphics_content/AutomaticShaderCache8.html).
- [Khronos: deferred host operations](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_deferred_host_operations.html).

Conferidas em 07/11/2026. Sao referencias de contratos e limitacoes; nao sao benchmarks deste pacote.
