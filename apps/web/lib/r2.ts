import "server-only";
import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { isR2Configured, serverEnv } from "@/lib/env";

export interface PresignedUpload {
  /** Pre-signed PUT URL — upload the file bytes directly to this. */
  uploadUrl: string;
  /** Public URL where the object will be readable after upload. */
  publicUrl: string;
}

let cachedClient: S3Client | null = null;

function r2Client(): S3Client {
  if (cachedClient) return cachedClient;
  cachedClient = new S3Client({
    region: "auto",
    endpoint: `https://${serverEnv.r2AccountId}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: serverEnv.r2AccessKeyId as string,
      secretAccessKey: serverEnv.r2SecretAccessKey as string,
    },
  });
  return cachedClient;
}

/**
 * Pre-sign a PUT upload to Cloudflare R2 for `key`.
 *
 * Throws a clear error when R2 is not configured — call only behind an
 * `isR2Configured()` check (the upload route does this). Never throws at import.
 */
export async function presignUpload(
  key: string,
  contentType: string,
): Promise<PresignedUpload> {
  if (!isR2Configured()) {
    throw new Error(
      "R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET.",
    );
  }

  const command = new PutObjectCommand({
    Bucket: serverEnv.r2Bucket,
    Key: key,
    ContentType: contentType,
  });

  const uploadUrl = await getSignedUrl(r2Client(), command, { expiresIn: 600 });

  const base =
    serverEnv.r2PublicUrl?.replace(/\/$/, "") ||
    `https://${serverEnv.r2AccountId}.r2.cloudflarestorage.com/${serverEnv.r2Bucket}`;
  const publicUrl = `${base}/${key}`;

  return { uploadUrl, publicUrl };
}
