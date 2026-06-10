import { ImageResponse } from "next/og";

export const alt = "DeepInterview — Practice the interview out loud";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        backgroundColor: "#FBFAF8",
        padding: "80px",
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      <div
        style={{
          display: "flex",
          fontSize: 26,
          letterSpacing: "0.16em",
          textTransform: "uppercase",
          color: "#4338CA",
          fontFamily: "monospace",
          marginBottom: 28,
        }}
      >
        OPEN-SOURCE AI INTERVIEWER
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 104,
          lineHeight: 1.05,
          color: "#17171A",
          letterSpacing: "-0.02em",
        }}
      >
        DeepInterview
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 36,
          color: "#3A3A40",
          marginTop: 28,
          maxWidth: 900,
        }}
      >
        Practice the interview out loud, then pass the real one.
      </div>
    </div>,
    { ...size },
  );
}
