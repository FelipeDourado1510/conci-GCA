# API de Conciliação Financeira

Esta é uma API Flask que gera arquivos de conciliação financeira a partir de dados do banco de dados e os envia via FTP.

## 📋 Funcionalidades

- **Gerar Arquivo de Conciliação**: Processa transações do banco e gera arquivo no formato específico
- **Consultar Dados**: Visualiza os dados antes de gerar o arquivo
- **Status de Conectividade**: Verifica conexões com banco e FTP
- **Logs Automáticos**: Registra todas as operações com timestamp
- **Health Check**: Endpoint para monitoramento da aplicação

## 🚀 Endpoints da API

### `GET /health`
Verifica se a API está funcionando
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0"
}
```

### `POST /gerar-conciliacao`
Gera o arquivo de conciliação e envia para o FTP
```json
// Request (opcional)
{
  "data": "2024-01-15"  // Se não informado, usa ontem
}

// Response
{
  "success": true,
  "message": "Arquivo enviado com sucesso: GCACARD000001.txt",
  "arquivo": "GCACARD000001.txt",
  "quantidade_transacoes": 150,
  "total_credito": 45750.50,
  "log": "..."
}
```

### `GET/POST /consultar-dados`
Consulta os dados sem gerar arquivo
```json
// Request (POST - opcional)
{
  "data": "2024-01-15"
}

// Response
{
  "success": true,
  "message": "Dados encontrados: 150 registros",
  "quantidade": 150,
  "total_credito": 45750.50,
  "dados": [...]
}
```

### `GET /status-ftp`
Verifica conectividade com servidor FTP
```json
{
  "success": true,
  "message": "Conexão FTP estabelecida com sucesso",
  "servidor": "ftp.ercard.com.br",
  "arquivos_exemplo": ["arquivo1.txt", "arquivo2.txt"]
}
```

### `GET /status-db`
Verifica conectividade com banco de dados
```json
{
  "success": true,
  "message": "Conexão com banco de dados estabelecida com sucesso",
  "servidor": "138.0.160.201",
  "database": "ErCardGCAD1"
}
```

## 🐳 Executando com Docker

### 1. Usando Docker Compose (Recomendado)

```bash
# Clone o repositório
git clone <seu-repositorio>
cd conciliacao-api

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env com suas credenciais

# Execute a aplicação
docker-compose up -d

# Visualizar logs
docker-compose logs -f

# Parar a aplicação
docker-compose down
```

### 2. Usando Docker Build Manual

```bash
# Build da imagem
docker build -t conciliacao-api .

# Executar container
docker run -d \
  --name conciliacao-api \
  -p 5000:5000 \
  -e DB_SERVER=138.0.160.201 \
  -e DB_DATABASE=ErCardGCAD1 \
  -e DB_USER=seu_usuario \
  -e DB_PASSWORD=sua_senha \
  -e FTP_HOST=ftp.ercard.com.br \
  -e FTP_USER=seu_usuario_ftp \
  -e FTP_PASS=sua_senha_ftp \
  conciliacao-api
```

## 💻 Desenvolvimento Local

### Pré-requisitos
- Python 3.11+
- SQL Server ODBC Driver 17
- Acesso ao banco de dados SQL Server
- Acesso ao servidor FTP

### Instalação

```bash
# Clone o repositório
git clone <seu-repositorio>
cd conciliacao-api

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env

# Execute a aplicação
python app.py
```

A API estará disponível em `http://localhost:5000`

## 🔧 Configuração

### Variáveis de Ambiente

Todas as configurações podem ser feitas através de variáveis de ambiente:

| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `DB_SERVER` | Servidor do SQL Server | 138.0.160.201 |
| `DB_DATABASE` | Nome do banco de dados | ErCardGCAD1 |
| `DB_USER` | Usuário do banco | d1.devee |
| `DB_PASSWORD` | Senha do banco | - |
| `DB_DRIVER` | Driver ODBC | ODBC Driver 17 for SQL Server |
| `FTP_HOST` | Servidor FTP | ftp.ercard.com.br |
| `FTP_USER` | Usuário FTP | - |
| `FTP_PASS` | Senha FTP | - |
| `FTP_PORT` | Porta FTP | 21 |
| `FLASK_ENV` | Ambiente Flask | production |
| `FLASK_DEBUG` | Debug mode | false |

## 📁 Estrutura do Projeto

```
conciliacao-api/
├── app.py                 # Aplicação Flask principal
├── requirements.txt       # Dependências Python
├── Dockerfile            # Configuração Docker
├── docker-compose.yml    # Orquestração Docker
├── .env.example          # Exemplo de variáveis de ambiente
├── README.md             # Este arquivo
└── logs/                 # Diretório de logs (criado automaticamente)
```

## 🔍 Monitoramento

### Health Check
A aplicação inclui health check automático:
- **Endpoint**: `GET /health`
- **Docker**: Health check integrado no container
- **Intervalo**: 30 segundos

### Logs
- Logs estruturados com timestamp
- Logs de erro detalhados com stack trace
- Logs salvos no FTP em `/Financeiro/Log/`
- Volume para logs locais no Docker

## 🚨 Tratamento de Erros

A API possui tratamento robusto de erros:
- Conexão com banco de dados
- Conexão FTP
- Processamento de dados
- Validação de parâmetros
- Logs detalhados para debugging

## 📝 Formato do Arquivo de Conciliação

O arquivo gerado segue o padrão:
- **Nome**: `GCACARD{ID}.txt` (ex: GCACARD000001.txt)
- **Estrutura**: Registros A0, L0, CV/CC, L9, A9
- **Encoding**: UTF-8
- **Destino**: FTP `/Financeiro/`

## 🔐 Segurança

- Senhas configuráveis via variáveis de ambiente
- Usuário não-root no container Docker
- Validação de entrada nos endpoints
- Logs não exposição de credenciais

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para detalhes.

## 📞 Suporte

Para suporte, entre em contato através:
- Email: seu-email@empresa.com
- Slack: #conciliacao-financeira
- Issues: GitHub Issues