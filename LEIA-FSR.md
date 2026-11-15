# AkynoLeyend com AMD FSR SDK 2.4

Sobreposição de fontes para o Teste 4 r6 com a correção de logs incluída neste handoff. O modo temporal usa o provedor FSR 3.1.6 do SDK Vulkan que você enviou. O ZIP inclui o loader e o upscaler oficiais, com os hashes registrados em `third_party/amd-fsr-sdk/sdk.json`.

## Preparar a candidata no Windows

1. Extraia este ZIP sobre **uma cópia da instalação r6 com a correção de logs** que tenha o SDK do projeto em `ferramentas`. Use um diretório separado da instalação em que a Claude está trabalhando.
2. Abra o Builder da cópia. Em **Salvar o jogo em**, aponte para a pasta `jogo` da **candidata**. Selecione a mesma entrada local. As pastas já extraídas `romfs` e `exefs` também servem e evitam repetir a extração do NUP.
3. Clique em **Criar**. Essa etapa gera os três hooks da câmera e compila o host e o renderizador. O compilador confere os objetos disponíveis pelas chaves do cache. Uma cópia com caminhos diferentes pode ter menos acertos de cache. Preserve as pastas `work` e os saves da instalação de origem.
4. Abra **Jogar-FSR-4K.cmd** na candidata. Ele pede saída de 3840×2160, escala interna de 50%, contador ligado e geração de quadros desligada. Se a sua saída do jogo estiver em outro diretório, passe `--out` com o caminho correspondente.

Aplique os arquivos desta pasta sobre a r6 com a correção de logs. O Builder incluído na r6 abre a build normalmente. O atalho ativa o FSR temporal pela CLI. O código da interface também inclui a escolha, disponível ao compilar o Builder com esses fontes.

Se o loader informar que faltam `MSVCP140.dll` ou `VCRUNTIME140*.dll`, use o [Redistribuível do Visual C++ x64 da Microsoft](https://learn.microsoft.com/pt-br/cpp/windows/latest-supported-vc-redist).

## Conferir no jogo

- Procure `AMD FSR 3.1.6 SDK frames=` no `erros.log` da sessão. A linha registra o tamanho de entrada e saída e o jitter. `AMD FSR SDK fallback` traz a razão do retorno ao upscale existente.
- Compare a mesma área e o mesmo save com FSR 1 e FSR temporal, com geração de quadros desligada. Meça os FPS base após o aquecimento dos shaders e observe água, Link em movimento, Navi, cortes de câmera e transições.
- O movimento disponível nesta candidata vem da câmera e da profundidade da cena. Os vetores por ator e a máscara de transparência ainda precisam de validação e integração para reduzir rastros em objetos móveis.

O objetivo é medir 30 FPS reais. O FSR temporal também consome GPU e VRAM. A geração de quadros AMD fica para a integração do passe de interpolação com a apresentação, a composição do HUD e a sincronização do Vulkan.

## Origem

Os hooks de projeção e a reprojeção de câmera adaptam o Hookshot v2.0.14, distribuído sob GPL-3.0. As DLLs AMD são as do arquivo fornecido, e as condições de redistribuição e avisos estão em `third_party/amd-fsr-sdk`.

## Validação original da integração sobre a r5

- Os dois shaders novos passaram no validador SPIR-V para Vulkan 1.2.
- As 183 unidades Vulkan compilaram e a DLL de verificação Windows x64 fechou o link com Clang 19 e MinGW. O link cruzado reportou avisos de seções RTTI duplicadas da libstdc++. O SDK LLVM-MinGW da instalação é a ferramenta usada para gerar a candidata no Windows.
- O host `nn_vi.c` compilou para Windows x64 com os headers gerados em fixture. A prova de emissão exige os três hooks, e o carimbo do tradutor de shaders é o mesmo da r5.
- Dos 274 testes, 262 passaram, 10 foram omitidos e 2 falharam também na r5 original. As falhas de base são a importação da extensão Windows `astc_encoder` neste Linux e a fixture antiga da tabela de páginas que omite o header `<memory>`.
- Falta executar com os arquivos locais do jogo e uma GPU Windows. FPS e qualidade visual ainda são resultados a medir.
