import logging
import os
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from modules.module1 import substructure_search


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_app")


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./molecules.db"
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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/molecules")
def add_molecule(item: MoleculeCreate, db: Session = Depends(get_db)):
    logger.info("POST /molecules")

    molecule = Molecule(smiles=item.smiles, name=item.name)
    db.add(molecule)
    db.commit()
    db.refresh(molecule)

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

    molecules = db.query(Molecule).offset(skip).limit(limit).all()

    return {
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

    molecule.smiles = item.smiles
    molecule.name = item.name

    db.commit()
    db.refresh(molecule)

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

    molecules = db.query(Molecule).all()
    smiles_list = [molecule.smiles for molecule in molecules]

    try:
        result = substructure_search(smiles_list, substructure)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    return {"result": result}