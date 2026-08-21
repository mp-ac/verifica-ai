# 🔒 SECURITY — Auditoria de Segurança VerificaAI

> **Metodologia:** OWASP ZAP (Zed Attack Proxy) — análise estática (SAST) via Bandit + revisão manual de código  
> **Data:** 2026-08-19  
> **Versão auditada:** 1.3.0  
> **Escopo:** Todos os arquivos em `src/`, configurações Docker, variáveis de ambiente e dependências

---

## Sumário Executivo

| Severidade   | Qtd | Descrição resumida                                    |
|:-------------|:---:|:------------------------------------------------------|
| 🔴 Alta      |  4  | Tokens em texto claro, IDOR, vazamento de exceções, ausência de CORS |
| 🟠 Média     |  6  | SQL dinâmico, sem rate limiting, sem security headers, Redis sem auth, timing attack, Docker root |
| 🟡 Baixa     |  4  | Docs expostos, token hardcoded em `.env.example`, logging insuficiente, `.dockerignore` incompleto |
| 🔵 Info      |  2  | Ausência de pip-audit no CI, sem política de divulgação responsável |

---

## 🔴 Severidade Alta

### SEC-01 — Tokens de API armazenados em texto claro (CWE-256)

**OWASP ZAP ID:** 10024 (Information Disclosure — Sensitive Data in Storage)  
**OWASP Top 10:** A02:2021 — Cryptographic Failures

**Localização:**
- `src/auth/repository.py` — coluna `token TEXT NOT NULL` (linhas 20-27)
- `src/auth/validators.py` — comparação direta `token = ?` (linha 229)

**Problema:** Os tokens Bearer das aplicações consumidoras são gravados no SQLite **sem hash**. Um invasor com acesso ao arquivo `db/auth.sqlite3` obtém imediatamente todos os tokens válidos.

**Correção recomendada:**
1. Ao criar um token, gerar com `secrets.token_urlsafe(32)`.
2. Armazenar apenas `sha256(token)` na coluna `token_hash` do banco.
3. Retornar o token em texto claro **somente** na resposta `POST /admin/tokens` (única vez).
4. Na validação (`get_token_by_value`), fazer `WHERE token_hash = ?` com `hashlib.sha256(input).hexdigest()`.
5. Migrar tokens existentes com um script de hash one-way.

---

### SEC-02 — Endpoint `/status/{task_id}` sem autenticação (CWE-284 / IDOR)

**OWASP ZAP ID:** 10105 (Insufficient Authentication)  
**OWASP Top 10:** A01:2021 — Broken Access Control

**Localização:**
- `src/main.py` — `GET /status/{task_id}` (linhas 174-202)

**Problema:** Qualquer pessoa que conheça (ou adivinhe) um `task_id` pode consultar o resultado completo de uma análise, incluindo a resposta final e dados de execução. Os IDs do RQ são UUIDs previsíveis.

**Correção recomendada:**
1. Adicionar `Depends(verify_bearer_token)` ao endpoint.
2. Validar que o `application_id` do token corresponde ao que originou o job (tabela `analyze_requests`).
3. Considerar retornar IDs opacos (HMAC do UUID + secret) em vez de UUIDs puros.

---

### SEC-03 — Vazamento de stack traces internos via API (CWE-209)

**OWASP ZAP ID:** 10023 (Information Disclosure — Debug Error Messages)  
**OWASP Top 10:** A09:2021 — Security Logging and Monitoring Failures

**Localização:**
- `src/main.py` — linha 199: `error=str(job.exc_info)`
- `src/reanalysis/api.py` — linha 121: `error=str(job.exc_info)`

**Problema:** `job.exc_info` contém o traceback completo do Python, incluindo caminhos do servidor, nomes de módulos internos e potencialmente dados sensíveis. Esse conteúdo é retornado diretamente ao cliente.

**Correção recomendada:**
1. Retornar uma mensagem genérica ao cliente: `"A análise falhou. Contate o suporte."`.
2. Registrar o traceback completo apenas nos logs internos com `logger.error(...)`.
3. Incluir um `correlation_id` na resposta para rastreio.

---

### SEC-04 — Ausência total de configuração CORS (CWE-942)

**OWASP ZAP ID:** 10098 (Cross-Domain Misconfiguration)  
**OWASP Top 10:** A05:2021 — Security Misconfiguration

**Localização:**
- `src/main.py` — nenhuma instância de `CORSMiddleware`
- `.env.example` — `APP_ORIGINS` definido mas nunca utilizado (linha 4)

**Problema:** A variável `APP_ORIGINS` existe no `.env.example` mas **não é consumida** pelo código. Sem `CORSMiddleware`, o comportamento depende inteiramente do navegador/proxy. Em produção sem proxy reverso com CORS, a API ficará inacessível a frontends legítimos ou, pior, acessível a qualquer origem.

**Correção recomendada:**
```python
from fastapi.middleware.cors import CORSMiddleware

origins = [o.strip() for o in os.getenv("APP_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)
```

---

## 🟠 Severidade Média

### SEC-05 — Construção dinâmica de SQL com f-strings (CWE-89)

**OWASP ZAP ID:** 40018 (SQL Injection)  
**Bandit:** B608 (hardcoded_sql_expressions)

**Localização:**
- `src/analyze_requests.py` — linhas 97, 101-102
- `src/auth/repository.py` — linha 164

**Problema:** Embora os valores sejam parametrizados com `?`, a **estrutura da query** é construída com f-strings. No `analyze_requests.py`, a cláusula `WHERE` é interpolada diretamente. No `repository.py`, os nomes das colunas em `updates` vêm de lógica controlada (não de input do usuário), reduzindo o risco real — mas a prática viola o princípio de defesa em profundidade.

**Correção recomendada:**
1. Em `analyze_requests.py`, usar uma query fixa com `WHERE (? IS NULL OR application_id = ?)`.
2. Em `repository.py`, validar explicitamente os nomes de coluna contra uma allowlist antes de usá-los no `join`.

---

### SEC-06 — Ausência de Rate Limiting (CWE-770)

**OWASP ZAP ID:** 10049 (Storable and Cacheable Content / no rate limit)  
**OWASP Top 10:** A04:2021 — Insecure Design

**Localização:**
- `src/main.py` — todos os endpoints, especialmente `POST /analyze` e `POST /admin/tokens`

**Problema:** Nenhum mecanismo de rate limiting está implementado. Um atacante pode:
- Exaurir os workers RQ com requisições massivas em `/analyze`
- Tentar força bruta em tokens admin via `/admin/tokens`
- Gerar custos com chamadas a LLMs (Google Gemini, OpenAI)

**Correção recomendada:**
1. Adicionar `slowapi` ou middleware customizado com Redis para limitar requisições.
2. Limites sugeridos: `/analyze` → 10 req/min por token; `/admin/*` → 5 req/min por IP.
3. Retornar HTTP 429 com header `Retry-After`.

---

### SEC-07 — Ausência de Security Headers (CWE-693)

**OWASP ZAP ID:** 10038, 10020, 10021, 10037, 10036  
**OWASP Top 10:** A05:2021 — Security Misconfiguration

**Problema:** A API não define nenhum dos seguintes headers de segurança:
- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Cache-Control: no-store` (para respostas sensíveis)

**Correção recomendada:**
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

### SEC-08 — Redis sem autenticação (CWE-306)

**OWASP Top 10:** A07:2021 — Identification and Authentication Failures

**Localização:**
- `docker-compose.example.yml` — serviço `verificaai-redis` (linhas 101-108)
- `.env.example` — `REDIS_URL=redis://localhost:6379/0` (sem senha)

**Problema:** O Redis é exposto sem senha (`requirepass`). Qualquer container na mesma rede Docker pode ler/escrever dados de jobs, incluindo resultados de análise e tokens.

**Correção recomendada:**
1. Adicionar `command: redis-server --requirepass ${REDIS_PASSWORD}` no `docker-compose.yml`.
2. Atualizar a URL: `REDIS_URL=redis://:${REDIS_PASSWORD}@verificaai-redis:6379/0`.
3. Não expor a porta 6379 fora da rede Docker.

---

### SEC-09 — Comparação de tokens vulnerável a timing attack (CWE-208)

**OWASP Top 10:** A02:2021 — Cryptographic Failures

**Localização:**
- `src/auth/validators.py` — linha 47: `credentials.credentials not in admin_tokens`
- `src/auth/repository.py` — linha 229: comparação SQL via `WHERE token = ?`

**Problema:** A comparação de admin tokens usa o operador `in` do Python sobre um `set`, que não é constant-time. Um atacante sofisticado pode medir diferenças de tempo para inferir caracteres do token.

**Correção recomendada:**
```python
import hmac

def _safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

# Em verify_admin_token:
if not any(_safe_compare(credentials.credentials, t) for t in admin_tokens):
    raise HTTPException(status_code=401, detail="Token não autorizado")
```

---

### SEC-10 — Container Docker roda como root (CWE-250)

**OWASP Top 10:** A05:2021 — Security Misconfiguration

**Localização:**
- `Dockerfile.example` — nenhuma instrução `USER`

**Problema:** O processo uvicorn roda como `root` dentro do container. Se um atacante explorar uma vulnerabilidade (ex: prompt injection que executa código via LLM), ele terá acesso root ao filesystem do container.

**Correção recomendada:**
```dockerfile
RUN addgroup --system app && adduser --system --ingroup app app
USER app
```

---

## 🟡 Severidade Baixa

### SEC-11 — Documentação Swagger/OpenAPI habilitável em produção (CWE-200)

**Localização:**
- `src/main.py` — linha 58: `DOCS_URL_ENABLED`
- `.env.example` — `DOCS_URL_ENABLED=true`

**Problema:** Se a variável não for explicitamente desativada em produção, a documentação interativa `/docs` ficará acessível, revelando todos os endpoints, schemas e parâmetros da API.

**Correção recomendada:**
1. Inverter o default para `false` no `.env.example` e no código.
2. Considerar proteger `/docs` com `verify_admin_token`.

---

### SEC-12 — Token de exemplo hardcoded no `.env.example` (CWE-798)

**Localização:**
- `.env.example` — linha 28: `FINAL_RESULTS_API_TOKEN="6f9c7ceed00d..."`

**Problema:** Um token de aparência real está no arquivo de exemplo versionado. Desenvolvedores podem usá-lo acidentalmente em staging/produção.

**Correção recomendada:**
1. Substituir por um placeholder: `FINAL_RESULTS_API_TOKEN=""`.
2. Adicionar comentário: `# Gere com: python -c "import secrets; print(secrets.token_hex(32))"`.

---

### SEC-13 — Logging de segurança insuficiente (CWE-778)

**OWASP Top 10:** A09:2021 — Security Logging and Monitoring Failures

**Problema:** Não há logging estruturado para:
- Tentativas de autenticação falhadas (401)
- Tokens admin inválidos
- Payloads com attachments rejeitados
- Ações administrativas (CRUD de tokens)

**Correção recomendada:**
1. Adicionar log em cada `raise HTTPException(status_code=401, ...)` nos validators.
2. Usar formato JSON estruturado com campos: `event`, `ip`, `token_id`, `timestamp`.
3. Registrar ações admin com audit trail.

---

### SEC-14 — `.dockerignore` incompleto (CWE-200)

**Localização:**
- `.dockerignore` — não exclui `db/`, `tests/`, `.env.*.example`, `*.md`

**Problema:** Arquivos de banco de dados local e testes podem ser copiados para a imagem Docker, aumentando a superfície de ataque e o tamanho da imagem.

**Correção recomendada:**
```
db/
tests/
*.md
.github/
.agent/
prompts/*.example
```

---

## 🔵 Informativo

### SEC-15 — Ausência de análise de dependências no CI (SCA)

**Problema:** O projeto não possui pipeline CI/CD com scanning de dependências (SAST/SCA). Vulnerabilidades em pacotes como `requests`, `langchain`, `qdrant-client` não serão detectadas automaticamente.

**Correção recomendada:**
1. Adicionar `pip-audit` e `bandit` ao GitHub Actions.
2. Considerar Dependabot ou Renovate para atualizações automáticas.
3. Exemplo de step:
```yaml
- name: Security Scan
  run: |
    pip install bandit pip-audit
    bandit -r src/ -ll -f json -o bandit-report.json
    pip-audit --fix --dry-run
```

---

### SEC-16 — Ausência de política de divulgação responsável

**Problema:** O projeto não possui instruções para pesquisadores de segurança reportarem vulnerabilidades de forma responsável.

**Correção recomendada:** Adicionar uma seção neste documento ou criar `SECURITY_POLICY.md`:
```markdown
## Reportando Vulnerabilidades
Envie um e-mail para seguranca@mpac.mp.br com:
- Descrição da vulnerabilidade
- Passos para reprodução
- Impacto estimado
Responderemos em até 72 horas.
```

---

## Resultados do Bandit (SAST)

| ID   | Arquivo                            | Linha | Severidade | Confiança | CWE   | Descrição                                    |
|:-----|:-----------------------------------|:-----:|:----------:|:---------:|:-----:|:---------------------------------------------|
| B608 | `src/analyze_requests.py`          |  97   |   Média    |   Média   | CWE-89  | SQL construído com f-string                |
| B608 | `src/analyze_requests.py`          |  101  |   Média    |   Média   | CWE-89  | SQL construído com f-string                |
| B608 | `src/auth/repository.py`           |  164  |   Média    |   Média   | CWE-89  | SQL construído com f-string                |
| B113 | `src/final_results.py`             |  68   |   Média    |   Baixa   | CWE-400 | Falso positivo (timeout presente)          |
| B113 | `src/reanalysis/verificaai_painel.py` | 42 |   Média    |   Baixa   | CWE-400 | Falso positivo (timeout presente)          |
| B113 | `src/reanalysis/verificaai_painel.py` | 91 |   Média    |   Baixa   | CWE-400 | Falso positivo (timeout presente)          |

> **Nota:** Os alertas B113 são falsos positivos — o `timeout` está presente nas chamadas. O Bandit não reconhece a variável passada como argumento nomeado em certas configurações.

---

## Matriz de Priorização

| #      | Descrição                      | Esforço | Impacto | Prioridade |
|:-------|:-------------------------------|:-------:|:-------:|:----------:|
| SEC-01 | Hash de tokens                 |  Médio  |  Alto   |   **P0**   |
| SEC-02 | Autenticação em `/status`      |  Baixo  |  Alto   |   **P0**   |
| SEC-03 | Sanitizar erros na resposta    |  Baixo  |  Alto   |   **P0**   |
| SEC-04 | Configurar CORS                |  Baixo  |  Alto   |   **P0**   |
| SEC-06 | Rate limiting                  |  Médio  |  Alto   |   **P1**   |
| SEC-07 | Security headers               |  Baixo  |  Médio  |   **P1**   |
| SEC-08 | Redis com senha                |  Baixo  |  Médio  |   **P1**   |
| SEC-09 | Timing-safe comparison         |  Baixo  |  Médio  |   **P1**   |
| SEC-10 | Non-root container             |  Baixo  |  Médio  |   **P1**   |
| SEC-05 | Refatorar SQL dinâmico         |  Médio  |  Médio  |   **P2**   |
| SEC-11 | Docs desabilitados por padrão  |  Baixo  |  Baixo  |   **P2**   |
| SEC-12 | Remover token de exemplo       |  Baixo  |  Baixo  |   **P2**   |
| SEC-13 | Logging de segurança           |  Médio  |  Médio  |   **P2**   |
| SEC-14 | `.dockerignore` completo       |  Baixo  |  Baixo  |   **P3**   |
| SEC-15 | SCA no CI                      |  Médio  |  Médio  |   **P3**   |
| SEC-16 | Política de divulgação         |  Baixo  |  Baixo  |   **P3**   |

---

## Referências

- [OWASP Top 10:2021](https://owasp.org/Top10/)
- [OWASP ZAP Alert Reference](https://www.zaproxy.org/docs/alerts/)
- [OWASP ASVS v4.0](https://owasp.org/www-project-application-security-verification-standard/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
