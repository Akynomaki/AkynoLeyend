# Atualizacao do fluxo de otimizacao e leitura NUP

## Evidencia dos logs

A geracao passou pela falha anterior e terminou em 111 segundos, com 57 arquivos C. O comando seguinte chamou split_hot.py, que tentou abrir code_hot.c.whole inexistente. A base anterior definia A64_HOT_CHUNK, mas nao fornecia A64_HOT_FUNCS; o lifter separa esse arquivo apenas quando encontra funcoes da lista.

## Correcao aplicada

A lista de 849 enderecos do build e0f3ccfa passa a ser distribuida em profiles/e0f3ccfa/hot_funcs.txt e selecionada explicitamente. O script de divisao e chamado apenas quando a geracao atual produziu code_hot.c. Uma geracao sem funcoes separadas continua com as unidades normais; pecas e arquivo whole de uma geracao anterior sao removidos para impedir a selecao de codigo obsoleto.

O leitor NUP recebeu o suporte a wrappers Zstandard observado no pacote novo. Ele preserva .zs nativos e remove apenas a camada externa do dump, confere o tamanho descompactado e publica cada arquivo extraido apos terminar a escrita. A recuperacao de modulos completos de outro titulo do mesmo pacote foi adaptada do leitor fornecido. As verificacoes locais de caminhos e limites de metadados foram mantidas.

O cache privado guarda a identidade do leitor. Ao encontrar uma extracao antiga, o build executa uma verificacao/reparo na mesma pasta: arquivos packed sao extraidos corretamente mesmo quando um arquivo antigo tem o tamanho esperado. A identidade nova so e gravada apos sucesso. Uma tentativa interrompida volta ao reparo na proxima execucao.

## Origem e limites de integracao

Pacote adicional: HookshotBuilder(1).zip, SHA-256 0457778dfbafdef3d836b962b6f82ebd9e1ef8a28153ca06df7405b30ed306e8.

Foram usados a logica do leitor NUP, o perfil hot_funcs.txt e a distribuicao Windows x64 de python-zstandard 0.25.0 para CPython 3.14. A toolchain LLVM-MinGW e a orquestracao local foram preservadas. As demais alteracoes de host/GPU e os binarios de PGO do pacote adicional nao foram incorporados nesta correcao do fluxo; exigem validacao propria. Os binarios de a64emit e do compilador do pacote adicional tambem nao foram copiados.

A lista e metadado de enderecos, sem codigo de funcoes, imagem do jogo, saves ou cache. Licencas da dependencia foram preservadas.

## Validacao

51 testes Python passaram, incluindo o encadeamento ate a publicacao com e sem funcoes separadas; descarte de pecas antigas; NUP plain, compactado e sem tamanho no frame; preservacao de .zs; recuperacao de modulos; arquivo truncado; migracao real da extracao privada e recuperacao de reparo interrompido. As duas extensoes Windows da dependencia foram conferidas como PE x64 e mantidas no formato CPython 3.14 do pacote fornecido.

Nao houve execucao das extensoes Windows, do jogo ou de uma GPU neste host Linux. Os testes de extracao usam arquivos sinteticos e python-zstandard 0.25.0 no host.

A limpeza de chunks normais usa os nomes efetivamente gerados, pois a lista do lifter tambem inclui code_hot.c. Um teste cobre a retirada de um arquivo numerado antigo quando o arquivo hot conta como outra saida. Quando a etapa split e dispensada, seu log recebe a explicacao atual para evitar um erro antigo no diagnostico.
