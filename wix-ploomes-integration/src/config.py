import os

class Config:
    """
    Configurações da aplicação.
    Em produção, estas variáveis devem ser definidas como variáveis de ambiente.
    """
    
    # Chave pública do Wix para verificação de JWT
    WIX_PUBLIC_KEY = os.environ.get("WIX_PUBLIC_KEY", "")
    
    # User-Key do Ploomes para autenticação na API
    PLOOMES_USER_KEY = os.environ.get("PLOOMES_USER_KEY", "")
    
    # URL base da API do Ploomes
    PLOOMES_API_BASE = os.environ.get("PLOOMES_API_BASE", "https://api2.ploomes.com")
    
    # ID do Pipeline no Ploomes onde os cartões serão criados
    PLOOMES_PIPELINE_ID = int(os.environ.get("PLOOMES_PIPELINE_ID", "1"))
    
    # ID do Estágio inicial no Ploomes onde os cartões serão criados
    PLOOMES_STAGE_ID = int(os.environ.get("PLOOMES_STAGE_ID", "1"))
    
    # URI de conexão com o MongoDB Atlas
    MONGO_URI = os.environ.get("MONGO_URI", "")

    # Configurações de logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    
    # Configurações do Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "asdf#FGSgvasgf$5$WGT")
    DEBUG = False  # Sempre False em produção
    
    @classmethod
    def validate_config(cls):
        """
        Valida se todas as configurações obrigatórias estão definidas.
        """
        required_vars = ["WIX_PUBLIC_KEY", "PLOOMES_USER_KEY", "MONGO_URI"]
        missing_vars = []
        
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing_vars)}")
        
        return True

