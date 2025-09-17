# Makefile para API de Conciliação

.PHONY: help build up down logs restart clean test

# Variáveis
DOCKER_COMPOSE = docker-compose
DOCKER = docker
APP_NAME = conciliacao-api
IMAGE_NAME = conciliacao-api

# Variáveis Docker Hub (podem ser sobrescritas via environment)
DOCKER_USER ?= seu-usuario
DOCKER_IMAGE ?= $(DOCKER_USER)/$(IMAGE_NAME)
DOCKER_TAG ?= latest
VERSION ?= $(shell date +%Y%m%d-%H%M%S)

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

# Comandos Docker Hub
docker-login: ## Login no Docker Hub
	@echo "Fazendo login no Docker Hub..."
	$(DOCKER) login

docker-build: ## Build da imagem para Docker Hub
	@echo "Building imagem $(DOCKER_IMAGE):$(DOCKER_TAG)..."
	$(DOCKER) build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	$(DOCKER) tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):latest

docker-push: ## Push da imagem para Docker Hub
	@echo "Pushing imagem $(DOCKER_IMAGE):$(DOCKER_TAG) para Docker Hub..."
	$(DOCKER) push $(DOCKER_IMAGE):$(DOCKER_TAG)
	$(DOCKER) push $(DOCKER_IMAGE):latest

docker-build-push: docker-build docker-push ## Build e push para Docker Hub
	@echo "✅ Imagem $(DOCKER_IMAGE):$(DOCKER_TAG) enviada para Docker Hub com sucesso!"

docker-build-versioned: ## Build com versão automática (timestamp)
	@echo "Building imagem versionada $(DOCKER_IMAGE):$(VERSION)..."
	$(DOCKER) build -t $(DOCKER_IMAGE):$(VERSION) .
	$(DOCKER) tag $(DOCKER_IMAGE):$(VERSION) $(DOCKER_IMAGE):latest

docker-push-versioned: ## Push da versão específica para Docker Hub
	@echo "Pushing imagem versionada $(DOCKER_IMAGE):$(VERSION)..."
	$(DOCKER) push $(DOCKER_IMAGE):$(VERSION)
	$(DOCKER) push $(DOCKER_IMAGE):latest

docker-release: docker-build-versioned docker-push-versioned ## Release completo com versão
	@echo "✅ Release $(VERSION) enviado para Docker Hub!"
	@echo "📦 Imagem: $(DOCKER_IMAGE):$(VERSION)"
	@echo "📦 Latest: $(DOCKER_IMAGE):latest"

# Deploy produção com Docker Hub
prod-deploy-hub: ## Deploy produção usando imagem do Docker Hub
	@echo "Fazendo deploy de produção usando Docker Hub..."
	@echo "Imagem: $(DOCKER_IMAGE):$(DOCKER_TAG)"
	DOCKER_IMAGE=$(DOCKER_IMAGE) DOCKER_TAG=$(DOCKER_TAG) $(DOCKER_COMPOSE) -f docker-compose.prod.yml up -d
	@echo "Aguardando inicialização..."
	@sleep 15
	$(MAKE) test-all

prod-deploy-version: ## Deploy produção com versão específica
	@echo "Deploy com versão $(VERSION)..."
	DOCKER_IMAGE=$(DOCKER_IMAGE) DOCKER_TAG=$(VERSION) $(DOCKER_COMPOSE) -f docker-compose.prod.yml up -d
	@echo "Aguardando inicialização..."
	@sleep 15
	$(MAKE) test-all
