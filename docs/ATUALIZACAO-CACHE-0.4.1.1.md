> HISTÓRICO: este documento descreve uma revisão anterior. O estado atual está em `../README.md` e `Relatorio-AkynoLeyend-0.4.2.md`.

# AkynoLeyend 0.4.1.1 — preparação de shaders e compatibilidade de folhagem

**Data:** 2026-11-08. **Tipo:** patch de fontes integrado no ZIP Windows do AkynoLeyend 0.4.1. **Estado:** candidato, sem validação visual no Windows.

## Evidência do log Hookshot 2.0.5

Log recebido: `hookshot_log(2).txt` de uma RTX 4060 Ti, 5.842 linhas. Não é um benchmark pareado do AkynoLeyend.

- Cache inicial de programas: **0 chaves, 0 KiB**. Cache de pipelines do driver: **464.205 KiB**.
- Primeiro preparo: **38.809 programas, 46.570 novas traduções, 97 falhas, 10.340 bibliotecas de estágio, 639,9 s**. As quantidades incluem conceitos distintos e não devem ser somadas.
- Passagem de pré-compilação: **10.340 pipelines compute, 0 graphics, 6.853 ms**. **Não** é prova de ausência de compilação de gráficos durante a partida.
- **84 linhas visíveis** `does not lower`. Principais ocorrências: 40 de `native constant LEA carry mode` (opcode 0xa11), 17 `native formatted surface load mode` (0xb97), 12 `unsupported native opcode` (0x905). Esses números não são necessariamente 84 shaders distintos.
- Aparecem amostras com trabalho de shaders durante a sessão, até **102,7 draws/frame não prontos** e **182 ms** de espera média para os shaders/pipelines nessa amostra. O total de FPS das amostras não representa benchmark.
- O log encerrou com fechamento da janela, sem `device lost` registrado. Isso **não demonstra** que o programa é imune a device lost, nem que os problemas da RX 9060 XT estão resolvidos.

## Melhorias realmente incorporadas

1. **Mesmo limite real de workers do começo ao fim**: `RX_VK_COMPILE_THREADS=1..8` agora limita tanto a tradução do seed quanto o pré-aquecimento dos pipelines. Antes, o launcher aceitava 8, o seed limitava a 4 e o prewarm normal ignorava a seleção e podia criar 64 threads. Continua limitado também aos núcleos lógicos e às tarefas disponíveis. Comportamento Original: seed default 2 e prewarm default até 8 núcleos; Streaming continua default 2; opção do usuário prevalece.
2. **Atualização controlada do tradutor Ampere→Maxwell**: traz de Hookshot 2.0.5 o fallback de renomeação estendida de registradores e suporte ampliado para dependências/LEA e programas que antes falhavam, incluindo caminhos usados pela vegetação. A primeira tentativa de lowering preserva a rota antiga e só recorre à nova quando ela falha. O caso novo de global compare-and-swap 0x3a9 **não** foi habilitado, porque a camada Maxwell/IR do AkynoLeyend ainda carece do `ATOM_cas` completo; copiar somente o opcode criaria uma falsa correção. O shader cache é invalidado quando a identidade do tradutor muda; uma preparação completa no primeiro uso é esperada.
3. **Diagnóstico integrado**: `Analisar-Log-Shaders.cmd` processa um arquivo de log de execução e cria um resumo JSON sem caminhos internos, com causas de falhas, tempos, contagens de caches e amostras de FPS. Não executa binários, não modifica arquivos de shader e não distribui caches de outros usuários.
4. **Regressões**: teste C++ nativo do lowering de DEPBAR e testes Python do resumo e dos limites de compilação. Os arquivos originais permanecem; não há alterações em saves, ROM, nem alterações automáticas de switches de terceiros.

## Por que o instalador MDias não foi incorporado

`vulkan.bin`, `vulkan.fork-v54.bin` e `vulkan_static_pipelines.bin` pertencem a outro pipeline de cache, com identidade de driver/dispositivo e formato interno próprios. Conforme a especificação Vulkan, cache de pipelines pode depender da GPU, versão do driver e UUID. Um `.ash` do Eden também não é automaticamente uma entrada no cache HKSEED01 do AkynoLeyend. Copiar esses arquivos como se fossem shaders binários universais pode provocar rejeição, corrupção de cache ou compilação repetida, não ganhos demonstrados.

**Também não houve integração de FSR 3.1/LSFG/OpenGL por simples cópia de shaders.** Essas opções exigem novas interfaces e testes de sincronização. As atualizações aqui focam o tradutor existente e a fase de compilação.

## Testes e limites

- O teste nativo DEPBAR foi compilado e executado no Linux usando C++20; os novos testes de cache também passaram.
- Sem teste de GPU física, não podemos afirmar correção da vegetação, melhoria de FPS, ausência de microtravamentos, ou crash AMD resolvido.
- **O EXE WPF e a DLL pré-compilada no ZIP ainda pertencem à build anterior**. É necessário executar **Criar** no Builder Windows para recompilar o EXE do jogo e a DLL Vulkan a partir destes fontes. Não basta rodar um EXE ou substituir a DLL antiga, porque a correção de diretórios fica no host. A hash dos fontes alterados impede a reutilização silenciosa de um renderizador pré-compilado incompatível.
- Recomenda-se primeiro testar vegetação a 100% de escala, com `--framegen 0`, e comparar a mesma cena. Depois testar o modo Equilibrado e `--shader-workers 2`, 4 e 8 em sessões separadas. Meça tempo de preparação e FPS real depois do aquecimento do cache.

## Créditos

Base e referências: NotRexed/Hookshot v2.0.5, Khronos Vulkan Pipeline Cache, código GPL-3.0-or-later de shader recompiler Eden/Suyu já incluído no projeto. Cabeçalhos e licenças de terceiros preservados; testes nativos do upstream incorporados com atribuição.
