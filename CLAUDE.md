# RPA Validator

Validador determinístico de RPAs (documentos Word) contra a planilha de conferência do mês.
MVP na Google Cloud: FastAPI + React/Vite num único serviço **Cloud Run**; Firestore, Firebase Auth e Secret Manager.

## Documentação (fonte da verdade)

**Toda a documentação do projeto está no Notion:**
https://app.notion.com/p/RPA-Validator-40ed86365ab480ddae53c691956a02ef?source=copy_link

| Página | Para quê |
| --- | --- |
| [01 · Visão geral e decisões](https://app.notion.com/p/40ed86365ab48186a486c852e766acdc) | Objetivo, escopo, decisões D1–D7, pendências |
| [02 · Arquitetura e dados](https://app.notion.com/p/40ed86365ab481e19cf4fcea979680c4) | Fluxos, collections, variáveis de ambiente, segurança, estrutura de arquivos, rotas |
| [03 · Plano de implementação](https://app.notion.com/p/40ed86365ab481eab62fc77da4b64ed4) | Global constraints, review focus e as tarefas T01–T13 com código |
| [04 · Kanban de desenvolvimento](https://app.notion.com/p/e51d624015754fc689b34d8101c667ab) | Fila de execução (views *Quadro* e *Fila do agente*) |
| [05 · Protocolo dos agentes](https://app.notion.com/p/40ed86365ab48150a960fb73a92d3c7b) | Como implementador e revisor consomem o kanban; portões humanos |

- Em caso de divergência entre este arquivo e o Notion, **vale o Notion**. Avise o humano e corrija este arquivo.
- Os agentes precisam do conector do Notion ativo na sessão. Sem ele, **pare e avise**; não trabalhe de memória.
- Desvio do plano: corrigir o mínimo, registrar em **Observações** do card o que mudou e por quê.
  Se a correção mudar uma interface usada por tarefa posterior, marcar o card como *Bloqueado* e pedir decisão humana.

## Stack

- **Backend:** Python, FastAPI, pandas; testes com pytest; lint com `ruff`. Código em `backend/app/`.
- **Front-end:** React + Vite + TypeScript, servido pelo FastAPI (`STATIC_DIR`). Código em `frontend/src/`.
- **Extração:** LibreOffice (Word → texto) com Tesseract como reserva.
- **GCP:** Cloud Run, Firestore, Firebase Auth, Secret Manager, Cloud Logging.
- Variáveis de ambiente e rotas: página 02 do Notion.

## Fluxo de trabalho: um card, uma branch, um PR

- **Branch principal: `main`**, protegida. Nada entra nela sem Pull Request, CI verde e revisão. **O merge é sempre humano.**
- **Uma branch por card/feature**, criada a partir da `main` atualizada: `tarefa/<id-do-card>-<slug>` (ex.: `tarefa/RPA-1-dinheiro`).
- **Um agente, um card por vez.** Cada tarefa roda isolada num worktree (skill `using-git-worktrees`).
- Commits pequenos, no fim de cada passo do plano (teste falha → implementação → teste passa). Mensagens em português, no imperativo.
- **PR:** título `<id> · <título do card>`; use o template em `.github/pull_request_template.md`.
- Nunca fazer push direto na `main`, `push --force` nem `gh pr merge` (bloqueados em `.claude/settings.json`).

### Kanban (campos do card)
Status: *Backlog* → *Pronto p/ agente* → *Em desenvolvimento* (preencher **Branch**) → *Em revisão* (preencher **Pull request**, **Responsável** = Agente revisor) → *Concluído*. *Bloqueado* quando o agente não resolve sozinho (motivo em **Observações**).
Pegar o card de menor **Ordem** na view *Fila do agente*, só se todos os cards em **Depende de** estiverem *Concluído*. Não mover cards dependentes: isso ocorre quando o card chega a *Concluído*.

## Papéis

| Papel | Agente | Faz | Não faz |
| --- | --- | --- | --- |
| **Planejador** | `planejador` | Planeja demandas **novas** (sem card): requisitos, abordagem, plano e cards propostos | Escrever código |
| **Pesquisador** | `pesquisador` | Consulta docs de bibliotecas e do GCP; devolve resumo com fontes | Alterar arquivos |
| **Codificador** | `codificador` | Executa UM card em TDD na branch `tarefa/<id>-<slug>`, abre o PR, move o card para *Em revisão* | Revisar o próprio PR; mudar decisões; mexer em card de outro responsável |
| **Revisor** | `revisor` | Revisa o PR contra a página do plano e o critério de aceite; aprova ou devolve | Implementar correções no mesmo PR |
| **Tester** | `tester` | Escreve testes/casos de borda, roda a suíte completa e reporta | Alterar código de produção |
| **Depurador** | `depurador` | Acha a causa raiz de falhas (testes, CI) e propõe correção mínima com teste de regressão | Corrigir sem causa raiz; tocar na `main` |
| **Deployer** | `deployer` | Prepara Dockerfile e workflows, roda `docker build` local | Provisionar ou publicar na GCP |
| **Humano** | (você) | Decisões (H01, H02), credenciais e console GCP (T12), aceite final (T13), **merge** | — |

Agentes ficam em `.claude/agents/`. A sessão principal é a orquestradora: despacha um `codificador` por card e depois o `revisor`. O planejador só entra para trabalho fora do kanban.

## Regra de ouro: modelo e esforço (custo de tokens)

**Padrão do projeto: Sonnet 5.5 (`claude-sonnet-5-5`), esforço *médio* ou *alto*.** Subir de modelo ou de esforço é exceção, não rotina.

| Papel | Modelo | Esforço | Por quê |
| --- | --- | --- | --- |
| Sessão principal (orquestra) | Sonnet 5.5 | médio | Só despacha e integra; o trabalho pesado fica nos agentes |
| `planejador` | Sonnet 5.5 | **alto** | Erro de plano se multiplica em todas as tarefas seguintes |
| `pesquisador` | Sonnet 5.5 | médio | Busca e resumo com fontes; não precisa de raciocínio profundo |
| `codificador` | Sonnet 5.5 | médio | O plano já traz o código e os testes; é execução guiada em TDD |
| `revisor` | Sonnet 5.5 | **alto** | Última barreira antes do merge; esforço maior que o do codificador |
| `tester` | Sonnet 5.5 | médio | Casos de borda a partir de regras já escritas |
| `depurador` | Sonnet 5.5 | **alto** | Achar causa raiz exige raciocínio; barato comparado a tentativa e erro |
| `deployer` | Sonnet 5.5 | médio | Dockerfile e workflows são padronizados e validados por build |

**Regras**
1. **Esforço antes de modelo.** Se um agente travar, primeiro suba o esforço (médio → alto); só depois considere trocar de modelo.
2. **Fora de questão, sem exceção e nem com aprovação: modelo Fable e esforço `max`.** Nunca escreva `model: fable` nem `effort: max` em agente, skill ou comando, e nunca os selecione na sessão.
   **Opus e `xhigh`: só com aprovação humana explícita.** A aprovação se materializa no humano editando `availableModels` / `maxEffortLevel` em `.claude/settings.json`; o agente não edita essas chaves. Registre em **Observações** do card o motivo e o agente afetado, e volte ao padrão no card seguinte.
3. **Exceções candidatas** (decisão do humano, por card): `revisor` em Opus nos cards de maior risco, como T05 (comparação) e T07 (autenticação); `depurador` em Opus após 3 tentativas sem causa raiz.
4. **Modelo fixado por versão** (`claude-sonnet-5-5`), não pelo alias, para o custo não mudar sem aviso. Trocar de versão é decisão consciente, no `settings.json` e nos agentes.
5. **Travas técnicas** (`.claude/settings.json`): `availableModels: ["claude-sonnet-5-5"]` deixa Fable e Opus indisponíveis no projeto, e `maxEffortLevel: "high"` impede `xhigh` e `max`. Um agente que peça modelo fora da lista cai em modelo de fallback, sem falhar: por isso o `revisor` trata qualquer menção a Fable, Opus, `xhigh` ou `max` em `.claude/` como achado **bloqueante**.
6. **Onde está configurado:** modelo e esforço padrão da sessão em `.claude/settings.json`; por agente, nos campos `model`, `effort` e `maxTurns` de `.claude/agents/*.md`. As variáveis `CLAUDE_CODE_EFFORT_LEVEL` e `CLAUDE_CODE_SUBAGENT_MODEL` sobrepõem esses valores: não as defina no ambiente sem querer.
7. **Haiku** não é usado (sem ganho que compense o risco de erro neste projeto); reavaliar se o custo pesar.

**Hábitos que reduzem tokens**
- Uma sessão por card; `/clear` ao trocar de card e `/compact` quando o contexto crescer.
- Ler só a página do plano do card e as *Global constraints*, não o Notion inteiro; não reler páginas já lidas.
- Cada agente devolve **resumo curto** (resultado, arquivos, saída dos testes), não despejo de arquivos ou logs.
- Rodar testes com saída enxuta (`pytest -q`) e só colar o trecho que falhou.
- `maxTurns` limita cada agente (valores iniciais, ajustar com a prática).
- Não usar *agent teams* (experimental, multiplica o consumo) nem `ultracode` sem aprovação humana.
- Dois agentes em paralelo só quando os cards forem realmente independentes (**Depende de** vazio).

## Como usar o Superpowers neste projeto

O **plano já existe** (Notion, página do card). Portanto, para cards do kanban:
- **Não** rodar `brainstorming` nem `writing-plans`; seguir a página do plano.
- Usar `using-git-worktrees` → `subagent-driven-development` (ou `executing-plans`) → `test-driven-development` → `verification-before-completion` → `requesting-code-review`.
- Em falha inesperada: `systematic-debugging`.
- `brainstorming` só para trabalho **fora** do kanban (ideia nova ainda sem card).
- Não pular a confirmação de que o teste falha **pelo motivo indicado** antes de implementar.

## Regras de código
- Nomes (funções, módulos, scripts, componentes) em **português**.
- **Dinheiro sempre em centavos inteiros**; nunca aritmética de `float` (conversão `repr → Decimal → centavos`; `app/dinheiro.py` é a única fonte de arredondamento).
- `ruff check .` limpo e **suíte inteira** passando, não só o arquivo da tarefa.
- Front-end: `npm test` e `npm run build` passando.

## Definição de pronto (todo card)
- [ ] Testes da tarefa e suíte inteira passando; `ruff check .` limpo (e `npm test` / `npm run build` no front)
- [ ] Critério de aceite do card cumprido e evidenciado no PR
- [ ] Nenhum dado pessoal real versionado; logs sem nome, CPF ou valores de documento
- [ ] Desvios do plano registrados em **Observações**

## CI e publicação na GCP

- **CI** (`.github/workflows/ci.yml`): roda em todo PR para `main` e em todo push de branch `tarefa/**`.
  Backend (`ruff` + `pytest`), front-end (`npm test` + `npm run build`) e `docker build` sem publicar.
  Cada job só roda quando o código correspondente existe (`backend/pyproject.toml`, `frontend/package.json`, `Dockerfile`).
- **Publicação** (`.github/workflows/deploy-gcp.yml`): **manual** (`workflow_dispatch`), só na `main`, e **desligada** até a variável
  de repositório `GCP_DEPLOY_HABILITADO` ser `true`. Autentica por **Workload Identity Federation** (sem chave JSON) e exige aprovação
  humana no *environment* `producao`.
- Agentes **não** executam `gcloud`, `firebase`, `terraform apply` nem `docker push` (T12 é dos humanos; o agente só prepara Dockerfile e roda o build).
- Proteção da `main` (configurar no GitHub, *Settings → Branches*): exigir PR, exigir os checks do CI, bloquear push direto e force-push.

### Tamanho da imagem Docker (custo)
O tamanho da imagem custa em três lugares: **armazenamento no Artifact Registry** (cobrado por GB, por imagem/versão guardada), **partida a frio no Cloud Run** (a imagem precisa ser baixada, e esse tempo conta) e **minutos de CI** (build e push maiores). Confira os preços atuais na GCP no T12.
O componente mais pesado é o **LibreOffice** (decisão D2, junto do Tesseract). Não trocar essa decisão sem o humano; **medir primeiro** e, se o tamanho pesar, levar opções ao humano.

Regras do `Dockerfile` (imagem única, `deployer` e T12):
1. **Multi-stage:** um estágio `node:22-slim` gera o `dist` do front-end; a imagem final é `python:3.12-slim` e recebe só o `dist` (em `STATIC_DIR`). Node, npm e `node_modules` **não** entram na imagem final.
2. **apt enxuto:** `--no-install-recommends`, só o necessário (`libreoffice-writer`, `tesseract-ocr`, `tesseract-ocr-por`), preferindo a variante sem interface gráfica se a base a oferecer; `rm -rf /var/lib/apt/lists/*` **na mesma camada** do `apt-get install`.
3. **pip:** `--no-cache-dir` e apenas dependências de runtime (pytest e ruff ficam fora da imagem final).
4. **`.dockerignore`** mantido (testes, `.git`, `.claude`, `.github`, `.env*`, planilhas, `docs_reais`, `node_modules`); camadas ordenadas da que menos muda (sistema) para a que mais muda (código), para o cache funcionar.
5. **Usuário não-root** e sem ferramentas de build na imagem final.
6. **Medir e registrar:** o CI imprime o tamanho e o histórico de camadas no resumo do job. O PR do T12 informa o tamanho final e as camadas maiores.
7. **Orçamento:** após a primeira medição, o humano define a variável de repositório `IMAGEM_MAX_MB`; a partir daí o CI **falha** se a imagem passar do limite.
8. **Limpeza no Artifact Registry** (humano, T12): política para manter só as últimas N imagens, já que o deploy publica uma tag por commit (`$GITHUB_SHA`).

## Segurança e dados pessoais
- Nenhum dado pessoal real em fixtures versionadas. Amostras reais só em `backend/tests/fixtures/docs_reais/` (**fora do git**; não ler).
- Logs em JSON **sem** nome, CPF ou valores; e-mail sempre mascarado (`th***@empresa.com`).
- Relatórios mostram o número do RPA e o nome ofuscado; dados completos só no Firestore.
- O relatório é uma **página da própria aplicação** (cards-resumo + detalhes da validação); a exportação é **somente PDF e Markdown**. **Não existe HTML exportável**: o HTML é só etapa interna da geração do PDF e deve ter `autoescape=True`.
- Segredos (`FIREBASE_WEB_API_KEY`) só no Secret Manager; nunca no front-end, no repositório nem em logs.
- Nunca ler nem versionar `.env`, `acessos.txt` ou credenciais.

## Pendências humanas
- **H01** · layout da planilha: bloqueia o aceite (T13), não a implementação (o leitor é parametrizável).
- **H02** · validação do CNPJ divergente.
- Detalhes: página 01 do Notion.
