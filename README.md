# Demo simplificada do Escopo 1

Esta aplicação demonstra, de forma executável, a ideia central do Escopo 1:

- pipeline de conciliação **multi-estágio**;
- matching **exato**, **fuzzy**, **ML** e **revisão humana**;
- **trilha de auditoria** com eventos detalhados;
- **critérios de qualidade** e uma visão simples de **degradação**.

## O que a demo faz

Ao subir a aplicação, ela carrega dados mockados com 5 casos:

1. **EXACT**: match automático por valor + referência.
2. **FUZZY**: match automático por similaridade textual.
3. **ML**: match automático por modelo simples de classificação.
4. **HUMAN por materialidade**: candidato forte, mas o valor exige revisão humana.
5. **HUMAN por baixa confiança**: caso que não atingiu confiança suficiente.

## Stack

- **FastAPI**: API e Swagger rápido para demonstrar o fluxo.
- **SQLite**: persistência simples e portátil para demo.
- **RapidFuzz**: similaridade textual no estágio fuzzy.
- **scikit-learn**: pequeno modelo de Machine Learning para o estágio ML.
- **Docker Compose**: subida simples com um comando.

## Como rodar

```bash
docker compose up --build
```

Depois abra:

- Interface simples: `http://localhost:8000/`
- Swagger: `http://localhost:8000/docs`

## Fluxo sugerido para testar

1. Suba a aplicação.
2. Acesse `/`.
3. Clique em **Executar conciliação**.
4. Veja os resultados em:
   - decisões;
   - eventos de auditoria;
   - métricas de qualidade;
   - status de degradação.
5. Para revisar casos humanos, use a API em `/docs`.

## Exemplo de revisão humana

### Aprovar uma pendência

```http
POST /api/review/4
Content-Type: application/json

{
  "action": "approve",
  "comment": "Aprovado pelo controller"
}
```

### Rejeitar uma pendência

```http
POST /api/review/5
Content-Type: application/json

{
  "action": "reject",
  "comment": "Sem evidência suficiente"
}
```

## Endpoints principais

- `POST /api/reset` — reseta os dados da demo.
- `POST /api/reconcile/run` — executa o pipeline.
- `GET /api/transactions` — lista transações ERP e banco.
- `GET /api/decisions` — mostra decisões com contexto.
- `GET /api/events` — mostra trilha de auditoria.
- `GET /api/review/pending` — mostra fila humana.
- `POST /api/review/{decision_id}` — aprova/rejeita revisão.
- `GET /api/quality` — calcula métricas de qualidade.
- `GET /api/degradation` — compara o estado atual com um baseline.
- `GET /api/health` — healthcheck.

## Como esta demo mapeia para o Escopo 1

### 1. Multi-estágio
O pipeline tenta resolver do mais confiável para o menos confiável:

1. **Exact**
2. **Fuzzy**
3. **ML**
4. **Human review**

### 2. Auditabilidade
Cada etapa gera eventos com:

- versão do pipeline;
- versão do modelo;
- candidatos considerados;
- scores calculados;
- decisão final;
- comentário humano, quando houver.

### 3. Critérios de qualidade
A demo expõe:

- **precision**;
- **recall**;
- **f1**;
- **human queue rate**;
- **auto approval rate**;
- **stage accuracy**.

### 4. Degradação
A API compara o resultado atual com um baseline simples:

- precision mínima esperada;
- taxa máxima de fila humana.

Se sair do intervalo esperado, o status muda para `degraded`.

## Estrutura do projeto

```text
escopo1-demo/
├── app/
│   ├── main.py
│   └── static/
│       └── index.html
├── data/
│   └── lake/
├── docker-compose.yml
├── Dockerfile
├── README.md
└── requirements.txt
```

## Limitações intencionais

Esta é uma demo simplificada para portfólio e avaliação técnica. Ela **não** pretende reproduzir um ambiente produtivo completo.

O que foi simplificado:

- banco SQLite em vez de banco transacional + lake + busca;
- modelo de ML treinado com dados sintéticos;
- UI muito simples;
- regras fixas e thresholds estáticos.

Mesmo assim, ela mostra a ideia central do Escopo 1 com execução prática e rastreável.
