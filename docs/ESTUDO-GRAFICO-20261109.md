# Trabalho gráfico 0.4.3 — NÃO É RELEASE

Em 09/11 o usuário esclareceu que precisa receber uma versão de teste para
validar o resultado. A distribuição de teste 0.4.3-test.1 inclui launcher, DLL
Vulkan e ferramentas genéricas. A confirmação no jogo continua pendente; não é
uma declaração de vegetação/FPS resolvidos. O roteiro está em `TESTE-0.4.3.md`.
A cópia de fontes permanece separada e não contém jogo, saves, caches ou SDKs.

## Referência e novos arquivos recebidos

A referência de fontes é Hookshot v2.0.6, commit
`fa439391aae6f3bf104340ea36c6ea993b38534e`, cujo `nx2/version.py` calcula o
fingerprint `9b541c9c`. O novo log e a captura v2.0.7 mostram esse mesmo fingerprint;
ele não é um commit Git nem prova de identidade dos binários. O instalador
HookshotBuilder.exe recebido coincide com o digest do asset oficial; não foi executado.

Nesta continuação foram lidos os dois logs, o vídeo, o banco novo, os seis arquivos
Shader, o dicionário de Pack, os cinco módulos ExeFS, TableParam, AnimationEvent,
os Boxes e as cinco partes do RuntimeId. Os dados privados ficam fora dos fontes.
As identidades disponíveis estão em `verification/new-input-identities043.json`.

As cinco partes (`parte 1.zip`, `parte 2.zip`, `parte3.zip`, `parte4.zip` e
`ultimaparte.zip`) têm 35.313 RuntimeIds únicos, mais duas cópias idênticas.
Todos correspondem aos 35.313 registros dos 51 Boxes: nenhum ID faltando ou extra.
Isso confirma a cobertura do conjunto enviado, sem afirmar que o culling foi
executado corretamente. Os arquivos não foram alterados. As partes substituem
para a análise os antigos arquivos grandes indisponíveis RuntimeId.zip e
PreComputedCulling; não é necessário solicitar novamente esses mesmos conteúdos.

## O que os logs dizem sobre FPS

O log novo seleciona RTX 5070 Ti Laptop e registra Hookshot v2.0.7, saída de jogo
2048×1152. A captura mostra renderização a 50% (768×432), Lanczos, nitidez 50%,
handheld ligado e geração de quadros desligada. Não equivale a uma renderização
interna nativa na resolução do monitor. O vídeo está codificado a 240 FPS;
os valores visíveis de jogo nos quadros inspecionados são 33, 36 e 44 FPS.

Filtrando o log por média de pelo menos 1.000 draws, há 132 amostras:
mediana 40,7 FPS, GPU 14,3 ms e 2.147 draws. Os timers de replay têm medianas
submit 12,67 ms, draw 7,525 ms, descritores 2,665 ms e programas 1,5 ms.
Esses timers se sobrepõem e não devem ser somados. Sugerem investigar trabalho
por draw/binding na CPU, sem provar um gargalo único. O log é da referência;
não existe benchmark pareado do AkynoLeyend após estas mudanças.

## Vegetação e tradução de registradores

O reparo REGMAP da PR759 de pelicanux faz um levantamento dos operandos antes de
escolher registradores temporários. Evita escolher um marcador que coincide com
um registrador original visitado depois. Não muda filtros de cor nem descarta shaders.

No primeiro banco privado, com 13.773 estágios, a tradução antiga tinha 313 colisões
de mapeamento em 43 estágios; após o reparo, zero. Todos passaram pelo lowering
antes/depois; 50 tiveram a tradução alterada (31 vertex e 19 mesh). A regressão
sintética upstream de 89 casos passou de 11 falhas para zero. O banco novo também
teve zero colisões. Isso verifica o defeito do tradutor, sem comprovar a cena renderizada.

Também adaptado o conjunto da issue 302: topologia NVN2 1→pontos SPIR-V 0,
preservando 3→triângulos 4, e coordenadas `(s,t,0,1)` para generics de point sprites
não escritos pelo mesh. Inclui declaração e consumo de PointCoord juntos. O primeiro
banco contém quatro mesh de pontos; dois testes executam setup e emissão de atributos
reais com estado sintético. Os quatro programas reais ainda não foram renderizados.

O workaround de seis locais de oclusão permanece: os contadores atuais ainda usam
amostras sintéticas por draw, não uma consulta real de visibilidade da GPU. Desligar
o workaround para reduzir draws pode esconder novamente a vegetação. Os novos dados
de culling não foram apagados ou modificados para produzir um número maior de FPS.

## Cobertura e compilação dos shaders

| Banco | Programas | Estágios únicos | Compute |
|---|---:|---:|---:|
| Primeiro banco privado | 14.179 | 13.773 | 0 |
| Banco novo recebido | 38.809 | 42.856 | 4.128 |
| Census dos seis arquivos Shader recebidos | 15.504 | 14.726 | 251 |

O banco novo contém 15.852 vertex, 22.356 fragment, 4.128 compute, 20 task e
500 mesh. O log registra 38.809 programas preparados, 46.570 novos, 97 falhas e
10.316 bibliotecas/variantes compute em 252,4 s. São unidades diferentes.
A barra de 116.427 corresponde a 38.809×3 tentativas de variantes de atributos;
não representa 116.427 programas únicos ou pipelines finais de draw.

A coleta agora percorre Shader, Layout2Shader, Lib, Movie e Effect, com leitores
BNSH, BAHS, NDSR e NDVE, deduplicação, spool limitado e publicação atômica.
A identidade de preparação inclui esses locais e os leitores. O census local
foi executado com o dicionário de Pack nos seis arquivos fornecidos: produziu
exatamente os mesmos 15.504 programas e 14.726 estágios da referência no mesmo
subconjunto. Não é alegada regeneração dos 38.809 a partir de pastas não recebidas.

Na preparação compute, o controle do programa vem do banco em disco por um override
TLS com restauração por escopo. Antes, a consulta podia usar uma captura vazia do cache
ao preparar os programas. O teste executa a seleção real sem poluir o cache vivo.

### Cadeia ATOMG.CAS de 32 bits

Seis compute do banco novo eram aceitos pela referência e rejeitados pela base no
opcode nativo 0x3a9. Foi adaptada a cadeia completa e limitada de CAS: lowering,
frontend Maxwell, IR, efeitos laterais, coleta de informações, transformação global
para SSBO e emissão SPIR-V. São 15 arquivos Eden e duas novas operações, com tabelas
ajustadas de 539 para 541 entradas. Larguras não suportadas continuam rejeitadas.
Não foi copiado o passe geral inteiro de memória global.

Auditoria de todos os 42.856 estágios, com emulação tensor ligada e matriz nativa
desligada: AkynoLeyend e referência aceitam os mesmos 42.771 e rejeitam os mesmos 85,
com zero diferenças de status, zero diferenças de saída de lowering e zero colisões
REGMAP. Isso não equivale à emissão de todos os SPIR-V nem a todos os pipelines.
Os 85 casos ainda rejeitados têm limitações também presentes na referência.

O fixture genérico liga 70 unidades reais de IR/backend. Valida quatro módulos
SPIR-V sintéticos, com writes pela tabela de páginas desligados e ligados. Confere
efeito lateral preservado pelo DCE, ordem comparator/value, uma operação por ramo
e retorno da palavra anterior em cada ramo. Não executa os shaders na GPU.
O primeiro teste adicional de page-table assumia erroneamente uma única instrução
estática para dois ramos exclusivos; foi corrigido para conferir cada ramo.

## Mudanças para reduzir trabalho de CPU/GPU

Bindings idênticos deixam de invalidar os descritores. Os bancos driver c0 e c2
usam gerações de SSBO e textura por estágio gráfico; alterações em UBOs sem relação
não os reconstroem. Compute/task/mesh mantêm a geração global conservadora.
`RX_VK_BANK_GEN_OFF` restaura a chave global para comparação. Três testes executam
as funções de produção, incluindo limites inválidos e 5.000 alterações de UBO.

Barreiras completas vazias consecutivas podem compartilhar a mesma sincronização
somente no mesmo command buffer e epoch de trabalho. Um contador atômico global
invalida a deduplicação quando ocorre trabalho, inclusive em outro thread, reset
ou reutilização do command buffer. A otimização fica desligada no replay paralelo;
`RX_VK_BARRIER_DEDUPE_OFF` permite comparação. O fixture Vulkan verifica ambos os
modos e os limites de reutilização. Não foi medido ganho de FPS no jogo.

## FSR 1 e apresentação

Integração dos headers oficiais MIT da AMD, sem alterações, do commit
`a21ffb8f6c13233ba336352bdff293894c706575`. EASU e RCAS são passes separados,
com intermediário RGBA16F e recorte antes do filtro. Nitidez zero pula RCAS.
Downsampling usa Lanczos explicitamente. Não é FSR 3 temporal ou frame generation.
Há seleção no CLI, launcher WPF e menu Insert.

O caminho direto agora fornece obrigatoriamente a view da textura a present_image;
a omissão anterior podia pular o filtro. Criação dos filtros é independente da geração
de quadros. Falhas parciais descartam recursos e restauram dimensões para permitir retry.

O fixture extrai as funções reais de criação, recorte, passes, framegen_scale e blit_crop
e executa os mesmos SPIR-V embutidos na DLL. Onze grupos passaram em llvmpipe
LLVM 20.1.2, com Khronos 1.3.275 e validação de sincronização, em ambos os modos de
deduplicação: zero erros, hazards e avisos. Incluem RCAS ligado/desligado, recortes
positivos/negativos/extrapolados, alocação/view/pipeline falhando, recuperação,
640×360→3840×2160, retorno a saída menor e zero recursos vivos após destruição.
Não houve swapchain/janela real nem confirmação visual no jogo.

## Resolução e memória

O conjunto de saída da referência/PR849 inclui o enum GetCurrentGraphicsScale,
refresh da escala fixa e escala em cache. `native-1440` e `native-4k` pedem
HOS_OUTPUT_RES=1/2 e 100%; o menu salva output_resolution e exige reinício.
O conjunto confere oito âncoras de texto antes de alterar o C gerado. O pool de
305 MiB escala para 687 MiB em 4K e o heap que o contém cresce junto.
As funções envolvidas mantêm registradores no Ctx para permitir esses patches.

Os cinco módulos ExeFS recebidos permitiram gerar privadamente nove funções reais
e aplicar os patches: oito guardas de saída/pool, guarda dinâmica e guarda da escala
em cache passaram. As seis palavras ARM64 da oclusão também conferiram. Esse C e os
módulos não entram nos fontes. Não foi construído o executável completo do jogo.
A identidade de coerência exige um novo host; trocar só a DLL não aplica esses patches.
Alvos efetivos, HUD, filmes, VRAM e nitidez em AMD/NVIDIA continuam sem confirmação.

## Limpeza do projeto

Retirados 250 arquivos sem participação no include graph/build ativo, totalizando
2.824.542 bytes: implementação WebGPU, compilador Suyu duplicado, ferramenta offline
obsoleta, comandos/textos duplicados. Os três headers NVN compartilhados permanecem,
assim como o compilador Eden ativo, fontes necessários, licenças e créditos.
O manifesto `limpeza-043.json` registra caminhos, razões e hashes para revisão.

Vinte e dois comandos opcionais foram movidos para suporte/ com os caminhos rebaseados.
A raiz tem Compilar.cmd, Jogar.cmd, Preparar-Shaders.cmd e Verificar.cmd.
Foram conferidos 46 caminhos literais dos CMDs, sem destino inválido; os executáveis
e SDKs de distribuição ficam fora desta cópia de fontes. Mensagens da CLI apontam
para a nova pasta. O empacotador recusa bancos .bin fora das pastas privadas previstas.

## Estado da validação

A suite Python descobriu 186 casos: 177 passaram, nove foram omitidos por dependências
Windows/PowerShell, zero falhas. A DLL Vulkan Windows x64 foi compilada do zero a
partir de 182 unidades, zero falhas. Na etapa anterior, o runner C# passou nove checks,
a GUI WPF foi publicada e os dois módulos host alterados compilaram; não são novos
testes de interação no Windows nesta continuação.

Ainda faltam execução do AkynoLeyend completo, comparação da mesma cena no hardware,
vegetação integral, FSR visível, resolução efetiva e medição de FPS/frametime/VRAM.
Os arquivos recebidos bastam para a análise atual; não é necessário repetir o envio
dos logs ou do RuntimeId. Esta versão de teste permite obter essa validação; não é uma release estável.
