# Decisões de arquitetura

## ADR 001 Escopo pequeno e observável

Status: aceita em 28 de outubro de 2026.

Contexto: demonstrar um conceito comum em empresas e diretamente relacionado à vaga Python júnior, sem esconder fundamentos atrás de infraestrutura desnecessária.

Decisão: implementar cadastro de parceiros com API REST, regras explícitas, persistência, erros e testes. A operação é inteiramente sintética. Não fazer scoring, concessão de crédito ou consulta a pessoas.

Consequência: o serviço é pequeno o suficiente para explicar cada caminho. Não representa uma operação financeira real ou um produto contratado pela byx.

## ADR 002 SQLite em arquivo com SQLAlchemy

Status: aceita.

Contexto: o projeto precisa de persistência reproduzível e testes que atravessem o banco real, sem depender de um daemon Docker para executar o exercício básico.

Decisão: SQLite em arquivo, SQLAlchemy 2 e constraint de unicidade para o código. A sessão de cada request é independente; conflito de integridade faz rollback antes de responder `409`. Consultas usam binding de parâmetros. Paginação é ordenada e limitada.

Consequência: o arquivo sobrevive a novas instâncias da aplicação, algo verificado por teste. Contenção de escrita é limitada pelo SQLite. Não extrapolar os resultados para PostgreSQL concorrente ou escala de produção. Schema inicial usa `create_all`; migrations não fazem parte desse escopo pequeno.

## ADR 003 Chave local explícita e sem segredo padrão

Status: aceita.

Contexto: o endpoint de catálogo precisa demonstrar uma barreira de acesso sem sugerir que uma autenticação simulada é um provedor de identidade real.

Decisão: startup exige chave definida em ambiente, com 32 a 256 caracteres ASCII URL-safe. Comparação de bytes em tempo constante. O placeholder do exemplo é recusado. Não existem chaves reais no repositório. Fixtures usam texto sintético exclusivo para testes.

Consequência: a chave protege o catálogo como um todo e não identifica pessoas ou empresas. Produção exigiria TLS, rotação, identidade, autorização e limitação de consumo apropriadas. `/health` e o contrato OpenAPI continuam públicos.

## ADR 004 Testar contratos e falhas em vez de perseguir uma nota

Status: aceita.

Decisão: casos automatizados verificam o estado persistido, o contrato HTTP, conflitos, entradas inválidas, limites e isolamento dos fixtures. Validação por Ruff, pytest, cobertura por ramo e auditoria de dependências. Evidência pública inclui fonte identificável e JUnit sanitizado; logs brutos ficam ignorados.

Consequência: a contagem representa os casos executados, incluindo parâmetros de limites distintos, e não um índice universal de competência. Teste local, CI e implantação são estados diferentes. Não há benchmark de carga ou alegação de operação produtiva.

## ADR 005 Assistência de IA declarada

Status: aceita.

Decisão: manter descrição clara do processo assistido, das decisões, da validação e dos limites. O portfólio serve para estudo, revisão externa e apresentação de competências que seu responsável consiga explicar.

Consequência: autoria do portfólio não é uma declaração de digitação exclusivamente humana. Uma revisão externa deve avaliar o comportamento e suas evidências, e não inferir qualidade pelo estilo ou pela ferramenta usada.
