from flask import Flask, jsonify, request
from sqlalchemy import create_engine
from ftplib import FTP
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import os
import traceback
import logging

app = Flask(__name__)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CONFIGURAÇÕES
ADMINISTRADORA = "GCACARD"
REMETENTE = "0000"
DESTINATARIO = "000000"
TIPO_PROCESSAMENTO = "N"
MOEDA = "RE"

# Configurações FTP (podem ser movidas para variáveis de ambiente)
FTP_HOST = os.getenv('FTP_HOST', 'ftp.ercard.com.br')
FTP_USER = os.getenv('FTP_USER', 'gcactb@ercard.com.br')
FTP_PASS = os.getenv('FTP_PASS', 'ZC3Vtlzo#A')
FTP_PORT = int(os.getenv('FTP_PORT', '21'))

# Configurações do banco (podem ser movidas para variáveis de ambiente)
SERVER = os.getenv('DB_SERVER', '138.0.160.201')
DATABASE = os.getenv('DB_DATABASE', 'ErCardGCAD1')
USER = os.getenv('DB_USER', 'd1.devee')
PASSWORD = os.getenv('DB_PASSWORD', '6$ZY325Eo0')
DRIVER = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')

# CONEXÃO COM SQL SERVER USANDO SQLALCHEMY
def conectar_sqlalchemy():

# Túnel SSH
    SERVER = "138.0.160.201"
    DATABASE = "ErCardGCAD1"
    USER = "d1.devee"
    PASSWORD = "6$ZY325Eo0"
    DRIVER = "ODBC Driver 17 for SQL Server"

    ssh_tunnel = SSHTunnelForwarder(
        ('192.168.100.100', 22),      # Servidor SSH
        ssh_username='gabriel',
        ssh_password='1234',
        remote_bind_address=(SERVER, 1433),  # Banco remoto
        local_bind_address=('127.0.0.1', 0)  # Porta local aleatória
    )

    ssh_tunnel.start()
    db_host = "127.0.0.1"
    db_port = ssh_tunnel.local_bind_port


    connection_string = (
        f"mssql+pyodbc://{USER}:{PASSWORD}@{SERVER}/{DATABASE}"
        f"?driver={DRIVER.replace(' ', '+')}"
    )

    odbc_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={db_host},{db_port};"
        f"Database={DATABASE};"
        f"UID={USER};"
        f"PWD={PASSWORD};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
    )
    
    conn_str = "mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc_str)
    engine = create_engine(conn_str)

    return engine

# GERA ID DE MOVIMENTO
def gerar_id_movimento():
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd('/Financeiro')

        arquivos = ftp.nlst()
        ids = []

        for f in arquivos:
            if f.startswith(ADMINISTRADORA) and f.endswith(".txt"):
                try:
                    num = int(f[len(ADMINISTRADORA):-4])
                    ids.append(num)
                except ValueError:
                    pass

        ftp.quit()
        return max(ids) + 1 if ids else 1

    except Exception as e:
        logger.error(f"Erro ao buscar ID no FTP ({e}), definindo como 1.")
        return 1

def formatar_valor(valor):
    return f"{float(valor):011.2f}".replace('.', '')

# REGISTROS
def formatar_registro_A0(id_mov, datahora, nseq):
    return (
        f"A0" +
        "001.7c" +
        datahora.strftime('%Y%m%d') +
        datahora.strftime('%H%M%S') +
        str(id_mov).zfill(6) +
        ADMINISTRADORA.ljust(30)[:30] +
        REMETENTE.zfill(4) +
        DESTINATARIO.zfill(6) +
        TIPO_PROCESSAMENTO +
        str(nseq).zfill(6)
    )

def formatar_registro_L0(row, nseq):
    return f"L0{row['data_transacao']}{MOEDA}{str(nseq).zfill(6)}"

def formatar_registro_CV(row, nseq):
    return (
        f"CV"
        f"{str(row['cnpj_loja'])}"
        f"{str(row['nsu'])}"
        f"{row['data_transacao']}"
        f"{str(row['hora_transacao'])}"
        f"{str(row['tipo_lanc'])}"
        f"{row['dataprevisao']}"
        f"C"
        f"9"
        f"{formatar_valor(row['valor_bruto'])}"
        f"{'00000000000'}"
        f"{formatar_valor(row['valor_bruto'])}"
        f"{str(row['numero_cartao']).zfill(19)}"
        f"{str(row['n_parcela'])}"
        f"{str(row['n_prazo'])}"
        f"{str(row['nsu'])}"
        f"{formatar_valor(row['valor_parcela'])}"
        f"{'00000000000'}"
        f"{formatar_valor(row['valor_parcela'])}"
        f"{str(row['banco_dep'])}"
        f"{str(row['agencia_dep'])}"
        f"{str(row['conta_dep'])}"
        f"{'000000000000'}"
        f"{'000'}"
        f"{str(nseq).zfill(6)}"
    )

def formatar_registro_CC(row, nseq):
    return (
        f"CC"
        f"{str(row['cnpj_loja'])}"
        f"{str(row['nsu'])}"
        f"{row['data_transacao']}"
        f"{str(row['n_parcela'])}"
        f"{str(row['nsu_cancelamento'])}"
        f"{row['data_transacao']}"
        f"{str(row['hora_transacao'])}"
        f"9"
        f"{str(nseq).zfill(6)}"
    )

def formatar_registro_L9(qtd_registros, total_credito, nseq):
    return f"L9{str(qtd_registros).zfill(6)}{formatar_valor(total_credito).rjust(14, '0')}{str(nseq).zfill(6)}"

def formatar_registro_A9(total_registros, nseq):
    return f"A9{str(total_registros).zfill(6)}{str(nseq).zfill(6)}"

# BUSCA DADOS DO BANCO
def buscar_dados_do_banco(data_especifica=None):
    # Se não especificar data, usa ontem
    if data_especifica is None:
        data_filter = "CAST(GETDATE() - 1 AS DATE)"
    else:
        data_filter = f"'{data_especifica}'"
    
    query = f"""
    SELECT
CASE WHEN CP.SITUACAO = 'C' THEN 'CC'
     WHEN CP.SITUACAO = 'A' THEN 'CV' 
END                                                 AS tipo_registro,
REPLACE(LJ.CODIGOESTABELECIMENTO, ' ', '')                     AS cnpj_loja,
ISNULL(FORMAT(CP.AUTORIZACAO, '000000000000'), '000000000000')              AS nsu,
ISNULL(FORMAT(CP.AUTORIZACAOCANCELAMENTO, '000000000000'), '000000000000')  AS nsu_cancelamento,
CONVERT(VARCHAR(8), CP.DATACOMPRA, 112)             AS data_transacao,
REPLACE(CP.HORACOMPRA, ':','')                      AS hora_transacao,
CASE
	WHEN PA.REPASSE = 'N' THEN 0
	WHEN PA.REPASSE = 'S' THEN 1
    WHEN PA.REPASSE = 'D' THEN 2
	
END		                                            AS tipo_lanc,

CASE 
    WHEN PA.DATAPREVISAOREPASSE IS NULL 
        THEN CONVERT(VARCHAR(8), DATEADD(DAY, 30, ISNULL(CP.DATACOMPRA, GETDATE())), 112)
    ELSE CONVERT(VARCHAR(8), PA.DATAPREVISAOREPASSE, 112)
END                                                 AS dataprevisao,
CP.VALORCOMPRA                                      AS valor_bruto,
RIGHT('0000000000000000000' + CAST(REPLACE(CP.PLASTICO, ' ', '')AS VARCHAR(19)), 19) AS numero_cartao,
CASE
    WHEN PA.PARCELA = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(PA.PARCELA AS VARCHAR(2)), 2)
END                                                 AS n_parcela,

CASE
    WHEN CP.PRAZO = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(CP.PRAZO AS VARCHAR(2)), 2)
END                                                 AS n_prazo,
CASE
    WHEN CP.PRAZO = 1 THEN '00000000000'
    ELSE
         PA.PRESTACAO
END                                                 AS valor_parcela,
CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT(CAST(CAST(LJ.BANCO AS INT) AS VARCHAR(3)), 3)	
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT(CAST(CAST(LI.BANCO  AS INT) AS VARCHAR(3)), 3)
END														AS banco_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('000000' + CAST(REPLACE(LJ.BANCOAGENCIA + LJ.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('000000' + CAST(REPLACE(LI.BANCOAGENCIA + LI.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
END														AS agencia_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('00000000000' + CAST(LJ.BANCOCONTACORRENTE + LJ.BANCOCONTADIGITO AS VARCHAR(11)), 11)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('00000000000' + CAST(LI.BANCOCONTACORRENTE + LI.BANCOCONTADIGITO AS VARCHAR(11)), 11) 
END														AS conta_dep

FROM CRTCOMPRASPARCELAS     AS PA
INNER JOIN CRTCOMPRAS       AS CP ON CP.AUTORIZACAO = PA.AUTORIZACAO
INNER JOIN CRTLOJAS         AS LJ ON LJ.LOJA = CP.LOJA
INNER JOIN CRTLOJISTAS      AS LI ON LI.LOJISTA = CP.LOJISTA
WHERE CP.SITUACAO IN ('A', 'C')
AND CP.DATACONTABIL = {data_filter}

UNION

SELECT
CASE WHEN CP.SITUACAO = 'C' THEN 'CC'
     WHEN CP.SITUACAO = 'A' THEN 'CV' 
END                                                 AS tipo_registro,
REPLACE(LJ.CODIGOESTABELECIMENTO, ' ', '')                     AS cnpj_loja,
ISNULL(FORMAT(CP.AUTORIZACAO, '000000000000'), '000000000000')              AS nsu,
ISNULL(FORMAT(CP.AUTORIZACAOCANCELAMENTO, '000000000000'), '000000000000')  AS nsu_cancelamento,
CONVERT(VARCHAR(8), CP.DATACOMPRA, 112)             AS data_transacao,
REPLACE(CP.HORACOMPRA, ':','')                      AS hora_transacao,
CASE
	WHEN PA.REPASSE = 'N' THEN 0
	WHEN PA.REPASSE = 'S' THEN 1
    WHEN PA.REPASSE = 'D' THEN 2
	
END		                                            AS tipo_lanc,

CASE 
    WHEN PA.DATAREPASSE IS NULL 
        THEN CONVERT(VARCHAR(8), DATEADD(DAY, 30, ISNULL(CP.DATACOMPRA, GETDATE())), 112)
    ELSE CONVERT(VARCHAR(8), PA.DATAREPASSE, 112)
END                                                 AS dataprevisao,

CP.VALORCOMPRA                                      AS valor_bruto,
RIGHT('0000000000000000000' + CAST(REPLACE(CP.PLASTICO, ' ', '')AS VARCHAR(19)), 19) AS numero_cartao,
CASE
    WHEN PA.PARCELA = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(PA.PARCELA AS VARCHAR(2)), 2)
END                                                 AS n_parcela,

CASE
    WHEN CP.PRAZO = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(CP.PRAZO AS VARCHAR(2)), 2)
END                                                 AS n_prazo,
CASE
    WHEN CP.PRAZO = 1 THEN '00000000000'
    ELSE
         PA.PRESTACAO
END                                                 AS valor_parcela,
CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT(CAST(CAST(LJ.BANCO AS INT) AS VARCHAR(3)), 3)	
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT(CAST(CAST(LI.BANCO  AS INT) AS VARCHAR(3)), 3)
END														AS banco_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('000000' + CAST(REPLACE(LJ.BANCOAGENCIA + LJ.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('000000' + CAST(REPLACE(LI.BANCOAGENCIA + LI.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
END														AS agencia_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('00000000000' + CAST(LJ.BANCOCONTACORRENTE + LJ.BANCOCONTADIGITO AS VARCHAR(11)), 11)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('00000000000' + CAST(LI.BANCOCONTACORRENTE + LI.BANCOCONTADIGITO AS VARCHAR(11)), 11) 
END														AS conta_dep

FROM CRTCOMPRASPARCELAS     AS PA
INNER JOIN CRTCOMPRAS       AS CP ON CP.AUTORIZACAO = PA.AUTORIZACAO
INNER JOIN CRTLOJAS         AS LJ ON LJ.LOJA = CP.LOJA
INNER JOIN CRTLOJISTAS      AS LI ON LI.LOJISTA = CP.LOJISTA
WHERE CP.SITUACAO IN ('A', 'C')
AND PA.DATAREPASSE = {data_filter}
ORDER BY tipo_lanc;
    """
    engine = conectar_sqlalchemy()
    return pd.read_sql(query, engine.connect())

# FUNÇÃO PARA SALVAR LOG COM DATA NO NOME
def salvar_log(nome_arquivo, qtd_transacoes, total_credito, status, mensagem=""):
    datahora = datetime.now()
    timestamp = datahora.strftime('%Y%m%d_%H%M%S')
    log_nome = f"log_geracao_{timestamp}.txt"

    log_content = (
        f"Data/Hora: {datahora.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Arquivo: {nome_arquivo}\n"
        f"Quantidade de transações: {qtd_transacoes}\n"
        f"Total crédito: {total_credito:.2f}\n"
        f"Status: {status}\n"
    )
    if mensagem:
        log_content += f"Mensagem: {mensagem}\n"
    log_content += "-"*50 + "\n"

    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd('/Financeiro/Log')

        with BytesIO(log_content.encode('utf-8')) as f:
            ftp.storbinary(f"STOR {log_nome}", f)

        ftp.quit()
        logger.info(f"Log enviado para FTP (/Financeiro/Log): {log_nome}")
    except Exception as e:
        logger.error(f"Erro ao enviar log para FTP: {e}")

    return log_content

# GERA ARQUIVO
def gerar_arquivo_conciliacao(data_especifica=None):
    try:
        df = buscar_dados_do_banco(data_especifica)
        if df.empty:
            log_content = salvar_log("N/A", 0, 0.0, "Nenhum dado", "Nenhum dado encontrado para gerar o arquivo")
            return {
                "success": False,
                "message": "Nenhum dado encontrado para gerar o arquivo",
                "log": log_content
            }

        id_mov = gerar_id_movimento()
        datahora = datetime.now() - timedelta(days=1) if data_especifica is None else datetime.strptime(data_especifica, '%Y-%m-%d')
        nseq = 1
        conteudo = []

        conteudo.append(formatar_registro_A0(id_mov, datahora, nseq))
        nseq += 1
        conteudo.append(formatar_registro_L0(df.iloc[0], nseq))
        nseq += 1

        qtd_transacoes = 0
        total_credito = 0.0

        for _, row in df.iterrows():
            if row['tipo_registro'] == "CV":
                conteudo.append(formatar_registro_CV(row, nseq))
                total_credito += float(row['valor_bruto'])
                qtd_transacoes += 1
                nseq += 1
            elif row['tipo_registro'] == "CC":
                conteudo.append(formatar_registro_CC(row, nseq))
                qtd_transacoes += 1
                nseq += 1

        conteudo.append(formatar_registro_L9(qtd_transacoes, total_credito, nseq))
        nseq += 1
        conteudo.append(formatar_registro_A9(len(conteudo) + 1, nseq))
        nseq += 1

        nome_arquivo = f"{ADMINISTRADORA}{str(id_mov).zfill(6)}.txt"
        conteudo_str = "\n".join(conteudo)

        # Enviar para FTP
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd('/Financeiro')

        with BytesIO(conteudo_str.encode('utf-8')) as f:
            ftp.storbinary(f"STOR {nome_arquivo}", f)

        ftp.quit()
        
        log_content = salvar_log(nome_arquivo, qtd_transacoes, total_credito, "Enviado com sucesso")
        
        return {
            "success": True,
            "message": f"Arquivo enviado com sucesso: {nome_arquivo}",
            "arquivo": nome_arquivo,
            "quantidade_transacoes": qtd_transacoes,
            "total_credito": total_credito,
            "log": log_content
        }

    except Exception as e:
        error_msg = f"Erro ao gerar arquivo: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        log_content = salvar_log("ERRO", 0, 0.0, "Erro na geração", str(e))
        
        return {
            "success": False,
            "message": error_msg,
            "log": log_content
        }

# ENDPOINTS DA API

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se a API está funcionando"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/gerar-conciliacao', methods=['POST'])
def gerar_conciliacao():
    """Endpoint para gerar arquivo de conciliação"""
    try:
        data = request.get_json() if request.is_json else {}
        data_especifica = data.get('data') if data else None
        
        resultado = gerar_arquivo_conciliacao(data_especifica)
        
        status_code = 200 if resultado["success"] else 400
        return jsonify(resultado), status_code
        
    except Exception as e:
        logger.error(f"Erro no endpoint gerar-conciliacao: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "message": f"Erro interno: {str(e)}"
        }), 500

@app.route('/consultar-dados', methods=['GET', 'POST'])
def consultar_dados():
    """Endpoint para consultar dados do banco sem gerar arquivo"""
    try:
        if request.method == 'POST':
            data = request.get_json() if request.is_json else {}
            data_especifica = data.get('data') if data else None
        else:
            data_especifica = request.args.get('data')
        
        df = buscar_dados_do_banco(data_especifica)
        
        if df.empty:
            return jsonify({
                "success": True,
                "message": "Nenhum dado encontrado",
                "quantidade": 0,
                "dados": []
            })
        
        # Converter DataFrame para dicionário
        dados = df.to_dict('records')
        
        # Calcular totais
        total_credito = df[df['tipo_registro'] == 'CV']['valor_bruto'].sum()
        
        return jsonify({
            "success": True,
            "message": f"Dados encontrados: {len(dados)} registros",
            "quantidade": len(dados),
            "total_credito": float(total_credito),
            "dados": dados
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint consultar-dados: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "message": f"Erro interno: {str(e)}"
        }), 500

@app.route('/status-ftp', methods=['GET'])
def status_ftp():
    """Endpoint para verificar conectividade com FTP"""
    try:
        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.cwd('/Financeiro')
        
        # Listar alguns arquivos para teste
        arquivos = ftp.nlst()[:10]  # Primeiros 10 arquivos
        
        ftp.quit()
        
        return jsonify({
            "success": True,
            "message": "Conexão FTP estabelecida com sucesso",
            "servidor": FTP_HOST,
            "arquivos_exemplo": arquivos
        })
        
    except Exception as e:
        logger.error(f"Erro ao conectar FTP: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Erro de conexão FTP: {str(e)}"
        }), 500

@app.route('/status-db', methods=['GET'])
def status_db():
    """Endpoint para verificar conectividade com banco de dados"""
    try:
        engine = conectar_sqlalchemy()
        # Teste simples de conexão
        with engine.connect() as conn:
            result = conn.execute("SELECT 1 as teste").fetchone()
        
        return jsonify({
            "success": True,
            "message": "Conexão com banco de dados estabelecida com sucesso",
            "servidor": SERVER,
            "database": DATABASE
        })
        
    except Exception as e:
        logger.error(f"Erro ao conectar banco: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Erro de conexão com banco: {str(e)}"
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "Endpoint não encontrado"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "Erro interno do servidor"
    }), 500

if __name__ == '__main__':
    # Configurações para desenvolvimento
    app.run(host='0.0.0.0', port=5000, debug=True)
    

