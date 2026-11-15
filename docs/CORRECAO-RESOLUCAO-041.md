> HISTÓRICO: este documento descreve uma revisão anterior. O estado atual está em `../README.md` e `Relatorio-AkynoLeyend-0.4.2.md`.

# Por que Max Resolution não aparecia ou não era aplicado

## Estado real

1. A interface WPF em `builder/AkynoLeyendBuilder` tem opções 125/150 nos fontes,
   mas o `AkynoLeyendBuilder.exe` **incluído** foi compilado na versão 0.4.0,
   antes dessas alterações. Apenas extrair o ZIP não recompila esse programa.
2. Os comandos `Jogar-MaxResolucao-125.cmd` e `Jogar-MaxResolucao-150.cmd` usam
   `--resolution 125|150` no Python atualizado e solicitam `HOS_RES_SCALE`
   ao host nativo. Isso NÃO é o patch de Max Resolution do emulador, nem FSR/DLSS.
3. O menu Insert do renderizador dispõe somente de Auto/100/75/67/50 e
   exibe 100 quando o host recebe 125/150. Essa leitura do menu **não prova**
   se a escala maior foi ou não aplicada. Tampouco indica a resolução final da janela.
4. O host recompilado a partir desses fontes passa a escrever no `saida.log`:
   `vi: fixed scale requested: 1.250` (ou 1.500) e, depois do aquecimento,
   `vi: fixed scale active: 1.250 ... (CPU-side)` (ou 1.500).
   Isso confirma a escolha do caminho CPU, não os pixels efetivos da GPU.
5. O launcher Python confere a existência da string `HOS_RES_SCALE` no EXE antes
   de tentar 125/150. Uma string encontrada é apenas um indício de compatibilidade;
   a ausência impede a execução com falsa promessa de resolução.

## Instalação e verificação

- **Não sobreponha a árvore 0.4.1 à pasta 0.4.0.** Extraia o ZIP em uma pasta
  NOVA; mantenha os `jogo/`, `work/`, RomFS e saves antigos intactos.
- Para usar a instalação compilada antiga sem sobrescrever nada, abra o terminal
  na pasta nova e execute
  `Jogar-MaxResolucao-125.cmd --out "C:\PASTA_ANTIGA\jogo"`
  (ou o script 150). Os comandos só aplicam a escala se o EXE executado possuir
  a implementação nativa compatível.
- Para incorporar as **novas mensagens de confirmação**, recompile o **EXE
  recompilado do jogo** pelo Builder com os fontes atualizados e a entrada
  original. Recompilar só a DLL Vulkan não atualiza o código em `host/nn_vi.c`.
- `AkynoLeyendBuilder.exe` **não foi recompilado neste ambiente Linux**.
  Portanto as novas opções podem não aparecer na janela. Use os CMDs até
  publicar a GUI pelo .NET 8 WPF no Windows.
- Compare `jogo/diagnosticos/<ultima tentativa>/execucao.json` para
  `environment.HOS_RES_SCALE`, `environment.AKYNO_RESOLUTION`, `HOS_DYNRES`.
  O `saida.log` do EXE recompilado mostrará se o caminho fixo foi escolhido.
- O real Max Resolution como mod do jogo ou do emulador **não foi portado**.
  Ele exige adaptar patches e recursos gráficos do jogo e validar a renderização;
  não é correto anunciar as escalas fixas como esse mod.

Nenhuma ferramenta altera saves, ROM ou EXE diretamente ao selecionar a escala.
