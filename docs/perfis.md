# Perfis e significado das variaveis

`original` e a referencia: preserva os defaults do motor e remove variaveis de experimentos anteriores do processo filho. `8gb` e uma configuracao experimental mais conservadora. Nenhum dos dois promete uma quantidade fixa de VRAM nem impede sozinho `VK_ERROR_DEVICE_LOST`.

| Ajuste do perfil 8gb | Valor | Escopo real |
|---|---|---|
| `RX_VK_VRAM_MB` | 2048 | Budget do cache de texturas; outros recursos tambem usam VRAM |
| `RX_VK_MIRROR_MB` | 1024 | Budget separado dos mirrors; eles continuam habilitados |
| `RX_VK_TEX_MAX_DIM` | 1024 | Selecao de mips em texturas grandes elegiveis; nao redimensiona toda a imagem do jogo |
| `RX_VK_TEX_MAX_MB` | 256 | Limiar para uma textura individual, nao para o cache inteiro |
| `RX_VK_IMPORT_CHUNK_MB` | 8 | Granularidade da importacao de memoria; valor potencia de dois |

Limiares de textura menores podem reduzir qualidade. Os caches trabalham com recursos em uso e trabalho em voo; seus budgets nao se somam a um teto absoluto de consumo do processo.

## Comparacao de movimento em 0.3.4

Desde 0.3.4, `nitido` e uma comparacao de movimento, disponivel em Jogar-Nitido.cmd:

| Ajuste Nitido | Valor | Escopo |
|---|---|---|
| RX_VK_TAAU_KEYS | fd029a317a9a4b94 | Seleciona a alternativa espacial de gameplay ja implementada; perde o antialiasing temporal |
| HOS_DYNRES | 0 | Resolucao 100%; pode custar mais pixels que Auto |

Nao habilita clamp de historico, nao altera exposicao, nao pula pipelines e nao limita texturas. Em AMD que ja usa o caminho espacial, o principal efeito pode ser a resolucao fixa. O perfil nao promete resolver folhas ou sombras. Os perfis Original/8GB da interface permanecem disponiveis.

## Conferencia do script sugerido na conversa (historico)

Nos fontes Ocarina 0.2.1 recebidos, nenhuma das nove variaveis `RX_VK_*` abaixo e lida pelo runtime. Elas pertencem ao Hookshot; defini-las no lancador antigo nao implementa essas politicas naquele motor.

| Variavel sugerida | O que os fontes do Hookshot mostram |
|---|---|
| `RX_VK_MIRROR=0` | Desliga mirrors. A economia depende do que foi alocado; pode aumentar leituras por PCIe e prejudicar muito o desempenho. |
| `RX_VK_VRAM_MB=2048` | Controla o budget do cache de texturas, sem limitar toda a VRAM. |
| `RX_VK_TEX_MAX_DIM=1024` | Participa da selecao de mips de texturas grandes, com condicoes. O default no codigo enviado e 2048. |
| `RX_VK_TEX_MAX_MB=256` | Participa do limite por textura; o default efetivo no codigo enviado e 1536 MiB, apesar de um comentario antigo citar outro valor. |
| `RX_VK_ASTC_CPU=1` | Desliga o caminho compute do decoder ASTC; nao significa necessariamente menor uso total. |
| `RX_VK_ASTC_RGBA8=1` | Desliga a conversao de grandes texturas para BC3 e as mantem como RGBA8. Pode aumentar bastante a memoria. |
| `RX_VK_PIPE_WAIT=1` | O nome aparece em comentario, sem leitura por getenv nessa copia. O comportamento efetivo usa `RX_VK_PIPE_SKIP`; esperar ja e o default. Esperar compilacao nao elimina seu custo. |
| `RX_VK_IMPORT_CHUNK_MB=8` | Ajusta a granularidade. Mais chunks tambem podem aumentar numero de imports e overhead. |
| `RX_VK_CAPTURE_POOL_MB=32` | Limiar do tamanho de pools incluidos nas capturas antecipadas, nao um teto global de 32 MiB para o sistema de captura. Reduzi-lo pode alterar a cobertura da sincronizacao. |

Os perfis novos mantem o caminho de compressao e a captura padrao. `ASTC_CPU`, `ASTC_RGBA8`, desativacao de mirrors e `PIPE_SKIP` nao sao usados como defaults de otimizacao.

## Comparar duas tentativas

1. Use o mesmo executavel, save, cena, resolucao e opcoes do menu.
2. Rode primeiro `Jogar.cmd`, depois `Jogar-8GB.cmd`, fechando o processo entre as tentativas.
3. Registre quanto tempo permaneceu na cena e a acao exata de troca de foco.
4. Compare imagem, FPS base, pausas e memoria. Separe caches frios de caches aquecidos.
5. Envie os registros completos de cada tentativa. Validacao Vulkan e frame generation alteram as medicoes e devem ser identificados.
