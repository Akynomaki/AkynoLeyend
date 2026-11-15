# Desenvolvimento desta base

Leia README.md, docs/arquitetura.md e docs/validacao.md antes de modificar.

- O motor vem de Hookshot-Release.zip. Preserve os avisos e registre as mudancas em docs/origem.md.
- A orquestracao nova fica em akynoleyend/. Compilador ARM64, runtime e GPU mantem as interfaces da base.
- Nao adicione codigo gerado, dados do jogo, saves ou caches aos fontes ou ao pacote de distribuicao.
- Nao edite codigo gerado manualmente. Mude o gerador ou os patches explicitos do lifter.
- O perfil original preserva os defaults do motor. Perfis experimentais ficam em akynoleyend/environment.py.
- Rode os testes de tests/ e as verificacoes de compilacao adequadas a mudanca.
- Nao declare que o jogo ou uma GPU foi testada apenas por compilar os fontes.
