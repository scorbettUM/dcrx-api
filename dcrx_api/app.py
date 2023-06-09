from fastapi import FastAPI
from dcrx_api.services.jobs.service import jobs_router
from dcrx_api.services.registry.service import registry_router
from dcrx_api.services.users.service import users_router
from dcrx_api.lifespan import lifespan
from dcrx_api.middleware.auth_middleware import AuthMidlleware

app = FastAPI(lifespan=lifespan)
app.include_router(jobs_router)
app.include_router(registry_router)
app.include_router(users_router)
app.add_middleware(AuthMidlleware)