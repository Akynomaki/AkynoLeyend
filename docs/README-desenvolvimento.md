# AkynoLeyend — desenvolvimento 0.4.3

**Checkpoint de fontes de 10/11/2026: candidato não lançado.** Esta árvore contém
backports 2.0.13/2.0.14 e ajustes de diagnóstico posteriores ao Teste 3.
Não copie estes fontes sobre uma instalação pronta. O `VERSION` abaixo identifica
a base Windows anterior, não um novo executável publicado.
Veja [o estado e os limites](docs/CONTINUACAO-UPSTREAM-20261110.md).
Controles/ícones e write-back diferencial opt-in foram implementados depois deste checkpoint.
Veja [a continuidade atual e as tarefas Windows/FSR](docs/CONTINUIDADE-CONTROLES-WB-20261110.md).
FSR temporal/AMD Frame Generation e a validação física continuam pendentes.

**Versão Windows de teste: 0.4.3-test.4.** Inclui Full HD, perfis com FSR 1 e FPS,
menu por mouse/WASD, preparação automática de shaders ao jogar e atualização pelo launcher.

**Já compilou o Teste 1 ou 2?** Extraia a atualização na pasta que contém o Builder
e execute `suporte/Atualizar-AkynoLeyend.cmd`. Esse primeiro passo instala o botão
novo; atualizações seguintes usam **Atualizar build**, ao lado de Jogar, escolhendo
o ZIP de atualização. O fluxo reaproveita os objetos do jogo em `work`, recompila
os componentes nativos alterados e religa o EXE. Não repete extração nem lift.
Se os objetos necessários sumiram ou mudaram, ele interrompe e explica.

Em **Gráficos**, escolha **AMD básico · Full HD + FSR**, Fluidez, Equilibrado ou
Qualidade. A primeira escolha usa perfil portátil e escala interna 50%; as outras
usam 67/75/100%. Todas selecionam saída 1920×1080, FSR 1 e contador de FPS.
Use **Ctrl+M** no jogo; mouse ou WASD controlam o menu, inclusive a nitidez por arraste.

Ao clicar em **Jogar**, o launcher confere o banco e mostra a preparação de shaders
e pipelines. A primeira inicialização depois desta correção do tradutor prepara
o cache novamente; as seguintes reutilizam o que corresponde à GPU/driver.
O [roteiro](docs/TESTE-0.4.3.md) detalha instalação, atualização e comparação.

Em instalação nova, use o ZIP completo e **Criar** com sua entrada local.
O modo Automático consulta CPU e memória disponível deste computador.

O projeto usa o compilador ARM64 e o renderizador Vulkan derivados do Hookshot,
com launcher Windows e orquestração próprios. Não contém jogo, saves ou caches
privados. Os arquivos recebidos para análise ficam fora desta árvore.

## Entradas principais

| Entrada | Função |
|---|---|
| AkynoLeyendBuilder.exe | Interface Windows, quando publicada destes fontes |
| Compilar.cmd | Compilar a entrada local do usuário |
| Jogar.cmd | Conferir e executar o build atual |
| Preparar-Shaders.cmd | Preparar os shaders da entrada local |
| Verificar.cmd | Conferir ferramentas e dependências |
| suporte/ | Diagnóstico, reparos e perfis opcionais |

O pacote Windows inclui os executáveis e SDKs; a cópia separada de fontes não os inclui. A manutenção destes fontes reconhece os hosts conhecidos dos Testes 1 e 2 e a identidade Windows Teste 3 conferida;
versões anteriores aos patches de saída e pools exigem um novo host.
Uma futura distribuição deve passar pelas verificações de identidade do launcher,
renderizador e host antes de ser publicada.

## Gráficos em desenvolvimento

- FSR 1 oficial AMD: EASU e RCAS separados; não equivale a FSR 3 ou geração de quadros.
- Saída 1920×1080, 2560×1440 ou 3840×2160 com escala fixa; exige reinício do jogo.
- Escalas internas, Lanczos, Catmull-Rom, nitidez e frame pacing no launcher/menu.
- Preparação BNSH, BAHS, NDSR e NDVE com banco em disco e leituras limitadas.
- Reparos de registradores e dos pontos das sombras da grama provenientes da referência.

O backend disponível é Vulkan. O renderizador WebGPU que não participava deste
build foi retirado; os tipos e registros NVN compartilhados foram preservados.
Licenças, créditos e fontes exigidos pelas dependências continuam incluídos.

## Desenvolvimento

akynoleyend/ contém a orquestração; nx2/, a tradução; host/, o runtime;
gpu/vk/, o renderizador e seu compilador; builder/, a interface Windows.
work/ e jogo/ são resultados locais e ficam fora dos fontes e pacotes.

```text
python -m unittest discover -s tests -v
python tools/test_fsr_present.py
```

O segundo comando exige headers/loader Vulkan e um dispositivo compatível, que
pode ser um ICD por software. Esses testes não confirmam o jogo em AMD/NVIDIA.

Estado e evidências: [estudo gráfico](docs/ESTUDO-GRAFICO-20261109.md),
[validação](docs/validacao-grafica-043.json), [limpeza](docs/limpeza-043.json),
[arquitetura](docs/arquitetura.md), [origem](docs/origem.md) e [créditos](creditos/README.md).
Documentos que descrevem versões anteriores são históricos.
