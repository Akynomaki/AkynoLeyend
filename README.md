# AkynoLeyend

**Ferramenta independente de recompilação estática e pesquisa de compatibilidade para Windows x64.**

O AkynoLeyend desenvolve um fluxo para traduzir código ARM64 a partir de arquivos locais e executar o resultado com um runtime nativo e um renderizador Vulkan. O trabalho parte do [Hookshot](https://github.com/NotRexed/Hookshot), de NotRexed e colaboradores.

## Fontes e downloads

Os pacotes para Windows ficam nas [Releases](https://github.com/Akynomaki/AkynoLeyend/releases). A versão mais recente é a [0.5.5 — multiplayer dentro do jogo](https://github.com/Akynomaki/AkynoLeyend/releases/tag/v0.5.5):

- **Instalação nova:** `AkynoLeyend-0.5.5.zip`. Extraia e abra o `AkynoLeyend-Launcher.exe`.
- **Quem já tem a 0.5.4 ou a 0.5.4-MOD:** `AkynoLeyend-Atualizacao-0.5.5.zip`. No launcher, **Atualizações** acha essa versão sozinho em **Procurar atualização**, ou você escolhe o ZIP em **Selecionar atualização (.zip)**. Depois clique em **Atualizar o jogo**.
- **Quem está numa versão mais antiga:** use o ZIP completo.

Os dois ZIPs têm o mesmo conteúdo: o launcher, as ferramentas com os fontes do host e do renderizador, o Python e o compilador. A atualização do launcher troca a pasta `ferramentas` inteira, por isso o pacote de atualização também é completo.

O git deste repositório ainda contém os fontes da 0.4.9: o launcher, a orquestração em Python, o host, o renderizador Vulkan, os testes e a documentação em `docs/`. Os fontes da 0.5.5 vão dentro do pacote, na pasta `ferramentas`. O compilador LLVM-MinGW, o Python embutido e as bibliotecas Python vêm apenas nos pacotes, não no git. O SDK DLSS da NVIDIA é usado na compilação do renderizador. A licença dele não permite redistribuí-lo, então ele não está no repositório nem nos pacotes. O runtime DLSS é baixado no PC do jogador pelo launcher.

## Novidades da 0.5.5

- **Multiplayer dentro do jogo (em teste):**
  - O menu do F1 (ou Insert) tem as abas **Multijogador**, **Sala** e **Mods** do co-op do [Squadala!](https://github.com/daurosk/oot-remake-multiplayer), entre Controles e Sistema.
  - Nelas dá para hospedar e entrar numa partida, jogar co-op local, mudar o nome e as cores do Link e ver quem está na partida.
  - Os textos das abas estão em português.
  - O **Jogar** do launcher deixa o multiplayer carregado e parado até você hospedar ou entrar.
- **Página Multiplayer no launcher:** instala o Squadala! v0.11.7 conferido pelo SHA-256, hospeda com código de convite e entra com o código de um amigo.
- **Placa de vídeo no launcher:** em Gráficos, ao lado do perfil de memória, você escolhe a placa em que o jogo abre.
- **Mods do GameBanana no launcher:** busca, instalação e organização dos mods de RomFS.

O multiplayer foi testado com um jogador por PC. Uma partida entre dois PCs ainda não foi testada.

## O que já vinha na 0.4.9

- Launcher para Windows com perfis gráficos, detecção de CPU, aviso de memória disponível e fluxo de manutenção incremental.
- Preparação de shaders e pipelines já encontrados em partidas anteriores, com preparação dos pipelines gráficos restantes em segundo plano.
- Renderização Vulkan com controle de resolução, FSR conforme a GPU e a configuração, ajuste de distância de renderização e opção experimental de malhas por Compute.
- Ajustes de memória de vídeo, sincronização e diagnóstico de desempenho por quadro. O menu F1 também reúne opções de imagem e controles.
- Atualização de desempenho:
  - Menos pressão de memória e de write-back.
  - Consultas de oclusão em lotes.
  - Descarte de texturas distribuído entre quadros.
  - Preset opcional NVIDIA RTX · 1600p DLSS Qualidade.
- Opção Gráficos > Vegetação e efeitos decorativos (0.4.9): remove o capim, as plantas, as samambaias e o musgo do chão, as folhas caindo e os vagalumes. Vale ao abrir o jogo. Alivia a placa de vídeo; o FPS sobe quando ela é o limite.

## Desempenho medido

| Teste de desenvolvimento | Resultado observado |
| --- | --- |
| Compilação das mesmas 400 unidades, Ryzen 5 3500X e 16 GB, r13c → 0.4.5 | 114,6 → 23,7 minutos. Conta somente a etapa de compilação. |
| Extração de um trecho com cerca de 6 mil arquivos comprimidos, leitor anterior → 0.4.5 | 39–45 → 3,9–4,5 segundos. |
| Campo de Hyrule, RTX 3060 Ti 8 GB, Ryzen 5 3500X, geração de quadros desligada, test.2 → duas variantes da test.3 | 25,9 → 12,2–12,8 quadros acima de 250 ms por minuto nas execuções citadas. |
| Kokiri em 1080p, RTX 5070 Ti Laptop, câmera parada na mesma sessão | Aproximadamente 36,2 → 38,5 FPS com distância de renderização limitada a 60 m. A opção reduz a quantidade de objetos visíveis à distância. |
| Kokiri, RTX 5070 Ti Laptop, preset 1600p DLSS Qualidade, segunda atualização → atualização cumulativa de desempenho | Câmera parada: 21,6 → 30,0 FPS médios, 152 → 0 quadros acima de 50 ms. Girando a câmera: 27,5 → 31,4 FPS médios, 40 → 8 quadros acima de 50 ms. |

Essas medições são de máquinas e cenários específicos nas revisões indicadas. O ganho do novo pré-carregamento da 0.4.8 ainda precisa ser medido em partidas. A compatibilidade com GPUs antigas e integradas, o HDR e a geração dinâmica de quadros seguem em validação. Há relatos de encerramento ao carregar alguns trechos do mapa.

## Jogo, conteúdo e suporte

O AkynoLeyend é um projeto não oficial, sem afiliação, patrocínio ou aprovação da Nintendo. Os nomes de produtos são citados para identificar a compatibilidade. Marcas e conteúdo do jogo pertencem aos respectivos titulares.

O projeto não inclui nem indica onde obter cópias do jogo, firmware, chaves, arquivos extraídos, executáveis recompilados, caches derivados ou recursos audiovisuais proprietários. Use apenas arquivos locais que você tenha o direito de usar e respeite as leis e licenças aplicáveis. Não envie esse material em Issues, Pull Requests ou links externos. O projeto não apoia pirataria nem oferece suporte para obter cópias não autorizadas ou contornar proteções.

## Créditos

O Hookshot fornece a base técnica. O histórico do projeto reconhece também contribuições do Eden, suyu, yuzu, Sirit, a64-kit e demais dependências, com os respectivos avisos nos fontes. O NX2navi serviu de referência de comportamento para o pré-carregamento. O multiplayer é o Squadala! (daurosk e contribuidores, GPL-3.0); a ponte e as abas do menu adaptam patches dele ao motor, e o módulo e o servidor são baixados do release dele. As mudanças do AkynoLeyend incluem o launcher, a automação de compilação e atualização, ajustes de renderização e ferramentas de diagnóstico.

Veja [como contribuir](CONTRIBUTING.md).
