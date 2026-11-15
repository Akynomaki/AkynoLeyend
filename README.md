# AkynoLeyend

**Ferramenta independente de recompilação estática e pesquisa de compatibilidade para Windows x64.**

O AkynoLeyend desenvolve um fluxo para traduzir código ARM64 a partir de arquivos locais e executar o resultado com um runtime nativo e um renderizador Vulkan. O trabalho parte do [Hookshot](https://github.com/NotRexed/Hookshot), de NotRexed e colaboradores.

## Fontes e downloads

Este repositório contém os fontes da 0.4.8: o launcher, a orquestração em Python, o host, o renderizador Vulkan, os testes e a documentação em `docs/`. Os pacotes para Windows ficam nas [Releases](https://github.com/Akynomaki/AkynoLeyend/releases). A versão mais recente é a [0.4.8 — atualização de desempenho](https://github.com/Akynomaki/AkynoLeyend/releases/tag/v0.4.8-desempenho):

- **Instalação nova:** o ZIP completo, que já traz o launcher, o renderizador, o Python e o compilador.
- **Quem já tem a 0.4.8:** o ZIP de atualização, usado em **Atualizar build** no launcher.
- **Da Teste 4 até a 0.4.7:** o mesmo ZIP no launcher ou o atualizador `.exe`, que já leva o ZIP dentro.

O compilador LLVM-MinGW, o Python embutido e as bibliotecas Python vêm apenas no ZIP completo, não no git. O SDK DLSS da NVIDIA é usado na compilação do renderizador. A licença dele não permite redistribuí-lo, então ele não está no repositório nem nos pacotes. O runtime DLSS é baixado no PC do jogador pelo launcher.

## O que a versão de teste 0.4.8 reúne

- Launcher para Windows com perfis gráficos, detecção de CPU, aviso de memória disponível e fluxo de manutenção incremental.
- Preparação de shaders e pipelines já encontrados em partidas anteriores, com preparação dos pipelines gráficos restantes em segundo plano.
- Renderização Vulkan com controle de resolução, FSR conforme a GPU e a configuração, ajuste de distância de renderização e opção experimental de malhas por Compute.
- Ajustes de memória de vídeo, sincronização e diagnóstico de desempenho por quadro. O menu F1 também reúne opções de imagem e controles.
- Atualização de desempenho:
  - Menos pressão de memória e de write-back.
  - Consultas de oclusão em lotes.
  - Descarte de texturas distribuído entre quadros.
  - Preset opcional NVIDIA RTX · 1600p DLSS Qualidade.

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

O Hookshot fornece a base técnica. O histórico do projeto reconhece também contribuições do Eden, suyu, yuzu, Sirit, a64-kit e demais dependências, com os respectivos avisos nos fontes. O NX2navi serviu de referência de comportamento para o pré-carregamento. As mudanças do AkynoLeyend incluem o launcher, a automação de compilação e atualização, ajustes de renderização e ferramentas de diagnóstico.

Veja [como contribuir](CONTRIBUTING.md).
