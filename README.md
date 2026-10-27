# 🤖 J.A.R.V.I.S — Assistente Operacional Simpress

Assistente com interface gráfica futurista em **PyQt5** (baseada na arquitetura do projeto de Rahees Ahmed) e modo terminal, integrado ao inventário local do **Simpress** (`http://127.0.0.1:8000`), síntese de voz natural (Edge-TTS) e inteligência artificial via **OpenRouter**.

---

## 🚀 Como Iniciar

1. Certifique-se de que o Simpress local está ligado (em `http://127.0.0.1:8000`).
2. Dê **dois cliques** no arquivo:
   ```
   iniciar_jarvis.bat
   ```
   *(Ele abrirá a **Interface Gráfica Futurista (GUI)**).*
3. Se preferir rodar no terminal clássico, use:
   ```
   iniciar_jarvis_terminal.bat
   ```

---

## 🎨 Recursos da Interface Gráfica (Inspirada no Jarvis de Rahees Ahmed)

- **HUD Espacial Escuro & Ciano:** Visual moderno em tons de azul escuro (`#0B1320`), painéis metálicos e detalhes ciano neon (`#40CFFF`).
- **Arquitetura Assíncrona (`QThread`):** As consultas aos modelos de IA, ferramentas e geração de áudio rodam 100% em segundo plano, garantindo que a tela nunca congele.
- **Seletor Dinâmico de Modelos:** Troque entre DeepSeek, Gemini, Claude, GPT e Llama diretamente no menu da janela, sem reiniciar nada.
- **Botão de Áudio (TTS):** Ative ou silencie a voz com um único clique (`[🔊 ÁUDIO ATIVO]` / `[🔇 MUDO]`).
- **Indicador de Conexão Simpress:** Exibe se o servidor local `127.0.0.1:8000` está online e a contagem de máquinas.
- **Chips de Perguntas Rápidas:** Botões com um clique para consultar totais do inventário, chamados abertos, máquinas sem usuário logado e status de automação.
- **Badges de Ferramentas:** Mostra visualmente quais ferramentas o Jarvis consultou para responder (ex.: `🔧 consultar_equipamento`).

---

## 🧠 Catálogo de Modelos (OpenRouter)

| # | Modelo | Características |
| :-: | :--- | :--- |
| **1** | `deepseek/deepseek-v4.1-flash-1017` | **Prioridade Máxima:** Raciocínio afiado, custo ultra-baixo e velocidade extrema. |
| **2** | `deepseek/deepseek-v4.1-flash` | Versão estável do DeepSeek Flash. |
| **3** | `google/gemini-2.5-flash` | **Fallback:** Resposta em milissegundos e suporte a contexto massivo. |
| **4** | `openai/gpt-4o-mini` | Precisão cirúrgica em chamadas de ferramentas e estabilidade. |
| **5** | `meta-llama/llama-3.3-70b-instruct` | Modelo aberto de ponta da Meta. |
| **6** | `anthropic/claude-haiku-5.5:batch` | Respostas polidas e objetivas da Anthropic. |

---

## 🛠️ Ferramentas Locais Disponíveis

O Jarvis consulta o Simpress através das seguintes ferramentas em `tools/simpress_tools.py`:

1. `consultar_equipamento(serial)`: Localiza qualquer máquina por número de série (trata automaticamente séries de MacBook com ou sem o prefixo `S`).
2. `pesquisar_catalogo(termo, cidade, categoria, usuario)`: Filtra máquinas por cidade, tipo ou status de usuário logado.
3. `obter_totais_inventario()`: Informa o total oficial de computadores, unidades e alterações pendentes.
4. `listar_chamados_abertos()`: Lista chamados e ordens de serviço (OS) em andamento.
5. `consultar_status_automacao()`: Verifica o andamento das automações de navegador no Chrome.
6. `consultar_ultima_comparacao()`: Exibe o resumo do último cruzamento de planilhas Simpress x Endpoint.

---

## 🛡️ Segurança e Privacidade (LGPD)

- **Apenas Leitura:** O Jarvis não tem permissão para gravar, deletar ou modificar bases ou planilhas operacionais.
- **Sanitização de Dados:** Antes de enviar qualquer texto para a IA, o Jarvis remove endereços detalhados e mascara e-mails e telefones.
- **Privacidade no Provedor:** As requisições ao OpenRouter utilizam o parâmetro `data_collection: "deny"`, proibindo o uso dos dados para treinamento.
