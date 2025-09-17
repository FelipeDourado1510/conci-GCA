# Makefile para API de Conciliação

.PHONY: help build up down logs restart clean test

# Variáveis
DOCKER_COMPOSE = docker-compose
DOCKER = docker
APP_NAME = conciliacao-api
IMAGE_NAME = conciliacao-api

help: ## Mostra esta mensagem de ajuda
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build da imagem Docker
	$(DOCKER_COMPOSE) build

up: ## Inicia a aplicação
	$(DOCKER_COMPOSE) up -d

down: ## Para a aplicação
	$(DOCKER_COMPOSE) down

logs: ## Visualiza os logs
	$(DOCKER_COMPOSE) logs -f

restart: ## Reinicia a aplicação
	$(DOCKER_COMPOSE) restart

status: ## Mostra status dos containers
	$(DOCKER_COMPOSE) ps

clean: ## Remove containers, redes, volumes e imagens
	$(DOCKER_COMPOSE) down -v --rmi all --remove-orphans

clean-images: ## Remove imagens não utilizadas
	$(DOCKER) image prune -f

clean-all: ## Limpeza completa do Docker
	$(DOCKER) system prune -a -f

dev-setup: ## Configura ambiente de desenvolvimento
	cp .env.example .env
	@echo "Configure o arquivo .env com suas credenciais"

dev-run: ## Executa em modo desenvolvimento local
	python app.py

dev-install: ## Instala dependências para desenvolvimento
	pip install -r requirements.txt

test-health: ## Testa o endpoint de health
	curl -f http://localhost:5000/health || echo "Serviço não está respondendo"

test-db: ## Testa conexão com banco
	curl -f http://localhost:5000/status-db || echo "Problema na conexão com banco"

test-ftp: ## Testa conexão FTP
	curl -f http://localhost:5000/status-ftp || echo "Problema na conexão FTP"

test-all: ## Executa todos os testes básicos
	@echo "Testando health..."
	@curl -s http://localhost:5000/health | grep -q "healthy" && echo "✅ Health OK" || echo "❌ Health FAIL"
	@echo "Testando banco..."
	@curl -s http://localhost:5000/status-db | grep -q "success" && echo "✅ DB OK" || echo "❌ DB FAIL"
	@echo "Testando FTP..."
	@curl -s http://localhost:5000/status-ftp | grep -q "success" && echo "✅ FTP OK" || echo "❌ FTP FAIL"

backup-logs: ## Faz backup dos logs
	$(DOCKER_COMPOSE) exec $(APP_NAME) tar -czf /tmp/logs_backup_$(shell date +%Y%m%d_%H%M%S).tar.gz /app/logs/

deploy: ## Deploy completo (build + up)
	$(MAKE) build
	$(MAKE) up
	@echo "Aguardando inicialização..."
	@sleep 10
	$(MAKE) test-health

redeploy: ## Redeploy completo (down + build + up)
	$(MAKE) down
	$(MAKE) build
	$(MAKE) up
	@echo "Aguardando inicialização..."
	@sleep 10
	$(MAKE) test-health

monitor: ## Monitora recursos dos containers
	$(DOCKER) stats $(shell $(DOCKER_COMPOSE) ps -q)

shell: ## Acessa shell do container
	$(DOCKER_COMPOSE) exec $(APP_NAME) /bin/bash

# Comandos de produção
prod-deploy: ## Deploy para produção
	@echo "Fazendo deploy para produção..."
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --build
	@echo "Aguardando inicialização..."
	@sleep 15
	$(MAKE) test-all

prod-backup: ## Backup de produção
	@echo "Fazendo backup de produção..."
	$(MAKE) backup-logs
	$(DOCKER_COMPOSE) exec $(APP_NAME) tar -czf /tmp/app_backup_$(shell date +%Y%m%d_%H%M%S).tar.gz /app/

prod-update: ## Atualiza produção
	@echo "Atualizando produção..."
	$(DOCKER_COMPOSE) pull
	$(MAKE) redeploy
	$(MAKE) test-all