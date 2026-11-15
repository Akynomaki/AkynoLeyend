# Análises até a 0.4.4 (12/11/2026)

O que foi medido, lido e decidido entre a r13h e a 0.4.4. As notas de cada revisão estão em `docs/origem.md`; aqui fica o
porquê. Nada aqui afirma que o jogo foi testado numa placa ou CPU além das citadas.

## 1. Desempenho no PC do Teste-1 (vídeo e diagnóstico de 12/11, 16:16)

PC: Ryzen 5 3500X (6 núcleos, sem SMT), 16 GB, RTX 3060 Ti 8 GB, driver 616.92. Build r13h.

| Medida | Valor | Leitura |
| --- | --- | --- |
| FPS base na Cidade do Castelo | 6 a 17 (mediana no log 18,7) | ~53 ms por quadro |
| Espera da CPU pela GPU | 0,1 ms | a GPU não é o limite |
| GPU por quadro | ~15 ms | sobra GPU |
| CPU no vídeo | 85 a 94% | os 6 núcleos no limite |
| Esperas por núcleo virtual | até 250 ms | as travadas |
| Geração de quadros | ligada no meio da sessão (0 → 3x) | ~55 FPS mostrados sobre base 18 |

Causas, em ordem de peso:

1. **Laços de sono curto do jogo nos 6 núcleos.** Os trabalhadores ociosos (`ModuleSystemWorker*`, `OptimizeChangeBanc`)
   dormem 20 µs e olham a fila de novo; o host cedia a vez em laço, ocupando um núcleo por thread. Corrigido na r13i
   (Hookshot PR 2263).
2. **Descarte de um oitavo do cache de texturas perto da linha dos 90%.** 645 descartes na sessão, por exemplo
   2936 → 2562 MB e de volta. Corrigido na r13i (Hookshot PR 2826, medido pelo Hookshot numa 3060 Ti no mesmo lugar).
3. **Cópias de volta de buffers grandes escritos pela GPU** (`slow descriptor 55,7 ms`, `slow submit 196,7 ms`). Não mudado;
   o perfil `4k-wb-experimental` (`RX_VK_WB_MAX_KB`) fica para um A/B.
4. **Modo de cache "streaming" no launcher** (16 MB de leitura antecipada: 1003 faltas para 69 acertos). Recomendação:
   "Equilibrado" em PCs com 16 GB.
5. **Geração de quadros 3x sobre base de 18 FPS**: espaçamento irregular e atraso de 18 FPS. Recomendação: desligada até a
   base passar de ~40.

Depois da r13i o jogador relatou que funciona; o diagnóstico dessa sessão ainda não foi conferido.

## 2. Repositórios comparados

| Repositório | Licença | O que serve |
| --- | --- | --- |
| Hookshot (NotRexed) | GPL-3.0, a base | Copiável com aviso. Usados: PR 1334 (árvores), 2263 (sono curto), 2826 (VRAM). Candidatos: 2865/2869 (pipelines na primeira abertura depois de preparar), 2545 (blocos de terreno escritos pela GPU), 2731 (write-back limitado), 2850 (preset "Auto (este PC)"). |
| Lichii (zortos293) | GPL-3.0 | PR 408: funções auxiliares de memória global expandidas em todos os estágios menos compute; chave de pipeline só com os atributos lidos (nosso renderizador monta a chave de outro jeito: a conferir). Build genérico com presets de CPU (ideia usada na r13j). |
| Fritchii (Frizti) | GPL-3.0 (fork do Lichii) | Issue 55: padrões para placas com menos de 5 GB (não é o caso da 3060 Ti). Mesmo esquema de presets de CPU do Lichii. |
| NX2navi (tangerineturtle1) | todos os direitos reservados | Só ideias, nenhum código. |
| eglantine (ProfMPPDias) | sem licença | Nada copiável. Mistura Lichii e Fritchii; cache de shaders, interface PT-BR, launcher 3D. |

## 3. Árvores no ar

A oclusão real da r13h funciona (mais de 100 mil relatórios, ~70% zero), mas não era a causa. A causa é o PR 1334 do
Hookshot: no NVIDIA, com a função de leitura da memória global não expandida, o programa de tarefa das árvores
(`3cb76827`) lia o endereço errado na terceira leitura, recebia 0 e desenhava 256 árvores por célula. Corrigido na r13i, só
nos estágios de tarefa e malha; o cache de programas retraduz só esses (tipo de registro 16) e a primeira abertura prepara de
novo.

## 4. Código 0xC000001D num PC com RX 590 (Teste 4 r3)

O jogo fechava na abertura com instrução ilegal: registradores do jogo todos em zero, falha no código de início do host. O
build era sempre x86-64-v3 (AVX2, FMA, BMI1/2); uma CPU sem essas instruções para na primeira delas. A DLL pronta também é
x86-64-v3 (9711 usos de `ymm`; compilada para x86-64, nenhum). Na r13j o Criar escolhe o nível pela CPUID (v3, v2 ou x86-64),
o renderizador é compilado no PC quando o nível é menor (sem DLSS), o Jogar recusa um build que a CPU não roda e a tela de
jogo encerrado explica o código. Conferido: host, dois blocos grandes do código traduzido e a DLL compilam em `-march=x86-64`;
o FFmpeg do pacote já é genérico. Não executado numa CPU sem AVX2.

## 5. O ramo Intel e a junção na 0.4.4

O ramo Intel (r13d e r13e a partir da r13c) corrige a GPU integrada da Intel: código 70 na tela de título e na floresta
(limite do compare-exchange, posição invariante, saída de cor sem NaN; cópia dos uniformes na Intel), silhuetas pretas (fim
dos storage buffers com alinhamento acima de 16) e explica 0xC000013A e pouca RAM. Avaliação de cada mudança:

| Mudança do ramo Intel | Efeito na NVIDIA | Na AMD | Na Intel | Decisão |
| --- | --- | --- | --- | --- |
| Limite do compare-exchange | nenhum (desligado) | ligado: só termina laços infinitos | evita perda do dispositivo | entra |
| Posição invariante | nenhum | ligado: evita buracos no passe de cor | idem | entra |
| Saída de cor sem NaN | nenhum | ligado: evita blocos brilhantes no bloom | idem | entra |
| Fim dos storage buffers | nenhum (alinhamento 16) | nenhum (4) | corrige silhuetas pretas | entra |
| Cópia dos uniformes | nenhum (só Intel sem espelho) | nenhum | evita perda do dispositivo; não é neutra numa RTX | entra, só na Intel |
| 0xC000013A e pouca RAM | — | — | — | entra |
| Texto do 0xC000001D e aviso de AVX2 | — | — | — | não entra: a r13j já compila para a CPU, e o texto ficaria errado |

Nenhuma mudança do ramo Intel desfaz uma da r13d-r13j, nem o contrário. A mesclagem de três vias não teve conflito de
texto, e as duas marcas do cache de programas (as flags do ramo Intel no `disk_stamp`, o tipo 16 e a marca de preparação da
r13i) convivem.

## 6. Testes e verificações

- Bateria completa: os mesmos 15 testes que falham na r13h, na r13i e na r13j falham na 0.4.4, todos de ambiente (o clang do
  sistema com cabeçalhos MSVC e `-Werror`, a contagem de jobs do `test_hot_pipeline`); os demais passam, inclusive os dos
  dois ramos (`test_r13d_intel`, `test_r13e_ssbo_end`, `test_r13e_exit_reasons`, `test_r13i_p0`, `test_r13j_cpu`).
- DLL do renderizador 0.4.4 compilada com a toolchain do pacote; host conferido; launcher republicado com a versão 0.4.4.
- No jogo: só no Teste-1 (RTX 3060 Ti), e só o que está escrito em cada revisão. A Intel foi vista pelo ramo Intel, na r13e
  dele; a AMD e as CPUs sem AVX2 não foram vistas com a 0.4.4.

## 7. Pendências

- Conferir o diagnóstico de uma sessão com a 0.4.4 no Teste-1 (FPS base, árvores, descartes, esperas por núcleo).
- Intel: o véu de luz em Kokiri (compute `ee7764a6b1ef459c`) e a perda intermitente no compute `4b03b3040d7cf076`.
- Um PC sem AVX2: Criar com a 0.4.4 e a linha `machine:` do `erros.log`.
- Atualizações em PCs sem AVX2 compilam o renderizador no PC (sem DLSS).
- A/B do write-back limitado; preparação de pipelines na primeira abertura; PGO (falta `llvm-profdata`).
