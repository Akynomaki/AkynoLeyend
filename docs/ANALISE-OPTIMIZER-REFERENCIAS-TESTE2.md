# Análise da lentidão, otimizador e referências — 09/11/2026

## Registros do Teste 1

Recebidos Diagnostico.zip, três vídeos, logs de extração/lift/split/compile/census
e compile-summary.json. O build terminou: 393 unidades, dois processos, zero
falhas, 2.639,132 s de compilação; o manifesto registra 3.151,07 s no processo total.
A preparação encontrou 38.809 programas e 42.856 estágios, incluindo 4.128 compute.
A primeira preparação levou 351,8 s com dois workers; outra reutilizou os programas
em 1,1 s. Uma partida gastou 22,667 s na preparação inicial de pipelines.

Nos vídeos, a vegetação está presente, há artefatos e a taxa varia muito. As opções
salvas mostram saída 4K, 150% experimental, nitidez 100% e filtro Off; os logs
confirmam swapchain 1920×1080 e escala fixa 1,500. Há amostras pesadas com GPU em
43,3 ms e replay em 22,34 ms, sem espera por compilação de shader naquela amostra.
Timers podem se sobrepor: não somá-los. Não existe comparação pareada do Teste 2.

## build_optimizer.zip

O ZIP foi lido como material de análise; os seus scripts não foram executados.
Foram examinados detecção, cálculo, comandos, ambiente e fases.

| Parte | Achado e tratamento |
|---|---|
| Hardware salvo | Refere-se a outro PC e a um caminho E: da versão 0.4.0. A instalação consulta o computador atual. |
| Memória | O cálculo usa RAM total. O plano integrado usa RAM disponível e limite de commit, e mede novamente depois do lift. |
| CPU | O fallback estima núcleos físicos como metade dos threads. A integração informa os threads disponíveis ao processo. |
| Disco | A saída de volume não comprova NVMe. Disco não multiplica o limite de CPU. |
| ISA | O otimizador escolhe v4 pelo nome da CPU. Essa regra não verifica instruções; o pacote mantém seu alvo v3. |
| Blocos/tempos | A estimativa parte de 44 blocos. O build recebido gerou 212 blocos normais, além das partes quentes; não prometer 22 blocos ou 23,8 min. |
| Comandos | Há chamadas diretas a cli.py com imports relativos e opções incompatíveis (`--output`, `--folder`, `--renderer-from-source`). A integração usa manage.py e as opções reais. |
| Fases | Preservada a ideia de fases ordenadas e dados do plano; já existem logs e caches reais na base. Não adicionados scripts duplicados de limpeza. |

O modo Automático escolhe até oito processos por CPU/memória disponível. Alvo novo
12 MiB somente com pelo menos 32 GiB totais, 24 GiB disponíveis e oito threads;
nos demais casos usa 6 MiB. Para alvos maiores há orçamento de memória por processo
mais conservador. São estimativas de admissão, não medições de RSS nem garantias de
tempo. Valores manuais são respeitados e os limites de chunks existentes são mantidos.

## Hookshot 2.0.10

Fonte recebida no ZIP; tag oficial v2.0.10 resolvida ao commit
`7f9daf06d902588476102d6650c600bb84f02ce5`. Selecionados o cache por ID/comparação
com geração de registros de samplers e a união somente de cópias consecutivas dos
buffers capturados. A construção existente de samplers, incluindo o comportamento
AMD de comparação de profundidade, foi preservada.

O comentário/código desta versão deixa write-back diff e fila separada de presents
**desligados por padrão**, após o caso de device lost da issue 1161. O texto de
v2.0.8 descreve um estado anterior. Esses dois caminhos não foram transplantados
nem ativados nesta correção. Também não houve importação integral do novo runtime,
compilador ou menu. O ganho divulgado de 25% não é um benchmark do AkynoLeyend.

Regressões nativas verificam bytes idênticos após unir cópias, bordas, lacunas,
overflow e agrupamento por buffer; e cache de sampler com gerações, parâmetros
reescritos, comparação de profundidade e tabelas por thread, ligado/desligado.

## NX2navi 0.6.1

Setup recebido conferido contra tamanho/SHA-256 do NX2navi-update.json. Código do
commit `78ee0ddb1e29206ec730bbcfb8f5105cb4087499` e avisos foram consultados como
referência. LICENSE-ADDITIONS reserva as adições posteriores ao import inicial;
nenhuma dessas adições foi copiada. O estudo de atualizações que preservam o jogo
é compatível com a atualização local por revisão exata de host, implementada aqui.
Os executáveis e o AppImage fornecidos não foram executados.

## Preservação e limites

Host, lifter e ABI pública continuam idênticos ao Teste 1; somente três CPP do GPU
receberam as otimizações selecionadas. O identificador do tradutor de shaders foi
mantido e seu prefixo de hash compilado foi conferido nas duas DLLs, permitindo
manter os shaders preparados com a mesma GPU/driver/opções de tradução.
A atualização exige o host conhecido e mantém seu EXE, imagem e saves; não altera
código gerado manualmente. GUI Windows publicada e conferida, testes portáteis
executados, sem execução local do jogo/GPU física. Validação atual em
`validacao-teste-0.4.3-test2.json`.
