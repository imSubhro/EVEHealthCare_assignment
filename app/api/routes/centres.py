from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.schemas.centre import (
    CentreCreate,
    CentreDetailResponse,
    CentreResponse,
    CentreTestAttach,
    CentreTestResponse,
    CentreTestUpdate,
    TestCreate,
    TestResponse,
)

router = APIRouter(tags=["centres"])


@router.get("/centres", response_model=list[CentreDetailResponse])
def list_centres(
    city: str | None = None,
    test_name: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(DiagnosticCentre)
    if city:
        query = query.filter(DiagnosticCentre.city.ilike(f"%{city}%"))
    if test_name:
        query = (
            query.join(CentreTest, CentreTest.centre_id == DiagnosticCentre.id)
            .join(DiagnosticTest, DiagnosticTest.id == CentreTest.test_id)
            .filter(
                CentreTest.is_active == True,  # noqa: E712
                DiagnosticTest.name.ilike(f"%{test_name}%"),
            )
            .distinct()
        )
    query = query.order_by(DiagnosticCentre.created_at.desc())
    query = query.offset(offset).limit(limit)
    centres = query.all()

    results = []
    for centre in centres:
        ct_query = db.query(CentreTest).filter(
            CentreTest.centre_id == centre.id,
            CentreTest.is_active == True,  # noqa: E712
        )
        tests = ct_query.all()
        results.append(
            CentreDetailResponse(
                id=centre.id,
                name=centre.name,
                city=centre.city,
                address=centre.address,
                tests=[CentreTestResponse.model_validate(t) for t in tests],
            )
        )
    return results


@router.get("/centres/{centre_id}", response_model=CentreDetailResponse)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    centre = db.query(DiagnosticCentre).filter(DiagnosticCentre.id == centre_id).first()
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Centre not found", "code": "CENTRE_NOT_FOUND"},
        )
    tests = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.is_active == True)  # noqa: E712
        .all()
    )
    return CentreDetailResponse(
        id=centre.id,
        name=centre.name,
        city=centre.city,
        address=centre.address,
        tests=[CentreTestResponse.model_validate(t) for t in tests],
    )


@router.post(
    "/centres", response_model=CentreResponse, status_code=status.HTTP_201_CREATED
)
def create_centre(
    data: CentreCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    existing = (
        db.query(DiagnosticCentre)
        .filter(
            DiagnosticCentre.name == data.name,
            DiagnosticCentre.city == data.city,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "Centre already exists in this city",
                "code": "DUPLICATE_CENTRE",
            },
        )
    centre = DiagnosticCentre(name=data.name, city=data.city, address=data.address)
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("/tests", response_model=list[TestResponse])
def list_tests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    tests = (
        db.query(DiagnosticTest)
        .order_by(DiagnosticTest.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return tests


@router.post("/tests", response_model=TestResponse, status_code=status.HTTP_201_CREATED)
def create_test(
    data: TestCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    existing = db.query(DiagnosticTest).filter(DiagnosticTest.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Test already exists", "code": "DUPLICATE_TEST"},
        )
    test = DiagnosticTest(name=data.name, description=data.description)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.post(
    "/centres/{centre_id}/tests",
    response_model=CentreTestResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_test_to_centre(
    centre_id: str,
    data: CentreTestAttach,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    centre = db.query(DiagnosticCentre).filter(DiagnosticCentre.id == centre_id).first()
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Centre not found", "code": "CENTRE_NOT_FOUND"},
        )
    test = db.query(DiagnosticTest).filter(DiagnosticTest.id == data.test_id).first()
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Test not found", "code": "TEST_NOT_FOUND"},
        )
    if data.price <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "Price must be positive", "code": "INVALID_PRICE"},
        )
    existing = (
        db.query(CentreTest)
        .filter(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == data.test_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "Test already attached to this centre",
                "code": "DUPLICATE_ATTACH",
            },
        )
    ct = CentreTest(centre_id=centre_id, test_id=data.test_id, price=data.price)
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return ct


@router.patch(
    "/centres/{centre_id}/tests/{test_id}",
    response_model=CentreTestResponse,
)
def update_centre_test(
    centre_id: str,
    test_id: str,
    data: CentreTestUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    ct = (
        db.query(CentreTest)
        .filter(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
        )
        .first()
    )
    if ct is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": "Centre-test link not found",
                "code": "CENTRE_TEST_NOT_FOUND",
            },
        )
    if data.price is not None:
        if data.price <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"detail": "Price must be positive", "code": "INVALID_PRICE"},
            )
        ct.price = data.price
    if data.is_active is not None:
        ct.is_active = data.is_active
    db.commit()
    db.refresh(ct)
    return ct
