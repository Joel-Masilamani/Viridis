from io import BytesIO
import os
from typing import List

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import crud, schemas
from .business import calculate_sustainability_score, get_emission_factor
from .database import SessionLocal
from .ml import prepare_emission_timeseries, train_predict_emissions
from .models import Emission, Hospital


def get_cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


app = FastAPI(title="Viridis API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "Viridis backend is running!"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1;"))
    return {"db_connection": result.first() is not None}


@app.post("/hospitals/", response_model=schemas.HospitalRead, status_code=status.HTTP_201_CREATED)
def create_hospital(hospital: schemas.HospitalCreate, db: Session = Depends(get_db)):
    return crud.create_hospital(db, hospital)


@app.get("/hospitals/", response_model=List[schemas.HospitalRead])
def read_hospitals(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_hospitals(db, skip, limit)


@app.get("/hospitals/{hospital_id}", response_model=schemas.HospitalRead)
def read_hospital(hospital_id: int, db: Session = Depends(get_db)):
    hospital = crud.get_hospital(db, hospital_id)
    if hospital is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


@app.delete("/hospitals/{hospital_id}", response_model=schemas.HospitalRead)
def delete_hospital(hospital_id: int, db: Session = Depends(get_db)):
    hospital = crud.delete_hospital(db, hospital_id)
    if hospital is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


@app.post("/departments/", response_model=schemas.DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(department: schemas.DepartmentCreate, db: Session = Depends(get_db)):
    return crud.create_department(db, department)


@app.get("/departments/", response_model=List[schemas.DepartmentRead])
def read_departments(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_departments(db, skip, limit)


@app.get("/departments/{department_id}", response_model=schemas.DepartmentRead)
def read_department(department_id: int, db: Session = Depends(get_db)):
    department = crud.get_department(db, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


@app.post("/emissions/", response_model=schemas.EmissionRead, status_code=status.HTTP_201_CREATED)
def create_emission(emission: schemas.EmissionCreate, db: Session = Depends(get_db)):
    return crud.create_emission(db, emission)


@app.get("/emissions/", response_model=List[schemas.EmissionRead])
def read_emissions(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_emissions(db, skip, limit)


@app.get("/emissions/{emission_id}", response_model=schemas.EmissionRead)
def read_emission(emission_id: int, db: Session = Depends(get_db)):
    emission = crud.get_emission(db, emission_id)
    if emission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emission not found")
    return emission


@app.post("/upload-emissions/")
async def upload_emissions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV uploads are currently supported.",
        )

    contents = await file.read()
    try:
        df = pd.read_csv(BytesIO(contents))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse CSV file.",
        ) from exc

    required_columns = {"hospital_id", "department_id", "date", "category", "quantity"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required CSV columns: {', '.join(missing_columns)}",
        )

    try:
        for _, row in df.iterrows():
            subcategory = "" if pd.isna(row.get("subcategory", "")) else str(row.get("subcategory", ""))
            category = str(row["category"])
            quantity = float(row["quantity"])
            factor = row.get("emission_factor")
            emission_factor = (
                get_emission_factor(category, subcategory)
                if pd.isna(factor)
                else float(factor)
            )
            co2e = quantity * emission_factor

            db.add(
                Emission(
                    hospital_id=int(row["hospital_id"]),
                    department_id=int(row["department_id"]),
                    date=pd.to_datetime(row["date"]).date(),
                    category=category,
                    subcategory=subcategory or None,
                    quantity=quantity,
                    unit=None if pd.isna(row.get("unit")) else str(row.get("unit")),
                    emission_factor=emission_factor,
                    co2e=round(co2e, 4),
                )
            )
        db.commit()
    except (KeyError, TypeError, ValueError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV contains invalid emission data.",
        ) from exc

    return {"success": True, "rows": len(df)}


@app.get("/dashboard/{hospital_id}")
def get_dashboard_data(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

    rows = (
        db.query(Emission.category, func.sum(Emission.co2e))
        .filter(Emission.hospital_id == hospital_id)
        .group_by(Emission.category)
        .all()
    )
    return [{"category": category, "total_co2e": float(total or 0)} for category, total in rows]


@app.post("/compliance-reports/", response_model=schemas.ComplianceReportRead, status_code=status.HTTP_201_CREATED)
def create_report(report: schemas.ComplianceReportCreate, db: Session = Depends(get_db)):
    return crud.create_compliance_report(db, report)


@app.get("/compliance-reports/", response_model=List[schemas.ComplianceReportRead])
def read_reports(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_compliance_reports(db, skip, limit)


@app.get("/compliance-reports/{report_id}", response_model=schemas.ComplianceReportRead)
def read_report(report_id: int, db: Session = Depends(get_db)):
    report = crud.get_compliance_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@app.post("/benchmarks/", response_model=schemas.BenchmarkRead, status_code=status.HTTP_201_CREATED)
def create_benchmark(benchmark: schemas.BenchmarkCreate, db: Session = Depends(get_db)):
    return crud.create_benchmark(db, benchmark)


@app.get("/benchmarks/", response_model=List[schemas.BenchmarkRead])
def read_benchmarks(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_benchmarks(db, skip, limit)


@app.get("/benchmarks/{benchmark_id}", response_model=schemas.BenchmarkRead)
def read_benchmark(benchmark_id: int, db: Session = Depends(get_db)):
    benchmark = crud.get_benchmark(db, benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark not found")
    return benchmark


@app.post("/achievements/", response_model=schemas.AchievementRead, status_code=status.HTTP_201_CREATED)
def create_achievement(achievement: schemas.AchievementCreate, db: Session = Depends(get_db)):
    return crud.create_achievement(db, achievement)


@app.get("/achievements/", response_model=List[schemas.AchievementRead])
def read_achievements(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return crud.get_achievements(db, skip, limit)


@app.get("/achievements/{achievement_id}", response_model=schemas.AchievementRead)
def read_achievement(achievement_id: int, db: Session = Depends(get_db)):
    achievement = crud.get_achievement(db, achievement_id)
    if achievement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")
    return achievement


@app.get("/predict-trend/{hospital_id}")
def predict_hospital_emission_trend(hospital_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Emission.date, Emission.co2e)
        .filter(Emission.hospital_id == hospital_id)
        .all()
    )
    if not rows:
        return {"detail": "No emission data found"}

    df = prepare_emission_timeseries(rows)
    future_months, predictions = train_predict_emissions(df)
    if future_months is None or predictions is None:
        return {"detail": "Not enough data to predict"}

    prediction_list = [
        {"month_offset": int(month), "predicted_co2e": float(prediction)}
        for month, prediction in zip(future_months, predictions)
    ]
    return {
        "history": df[["date", "co2e"]].to_dict("records"),
        "predictions": prediction_list,
    }


@app.get("/sustainability-score/{hospital_id}")
def sustainability_score(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

    beds = hospital.beds or 1

    total_kwh = (
        db.query(func.sum(Emission.quantity))
        .filter(Emission.hospital_id == hospital_id)
        .filter(Emission.category == "electricity")
        .scalar()
        or 0
    )
    epi = total_kwh / beds

    total_waste = (
        db.query(func.sum(Emission.quantity))
        .filter(Emission.hospital_id == hospital_id)
        .filter(Emission.category == "biomedical")
        .scalar()
        or 0
    )
    segregated_waste = (
        db.query(func.sum(Emission.quantity))
        .filter(Emission.hospital_id == hospital_id)
        .filter(Emission.category == "biomedical")
        .filter(Emission.subcategory == "incinerated")
        .scalar()
        or 0
    )
    waste_segregation = segregated_waste / total_waste if total_waste else 0

    total_renewable = (
        db.query(func.sum(Emission.quantity))
        .filter(Emission.hospital_id == hospital_id)
        .filter(Emission.category == "electricity")
        .filter(Emission.subcategory == "renewable")
        .scalar()
        or 0
    )
    renewable_pct = total_renewable / total_kwh if total_kwh else 0

    emission_year = func.extract("year", Emission.date)
    yearly_emissions = (
        db.query(emission_year, func.sum(Emission.co2e))
        .filter(Emission.hospital_id == hospital_id)
        .group_by(emission_year)
        .order_by(emission_year.desc())
        .limit(2)
        .all()
    )
    trend = 0
    if len(yearly_emissions) == 2:
        latest = yearly_emissions[0][1]
        previous = yearly_emissions[1][1]
        trend = ((previous - latest) / previous) * 100 if previous else 0

    grade = calculate_sustainability_score(epi, waste_segregation, renewable_pct, trend)
    return {
        "grade": grade,
        "details": {
            "epi": epi,
            "waste_segregation": waste_segregation,
            "renewable_pct": renewable_pct,
            "trend": trend,
            "total_kwh": total_kwh,
        },
    }
