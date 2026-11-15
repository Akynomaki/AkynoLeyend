# Análise 0.4.5: tempo de criação do jogo

PC: Ryzen 5 3500X (6 núcleos, 6 threads), 16 GB, SSD SATA. Referência: o log da r13c enviado em 12/11/2026, 2 h 21 min no total.

## Onde ia o tempo (r13c)

| Etapa | Tempo | Causa |
| --- | ---: | --- |
| Entradas: identidade do .nup + extração | 1222 s | 193 s de SHA-256 dos 25 GB em toda criação; 186 mil arquivos, cada um com nome temporário + renomeação; `.zs` embrulhado descomprimido duas vezes |
| Tradução (lift) | 367 s | não mexido |
| Compilação | 6887 s | **1 processo**: 3,5 GiB reservados por compilador, e havia 7,7 GiB livres |
| Link e publicação | 18 s | não mexido |

## Memória real por unidade (clang-23, pico)

Medida com `PeakWorkingSet64` e `PrivateMemorySize64` do processo `clang-23.exe`, filho do `x86_64-w64-mingw32-clang.exe`.
Foram 6 unidades juntas, e depois uma compilação completa.

- **Blocos comuns de 6 MiB:** 0,28–0,48 GiB (51 medidos).
- **Blocos pesados (os que levam mais de 1 min):** `code_087` 2,56, `code_083` 1,48, `code_088` 1,44, `code_081` 1,42 e
  `code_082` 1,33 GiB.
- **Peças hot em -O2:** `hot_7` 1,82, `hot_5` 1,70, `hot_1` 0,97, `hot_3` 0,91 e `hot_4` 0,57 GiB.
- **Seis unidades pesadas juntas:** a soma ficou em 4,66 GiB.

O pico acompanha o tempo da unidade, não o tamanho. Por isso a estimativa vem do tempo conhecido, ou do pico medido mais
15%.

## Compilação: antes e depois, mesmo PC e mesmas 400 unidades

| | r13c | 0.4.5 |
| --- | ---: | ---: |
| Processos ao mesmo tempo | 1 | até 6 |
| Tempo de compilação | 6874 s (114,6 min) | **1424 s (23,7 min)** |
| Falhas | 0 | 0 |
| Esperas por memória | — | 14 |

O teste da 0.4.5 rodou com 7,9 GB livres e o launcher r13c aberto, numa pasta de trabalho separada sem cache de objetos.
O renderizador pronto foi usado, como num Criar normal.

- **hot_7** (a unidade mais longa): começou no segundo 0 e terminou aos 643 s. Sozinha, levou 510 s.
- **Resultado:** link de 449 MB sem erro.
- **Objetos:** iguais aos de uma compilação de uma unidade por vez, byte a byte, fora o carimbo de hora do COFF (bytes 4–7),
  que muda até entre duas compilações seguidas do mesmo arquivo. Conferido em `code_044`, `code_120`, `code_013`,
  `code_hot_4` e `a64_table`.

Simulação com os tempos do log e a RAM livre no início:

| RAM livre | Tempo previsto |
| ---: | ---: |
| 4 GiB | ~52 min |
| 5 GiB | ~38 min |
| 6,6 GiB | ~27 min |
| 9,5 GiB | ~24 min |

O limite de baixo é o hot_7: sozinho, ~10 min com os núcleos ocupados.

## Extração do .nup

Os bytes ficaram idênticos ao leitor anterior. Conferido em 12 mil arquivos do começo e em 6 mil arquivos comprimidos.

| Trecho | Leitor anterior | 0.4.5 |
| --- | ---: | ---: |
| 12 mil primeiros arquivos (1,9 GB) | 34–49 s | 27 s |
| 6 mil arquivos comprimidos de uma pasta | 39–45 s | 3,9–4,5 s |

O tempo ia para o Windows: criar, fechar e renomear (no perfil, 6,6 s de renomeação em 37 s), e não para o Python. Threads
pioraram o resultado: 21,5 s com 3 e 52,7 s com 6 no trecho comprimido, porque os arquivos disputam a mesma pasta. Ficou 1
thread por padrão.

A identidade do .nup (SHA-256, 193 s) fica guardada pelo caminho, tamanho e data. A partir da segunda criação, não lê os 25 GB
de novo.

## O que não mudou

- **Tradução (6 min):** é o lifter do Hookshot, num processo só.
- **Otimização:** -O1 nos blocos e -O2 nas peças hot, como antes. Nada foi trocado por velocidade de execução do jogo.
- **Primeira extração:** continua gravando os 26 GB. O ganho medido é por arquivo. O total no jogo inteiro não foi medido.

## Não conferido

- Um Criar completo pelo launcher com o pacote 0.4.5. Foi conferida a compilação completa pelo `nx2/build.py` novo e a
  extração por trechos.
- Outro PC.
