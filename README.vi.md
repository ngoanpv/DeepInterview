<div align="center">

<img src="assets/logo.svg" width="132" alt="DeepInterview" />

# DeepInterview: AI Phỏng Vấn Thử, Ưu Tiên Giọng Nói, Đa Ngôn Ngữ

### Luyện phỏng vấn bằng giọng nói. Rồi vượt qua buổi thật. · Ưu tiên tiếng Anh · Mã nguồn mở

[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-4338CA.svg)](LICENSE)
[![Build](https://img.shields.io/github/actions/workflow/status/ngoanpv/DeepInterview/ci.yml?branch=main&label=build)](https://github.com/ngoanpv/DeepInterview/actions)
[![Release](https://img.shields.io/github/v/release/ngoanpv/DeepInterview?include_prereleases&label=release&color=4338CA)](https://github.com/ngoanpv/DeepInterview/releases)
[![Stars](https://img.shields.io/github/stars/ngoanpv/DeepInterview?style=social)](https://github.com/ngoanpv/DeepInterview/stargazers)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-4338CA.svg)](apps/agent)
[![pnpm](https://img.shields.io/badge/pnpm-workspace-4338CA.svg)](pnpm-workspace.yaml)
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](#-cộng-đồng)

[🇺🇸 English](README.md) · **🇻🇳 Tiếng Việt**

[Tính năng](#-tính-năng) · [Khởi động nhanh](#-khởi-động-nhanh) · [Kiến trúc](#️-kiến-trúc) · [Lộ trình](#️-lộ-trình) · [Cộng đồng](#-cộng-đồng) · [Đóng góp](#-đóng-góp)

</div>

---

<!-- HERO: ảnh GIF 15–40 giây của một buổi phỏng vấn bằng giọng nói thật + bảng điểm. -->
<!-- Tệp này chưa được quay — xem assets/README.md (đây là hạng mục đầu tiên trong checklist ra mắt). -->
![DeepInterview demo](assets/demo.gif)

> **🚧 demo.gif chỉ là ảnh giữ chỗ.** Đoạn demo hero là tài sản quan trọng nhất cho buổi ra mắt và vẫn chưa được quay — xem [`assets/README.md`](assets/README.md).

> **Tải lên CV và một bản mô tả công việc. Trò chuyện với một người phỏng vấn AI. Nhận điểm — và được huấn luyện đúng những gì bạn còn thiếu.** Ưu tiên giọng nói, ưu tiên tiếng Anh, và đa ngôn ngữ ngay từ thiết kế.

DeepInterview khép kín vòng lặp **chuẩn bị ⇄ phỏng vấn ⇄ phản hồi**: phần suy luận nặng chạy *trước* buổi gọi (đọc CV + JD, nghiên cứu công ty, dựng kế hoạch câu hỏi thích ứng), một vòng lặp giọng nói thời gian thực gọn nhẹ điều khiển buổi phỏng vấn, sau đó các mô hình mạnh chấm điểm và đưa bạn vào một huấn luyện viên ôn tập cho những điểm yếu.

> **Tình trạng trung thực:** đây là một **bản dựng mở giai đoạn đầu**. Các hợp đồng dữ liệu (contracts), các pipeline chuẩn bị/trực tiếp/sau buổi, các màn hình web và CLI đã được hiện thực và **chạy ngoại tuyến với adapter giả lập** (không cần khóa API, các bài kiểm thử đều xanh). Giọng nói thời gian thực, nghiên cứu web và avatar video cần khóa nhà cung cấp, và `docker compose up` sẽ trở thành lệnh chạy toàn bộ stack thật khi phần DevOps (WP-12) hoàn tất. Chúng tôi ghi rõ những gì đã xong một cách trung thực trong [Lộ trình](#️-lộ-trình).

## 📰 Tin tức

> - **[2026.06]** 🧱 **Bản dựng đầu đã chạy.** Hợp đồng `InterviewContext` đa ngôn ngữ (TS ↔ Pydantic) round-trip thành công; các pipeline chuẩn bị/trực tiếp/sau buổi và toàn bộ màn hình web chạy **ngoại tuyến với adapter giả lập**. Giai đoạn trước ra mắt.
> - **[tiếp theo]** 🎙️ Buổi phỏng vấn giọng nói đầu tiên end-to-end trên nhà cung cấp thật (STT→LLM→TTS trên LiveKit) + ảnh GIF demo hero.
> - **[tiếp theo]** 🌐 Thêm gói ngôn ngữ và bản demo trực tuyến được host.

_(Phần changelog cố ý ở giai đoạn trước ra mắt và trung thực — không có tuyên bố "1.000 sao" hay tính năng đã ship cho đến khi điều đó là sự thật.)_

## 📦 Phiên bản phát hành

Chưa có bản phát hành được gắn tag — DeepInterview đang ở giai đoạn trước `v0.1`. Hãy theo dõi [Releases](https://github.com/ngoanpv/DeepInterview/releases) và phần Tin tức ở trên. Metadata trích dẫn nằm ở [`CITATION.cff`](CITATION.cff).

## ✨ Tính năng

- **🎙️ Phỏng vấn giọng nói thời gian thực** — chuỗi **STT → LLM → TTS** trên LiveKit (không phải speech-to-speech), nên bạn có bản ghi đầy đủ, kiểm soát từng thành phần, và chi phí dự đoán được. Ngắt lời (barge-in) và câu hỏi tiếp nối được dựng sẵn giữ cho buổi nói chuyện tự nhiên.
- **🌐 Ưu tiên tiếng Anh & đa ngôn ngữ** — mọi chuỗi hiển thị cho người dùng đều được i18n hóa (giao diện đã có EN + VI); phỏng vấn bằng giọng nói hỗ trợ 10+ ngôn ngữ (gồm **tiếng Việt, end-to-end**), ngôn ngữ là thiết lập theo từng phiên và pipeline giọng nói định tuyến STT/TTS theo ngôn ngữ. Cụ thể: **STT Deepgram nova-3** (mọi ngôn ngữ); **TTS Cartesia sonic** (en/es/zh/fr/de/ja/pt/hi/it/ko/nl/pl/ru/sv/tr), **ElevenLabs Flash v2.5 cho tiếng Việt** và các ngôn ngữ ngoài Cartesia, Gemini TTS làm phương án dự phòng khi không có khóa ElevenLabs; **LLM Gemini/OpenAI**. Khi không đặt khóa, mọi tầng rơi về **adapter giả lập** để chạy ngoại tuyến. Mỗi ngôn ngữ là một "gói" cắm-vào-là-chạy.
- **🧠 Chuẩn bị cá nhân hóa** — một pipeline LangGraph đọc CV + JD, nghiên cứu công ty mục tiêu, so sánh khoảng cách, và một **Bộ lập kế hoạch câu hỏi** tính trước kế hoạch, đường cong độ khó, rubric và các câu hỏi tiếp nối — để vòng lặp trực tiếp luôn nhanh. **Tài liệu CV tải lên (PDF/DOCX) được phân tích thành văn bản phía máy chủ bằng [Microsoft markitdown](https://github.com/microsoft/markitdown), với phương án dự phòng đa phương thức Gemini cho PDF scan/ảnh.**
- **📊 Phản hồi có chấm điểm** — một bộ đánh giá dựa trên rubric + huấn luyện viên ngôn ngữ ghi một `ScoreCard` theo từng năng lực với điểm mạnh, khoảng trống, câu trả lời mẫu, và các bước tiếp theo, ánh xạ thẳng về những câu hỏi bạn đã được hỏi.
- **📚 Huấn luyện viên ôn tập** *(đang phát triển)* — biến khoảng trống của bạn thành một vòng học LLM (lập kế hoạch → bài luyện → trò chuyện Socratic). Câu trả lời có dẫn nguồn + trích dẫn là **tùy chọn**: đặt `LIGHTRAG_URL` (hoặc nối một RAG được quản lý sau cùng adapter) để neo câu trả lời vào tài liệu bạn tải lên; mặc định, huấn luyện viên trả lời một cách trung thực mà không bịa ra trích dẫn.
- **🎭 Avatar tiết kiệm chi phí** — các vòng video idle/đang-nói dựng sẵn bằng **Veo 3.1**, chuyển cảnh chéo theo trạng thái agent. Các persona gốc anime / siêu anh hùng / nhà tuyển dụng (không dùng IP có bản quyền), nên chi phí lúc chạy **chỉ-CDN — không phí avatar theo phút**.
- **🔌 Không phụ thuộc nhà cung cấp & tự host được** — một lớp adapter gọn (LLM / tìm kiếm / embeddings, kèm một **adapter giả lập** cho phát triển ngoại tuyến). Mang khóa của riêng bạn (Soniox/Deepgram, Cartesia/ElevenLabs, Gemini/GPT, hoặc OSS faster-whisper / XTTS / Qwen3).
- **🔓 Mã nguồn mở (AGPLv3)** — tự host toàn bộ. Mọi mã trả phí/dành cho doanh nghiệp được cô lập trong [`ee/`](ee/README.md).

## 🚀 Khởi động nhanh

> **🔓 Không cần đăng nhập.** Bản tự host (OSS) chạy **ẩn danh** — thiết lập, buổi phỏng vấn trực tiếp và báo cáo đều hoạt động **không cần tài khoản, không cần đăng nhập** (báo cáo đọc trực tiếp từ agent API). Đăng nhập Supabase + thanh toán là tầng **chỉ-dành-cho-bản-host**; bạn không cần chúng để tự chạy vòng lặp.

**Yêu cầu:** Node **20+** (khuyến nghị 22 — xem [`.nvmrc`](.nvmrc)) · pnpm 11 · Python 3.11+ với [uv](https://docs.astral.sh/uv/) (cho agent) · Docker (cho toàn bộ stack).

### 1. Đường ngoại tuyến (đã kiểm chứng — không cần khóa API)

Đây là phần được kiểm thử trong CI hôm nay. Nó dựng các hợp đồng dữ liệu, chạy các bộ kiểm thử, và vận hành các pipeline chuẩn bị/trực tiếp/sau buổi với **adapter giả lập** — không cần khóa nhà cung cấp.

```bash
git clone https://github.com/ngoanpv/DeepInterview.git
cd deepinterview

pnpm install          # install the JS/TS workspace
pnpm build            # build packages/shared (contracts) + cli + web
pnpm test             # TS + Pydantic parity + pipeline tests (offline, mock adapters)

pnpm deepinterview init   # scaffold .env from .env.example (fill in keys later)
```

> `pnpm build` phải chạy trước `pnpm deepinterview init` — CLI được build vào `cli/dist/`.
> Với agent Python: `uv --directory apps/agent sync` rồi `uv --directory apps/agent run pytest`.

### 2. Đường toàn-stack (mục tiêu — `docker compose up`)

```bash
cp .env.example .env      # then fill in your provider keys
docker compose up         # web (:3000) + agent worker + lightrag (:9621)
```

> **Tình trạng:** tệp compose hợp lệ (`docker compose config`) và đã nối cả ba dịch vụ. Image thật, healthcheck, và trải nghiệm "mở http://localhost:3000 và trò chuyện" đang được hoàn thiện trong **DevOps (WP-12)**. Cho đến lúc đó, hãy ưu tiên đường ngoại tuyến ở trên khi phát triển.

<details><summary>Cấu hình nhà cung cấp & thêm gói ngôn ngữ</summary>

- **Khóa** chỉ nằm trong `.env` (không bao giờ commit). Xem [`.env.example`](.env.example) để biết danh sách đầy đủ (LiveKit, Supabase, R2, STT/TTS/LLM, Tavily/Exa, thanh toán, observability).
- **Lựa chọn nhà cung cấp** theo từng thành phần: đặt `STT_PROVIDER`, `TTS_PROVIDER`, `LLM_PROVIDER` và khóa tương ứng. Khi không đặt khóa, agent tự rơi về **adapter giả lập** nên mọi thứ vẫn chạy ngoại tuyến.
- **Ngôn ngữ** là các gói cắm-vào-là-chạy. Chuỗi giao diện nằm ở `apps/web/lib/i18n/messages/` (đã có EN + VI); kế hoạch câu hỏi mang `text_en` / `text_vi` và một `language_mode`.

Xem [CONTRIBUTING.md](CONTRIBUTING.md) để biết toàn bộ thiết lập phát triển và mẫu provider-adapter.

</details>

## 🏗️ Kiến trúc

Xương sống của hệ thống là sự phân tách **chuẩn bị / trực tiếp / sau buổi** (mô hình mạnh chạy bất đồng bộ trước và sau buổi gọi; một mô hình nhanh gọn duy nhất trên đường xử lý lượt trực tiếp). Cả ba giai đoạn cùng dùng một "bảng đen" `InterviewContext` chung — được ghi ở giai đoạn chuẩn bị, đọc+ghi thêm ở giai đoạn trực tiếp, đọc ở giai đoạn sau buổi.

```
┌──────────── PREP (async · parallel · STRONG models · web tools) ────────────┐
│  CV ─┐                                                                        │
│  JD ─┼─►  LangGraph StateGraph (Orchestrator)         [WP-6]                  │
│ comp ┘     ├─ fan-out ─► [CV Analysis] [JD Analysis] [Company Research·web]   │
│            └─ join ────► [Gap/Matching] ─► [Question Planner ★]               │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                     ▼
                 ┌──────── InterviewContext (shared blackboard) ───────┐
                 │ candidate · job · company · gap · QUESTION_PLAN      │  [WP-0]
                 │ persisted in Postgres; loaded into LiveKit userdata  │
                 └───────────────────────────┬─────────────────────────┘
                                             ▼
┌──────────── LIVE (realtime <800ms · ONE fast model · LiveKit) ──────────────┐
│  AgentSession[InterviewContext]                       [WP-5]                  │
│   STT ─► [Interviewer Agent] ──reads plan, asks, light follow-up──► TTS       │
│                 ├─► [Coding-round Agent]   (handoff, own model/voice)         │
│                 └─► [Behavioral/STAR Agent]                                   │
│   <AvatarStage> crossfades Veo idle/speaking loops by agent state  [WP-9]     │
│   Director runs in BACKGROUND — never blocks a turn                           │
└───────────────────────────────────┬──────────────────────────────────────────┘
                          transcript + answers appended
                                     ▼
┌──────────── POST (async · STRONG/reasoning models · no latency budget) ─────┐
│  [Evaluator/Scorer] ─► [Language Coach EN/VI] ─► [Report Generator]  [WP-7]   │
│         writes per-competency ScoreCard ─► report screen            [WP-3]    │
│  Prep Coach re-plan (weak competencies) ◄── closes the loop         [WP-4/8]  │
│  Skill Distiller proposes playbook/rubric deltas → review queue     [WP-10]   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Ranh giới mô-đun:** `apps/web` sở hữu UI/auth/upload/token và không biết gì về LLM/STT/TTS · `apps/agent` sở hữu vòng lặp giọng nói + các pipeline chuẩn bị/sau buổi + tiện ích render avatar · `services/lightrag` sở hữu cơ sở tri thức · `cli/` sở hữu thiết lập lần đầu · **`packages/shared` là hợp đồng đa ngôn ngữ** (TS là nguồn chân lý, được phản chiếu thành Pydantic). Xem [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) và bản đặc tả đầy đủ trong [`site/AI-Interviewer-Build-Handoff.md`](site/AI-Interviewer-Build-Handoff.md).

## 📸 Ảnh chụp màn hình

> Ảnh giữ chỗ — xem [`assets/README.md`](assets/README.md). Các màn hình đã tồn tại (`/setup`, `/interview/[id]`, `/report/[id]`); ảnh chụp hoàn chỉnh sẽ có cùng đoạn demo.

| Thiết lập | Phỏng vấn trực tiếp | Báo cáo |
|---|---|---|
| ![setup](assets/screenshot-setup.png) | ![interview](assets/screenshot-interview.png) | ![report](assets/screenshot-report.png) |

## 🗺️ Lộ trình

Bản dựng được tổ chức thành **13 gói công việc (WP-0…WP-13)** trải qua các giai đoạn **P0–P6**. Các giai đoạn P0–P3 đã hiện thực và được kiểm chứng ngoại tuyến với adapter giả lập; P4–P6 đã được dựng khung.

| Giai đoạn | Gói công việc | Cung cấp những gì | Tình trạng |
|---|---|---|---|
| **P0** | WP-0 | Monorepo + hợp đồng TS↔Pydantic + khung CLI + `docker-compose` | ✅ Đã dựng · kiểm chứng ngoại tuyến |
| **P1** | WP-6, WP-5, WP-1 | Pipeline chuẩn bị · người phỏng vấn giọng nói trực tiếp · UI thiết lập/onboarding | ✅ Đã dựng · kiểm chứng ngoại tuyến |
| **P2** | WP-7, WP-3, WP-9 | Pipeline chấm điểm · màn hình báo cáo · hệ thống avatar Veo | ✅ Đã dựng · kiểm chứng ngoại tuyến |
| **P3** | WP-8, WP-4 | Dịch vụ tri thức (LightRAG) · UI Huấn luyện viên ôn tập (vòng lặp) | ✅ Đã dựng · kiểm chứng ngoại tuyến |
| **P4** | WP-13 | Tài sản ra mắt OSS (README này, tài liệu, good-first-issues) | 🟡 Đang làm |
| **P5** | WP-11, WP-10 | Thanh toán + giới hạn theo gói · thư viện kỹ năng + bộ chưng cất | 🟡 Đã dựng khung |
| **P6** | WP-12, `ee/` | DevOps/triển khai/observability · doanh nghiệp (SSO/RBAC/audit) | 🟡 Đã dựng khung |

> "Kiểm chứng ngoại tuyến" nghĩa là pipeline chạy end-to-end với adapter giả lập và các bài kiểm thử đều xanh — **giọng nói thời gian thực trên nhà cung cấp thật và một bản demo được host là cột mốc kế tiếp**, không phải một tuyên bố hiện tại.

**Thấy hữu ích? [Tặng chúng tôi một ⭐](https://github.com/ngoanpv/DeepInterview)** — tốc độ tăng sao là thứ giúp một dự án được khám phá, và nó thật sự có ích.

## 🌐 Cộng đồng

- 💬 **Discord** — tham gia kênh chat build-in-public _(link mời TBD — mở khi ra mắt)_.
- 🗣️ **[GitHub Discussions](https://github.com/ngoanpv/DeepInterview/discussions)** — câu hỏi, ý tưởng, yêu cầu gói ngôn ngữ.
- 🐛 **[Issues](https://github.com/ngoanpv/DeepInterview/issues)** — lỗi & tính năng (có sẵn template).

Xây dựng công khai. Chúng tôi trả lời các issue — bỏ rơi người đóng góp là nguyên nhân số 1 khiến dự án OSS chết, và chúng tôi không có ý định đó.

## 🤝 Đóng góp

Chúng tôi rất mong bạn giúp sức — đặc biệt là **gói ngôn ngữ**, **adapter nhà cung cấp**, và **khả năng tiếp cận**. Bắt đầu với:

- 📖 [CONTRIBUTING.md](CONTRIBUTING.md) — thiết lập phát triển, bản đồ monorepo, mô hình gói công việc, mẫu provider-adapter (mock-first), và cách chạy **ngoại tuyến không cần khóa**.
- 🌱 [Good first issues](docs/GOOD_FIRST_ISSUES.md) — các tác vụ cụ thể, có phạm vi rõ, rút ra từ các khoảng trống thật.
- 📜 [Quy tắc ứng xử](CODE_OF_CONDUCT.md) · 🔒 [Chính sách bảo mật](SECURITY.md).

<!-- Khảm người đóng góp — sẽ điền sau khi repo công khai (contrib.rocks đọc danh sách người đóng góp công khai). -->
[![Contributors](https://contrib.rocks/image?repo=ngoanpv/DeepInterview)](https://github.com/ngoanpv/DeepInterview/graphs/contributors)

> _Khảm ở trên hiển thị khi repo đã công khai và có người đóng góp._

## 📖 Trích dẫn

Nếu DeepInterview giúp ích cho công việc của bạn, hãy trích dẫn. Metadata đầy đủ nằm trong [`CITATION.cff`](CITATION.cff).

```bibtex
@software{deepinterview2026,
  title  = {DeepInterview: Voice-First, Multilingual AI Mock Interviewer},
  author = {The DeepInterview contributors},
  year   = {2026},
  license = {AGPL-3.0-only},
  url    = {https://github.com/ngoanpv/DeepInterview}
}
```

---

<div align="center">

**Giấy phép:** [AGPL-3.0-only](LICENSE) cho phần lõi · điều khoản thương mại cho [`ee/`](ee/README.md). · Xây dựng công khai 🌍

[⬆ về đầu trang](#deepinterview-ai-phỏng-vấn-thử-ưu-tiên-giọng-nói-đa-ngôn-ngữ)

</div>
