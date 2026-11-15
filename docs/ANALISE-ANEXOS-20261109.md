# Análise dos anexos — 09/11/2026

## Identidade

| Arquivo | SHA-256 | Resultado |
|---|---|---|
| integrated(2).zip | f4a28eaf856a9ae7d54d4779b1f3e8e3c82e2d887e62ede4645590bda23afa90 | Idêntico a integrated.zip e integrated(1).zip; 151 entradas |
| Nova pasta.zip | e64386d9275658826757f8308ee711eae96f920cddf007cc544a922f08f82868 | Catálogo Fritchii/Eden com 142 entradas em dez categorias |

Os arquivos foram inspecionados como referências, separados dos fontes ativos.
Não foram executados os scripts recebidos nem copiados compiladores inteiros.

## integrated

Há trabalho útil na organização das fases e nos modos PGO off/generate/use,
empacotamento, descoberta de patches e separação entre build completo e parcial.
Os scripts precisam de adaptação antes de dirigir esta base:

* `commands/generate.py` mantém um caminho absoluto de outro PC e executa
  `akynoleyend/cli.py` diretamente com `-I`; esta base usa `manage.py` para
  estabelecer o pacote e resolver seus imports relativos.
* `params/calculate.py` calcula jobs com RAM total e dobra o teto de CPU para
  NVMe. A base atual considera RAM disponível, commit e afinidade. Copiar o
  cálculo recebido pode aumentar simultaneamente o consumo e a paginação.
* A seleção alternativa de x86-64-v4 usa nomes de famílias. A detecção contém
  CPUID incompleto e inferências por banco de CPUs; não é uma consulta completa
  das instruções habilitadas pelo SO nesse computador.
* `generate_isa_rewrite_table` é explicitamente um placeholder: escreve cabeçalho
  com zero entradas. Não implementa emulação das instruções ausentes.
* O CMake pressupõe SDL3 e árvores `third_party/fsr-vulkan`, miniz, gcn e outras
  não fornecidas nesse ZIP. Nosso runtime distribuído usa SDL2 e outro build.
* Ativar PGO exige executar um binário instrumentado, produzir o perfil e usar
  esse perfil compatível. Memória e número de jobs sozinhos não validam PGO nem
  demonstram aumento de FPS. Alterar flags pode invalidar objetos do cache.
* O módulo de patches registra que a filtragem por título/build ainda é futura
  em `available_patches`. Não aplicar patches descobertos sem essa conferência.

Decisão: preservar o planejador atual e usar o material como referência para um
fluxo PGO explícito e validado, em trabalho próprio. Nada deste ZIP foi ativado
automaticamente na correção de extração.

## Catálogo Fritchii/Eden

| Categoria | O que há e o que precisa ser adaptado |
|---|---|
| GPU Thread Split | Fila SPSC e divisão puller/back; depende dos estados e da vida útil das engines/canais do emulador. Não equivale ao replay NVN nativo atual. |
| Async Pipeline Cache | Workers, cache em disco e estado de construção; útil para confrontar o aquecimento existente, com sincronização e invalidação por GPU/driver preservadas. |
| Submission/Async Draw | Orçamentos de flush e descarte de draws pendentes; exige conferir os efeitos dos draws antes de adotar, especialmente com vegetação problemática. |
| Frame generation/FSR | Código de interpolação, LSFG e upscale temporal; faltam recursos e dependências do projeto completo. |
| Queries/Fences | Implementações assíncronas acopladas ao rastreamento de memória e scheduler do emulador. |
| Scheduler | Worker, semáforos e pools; não pode substituir o scheduler da recomp isoladamente. |
| Shader recompiler | Base parcialmente compartilhada. Entre arquivos de mesmo nome com correspondência única, 19 são iguais após normalizar CRLF e 20 diferem. |
| Host shaders | Fontes de passes comuns, interpolação e probe da rede de upscale do próprio jogo. Não é um cache de shaders completo do jogo. |
| Thread utilities | Workers e rastreamento úteis como referência, mas não demonstram ganho nesta aplicação. |
| Documentação | Notas de outra implementação; seus números de desempenho não são medições do AkynoLeyend. |

### Reparos que a cópia integral perderia

O `global_memory_to_storage_buffer_pass.cpp` recebido ainda reescreve todas as
operações atômicas com três argumentos em `ReplaceAtomic`. A nossa correção do
Teste 3 preserva o quarto argumento de compare-exchange, verificado em seis
módulos SPIR-V. Substituir esse arquivo pelo catálogo reintroduziria o defeito
naquele caminho. Os estados do IR e o perfil de tradução também diferem.

### FSR 3, LSFG e DLSS

`vk_fsr3_upscaler.cpp` contém uma implementação dos passes do upscaler temporal
compatível com as constantes do SDK. Sua interface exige profundidade, vetores
de movimento, jitter e sinal de reset. Onze headers SPIR-V gerados que ele inclui
não estão no catálogo; os fontes desses onze passes também não vieram nas
pastas listadas. Integrar exige obtê-los, adaptar as entradas e validar barreiras,
histórico e resolução. O FSR 1 de apresentação já disponível na recomp continua
sendo uma implementação diferente desse caminho temporal.

`fsr3_frame_gen` usa optical flow e interpolação bilateral; o nome da classe não
comprova equivalência ao frame generation do SDK da AMD. `lsfg_common.cpp`
depende de `lsfg_shaders.h`, ausente no catálogo. O arquivo
`dlss_network_probe.comp` verifica brilho e NaN/Inf da rede do próprio jogo;
ele não fornece uma integração independente do SDK DLSS.

Preparar 116 mil pipelines e traduzir cerca de 39 mil programas são contagens
de objetos diferentes. O contador maior não mede por si só melhor compilador,
cobertura visual ou FPS. A comparação deve registrar programas aceitos/rejeitados,
variantes, pipelines, pausas e a mesma cena em cada implementação.

## Resultado desta rodada

O reparo entregue nesta rodada altera somente I/O e diagnóstico da extração.
Nenhum novo FSR 3, LSFG, DLSS ou ganho de FPS é declarado integrado ou medido
por esta correção. A validação visual do Teste 3 na RX 6600 continua pendente.
