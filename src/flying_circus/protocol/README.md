# Monty wire schema

`monty.proto` is copied from Monty commit `591527397445bf734873252d1ee20c1b6308fe7f`.
The client declares protocol version 5; incompatible workers must reject configuration.
The schema and generated client are covered by the accompanying `MONTY_LICENSE`.

Regenerate from this directory:

```sh
uv run --no-project --with grpcio-tools==1.78.0 python -m grpc_tools.protoc \
  -I . --python_out=. monty.proto
```
