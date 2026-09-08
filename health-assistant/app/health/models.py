"""건강검진 API 응답 스키마.

필드 이름은 파이썬 관례(snake_case)가 아니라 과제 안내서의 응답 키를 그대로 쓴다.
응답 JSON의 키가 안내서와 1:1로 맞는 것이 이 모델의 존재 이유이고, 별칭을 두면
이름을 둘씩 관리해야 한다.
"""

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
    """참고치 표의 한 행 (단위, 정상(A), 정상(B), 질환의심).

    정상(B)와 질환의심 행은 일부 항목이 없으므로 전부 선택 필드다. 응답에서는 None인
    필드를 빼서 안내서와 같은 모양을 만든다. 빈 문자열("")은 값이므로 남긴다.
    """

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
