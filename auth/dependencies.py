import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

security = HTTPBearer(auto_error=False)


class CurrentPatient:
    def __init__(self, patient_id: int, uid: str, roles: list[str]) -> None:
        self.patient_id = patient_id
        self.uid = uid          # Mammoth UUID
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _extract_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return credentials.credentials


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _build_patient(payload: dict) -> CurrentPatient:
    patient_id = payload.get("patient_id")
    uid = payload.get("uid")
    if patient_id is None or uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")
    return CurrentPatient(patient_id=int(patient_id), uid=uid, roles=payload.get("roles", []))


async def get_current_patient(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentPatient:
    token = _extract_token(credentials)
    payload = _decode_token(token)
    return _build_patient(payload)


def require_patient(patient: CurrentPatient = Depends(get_current_patient)) -> CurrentPatient:
    if not patient.has_role("ROLE_PATIENTS"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return patient
