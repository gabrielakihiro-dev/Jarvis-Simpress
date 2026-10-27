# J.A.R.V.I.S — Assistente operacional do Simpress

Casca desktop (PyQt5) com visual HUD escuro/ciano que reúne, numa só janela, as telas reais do Simpress e um assistente de IA (OpenRouter) com acesso às funções do servidor local.

## Como iniciar

1. Ligue o Simpress (`iniciar_servidor.bat` na pasta do Simpress). O Jarvis acha a porta sozinho (começa por `SIMPRESS_URL` e varre 8000–8099).
2. Copie `.env.example` para `.env` e preencha `OPENROUTER_API_KEY`.
3. Dê dois cliques em `iniciar_jarvis.bat` (janela) ou `iniciar_jarvis_terminal.bat` (terminal).

## A janela

- **Topo (HUD):** Simpress online/offline e porta, total de equipamentos, chamados abertos, estado da automação, modelo de IA e voz. Cada indicador tem ícone e texto, não só cor. Atualiza a cada 10 s.
- **Menu lateral:** Início, Transporte, Resumo, Automação, Chamados, Comparação, Histórico de apelidos, Relatório mensal, Atualizar planilhas, Histórico de planilhas, Unidades. `F1`–`F8` seguem os atalhos do Cockpit.
- **Centro:** a tela real do Simpress (QWebEngine). Com o servidor desligado aparece um aviso e o botão "Procurar de novo".
- **Direita:** chat com o assistente (`Ctrl+J` mostra/esconde), ações rápidas e seletor de modelo.
- **Abaixo de 1100 px:** o menu mostra só ícones e o chat vira painel sobreposto.

Teclado: `Tab` percorre menu, tela e chat; `Esc` cancela o cartão de confirmação.
Animações de 150–300 ms; desligue com `JARVIS_REDUZIR_MOVIMENTO=1`.

## Ferramentas da IA

17 de leitura (livres) e 5 de alteração. Alterações **sempre** mostram um cartão "Confirmar e executar / Cancelar" com texto montado pelo programa (nunca pela IA); no máximo uma alteração por turno.

Alteram dados (exigem confirmação): atualizar apelido, atualizar usuário, executar automação, cancelar automação, decidir pendência.
Não viram ferramenta (use a tela): upload de planilha, restauração, exclusões, salvar equipamento/unidade, agendamento Sebrae.

O Jarvis não se conecta ao Chrome de automação (porta 9333); rotinas rodam pelo servidor.

## Privacidade (LGPD)

Usuário logado, apelido, nomes, e-mails e telefones viram tokens `[PESSOA_n]` antes de ir à IA. O mapa fica só na memória. A voz (Edge-TTS) fala o texto mascarado.

## Variáveis de ambiente

`OPENROUTER_API_KEY`, `MODELO_PRINCIPAL`, `SIMPRESS_URL`, `JARVIS_REDUZIR_MOVIMENTO` (ver `.env.example`).

## Testes

```
.venv\Scripts\python -m pytest -q
```

Cobrem cliente HTTP, laço de ferramentas/confirmação, LGPD e contraste WCAG AA dos tokens. A janela em si foi verificada manualmente contra um servidor falso, não pela suíte.
