import { z } from "zod";

export const TokenRequestSchema = z.object({
  session_id: z.string(),
  identity: z.string(),
  name: z.string().nullable().default(null),
});
export type TokenRequest = z.infer<typeof TokenRequestSchema>;

export const TokenResponseSchema = z.object({
  token: z.string(),
  url: z.string(),
  room: z.string(),
});
export type TokenResponse = z.infer<typeof TokenResponseSchema>;

export const RoomMetadataSchema = z.object({
  session_id: z.string(),
});
export type RoomMetadata = z.infer<typeof RoomMetadataSchema>;
