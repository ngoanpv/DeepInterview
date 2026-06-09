"""Pydantic v2 mirror of packages/shared (the Zod source of truth).

Every wire field is snake_case and must stay field-identical with the TypeScript
contracts in packages/shared/src. Datetimes are plain ISO-8601 UTC strings
(e.g. "2026-06-08T09:00:00Z"), NOT datetime objects. The MODELS registry at the
bottom mirrors the SCHEMAS registry in packages/shared/src/registry.ts.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

LANGUAGES = ("en", "vi", "es", "zh", "hi", "id", "pt", "fr", "de", "ja")
Language = Literal["en", "vi", "es", "zh", "hi", "id", "pt", "fr", "de", "ja"]
Section = Literal["intro", "behavioral", "technical", "coding", "wrap"]
Seniority = Literal["intern", "junior", "mid", "senior", "staff", "principal"]
MasteryLevel = Literal["weak", "developing", "solid", "strong"]


def _validate_localized_text(v: dict[str, str]) -> dict[str, str]:
    if not isinstance(v, dict):
        raise ValueError("LocalizedText must be an object")
    if not v.get("en"):
        raise ValueError("LocalizedText must include a non-empty 'en' entry")
    for k in v:
        if k not in LANGUAGES:
            raise ValueError(f"LocalizedText contains an unsupported language key: {k}")
    return v


LocalizedText = Annotated[dict[str, str], AfterValidator(_validate_localized_text)]


# --- candidate ---------------------------------------------------------------


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    tech: list[str]


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institution: str
    degree: str
    field: str | None = None
    year: int | None = None


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    headline: str
    summary_120w: str
    years_experience: int
    seniority: Seniority
    skills: list[str]
    projects: list[Project]
    achievements: list[str]
    education: list[Education]
    spoken_languages: list[str]
    links: list[str] = Field(default_factory=list)


# --- job ---------------------------------------------------------------------


class JobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    company_name: str
    location: str | None = None
    seniority: Seniority
    must_have: list[str]
    nice_to_have: list[str]
    responsibilities: list[str]
    tech_stack: list[str]
    raw_text: str


# --- company -----------------------------------------------------------------


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str
    snippet: str | None = None


class CompanyIntel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    summary: str
    industry: str | None = None
    tech_stack: list[str]
    values: list[str]
    interview_process: list[str]
    recent_news: list[str]
    citations: list[Citation]


# --- gap ---------------------------------------------------------------------


class GapAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strengths: list[str]
    gaps: list[str]
    probe_targets: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    summary: str


# --- question ----------------------------------------------------------------


class RubricItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    criterion: str
    weight: float
    description: str


class PlannedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    section: Section
    text: LocalizedText
    difficulty: int
    rubric: list[RubricItem]
    followups: list[str]
    target_competency: str


class LanguageMode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary: Language
    mixed: bool


class QuestionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections_order: list[Section]
    questions: list[PlannedQuestion]
    time_budget_min: int
    language_mode: LanguageMode


# --- answer ------------------------------------------------------------------


class AnswerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    transcript: str
    started_at: str
    ended_at: str
    duration_sec: float | None = None
    followups_asked: list[str] = Field(default_factory=list)


# --- score -------------------------------------------------------------------


class CompetencyScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    competency: str
    score: float
    evidence: str
    level: MasteryLevel


class LanguageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fluency_score: float
    filler_word_count: int
    clarity_score: float
    code_switching_notes: str
    pronunciation_notes: str
    summary: str


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    answer: str


class ScoreCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_score: float
    competency_scores: list[CompetencyScore]
    strengths: list[str]
    weaknesses: list[str]
    weak_competencies: list[str]
    model_answers: list[ModelAnswer]
    next_steps: list[str]
    language_report: LanguageReport
    summary: str
    # Fraction of planned questions actually answered (0.0-1.0). Lets consumers
    # distinguish a low score caused by a short/aborted interview from genuinely
    # weak answers; unanswered questions are excluded from overall_score and
    # weak_competencies. Defaults to 1.0 for backward compatibility with
    # scorecards persisted before this field existed.
    coverage_pct: float = 1.0


# --- coach (WP-4 study coach) ------------------------------------------------


MasteryState = Literal["unseen", "learning", "shaky", "mastered"]


class StudyModule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    competency: str
    status: MasteryState
    est_min: int
    rationale: str


class StudyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modules: list[StudyModule]
    summary: str
    total_min: int


class CoachChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    query: str
    lang: Language


class CoachReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    citations: list[Citation]
    follow_ups: list[str]


# --- interview context -------------------------------------------------------


class InterviewContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    candidate: CandidateProfile
    job: JobSpec
    company: CompanyIntel
    gap: GapAnalysis
    plan: QuestionPlan
    cursor: int = 0
    answers: list[AnswerRecord] = Field(default_factory=list)
    scorecard: ScoreCard | None = None


# --- room --------------------------------------------------------------------


class TokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    identity: str
    name: str | None = None


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str
    url: str
    room: str


class RoomMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str


# --- api ---------------------------------------------------------------------


class PrepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cv_url: str
    jd_text: str
    company: str
    language_mode: LanguageMode


class PrepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str


class ScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    scorecard: ScoreCard


class KbIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    files: list[str]


class KbIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: str


class KbQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    query: str
    lang: Language


class KbQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    citations: list[Citation]


# --- registry (mirrors packages/shared/src/registry.ts SCHEMAS) --------------

MODELS: dict[str, type[BaseModel]] = {
    "Project": Project,
    "Education": Education,
    "CandidateProfile": CandidateProfile,
    "JobSpec": JobSpec,
    "Citation": Citation,
    "CompanyIntel": CompanyIntel,
    "GapAnalysis": GapAnalysis,
    "RubricItem": RubricItem,
    "PlannedQuestion": PlannedQuestion,
    "LanguageMode": LanguageMode,
    "QuestionPlan": QuestionPlan,
    "AnswerRecord": AnswerRecord,
    "CompetencyScore": CompetencyScore,
    "LanguageReport": LanguageReport,
    "ModelAnswer": ModelAnswer,
    "ScoreCard": ScoreCard,
    "StudyModule": StudyModule,
    "StudyPlan": StudyPlan,
    "CoachChatRequest": CoachChatRequest,
    "CoachReply": CoachReply,
    "InterviewContext": InterviewContext,
    "TokenRequest": TokenRequest,
    "TokenResponse": TokenResponse,
    "RoomMetadata": RoomMetadata,
    "PrepRequest": PrepRequest,
    "PrepResponse": PrepResponse,
    "ScoreRequest": ScoreRequest,
    "ScoreResponse": ScoreResponse,
    "KbIngestRequest": KbIngestRequest,
    "KbIngestResponse": KbIngestResponse,
    "KbQueryRequest": KbQueryRequest,
    "KbQueryResponse": KbQueryResponse,
}
