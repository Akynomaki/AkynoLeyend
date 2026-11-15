# AkynoLeyend 0.4.3 — Teste 3

## Atualizar uma instalação já compilada do Teste 1 ou 2

1. Feche o jogo e o Builder. Preserve a pasta `work` que pertence a essa instalação.
2. Extraia `AkynoLeyend-0.4.3-Teste-3-Atualizacao.zip` dentro da pasta que já contém
   `AkynoLeyendBuilder.exe`, substituindo os arquivos do pacote.
3. Execute `suporte/Atualizar-AkynoLeyend.cmd` e aguarde a conclusão.
4. Abra o Builder. A lateral deve mostrar **0.4.3 · TESTE 3**.

O primeiro passo manual instala o botão novo. Nas próximas atualizações, use
**Atualizar build**, ao lado de Jogar, selecione o ZIP recebido e deixe o launcher
reiniciar. Ele confere o pacote, aplica os arquivos e atualiza os componentes.
Também há **Ferramentas → Aplicar componentes instalados** para repetir a
manutenção depois de instalar os fontes correspondentes.

O atualizador usa pacotes ZIP fornecidos ao usuário; não há um servidor de
atualizações AkynoLeyend configurado para procurar/baixar versões sozinho.

O runtime de vídeo, a janela e a saída Full HD mudaram: é preciso compilar esses
componentes nativos e religar o EXE. **Não é um novo build completo do jogo**:
não há extração ou lift, e os objetos das unidades traduzidas são exigidos do
cache. Se uma unidade estiver ausente/incompatível, a atualização para antes
de iniciar essa compilação longa. Nesse caso, restaure o `work` correto ou use Criar.
Saves, preferências e ferramentas permanecem. A atualização tem reversão de
arquivos se a instalação ou a manutenção falhar; os detalhes ficam em
`atualizacoes/ultima-atualizacao.log`.

## Perfis e Full HD

| Perfil | Saída | Escala interna | Filtro | Portátil | FPS |
|---|---|---|---|---|---|
| AMD básico | 1920×1080 | 50% | AMD FSR 1 | Ligado | Visível |
| Fluidez | 1920×1080 | 67% | AMD FSR 1 | Desligado | Visível |
| Equilibrado | 1920×1080 | 75% | AMD FSR 1 | Desligado | Visível |
| Qualidade | 1920×1080 | 100% | AMD FSR 1 | Desligado | Visível |

Todos começam com nitidez 10%, geração de quadros desligada, ritmo ligado,
tempo real e cache Equilibrado. São pontos de partida; não são um benchmark.
1440p e 4K continuam no seletor de saída, independentemente da escala interna.
Full HD e perfil portátil são combináveis neste runtime; a seleção exige reinício.
Escolha **Mostrar FPS / Ocultar FPS** no launcher ou **FPS counter** no jogo.

O FSR integrado é o filtro espacial FSR 1 com EASU/RCAS. Não é FSR 3.1 nem geração
de quadros. Ele recebe a imagem de apresentação; EASU amplia quando essa entrada
é menor que a janela. Uma entrada igual/maior dispensa essa ampliação; o log
informa `EASU bypassed` em redução. Não confundir a resolução da janela com a
escala interna do 3D. Nitidez alta pode acentuar contornos/ruído.

## Menu sem setas

**Ctrl+M** abre e fecha. Insert e F1 continuam funcionando. Use W/S para navegar
e A/D para mudar valores, ou passe o mouse sobre uma linha e clique na metade
esquerda/direita do valor. Na nitidez, arraste a metade direita da linha.
Esc fecha. Enquanto o menu está aberto, o cursor fica livre e o clique nele
não deve capturar a câmera. A captura anterior volta ao fechar se o jogo tem foco.

## Preparação automática

**Jogar** confere o banco privado e prepara shaders/pipelines necessários antes
da partida. A interface mostra quantidade e porcentagem. Não precisa ir a
Ferramentas para a preparação normal. A opção manual continua disponível para
diagnóstico. A primeira abertura após mudar GPU, driver ou tradutor pode levar
vários minutos; as seguintes aproveitam o cache compatível. Banco inalterado
usa a conferência já registrada, evitando reler seu conteúdo inteiro em toda abertura.

Esta versão corrige um caminho do tradutor, portanto o cache traduzido muda uma
vez. O banco bruto do próprio usuário e os objetos C permanecem. O contador pode
mostrar tentativas de variantes (como 116.427 para 38.809 programas), depois outra
etapa de pipelines. Os números não representam a mesma unidade e não foram inflados.
Estados de pipeline encontrados pela primeira vez ainda podem causar pausas.

## Vídeo e RX 6600

Foi reproduzido e corrigido o erro `Invalid number of arguments 3 in
StorageAtomicCompareExchange32`: o caminho que transforma CAS global em acesso
ao buffer descartava o valor de substituição. A preparação recebida mostrou seis
programas afetados. O backend real passou na nova regressão e seis módulos SPIR-V
foram validados; isso não é uma execução do jogo na Radeon.

A conversão ASTC→BC3 agora usa uma camada por vez no scratch, seguindo a correção
Hookshot #956. É uma correção candidata para os arrays de terreno; não foi confirmada
a eliminação da imagem colorida na RX 6600 deste relato.

Vídeos NV12 deixam de converter/copyar RGBA quando o jogo só lê NV12. A recuperação
de atraso tem limite de passos e de tempo entre chamadas ao decoder, evitando
decodificar centenas de quadros de uma vez. Uma chamada do driver não pode ser
interrompida no meio. O sincronismo final de áudio/vídeo continua pendente de
comparação no PC. No perfil Compatibilidade, o diagnóstico registra o relógio do vídeo.

## Comparar

Use o mesmo save, posição e câmera, faça uma passagem de aquecimento e observe a
segunda por 60 segundos, com geração desligada. Teste também a mesma cutscene.
Anote versão, perfil, escala, saída, FPS e se as cores/brilhos persistem.
Depois feche o jogo e execute `suporte/Coletar-Crash.cmd`; ele também coleta
partidas encerradas normalmente. Envie o ZIP e uma captura. Não é necessário
enviar jogo, saves ou os bancos de shaders.

196 testes passaram, 9 foram omitidos; 12 verificações do launcher e seis módulos
SPIR-V passaram. DLL Windows ligada com 182 unidades; três C do host compilaram
com headers auxiliares de fixture. Sem execução local da janela WPF ou do jogo
em GPU física. Não há ganho de FPS medido para esta versão.
