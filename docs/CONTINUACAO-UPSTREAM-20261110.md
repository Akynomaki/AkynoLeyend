> Continuidade atual: [controles e write-back](CONTINUIDADE-CONTROLES-WB-20261110.md).
> O texto abaixo registra o checkpoint v7 anterior; seus itens pendentes e números não substituem a validação nova.

# Checkpoint de fontes — 10/11/2026

Candidato não lançado, baseado no Windows Teste 3. VERSION continua identificando
essa base; não existe um novo Builder publicado neste checkpoint.

Implementado: menu com ajuste/recorte, escala própria do FPS, caminhos de geração
com colchetes, LEA.HI constante sem carry, orçamento menor de texturas em placas
pequenas, pool conservador de targets aposentados, seleção de core rápido e
pin/restauração do replay síncrono Windows. A exclusão exata de GPU_PROFILE do
carimbo evita invalidar shaders só por diagnosticar. Cronômetros por draw são
opt-in; submit/present/espera continuam exatos. O profiler ganhou o span
`mirror write-back incl. barriers`.

A identidade Windows Teste 3 conhecida pode entrar na manutenção incremental;
a verificação de objetos traduzidos ausentes permanece. Não repetir extração
ou lift para atualizar somente host/renderer. Não editar C gerado à mão.

Validação: 230 testes descobertos, 221 passaram, nove omitidos, nenhuma falha.
Renderer Windows x64: 182 unidades compiladas e DLL ligada, Clang 23.1.4.
Host hos_thread compilado com headers do gerador original, sem dump do jogo.
Os artefatos de compilação e caches não fazem parte deste ZIP de fontes.

Pendente: teste visual/FPS no Windows; medição localizada dos custos de memória;
Button prompts e editor de bindings; FSR3 temporal e jitter; write-back lazy/diff;
texture detail por mip; hooks de tempo acima de 60 FPS; HDR; bugs AMD e vegetação.
Não adicionar controles de UI que ainda não têm implementação funcional.
O nosso host ainda tem stubs de mods e mapeamento fixo; a referência Button
prompts requer integrar esse caminho e gerar assets do RomFS local do usuário.

Origem: Hookshot GPL-3.0 v2.0.13/v2.0.14; avisos preservados em origem.md e
licenses/. Não foi incorporado código reservado do NX2navi. Para as tarefas
coordenadas e medições do usuário, consultar o pacote de continuidade separado.
