import { motion, useReducedMotion } from "framer-motion";

interface SettlementHeroProps {
  collapsed: boolean;
}

const HERO_CARDS = [
  {
    id: "extract",
    label: "Extraction",
    title: "Trace every proposal",
    body: "Schema-sealed intake with live model telemetry and bounded fields.",
    metric: "Live schema lock"
  },
  {
    id: "gate",
    label: "Clearance",
    title: "Gate deterministically",
    body: "A visible chain of hard checks before anything touches execution.",
    metric: "5 visible gates"
  },
  {
    id: "proof",
    label: "Audit",
    title: "Seal every outcome",
    body: "Tokens, proof packets, and ledger verification in one review surface.",
    metric: "Ledger-backed proof"
  }
] as const;

function GuillocheTexture() {
  return (
    <svg
      className="settlement-hero__guilloche"
      viewBox="0 0 760 280"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {Array.from({ length: 12 }, (_, index) => {
        const rotation = index * 15;
        const radiusX = 180 + index * 14;
        const radiusY = 68 + index * 6;
        return (
          <ellipse
            key={`ellipse-${rotation}`}
            cx="380"
            cy="140"
            rx={radiusX}
            ry={radiusY}
            transform={`rotate(${rotation} 380 140)`}
            stroke="currentColor"
            strokeOpacity={index % 3 === 0 ? 0.22 : 0.12}
            strokeWidth="1"
          />
        );
      })}
      {Array.from({ length: 8 }, (_, index) => (
        <circle
          key={`circle-${index}`}
          cx="380"
          cy="140"
          r={38 + index * 22}
          stroke="currentColor"
          strokeOpacity={index === 0 ? 0.2 : 0.1}
          strokeWidth="1"
        />
      ))}
    </svg>
  );
}

function SettlementHero({ collapsed }: SettlementHeroProps) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <motion.section
      className={`settlement-hero ${collapsed ? "settlement-hero--collapsed" : ""}`}
      data-testid="settlement-hero"
      data-collapsed={collapsed ? "true" : "false"}
      initial={false}
      animate={{
        height: collapsed ? 76 : 412,
        paddingTop: collapsed ? 12 : 28,
        paddingBottom: collapsed ? 12 : 32
      }}
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3, ease: "easeInOut" }}
    >
      <div className="settlement-hero__texture">
        <GuillocheTexture />
      </div>
      <motion.div
        className="settlement-hero__content"
        initial={false}
        animate={{
          gap: collapsed ? 8 : 16
        }}
        transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3, ease: "easeInOut" }}
      >
        <div className="settlement-hero__brandline">
          <span className="settlement-hero__eyebrow">Trust-Orchestrated Settlement &amp; Control OS</span>
          <h1 className="settlement-hero__wordmark">TOSCO</h1>
        </div>
        <motion.div
          className="settlement-hero__copy"
          initial={false}
          animate={{
            opacity: collapsed ? 0 : 1,
            y: collapsed ? -8 : 0,
            maxHeight: collapsed ? 0 : 80
          }}
          transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.28, ease: "easeOut" }}
        >
          <p className="settlement-hero__tagline">
            Agents propose. TOSCO clears. Execution obeys. Audit proves.
          </p>
        </motion.div>
        <motion.div
          className="settlement-hero__cards"
          initial={false}
          animate={{
            opacity: collapsed ? 0 : 1,
            y: collapsed ? -12 : 0,
            maxHeight: collapsed ? 0 : 260
          }}
          transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3, ease: "easeOut" }}
        >
          {HERO_CARDS.map((card, index) => (
            <motion.article
              key={card.id}
              className={`settlement-hero__card settlement-hero__card--${card.id}`}
              initial={false}
              animate={{
                opacity: collapsed ? 0 : 1,
                y: collapsed ? -10 : 0
              }}
              transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.24, delay: collapsed ? 0 : index * 0.04 }}
            >
              <div className="settlement-hero__card-visual" aria-hidden="true">
                <span className="settlement-hero__card-glow" />
                <span className="settlement-hero__card-core" />
                <span className="settlement-hero__card-ring settlement-hero__card-ring--a" />
                <span className="settlement-hero__card-ring settlement-hero__card-ring--b" />
                <span className="settlement-hero__card-arc" />
                <span className="settlement-hero__card-metric">{card.metric}</span>
              </div>
              <div className="settlement-hero__card-copy">
                <span className="settlement-hero__card-label">{card.label}</span>
                <strong className="settlement-hero__card-title">{card.title}</strong>
                <p className="settlement-hero__card-body">{card.body}</p>
              </div>
            </motion.article>
          ))}
        </motion.div>
        <motion.div
          className="settlement-hero__rail"
          initial={false}
          animate={{
            opacity: collapsed ? 0.72 : 1,
            scaleX: collapsed ? 0.96 : 1
          }}
          transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3, ease: "easeInOut" }}
        >
          <span className="settlement-hero__rail-line settlement-hero__rail-line--left" />
          <span className="settlement-hero__rail-chip">Night settlement surface</span>
          <span className="settlement-hero__rail-line settlement-hero__rail-line--right" />
        </motion.div>
      </motion.div>
    </motion.section>
  );
}

export default SettlementHero;
