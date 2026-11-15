# Correcao da primeira geracao standalone

Os logs recebidos mostram extracao concluida e `FileNotFoundError` em `nx2/chunks.py`, ao abrir `work/image/chunks.txt` para escrita. O lifter standalone grava a imagem em `work/sa/image`, mas reutiliza deliberadamente os limites de chunks de `work/image`. Uma instalacao limpa ainda nao tem esse segundo diretorio.

`save()` passa a criar o diretorio compartilhado antes de gravar. A imagem continua em `sa/image`; o local dos limites e o algoritmo de traducao nao foram alterados. As leituras em `load()` e `seed_from_gen()` agora usam gerenciadores de contexto para fechar os arquivos, inclusive ao encontrar a primeira funcao de um arquivo gerado.

A regressao reproduziu o mesmo FileNotFoundError nos tres casos antes da mudanca: gravacao inicial, primeira geracao standalone e retomada com codigo ja gerado. Todos passaram depois, preservando a imagem sintetica e os limites existentes. A suite completa terminou com 33 testes, zero falhas, zero erros e zero pulos.

Reaplicar Criar na mesma instalacao preserva as entradas privadas completas de `work/inputs` e repete o lifter para concluir a geracao. Nao remova a pasta work para aplicar esta correcao.

Validacao feita com entradas sinteticas; o jogo nao foi recompilado ou executado neste ambiente.
