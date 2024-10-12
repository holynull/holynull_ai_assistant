.PHONY: start
start:
	uvicorn main:app --reload --port 8081 --host 192.168.3.6

.PHONY: format
format:
	black .
	isort .
