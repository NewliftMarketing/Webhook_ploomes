import json
import jwt
import requests
from flask import Blueprint, request, jsonify
from src.config import Config
import logging
from datetime import datetime

# Importar o objeto mongo_db do main.py
from main import mongo_db

webhook_bp = Blueprint("webhook", __name__)

logger = logging.getLogger(__name__)
logging.basicConfig(level=Config.LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")

def log_to_mongodb(event_type, payload, status, error=None, ploomes_card_id=None):
    if mongo_db:
        try:
            log_entry = {
                "timestamp": datetime.utcnow(),
                "event_type": event_type,
                "payload": payload,
                "status": status,
                "error": str(error) if error else None,
                "ploomes_card_id": ploomes_card_id
            }
            mongo_db.webhook_logs.insert_one(log_entry)
            logger.info("Log salvo no MongoDB.")
        except Exception as e:
            logger.error(f"Erro ao salvar log no MongoDB: {e}")

def create_ploomes_card(member_info):
    """
    Cria um cartão no Ploomes CRM com as informações do membro.
    """
    try:
        # Headers para a API do Ploomes
        headers = {
            'User-Key': Config.PLOOMES_USER_KEY,
            'Content-Type': 'application/json'
        }
        
        # Dados do cartão (Deal) para o Ploomes
        card_data = {
            "Title": f"Novo membro: {member_info.get('nickname', member_info.get('email', 'Sem nome'))}",
            "Amount": 0,  # Valor inicial do negócio
            "StageId": Config.PLOOMES_STAGE_ID,
            "PipelineId": Config.PLOOMES_PIPELINE_ID,
            "OtherProperties": [
                {
                    "FieldKey": "wix_member_id",
                    "StringValue": member_info.get('id', '')
                },
                {
                    "FieldKey": "wix_member_email",
                    "StringValue": member_info.get('email', '')
                },
                {
                    "FieldKey": "wix_member_status",
                    "StringValue": member_info.get('status', '')
                },
                {
                    "FieldKey": "wix_created_date",
                    "StringValue": member_info.get('created_date', '')
                }
            ]
        }
        
        # Se temos um contact_id, podemos tentar associar ao contato
        if member_info.get('contact_id'):
            contact_result = create_or_find_ploomes_contact(member_info)
            if contact_result['success']:
                card_data['ContactId'] = contact_result['contact_id']
        
        # Fazer a requisição para criar o cartão
        response = requests.post(
            f"{Config.PLOOMES_API_BASE}/Deals",
            headers=headers,
            json=card_data,
            timeout=30
        )
        
        if response.status_code == 201:
            created_card = response.json()
            log_to_mongodb("member_created", member_info, "success", ploomes_card_id=created_card.get("Id"))
            return {
                'success': True,
                'card_id': created_card.get('Id'),
                'card_data': created_card
            }
        else:
            log_to_mongodb("member_created", member_info, "failure", error=response.text)
            return {
                'success': False,
                'error': f"Erro HTTP {response.status_code}: {response.text}"
            }
            
    except requests.RequestException as e:
        log_to_mongodb("member_created", member_info, "failure", error=f"Erro de conexão com Ploomes: {e}")
        return {
            'success': False,
            'error': f"Erro de conexão com Ploomes: {e}"
        }
    except Exception as e:
        log_to_mongodb("member_created", member_info, "failure", error=f"Erro interno: {e}")
        return {
            'success': False,
            'error': f"Erro interno: {e}"
        }

def create_or_find_ploomes_contact(member_info):
    """
    Cria ou encontra um contato no Ploomes baseado nas informações do membro.
    """
    try:
        headers = {
            'User-Key': Config.PLOOMES_USER_KEY,
            'Content-Type': 'application/json'
        }
        
        # Primeiro, tentar encontrar o contato pelo email
        email = member_info.get('email')
        if email:
            search_url = f"{Config.PLOOMES_API_BASE}/Contacts?$filter=Email eq '{email}'"
            response = requests.get(search_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                contacts = response.json().get('value', [])
                if contacts:
                    # Contato já existe
                    return {
                        'success': True,
                        'contact_id': contacts[0].get('Id'),
                        'existing': True
                    }
        
        # Se não encontrou, criar novo contato
        contact_data = {
            "Name": member_info.get('nickname', 'Novo Membro'),
            "Email": member_info.get('email', ''),
            "OtherProperties": [
                {
                    "FieldKey": "wix_member_id",
                    "StringValue": member_info.get('id', '')
                }
            ]
        }
        
        response = requests.post(
            f"{Config.PLOOMES_API_BASE}/Contacts",
            headers=headers,
            json=contact_data,
            timeout=30
        )
        
        if response.status_code == 201:
            created_contact = response.json()
            return {
                'success': True,
                'contact_id': created_contact.get('Id'),
                'existing': False
            }
        else:
            return {
                'success': False,
                'error': f"Erro ao criar contato: HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f"Erro ao processar contato: {e}"
        }

@webhook_bp.route('/wix-member-created', methods=['POST'])
def handle_wix_member_created():
    try:
        jwt_token = request.get_data(as_text=True)
        
        if not jwt_token:
            logger.error("JWT token não encontrado no corpo da requisição")
            log_to_mongodb("member_created", {"raw_jwt": jwt_token}, "failure", error="JWT token não encontrado")
            return jsonify({"error": "JWT token não encontrado"}), 400
        
        try:
            decoded_payload = jwt.decode(jwt_token, Config.WIX_PUBLIC_KEY, algorithms=['RS256'])
            logger.info(f"JWT decodificado com sucesso: {decoded_payload}")
        except jwt.InvalidTokenError as e:
            logger.error(f"Erro ao decodificar JWT: {e}")
            log_to_mongodb("member_created", {"raw_jwt": jwt_token}, "failure", error=f"JWT inválido: {e}")
            return jsonify({"error": "JWT inválido"}), 401
        
        event_type = decoded_payload.get('eventType')
        if event_type != 'wix.members.v1.member_created':
            logger.warning(f"Tipo de evento inesperado: {event_type}")
            log_to_mongodb(event_type, decoded_payload, "failure", error="Tipo de evento não suportado")
            return jsonify({"error": "Tipo de evento não suportado"}), 400
        
        member_data_str = decoded_payload.get('data', '{}')
        member_data = json.loads(member_data_str)
        
        member_entity = member_data.get('createdEvent', {}).get('entity', {})
        
        member_info = {
            'id': member_entity.get('id'),
            'email': member_entity.get('loginEmail'),
            'contact_id': member_entity.get('contactId'),
            'nickname': member_entity.get('profile', {}).get('nickname'),
            'status': member_entity.get('status'),
            'created_date': member_entity.get('createdDate')
        }
        
        logger.info(f"Dados do membro extraídos: {member_info}")
        
        ploomes_result = create_ploomes_card(member_info)
        
        if ploomes_result['success']:
            logger.info(f"Cartão criado no Ploomes com sucesso: {ploomes_result['card_id']}")
            log_to_mongodb("member_created", member_info, "success", ploomes_card_id=ploomes_result['card_id'])
            return jsonify({
                "message": "Webhook processado com sucesso",
                "member_id": member_info['id'],
                "ploomes_card_id": ploomes_result['card_id']
            }), 200
        else:
            logger.error(f"Erro ao criar cartão no Ploomes: {ploomes_result['error']}")
            log_to_mongodb("member_created", member_info, "failure", error=ploomes_result['error'])
            return jsonify({
                "error": "Erro ao criar cartão no Ploomes",
                "details": ploomes_result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Erro interno no processamento do webhook: {e}")
        log_to_mongodb("member_created", {"raw_jwt": request.get_data(as_text=True)}, "failure", error=f"Erro interno: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@webhook_bp.route('/health', methods=['GET'])
def health_check():
    try:
        status = "healthy"
        # Opcional: Adicionar verificação de conexão com Ploomes e MongoDB aqui
        if mongo_db:
            try:
                mongo_db.command('ping')
                mongo_status = "connected"
            except Exception as e:
                mongo_status = f"error: {e}"
                status = "unhealthy"
        else:
            mongo_status = "not configured"

        # Testar conexão com Ploomes (exemplo simples)
        try:
            headers = {'User-Key': Config.PLOOMES_USER_KEY}
            response = requests.get(f"{Config.PLOOMES_API_BASE}/Users", headers=headers, timeout=5)
            if response.status_code == 200:
                ploomes_status = "connected"
            else:
                ploomes_status = f"error: {response.status_code}"
                status = "unhealthy"
        except Exception as e:
            ploomes_status = f"error: {e}"
            status = "unhealthy"

        return jsonify({
            "service": "wix-ploomes-integration",
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {
                "mongodb": mongo_status,
                "ploomes_api": ploomes_status
            }
        }), 200
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({"service": "wix-ploomes-integration", "status": "error", "error": str(e)}), 500

@webhook_bp.route('/test', methods=['GET', 'POST'])
def test_webhook():
    """
    Endpoint de teste para verificar se o serviço está funcionando.
    """
    return jsonify({
        "message": "Serviço de integração Wix-Ploomes está funcionando",
        "timestamp": datetime.now().isoformat()
    })

