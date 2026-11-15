# Ocarina 0.3.7 — estudo, alterações aplicadas e validação

Data: 07/11/2026. Motor/orquestração: **0.3.7-dev.1**. Interface WPF: publicação **0.3.2-dev.1**, preservada. Distribuição: Windows x64, experimental.

## Conclusão

Continuar a base é a opção recomendada. O estudo encontrou diferenças úteis nos outros ports, mas também mostrou que várias correções anunciadas já existiam nos nossos fontes. Foram aplicadas mudanças próprias na instalação, controle de memória e diagnóstico, mantendo o runtime e renderizador do Hookshot como um conjunto.

A 0.3.7 contém blocos normais menores para instalações novas, renderizador Vulkan genérico pré-compilado com verificação de identidade, limite de mirrors para a classe de 12 GiB, distinção entre ausência e acesso negado e registros de tempo/cache. Não promete FPS fixo, build em um minuto ou correção de todos os problemas gráficos.

## Evidência real do PC do usuário

### Build da 0.3.6

Arquivos: `compile(3).log`, `lift(5).log`, `split(4).log`, `extract(5).log` e manifesto contido em `20261107-173925-164655-10764.zip`.

| Medida observada | Resultado |
|---|---:|
| Tempo total registrado pelo build | 2.722,92 s — 45 min 23 s |
| Compilação C/C++ | 2.220 s — 37 min |
| Processos de compilação | 2 |
| Unidades / falhas | 418 / 0 |
| Tradução ARM64 registrada | 120 s |
| Funções / instruções traduzidas | 294.529 / 17.646.501 |
| Código normal emitido | 55 arquivos |
| Grupo quente | 8 peças de aproximadamente 9–11 MiB |
| Extração | 186.588 arquivos, 26,27 GB |

Foram observadas **418 mensagens de início de compilador**. Os 192 resultados arredondados para 0 s não são prova de cache: nesta tentativa, todos os compiladores foram iniciados. A 0.3.7 passa a registrar acertos reais explicitamente.

Somando os tempos arredondados por unidade, o C do jogo representa 4.207 de 4.398 segundos-processo, aproximadamente 95,7%. Esse somatório de trabalho paralelo não é tempo de parede. Os maiores casos foram `code_020.c` (442 s), `code_hot_7.c` (368 s) e `code_021.c` (304 s). A última unidade do jogo acabou em 2.197 s; o conjunto terminou em 2.220 s.

Consequência: pré-compilar o motor é útil, mas **o principal custo deste teste é o C gerado**. Não é sustentado prometer uma redução de horas apenas por distribuir a DLL pronta. O alvo menor dos blocos normais é um experimento de engenharia que ainda precisa de comparação no PC real; as peças quentes foram preservadas para não alterar seu agrupamento de otimização indiscriminadamente.

### Duas execuções reais, manter separadas

O ZIP das 17h39 registra a 0.3.6 Original, termina com código 0 e `window closed`, aproximadamente 14 min 38 s depois. Não contém linha fatal ou device lost nesse log. A GPU registrada é RTX 5070 Ti Laptop. A VRAM reportada chegou a 10.571 MB de 11.176 MB permitidos. O contador acumulado de construção de pipelines chegou a 142.924 ms; não foi uma pausa única de 143 segundos.

O conjunto novo `execucao(3).json` / `erros(3).log` é outra execução, das 19h38 às 19h41, com os mesmos hashes de EXE e DLL e término normal. Configuração antes/depois idêntica: `frame_generation=0`, `resolution=0`, `upscaling=0`, `game_speed=1`. Driver identificado no log: NVIDIA 617.42. Não confundir com a captura de um driver Studio citada anteriormente como referência.

Na segunda execução, havia 1.026 chaves no cache de programas e aproximadamente 59 MB de cache de pipelines. O backend registrou 1.024 programas vindos do cache. Mesmo assim, os últimos intervalos ficaram próximos de 49–52 FPS. A VRAM chegou a 10.100 MB dos mesmos 11.176 MB permitidos; o último valor foi 10.077 MB, com 1.662 MB livres nos blocos do alocador. Esses números não são prova de estouro nem de que toda queda seja paginação de VRAM.

No fim há cerca de 1.500 draws, 100 dispatches e 150 passes por quadro, com tempo GPU reportado próximo de 12–13 ms. Isso justifica investigar também o custo de CPU/replay/submissões; não permite fechar sozinho o diagnóstico de gargalo.

### Vídeo novo

`Hookshot 2026-11-07 19-39-59.mp4`: 59,63 s, 1920×1080, H.264 e faixa AAC. Amostras aos 3, 20 e 40 segundos mostram interior, apresentação da floresta e Saria. As copas/vegetação e a iluminação de Saria aparecem, diferente da captura antiga sem copas. Essa melhora pertence ao teste **0.3.6**, não é validação visual da 0.3.7 ainda não entregue.

A clareza/neblina do exterior precisa ser comparada no mesmo ponto e câmera. Frames isolados não validam rastros durante movimento. A existência de uma faixa AAC não comprova som correto ou sincronizado. A taxa codificada do vídeo não é um benchmark independente do FPS do jogo.

### Auditoria com acesso negado

A captura informa `Permission denied` em alguns probes e ausência em outros, enquanto `System` e `Pack` aparecem como AUSENTE. A 0.3.6 usava `Path.is_dir()`, que pode transformar falhas de consulta em resultado falso. A nova auditoria usa `stat()` com tratamento separado e mostra INACESSIVEL.

O build e as sessões registradas conseguiram usar dados do jogo; a captura posterior não demonstra que toda a extração sempre esteve ausente. Ainda é necessário verificar acesso/estado da pasta no momento do erro. Não alterar ACLs em massa, tomar posse de toda a instalação ou atribuir esse erro automaticamente à GPU. A correção de mensagem não recupera arquivos nem concede permissões.

## Fontes e pacotes estudados

| Referência | Revisão / verificação |
|---|---|
| [Hookshot foliage-linux-updater](https://github.com/NotRexed/Hookshot/releases/tag/foliage-linux-updater) | `170ce53ca3d69309b3f5151a334136be8b4c38d6`, já integrado na 0.3.6 |
| `HookshotBuilder(5).zip` | 281.859.654 bytes; SHA-256 `b90d57ffdcb563c1cb2376422fbf3fcfdff90c5af6a8aa380d37351db31f0ded`, igual ao asset oficial |
| AppImage anexado | 215.132.664 bytes; SHA-256 `0e69d9b65ec32e0e7fa57181494577aa4db9485ced6b572c3c473845aa428ed1`, igual ao asset oficial |
| [Ocarina Recomp 0.2.4](https://github.com/sostenesfreitas/ocarina-recomp/releases/tag/v0.2.4) | Fontes anexados examinados; referência da release `1c362d72f561e7ce7b991921559f6b525378d773` |
| [Ocarina Recomp 0.2.5](https://github.com/sostenesfreitas/ocarina-recomp/releases/tag/v0.2.5) | Fontes do commit `c4896f8ed5eb122510f36001ae34607d9c7af568` examinados |
| `Ocarina-Setup-0.2.5-windows.zip` | SHA-256 `3bbcdce1c1d13468cfcf53161f727289441184c1afd3499554530be2955cf34e`, igual ao informado |
| [TotK Recomp](https://github.com/valentderah/totk-pc-recomp) | Fontes do commit `ae30a61b7bee4a3db959a234e7459e95939ac596` examinados |
| [SavageWindRecomp](https://github.com/Revivedx/SavageWindRecomp) | Fontes de `bf6146c14c37fee8781a601e5a544b93dff6d75e`; conferidos também arquivos de Alpha 4 `02bbb0fbd9dd0b2f2ead8e0642f797d8ebd496b3` |

O hash `45bdd73f...` anunciado na 0.2.4 refere-se ao instalador oficial, não ao ZIP de fontes de 3,4 MB. Não comparar hashes de arquivos diferentes como teste de corrupção. As numerações dos forks são independentes.

### O material do amigo

O RAR fornecido contém dois arquivos: `manage.py` e `OcarinaBuilder.exe`. Ambos são idênticos aos da distribuição 0.3.6 entregue. SHA-256 da GUI nos dois casos: `72c244e8364a38908cb021949259664afcab8d201e0c0e7f1de2a46dfe7f76fa`.

Esse anexo não contém um compilador/orquestrador modificado para avaliar. Não é evidência de uma otimização adicional do processo de instalação. O ZIP de metodologia e o Markdown colado descrevem reconstrução/byte matching; não contêm um novo runtime, renderizador ou correções prontas para o jogo. Não foram instalados como automação nem usados para declarar equivalência binária do nosso recompilador.

## Pontos fortes encontrados e o que foi aplicado

### Compilação e instalação

Savage Wind usa blocos de cerca de 1.500.000 bytes, limite de funções e isolamento de funções grandes. Seu instalador compila arquivos já emitidos enquanto os geradores seguem. TotK usa alvo estimado de 3.000.000 bytes, emissão paralela e opção de runtime pré-compilado. Fontes: `tools/gen.py`, `runtime/gamebuild.c` e `runtime/ui/launcher.mm` no Savage Wind; `recomp/gen.py`, `tools/build_game.py` e `installer/steps.py` no TotK.

Na nossa base, foram aplicados:

1. **Alvo de 6 MiB para blocos normais novos**, configurável por `--chunk-mib 3|6|12|24` e `Compilar.cmd -BlocoMiB`. Funções ficam inteiras. Isso é um alvo; uma função pode ultrapassá-lo.
2. **Limites existentes preservados**, incluindo o caso de um único bloco sem limites internos. Uma atualização não reagrupa todos os objetos só porque mudou o padrão. O grupo quente O2 continua com sua estratégia anterior.
3. **DLL Vulkan genérica pronta** no pacote, construída dos nossos fontes para Windows x64. `ocarina/prebuilt.py` compara fontes, headers/dependências, regras de build, configuração e hash do binário. Mudança incompatível usa compilação dos fontes. `--renderer-source` força esse caminho.
4. **Medição por fase**, em `work/build-timings.json`, inclusive quando uma fase falha. A medição não foi apresentada como uso de CPU ou pico de RAM.
5. **Contadores reais de objetos**, em `work/logs/compile-summary.json`: locais, compartilhados, compilados e falhos. O JSON informa também se a DLL pronta foi selecionada.
6. **Cache de extração mais seguro:** acesso negado não vira uma falta de cache; extração privada incompleta é recusada antes de fazer outra cópia grande. Os dados são preservados.

A geração menor não é uma promessa de aceleração proporcional. Também não foi copiada a estimativa de 768 MiB/job do TotK para nossa política de concorrência: gerador e arquivos são diferentes. A reserva conservadora da 0.3.6 continua. Sobrepor geração/compilação e medir picos reais de memória são próximos trabalhos.

### VRAM e estabilidade

A política nova limita mirrors a 1 GiB na classe física de 12 GiB, com tolerância de detecção. É uma adaptação própria motivada pelo caso observado e pela política da 0.2.5. A classe até 6 GiB mantém sua política de 1/8; a de 8 GiB mantém o padrão anterior por haver relatos de piora com leituras via PCIe. O perfil 8gb experimental continua disponível. Override explícito de mirror continua respeitado.

O limite não inclui texturas, render targets, caches internos do driver ou toda a VRAM do processo. O ganho e a correção de quedas precisam ser medidos na cena do usuário. Foram mantidos os mirrors; não foi feito um desligamento geral.

**Já existentes na 0.3.6:** compressão BC3 para texturas ASTC elegíveis; máscara de componentes de cor; budgets/evicção; backoff de imports de memória; sincronização de filmes e preferência por GPU dedicada. Não foram anunciados novamente como novidades criadas agora.

A 0.2.4 reflete os canais escritos pelo fragment shader e cruza a máscara com o estado NVN para preservar os demais. A nossa base já tem `frag_color_components` no coletor de IR e `target_write_mask()` em `vk_draw.cpp`, aplicado aos estados dinâmicos e estáticos. São implementações do mesmo princípio, não arquivos intercambiáveis.

O Savage Wind 4.1 divide certos acessos globais em dois bindings menores que 2 GB no driver AMD proprietário. A nossa base também tem endereços físicos SPIR-V e tabela de páginas. É necessário identificar uma falha equivalente antes de portar esse mecanismo. No TotK, a thread recorder tem restrições AMD por hangs/device lost; aumentar concorrência gráfica não é uma otimização universal.

## Pendências que não foram mascaradas

| Ponto | Estado e próximo passo |
|---|---|
| Catálogo de shaders do Hookshot | O Builder oficial chama `nx2/shader_census.py` e publica `hookshot_shaders.bin`. A orquestração local não faz isso. Integração pendente com leitura/índice e memória limitados; o gerador oficial acumula dados e não deve ser ativado indiscriminadamente como solução de RAM |
| Quedas com cache aquecido | Confirmadas no log novo; medir CPU/replay/submissões, tempo GPU, VRAM/paginação e mesmas cenas antes/depois do limite de mirrors |
| Registro AMD e nova tentativa sem otimização | A 0.2.5 tem mecanismo específico. Não foi importado em bloco para outro backend. Não habilitar omissão permanente de draws como se fosse correção visual |
| Intel e gravação de cache | As correções do outro fork exigem localizar chamadas/locks equivalentes e reproduzir com logs Intel; nenhuma execução Intel foi feita aqui |
| Redes neurais menores / upscale de console | Não integradas nesta rodada. Não anunciar qualidade neural ou compaction de shader que não foi implementada/testada |
| Iluminação, fog, flashes e rastros | Comparação real na mesma câmera/opções; a gravação nova comprova avanço na 0.3.6, não imagem perfeita ou validação da 0.3.7 |
| GPUs sem mesh/task shaders | Ainda precisam de caminho de geometria alternativo; BC3 e pipeline libraries não acrescentam esse recurso |
| GUI, Linux e atualizador | GUI anterior preservada; sem AppImage local ou atualizador oficial integrado |

O Streaming existente limita leitura antecipada, filas, prewarm e I/O. Seus 16 MiB não limitam a RAM interna que o driver usa compilando uma pipeline. O orçamento de admissão por estimativa de memória do Savage Wind é uma referência útil para trabalho posterior.

## Validação da 0.3.7

- **85 testes descobertos: 78 passaram, sete PowerShell não executados** pela ausência desse runtime.
- Testes novos cobrem acesso negado, entrada privada incompleta sem nova extração, preservação dos corpos/limites dos blocos, layout de um único bloco, fase falha com erro original preservado e DLL pronta adulterada/incompatível.
- A política de mirrors foi compilada e executada como C++ real, cobrindo 4/6/8/12/16/24 GiB e limites.
- Backend Vulkan: **182 unidades compiladas, zero falhas, DLL Windows x64 ligada** com LLVM-MinGW 20261020 / Clang 23.1.5. Export `mkwvk_init` conferido no PE. Compilador conferido pelo digest oficial `55064b60b991a1e1e8090b8c2f84e82b22cfe5903d12c159d65064cf5e8ae335`.
- Repetição incremental: **182 acertos locais, zero recompilações**, DLL ligada novamente. Objetos de teste não vão ao pacote.
- A DLL distribuída contém o backend genérico, não código/imagem do jogo. A rotina de desenvolvimento usada foi Vulkan-only; nenhum corpo de jogo foi compilado nessa etapa.
- Identidade do tradutor/ABI comparada byte a byte com 0.3.6: stamp `7d16d3d712a683ce` igual. O cache pode ser reutilizado quando GPU/driver/opções também coincidem. A incompatibilidade com 0.3.5 permanece.
- Não houve execução local de jogo/GPU/som físico ou janela WPF. Os logs reais analisados pertencem ao usuário rodando 0.3.6. A 0.3.7 ainda precisa desse teste.

## Instalação e continuação por outra IA

Para atualizar, fechar jogo/Builder, guardar cópia de `jogo/user/save`, extrair separadamente e copiar o conteúdo da pasta nova sobre a instalação existente. Manter `work`, `jogo`, entrada, destino e caminho da instalação. Repetir **Criar** para publicar o conjunto conferido. Não apagar `work` para uma atualização normal.

Para comparar um build limpo sem destruir a referência, usar outra pasta de trabalho/destino e manter dois jobs, como no teste registrado. Exemplo a partir da pasta do projeto:

```powershell
.\Compilar.cmd -Trabalho "C:\OcarinaHookshot\work-teste037" -Destino "C:\OcarinaHookshot\jogo-teste037" -BlocoMiB 6 -Jobs 2
```

Sem `-Jogo`, a seleção de NUP é aberta. O alvo menor vale para limites novos. Para recompilar o backend dos fontes, usar a CLI `manage.py build ... --renderer-source`.

Começar por `AGENTS.md`, `README.md`, `docs/arquitetura.md`, este relatório e `upstream.json`. Mudanças desta rodada ficam principalmente em `ocarina/prebuilt.py`, `timing.py`, `romfs.py`, `build.py`, `config.py`, `cli.py`, `nx2/chunks.py`, `nx2/build.py`, `gpu/vk/mirror_policy.h` e `vk_memory.cpp`.

Preservar saves, arquivos/mapas da tentativa e estados de cache. Associar cada teste ao hash do EXE/DLL, perfil, driver, opções, modo de cache e posição no jogo. Nunca distribuir a entrada privada, shaders extraídos, código gerado, EXE do jogo ou saves. Manter os avisos/licenças; nenhum arquivo de implementação dos forks 0.2.4/0.2.5 foi copiado para esta entrega.

Registros mínimos para a próxima análise: `build-request.json`, `build-timings.json`, `logs/compile-summary.json`, `logs/compile.log` e os arquivos da mesma sessão de `jogo/diagnosticos`. A próxima prioridade é avaliar a 0.3.7 no PC real e desenvolver a preparação de shaders com limites, sem esconder falhas essenciais de renderização.
