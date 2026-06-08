"""Prompt builders for the prep graph nodes.

English-first: every system prompt is in English, but where a node produces
``LocalizedText`` (the question planner) it instructs the model to fill BOTH the
``en`` entry and the candidate's primary language. The mock LLM ignores prompt
content entirely, so these strings only matter once a real provider is wired.

Each builder returns a ``(system, user)`` tuple. ``user`` payloads are compact,
model-readable summaries of upstream state so the live agent prompt downstream
stays small (per the project's prep/live/post split).
"""

from __future__ import annotations

from ..shared_models import (
    CandidateProfile,
    CompanyIntel,
    GapAnalysis,
    JobSpec,
    LanguageMode,
    PrepRequest,
)

# Human-readable language names for the small set we support, so prompts can say
# "also write Vietnamese" rather than leaking the raw code to the model.
_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "vi": "Vietnamese",
    "es": "Spanish",
    "zh": "Chinese",
    "hi": "Hindi",
    "id": "Indonesian",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
}


def language_name(code: str) -> str:
    """Return a human-readable language name for ``code`` (defaults to the code)."""
    return _LANGUAGE_NAMES.get(code, code)


# --- cv analysis -------------------------------------------------------------


def cv_analysis_prompts(cv_text: str) -> tuple[str, str]:
    """System/user prompts to extract a ``CandidateProfile`` from raw CV text."""
    system = (
        "You are a meticulous technical recruiter. Read the candidate's CV/resume "
        "text and extract a structured profile. Infer seniority from years of "
        "experience and scope of work. Be faithful to the source; do not invent "
        "employers, degrees, or skills that are not supported by the text. Keep "
        "summary_120w to roughly 120 words. Respond ONLY with the requested schema."
    )
    user = f"CANDIDATE CV / RESUME TEXT:\n{cv_text}"
    return system, user


# --- jd analysis -------------------------------------------------------------


def jd_analysis_prompts(jd_text: str, company: str) -> tuple[str, str]:
    """System/user prompts to extract a ``JobSpec`` from the job description."""
    system = (
        "You are a hiring manager. Parse the job description into a structured job "
        "spec: title, seniority, must-have vs nice-to-have requirements, core "
        "responsibilities, and the technology stack. Preserve the original text in "
        "raw_text. Do not fabricate requirements the description does not state. "
        "Respond ONLY with the requested schema."
    )
    user = f"TARGET COMPANY: {company}\n\nJOB DESCRIPTION:\n{jd_text}"
    return system, user


# --- company research --------------------------------------------------------


def company_research_prompts(company: str, snippets: str) -> tuple[str, str]:
    """System/user prompts to synthesize ``CompanyIntel`` from search snippets."""
    system = (
        "You are an interview-prep researcher. Using ONLY the provided web search "
        "snippets, summarize what a candidate should know before interviewing: a "
        "short company summary, industry, likely technology stack, stated values, "
        "the typical interview process and stages, and any recent news. If a field "
        "is not supported by the snippets, leave its list empty rather than "
        "guessing. Leave citations empty; the pipeline fills them. Respond ONLY "
        "with the requested schema."
    )
    user = f"COMPANY: {company}\n\nWEB SEARCH SNIPPETS:\n{snippets}"
    return system, user


# --- gap matching ------------------------------------------------------------


def gap_matching_prompts(candidate: CandidateProfile, job: JobSpec) -> tuple[str, str]:
    """System/user prompts comparing the candidate against the job requirements."""
    system = (
        "You are an interview strategist. Compare the candidate against the job "
        "requirements. Identify genuine strengths, gaps, and the specific topics an "
        "interviewer should PROBE to confirm or disprove fit (probe_targets). List "
        "which required skills are matched vs missing. Be concrete and evidence-led. "
        "Respond ONLY with the requested schema."
    )
    user = (
        "CANDIDATE SUMMARY:\n"
        f"- name: {candidate.name}\n"
        f"- headline: {candidate.headline}\n"
        f"- seniority: {candidate.seniority} ({candidate.years_experience}y)\n"
        f"- skills: {', '.join(candidate.skills)}\n"
        f"- achievements: {'; '.join(candidate.achievements)}\n\n"
        "JOB REQUIREMENTS:\n"
        f"- title: {job.title} at {job.company_name}\n"
        f"- seniority: {job.seniority}\n"
        f"- must_have: {', '.join(job.must_have)}\n"
        f"- nice_to_have: {', '.join(job.nice_to_have)}\n"
        f"- tech_stack: {', '.join(job.tech_stack)}\n"
        f"- responsibilities: {'; '.join(job.responsibilities)}"
    )
    return system, user


# --- question planner --------------------------------------------------------


def question_planner_prompts(
    candidate: CandidateProfile,
    job: JobSpec,
    company: CompanyIntel,
    gap: GapAnalysis,
    language_mode: LanguageMode,
) -> tuple[str, str]:
    """System/user prompts for the keystone interview-plan generation node."""
    primary = language_mode.primary
    primary_name = language_name(primary)
    also_localize = (
        ""
        if primary == "en"
        else (
            f" In addition to the required 'en' entry, also provide a '{primary}' "
            f"({primary_name}) translation for every question's text."
        )
    )
    mixed_note = (
        " The interview may code-switch between English and the primary language."
        if language_mode.mixed
        else ""
    )
    system = (
        "You are a senior interviewer designing a structured ~15 minute mock "
        "interview. Produce a question plan that:\n"
        "- Orders sections across intro, behavioral, technical, coding, and wrap.\n"
        "- Follows a RISING difficulty curve scored 1-5 (start easy, ramp up).\n"
        "- Gives every question a target_competency drawn from the gap analysis "
        "(prioritise probe_targets and missing_skills).\n"
        "- Attaches a scoring rubric of 1-3 RubricItems per question whose weights "
        "sum to about 1.0.\n"
        "- Seeds at least one followup probe per question.\n"
        "- Sets time_budget_min to about 15 and language_mode as given.\n"
        "- Tailors questions to the candidate's background and the company's "
        "interview process and values.\n"
        f"Write each question's text with an 'en' entry.{also_localize}{mixed_note} "
        "Respond ONLY with the requested schema."
    )
    user = (
        f"TARGET ROLE: {job.title} ({job.seniority}) at {company.name}\n"
        f"PRIMARY LANGUAGE: {primary} ({primary_name}); mixed={language_mode.mixed}\n\n"
        "CANDIDATE:\n"
        f"- {candidate.headline}; {candidate.years_experience}y; "
        f"skills: {', '.join(candidate.skills)}\n\n"
        "COMPANY INTERVIEW CONTEXT:\n"
        f"- values: {', '.join(company.values)}\n"
        f"- interview_process: {' -> '.join(company.interview_process)}\n"
        f"- tech_stack: {', '.join(company.tech_stack)}\n\n"
        "GAP ANALYSIS:\n"
        f"- strengths: {', '.join(gap.strengths)}\n"
        f"- gaps: {', '.join(gap.gaps)}\n"
        f"- probe_targets: {', '.join(gap.probe_targets)}\n"
        f"- missing_skills: {', '.join(gap.missing_skills)}\n\n"
        "Design the plan now."
    )
    return system, user


def _job_user_payload(req: PrepRequest) -> str:
    """Compact JD payload used by the jd_analysis node (company + raw text)."""
    return f"TARGET COMPANY: {req.company}\n\nJOB DESCRIPTION:\n{req.jd_text}"
