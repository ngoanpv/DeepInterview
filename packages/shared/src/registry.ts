import type { ZodType } from "zod";
import * as A from "./answer";
import * as Api from "./api";
import * as C from "./candidate";
import * as Co from "./company";
import * as G from "./gap";
import * as I from "./interview-context";
import * as J from "./job";
import * as P from "./primitives";
import * as Q from "./question";
import * as R from "./room";
import * as S from "./score";
import * as Coach from "./coach";

export const SCHEMAS: Record<string, ZodType> = {
  Project: C.ProjectSchema,
  Education: C.EducationSchema,
  CandidateProfile: C.CandidateProfileSchema,
  JobSpec: J.JobSpecSchema,
  Citation: Co.CitationSchema,
  CompanyIntel: Co.CompanyIntelSchema,
  GapAnalysis: G.GapAnalysisSchema,
  RubricItem: Q.RubricItemSchema,
  PlannedQuestion: Q.PlannedQuestionSchema,
  LanguageMode: P.LanguageModeSchema,
  QuestionPlan: Q.QuestionPlanSchema,
  AnswerRecord: A.AnswerRecordSchema,
  CompetencyScore: S.CompetencyScoreSchema,
  LanguageReport: S.LanguageReportSchema,
  ModelAnswer: S.ModelAnswerSchema,
  ScoreCard: S.ScoreCardSchema,
  StudyModule: Coach.StudyModuleSchema,
  StudyPlan: Coach.StudyPlanSchema,
  CoachChatRequest: Coach.CoachChatRequestSchema,
  CoachReply: Coach.CoachReplySchema,
  InterviewContext: I.InterviewContextSchema,
  TokenRequest: R.TokenRequestSchema,
  TokenResponse: R.TokenResponseSchema,
  RoomMetadata: R.RoomMetadataSchema,
  PrepRequest: Api.PrepRequestSchema,
  PrepResponse: Api.PrepResponseSchema,
  ScoreRequest: Api.ScoreRequestSchema,
  ScoreResponse: Api.ScoreResponseSchema,
  KbIngestRequest: Api.KbIngestRequestSchema,
  KbIngestResponse: Api.KbIngestResponseSchema,
  KbQueryRequest: Api.KbQueryRequestSchema,
  KbQueryResponse: Api.KbQueryResponseSchema,
};
