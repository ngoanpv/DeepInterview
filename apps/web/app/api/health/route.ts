import {
  InterviewContextSchema,
  SAMPLE_INTERVIEW_CONTEXT,
  LANGUAGES,
} from "@deepinterview/shared";

export function GET() {
  const parsed = InterviewContextSchema.parse(SAMPLE_INTERVIEW_CONTEXT);
  return Response.json({
    ok: true,
    wp: "WP-0",
    session_id: parsed.session_id,
    questions: parsed.plan.questions.length,
    languages_supported: LANGUAGES.length,
  });
}
