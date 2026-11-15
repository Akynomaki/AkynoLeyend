# Integracao pointer-lighting-2 — 0.3.3-dev.1

## Origem verificada

O arquivo correto HookshotBuilder(3).zip coincide por SHA-256 com o asset HookshotBuilder.zip informado pela API oficial da release pointer-lighting-2: 5c017fe89bc468a606afb0192bff923d3118380bd315f3b4433555b2ae1e4f11. O ultimo HookshotBuilder(2).zip enviado tem os mesmos bytes. O arquivo mais antigo HookshotBuilder (2).zip, com espaco, e diferente.

A API oficial identifica publicacao em 2026-11-07T11:28:13Z. Fontes: https://github.com/NotRexed/Hookshot/releases/tag/pointer-lighting-2 e https://api.github.com/repos/NotRexed/Hookshot/releases/tags/pointer-lighting-2 . O target_commitish da release e main; isso nao e tratado como identificacao de commit imutavel.

## Mudancas aplicadas ao motor

- Leitura indireta da memoria guest pelo shader compute com tabela de paginas, preservando o caminho anterior dos shaders graficos. O passe de memoria deixa de aplicar a regra de ponteiros mistos ao texto do menu.
- Endereco da tabela enviado por push constants. Ele deixa de entrar como constante de execucao no SPIR-V. O cache do driver pode reutilizar shaders iguais nos proximos inicios; caches ainda dependem de GPU, driver, tradutor e opcoes.
- Atualizacao da tabela ao criar/importar/mirrorizar/retirar pools. A liberacao de mirror de pool aposentado nao recoloca um endereco antigo na faixa que outro pool ocupa.
- Fallback do VMA para imagens quando a tentativa limitada a VRAM falha. Nao e um teto global de memoria e nao garante boa velocidade sob pressao.
- Leitura de language.txt tolera BOM e ignora linhas que nao representam um idioma valido. Portugues brasileiro segue disponivel.
- Mantidas as correcoes AMD de subgrupos, gather, Position SPIR-V, filmes, protecao de flashes e sincronizacao inicial do renderizador da 0.3.2.

Adaptacoes locais: flush das faixas alteradas da tabela em memoria host nao coerente (VMA), asserts do alinhamento/tamanho dos push constants e simplificacao do dumper SPIR-V opcional. O caminho experimental RX_VK_NO_F16 continua desativado por padrao. Nenhum desenho extra foi omitido para esconder erros.

## Compilacao e lentidao

O orquestrador e os compiladores filhos solicitam desativar EcoQoS nos seus processos. Durante o build e solicitada continuidade do sistema, com restauracao do estado anterior ao sair, inclusive por excecao. Nao sao alterados plano de energia, prioridade de tempo real ou limites de seguranca de RAM. O maximo automatico permanece oito processos, condicionado a memoria livre.

As etapas Python passam a usar -u para liberar a saida imediatamente. As flags O1/O2 dos arquivos traduzidos e a selecao de chunks permanecem; caches de objetos validos sao reaproveitados. Os ajustes do upstream para localizar SDK/CRT do Visual Studio nao foram copiados: esta base usa LLVM-MinGW/UCRT portatil e ja verifica um link Windows antes do build longo.

A interface WPF e seu executavel continuam sendo o componente 0.3.2; o motor/orquestrador e esta distribuicao sao 0.3.3-dev.1. Nao houve mudanca visual nesta entrega.

## Crash de execucao recebido

A tentativa recebida usou a 0.3.2-dev.1, perfil Original, RTX 5070 Ti Laptop e driver NVIDIA 617.42. O Vulkan iniciou, importou memoria, preparou a fila e recebeu comandos. A falha foi de CPU na BootupBackgroundWorkThread: 0xC0000005 ao ler guest 0x150, em hookshot.exe+0x11bd0984. Nao ha VK_ERROR_DEVICE_LOST nesse log.

O build recebido fechou o link de ambos os binarios: 223 segundos na compilacao, zero falhas, total registrado 382.62 segundos. Os chunks de jogo foram reaproveitados (0 s). Portanto, a compilacao longa anterior nao se repetiu nessa tentativa.

O RomFS registrado ocupa 160 caracteres antes do nome relativo. nn_fs.c usa char[MAX_PATH] e snprintf sem detectar truncamento: sobram 98 caracteres para um nome relativo ASCII nesse caminho. Isso demonstra uma limitacao do runtime em pastas profundas; os logs enviados nao mostram ainda qual arquivo falhou. Nao e prova da causa do ponteiro nulo.

## Teste sem mover dados

Jogar-Teste-Crash.cmd usa --short-romfs --trace-files --collect-crash. Cria um alias DOS livre apenas para RomFS, registra HOS_FS_TRACE e remove o alias ao terminar. Nao ativa validacao Vulkan nem estatisticas de todas as chamadas host, para evitar esse custo no teste. Nao ha recompilacao, extracao ou alteracao de saves nesse comando.

Coletar-Crash.cmd empacota a ultima tentativa. Os ZIPs incluem apenas logs, resumo e hookshot.map quando o executavel junto do mapa tem o mesmo hash daquele crash. Nenhum executavel, imagem, codigo gerado ou save e incluido. Antes de um novo build, o programa tenta preservar esse diagnostico, para nao perder o mapa anterior quando o link o substituir.

Mapear o simbolo anterior a um endereco nao equivale a demonstrar a causa da falha. Se o formato do mapa nao for reconhecido, ele e incluido para analise; se o executavel mudou, ele nao e atribuido ao crash antigo.

Fontes tecnicas do alias e da limitacao de caminhos: https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-definedosdevicew e https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation . A remocao usa DDD_EXACT_MATCH_ON_REMOVE para nao remover um mapeamento alheio.

## Limites

Nao foi executado o jogo ou uma GPU fisica neste ambiente Linux. Nao houve benchmark, verificacao visual do menu/iluminacao nem teste real do alias DOS neste host. A compatibilidade Windows foi conferida por compilacao/link cruzados e testes sinteticos; detalhes em resultado-native-0.3.3.txt e resultado-testes.txt.

Folhas, grama e samambaias incompletas, ruido em GTX 10xx e stutter no primeiro acesso a areas continuam sendo limitacoes relatadas pelo upstream. Nao foi atribuida a esta integracao uma solucao que o autor ainda esta investigando.
