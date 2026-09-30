from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    items: list
    total: int
    limit: int
    offset: int
