# Ocarina 0.3.9 — atualização e continuidade

Data: 08/11/2026. Motor/scripts: **0.3.9-dev.1**. Interface WPF distribuída: **0.3.2-dev.1**, sem republicação. Windows x64, renderizador Vulkan. Este documento complementa o histórico 0.3.8; não houve execução do jogo nem teste físico de GPU neste ambiente.

## Resultado concreto

Foi compilada uma nova DLL Vulkan genérica e preparada uma atualização que preserva o EXE, a imagem, os objetos C e os saves da instalação atual. Ela incorpora correções de sincronização e iluminação identificadas nos relatórios, leituras de shader antes ausentes, uma otimização de consultas de uniformes e tratamento explícito de perda do dispositivo.

O pacote **não comprova** que toda tela preta, piscada ou queda de FPS tenha desaparecido no PC do usuário. O teste necessário agora é a mesma rota com essa DLL, comparada pelos hashes/versões internos. Não iniciar outra compilação completa para atualizar esse build 0.3.8.

## Evidência dos relatórios recebidos

Foram examinadas 14 execuções, incluindo os quatro ZIPs anteriores, os novos ZIPs e as entradas completas recuperáveis de diagnostico-2kqohj7x.tmp. Este último era um ZIP incompleto; execucao.json e erros.log estavam completos e foram recuperados sem usar o mapa incompleto.

As sessões identificam **RTX 5070 Ti Laptop, driver NVIDIA 617.42**, launcher 0.3.8-dev.2 e a mesma DLL 0.3.8, mesmo dentro de pasta chamada 0.3.7. Não são os testes AMD 0.3.5 do relatório anterior.

| Execução | Configuração | Evidência |
|---|---|---|
| 07/11 22:15:48, TMP recuperado | Original, CPU/RGBA8 | Device lost; marcador próximo de 53caac5f38279735 |
| 07/11 22:17:47 | Original, RGBA8 | Trecho curto sem device lost registrado; usuário fecha após cerca de 40 s |
| 07/11 22:18:35 | Original, caminho curto | Device lost no mesmo ponto de compute |
| 07/11 22:19:27 | Original, sondagem de luzes | Device lost no mesmo ponto de compute |
| 07/11 22:22:58 | Perfil 8 GB | Cerca de 15 min sem device lost registrado; uso máximo reportado de 6.920/11.176 MB |
| 08/11 00:17:10, 00:18:44 e 00:26:21 | Original, CPU/RGBA8 | Device lost no mesmo ponto de compute |
| 08/11 00:28:59 | Original, RGBA8 | Device lost no mesmo ponto de compute |
| 08/11 00:30:53 e 00:31:50 | Original, auto; direto e caminho curto | Device lost no mesmo ponto de compute |
| 08/11 00:32:56 | Preparação de shaders seguida de jogo | 14.179 programas em 78 s, depois device lost no mesmo ponto |
| 08/11 00:35:44 | Original | Interrupção 0xC000013A durante início; não rotular como o mesmo crash GPU |
| 08/11 00:36:16 | Original, sondagem de luzes | Device lost no mesmo ponto de compute |

Onze das 14 execuções contêm perda do dispositivo; as onze apontam o último checkpoint para **53caac5f38279735**. O checkpoint localiza o trabalho próximo da falha, não prova por si só qual instrução causou o reset. As cópias de pools imediatamente anteriores e o código de atualização da tabela sustentam a correção escolhida.

Os logs continuavam a registrar atividade depois da falha e retornavam zero quando a janela era fechada. Isso explica o FPS ativo sobre uma tela preta e os diagnósticos que aparentavam sucesso. Não usar esses FPS posteriores como desempenho válido.

O defeito também ocorre com BC3 desativado e com decode ASTC na CPU. BC3 não explica sozinho essas perdas de dispositivo. O uso de VRAM amostrado nas falhas frequentemente era 7–9 GB de orçamento 11.176 MB; não há prova de que todos esses casos sejam falta de VRAM.

A auditoria de acesso de 00:16:44 já lê manifesto, EXE, DLL e image.bin. O bloqueio anterior de permissões não explica essas execuções que já chegam ao Vulkan. Preservar o reparo de staging da 0.3.8-dev.2; não repeti-lo como solução para device lost.

## Builds novas estudadas

**HookshotBuilder(6).zip:** os trechos de tabela de páginas e de leituras estreitas conferem com o snapshot upstream usado, normalizando CRLF. A integração foi seletiva; não foi substituída toda a ABI/runtime por uma versão incompatível.

**Ocarina-Setup-0.2.7-windows.zip:** foram examinados instalador, README e os caminhos Vulkan de memória/texturas/pipelines. Pontos úteis: reaproveitamento incremental, preparação de chaves e tratamento de falha do driver durante criação de pipeline. Nosso fluxo mantém atualização só da DLL, caches locais e preparação limitada. O journal com retry NOOPT/skip desse outro runtime continua **não integrado**: ele trata crash durante compilação de pipeline; os casos aqui são perda durante execução no compute 53caac5f. Não transplantar o runtime C desse projeto para o ABI Hookshot C++.

O SCSKiller foi consultado na documentação oficial: o escopo publicado é DirectX 12 e DirectX 11/NVIDIA. Não há integração pronta demonstrada com o banco próprio SPIR-V/NVN do Hookshot. O aquecimento nativo é o caminho entregue; não foi acrescentada injeção ou limpeza global de cache do driver.

## Alterações implementadas

1. **Tabela de endereços ordenada pela GPU.** Em vk_memory.cpp, mudanças durante a gravação ficam em runs; o último valor por página prevalece. vk_texture.cpp descarrega esses runs no upload command buffer depois das cópias dos mirrors, antes da barreira e do comando que usa os endereços. Updates limitados a 64 KiB e buffer com TRANSFER_DST. A correção local de flush em memória não coerente foi preservada.
2. **Contadores CPU preservados.** O replay registra palavras de REPORT_COUNTER como pertencentes à CPU. Os writebacks dos mirrors recortam essas palavras, evitando restaurar flags antigas que controlam limpeza/iluminação. Mantido o mecanismo upstream; não se omitem os passes de luz.
3. **Leituras globais de 8/16 bits.** Os quatro emitters usam a busca já existente de palavra de 32 bits e extraem byte/halfword com extensão de sinal adequada. O log de preparação mostrava LoadGlobalS16 não implementado em shaders mesh. Isso muda a tradução e exige nova identidade de cache.
4. **Consultas de uniformes.** A faixa sem atualização sobreposta é lembrada. Leituras repetidas nessa faixa não percorrem a lista novamente; append/prune invalidam o cache por epoch. Foram deixados de fora caches adicionais de palavras/cópias de versões posteriores, cujas dependências não pertencem a esta base.
5. **Falha GPU encerra corretamente.** Waits, timeline, submits, acquire e present passam a verificar device lost; há marcador GPU_FATAL, tentativa de checkpoints e saída 70. O contador UINT64_MAX não é tratado como conclusão de todo o trabalho pendente. A saída terminal evita continuar writebacks e gravar caches em teardown após perda do dispositivo.
6. **Launcher reconhece falhas antigas.** Um leitor em blocos de 64 KiB encontra os marcadores explícitos, mesmo cruzando blocos. O código real fica em process_exit_code; se um renderer antigo retornou zero após device lost, exit_code passa a 70. O ZIP inclui a identificação do erro. Mensagens genéricas sobre prevenção de device lost não bastam para classificar a falha.
7. **Preparar sem entrar na partida.** O modo preparacao define RX_VK_PREPARE_ONLY. Banco ausente/inválido retorna 71; com banco válido, prepara, salva o cache do driver e encerra antes de gameplay. Depois o usuário executa Jogar. Ainda pode existir janela/console de preparação: não anunciar como o modo headless oficial completo, que exigiria mudanças de host/CLI diferentes.

Os backports correspondem aos commits upstream [9bb52a94](https://github.com/NotRexed/Hookshot/commit/9bb52a94d8a542d37edeaf86e4a128a9848fb261), [c3459dc2](https://github.com/NotRexed/Hookshot/commit/c3459dc2822326434b5107222a70095494fe497d) e ao caminho de tabela introduzido antes deles. São mudanças de fonte aplicadas e compiladas; resultados físicos relatados em comentários upstream não são testes feitos neste ambiente.

## Compatibilidade e cache

O header público vk_api.h é idêntico byte a byte ao pacote 0.3.8: atualização isolada permitida nos builds locais listados 0.3.6-dev.1, 0.3.7-dev.1, 0.3.8-dev.1/dev.2 e 0.3.9-dev.1, com build ID suportado e hashes válidos. EXE/imagem/saves não são trocados por esse comando. A versão do EXE fica preservada, com renderer_version separada.

O novo stamp do tradutor é **2fd6984aaeff3c88**, diferente de 7d16d3d712a683ce. Não forçar reutilização do cache traduzido antigo: os emitters mudaram. O banco privado HKSEED01 e os objetos C são outros artefatos; não precisam ser apagados nem reextraídos por isso. O banco local pode ser reaproveitado pelo preparador quando sua identidade confere.

Limites de leitura/entrada do preparador e do cache Streaming foram mantidos. Eles não são teto global de RAM/VRAM nem garantem zero stutter; variantes de estado e trabalho novo ainda podem exigir criação de pipelines durante a partida.

DLL SHA-256: **8e440ce8cbf3a061c63f90e646693678b5f65946641c4680870fb39904f11f58**.

Fingerprint do renderer: **b5e9d61ecfd48d3996aab1a8668b49ae6acd814154e853f116c5fe4e2578238b**.

## Validação

- 112 testes descobertos: **103 passaram, nove omitidos, zero falhas**. Os nove dependem de Windows/PowerShell ausentes aqui.
- 182 unidades Vulkan compiladas para Windows x64; DLL ligada e export mkwvk_init conferido. Primeira compilação: 47,863 s neste host. Repetições posteriores recompilaram somente a unidade alterada e religaram a DLL. Não confundir esses segundos com o build do jogo no PC do usuário.
- Fixtures C++ executam os próprios trechos de tabela, recorte de contadores e emitters estreitos, com APIs/operandos simulados: última escrita vence, conteúdo antigo permanece até o comando, janela de 12 GiB, chunks até 64 KiB e leituras com/sem sinal em milhares de combinações.
- Teste do cache de uniformes verifica 10.000 consultas repetidas sem novo acesso à lista e invalidação após mudanças.
- Processo filho real confirma que saída zero não esconde perda do dispositivo. Handler nativo extraído é executado e termina em 70 antes de atexit. O startup extraído confirma preparação sem entrar em gameplay e recusa de banco ausente.
- Testes existentes de hash, rollback, staging e publicação continuam passando.

Não foram testados aqui driver/GPU físico, áudio físico, janela WPF, reparo UAC nem visual final do jogo. Compilar e testar fixtures não demonstra ausência de flashes no hardware.

## Compilação e vídeo fornecidos

O compile-summary.json real registra **393 unidades, dois jobs, 393 compiladas, zero cache hits e zero falhas**, em **2.045,508 s** (cerca de 34 min). O manifesto registra cerca de 42 min no fluxo total. É uma compilação fria real, não evidência de que o cache incremental falhou numa atualização. Para esta entrega, a troca da DLL evita repetir esse trabalho.

O vídeo do Drive é H.264/AAC, 2304×1440, aproximadamente 13 min 38 s e 5,34 GB. Foram extraídas e inspecionadas amostras em 30 s, 90 s e 780 s; mostram interior e floresta renderizados, com contadores visíveis de 59, 56 e 60 FPS. Isso não é uma análise quadro a quadro nem um benchmark médio. Outras amostras não produziram quadros válidos pelo streaming. Não usar esse vídeo anterior como prova visual da DLL nova; artefatos de movimento/folhagem ainda exigem comparação na mesma rota.

## Instalação e próximo teste

1. Fechar jogo/launcher. Copiar o conteúdo de Ocarina-0.3.9-atualizacao.zip para a pasta existente de manage.py; preservar work, jogo, entrada e saves. O nome antigo da pasta pode permanecer.
2. Executar Atualizar-Renderizador.cmd e conferir sucesso. Não clicar Criar nem iniciar outro build completo para esse update compatível.
3. Executar Preparar-Shaders.cmd uma vez. A primeira tradução com novo stamp pode demorar; no fim o processo termina e confirma a preparação.
4. Executar Jogar.cmd, perfil Original, na mesma rota. Frame generation desligado para medir FPS base. Manter resolução/opções/câmera iguais ao comparar.
5. Só se necessário, comparar Jogar-8GB.cmd; ele reduz texturas e não deve ser descrito como qualidade idêntica. Guardar os ZIPs das novas tentativas com os hashes correspondentes.

## Trabalho que permanece

- Confirmar no PC do usuário se a falha do compute 53caac5f desapareceu e se as piscadas diminuíram. Se ainda ocorrer, analisar o novo último checkpoint e endereço; não presumir que todo device lost tenha a mesma causa.
- Comparar sombras/fog/temporal upscale em movimento. A correção dos contadores não promete corrigir todo borrão, barra lateral ou flash claro.
- Medir CPU/replay e tempos de shader após o cache aquecido. A otimização de uniformes evita trabalho repetido, mas não garante 60 FPS em cenas cheias.
- Avaliar se falhas reais de compilação AMD justificam um journal persistente e retry NOOPT, com identidade de GPU/driver/opções. Isso continua pendente; não anunciar o código do outro projeto como integrado.
- GPUs sem mesh shaders, como RX 580/algumas gerações antigas, continuam exigindo um caminho compatível próprio. Não extrapolar testes em RTX 5070 Ti para suporte completo a elas.
- Interface WPF, Linux/AppImage e atualizador oficial continuam fora desta entrega. Preservar licenças e não distribuir jogo, bancos privados, caches, saves ou mapas do jogo.

Referências adicionais: [Vulkan — dispositivo perdido](https://docs.vulkan.org/spec/latest/chapters/devsandqueues.html), [vkGetSemaphoreCounterValue](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetSemaphoreCounterValue.html), [SCSKiller — escopo oficial](https://github.com/BlueHeisenberg/SCSKiller).
