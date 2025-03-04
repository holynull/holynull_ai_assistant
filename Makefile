.PHONY: start
set_proxy:
	export HTTP_PROXY=http://127.0.0.1:7890
	export HTTPS_PROXY=http://127.0.0.1:7890
	export NO_PROXY=localhost,127.0.0.1
update_chromedriver:
	export HTTP_PROXY=http://127.0.0.1:7890
	export HTTPS_PROXY=http://127.0.0.1:7890
	export NO_PROXY=localhost,127.0.0.1
	python update_chromedriver.py
start:
	export HTTP_PROXY=http://127.0.0.1:7890
	export HTTPS_PROXY=http://127.0.0.1:7890
	export NO_PROXY=localhost,127.0.0.1
	uvicorn main:app --reload --port 8081 --host 192.168.3.6

.PHONY: format
format:
	black .
	isort .
start_ollama_serve:
	export OLLAMA_HOST=127.0.0.1 # environment variable to set ollama host
	export OLLAMA_PORT=11434 # environment variable to set the ollama port
	ollama serve