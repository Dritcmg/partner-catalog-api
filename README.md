# Partner Catalog API

API pequena de cadastro de parceiros B2B, construída para demonstrar fundamentos de backend Python: contratos REST, validação, persistência relacional, erros previsíveis e testes automatizados.

O problema escolhido é simples: uma operação que integra originadores, investidores e prestadores precisa manter um catálogo consistente de parceiros. O projeto usa somente organizações sintéticas. Não concede crédito, não calcula risco e não acessa sistemas de empresas.

Projeto de portfólio de **Adriano Camargo de Oliveira**, desenvolvido com assistência de IA declarada em [AI_ASSISTANCE.md](AI_ASSISTANCE.md). A motivação usa o contexto público de APIs modulares e integração de parceiros descrito pela [byx](https://byx.com.br/), sem vínculo, encomenda ou validação da empresa.

## O que demonstrar em cinco minutos

1. Criar um parceiro com código único e receber `201` com `Location`.
2. Tentar repetir o código e observar `409`, sem corromper a sessão do banco.
3. Consultar com paginação limitada e filtro por estado ativo.
4. Alterar somente os campos enviados e excluir um registro.
5. Reiniciar a aplicação e consultar o mesmo SQLite persistido.
6. Executar os testes, incluindo falhas de autenticação e validação.

## Stack e decisões

- Python 3.12, FastAPI e Pydantic 2.
- SQLAlchemy 2 com SQLite em arquivo e constraints no banco.
- Pytest, TestClient, Ruff, cobertura por linha/ramo e pip-audit.
- OpenAPI e configuração para terminal, depuração e testes no VS Code.

É um serviço de catálogo com um único perfil de acesso. SQLite e uma chave local mantêm o exercício pequeno e reproduzível. Multi-tenancy, autenticação corporativa, migrations e processamento assíncrono pertencem a escopos maiores. As decisões e os limites estão em [docs/DECISIONS.md](docs/DECISIONS.md).

## Execução local no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PARTNER_API_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
$env:PARTNER_DATABASE_URL = 'sqlite:///./var/partners.db'
.\.venv\Scripts\python.exe -m uvicorn partner_catalog.main:create_app --factory --host 127.0.0.1 --port 8011
```

Mantenha essa chave na sessão local e use outro terminal com o mesmo valor para fazer chamadas. Não publique `.env`, valores da chave ou dados reais. A aplicação não carrega `.env` sozinha. No VS Code, o launch configurado pode ler uma cópia local de `.env.example` chamada `.env`, depois de substituir o placeholder por uma chave própria. É necessária a extensão Python Debugger para esse launch; a execução no terminal não depende dela.

## Linux ou macOS

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
export PARTNER_API_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export PARTNER_DATABASE_URL='sqlite:///./var/partners.db'
.venv/bin/python -m uvicorn partner_catalog.main:create_app --factory --host 127.0.0.1 --port 8011
```

No VS Code em Linux/macOS, selecione `.venv/bin/python` como interpretador. O valor padrão do arquivo de settings atende à máquina Windows usada no desenvolvimento.

## Contrato REST

Os endpoints de catálogo exigem `X-API-Key`. `/health`, `/docs` e `/openapi.json` são públicos e não expõem registros do catálogo. A especificação está também em [docs/openapi.json](docs/openapi.json).

| Método | Endpoint | Resultado |
| --- | --- | --- |
| POST | `/v1/partners` | `201`, registro e `Location` |
| GET | `/v1/partners?limit=20&offset=0&active=true` | Lista ordenada por código e total filtrado |
| GET | `/v1/partners/{uuid}` | Registro ou `404` |
| PATCH | `/v1/partners/{uuid}` | Atualização parcial; objeto vazio e valores nulos são rejeitados |
| DELETE | `/v1/partners/{uuid}` | `204`, sem corpo; exclusão definitiva |
| GET | `/health` | `SELECT 1` e estado básico da aplicação |

Exemplo de corpo sintético:

```json
{
  "code": "DEMO-001",
  "display_name": "Synthetic Originator",
  "category": "originator",
  "active": true
}
```

Categorias aceitas: `originator`, `investor`, `servicer`. Código: 3 a 32 caracteres ASCII maiúsculos, números, hífen ou underscore; primeiro caractere alfanumérico. Nomes: 3 a 120 caracteres depois de remover espaços externos. Paginação: `limit` entre 1 e 100, `offset` não negativo. Campos extras são rejeitados.

```powershell
$headers = @{ 'X-API-Key' = $env:PARTNER_API_KEY }
$body = @{ code='DEMO-001'; display_name='Synthetic Originator'; category='originator' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8011/v1/partners' -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod -Uri 'http://127.0.0.1:8011/v1/partners?limit=10' -Headers $headers
```

Erros esperados: `401 invalid_api_key`, `404 partner_not_found`, `409 partner_code_conflict` e `422` para entradas incompatíveis com o contrato. A chave não identifica uma pessoa nem limita acesso por parceiro: qualquer cliente com a chave local tem acesso ao catálogo inteiro.

## Testes e evidências

```powershell
.\.venv\Scripts\python.exe scripts/verify.py
```

O mesmo comando roda na CI com `python scripts/verify.py`. Executa lint, formato, testes contra SQLite real temporário, cobertura e auditoria das dependências pinadas. Não usa credenciais de produção. Os testes cobrem CRUD, constraints, conflitos, rollback, paginação, filtragem, validação estrita, isolamento entre bancos, persistência após nova instância e ausência de chave/payload nos logs estruturados.

- [evidence/results.json](evidence/results.json): resultados, versões e fingerprint da fonte avaliada.
- [evidence/junit.xml](evidence/junit.xml): casos executados, sem hostname e timestamp da estação.
- `artifacts/`: logs e relatórios locais ignorados pelo Git.
- [CI](https://github.com/Dritcmg/partner-catalog-api/actions): execução independente em Ubuntu após publicação.

A cobertura ajuda a localizar caminhos sem exercício; não é garantia de correção universal. Um scanner sem achados cobre apenas suas regras e os arquivos inspecionados. A auditoria depende de rede e do estado da base de vulnerabilidades no momento da execução.

## Limites conhecidos

- Aplicação demonstrativa local. Não é uma plataforma de crédito nem uma entrega para a byx.
- Autenticação por uma chave de desenvolvimento; sem usuários, papéis, tenants ou provedor de identidade.
- SQLite com timeout de escrita; sem alegação de throughput, alta disponibilidade ou desempenho em produção.
- Edição concorrente do mesmo registro usa o último commit; não há ETag ou histórico de versões.
- Exclusão definitiva e sem trilha de auditoria. Não adequado a registros regulados.
- Schema inicial criado por SQLAlchemy. Evolução de schema exigiria migrations; não executar esta aplicação sobre bases existentes de terceiros.
- Sem rate limiting, TLS, backup automatizado ou publicação de serviço remoto. Bind local por padrão nos exemplos.

## Autoria e licença

MIT para o código produzido neste repositório. Dependências mantêm suas próprias licenças. Consulte [LICENSE](LICENSE), [AI_ASSISTANCE.md](AI_ASSISTANCE.md) e [CONTRIBUTING.md](CONTRIBUTING.md).

## Verificação remota da revisão publicada

A [execução de CI](https://github.com/Dritcmg/partner-catalog-api/actions/runs/40730629787) aprovou **54 testes, sem falhas ou skips**, além de lint e auditoria de dependências. O escopo usa SQLite real e HTTP local. O artefato remoto foi baixado e seu fingerprint conferido com a fonte local. Consulte [evidence/ci-verification.json](evidence/ci-verification.json) para a revisão exata e o resultado; o relatório local inicial tem escopo próprio.
