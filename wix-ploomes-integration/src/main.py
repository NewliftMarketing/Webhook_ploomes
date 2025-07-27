import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory
from src.models.user import db
from src.routes.user import user_bp
from src.routes.webhook import webhook_bp
from pymongo import MongoClient

# Configuração do MongoDB
mongo_uri = os.environ.get("MONGO_URI")
if mongo_uri:
    mongo_client = MongoClient(mongo_uri)
    mongo_db = mongo_client.get_database() # Pega o banco de dados do URI
else:
    mongo_client = None
    mongo_db = None
    print("AVISO: MONGO_URI não configurada. Logs não serão salvos no MongoDB.")

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'src', 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(webhook_bp, url_prefix='/webhook')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.path.dirname(__file__), "src", "database", "app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)