# Dattos Demo

Demo técnica com os 3 escopos integrados em uma aplicação Python/FastAPI.

## Visão geral

Este projeto demonstra três blocos funcionais:

- **Escopo 1**: conciliação bancária com mecanismo multiestágio, revisão humana, métricas de qualidade e degradação.
- **Escopo 2**: detecção de anomalias em camadas, com explicação e métricas operacionais.
- **Escopo 3**: RAG financeiro com busca híbrida, controle de acesso por perfil, citações, conflito documental e avaliação.

## Principais funcionalidades

### Escopo 1

- Conciliação com match exato, fuzzy, ML e revisão humana.
- Trilha de auditoria de decisões e eventos.
- Métricas de qualidade (`precision`, `recall`, `f1`) e status de degradação.
- Reset de demo e re-seed de dados.

### Escopo 2

- Detecção de anomalias em quatro camadas.
- Métricas de operação e explicabilidade.
- Visualização de histórico e lote atual.

### Escopo 3

- Busca e recuperação de documentos financeiros.
- Perfis de usuário com ACL.
- Cenários de análise de transações.
- Avaliação de desempenho do motor de RAG.

## Tecnologias usadas

- **FastAPI**
- **SQLite**
- **Docker Compose**
- **RapidFuzz**
- **scikit-learn**
- **Jinja2** para templates

## Executando o projeto

```bash
docker compose up --build
```

Em seguida, abra no navegador:

- Aplicação: `http://localhost:8000`
- Documentação Swagger: `http://localhost:8000/docs`

## Estrutura da interface

- `Visão Geral` — dashboard principal.
- `Escopo 1` — conciliação com execução, reset, decisões e fila humana.
- `Escopo 2` — detecção de anomalias e métricas.
- `Escopo 3` — análise de transações com RAG e profiles.
- `Auditoria` — visão combinada de métricas de todos os escopos.

## Endpoints mais importantes

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

### Escopo 2

- `POST /api/escopo2/run`
- `GET /api/escopo2/dataset`
- `GET /api/escopo2/transactions`
- `GET /api/escopo2/last-result`

### Escopo 3

- `GET /api/escopo3/dataset`
- `POST /api/escopo3/analyze`
- `POST /api/escopo3/search`
- `GET /api/escopo3/eval`

### Auditoria

- `GET /api/audit/combined`
- `GET /api/health`

## Como testar rapidamente

1. Suba a aplicação.
2. Acesse a UI em `http://localhost:8000`.
3. No menu, vá para `Escopo 1` e execute a conciliação.
4. Em `Escopo 3`, use os botões de cenário:
   - **TX-1001 / controller** — caso conclusivo.
   - **TX-1003 / controller** — conflito documental.
   - **TX-1004 / auditor** — controle de acesso.
5. Abra `Auditoria` e clique em `Carregar auditoria`.

## Observações importantes

- Se `Escopo 1` não tiver decisões, as métricas de auditoria aparecem como `null` porque ainda não há dados calculados.
- Após `Resetar demo`, os dados são re-seedados automaticamente.
- A interface principal também pode ser explorada via Swagger em `/docs`.

## Estrutura do projeto

```text
app/
  ├── main.py
  ├── scope1_module.py
  ├── escopo2_engine.py
  ├── escopo2_data.py
  ├── escopo3_engine.py
  ├── escopo3_data.py
  ├── scope3_module.py
  ├── templates/
  └── static/

data/
Dockerfile
docker-compose.yml
requirements.txt
README.md
```

## Limitações desta demo

Esta é uma prova de conceito e não um produto final. O foco é demonstrar:

- fluxo de conciliação e auditoria;
- detecção de anomalias explicável;
- motor de RAG com perfil e citações;
- integração UI/API em container.

Limitações intencionais:

- banco em SQLite;
- dados mockados;
- modelo ML simplificado;
- lógica de regras estática.
