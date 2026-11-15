# AkynoLeyend 0.4.1 — correção de diagnóstico da escala experimental

**Não instale o novo ZIP por cima da pasta antiga.** O executável WPF incluso
permanece 0.4.0 e não incorpora visualmente as opções adicionadas só aos
fontes. Para escala experimental 125/150%, utilize `Jogar-MaxResolucao-125.cmd`
ou `Jogar-MaxResolucao-150.cmd`; para apontar ao jogo existente, inclua
`--out "CAMINHO\jogo"`. Essas opções **não são o mod Max Resolution de outro
emulador** e ainda exigem validação da GPU. A nova verificação impede anunciar
escala maior com um EXE sem o suporte nativo necessário. Leia
[docs/CORRECAO-RESOLUCAO-041.md](docs/CORRECAO-RESOLUCAO-041.md).

## Histórico da base integrada

# AkynoLeyend 0.4.0-dev.1 — fontes integrados candidatos 0.4.1

Launcher Windows preto e dourado, controles gráficos ligados ao renderizador e atualização de instalações locais 0.3.6–0.3.9 com backup. Inclui uma correção de sincronização para a leitura do medidor de exposição e otimizações do trabalho de CPU do backend Vulkan.

**Pacote atualizado de fontes (candidato 0.4.1).** Consulte [docs/INTEGRACAO-0.4.1-CANDIDATO.md](docs/INTEGRACAO-0.4.1-CANDIDATO.md) para as correções de folhagem, o teste de pipelines task/mesh AMD, o controle experimental de resolução 125/150% e os ajustes de preparação de shaders. Os executáveis genéricos incluídos ainda são 0.4.0: recompilar no Windows antes de validar os fixes do host e GPU.

**Experimental. O crash AMD recebido ainda não tem causa exata demonstrada. OpenGL ainda não está implementado.** A DLL e o launcher foram compilados para Windows; os testes locais usam dados sintéticos e não demonstram ganho de FPS nem correção visual numa GPU física.

## Continuar a instalação existente com segurança

1. Feche o jogo e o launcher. Faça backup de `jogo`, `work` e dos saves.
2. **Extraia este pacote em uma pasta nova**; não copie sua árvore inteira por cima da versão anterior.
3. Como a GUI pré-compilada continua sendo 0.4.0, para experimentar a escala
   use o CMD deste novo pacote apontando ao jogo compilado anterior:
   `Jogar-MaxResolucao-125.cmd --out "C:\PASTA_ANTIGA\jogo"`
   ou `Jogar-MaxResolucao-150.cmd --out "C:\PASTA_ANTIGA\jogo"`.
   O launcher avisará caso o executável não contenha o suporte nativo mínimo.
4. Para aplicar os novos ajustes de **código C/C++**, o Builder precisa gerar
   um novo EXE a partir de sua entrada original; atualizar apenas a DLL não basta.
   Nunca altere os saves, o `image.bin` ou o manifesto manualmente.
5. Para a confirmação no log, procure `vi: fixed scale active` em
   `jogo/diagnosticos/.../saida.log` **depois de recompilar o host com estes fontes**.
   A ausência dessa mensagem em um EXE antigo não comprova falha da resolução.

**A interface WPF desta distribuição não foi republicada:** opções adicionadas
só ao XAML podem não aparecer no `AkynoLeyendBuilder.exe` incluído. Veja
`docs/CORRECAO-RESOLUCAO-041.md`. O verdadeiro patch ARM64 Max Resolution do
emulador não faz parte desta distribuição.

## Instalação nova

Extraia **todo** o pacote Windows, abra `AkynoLeyendBuilder.exe`, selecione sua própria cópia suportada `.nup` ou as pastas `exefs` e `romfs`, escolha o destino e clique em **Criar**. O build suportado tem ID iniciado por `e0f3ccfa`, correspondente à versão 1.1.1 desta base.

O pacote não inclui jogo, chaves, saves, cache de terceiros nem EXE recompilado do jogo. Inclui Python, ferramentas de compilação, runtime do launcher e DLL gráfica genérica. O ZIP de fontes separado não contém essas ferramentas/binários prontos.

Requisitos da execução: Windows 10/11 x64, CPU compatível com x86-64-v3/AVX2 e driver Vulkan com os recursos task/mesh exigidos por esta base. A presença de Vulkan, por si só, não garante compatibilidade. Reserve espaço para a compilação; a interface estima 60 GiB e ajusta o paralelismo à RAM disponível.

## Gráficos no launcher

Os ajustes são persistidos em `AkynoLeyend-launcher.json`. A opção **Salvo no jogo** preserva o valor do menu Insert/F1. Os controles explícitos são aplicados ao iniciar cada sessão.

| Controle | Comportamento |
|---|---|
| API | Vulkan funcional; OpenGL aparece indisponível e é recusado também na CLI |
| Resolução | Auto ou escala interna fixa de 100%, 75%, 67% ou 50% |
| Qualidade | 100%, Lanczos, nitidez 10%, tempo real, geração de quadros desligada |
| Equilibrado / Fluidez | 75% / 67% com o mesmo filtro; pode aliviar uma GPU limitada pela resolução |
| Velocidade | Tempo real ou Por quadro; tempo real evita jogo lento quando o FPS cai, dentro do limite de passo do motor |
| Geração de quadros | Desligada ou 2x–8x; quadros gerados não são FPS de simulação |
| Ritmo de quadros | Controle existente de apresentação, sem promessa de mais FPS |
| Cache | Original ou Streaming; preparação disponível na página Ferramentas |

100% fixa a escala interna prevista pela base: não significa renderizar necessariamente na resolução nativa do monitor nem ativar supersampling 4K. O caminho dinâmico inicial continua funcionando por 30 quadros para preencher os campos necessários antes da escala fixa. Os patches IPS Max Resolution/Dynamic FPS de emuladores não foram copiados para os endereços do EXE recompilado.

O preset Qualidade é um ponto de partida para comparar nitidez. Ele não força mais exposição, remove neblina ou corrige geometria ausente. Os flashes/objetos pretos precisam ser avaliados na mesma cena depois da atualização.

## Perfis e diagnóstico

| Perfil/comando | Finalidade |
|---|---|
| Original / `Jogar.cmd` | Defaults do motor, sem herdar variáveis experimentais de outras tentativas |
| 8 GB / `Jogar-8GB.cmd` | Orçamento de texturas menor e seleção de mip reduzida para texturas elegíveis |
| Compatibilidade / `Jogar-Compatibilidade.cmd` | Texturas até 4096 MiB, mirrors até 512 MiB, dois workers; preserva dimensões e registra operações recentes da CPU |
| `Preparar-Shaders.cmd` | Banco privado de shaders, progresso e saída ao terminar a preparação |
| `Testar-Luzes.cmd` | Métricas de exposição/frames, sem gravar vídeo a cada quadro |
| `Jogar-Sem-BC3.cmd` / `Jogar-ASTC-CPU.cmd` | Comparações de textura; podem elevar memória/tempo de CPU e não são correções confirmadas |
| `Coletar-Crash.cmd` | ZIP da tentativa com logs, manifesto, hashes e mapa correspondente quando disponível |

Os limites dos perfis são de categorias específicas, **não um teto global de VRAM**. Compatibilidade é uma mitigação para comparação e não uma solução comprovada para o device lost da RX 9060 XT.

Cada tentativa gera `jogo/diagnosticos/DATA-HORA-PID` com `execucao.json`, `saida.log` e `erros.log`. Em caso de crash, compartilhe o ZIP completo da mesma tentativa. Os novos `CPU_BREADCRUMB` mostram a ordem recente de gravação na CPU; não identificam por si só o comando concluído na GPU ou o shader causador.

## Créditos e desenvolvimento

Autores e componentes em [creditos/README.md](creditos/README.md); TXT antigos em `creditos/historico`; [relatório técnico](docs/HANDOFF-OUTRA-IA.md). Os avisos originais continuam nos fontes, em `LICENSE`, `THIRD_PARTY_NOTICES.md` e nas pastas de dependências.

```powershell
.\ferramentas\python\python.exe -I -X utf8 .\manage.py doctor
.\ferramentas\python\python.exe -m unittest discover -s tests -v
.\Jogar.cmd --resolution 100 --speed realtime --upscaling lanczos --sharpness 10 --framegen 0
```

O código de orquestração fica em `akynoleyend/`, a interface em `builder/AkynoLeyendBuilder`, o runtime em `host` e o renderizador em `gpu/vk`. Identificadores antigos ficam onde necessários à migração, ao cache/ABI ou à atribuição histórica.
