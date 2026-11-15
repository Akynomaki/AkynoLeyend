> HISTÓRICO: este documento descreve uma revisão anterior. O estado atual está em `../README.md` e `Relatorio-AkynoLeyend-0.4.2.md`.

# Relatório AkynoLeyend 0.4.0-dev.1

Data: 8 de novembro de 2026. Entrega experimental para Windows x64. Este documento descreve o código e os binários entregues; os relatos anteriores ficam em `creditos/historico/HANDOFF-0.3.9.md`.

## Resultado e limites

O launcher AkynoLeyend foi recompilado com visual preto/dourado, navegação lateral, controles gráficos persistidos e ferramentas de atualização, preparação e diagnóstico. A DLL Vulkan genérica foi compilada para Windows e ligada com o export `mkwvk_init` preservado. O pacote não contém EXE recompilado do jogo nem dados do jogo.

Foram incorporados a espera de resultados da GPU usados pela CPU e backports que reduzem consultas/bindings/trabalho de estado no backend. A imagem e o FPS **não foram medidos nesta versão numa GPU física**. Não se pode anunciar os flashes, a renderização preta ou o crash AMD como resolvidos.

**OpenGL não foi implementado.** A opção aparece indisponível no launcher; a CLI recusa `--backend opengl`. Implementar um seletor não produziria um backend gráfico funcional.

## Crash AMD recebido no fim do trabalho

O TXT recebido tem 2.368.067 bytes e 18.039 linhas. A análise abaixo usa esse arquivo, não os prints das tentativas antigas.

| Evidência | Leitura |
|---|---|
| GPU e driver | AMD Radeon RX 9060 XT; 26.10.1, compilador LLPC; Vulkan 1.4 |
| Contexto | Caminhos da instalação 0.3.9; mais de 35 mil apresentações antes da falha |
| Última operação reportada | `submit 248704 failed (-4)`; `GPU_FATAL device_lost`, saída 70 |
| Última amostra de VRAM | 9.992 MB usados / 11.557 MB permitidos; 2.299 MB livres dentro dos blocos do alocador |
| Texturas na última amostra | 5.073 MB, orçamento 6.144 MB, 2.450 texturas |
| Amostra recente mais alta | 10.600 MB usados / 11.576 MB permitidos |
| Pré-compilação inicial | 0 programas e 0 pipelines construídos nesse trecho de startup |
| Compilação durante a sessão | 485.676 ms acumulados em pipelines; alguns picos de vários segundos |
| Programas omitidos | 11 redes de upscale de filme deliberadamente não traduzidas nessa placa; o log explica essa omissão |
| Identidade incompleta | O TXT sozinho não inclui os hashes do EXE/DLL do `execucao.json` |

`-4` corresponde a `VK_ERROR_DEVICE_LOST`, distinto de `VK_ERROR_OUT_OF_DEVICE_MEMORY (-2)` na API Vulkan. A memória disponível na última amostra não prova ausência de pressão em outros momentos, e tampouco prova que falta de memória foi a causa. A falha pode decorrer de uma operação anterior na fila; o último submit não identifica o shader causador.

Não há no arquivo checkpoint de conclusão da GPU ou endereço de falha que permita apontar uma instrução. Os 11 programas de redes omitidas não devem ser descritos como 11 crashes do compilador. Este crash também não é o `PermissionError` de leitura do EXE, nem permite concluir que o antigo `0xc0000005` tem a mesma origem.

### Mudanças feitas a partir desse crash

- `cpu_breadcrumbs.h`: anel limitado a 64 entradas, protegido por mutex, com sequência, tipo de operação, chave e quadro. Só é ativado em sessões de suporte/Compatibilidade.
- A falha imprime `CPU_BREADCRUMB` mesmo sem os checkpoints específicos de NVIDIA. O texto diz explicitamente que são operações gravadas pela **CPU**, não prova de conclusão na GPU ou do shader responsável.
- Perfil `compatibilidade`: orçamento de texturas 4096 MiB, mirrors 512 MiB, dois workers de compilação; sem limite menor de dimensões/mips. É uma mitigação comparativa, não um teto global de VRAM ou correção comprovada.
- `Jogar-Compatibilidade.cmd` liga a coleta; o mesmo perfil na GUI liga o registro de suporte. Logs e manifesto permanecem associados à tentativa.

Não foram aplicados aumento de TDR, limpeza indiscriminada de caches, desativação automática de BC3 ou descarte de texturas renderizadas que podem conter a única cópia válida de dados.

## Luzes piscando, objetos pretos e BC3

O vídeo fornecido foi examinado quadro a quadro. Ele tem 583 quadros decodificados em aproximadamente 12,14 segundos de vídeo; a informação nominal 240/1 do contêiner não é o FPS real do jogo. Os quadros em torno de 0,9–1,2 s alternam cenário iluminado e silhuetas pretas de personagem/terreno. Uma média de brilho sozinha não basta para atribuir a causa à exposição.

As capturas mostram tela preta também nos modos sem BC3 e ASTC por CPU. São evidência contra tratar BC3 como causa única já comprovada, embora as tentativas não constituam um teste controlado com estado de cache e cena idênticos. O perfil 8 GB renderiza uma das cenas; Streaming chega a desenhar cenário com materiais/objetos ausentes. O contador de FPS sobre fundo preto não comprova renderização correta.

Os dois ZIPs anteriores de diagnóstico NVIDIA terminaram com saída zero e sem `GPU_FATAL`; isso não exclui o defeito visual filmado. Não devem ser usados como prova de que o crash AMD foi reproduzido ou resolvido.

### Sincronização de exposição incorporada

Backport seletivo da [PR296 de evilmfkr/EvilBoyce](https://github.com/NotRexed/Hookshot/pull/296): registra, por página guest, o timeline da última escrita de GPU copiada para a memória que a CPU lê. `invalidate` alcança a fila de replay, consulta novamente o timeline mais recente e espera sua conclusão antes de entregar os resultados à CPU. Isso cobre a leitura/reset do medidor de exposição e preserva a exclusão de palavras escritas pela CPU da correção 0.3.9.

O teste usa as funções reais extraídas dos fontes e simula a fila publicando uma escrita mais nova durante a espera. Ele passou; o resultado visual na máquina afetada continua pendente. Gamma, intensidade da iluminação e neblina não foram arbitrariamente substituídos.

## Otimizações do renderizador

| Origem | Alteração |
|---|---|
| PR300, SkippySteve | Uma busca do handle de textura por binding; contadores opcionais fora do caminho comum |
| PR327, SkippySteve | Reutiliza o stream de vértices até endereço, tamanho ou geração do buffer mudar; criação de mirror invalida o estado |
| PR362, SkippySteve | Reutiliza o estado dinâmico quando os valores necessários são iguais |
| PR416, SkippySteve | Máscara dos render targets amostrados evita varrer todas as texturas no teste de hazard, preservando as barreiras |
| Implementação local | Cache de 256 leituras pequenas, até 16 bytes, exclusivamente quando todos os bytes vêm de capturas imutáveis |

O cache local ainda executa `host->gpu_read` em toda leitura, mantém erros do host e nunca memoriza regiões vivas/parcialmente capturadas. A chave inclui endereço guest, tamanho, submissão, geração e contador de capturas retiradas. Contadores diagnósticos são agregados em lotes de 4096 leituras, reduzindo duas operações atômicas por palavra no caminho anterior.

O teste compara 40 mil leituras com uma referência sem cache, incluindo mudanças de captura, endereços remapeados, fronteiras de página, áreas parciais/vivas e falhas do host. Também roda com o cache desligado. Isso verifica equivalência do caminho testado; não mede ganho de FPS da aplicação.

## Max Resolution, Dynamic FPS e OpenGL

O fork MDias v6 fornecido e sua página de releases foram estudados como referência. Max Resolution nos patches de emulador modifica o executável ARM64 original; os endereços IPS não podem ser copiados para o EXE x64 produzido por esta base. Dynamic FPS também modifica a lógica/estado original e precisa ser comparado com o relógio já implementado no runtime.

O launcher agora expõe os caminhos nativos existentes: Auto ou 100/75/67/50% de escala interna; tempo real ou por quadro. O runtime preserva 30 passagens iniciais do caminho dinâmico antes da escala fixa para inicializar os campos que a renderização 3D usa. O teste do menu verifica que opções explícitas prevalecem sobre o INI e que `framegen=0` realmente desliga a opção.

100% não significa automaticamente a resolução 2560×1600 do monitor: a escala interna e a resolução de saída são diferentes. As imagens “sem/com” mostram diferença de nitidez aparente; câmera/folhagem e animação variam, e não há um benchmark pareado que permita quantificar desempenho.

O arquivo `src/shader_recompiler/backend/glsl/glsl_emit_context.cpp:322` do ZIP MDias v6 lança `NotImplementedException` para programas GLSL task/mesh. O renderizador do emulador ainda depende de suas interfaces de memória, consultas e comandos, diferentes do runtime NVN desta base. Adicionar OpenGL exige implementar/adaptar esses caminhos e validá-los; não foi feito nesta entrega.

## Identidade, interface e atualização

Arquivos ativos: `AkynoLeyendBuilder.exe`, `AkynoLeyend.exe`, `AkynoLeyend.dll`, `AkynoLeyend_opts.ini`, `AkynoLeyend-build.json` e caches com prefixo AkynoLeyend. Orquestração em `akynoleyend/`; GUI em `builder/AkynoLeyendBuilder`.

A migração aceita somente instalações locais reconhecidas 0.3.6–0.3.9, build e0f3ccfa e hashes válidos. Recusa PE diferente de AMD64/PE32+, assinado, truncado ou com literais em seções inesperadas. Substitui literais completos de DLL/INI, de mesmo comprimento, em dados somente de leitura; não modifica instruções. O manifesto novo é publicado por último. Falha nessa publicação remove os novos arquivos e preserva o build original. Após sucesso, originais ficam em `backup-identidade`.

A atualização isolada da DLL preserva a ABI pública e também faz rollback de DLL/manifesto se a publicação falhar. Arquivos de acesso negado são diagnosticados antes de executar; o auditor e o reparo continuam aceitando nomes antigos quando a migração ainda não conseguiu ler o EXE. O reparo mantém a lista fixa de arquivos, SID do usuário, conferência de hashes e recusa de links/junções.

O launcher possui páginas Início, Gráficos, Ferramentas e Créditos; tema preto/ouro, título dourado e ornamentos geométricos/folha. Mantém a seleção de entrada, idioma, progresso, logs, cancelamento e execução por `ArgumentList`. As opções são salvas atomicamente; nenhum comando shell é montado a partir dos caminhos do usuário.

TXT e documentos antigos foram reunidos em `creditos/historico`. Nomes legados permanecem em compatibilidade, comentários, atribuição e alguns identificadores internos de ABI/cache. Não foram apagados os copyrights/licenças de terceiros.

## Validação executada

- Suíte Python: **124 testes descobertos; 115 passaram, 9 omitidos, zero falhas**. Sete omissões são checks de PowerShell ausente; duas dependem das APIs Windows/DACL e do parser PowerShell. Inclui fixtures nativas e quatro regressões dos backports.
- C#: **7 checks passaram**, incluindo configurações gráficas, argumentos, UTF-8, duas saídas simultâneas e cancelamento; execução do runner no Linux com processo filho real.
- DLL Vulkan: **182 unidades C/C++** compiladas para Windows x64 na passagem limpa, zero falhas; relink incremental após formatação de headers. Export público conferido no PE.
- GUI: publicação WPF Windows x64, .NET 8.0.33 autocontido, pelo SDK 8.0.427; compilação de XAML/C# concluída. A janela não foi executada nem inspecionada no Windows.
- Ruff: verificações passaram em `akynoleyend`, `tests/test_release040.py` e `tools/make_distribution.py`. Não se afirma limpeza de estilo de todos os testes históricos/vendor.
- Distribuição: os pacotes passam por conferência de CRC, nomes sem colisão no Windows, identidade da DLL e exclusão de jogo/saves/cache/diagnósticos pessoais.

Hashes da DLL/GUI, registros resumidos e origem dos backports estão em `docs/validacao-0.4.0.json`, `ferramentas/prebuilt/renderer.json` e `upstream.json`.

## Verificação na máquina afetada

1. Aplique o ZIP de atualização na pasta existente e rode `Atualizar-AkynoLeyend.cmd`; preserve o backup, `work`, `jogo` e a RomFS.
2. Prepare shaders uma vez. Inicie a cena no Original e registre se personagens, chão, folhagem e iluminação renderizam corretamente.
3. Repita a mesma rota no Compatibilidade, com resolução, geração de quadros e opções idênticas. Separe cache frio de cache já aquecido.
4. Se houver device lost, compartilhe o ZIP completo gerado nessa tentativa, incluindo `execucao.json` com hashes; anote ação/cena/tempo e se houve troca de foco.
5. Compare FPS e tempos de quadro depois que ambas as tentativas estiverem aquecidas. O número da sobreposição com geração de quadros não substitui FPS real de simulação.

Pendentes: reproduzir/localizar o crash da RX 9060 XT, validar os flashes/renderização preta em AMD/NVIDIA, medir FPS/VRAM e implementar OpenGL. Sem esses testes não há base para declarar todos os problemas resolvidos.

## Fontes primárias

- [Vulkan — VkResult](https://docs.vulkan.org/refpages/latest/refpages/source/VkResult.html).
- [Hookshot PR296](https://github.com/NotRexed/Hookshot/pull/296), [PR300](https://github.com/NotRexed/Hookshot/pull/300), [PR327](https://github.com/NotRexed/Hookshot/pull/327), [PR362](https://github.com/NotRexed/Hookshot/pull/362), [PR416](https://github.com/NotRexed/Hookshot/pull/416).
- [Eglantine MDias — releases](https://github.com/ProfMPPDias/eglantine_NX2_forkMDias/releases), fonte v6 fornecida pelo usuário.
- Dois ZIPs de diagnóstico NVIDIA, vídeo, capturas e TXT AMD fornecidos pelo usuário; os arquivos brutos não são redistribuídos nestes pacotes.
