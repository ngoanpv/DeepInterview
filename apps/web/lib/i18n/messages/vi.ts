import type { Messages } from "./en";

/**
 * `en` is declared `as const`, so `Messages` carries literal value types. A
 * translated pack obviously can't match those literals, so we widen every
 * string leaf to `string` while keeping the exact key structure — any missing
 * or extra key is still a compile error (true parity), only the *values* widen.
 *
 * Exported so the registry (`lib/i18n/index.ts`) can type the resolved
 * dictionary structurally instead of asserting packs back to literals.
 */
export type Localized<T> = {
  [K in keyof T]: T[K] extends string ? string : Localized<T[K]>;
};

/**
 * Vietnamese message dictionary. Mirrors the `en` key shape exactly. English
 * stays the default; the pack is wired into the registry in
 * `lib/i18n/index.ts`.
 */
export const vi: Localized<Messages> = {
  common: {
    appName: "DeepInterview",
    continue: "Tiếp tục",
    back: "Quay lại",
    cancel: "Hủy",
    loading: "Đang tải…",
    error: "Đã có lỗi xảy ra.",
  },
  nav: {
    setup: "Thiết lập",
    interview: "Phỏng vấn",
    report: "Báo cáo",
    coach: "Huấn luyện",
  },
  landing: {
    eyebrow: "Phỏng vấn thử bằng giọng nói với AI",
    titleLead: "Luyện tập buổi phỏng vấn",
    titleAccent: "giúp bạn nhận được lời mời",
    subtitle:
      "DeepInterview đọc CV và mô tả công việc của bạn, tìm hiểu về công ty, sau đó chạy một buổi phỏng vấn bằng giọng nói linh hoạt — và chỉ ra chính xác điều cần cải thiện.",
    ctaStart: "Bắt đầu phỏng vấn thử",
    ctaLogin: "Đăng nhập",
  },
  auth: {
    loginTitle: "Chào mừng trở lại",
    loginSubtitle: "Đăng nhập để thiết lập buổi phỏng vấn tiếp theo.",
    signupTitle: "Tạo tài khoản",
    signupSubtitle: "Bắt đầu luyện tập chỉ trong vài phút.",
    emailLabel: "Email",
    passwordLabel: "Mật khẩu",
    signIn: "Đăng nhập",
    signUp: "Tạo tài khoản",
    noAccount: "Chưa có tài khoản?",
    haveAccount: "Đã có tài khoản?",
    toSignup: "Đăng ký",
    toLogin: "Đăng nhập",
    checkEmail: "Kiểm tra email để xác nhận tài khoản, sau đó đăng nhập.",
    devNotice: "Chưa cấu hình đăng nhập — tiếp tục ở chế độ dev.",
    devContinue: "Tiếp tục đến thiết lập",
  },
  setup: {
    title: "Thiết lập buổi phỏng vấn",
    subtitle: "Mang theo CV và công việc bạn đang nhắm tới.",
    cvLabel: "CV của bạn",
    cvHint: "PDF hoặc DOCX. Chúng tôi đọc để điều chỉnh câu hỏi.",
    cvDrop: "Kéo thả PDF hoặc DOCX vào đây, hoặc nhấn để chọn.",
    cvPasteLabel: "…hoặc dán nội dung CV",
    cvPasteHint: "Không cần tải lên — hoạt động cả khi ngoại tuyến.",
    jdLabel: "Mô tả công việc",
    jdHint: "Dán vị trí bạn đang phỏng vấn.",
    companyLabel: "Công ty",
    companyHint: "Chúng tôi tìm hiểu công ty để buổi phỏng vấn sát thực tế.",
    languageLabel: "Ngôn ngữ phỏng vấn",
    languageMixed: "Cho phép xen lẫn tiếng Anh",
    personaLabel: "Người phỏng vấn",
    personaHint: "Chọn avatar sẽ điều hành buổi phỏng vấn.",
    deviceLabel: "Kiểm tra micro",
    start: "Bắt đầu phỏng vấn",
    researching: "Đang tìm hiểu {company}…",
    stepCv: "Đang đọc CV của bạn",
    stepCompany: "Đang tìm hiểu công ty",
    stepPlan: "Đang lên kế hoạch câu hỏi",
    needCv: "Thêm CV của bạn (tải tệp lên hoặc dán nội dung).",
    needJd: "Dán mô tả công việc.",
    needCompany: "Nhập tên công ty mục tiêu.",
    micWorking: "Micro hoạt động tốt",
    micRequesting: "Đang yêu cầu quyền truy cập…",
    micDenied: "Bị từ chối — kiểm tra quyền micro của trình duyệt",
    micUnsupported: "Không thể dùng micro trên trang này",
    micIdle: "Chưa kiểm tra",
    micTest: "Kiểm tra micro",
    micStop: "Tắt micro",
  },
  interview: {
    title: "Đang phỏng vấn",
    connecting: "Đang kết nối với người phỏng vấn…",
    listening: "Đang nghe",
    speaking: "Đang nói",
    end: "Kết thúc phỏng vấn",
    endButton: "Kết thúc",
    ending: "Đang kết thúc…",
    confirmEnd: "Nhấn lại để kết thúc",
    recording: "Đang ghi âm",
    ready: "Sẵn sàng phỏng vấn",
    readySubtitle: "Buổi phỏng vấn cá nhân hóa đã chuẩn bị xong và đang chờ.",
    join: "Vào phỏng vấn",
    connected: "Đã kết nối — giao diện phỏng vấn trực tiếp sẽ có ở WP-2.",
    sessionId: "Phiên",
    transcript: "Bản ghi",
    transcriptEmpty: "Cuộc trò chuyện sẽ hiện ở đây khi bạn nói.",
    roleInterviewer: "Người phỏng vấn",
    roleYou: "Bạn",
    live: "Trực tiếp",
    controls: "Điều khiển phỏng vấn",
    mute: "Tắt micro",
    unmute: "Bật micro",
    enableAudio: "Bật âm thanh phỏng vấn",
    elapsed: "Thời gian phỏng vấn đã qua",
    micUnavailable: "Không dùng được micro",
    micTypeFallback: "Trong lúc đó, bạn có thể gõ câu trả lời bên dưới.",
    micBlocked:
      "Quyền micro đang bị chặn. Nhấn biểu tượng ổ khóa hoặc micro trên thanh địa chỉ, cho phép micro, rồi bật lại.",
    micNotFound:
      "Không tìm thấy micro. Hãy kết nối micro (hoặc chọn đầu vào khác trong cài đặt), rồi bật lại.",
    micInUse:
      "Micro đang được ứng dụng khác dùng. Hãy tắt ứng dụng đó, rồi bật lại.",
    micUnknown:
      "Không thể truy cập micro. Kiểm tra quyền micro của trình duyệt, rồi bật lại.",
    agentMissing: "Người phỏng vấn chưa tham gia",
    agentMissingBody:
      "Bạn đã kết nối vào phòng, nhưng voice worker chưa tới. Nó chạy như một tiến trình riêng — hãy khởi động bằng `docker compose --profile live up` và kiểm tra LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET cùng các key STT/TTS/LLM trong `.env` gốc. Trong lúc đó bạn có thể gõ câu trả lời bên dưới.",
    reconnecting: "Kết nối không ổn định — đang kết nối lại…",
    previewBody:
      "Chế độ xem trước — kết nối LiveKit (đặt LIVEKIT_* trong .env) để phỏng vấn thật.",
    endedTitle: "Buổi phỏng vấn đã kết thúc",
    endedBody: "Phiên này không còn tham gia được nữa.",
    viewReport: "Xem báo cáo",
    connLost: "Mất kết nối",
    couldntReach:
      "Không thể vào phòng phỏng vấn. Kiểm tra mạng rồi tham gia lại.",
    connDropped:
      "Kết nối tới buổi phỏng vấn bị ngắt. Hãy tham gia lại để tiếp tục.",
    rejoin: "Tham gia lại",
    connectingShort: "Đang kết nối…",
    typeAnswerLabel: "Gõ câu trả lời thay vì nói",
    typeAnswer: "Gõ câu trả lời",
    typePlaceholder: "Gõ câu trả lời…",
    typePlaceholderOffline: "Gõ câu trả lời khi đã trực tiếp",
    sendAnswer: "Gửi câu trả lời",
  },
  report: {
    title: "Báo cáo phỏng vấn của bạn",
    subtitle: "Bạn mạnh ở đâu, và cần cải thiện gì tiếp theo.",
    overall: "Tổng thể",
    strengths: "Điểm mạnh",
    improvements: "Cần cải thiện",
    practiceWeak: "Luyện các điểm yếu",
  },
};
