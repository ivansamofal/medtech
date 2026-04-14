from enum import Enum


class QuestAppointmentStatusEnum(str, Enum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    BOOKED = "booked"
    HOLD = "hold"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class QuestOrderStatusEnum(str, Enum):
    NEW = "new"
    SENT = "sent"
    ERROR = "error"
    ERROR_RESULT = "error_result"
    COMPLETED = "completed"


class QuestResultTypeEnum(str, Enum):
    HL7 = "HL7"
    PRINTABLE = "PRINTABLE"


class QuestDocumentTypeEnum(str, Enum):
    REQ = "REQ"


class QuestBookingEndpointEnum(str, Enum):
    PATIENT_SERVICE_CENTERS = "/assets/facilities/psc"
    APPOINTMENTS = "/assets/psc/schedule/appointments"
    CREATE_APPOINTMENT = "/assets/psc/schedule"
    MODIFY_APPOINTMENT = "/assets/psc/schedule/appointments/modify"
    HOLD_APPOINTMENT = "/assets/psc/schedule/appointments/holdAppointment"
    CANCEL_APPOINTMENT = "/assets/psc/schedule/appointments/cancel/"
    APPOINTMENT_DETAILS = "/assets/psc/schedule/appointments/details/confirmation/"
    LOCATIONS = "/assets/psc/schedule/locations"


class QuestOrderUrlEnum(str, Enum):
    TOKEN = "/oauth/token"
    ORDER_SUBMISSION = "/orders"
    ORDER_DOCUMENT = "/orders/documents"
    GET_RESULTS = "/results"
    ACKNOWLEDGE_RESULTS = "/results/acknowledge"


class QuestClientLogTypeEnum(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
