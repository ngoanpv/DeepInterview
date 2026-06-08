import type { Messages } from "./en";

/**
 * `en` is declared `as const`, so `Messages` carries literal value types. A
 * translated pack obviously can't match those literals, so we widen every
 * string leaf to `string` while keeping the exact key structure — any missing
 * or extra key is still a compile error (true parity), only the *values* widen.
 */
type Localized<T> = {
  [K in keyof T]: T[K] extends string ? string : Localized<T[K]>;
};

/**
 * Vietnamese message dictionary. Mirrors the `en` key shape exactly. English
 * stays the default; activate this pack at the documented extension point in
 * `lib/i18n/index.ts` (currently `vi` falls back to `en` there).
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
  },
  interview: {
    title: "Đang phỏng vấn",
    connecting: "Đang kết nối với người phỏng vấn…",
    listening: "Đang nghe",
    speaking: "Đang nói",
    end: "Kết thúc phỏng vấn",
    recording: "Đang ghi âm",
    ready: "Sẵn sàng phỏng vấn",
    readySubtitle: "Buổi phỏng vấn cá nhân hóa đã chuẩn bị xong và đang chờ.",
    join: "Vào phỏng vấn",
    connected: "Đã kết nối — giao diện phỏng vấn trực tiếp sẽ có ở WP-2.",
    sessionId: "Phiên",
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
