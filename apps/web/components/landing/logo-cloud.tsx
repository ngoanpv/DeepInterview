import { Container } from "@/components/ui/container";

const COMPANIES = [
  "Google",
  "Amazon",
  "Stripe",
  "Grab",
  "Atlassian",
  "Datadog",
];

export function LogoCloud() {
  return (
    <div className="border-b border-line py-[34px]">
      <Container>
        <p className="mb-[18px] text-center font-mono text-[12.5px] uppercase tracking-[0.06em] text-faint">
          Prepare for interviews at companies like
        </p>
        <div className="flex flex-wrap items-center justify-center gap-x-[46px] gap-y-4">
          {COMPANIES.map((name) => (
            <span
              key={name}
              className="text-lg font-semibold tracking-[-0.01em] text-[#B9B6AE]"
            >
              {name}
            </span>
          ))}
        </div>
      </Container>
    </div>
  );
}
