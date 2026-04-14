from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


class CurrentPatient:
    def __init__(self, patient_id: int, uid: str, roles: list[str]) -> None:
        self.patient_id = patient_id
        self.uid = uid          # Mammoth UUID
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles


async def get_current_patient(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentPatient:
    """
    Validates JWT and returns the current patient.
    Currently a stub – wire up real JWT validation here.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    # TODO: decode JWT, validate signature with settings.jwt_secret
    # For now, accept any bearer token and return a mock patient
    return CurrentPatient(patient_id=1, uid="test-uid", roles=["ROLE_PATIENTS"])


def require_patient(patient: CurrentPatient = Depends(get_current_patient)) -> CurrentPatient:
    if not patient.has_role("ROLE_PATIENTS"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return patient
