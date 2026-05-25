import json
import logging
import os
from typing import List

import redis
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rdkit import Chem
from sqlalchemy import Column, Integer, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from modules.module1 import substructure_search


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_app")


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./molecules.db"
)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)


if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


try:
    redis_client = redis.from_url(
        REDIS_URL,
        decode_responses=True
    )
    redis_client.ping()
except redis.RedisError:
    redis_client = None


class Molecule(Base):
    __tablename__ = "molecules"

    id = Column(Integer, primary_key=True, index=True)
    smiles = Column(String, index=True)
    name = Column(String, default="")


Base.metadata.create_all(bind=engine)


class MoleculeCreate(BaseModel):
    smiles: str
    name: str = ""


class MoleculeUpdate(BaseModel):
    smiles: str
    name: str = ""


class SearchRequest(BaseModel):
    molecules: List[str]
    substructure: str


app = FastAPI(title="Molecule Search API")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_smiles(smiles: str):
    if not smiles.strip():
        raise HTTPException(status_code=422, detail="SMILES is empty")

    molecule = Chem.MolFromSmiles(smiles)

    if molecule is None:
        raise HTTPException(status_code=422, detail="Incorrect SMILES")


def get_cache_key(substructure: str):
    return "search:" + substructure.strip()


def get_cached_result(substructure: str):
    if redis_client is None:
        return None

    key = get_cache_key(substructure)

    try:
        data = redis_client.get(key)
    except redis.RedisError:
        return None

    if data is None:
        return None

    return json.loads(data)


def save_cached_result(substructure: str, result):
    if redis_client is None:
        return

    key = get_cache_key(substructure)

    try:
        redis_client.setex(
            key,
            300,
            json.dumps(result)
        )
    except redis.RedisError:
        pass


def clear_search_cache():
    if redis_client is None:
        return

    try:
        keys = list(redis_client.scan_iter("search:*"))
        if keys:
            redis_client.delete(*keys)
    except redis.RedisError:
        pass


@app.post("/molecules")
def add_molecule(item: MoleculeCreate, db: Session = Depends(get_db)):
    logger.info("POST /molecules")

    smiles = item.smiles.strip()
    name = item.name.strip()

    check_smiles(smiles)

    molecule = Molecule(smiles=smiles, name=name)
    db.add(molecule)
    db.commit()
    db.refresh(molecule)

    clear_search_cache()

    return {
        "status": "added",
        "molecule": {
            "id": molecule.id,
            "smiles": molecule.smiles,
            "name": molecule.name
        }
    }


@app.get("/molecules")
def list_molecules(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    logger.info("GET /molecules")

    if skip < 0:
        skip = 0

    if limit <= 0:
        limit = 10

    total = db.query(func.count(Molecule.id)).scalar()
    molecules = db.query(Molecule).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "molecules": [
            {
                "id": molecule.id,
                "smiles": molecule.smiles,
                "name": molecule.name
            }
            for molecule in molecules
        ]
    }


@app.get("/molecules/{molecule_id}")
def get_molecule(molecule_id: int, db: Session = Depends(get_db)):
    logger.info("GET /molecules/%s", molecule_id)

    molecule = db.query(Molecule).filter(Molecule.id == molecule_id).first()

    if molecule is None:
        raise HTTPException(status_code=404, detail="Molecule not found")

    return {
        "id": molecule.id,
        "smiles": molecule.smiles,
        "name": molecule.name
    }


@app.put("/molecules/{molecule_id}")
def update_molecule(
    molecule_id: int,
    item: MoleculeUpdate,
    db: Session = Depends(get_db)
):
    logger.info("PUT /molecules/%s", molecule_id)

    molecule = db.query(Molecule).filter(Molecule.id == molecule_id).first()

    if molecule is None:
        raise HTTPException(status_code=404, detail="Molecule not found")

    smiles = item.smiles.strip()
    name = item.name.strip()

    check_smiles(smiles)

    molecule.smiles = smiles
    molecule.name = name

    db.commit()
    db.refresh(molecule)

    clear_search_cache()

    return {
        "status": "updated",
        "molecule": {
            "id": molecule.id,
            "smiles": molecule.smiles,
            "name": molecule.name
        }
    }


@app.delete("/molecules/{molecule_id}")
def delete_molecule(molecule_id: int, db: Session = Depends(get_db)):
    logger.info("DELETE /molecules/%s", molecule_id)

    molecule = db.query(Molecule).filter(Molecule.id == molecule_id).first()

    if molecule is None:
        raise HTTPException(status_code=404, detail="Molecule not found")

    result = {
        "id": molecule.id,
        "smiles": molecule.smiles,
        "name": molecule.name
    }

    db.delete(molecule)
    db.commit()

    clear_search_cache()

    return {
        "status": "deleted",
        "molecule": result
    }


@app.post("/search")
def search_molecules(request: SearchRequest):
    logger.info("POST /search")

    try:
        result = substructure_search(
            request.molecules,
            request.substructure
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    return {"result": result}


@app.post("/search/database")
def search_in_database(
    substructure: str,
    db: Session = Depends(get_db)
):
    logger.info("POST /search/database")

    substructure = substructure.strip()

    if not substructure:
        raise HTTPException(status_code=422, detail="Substructure is empty")

    cached_result = get_cached_result(substructure)
    if cached_result is not None:
        return {
            "result": cached_result,
            "source": "cache"
        }

    molecules = db.query(Molecule).all()
    smiles_list = [molecule.smiles for molecule in molecules]

    try:
        found_smiles = substructure_search(smiles_list, substructure)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    unique_smiles = list(dict.fromkeys(found_smiles))

    result = []
    for smiles in unique_smiles:
        molecule = db.query(Molecule).filter(Molecule.smiles == smiles).first()
        if molecule is not None:
            result.append({
                "id": molecule.id,
                "smiles": molecule.smiles,
                "name": molecule.name
            })

    save_cached_result(substructure, result)

    return {
        "result": result,
        "source": "database"
    }