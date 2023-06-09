from dcrx_api.database import (
    DatabaseConnection,
    ConnectionConfig
)
from dcrx_api.database.models import DatabaseTransactionResult
from dcrx_api.env import Env
from typing import (
    List,
    Dict,
    Any,
    Union,
    Tuple
)
from .models import JobMetadata
from .status import JobStatus
from .table import JobsTable


class JobsConnection(DatabaseConnection[JobMetadata]):

    def __init__(self, env: Env) -> None:
        super().__init__(
            ConnectionConfig(
                database_username=env.DCRX_API_DATABASE_USER,
                database_password=env.DCRX_API_DATABASE_PASSWORD,
                database_type=env.DCRX_API_DATABASE_TYPE,
                database_uri=env.DCRX_API_DATABASE_URI,
                database_port=env.DCRX_API_DATABASE_PORT,
                database_name=env.DCRX_API_DATABASE_NAME,
                database_transaction_retries=env.DCRX_API_DATABASE_TRANSACTION_RETRIES
            )
        )

        self.table: JobsTable[JobMetadata] = JobsTable(
            'jobs',
            database_type=self.config.database_type
        )

    async def init(self) -> DatabaseTransactionResult[JobMetadata]:
        return await self.create_table(self.table.selected.table)

    async def select(
        self, 
        filters: Dict[str, Union[Any, Tuple[Any, ...]]]={}
    ) -> DatabaseTransactionResult[JobMetadata]:
        return await self.get(
            self.table.select(
                filters=filters
            )
        )
    
    async def create(
        self, 
        jobs: List[JobMetadata]
    ) -> DatabaseTransactionResult[JobMetadata]:
       return await self.insert_or_update(
           self.table.insert(jobs)
       )
    
    async def update(
        self, 
        jobs: List[JobMetadata],
        filters: Dict[str, Any]={}
    ) -> DatabaseTransactionResult[JobMetadata]:
        return await self.insert_or_update(
            self.table.update(
                jobs,
                filters={
                    name: self.table.selected.types_map.get(
                        name
                    )(value) for name, value in filters.items()
                }
            )
        )
    
    async def remove(
        self,
        filters: Dict[str, Any]
    ) -> DatabaseTransactionResult[JobMetadata]:
        return await self.delete([
            self.table.delete({
                name: self.table.selected.types_map.get(
                    name
                )(value) for name, value in filters.items()
            })
        ])
    
    async def drop(self) -> DatabaseTransactionResult[JobMetadata]:
        return await self.drop_table(self.table)
    
