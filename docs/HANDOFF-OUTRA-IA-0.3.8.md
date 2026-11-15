# Ocarina 0.3.8 — entrega e continuidade para outra IA

## Correcao posterior: acesso 0.3.8-dev.2

A orquestracao atual e **0.3.8-dev.2**; os detalhes de preparacao/renderizador abaixo continuam validos. A DLL e o stamp de shaders nao mudaram.

O ZIP real `20261107-205245-647183-1124.zip`, das20:52:45-03, mostra `ocarina-build.json` legivel, `hookshot.exe` 472.193.024bytes, DLL 5.651.456bytes e `image.bin` 100.794.368bytes existentes, mas com leitura e consulta de ACL negadas: WinError 5. Sem processo hookshot.exe, EFS ou reparse point nesses arquivos. Nao e evidência de falta do binario, hash divergente ou device lost. O nome antigo 0.3.7 da pasta nao significa launcher antigo: a coleta registra 0.3.8-dev.1.

Ha uma causa provavel concreta na publicacao: os arquivos eram copiados para TemporaryDirectory e depois movidos. O Python usa `D:P(...SY)(...BA)(...OW)`; em processos elevados, o dono pode ser Administrators, deixando o usuario normal sem acesso. O manifesto era criado por outro caminho, diretamente na pasta de destino, e ficou legivel. [Relato primario CPython#157876](https://github.com/python/cpython/issues/157876). [Microsoft: seguranca nao e reaplicada ao renomear/mover](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights). Trata-se de hipotese forte; confirmar dono e SDDL no novo log antes de anunciar causa comprovada.

`ocarina/windows_acl.py` cria uma DACL privada com SID real do TokenUser explicitamente, SYSTEM e Administrators. `workspace_stage()` aplica-a antes de qualquer copia nos tres pontos de build.py e dois de shader_prepare.py. Nao adiciona Everyone nem modifica a ACL de pastas existentes durante o build. O programa normal continua sem elevacao.

`Reparar-Acesso.cmd` chama reparar-acesso.ps1. O script captura o SID do usuario antes do UAC, valida manifesto e nomes, recusa links/juncoes, registra ACL/dono antigos quando acessiveis, restaura heranca e concede Modify somente ao usuario original nos tres arquivos. takeown e fallback apenas de arquivo pontual, sem recursao. Hashes obrigatorios continuam sendo verificados. Se o usuario NORMAL constatar System/Pack bloqueados, pode acrescentar permissao herdavel somente a entrada hash de work/inputs registrada no manifesto; sem reset do drive, perfil ou work inteiro. Volta ao processo normal para audit-access e run --dry-run; nao executa o jogo elevado. Registro em diagnosticos-acesso/reparo-*.json.

A correcao pequena se aplica sobre a 0.3.8 existente, na pasta de manage.py. Preservar work/jogo. Ao falhar, pedir o novo ZIP e o JSON do reparo, sem iniciar recompilacao longa. Confirmar se o owner antigo era Administrators e a SDDL tinha OWNER RIGHTS. Verificar se a leitura normal/hashes passam antes de dizer “resolvido”. Nenhuma alteracao em GPU/ASTC/IR foi feita nesta etapa e as piscadas continuam pendentes.

103 testes: 94 passaram e nove omitidos (sete PowerShell e dois Windows/API/parser). Politica e integracao de staging testadas; reparo elevado e API nativa Windows nao executados neste host. Os testes Windows incluidos podem ser executados no PC de destino. Documento operacional: LEIA-ME-REPARO-ACESSO.txt.


Motor/orquestração: **0.3.8-dev.1**. Interface publicada: **0.3.2-dev.1**, preservada. Windows x64. Data: 07/11/2026. Histórico completo do estudo anterior: `HANDOFF-OUTRA-IA-0.3.7.md`.

## Estado dos dois problemas

| Problema | Evidência | Resultado desta entrega | Ainda necessário |
|---|---|---|---|
| PermissionError ao ler `jogo/hookshot.exe` | Traceback termina no SHA-256, antes de iniciar o processo | Erro tratado, verificação estrita preservada e diagnóstico independente/automático | Executar a coleta no PC afetado para identificar o bloqueio real do Windows |
| Luzes/piscadas | Vídeos/relatos, arquivo `astc_analysis.rar` e problema aberto no upstream | Modos ASTC explícitos, comparação A/B e coleta limitada de brilho/exposição | Confirmar se a diferença acompanha BC3, decoder, exposição ou outro estado gráfico; nenhuma correção visual foi comprovada |

**Não anunciar “os dois resolvidos”.** A falha de tratamento do launcher foi corrigida. Não foram concedidas permissões no computador do usuário nem demonstrada uma correção das piscadas numa GPU física.

## Anexos lidos nesta etapa

O ZIP `20261107-193858-856891-35096.zip` contém a execução **0.3.6**, iniciada às 19:38:58-03 e encerrada às 19:41:19-03, com `exit_code=0` e `window closed`. Não registra a falha de permissão atual, que ocorre antes de ser criada uma sessão do jogo. Não reutilizar o mapa/backtrace dessa sessão como evidência do bloqueio atual.

As capturas mostram caminhos 0.3.6 e 0.3.7. Atualizar fontes dentro de uma pasta cujo nome ainda é 0.3.6 é permitido. O nome da pasta não prova qual motor foi carregado; a versão e os hashes no log são a evidência.

`Verificar.cmd` confere ferramentas. Não valida, por si só, o acesso a `jogo/hookshot.exe` nem a renderização. O novo `Diagnosticar-Acesso.cmd` cobre a primeira parte explicitamente.

O arquivo `astc_analysis.rar` contém somente quatro fontes/trechos:

| Arquivo | Papel observado | SHA-256 |
|---|---|---|
| gl_texture_cache.cpp | Renderer OpenGL Eden/Yuzu, seleção de formato/recompressão e decode assíncrono | 86221abce774a6c630abb587f36d60cc9e3a8d4f56f74b23ffa57a44560ec755 |
| settings.h | Opções e default de BC3 para economizar VRAM | 858e4363d2e2532019e02ad0687bd33734db85994f8cfbb9321392c6a7352dc7 |
| settings_enums.h | Enumerações de CPU/GPU/CPU assíncrono e sem compressão/BC1/BC3 | 16c110efe521102d3913833cc5ba0d385ea720e712322be0f8ebdba5735b34bd |
| shared_translation.cpp | Textos das opções, inclusive perda de qualidade e artefatos do modo assíncrono | 681ccbf06843178ed8b7a023ff66302648a060232ff73e7d0a591d6c363817c2 |

Nenhum desses quatro arquivos foi copiado para o backend Vulkan. São referências úteis de separação entre decode e recompressão; não contêm um patch completo do nosso decoder Vulkan, uma medição do defeito nem prova de que shader prewarming resolve flashes.

## Mudanças implementadas

### Acesso e integridade

`ocarina/access.py` distingue falha de `stat`, arquivo ausente, diretório com nome de EXE e leitura negada. O launcher captura erros do hash em `FileAccessError`, que deriva de `ProjectError`; a CLI mostra erro direto, com código e orientação. Erros OSError adicionais também recebem tratamento na CLI.

A conferência SHA-256 continua obrigatória. Hash divergente continua impedindo a execução. Não há bypass, concessão automática de ACL, alteração de antivírus/Registro, execução elevada ou “reparação” que apague o jogo.

A coleta lê inicialmente até 16bytes dos quatro arquivos obrigatórios, sem guardar seu conteúdo. Em Windows, um `CreateFileW` somente de leitura preserva o código Win32 quando o CRT apresenta apenas `errno 13`. Na coleta manual há `whoami /user`, `tasklist` filtrado pelo nome do jogo e `icacls` pontual em arquivos bloqueados, sem recursão nem mudança de permissões. Atributos EFS/reparse entram no relatório. Um código 5 não identifica sozinho antivírus, ACL ou outro componente;32 é falha de compartilhamento.

Os arquivos `acesso.json` e `acesso.txt` vão para um ZIP em `diagnosticos-acesso`; se necessário há fallback no diretório temporário. Não se cria um falso `execucao.json` dizendo que o jogo começou. Os diagnósticos de acesso são excluídos da distribuição.

### ASTC, BC3 e diagnóstico de luzes

`runtime_environment` aceita `texture_mode` independente de perfil/cache. O ambiente experimental herdado continua sendo limpo; as opções novas são aplicadas explicitamente depois dessa limpeza e registradas no processo filho.

| Modo | Efeito |
|---|---|
| auto | Mantém as escolhas de compressão elegível do motor |
| rgba8 | Define `RX_VK_ASTC_RGBA8=1`, dispensando a recompressão BC3 |
| cpu-rgba8 | Acrescenta `RX_VK_ASTC_CPU=1`, evitando também o decoder ASTC em compute |

Não forçar BC3 numa GPU/formato sem suporte. RGBA8 pode ocupar quatro vezes a memória das texturas convertidas; isso não significa quatro vezes a VRAM total. O log do usuário já chegou a 10.100/11.176 MiB e reportou cerca de 2.308 MiB em ASTC decodificado, 2.703 MiB em render targets e 389 MiB em outras texturas no fim da sessão. Não recomendar desligar compressão globalmente como otimização universal.

`--trace-lighting` usa as sondagens herdadas de 320×180 e o ring de 32 exposições. O backend agora pode executar esse modo sem thread de gravação nem fila de frames; há três buffers de readback e nenhum banco de todos os frames é escrito. O custo das sondagens ainda existe. Ele detecta saltos grandes de brilho, não qualquer oscilação sutil nem a causa por si só. Use logs normais para benchmark.

`Testar-Luzes.cmd` mantém o modo auto; `Testar-Luzes.cmd --texture-mode rgba8` muda a compressão. `Jogar-Sem-BC3.cmd` e `Jogar-ASTC-CPU.cmd` são comparações adicionais. Registrar resolução, frame generation, câmera/cena, GPU, driver e hashes; mudar uma variável de cada vez.

### Preparação com progresso e banco em disco

A console `Preparing shaders` já existia nos fontes herdados. Nosso fluxo anterior não chamava/publicava o censo de shaders. A 0.3.8 acrescenta `Preparar-Shaders.cmd` e o comando `prepare-shaders`: valida o build, atualiza a DLL compatível, gera o banco privado da RomFS e abre o jogo para preparar programas/pipelines. Não recompila o C traduzido.

O writer `nx2/shader_census.py` passa a fazer spool de estágios/programas no disco e publicação atômica, mantendo em RAM hashes/IDs, não uma lista de todos os payloads. Processa arquivos de shader descompactados individualmente; o maior arquivo e o compilador ainda consomem memória. A identidade de reutilização confere código do writer, imagem, caminho e metadados dos arquivos da RomFS; `--force` refaz o banco se esses metadados foram preservados apesar de mudanças intencionais.

O novo `gpu/vk/shader_seed.h` lê o formato HKSEED01 com índice de offsets, valida tamanhos/contagens/IDs/truncamentos e rejeita bancos inválidos. Os pacotes ficam no disco. As chaves do programa são calculadas por hash incremental equivalente ao anterior; os programas são lidos sob demanda por workers.

Há um limite compartilhado de 16 MiB para entradas brutas de programas simultâneos; um programa que exceda esse orçamento fica para a tradução sob demanda, em vez de ultrapassar o limite nesse caminho. I/O é particionado em até64 KiB. Dois workers por padrão, configuráveis de 1 a 4. Esses limites não abrangem memória de IR, SPIR-V, driver, pipeline, jogo ou texturas.

O modo de cache `preparacao` combina a política Streaming com a permissão explícita de preparar o banco antes do jogo. O cache de driver aplica seu limite já existente de 128 MiB. O token bucket herdado limita o aquecimento do histórico; a preparação integral do seed usa o limite de workers/bytes. Não descrever isso como um orçamento universal de 2 ms por frame: esta etapa ocorre antes de haver gameplay. Também não se trata de carregar binários de shader diretamente para VRAM sem criar pipelines pela API.

A console de progresso pode aproveitar uma console existente e só libera uma console que ela própria criou. O progresso termina em 100%. Primeira preparação pode demorar, e novas variantes/estados ainda podem causar stutter. Não foi acrescentado um placeholder gráfico universal: compute/mesh que escreve dados do jogo exige um fallback semanticamente correto, não um shader genérico qualquer.

### Atualização só da DLL

`Atualizar-Renderizador.cmd` aceita builds locais 0.3.6-dev.1,0.3.7-dev.1 e 0.3.8-dev.1 com build ID suportado. A ABI de `vk_api.h` foi comparada e permanece idêntica. O binário genérico precisa corresponder ao fingerprint de fontes/dependências/configuração e ao hash do manifesto pronto.

O processo valida a instalação existente, copia em staging, confere hash, troca a DLL e publica o manifesto por último. Uma falha de publicação tenta restaurar DLL/manifesto anteriores. EXE, imagem, saves e objetos não são recompilados nem substituídos por esse comando. Se a DLL estiver em uso e o Windows recusar a troca, é erro explícito. Manter fechados jogo/launcher/extrator ao atualizar.

A versão antiga do EXE permanece registrada, com `renderer_version` separado; não alegar que o EXE foi recompilado. A GUI WPF continua no binário 0.3.2. O novo fluxo funciona pelos CMDs/CLI incluídos e o botão Jogar reaproveita o launcher corrigido.

## Binário e compatibilidade

DLL Vulkan Windows x64: **664e28e2be7d38887abb472df940c0a8c9a76d5dfff9068dc4c3d9c9d439941c**.

Fingerprint do renderer: **247b4a795e43d4a51502882d8f7927773aeb0070d25ef9d2f4eef6e05696db4f**. Compilador: LLVM-MinGW 20261020/Clang 23.1.5. 182 unidades Vulkan, DLL ligada e export `mkwvk_init` conferido. Não contém dados do jogo.

Stamp do tradutor: **7d16d3d712a683ce**, igual à 0.3.6/0.3.7 auditadas. A mudança em `vk_shader.cpp` é de transporte do seed; funções de tradução, emissores, IR/Info e headers ABI permanecem iguais. O fingerprint exato está registrado em `profiles/shader-cache-compatible.json`. Não reaproveitar esse stamp para futuras alterações semânticas nem para 0.3.5.

## Validação executada

- 97 casos descobertos:90 passaram, sete checks PowerShell não executados por ausência desse runtime.
- Processo filho real confirma passagem de flags ASTC/diagnóstico/cache; erros de leitura/stat são simulados de forma determinística e nunca iniciam o jogo.
- Writer Python real interoperou com leitor C++ compilado/executado, incluindo arquivos corrompidos/truncados, índices inválidos e concorrência sob orçamento16 MiB.
- Censo real por subprocesso com BNSH/Zstandard sintéticos; reutilização do banco, preservação da entrada e recusa de índice inacessível.
- Publicação de DLL/manifesto e rollback testados com arquivos sintéticos, mantendo EXE/imagem/save.
- ASan/UBSan passaram no reader/budget. LeakSanitizer desativado por limitação do ambiente, sem alegação de verificação de vazamentos.
- 182 unidades Vulkan compiladas na primeira rodada; último ajuste recompilou uma unidade, com 181 acertos locais e zero falhas. DLL Windows ligada.

**Não houve** jogo em execução neste ambiente, GPU AMD/NVIDIA física, teste de ACL no PC do usuário, som físico, janela WPF ou confirmação visual das piscadas. Não transformar compilação sintética/native em benchmark de gameplay.

## Instalação e próximo teste

Leia `LEIA-ME-0.3.8.txt`. Na instalação existente, copie o conteúdo da pasta do ZIP para a pasta que já contém `manage.py`, `ferramentas` e `OcarinaBuilder.exe`; preserve `work`, `jogo` e a RomFS no mesmo caminho. Não criar outra pasta de jogo vazia e interpretá-la como perda de build.

1. Fechar jogo/launcher/extrator; aplicar os arquivos.
2. Executar `Diagnosticar-Acesso.cmd`. Se a leitura continuar negada, recolher esse ZIP antes de atribuir causa ou iniciar novo build.
3. Com o acesso confirmado, executar `Atualizar-Renderizador.cmd`.
4. Opcionalmente executar `Preparar-Shaders.cmd`; depois reutilizar o banco e os caches.
5. Reproduzir flashes em duas sessões da mesma cena com `Testar-Luzes.cmd`, depois com `--texture-mode rgba8`. No PC em questão, pouca folga de VRAM pede cena curta; se usar `--profile 8gb`, aplicar igualmente às duas tentativas.
6. Reunir ZIPs das tentativas correspondentes. Só depois escolher uma correção permanente por evidência.

## Trabalho pendente para a próxima IA

- Identificar o WinError/ACL/EFS/processo/registro de proteção real e resolver somente o bloqueio comprovado. Um traceback anterior de 0xC0000005 é outro problema, não explica este erro de leitura.
- Confirmar a variável que acompanha as piscadas; comparar, por frame, exposição, resultados dos passes, validade dos canais/attachments e sincronização dos dados. BC3 é uma hipótese testável, não um diagnóstico concluído.
- Se o problema persistir sem BC3, manter o caminho automático econômico e investigar o renderer. O arquivo recebido é OpenGL; não transplantar seus caches/descriptors como se fossem Vulkan.
- Avaliar em GPU real o custo de preparar todo o seed, a melhora na segunda abertura e variantes que ainda compilam durante jogo. Não prometer zero stutter.
- Republishar/validar a interface WPF para expor esses controles e distinguir “pré-lançamento falhou” de “jogo encerrou”; o título genérico da GUI atual ainda pode dizer Jogo encerrado com código1.
- Continuam pendentes o journal persistente por shader com retry NOOPT, validações Intel/AMD, compaction das redes quando semanticamente comprovada, fallback compatível por tipo e benchmark frio/repetido do build. Linux/AppImage/updater oficial não integrados.

## Referências primárias consultadas

- [Hookshot, problema 145: brilho/piscadas/bordas](https://github.com/NotRexed/Hookshot/issues/145). Continua aberto na consulta; inclui relato de exposição constante durante tela branca. Um relato externo não é diagnóstico do nosso usuário.
- [Hookshot foliage-linux-updater](https://github.com/NotRexed/Hookshot/releases/tag/foliage-linux-updater), base já integrada desde 0.3.6.
- [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) e [códigos de erro](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--0-499-).
- [Microsoft Histórico de proteção](https://support.microsoft.com/en-us/windows/security/windows-security/protection-history-in-the-windows-security-app), para verificar uma eventual detecção, sem presumir sua existência.

A distribuição exclui jogo, bancos privados, saves, mapas de jogo, logs pessoais e caches. O arquivo completo contém fontes, ferramentas, GUI e DLL genérica; o banco de shaders é gerado somente da cópia local do usuário.
