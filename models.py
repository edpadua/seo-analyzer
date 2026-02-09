from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Adicionado para evitar o erro de 'invalid keyword argument' no login do Google
    name = Column(String, nullable=True) 
    
    # Configurações de IA
    ai_provider = Column(String, default="gemini")
    ai_api_key = Column(String, nullable=True)
    ai_model = Column(String, nullable=True)
    
    # Chaves de API de Serviços Terceiros
    pagespeed_api_key = Column(String, nullable=True)
    openpagerank_api_key = Column(String, nullable=True)
    serpapi_key = Column(String, nullable=True)

    # Relacionamentos
    audits = relationship("AuditHistory", back_populates="owner", cascade="all, delete-orphan")
    rankings = relationship("KeywordTracking", back_populates="user")

class AuditHistory(Base):
    """
    Modelo para armazenar os relatórios técnicos e as sugestões da Inteligência Artificial.
    """
    __tablename__ = "audit_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Dados da pesquisa
    url = Column(String, nullable=False)
    keyword = Column(String, nullable=False)
    
    # Pontuações Técnicas (0 a 100)
    score_performance = Column(Float, default=0.0)
    score_on_page = Column(Float, default=0.0)
    score_semantic = Column(Float, default=0.0)
    score_authority = Column(Float, default=0.0)
    score_schema = Column(Float, default=0.0)
    
    # Conteúdo do Relatório
    report_html = Column(Text, nullable=True) # Guarda o HTML gerado pelo motor técnico
    
    # Insights da IA (Armazenado como String JSON)
    ai_insights_json = Column(Text, nullable=True) 

    # Metadados
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento inverso
    owner = relationship("User", back_populates="audits")

    def to_dict(self):
        """Auxiliar para converter o objeto em dicionário se necessário"""
        return {
            "id": self.id,
            "url": self.url,
            "keyword": self.keyword,
            "scores": {
                "performance": self.score_performance,
                "on_page": self.score_on_page,
                "semantic": self.score_semantic,
                "authority": self.score_authority,
                "schema": self.score_schema
            },
            "date": self.created_at.strftime("%d/%m/%Y %H:%M")
        }

class KeywordTracking(Base):
    __tablename__ = "keyword_tracking"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    url = Column(String)
    keyword = Column(String)
    position = Column(Integer) # Posição 1 a 100
    created_at = Column(DateTime, server_default=func.now())

    # Relacionamento para facilitar consultas
    user = relationship("User", back_populates="rankings")