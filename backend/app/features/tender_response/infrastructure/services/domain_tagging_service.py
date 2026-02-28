from app.features.tender_response.domain.models import (
    HistoricalAlignmentResult,
    TenderQuestion,
)

DOMAIN_KEYWORDS = {
    "security": ["tls", "encryption", "security", "sso", "authentication", "access"],
    "compliance": ["compliance", "policy", "gdpr", "hipaa", "iso", "soc", "fedramp"],
    "infra": ["backup", "disaster", "uptime", "infrastructure", "hosting", "resilience"],
    "architecture": ["architecture", "api", "saml", "oidc", "integration"],
    "ai": ["ai", "model", "llm", "prompt"],
    "pricing": ["pricing", "cost", "fee", "subscription"],
}


class DomainTaggingService:
    def tag(
        self,
        *,
        question: TenderQuestion,
        generated_answer: str,
        alignment: HistoricalAlignmentResult,
    ) -> str:
        if question.declared_domain:
            return question.declared_domain.strip().lower()
        if alignment.domain:
            return alignment.domain.strip().lower()

        lower_text = f"{question.original_question}\n{generated_answer}".lower()
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(keyword in lower_text for keyword in keywords):
                return domain
        return "general"
