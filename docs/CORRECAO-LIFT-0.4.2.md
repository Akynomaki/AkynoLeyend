# Correção da tradução interrompida — AkynoLeyend 0.4.2

Data: 09/11/2026. Aplicável ao candidato Windows 0.4.2-rc.1.

## Aplicação automática — recomendada quando o erro se repete

1. Feche o AkynoLeyend Builder e extraia **todo** o ZIP pequeno em uma pasta.
2. Abra `Aplicar-Correcao-Lift.cmd`. Ele procura primeiro a instalação em que está;
   se o ZIP estiver separado, procura a instalação indicada no log, em
   `%USERPROFILE%\Downloads\AkynoLeyend-0.4.2-Candidato-Windows\AkynoLeyend-0.4.2`.
   Também é possível arrastar a pasta da instalação sobre o CMD. Se nenhum desses
   caminhos estiver disponível, ele pede o caminho da pasta que contém o Builder.
3. Aguarde **CORRECAO CONFIRMADA** e abra o Builder no caminho exibido. Clique em
   **Criar** com a mesma entrada e destino.

O aplicador verifica a revisão, o hash do arquivo de correção e o caminho do módulo
realmente importado. Reconhece o tradutor original e o já corrigido; uma alteração
desconhecida é preservada. A substituição tem backup em `work/repairs` e é desfeita
se a verificação falhar. A conferência ocorre em um processo Python isolado com os
adaptadores `insn`/`lift_fixes` usados pelo fluxo de tradução, sem dados do jogo.
Ela exige `Lifter.after` e a emissão ordenada dos seis pontos em funções sintéticas.
O registro fica em `work/logs/reparo-lift.json`; entradas, saves e ferramentas não são
alterados. O mesmo bloqueio de `work/build.lock` impede reparar durante um build.

O novo `lift(3).log` continua mostrando `Lifter` sem o atributo. Isso confirma que a
correção não estava ativa no objeto carregado nessa tentativa; o log, sozinho, não
identifica o arquivo `a64_lift.py` importado. O aplicador agora mostra esse caminho
e confere a instalação de destino, sem depender da extração manual na pasta certa.

## Instalação manual da atualização pequena

1. Feche o AkynoLeyend Builder.
2. Abra `AkynoLeyend-0.4.2-Correcao-Lift.zip` e extraia seu conteúdo **dentro da pasta
   `AkynoLeyend-0.4.2` que contém `AkynoLeyendBuilder.exe`**. Aceite substituir os arquivos.
   A subpasta `third_party` do ZIP precisa se juntar à `third_party` existente.
3. Abra o mesmo `AkynoLeyendBuilder.exe`, mantenha a mesma entrada e o mesmo destino
   e clique em **Criar** novamente.

Não é preciso apagar `work`, extrair novamente o jogo ou baixar ferramentas. O fluxo
volta a conferir a entrada e usa a extração completa existente. O cálculo de identidade
do arquivo de entrada ainda pode levar algum tempo antes de chegar à tradução.
A tradução é refeita e a compilação aproveita os objetos que continuam válidos.
O atualizador consiste apenas nos arquivos indicados no ZIP; não acessa saves.

Se optar pelo pacote completo corrigido, a atualização pequena continua sendo o caminho
mais direto para conservar o trabalho já feito na instalação atual. Não misture
executáveis/DLLs de instalações anteriores.

## Causa confirmada

`extract(2).log` termina com 186.592 arquivos extraídos. `lift(2).log` mostra o erro
antes da descoberta das funções:

```text
nx2/oot_occlusion.py, install
if pc in lifter.after:
AttributeError: 'Lifter' object has no attribute 'after'
```

O patch de oclusão esperava uma interface que o `third_party/a64-kit/lift/a64_lift.py`
incluído não implementava. A tabela ausente e sua aplicação na geração foram
implementadas. Apenas criar `after = {}` eliminaria a exceção e deixaria de emitir o patch.

Cada endereço recebe o C adicional depois do texto da instrução original. A tradução
compartilhada do mesmo opcode permanece intacta: uma carga igual em outro endereço
não recebe a alteração. Os passes de flags e registradores usam o texto combinado,
inclusive quando `A64_LOCAL_REGS` está ativo. As seis palavras ARM64 originais
continuam sendo verificadas antes de instalar qualquer alteração.

## Verificação

- Erro reproduzido no `Lifter` real antes da correção.
- Quatro testes novos aprovados: seis sítios e ordem de emissão, instruções diferentes
  ou ilegíveis, preservação de acréscimos anteriores e execução do C gerado.
- O fixture C é compilado e executado com o controle de oclusão em 0 e 1, com
  registradores no contexto e com 31 registradores locais. Uma carga igual fora dos
  sítios mantém o byte original; uma escrita adicional também chega ao contexto.
- Suíte completa: **156 testes, 147 aprovados, 9 omitidos, zero falhas**.
  Os omitidos requerem Windows/PowerShell.
- Registro: `resultado-testes-lift-0.4.2.txt`.
- Conferência adicional com o helper nativo real `a64emit`: tradução ARM64, descoberta,
  gravação de chunks, compilação e execução do C sintético, com registradores locais
  em 0 e 31. O mesmo C compilou e fechou o link para Windows x64; esse PE não foi
  executado. Registro: `resultado-native-lift-0.4.2.txt`.
- Aplicador: sete testes aprovados, incluindo substituição do fonte original real,
  importação pelo Python isolado em caminho Unicode, backup, repetição sem nova
  substituição, restauração após falha, bloqueio durante build e rejeição de entrada
  inválida. A suíte passou a 163 casos: 154 aprovados e 9 omitidos.
  Registro: `resultado-testes-reparo-lift-0.4.2.txt`. O CMD e as chamadas de bloqueio
  do Windows ainda precisam ser executados no Windows; os testes do aplicador
  executaram sua CLI Python e processos filhos reais neste host Linux.

Os fixtures usam instruções/dados sintéticos e o lifter distribuído. Não foi executado
o jogo, a janela WPF ou uma GPU física neste ambiente. Esta correção trata o bloqueio
da tradução; os defeitos gráficos anteriormente relatados continuam dependendo de
verificação no jogo. Os binários do launcher e do renderer permanecem 0.4.2-rc.1.
