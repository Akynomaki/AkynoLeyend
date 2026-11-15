# Relatório AkynoLeyend 0.4.2-rc.1

Revisão candidata consolidada em 08/11/2026 (Brasil; verificação técnica em 09/11 UTC). Este relatório distingue defeitos observados, alterações de código, binários produzidos e validação ainda pendente.

## Resultado concreto

O launcher Windows e a DLL Vulkan foram recompilados nesta revisão. A versão PE do launcher é **0.4.2-rc.1**. Os fontes visuais candidatos anteriores agora estão representados na DLL pronta; as alterações do host exigem que o usuário crie um novo EXE a partir da sua própria entrada. A distribuição não contém esse EXE nem dados do jogo.

A execução pública verifica a versão, a identidade dos fontes, a revisão estrutural do host e os hashes publicados. Uma instalação 0.4.0 é recusada com instrução de recompilar. Não se limita a trocar o rótulo do executável antigo. O empacotador também recusa launcher ou DLL que não correspondam às fontes.

**Não foi demonstrado que o crash AMD, a tela preta ou a iluminação estejam resolvidos. Não foi medido ganho de FPS.** Os resultados abaixo tornam o candidato compilado e verificável; não substituem o teste visual e de driver na máquina de destino.

## Evidência recebida e diagnóstico

| Evidência | Constatação | Consequência |
|---|---|---|
| Screenshot mais recente, com 42 FPS | Terreno com padrão escuro repetitivo | FPS e janela aberta não demonstram imagem correta |
| `20261108-221038-988787-15212.zip` | Launcher/runtime `0.4.0-dev.1`, sem `renderer_version`; encerramento zero | A tentativa não demonstra execução dos novos patches do host candidato |
| Mesmo log, 40 avisos registrados de storage buffer não associado | Alguns endereços/contagens são incompatíveis com um buffer válido; o logger limita a repetição | Não é seguro associar memória arbitrária para eliminar a mensagem; não prova que todos os avisos sejam recursos efetivamente usados |
| Pacote Visual Candidato anterior | GUI ainda 0.4.0 e sem DLL candidata válida | Corrigida a diferença entre fontes e binários nesta distribuição |
| Log AMD anterior | `VK_ERROR_DEVICE_LOST`, sem localização conclusiva do comando/shader | Não há base para atribuir o crash exclusivamente ao BC3 ou à exposição |

A hipótese de perda de pequenas texturas escritas só pela GPU é pertinente ao padrão no terreno, mas a correspondência com esta imagem ainda é uma inferência. A [PR593 de duck-paradise](https://github.com/NotRexed/Hookshot/pull/593) documenta esse tipo de perda após descarte; o candidato conserva seletivamente essa categoria, com parâmetro de retenção de 256 MiB e política LRU sob pressão. Esse parâmetro não limita a VRAM inteira nem significa retenção permanente de todo recurso.

## Alterações visuais já existentes nos fontes candidatos e agora compiladas

- `host/nn_fs.c` e header de diretório: tipo de `DirectoryEntry` no offset `0x304`, tamanho em `0x308`, estrutura `0x310`; antes havia leitura incorreta do campo de tipo.
- `host/rx_backend.c`: preservação dos bytes de uploads de texels feitos antes de o renderer iniciar, além dos handles. Há validação do span por upload, incluindo strides; isso não é um teto global de memória.
- `gpu/vk/vk_draw.cpp`: grade do dispatch indireto copiada pela GPU para c0 no momento correto, com barreira transfer→compute. Backport seletivo relacionado à [PR252 de AyyBeeDee20738](https://github.com/NotRexed/Hookshot/pull/252). A própria referência deixa claro que esses reparos não resolvem todas as copas ausentes.
- `gpu/vk/vk_texture.cpp`: retenção seletiva de texturas pequenas finalizadas, escritas uma vez pela GPU, enquanto sua região continua válida.
- Lowering seletivo do tradutor e mitigação opcional de otimização AMD task/mesh preservados da base candidata. Não foi adicionado suporte fictício a opcode desconhecido.
- Patches ARM64 de oclusão são aplicados pelo gerador apenas nos seis sítios conferidos para o build suportado. Não há edição manual do C gerado do jogo.

Essas mudanças pertenciam ao candidato de fontes recebido. Esta revisão não as apresenta como seis consertos novos e independentemente confirmados no jogo.

## Correções novas de coerência e cache

1. `coherence.py` identifica a revisão estrutural do host. Atualizar somente a DLL de um host antigo é bloqueado antes de modificar os arquivos.
2. A CLI de execução exige o build atual por padrão; o botão Jogar da WPF também passa essa exigência explicitamente. A migração automática de nomes não antecede mais essa validação.
3. A publicação do jogo registra `host_revision`, `renderer_version` e `renderer_source_sha256`, além da identidade dos fontes e hashes dos arquivos.
4. `Stream::Payload` mantém a reserva de read-ahead durante a decodificação. Mover o payload transfere a reserva; destruí-lo libera primeiro a alocação e depois os bytes contabilizados. O contador pode sobreviver ao leitor com um payload ainda em uso.
5. O token bucket do pré-aquecimento é compartilhado entre os workers. O limite deixa de ser multiplicado pelo número de threads. Ele controla admissão; não interrompe uma chamada de driver já iniciada nem garante duração máxima por quadro.
6. Os índices 5/6 correspondem a 125/150% na CLI, no menu e no callback do renderer. O host mantém seu controle `HOS_RES_SCALE`. São opções experimentais, não o IPS Max Resolution do emulador.
7. O registro exato de compatibilidade de shader cache preserva o stamp do candidato anterior para a alteração de propriedade dos bytes em `vk_shader.cpp`, sem mudança de IR, ABI ou wire format. Isso não torna caches de outro driver ou emulador intercambiáveis.

Read-ahead limita os payloads reservados da fila, em voo, prontos e entregues ao consumidor. Metadados, leitura sob demanda, IR já decodificado e alocações do driver são categorias distintas. I/O em blocos limita cada operação de arquivo, não a soma de toda a RAM/VRAM.

## O que as referências OpenGL permitem — e o que ainda falta

**Não existe backend OpenGL funcional nesta revisão.** A opção segue indisponível; a CLI não simula sua seleção usando Vulkan. É necessário implementar o caminho de recursos, sincronização, apresentação e tradução compatível dos programas task/mesh usados pelo jogo. Só acrescentar o cache de programas não cria esse renderer.

A [especificação ARB_parallel_shader_compile](https://registry.khronos.org/OpenGL/extensions/ARB/ARB_parallel_shader_compile.txt) define consulta de conclusão e uma sugestão de número de threads. Essa sugestão não é garantia rígida de consumo do driver. Um caminho futuro deve consultar conclusão antes de consultar o resultado final de compilação/link, mantendo as chamadas GL no contexto correto. Isso reduz esperas evitáveis, sem prometer que toda chamada será livre de stalls.

A [ARB_get_program_binary](https://registry.khronos.org/OpenGL/extensions/ARB/ARB_get_program_binary.txt) usa o binário inteiro na obtenção/carga. Dividir o arquivo em blocos não permite injetar partes independentes por `glProgramBinary`, nem elimina a alocação do binário completo. Um desenho limitado precisa de teto separado por binário e rejeição de entradas excessivas. Deve validar `GL_LINK_STATUS` após a carga e recompilar quando rejeitada. Uma mudança de driver pode invalidar o cache; não é correto afirmar que toda atualização obrigatoriamente o rejeitará.

Uma chave futura de cache deve incluir schema, fontes/opções/tradutor, vendor, renderer, versões GL/GLSL, formato binário, comprimento e checksum. [ARB_gl_spirv](https://registry.khronos.org/OpenGL/extensions/ARB/ARB_gl_spirv.txt) não torna automaticamente válido em OpenGL o SPIR-V produzido para Vulkan. Shader substituto genérico também não pode omitir compute/culling essencial sem mudar o resultado.

O estudo MDias v6 não autoriza copiar offsets de outro EXE nem usar seu cache como se fosse desta base. Pré-carregamento e retenção ilimitados contrariam o objetivo de memória limitada; as promessas de zero stutter e percentuais externos não são benchmarks do AkynoLeyend.

## Verificação executada

| Verificação | Resultado | Limite |
|---|---|---|
| Suíte Python/nativa portátil | 152 casos: 143 aprovados, 9 omitidos, zero falhas | Os omitidos dependem de PowerShell/Windows |
| Runner C# | 8 aprovados | Transporte/processos e persistência; não abre a janela WPF |
| DLL Vulkan Windows x64 | 182 unidades configuradas; rodada inicial completa e fechamento incremental final, zero falhas | Link sem driver/GPU |
| Export PE da DLL | `mkwvk_init` conferido | Não confirma funcionamento de uma GPU |
| Quatro unidades host modificadas | `nn_fs.c`, `nn_vi.c`, `hos_main.c`, `rx_backend.c` compiladas para Windows | Objetos isolados; headers auxiliares sintéticos; não é link do jogo |
| Launcher WPF Windows x64 | Publicação autocontida .NET 8, ProductVersion 0.4.2-rc.1 | Compilado em cross-target; janela não executada |
| Cache C++ real com ASan/UBSan | Arquivo, limites, entrega, falhas, encerramento e parser passaram | LeakSanitizer desativado por limitação do ambiente |
| Ruff em módulos novos/selecionados | Aprovado | Não afirma limpeza de todos os fontes históricos/vendor |

O fixture de payload verifica que uma leitura de 64 bytes continua bloqueando nova admissão mesmo após `take()`, inclusive quando o payload sobrevive ao leitor. O teste concorrente de taxa usa oito threads e relógio controlado. O teste do menu compila trechos reais do callback e confere as sete seleções. Os testes de coerência garantem que o build antigo não inicia nem recebe a DLL nova, preservando seus arquivos.

Registros completos desta rodada e hashes estão nos arquivos `resultado-*-0.4.2.txt`, `validacao-0.4.2.json`, `builder/launcher-build.json` e `ferramentas/prebuilt/renderer.json` dentro do pacote.

## Como comparar sem misturar builds

Extraia o pacote completo em pasta nova e crie o jogo pela WPF ou por `Compilar-AkynoLeyend.cmd`. Na primeira comparação, use `Jogar-Visual.cmd` e depois `Jogar-Comparacao.cmd`, fechando o processo entre tentativas. Ambos usam o novo host, 100%, nitidez zero e geração de quadros desligada. O segundo desliga um conjunto de ajustes opcionais, portanto um resultado diferente ainda exige isolar cada um.

Compare o terreno, a copa das árvores, a exposição e a passagem entre áreas na mesma cena. Para desempenho, registre frametime e FPS de simulação no mesmo percurso, resolução e driver; separe a primeira preparação da rodada com cache já aquecido. Observe o orçamento de VRAM, não apenas a memória alocada. Em caso de falha, o ZIP completo da mesma tentativa permite conferir EXE, DLL e versão realmente utilizados.

Pendentes: execução Windows/WPF e DACL no computador de destino; confirmação visual AMD/NVIDIA; reprodução/localização do device lost; benchmark; OpenGL real; Max Resolution IPS/Dynamic FPS equivalentes aos de outro emulador; FSR3/DLSS/LSFG. Esses itens não foram marcados como concluídos.

## Identidade e continuidade

A entrada desta revisão é `AkynoLeyend-0.4.1-Visual-Candidato-Windows (1)(1).zip`, SHA-256 `207094fa6e26f0d539e0f22aa6d3b8cb3bd664be9bcc0c5ad2f00f5af9a51e11`. Foi comparado também o fonte fornecido Hookshot 2.0.5. Os autores originais e licenças continuam preservados. As mudanças desta revisão contra o candidato estão em `patches/0.4.2-coerencia-cache.patch`.

Há somente um pacote Windows atual. Scripts antigos 0.4.1 foram arquivados como texto em `creditos/historico/0.4.1`; não devem ser usados para sobrescrever o novo conjunto. O EXE antigo não foi reaproveitado com um nome/versão diferentes.
