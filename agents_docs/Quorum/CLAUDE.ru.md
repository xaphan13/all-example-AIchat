# CLAUDE.ru.md

> Claude Code читает этот файл. Канонические инструкции для всех харнесов лежат в
> [`AGENTS.ru.md`](AGENTS.ru.md) — прочитайте их перед работой с репозиторием.
> Русская версия. English version: [CLAUDE.md](CLAUDE.md).

---

Этот проект хранит **единый источник истины** для AI-ассистентов в
[`AGENTS.ru.md`](AGENTS.ru.md). Он намеренно не дублируется здесь, чтобы избежать рассинхрона.

**Прежде чем что-либо делать:**
1. Прочитайте [`AGENTS.ru.md`](AGENTS.ru.md) — обзор проекта, конвенции, правила для AI-ассистентов.
2. Прочитайте релевантный документ из [`docs/`](docs/) **перед** открытием исходников:
   - [`docs/01_project_structure.md`](docs/01_project_structure.md) — полное дерево директорий
   - [`docs/02_architecture.md`](docs/02_architecture.md) — архитектура и паттерны
   - [`docs/03_execution_flow.md`](docs/03_execution_flow.md) — поток выполнения
   - [`docs/04_code_quality.md`](docs/04_code_quality.md) — аудит качества и известные подводные камни
   - [`docs/05_optimization_roadmap.md`](docs/05_optimization_roadmap.md) — roadmap оптимизации
3. **Не** обходите рекурсивно весь `backend/src/` или `frontend/src/` — дерево уже
   задокументировано в `docs/01`.

Ключевые правила (полный список в `AGENTS.ru.md`): минимальные изменения, backend остаётся async,
доверяйте `docs/`, а не `README.md`/`ARCHITECTURE.md`, не правьте `docs/` без запроса, не
делайте commit/push без подтверждения.
