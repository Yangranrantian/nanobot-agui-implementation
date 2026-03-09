# AGUI Web Client

This is a zero-dependency static browser client for the nanobot AGUI backend.

## Run

1. Start the backend:

```bash
nanobot web
```

2. Serve this folder statically:

```bash
cd apps/agui-web
python serve.py --host 127.0.0.1 --port 4173
```

3. Open http://127.0.0.1:4173 and point the backend URL to `http://127.0.0.1:8000`.

## Features

- session list
- transcript rendering
- SSE streaming updates
- interrupt cards for `confirm`, `single_select`, and `form`
- file upload support
