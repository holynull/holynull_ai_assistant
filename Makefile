.PHONY: start
start:
	uvicorn main:app --reload --port 8081 --host 192.168.3.6 --log-config logging_config.yml

.PHONY: format
format:
	black .
	isort .