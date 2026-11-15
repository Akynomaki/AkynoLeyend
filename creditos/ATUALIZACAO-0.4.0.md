# AkynoLeyend 0.4.0-dev.1 — atualização experimental

- Launcher preto e dourado, navegação lateral e páginas Gráficos, Ferramentas e Créditos. Executável WPF recompilado para Windows x64.
- Nome público AkynoLeyend no launcher, jogo, DLL e configurações/cache novos. Migração de instalações reconhecidas 0.3.6–0.3.9 com conferência de hashes e backup; sem recompilar as instruções do jogo nessa operação.
- Controles funcionais de resolução interna, velocidade em tempo real, filtro, nitidez, geração/ritmo de quadros e cache. OpenGL permanece indisponível.
- Backport da espera por resultados da GPU usados pela CPU, incluindo o medidor de exposição. Otimizações de consultas/bindings/estado dinâmico/hazards e cache limitado de leituras capturadas para reduzir trabalho repetido na CPU.
- Novo perfil Compatibilidade com orçamento de texturas/mirrors e diagnóstico limitado das operações recentes. Responde ao log de device lost na RX 9060 XT; a causa exata ainda não foi demonstrada.
- Créditos reunidos e TXT de atualizações antigos em `creditos/historico`.

Para aplicar: extraia o ZIP de atualização na mesma pasta que contém `manage.py`, feche o jogo, execute `Atualizar-AkynoLeyend.cmd` e depois `Preparar-Shaders.cmd`. Abra `AkynoLeyendBuilder.exe`.

Os testes locais e a compilação não comprovam correção visual em AMD/NVIDIA nem ganho de FPS. Não houve execução do jogo ou da janela WPF neste host Linux. O crash AMD e a renderização preta continuam exigindo verificação na máquina afetada com o ZIP completo da nova tentativa.
