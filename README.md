# J.A.R.V.I.S — Assistente operacional do Simpress

Assistente desktop (PyQt6) com visual HUD escuro/ciano: um orbe, um chat em destaque e os números do Simpress ao lado. A IA (OpenRouter) usa as funções do servidor local; o Portal abre no navegador quando preciso.

## Como iniciar

1. Ligue o Simpress (`iniciar_servidor.bat` na pasta do Simpress). O Jarvis acha a porta sozinho (começa por `SIMPRESS_URL` e varre 8000–8099).
2. Copie `.env.example` para `.env` e preencha `OPENROUTER_API_KEY`.
3. Dê dois cliques em `iniciar_jarvis.bat` (janela) ou `iniciar_jarvis_terminal.bat` (terminal).

## A janela

- **Topo:** Simpress online/offline e porta, `💤 em espera` (escuta ativa ligada: microfone só procura palmas e “Hey Jarvis”), modelo de IA, voz 🔊/🔇 e o menu ⚙ (modelo, Abrir Simpress no navegador, Importar planilhas…, Nova conversa, Escuta ativa).
- **Esquerda:** cartões Equipamentos, Chamados abertos, Automação e Pendências. Atualizam a cada 10 s; clicar pergunta ao Jarvis.
- **Centro:** orbe (ocioso, pensando, falando, ouvindo — sempre com texto, não só cor) e a conversa em balões. Listas viram tabelas de até 10 linhas; depois de cada resposta aparecem até 3 sugestões de próxima pergunta.
- **Avisos:** chamados novos, rotina de automação terminada e queda/volta do Simpress aparecem no chat (e são falados com a voz ligada). Não passam pela IA.
- **Abaixo de 1100 px:** os cartões viram uma faixa no topo e o orbe encolhe.

Teclado: `Tab` percorre orbe, conversa e campo; `Enter`/`Espaço` no orbe começa a falar; `Esc` cancela o cartão de confirmação.
Animações de 150–300 ms; desligue com `JARVIS_REDUZIR_MOVIMENTO=1`.

## Chamar o Jarvis

Clique no orbe (ou 🎤), bata **duas palmas** ou diga **“Hey Jarvis”**. Toca um bipe; fale e ele para sozinho depois de 2 s de silêncio (máximo 20 s).

Palmas e “Hey Jarvis” exigem a **Escuta ativa** (⚙ › Escuta ativa; fica salva como `JARVIS_ESCUTA=1` no `.env`). “Hey Jarvis” é reconhecido pelo **openwakeword** (modelo `hey_jarvis`, offline); “cancelar” continua no Vosk com o modelo `modelos_voz/vosk-model-small-pt-0.3` (baixar de https://alphacephei.com/vosk/models e descompactar ali; a pasta fica fora do Git). Se o openwakeword ou o modelo faltar, aparece um aviso e o Vosk volta a reconhecer “Jarvis” (dito como “jarbas”) como plano B; sem o modelo do Vosk, o clique no orbe continua funcionando.

**Modelo do “Hey Jarvis” (passo único, precisa de internet):** o programa nunca baixa nada sozinho. Depois de instalar as dependências, rode uma vez:

```
.venv313\Scripts\python -c "import openwakeword.utils as u; u.download_models(['hey_jarvis'])"
```

Sensibilidade: `JARVIS_WAKE_LIMIAR` (0 a 1, padrão 0.5; suba se disparar sozinho, desça se não ouvir). Para ajustar, abra `iniciar_jarvis_debug.bat` e diga “Hey Jarvis” a distância normal. Sensibilidade das palmas: `JARVIS_PALMAS_LIMIAR` (padrão 0.2). A escuta pausa enquanto o Jarvis fala, grava, espera a IA ou mostra um cartão de confirmação.

**Privacidade da escuta:** o áudio contínuo é analisado só neste computador e não é gravado. Só o trecho gravado **depois** do bipe vai ao modelo de transcrição do OpenRouter, como no 🎤.

## Python 3.13 e ambiente virtual

O openwakeword usa o onnxruntime, que ainda não tem pacote para o Python 3.15. Por isso o Jarvis roda no **Python 3.13** (`winget install Python.Python.3.13`; confira com `py -3.13 --version`). Os `iniciar_jarvis*.bat` usam `.venv313` se existir; sem nenhuma pasta de ambiente, criam `.venv313` quando `py -3.13` existe (senão `.venv`, como antes); e com só a `.venv` antiga, seguem nela.

Para migrar: `py -3.13 -m venv .venv313`, `.venv313\Scripts\python -m pip install -r requirements.txt` e o passo do modelo acima. Depois do merge, se quiser o nome antigo: feche o Jarvis, apague a `.venv` e renomeie `.venv313` para `.venv`. Recriar com `py -3.13 -m venv .venv` é mais seguro que renomear, porque os scripts dentro do ambiente guardam o caminho antigo.

## Planilhas

- **Exportar:** “exporte a planilha de equipamentos / chamados / do histórico” salva em `Downloads` e mostra `Planilha Exportada com Sucesso!` com o link “Abrir pasta”.
- **Atualizar por automação:** “atualize as planilhas” roda a rotina de inventários do Simpress (pede confirmação).
- **Importar arquivos que você já tem:** ⚙ › Importar planilhas… (ou peça ao Jarvis). Escolha a planilha do Endpoint e a da Simpress, confirme, e o Jarvis entrega o lote em `data/state/entrada_automatica/pendentes/` do Simpress (`SIMPRESS_DIR`). Ele confere o resultado a cada 5 s, por até 5 min.

## Ferramentas da IA

Leituras são livres. Alterações **sempre** mostram um cartão "Confirmar e executar / Cancelar" com texto montado pelo programa (nunca pela IA); no máximo uma alteração por turno.

Alteram dados (exigem confirmação): atualizar apelido, atualizar usuário, executar automação, cancelar automação, decidir pendência, salvar unidade (editar ou criar).
Não viram ferramenta (use o Simpress no navegador): restauração, exclusões, salvar equipamento, agendamento Sebrae.

O Jarvis não se conecta ao Chrome de automação (porta 9333); rotinas rodam pelo servidor.

## Privacidade (LGPD)

Usuário logado, apelido, nomes, e-mails e telefones viram tokens `[PESSOA_n]` antes de ir à IA. O mapa fica só na memória. A voz (Edge-TTS) fala o texto mascarado.

## Variáveis de ambiente

`OPENROUTER_API_KEY`, `MODELO_PRINCIPAL`, `SIMPRESS_URL`, `SIMPRESS_DIR`, `JARVIS_REDUZIR_MOVIMENTO`, `JARVIS_ESCUTA`, `JARVIS_PALMAS_LIMIAR`, `JARVIS_WAKE_LIMIAR` (ver `.env.example`).

## Testes

```
.venv313\Scripts\python -m pytest -q
```

Cobrem cliente HTTP, exportação, lote de importação, cartões de resposta, avisos, palmas/corte de silêncio, “Hey Jarvis” (re-buffer, limiar, repouso e plano B, com modelo falso), laço de ferramentas/confirmação, LGPD e contraste WCAG AA dos tokens. A janela foi verificada à mão contra o Simpress real (:8000) e contra um servidor falso, não pela suíte.
