import uuid
from dcrx import Image
from dcrx_api.context.manager import context, ContextType
from dcrx_api.database.models import DatabaseTransactionResult
from dcrx_api.services.registry.context import RegistryServiceContext
from dcrx_api.services.registry.models import Registry, RegistryNotFoundException
from fastapi import APIRouter, HTTPException
from dcrx.layers import (
    Add,
    Arg,
    Cmd,
    Copy,
    Entrypoint,
    Env,
    Expose,
    Healthcheck,
    Label,
    Run,
    Stage,
    User,
    Volume,
    Workdir
)
from typing import List, Union
from .job import Job
from .models import (
    RemoteAdd,
    JobMetadata,
    JobNotFoundException,
    NewImage,
    ServerLimitException
)

Layer = List[
    Union[
        Add,
        Arg,
        Cmd,
        Copy,
        Entrypoint,
        Env,
        Expose,
        Healthcheck,
        Label,
        Run,
        Stage,
        User,
        Volume,
        Workdir
    ]
]


jobs_router = APIRouter()


@jobs_router.post(
    "/jobs/images/create",
    status_code=202,
    responses={
        404: {
            'model': RegistryNotFoundException
        },
        429: {
            'model': ServerLimitException
        },
        500: {
            "model": DatabaseTransactionResult
        }
    }
)
async def create_job(new_image: NewImage) -> JobMetadata:

    job_service_context = context.get(ContextType.JOB_SERVICE)
    monitoring_service_context = context.get(ContextType.MONITORING_SERVICE)
    registry_service_context: RegistryServiceContext = context.get(ContextType.REGISTRY_SERVICE)
    auth_service_context = context.get(ContextType.AUTH_SERVICE)

    if monitoring_service_context.exceeded_memory_limit:
        raise HTTPException(429, detail={
            "message": "Will not schedule job - memory limit exceeded.",
            "limit": monitoring_service_context.env.DCRX_API_MAX_MEMORY_PERCENT_USAGE,
            "current": monitoring_service_context.get_memory_usage_pct()
        })
    
    response = await registry_service_context.connection.select(
        filters={
            'registry_name': new_image.registry.registry_name
        }
    )

    if response.data is None or len(response.data) < 1:
        raise HTTPException(404, detail={
            "message": "Registry not found."
        })
    
    elif response.error:
        raise HTTPException(500, detail={
            "message": response.message,
            "error": response.error
        })
        
    registry = response.data.pop()

    dcrx_image = Image(
        new_image.name,
        tag=new_image.tag
    )

    layers: Layer = new_image.layers

    for layer in layers:

        if layer.layer_type == 'add':
            layer = RemoteAdd(
                source=layer.source,
                destination=layer.destination,
                user_id=layer.user_id,
                group_id=layer.group_id,
                permissions=layer.permissions,
                checksum=layer.checksum,
                link=layer.link
            )

        elif layer.layer_type == 'copy':
            layer = RemoteAdd(
                source=layer.source,
                destination=layer.destination,
                user_id=layer.user_id,
                group_id=layer.group_id,
                permissions=layer.permissions,
                link=layer.link
            )

        dcrx_image.layers.append(layer)

    decrypted_password = await auth_service_context.manager.decrypt_fernet(
        registry.registry_password
    )

    job = Job(
        job_service_context.connection,
        dcrx_image,
        Registry(
            id=registry.id,
            registry_name=registry.registry_name,
            registry_uri=registry.registry_uri,
            registry_user=registry.registry_user,
            registry_password=decrypted_password
        ),
        build_options=new_image.build_options,
        pool_size=job_service_context.queue.pool_size,
        timeout=job_service_context.env.DCRX_API_JOB_TIMEOUT,
        wait_timeout=job_service_context.env.DCRX_API_JOB_MAX_PENDING_WAIT
    )

    response = await job_service_context.queue.submit(job)

    if isinstance(response, ServerLimitException):
        raise HTTPException(429, detail={
            "message": response.message,
            "limit": response.limit,
            "current": response.current
            
        })
    
    return response


@jobs_router.get(
    "/jobs/images/{job_id}/get",
    responses={
        404: {
            "model": JobNotFoundException
        },
        500: {
            "model": DatabaseTransactionResult
        }
    }
)
async def get_job(job_id: str) -> JobMetadata:

    job_service_context = context.get(ContextType.JOB_SERVICE)

    retrieved_job = job_service_context.queue.get(
        uuid.UUID(job_id)
    )

    if isinstance(retrieved_job, JobNotFoundException):

        response = await job_service_context.connection.select(
            filters={
                'id': job_id
            }
        )

        if response.data is None or len(response.data) < 1:
            raise HTTPException(404, detail=retrieved_job.message)
        
        elif response.error:
            raise HTTPException(500, detail={
                "message": response.message,
                "error": response.error
            })
        
        job = response.data.pop()

        retrieved_job = JobMetadata(
            id=job.id,
            image_registry=job.image_registry,
            name=job.name,
            image=job.image,
            tag=job.tag,
            status=job.status,
            context=job.context,
            size=job.size
        )
    
    return retrieved_job


@jobs_router.delete(
    "/jobs/images/{job_id}/cancel",
    responses={
        404: {
            "model": JobNotFoundException
        },
        500: {
            "model": DatabaseTransactionResult
        }
    }
)
async def cancel_job(job_id: str) -> JobMetadata:

    job_service_context = context.get(ContextType.JOB_SERVICE)

    cancelled_job = job_service_context.queue.cancel(
        uuid.UUID(job_id)
    )

    if isinstance(cancelled_job, JobNotFoundException):
        raise HTTPException(404, detail=cancelled_job.message)
    
    return cancelled_job.metadata
    


    