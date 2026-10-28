# J.A.R.V.I.S — Assistente operacional do Simpress

Assistente desktop (PyQt6) com visual HUD escuro/ciano: um núcleo 3D girando (esfera de pontos e anéis desenhados com QPainter, sem OpenGL), um chat em destaque e os números do Simpress ao lado. A IA (OpenRouter) usa as funções do servidor local; o Portal abre no navegador quando preciso.

Destaques: chamada por voz “Hey Jarvis” (offline), conversa contínua que dorme sozinha, botão de microfone mudo, resposta falada curta e ferramentas plugáveis em `actions/`.

## Como iniciar

1. Ligue o Simpress (`iniciar_servidor.bat` na pasta do Simpress). O Jarvis acha a porta sozinho (começa por `SIMPRESS_URL` e varre 8000–8099).
2. Copie `.env.example` para `.env` e preencha `OPENROUTER_API_KEY`.
3. Dê dois cliques em `iniciar_jarvis.bat` (janela) ou `iniciar_jarvis_terminal.bat` (terminal).

## A janela

- **Topo:** Simpress online/offline e porta, `💤 em espera` (escuta ativa ligada: microfone só procura “Hey Jarvis”), modelo de IA, voz 🔊/🔇 e o menu ⚙ (modelo, Abrir Simpress no navegador, Importar planilhas…, Nova conversa, Escuta ativa).
- **Esquerda (trilho):** orbe grande (ocioso, pensando, falando, ouvindo — sempre com texto, não só cor; “Clique para cancelar” enquanto ativo) e, embaixo, os cartões Equipamentos, Chamados abertos, Automação e Pendências. Atualizam a cada 10 s; clicar pergunta ao Jarvis.
- **Direita:** a conversa em balões (até 880 px). Listas viram tabelas de até 10 linhas; depois de cada resposta aparecem até 3 sugestões de próxima pergunta.
- **Avisos:** chamados novos, rotina de automação terminada e queda/volta do Simpress aparecem no chat (e são falados com a voz ligada). Não passam pela IA.
- **Abaixo de 1100 px:** trilho e orbe encolhem, cartões em 2×2; Simpress, CPU/RAM e a linha de estado descem para uma barra no rodapé. Até 760 px os cartões viram lista. Em janela larga e baixa o orbe diminui (400/300 px).

Teclado: `Tab` percorre orbe, conversa e campo; `Enter`/`Espaço` no orbe começa a falar; `Esc` cancela o cartão de confirmação.
Animações de 150–300 ms; desligue com `JARVIS_REDUZIR_MOVIMENTO=1` (o núcleo fica parado).
Medidores de CPU e RAM aparecem discretos no topo (precisam do `psutil`, já no `requirements.txt`).

**Microfone mudo:** o botão do topo (ou `Ctrl+M`) descarta o áudio: o Jarvis não ouve nome, “cancelar” nem fala, e o núcleo mostra o estado “mudo”. Desmutar volta à espera sem acordar. O indicador de microfone do Windows continua aceso, porque o dispositivo segue aberto; o áudio é descartado.

## Chamar o Jarvis

Clique no orbe (ou 🎤) ou diga **“Hey Jarvis”**. Toca um bipe; fale e ele para sozinho depois de 2 s de silêncio (máximo 20 s).

**Conversa contínua:** depois que o Jarvis termina de falar, ele volta a ouvir sozinho, sem novo “Hey Jarvis”. Após 2 minutos sem você falar, ele dorme e volta a esperar pelo nome. “Cancelar” ou fechar o cartão de confirmação também encerra a conversa.

**Resposta falada curta:** a voz lê só as primeiras 3 frases (até cerca de 280 caracteres), sem tabelas, e termina com “O restante está na tela.” O texto completo continua no chat; por isso a IA começa cada resposta por uma conclusão curta.

“Hey Jarvis” exige a **Escuta ativa** (⚙ › Escuta ativa; fica salva como `JARVIS_ESCUTA=1` no `.env`). “Hey Jarvis” é reconhecido pelo **openwakeword** (modelo `hey_jarvis`, offline); “cancelar” continua no Vosk com o modelo `modelos_voz/vosk-model-small-pt-0.3` (baixar de https://alphacephei.com/vosk/models e descompactar ali; a pasta fica fora do Git). Se o openwakeword ou o modelo faltar, aparece um aviso e o Vosk volta a reconhecer “Jarvis” (dito como “jarbas”) como plano B; sem o modelo do Vosk, o clique no orbe continua funcionando.

**Modelo do “Hey Jarvis” (passo único, precisa de internet):** o programa nunca baixa nada sozinho. Depois de instalar as dependências, rode uma vez:

```
.venv313\Scripts\python -c "import openwakeword.utils as u; u.download_models(['hey_jarvis'])"
```

Sensibilidade: `JARVIS_WAKE_LIMIAR` (0 a 1, padrão 0.5; suba se disparar sozinho, desça se não ouvir). A escuta pausa enquanto o Jarvis fala, grava, espera a IA ou mostra um cartão de confirmação.

**Privacidade da escuta:** o áudio contínuo é analisado só neste computador e não é gravado. Só o trecho gravado **depois** do bipe vai ao modelo de transcrição do OpenRouter, como no 🎤.

## Python 3.13 e ambiente virtual

O openwakeword usa o onnxruntime, que ainda não tem pacote para o Python 3.15. Por isso o Jarvis roda no **Python 3.13** (`winget install Python.Python.3.13`; confira com `py -3.13 --version`). Os `iniciar_jarvis*.bat` usam `.venv313` se existir; sem nenhuma pasta de ambiente, criam `.venv313` quando `py -3.13` existe (senão `.venv`, como antes); e com só a `.venv` antiga, seguem nela.

Para migrar: `py -3.13 -m venv .venv313`, `.venv313\Scripts\python -m pip install -r requirements.txt` e o passo do modelo acima. Os `.bat` fecham a janela do prompt quando o Jarvis fecha; só ficam parados (`pause`) se ele terminar com erro, para você ler a mensagem.

## Planilhas

- **Exportar:** “exporte a planilha de equipamentos / chamados / do histórico” salva em `Downloads` e mostra `Planilha Exportada com Sucesso!` com o link “Abrir pasta”.
- **Atualizar por automação:** “atualize as planilhas” roda a rotina de inventários do Simpress (pede confirmação).
- **Importar arquivos que você já tem:** ⚙ › Importar planilhas… (ou peça ao Jarvis). Escolha a planilha do Endpoint e a da Simpress, confirme, e o Jarvis entrega o lote em `data/state/entrada_automatica/pendentes/` do Simpress (`SIMPRESS_DIR`). Ele confere o resultado a cada 5 s, por até 5 min.

## Ferramentas da IA

Cada ferramenta é um arquivo em `actions/` (um item `TOOL` ou lista `TOOLS` com schema, função e, se altera dados, o texto do cartão). `tools/simpress_tools.py` descobre os módulos só dentro dessa pasta. Ferramenta sem `altera_dados` explícito conta como alteradora e exige confirmação.

Leituras são livres. Alterações **sempre** mostram um cartão "Confirmar e executar / Cancelar" com texto montado pelo programa (nunca pela IA); no máximo uma alteração por turno.

Alteram dados (exigem confirmação): atualizar apelido, atualizar usuário, executar automação, cancelar automação, decidir pendência, salvar unidade (editar ou criar), clicar_confirmado e digitar_confirmado no navegador.
Não viram ferramenta (use o Simpress no navegador): restauração, exclusões, salvar equipamento, agendamento Sebrae.

O Jarvis não se conecta ao Chrome de automação (porta 9333); rotinas rodam pelo servidor. Os sites usam o Chrome do Jarvis (seção abaixo).

## Abrir e usar sites

- **Abrir (`abrir`):** sites do catálogo (YouTube, Endpoint Central, UX Simpress, Dashboard, SoftExpert; ver `sites.py`), qualquer URL http/https e programas do Menu Iniciar, vários de uma vez. Sites abrem no **Chrome do Jarvis**; o navegador padrão só é usado se o Chrome do Jarvis não puder subir.
- **Chrome do Jarvis:** Chrome visível com perfil próprio (`%LOCALAPPDATA%\JarvisChrome`) e CDP em 127.0.0.1, porta 9334 (`JARVIS_CHROME_PORTA`). É separado do Chrome do Simpress (9333).
- **Ferramentas de navegador:** navegar, ler_pagina, clicar, clicar_confirmado, digitar, digitar_confirmado, abas e logar_site.
- **Cartão de confirmação:** cliques de risco (enviar, salvar, excluir…) e digitação no SharePoint pedem o cartão. O cartão do Dashboard avisa que a rotina do Sebrae grava essa planilha a cada 30 min. `digitar` com Enter (busca) roda sem cartão fora do SharePoint: Enter num formulário pode enviá-lo.
- **Senhas:** ⚙ › Credenciais… guarda no Gerenciador de Credenciais do Windows (`Jarvis/<id>`). Senha nunca vai por chat ou voz e só é digitada nos sites permitidos. MFA e PIN são sempre seus. `logar_site` funciona para Dashboard e SoftExpert; as receitas do UX Simpress e do Endpoint Central ainda faltam (serão mapeadas ao vivo com você).

## Privacidade (LGPD)

Usuário logado, apelido, nomes, e-mails e telefones viram tokens `[PESSOA_n]` antes de ir à IA. O mapa fica só na memória. A voz (Edge-TTS) fala os nomes reais; esse texto vai à Microsoft para virar áudio.

## Variáveis de ambiente

`OPENROUTER_API_KEY`, `MODELO_PRINCIPAL`, `SIMPRESS_URL`, `SIMPRESS_DIR`, `JARVIS_REDUZIR_MOVIMENTO`, `JARVIS_ESCUTA`, `JARVIS_WAKE_LIMIAR`, `JARVIS_CHROME_PORTA` (padrão 9334; 9333, do Chrome do Simpress, é recusada) (ver `.env.example`).

Pacotes novos: `playwright` e `keyring`. O `iniciar_jarvis.bat` instala; para rodar manualmente use `pip install -r requirements.txt`.

## Testes

```
.venv313\Scripts\python -m pytest -q
```

Cobrem cliente HTTP, exportação, lote de importação, cartões de resposta, avisos, corte de silêncio, “Hey Jarvis” (re-buffer, limiar, repouso e plano B, com modelo falso), laço de ferramentas/confirmação, LGPD e contraste WCAG AA dos tokens. A janela foi verificada à mão contra o Simpress real (:8000) e contra um servidor falso, não pela suíte.
