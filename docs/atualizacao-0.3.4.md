# Atualizacao 0.3.4

## Evidencias recebidas

Foram analisados o video Hookshot 2026-11-07 09-56-58.mp4, os logs de build e as duas tentativas registradas pelo launcher 0.3.3. As analises nao exigiram dados do jogo, chaves ou saves.

| Evidencia | Conclusao e limite |
|---|---|
| Mesmo SHA-256 do EXE/DLL; abertura normal falha, teste com RomFS Z:\\ termina com codigo 0 apos cerca de 17 minutos | Caminho de acesso aos recursos diferencia as duas tentativas; nao e um simples caso de VRAM esgotada |
| Raiz RomFS de 160 caracteres; mais de 600 caminhos relativos distintos no trace excedem os 98 bytes que restam no buffer antigo | Truncamento demonstravel no filesystem, inclusive no arquivo LocationalLightMgrInitializeParam ligado ao ponto da falha |
| audio: no output device; GetAudioDeviceOutputVolume aparece como import nao implementado | Falha de saida confirmada; o stub tambem nao fornecia retorno float valido. O mixer ja convertia o sink de seis canais para stereo, portanto a quantidade de canais do jogo nao prova um problema de 5.1 no Windows |
| slow dispatch 2482.5 ms; criacao de pipeline domina o tempo | Parte das pausas vem da compilacao do driver; caches estavam frios no inicio desta tentativa |
| Interpolacao registrada em 1x | O video nao demonstra custo/artefato de geracao de quadros adicionais |
| 971 programas, zero falhas de traducao ao fim | Folhas ausentes nao podem ser tratadas apenas como shaders que falharam em compilar |
| compile(2).log: compilacao em 108 segundos, zero falhas | O cache ja evitou repetir boa parte do trabalho; esse e o tempo da etapa de compilacao, sem prometer o mesmo em outro PC |

Os rastros vistos na camera sao compativeis com reconstrucao temporal incorreta, mas o video nao determina sozinho a causa. A gravacao usa 240 quadros/s; isso nao equivale ao FPS do jogo. A faixa AAC tem sinal baixo e nao foi usada como prova de audio do jogo funcionando.

## Alteracoes

### Filesystem

host/nn_fs.c passa a usar buffers de 4096 bytes no lugar de MAX_PATH. host/path_join.h recusa overflow. host/win_path.c normaliza caminhos absolutos para as APIs UTF-16 estendidas, inclusive UNC, e preserva o erro Win32. OpenFile registra erros reais quando relevantes. Nao exige administrador, mudanca no registro ou unidade DOS no fluxo normal.

O escopo e o acesso aos arquivos do filesystem guest; outros caminhos de ferramentas/carregamento de DLLs continuam sujeitos aos limites anteriores. O limite interno de 4096 bytes e explicito, e componentes de diretorio ainda respeitam as estruturas Win32 usadas pelo runtime. Isso nao e suporte ilimitado a qualquer nome de arquivo Windows.

### Audio

host/audio_wasapi.c implementa saida compartilhada PCM16 stereo 48 kHz. O motor Windows faz a conversao para o formato do endpoint. O mixer usa WASAPI primeiro, e waveOut como alternativa; no caminho antigo tenta o mapper e dispositivos enumerados. Falha ou desconexao gera nova tentativa em dois segundos, no thread de audio. HRESULT/MMRESULT sao registrados. HOS_AUDIO=0 continua sendo respeitado quando selecionado explicitamente no runtime.

GetAudioDeviceOutputVolume e implementado como HLE, com retorno float em v0; SetAudioDeviceOutputVolume e o ganho final compartilham o mesmo valor limitado a [0,1]. O gerador passa a excluir o stub correspondente. Nenhum codigo gerado do jogo foi editado manualmente.

A opcao CLI --audio-backend permite auto, wasapi e waveout. A interface usa auto. Nenhuma dessas opcoes modifica configuracao de som do Windows.

### Movimento e desempenho

O perfil opcional nitido seleciona RX_VK_TAAU_KEYS=fd029a317a9a4b94 e HOS_DYNRES=0. Expoe a alternativa espacial que ja existe no Hookshot, sem habilitar o clamp de historico que pode borrar movimento. Na NVIDIA do log, permite comparar com a rede temporal; em placas AMD que ja usam essa alternativa, a diferenca pode ser apenas a resolucao fixa. Pode aumentar serrilhado e custo de pixels. O perfil Original nao e substituido.

Nenhuma mudanca de exposicao ou traducao de shaders foi feita nesta entrega. A identidade do tradutor foi comparada byte a byte com 0.3.3 e permanece igual. Os caches de programa e pipeline nao sao apagados. A reutilizacao depende da GPU/driver e das configuracoes compativeis. O primeiro encontro com novas pipelines ainda pode travar o frame; esperar compilacao nao elimina seu custo, e pular desenhos nao foi usado como otimizacao.

Jogar-Suporte.cmd ativa apenas estatisticas de audio e slow-frame log a partir de 25 ms, e coleta ao encerrar. O filtro anterior descartava frames de 500 ms ou mais; agora tambem inclui esses eventos. Nao ativa validacao Vulkan, trace de arquivos nem alias de unidade. Cada tentativa guarda copias limitadas a 64 KiB de hookshot_options.ini antes/depois, sem editar o arquivo. O menu do proprio jogo continua podendo salvar opcoes quando o usuario as altera.

## Uso e pendencias

A atualizacao e cumulativa para 0.3.2/0.3.3. Extraia sobre a instalacao existente, mantenha o nome da pasta/work/jogo e repita Criar com a mesma entrada/destino. Teste primeiro pelo launcher Original; depois compare Jogar-Nitido.cmd na mesma cena. Para destinos personalizados use --out.

Folhagem ausente continua reportada na origem: https://github.com/NotRexed/Hookshot/issues/35. Escuridao e sombras piscando tambem nao foram demonstradas como corrigidas. A nova abertura e o audio precisam de confirmacao no computador de destino. Os testes e suas limitacoes estao em validacao.md.
