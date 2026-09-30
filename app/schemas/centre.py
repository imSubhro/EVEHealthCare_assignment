from pydantic import BaseModel


class CentreCreate(BaseModel):
    name: str
    city: str
    address: str


class CentreResponse(BaseModel):
    id: str
    name: str
    city: str
    address: str

    model_config = {"from_attributes": True}


class CentreTestAttach(BaseModel):
    test_id: str
    price: float


class CentreTestUpdate(BaseModel):
    price: float | None = None
    is_active: bool | None = None


class CentreTestResponse(BaseModel):
    id: str
    centre_id: str
    test_id: str
    price: float
    is_active: bool

    model_config = {"from_attributes": True}


class CentreDetailResponse(CentreResponse):
    tests: list[CentreTestResponse] = []


class TestCreate(BaseModel):
    name: str
    description: str = ""


class TestResponse(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}
