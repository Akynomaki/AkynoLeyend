# Correção de extração NUP 1 — 09/11/2026

O log recebido é da versão 0.4.2, na primeira etapa, após 15.000 arquivos.
Falhou a abertura de um temporário cujo nome era o nome completo do arquivo
seguido por `.part`. O caminho transcrito tem 257 unidades UTF-16. Isso o
aproxima de MAX_PATH, mas não prova que o limite de 260 tenha sido ultrapassado.
O log também não comprova corrupção do NUP ou falta de espaço: informa 548 GB
livres. A disponibilidade da unidade S: e o acesso ao diretório ainda podem
precisar de verificação se o erro persistir.

## Mudança

`nx2/nup.py` passa os caminhos de I/O do Windows pelo formato Unicode estendido,
incluindo UNC. Usa um temporário exclusivo com nome curto, criado no próprio
diretório de destino, e publica por renomeação depois de concluir a entrada.
Limpa somente seu próprio temporário em falha. A validação dos caminhos do
arquivo e a proteção contra saída da pasta continuam ativas.

Erros de escrita agora informam errno, winerror, comprimento e existência do
diretório pai. O aplicador verifica o hash exato do leitor antigo, salva backup,
substitui atomicamente e executa uma extração sintética no mesmo volume. Se a
verificação falhar, restaura os bytes anteriores. Mantém o bloqueio do build.

O reparo não altera EXE, DLL, saves, objetos ou dados do NUP e não inicia o
compilador. Foi preparado para a instalação cuja extração falhou antes de um
primeiro build completo. Recusa substituir o leitor de uma instalação com
manifesto de jogo pronto, evitando invalidar a identidade dos fontes desse
build. Os ZIPs do Teste 3 anteriormente entregues permanecem imutáveis.

## Aplicar no PC afetado

1. Feche o jogo e o Builder.
2. Extraia `AkynoLeyend-Correcao-Extracao-1.zip` na pasta que contém
   `AkynoLeyendBuilder.exe`, `ferramentas` e `nx2`.
3. Execute `Corrigir-Extracao.cmd` e aguarde `CORRECAO CONFIRMADA`.
4. Abra o mesmo Builder e repita Criar com a mesma entrada e destino.
5. Preserve `work`. O reparo não apaga extrações nem objetos anteriores.

A fase que falhou neste log foi extração. Tradução e compilação ainda precisam
ocorrer para produzir o primeiro jogo. Não se promete retomar do arquivo 15.001:
o staging anterior pode ter sido removido pelo encerramento da tentativa.
O leitor reutiliza entradas simples completas quando a mesma árvore permanece;
arquivos compactados seguem a conferência/reparo de conteúdo já existente.

## Verificação e limites

25 testes de extração/reparo passaram no host Linux. Incluem gravação real em
caminho com mais de 350 caracteres, nome temporário curto, conteúdo compactado,
UNC/Unicode, falha de disco, preservação do arquivo completo, idempotência,
reversão e bloqueio de compilação. O comportamento Win32 não foi executado aqui.
O teste com o nome temporário antigo reproduz uma falha de abertura simulada;
não é uma reprodução física da causa específica da unidade S:.

Leitor antigo SHA-256 (LF):
`aabc240ecde5084ddba80c53a49b55a871be188cf31c03d3c5bf1a8b82b650a1`.
Leitor corrigido SHA-256 (LF):
`c1b9fb6f9bb6a6548d77d7a773a36fc852a37b40ba3c5285d27a1d8bcaef4374`.

Referência de formato Win32:
https://learn.microsoft.com/pt-br/windows/win32/fileio/maximum-file-path-limitation
