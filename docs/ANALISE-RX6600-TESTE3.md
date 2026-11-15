# RX 6600 e Teste 3 — análise de 09/11/2026

## Evidências recebidas

O ZIP contém oito sessões do Teste 1, duas de preparação e seis de partida.
GPU: RX 6600, driver AMD 26.10.1. O cache de programas já separava GPU/driver;
não se atribuiu o defeito a uma troca de GPU sem evidência.

Uma sessão pesada usou no máximo 4.633 MB de 7.379 MB permitidos. Os registros
recebidos não mostram estouro desse orçamento nem device lost. Os arquivos
chamados diagnostico-crash de duas sessões registram código zero; isso por si
só não prova um crash. Uma sessão de preparação foi encerrada externamente,
outra concluiu 38.809 programas, 177 falhas, em 191 s. Algumas falhas correspondem
a redes intencionalmente omitidas em GPU não NVIDIA; seis eram o CAS corrigido.

A sessão que alcança o mapa acumula 149.625 ms na criação de pipelines na
transição e chega a 0,8 FPS durante essa amostra; depois registra 23 FPS. É
evidência de grandes pausas de compilação, não um benchmark do novo renderer.
O vídeo usa AV1 via Media Foundation síncrono; o diagnóstico não tinha trace de
relógio para quantificar o desvio de áudio.

A imagem inicial mostra corrupção de cores com menu legível. Uma captura
posterior, com portátil ligado, escala 100%, FSR e nitidez 70%, aparece sem a
corrupção generalizada. O relato associado informa 22 FPS e dois objetos com
brilho persistente. Não há comparação pareada do Teste 3; não declarar a
vegetação completa nem as cores/sincronismo definitivamente corrigidos.

## Demora de build

O log de texto posterior informa 1.399,7 s para entrada/extração, 293,3 s no lift,
3,3 s no split, 6.880,7 s em compilação/link e 8,3 s de publicação. Foram 393
unidades, um processo, 8,4 GiB disponíveis e nenhum objeto aproveitado. A captura
mostra 2h23 no total. Com reserva 2 GiB e estimativa 3,5 GiB por compilador, esse
paralelismo é compatível com o limite de memória observado; não copiar os três
jobs fixos do otimizador de outro PC. A manutenção evita repetir essas fases e
exige os objetos traduzidos existentes antes de compilar qualquer unidade.

## Mudanças e verificação

* CAS global→storage: preservados comparador e substituição. A fixture do IR/pass
  original reproduziu a exceção exata antes da correção. Depois, 70 unidades reais
  do backend foram ligadas e seis módulos SPIR-V passaram no spirv-val 2025.1.
* ASTC→BC3: uma camada por execução, do Hookshot 2.0.10 / PR956. Mantém a compressão;
  não força todas as texturas a RGBA8. Verificação visual ainda necessária.
* Vídeo: conversão RGBA sob demanda, EOS tratado com quadros ainda na fila e
  recuperação adicional limitada a quatro passos/8 ms entre chamadas ao decoder.
  Fixtures executam o código de fila e aquisição com planos NV12 e relógio sintéticos.
* Interface: Full HD real no host/menu/CLI/GUI; mouse, WASD e Ctrl+M; FPS e portátil
  no launcher; quatro perfis explícitos. WPF compilada/publicada, sem janela executada.
* Atualizador: pacote indexado com hashes, staged antes de fechar o launcher;
  troca/reversão de arquivos; preservação de SDKs, preferências, saves e work.
  Manutenção exige fonte/ABI conhecida e objetos antigos, sem extração/lift.
* Jogar: preparação automática, progresso encaminhado ao launcher e reaproveitamento
  do banco inalterado sem novo hash integral. O cache traduzido muda com o reparo do CAS.

Fonte Hookshot: commit 7f9daf06d902588476102d6650c600bb84f02ce5, GPL-3.0,
recebido no ZIP fornecido. Nenhuma adição reservada do NX2navi foi copiada.
Referências públicas: https://github.com/NotRexed/Hookshot/pull/956,
https://github.com/NotRexed/Hookshot/issues/993 e
https://github.com/NotRexed/Hookshot/issues/1006. Esses casos relacionados não
provam que a causa de toda a imagem recebida seja a mesma.

Identidades e limites de validação em `validacao-teste-0.4.3-test3.json`.
