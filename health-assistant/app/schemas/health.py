"""건강검진 API 응답 스키마. 필드 이름은 안내서의 응답 키를 그대로 쓴다."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# 검진 항목 키. 응답과 참고치 표가 같은 키를 쓴다. 순서는 안내서의 등장 순서
METRIC_KEYS: tuple[str, ...] = (
    "height",
    "weight",
    "waists",
    "BMI",
    "vision",
    "hearing",
    "bloodPressure",
    "proteinuria",
    "hemoglobin",
    "fastingBloodGlucose",
    "totalCholesterol",
    "HDLCholesterol",
    "triglyceride",
    "LDLCholesterol",
    "serumCreatinine",
    "GFR",
    "AST",
    "ALT",
    "yGPT",
    "chestXrayResult",
    "osteoporosis",
)


class Overview(BaseModel):
    """검진 1회분의 측정값. 값은 안내서대로 전부 문자열이다."""

    model_config = ConfigDict(extra="forbid")

    checkupDate: str
    height: str
    weight: str
    waists: str
    BMI: str
    vision: str
    hearing: str
    bloodPressure: str
    proteinuria: str
    hemoglobin: str
    fastingBloodGlucose: str
    totalCholesterol: str
    HDLCholesterol: str
    triglyceride: str
    LDLCholesterol: str
    serumCreatinine: str
    GFR: str
    AST: str
    ALT: str
    yGPT: str
    chestXrayResult: str
    osteoporosis: str
    evaluation: str


class Reference(BaseModel):
    """참고치 표의 한 행. 정상(B)와 질환의심 행은 일부 항목이 없어 전부 선택 필드"""

    model_config = ConfigDict(extra="forbid")

    refType: str
    height: str | None = None
    weight: str | None = None
    waists: str | None = None
    BMI: str | None = None
    vision: str | None = None
    hearing: str | None = None
    bloodPressure: str | None = None
    proteinuria: str | None = None
    hemoglobin: str | None = None
    fastingBloodGlucose: str | None = None
    totalCholesterol: str | None = None
    HDLCholesterol: str | None = None
    triglyceride: str | None = None
    LDLCholesterol: str | None = None
    serumCreatinine: str | None = None
    GFR: str | None = None
    AST: str | None = None
    ALT: str | None = None
    yGPT: str | None = None
    chestXrayResult: str | None = None
    osteoporosis: str | None = None


class CheckupResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caseType: str
    checkupType: str
    checkupDate: str
    organizationName: str
    pdfData: str
    questionnaire: list[Any] = []


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patientName: str
    overviewList: list[Overview]
    referenceList: list[Reference]
    resultList: list[CheckupResult]


class HealthResponse(BaseModel):
    status: Literal["success"] = "success"
    data: HealthData
