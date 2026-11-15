> HISTÓRICO: este documento descreve uma revisão anterior. O estado atual está em `../README.md` e `Relatorio-AkynoLeyend-0.4.2.md`.

# AkynoLeyend 0.4.1 Visual — Código candidato, NÃO testado no jogo

> **IMPORTANTE:** Este ZIP contém **fontes modificados**, um Python embarcado e ferramentas de build. O **AkynoLeyendBuilder.exe ainda é o WPF pré-compilado 0.4.0**: não use seu menu para verificar se os novos parâmetros estão presentes; ele NÃO foi reconstruído aqui. NÃO há um AkynoLeyend.exe recompilado nem a DLL Vulkan recompilada com os patches novos. A aplicação real dos patches depende de executar `Compilar-Visual-041.cmd` no Windows com entrada própria do jogo (NUP), gerando EXE e DLL novos. Nenhuma melhoria de FPS/qualidade visual foi medida fisicamente.

## Diagnóstico que levou às alterações

- O log de 22:10 de 08/11/2026 ainda descreve runtime `0.4.0-dev.1`, com 89 operações iniciais de texturas/samplers, 40 avisos de storage buffer sem vínculo e 11 programas de shader que falharam. Não comprova que um patch 0.4.1 esteja ativo.
- A imagem mostra chão repetitivo e escuro em blocos. Os sintomas são compatíveis com **texturas feitas pela GPU e retiradas do cache antes de serem reutilizadas**, mas sem teste A/B não há confirmação definitiva.
- PR #593 do Hookshot (https://github.com/NotRexed/Hookshot/pull/593) descreve a retenção limitada de texturas pequenas e finalizadas como as normais de terreno 260x260. Não se deve fazer writeback geral sobre a memória do jogo: pode conter outros dados.
- PR #252 do Hookshot (https://github.com/NotRexed/Hookshot/pull/252) detalha contadores GPU de grupos indiretos e descritores relacionados a vegetação.

## Modificações integradas nesta base

1. `host/rx_backend.c`: cópia limitada dos bytes de texels escritos antes de o renderizador iniciar, reproduzida no início da execução. Ponteiros originais não são retidos.
2. `gpu/vk/vk_texture.cpp`: proteção de texturas pequenas escritas uma vez pela GPU e posteriormente finalizadas, até 256 MiB por padrão, com remoção das mais antigas caso o limite seja excedido; mínimo de 60 quadros antes de despejar texturas não protegidas.
3. `gpu/vk/vk_draw.cpp`: transferência GPU→GPU de contagens de despacho indireto para uniform c0 no caso computacional, com barreira transfer→compute. A rotina pode ser desligada para comparação com `RX_VK_NO_GRID_PATCH`.
4. `gpu/vk/vk_draw.cpp`: maior alcance dos *bare pointers* **somente de leitura**, limitado por pool e pelo máximo do dispositivo, 130 MiB padrão. Escritas permanecem com teto conservador.
5. `nx2/oot_occlusion.py`, `nx2/lift.py`, `host/hos_main.c`: desativação opcional de seis leituras para consultas de oclusão do jogo original, com conferência exata dos opcodes ARM64; omite locais não correspondentes.
6. `host/nn_fs.c` já carrega a correção de 0x302→0x304 na classificação de entradas de diretório (folhas ausentes).
7. `akynoleyend/environment.py`, `cli.py`, `launch.py`: comparação reproduzível `--visual-mode patched|comparison`; ambientes RX_ herdados são **limpos** por segurança, por isso os perfis passam os parâmetros explicitamente.
8. `Compilar-Visual-041.cmd`: compilação **de host e DLL** com diretórios NOVOS de saída; `Jogar-Visual-041.cmd` e `Jogar-Comparacao-041.cmd`: comparação de mesmo cenário sem filtros agressivos.
9. O renderizador pré-compilado 0.4.0 foi excluído de `ferramentas/prebuilt` para não ser usado por engano com fontes 0.4.1.

## Como usar com segurança no Windows

- **Não misture** este ZIP com `AkynoLeyend-0.4.0` nem use 'Atualizar' na instalação antiga.
- Extraia o ZIP inteiro em pasta independente, por exemplo `C:\AkynoLeyend-Visual041`.
- Execute **`Compilar-Visual-041.cmd`**. Selecione o NUP do jogo que você possui legitimamente. Isso compila no novo destino `jogo-Visual041`, mantendo intactos o jogo antigo, os caches e saves. Para passar pastas separadas, opções PowerShell `-Exefs`/`-Romfs` são aceitas pelo script `compilar.ps1`.
- Aguarde a marca **`@@done`** ao final da compilação. Apenas nesse momento use `Jogar-Visual-041.cmd`. Se a compilação falhar, envie o log. Não copie DLLs novas sobre EXEs antigos sem verificar o manifesto.
- Repita a **mesma cena, mesma câmera, mesmo tempo de jogo** com `Jogar-Comparacao-041.cmd`; os switches comparativos desativam parte das alterações e ajudam a localizar regressões.
- `run` gera `jogo-Visual041/diagnosticos/<data>/execucao.json` e `saida.log`. Compare `visual_mode`, `AKYNO_OCCLUSION_OFF`, `RX_VK_KEEP_FINALIZED_MB`, `RX_VK_BARE_READ_MB` e as mensagens `vk: finalized GPU-once textures retained`.
- Se o usuário tiver saves importantes, **faça backup antes** de abrir o novo jogo e copie-os apenas quando necessário, sob controle manual.

### Limitações técnicas

- **Max Resolution verdadeiro do mod ARM64 não foi integrado**, nem FSR 3.x, DLSS, LSFG ou backend OpenGL. `125%/150%` são opções de escala host experimental (e não aparecem no WPF antigo incluído); a revisão não as declara funcionais.
- As alterações nativas não foram compiladas neste ambiente Linux para Windows nem executadas numa GPU física. Testes Python/source-level não comprovam renderização correta.
- Há comportamentos não corrigidos: possíveis shaders Ampere não traduzidos, driver AMD `device lost`, flashes de exposição e outras formas de fog/foliage. Nenhum shader essencial foi desativado por hash; `RX_VK_OOT_VISUAL` não é ligado automaticamente para esconder neblina.
- Se o conjunto corrigido consumir VRAM excessiva, escolha comparação ou ajuste `RX_VK_KEEP_FINALIZED_MB` pelo código/perfil após nova medição, não por adivinhação.

## Validação local

Foram testadas verificações da aplicação Python, os seis patches ARM64 com guard de opcode, a lógica de configurações e os pontos de integração. Não há teste visual no Windows. Não alegar `bug corrigido` até comparar o mesmo local antes e depois com o novo `AkynoLeyend.exe` e `AkynoLeyend.dll` comprovadamente recompilados.

## Atualizar o menu WPF no Windows

Com **.NET 8 SDK** instalado, `Compilar-Interface-041.cmd` publica o novo Builder WPF e só substitui `AkynoLeyendBuilder.exe` **dentro desta pasta candidata** se a compilação terminar com sucesso. Se o SDK não existir ou falhar, o EXE antigo permanece. Esse passo só altera a interface, **não ativa Max Resolution real e não substitui a recompilação do jogo**.
