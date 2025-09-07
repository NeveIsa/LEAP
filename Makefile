.PHONY: default

default:
	uvicorn server.rpc_server:app --host 0.0.0.0 --port 9000
