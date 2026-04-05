from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    title: str
    company: str
    vendor: str
    source_type: str
    reference: str
    text: str
    version: int
    status: str
    access_roles: List[str]
    tags: List[str]


@dataclass
class TransactionRecord:
    id: str
    company: str
    amount: float
    date: str
    vendor: str
    description: str
    cost_center: str
    expected_status: str
    gold_docs: List[str]


@dataclass
class EvaluationCase:
    query: str
    gold_docs: List[str]


# User roles data
USER_ROLES = ["controller", "analyst", "auditor"]


# Transaction records data
TRANSACTION_RECORDS = [
    TransactionRecord(
        id="TX-1001",
        company="Dattos Brasil",
        amount=12500.0,
        date="2026-04-01",
        vendor="Fornecedor Alfa",
        description="Pagamento NF 98765 fornecedor Alfa",
        cost_center="FIN",
        expected_status="EVIDENCIA_ENCONTRADA",
        gold_docs=["DOC-ALFA-CONTRATO-V2", "DOC-ALFA-EMAIL-APR"],
    ),
    TransactionRecord(
        id="TX-1002",
        company="Dattos Brasil",
        amount=32000.0,
        date="2026-04-02",
        vendor="Consultoria Zeta",
        description="Adiantamento consultoria estratégica abril",
        cost_center="MKT",
        expected_status="EVIDENCIA_INSUFICIENTE",
        gold_docs=[],
    ),
    TransactionRecord(
        id="TX-1003",
        company="Dattos Brasil",
        amount=19800.0,
        date="2026-04-02",
        vendor="CloudNow",
        description="Mensalidade CloudNow abril infraestrutura",
        cost_center="TEC",
        expected_status="CONFLITO_DOCUMENTAL",
        gold_docs=["DOC-CLOUD-CONTRATO-OLD", "DOC-CLOUD-ADITIVO", "DOC-CLOUD-EMAIL"],
    ),
    TransactionRecord(
        id="TX-1004",
        company="Dattos Holding",
        amount=85000.0,
        date="2026-04-03",
        vendor="M&A Advisory",
        description="Success fee M&A projeto Orion",
        cost_center="CORP",
        expected_status="ACESSO_RESTRITO",
        gold_docs=["DOC-MA-MEMO", "DOC-MA-APPROVAL"],
    ),
]


# Document chunks data
DOCUMENT_CHUNKS = [
    DocumentChunk(
        chunk_id="DOC-ALFA-CONTRATO-V2#p2",
        doc_id="DOC-ALFA-CONTRATO-V2",
        title="Contrato Fornecedor Alfa v2",
        company="Dattos Brasil",
        vendor="Fornecedor Alfa",
        source_type="pdf",
        reference="p.2",
        text="Contrato vigente do fornecedor Alfa. Valor mensal aprovado: R$ 12.500,00. NF 98765 coberta pelo contrato operacional de abril.",
        version=2,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["contrato", "nf 98765", "fornecedor alfa", "abril", "12500"],
    ),
    DocumentChunk(
        chunk_id="DOC-ALFA-EMAIL-APR#email1",
        doc_id="DOC-ALFA-EMAIL-APR",
        title="Email de aprovação Alfa",
        company="Dattos Brasil",
        vendor="Fornecedor Alfa",
        source_type="email",
        reference="email thread 18",
        text="Aprovo o pagamento da NF 98765 do fornecedor Alfa no valor de R$ 12.500,00 para fechamento de abril. Assinado: controller@empresa.com",
        version=1,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["aprovacao", "nf 98765", "alfa", "12500", "fechamento"],
    ),
    DocumentChunk(
        chunk_id="DOC-POLICY-PAGAMENTOS#sec4",
        doc_id="DOC-POLICY-PAGAMENTOS",
        title="Política de pagamentos",
        company="Dattos Brasil",
        vendor="",
        source_type="docx",
        reference="seção 4",
        text="Pagamentos acima de R$ 50.000,00 exigem aprovação adicional. Adiantamentos sem contrato exigem evidência complementar.",
        version=3,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["politica", "aprovacao", "adiantamento", "contrato"],
    ),
    DocumentChunk(
        chunk_id="DOC-CLOUD-CONTRATO-OLD#p3",
        doc_id="DOC-CLOUD-CONTRATO-OLD",
        title="Contrato CloudNow antigo",
        company="Dattos Brasil",
        vendor="CloudNow",
        source_type="pdf",
        reference="p.3",
        text="Contrato CloudNow com valor mensal de R$ 18.500,00 para infraestrutura. Documento ainda aparece como vigente no repositório legado.",
        version=1,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["cloudnow", "infraestrutura", "18500", "contrato"],
    ),
    DocumentChunk(
        chunk_id="DOC-CLOUD-ADITIVO#p1",
        doc_id="DOC-CLOUD-ADITIVO",
        title="Aditivo CloudNow abril",
        company="Dattos Brasil",
        vendor="CloudNow",
        source_type="pdf",
        reference="p.1",
        text="Aditivo contratual de abril ajusta o valor mensal da CloudNow para R$ 19.800,00, válido a partir de 01/04/2026.",
        version=2,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["cloudnow", "aditivo", "19800", "abril"],
    ),
    DocumentChunk(
        chunk_id="DOC-CLOUD-EMAIL#email9",
        doc_id="DOC-CLOUD-EMAIL",
        title="Email ajuste CloudNow",
        company="Dattos Brasil",
        vendor="CloudNow",
        source_type="email",
        reference="email thread 9",
        text="Financeiro, o contrato antigo ainda aparece na pasta compartilhada. Para abril, considerar o aditivo de R$ 19.800,00. Favor atualizar o índice documental.",
        version=1,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["cloudnow", "aditivo", "contrato antigo", "indice documental"],
    ),
    DocumentChunk(
        chunk_id="DOC-MA-MEMO#sec2",
        doc_id="DOC-MA-MEMO",
        title="Memorando confidencial M&A",
        company="Dattos Holding",
        vendor="M&A Advisory",
        source_type="pdf",
        reference="seção 2",
        text="Memorando confidencial do projeto Orion. Success fee de R$ 85.000,00 condicionado ao fechamento do deal. Documento confidencial da holding.",
        version=1,
        status="vigente",
        access_roles=["controller", "analyst"],
        tags=["m&a", "orion", "85000", "success fee", "holding"],
    ),
    DocumentChunk(
        chunk_id="DOC-MA-APPROVAL#email3",
        doc_id="DOC-MA-APPROVAL",
        title="Aprovação projeto Orion",
        company="Dattos Holding",
        vendor="M&A Advisory",
        source_type="email",
        reference="email thread 3",
        text="Aprovado o success fee de R$ 85.000,00 da M&A Advisory no projeto Orion. Restrito ao time corporativo e controladoria.",
        version=1,
        status="vigente",
        access_roles=["controller", "analyst"],
        tags=["m&a", "orion", "85000", "aprovado", "restrito"],
    ),
    DocumentChunk(
        chunk_id="DOC-SUPPLIER-MAP#sheet1-row8",
        doc_id="DOC-SUPPLIER-MAP",
        title="Mapa de fornecedores",
        company="Dattos Brasil",
        vendor="Fornecedor Alfa",
        source_type="xlsx",
        reference="aba fornecedores linha 8",
        text="Fornecedor Alfa classificado como fornecedor recorrente com NFs operacionais e valor médio entre R$ 12.000 e R$ 13.000.",
        version=1,
        status="vigente",
        access_roles=["controller", "analyst", "auditor"],
        tags=["fornecedor alfa", "recorrente", "12000", "13000"],
    ),
]


# Evaluation cases data
EVALUATION_CASES = [
    EvaluationCase(
        query="NF 98765 fornecedor Alfa 12500",
        gold_docs=["DOC-ALFA-CONTRATO-V2", "DOC-ALFA-EMAIL-APR"],
    ),
    EvaluationCase(
        query="CloudNow abril 19800 aditivo",
        gold_docs=["DOC-CLOUD-ADITIVO", "DOC-CLOUD-EMAIL"],
    ),
    EvaluationCase(
        query="M&A Orion success fee 85000",
        gold_docs=["DOC-MA-MEMO", "DOC-MA-APPROVAL"],
    ),
]


class DocumentDataRepository:
    """Repository for document and transaction data following clean architecture principles."""

    @staticmethod
    def get_user_roles() -> List[str]:
        """Retrieve available user roles."""
        return USER_ROLES.copy()

    @staticmethod
    def get_transaction_records() -> List[TransactionRecord]:
        """Retrieve transaction records for analysis."""
        return TRANSACTION_RECORDS.copy()

    @staticmethod
    def get_document_chunks() -> List[DocumentChunk]:
        """Retrieve document chunks for retrieval."""
        return DOCUMENT_CHUNKS.copy()

    @staticmethod
    def get_evaluation_cases() -> List[EvaluationCase]:
        """Retrieve evaluation test cases."""
        return EVALUATION_CASES.copy()


# Backward compatibility functions
def mock_roles() -> list[str]:
    """Legacy function for user roles."""
    return DocumentDataRepository.get_user_roles()


def mock_transactions() -> list[dict]:
    """Legacy function for transaction records."""
    return [record.__dict__ for record in DocumentDataRepository.get_transaction_records()]


def mock_chunks() -> list[dict]:
    """Legacy function for document chunks."""
    return [chunk.__dict__ for chunk in DocumentDataRepository.get_document_chunks()]


def mock_eval_cases() -> list[dict]:
    """Legacy function for evaluation cases."""
    return [case.__dict__ for case in DocumentDataRepository.get_evaluation_cases()]
