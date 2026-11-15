# Suporte e perfis opcionais

Os comandos desta pasta localizam o projeto pela própria localização. As entradas
principais ficam na raiz: Compilar.cmd, Jogar.cmd, Preparar-Shaders.cmd e Verificar.cmd.

| Uso | Comandos |
|---|---|
| Coletar diagnóstico | Coletar-Crash.cmd, Analisar-Log-Shaders.cmd, Jogar-Suporte.cmd |
| Conferir arquivos e acesso | Auditar-RomFS.cmd, Diagnosticar-Acesso.cmd, Reparar-Acesso.cmd |
| Comparar renderização | Jogar-Visual.cmd, Jogar-Comparacao.cmd, Testar-Luzes.cmd |
| Perfis de memória/cache | Jogar-8GB.cmd, Jogar-Streaming.cmd, Jogar-Cache-Equilibrado.cmd |

Os demais comandos são opções de diagnóstico. Use uma comparação por vez e guarde
o log correspondente. Os perfis não garantem FPS ou limite total de VRAM.

Aplicar-Correcao-Lift.cmd atende instalações antigas 0.4.2-rc.1. A versão de teste
0.4.3 já inclui essa correção e não precisa executar esse reparo.
