from typing import Optional, List, Dict, Any
from backend.app.db.connection import get_db
from backend.app.db.repositories.patient_repo import PatientRepository

class PatientService:
    @staticmethod
    def create_patient(data: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
        with get_db(db_path) as conn:
            return PatientRepository.create(conn, data)

    @staticmethod
    def get_patient(patient_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return PatientRepository.get_by_id(conn, patient_id)

    @staticmethod
    def get_patient_by_identifier(patient_identifier: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return PatientRepository.get_by_identifier(conn, patient_identifier)

    @staticmethod
    def search_patients(query: Optional[str] = None, limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return PatientRepository.search(conn, query, limit)

    @staticmethod
    def update_patient(patient_id: str, data: Dict[str, Any], db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with get_db(db_path) as conn:
            return PatientRepository.update(conn, patient_id, data)

    @staticmethod
    def delete_patient(patient_id: str, force: bool = False, db_path: Optional[str] = None) -> bool:
        with get_db(db_path) as conn:
            return PatientRepository.delete(conn, patient_id, force)
