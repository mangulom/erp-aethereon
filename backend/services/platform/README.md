# Platform service · 18002

Reserved for platform administration, module registry and aggregated operational signals. It must not duplicate identity's role and membership data, nor claim a working health endpoint until its independent FastAPI application has been implemented. For this first stage the shell reads its module navigation from `frontend/public/assets/microfrontends.json`; the registry in Postgres is the planned server-side source of truth.
