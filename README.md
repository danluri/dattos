# Dattos Demo Unificada v3

Demo única com os 3 escopos do desafio:

- **Escopo 1**: conciliação bancária com matching exato, fuzzy, ML, fila humana, qualidade e degradação.
- **Escopo 2**: detecção de anomalias em 4 camadas, com explicabilidade e métricas.
- **Escopo 3**: RAG financeiro com busca híbrida, ACL por perfil, citações, conflito documental, avaliação e traces.

## Como subir

```bash
docker compose up --build
```

Acesse:

- App: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Destaques

### Escopo 1

- `POST /api/escopo1/run`
- `POST /api/escopo1/reset`
- `GET /api/escopo1/transactions`
- `GET /api/escopo1/decisions`
- `GET /api/escopo1/events`
- `GET /api/escopo1/human-queue`
- `POST /api/escopo1/human-review`
- `GET /api/escopo1/quality`
- `GET /api/escopo1/degradation`

Também existem rotas de compatibilidade do demo individual:

- `POST /api/reconcile/run`
- `GET /api/review/pending`
- `POST /api/review/{decision_id}`
- etc.

### Escopo 2

- `POST /api/escopo2/run`
- `GET /api/escopo2/dataset`
- `GET /api/escopo2/results`

### Escopo 3

- `POST /api/escopo3/analyze`
- `POST /api/escopo3/search`
- `GET /api/escopo3/eval`
- `GET /api/escopo3/traces`
- `POST /api/escopo3/feedback`

## Cenários bons para apresentação

- `TX-1001` com perfil `controller`: caso conclusivo com citações.
- `TX-1003` com perfil `controller`: conflito documental.
- `TX-1004` com perfil `auditor_externo`: acesso restrito por ACL.
