import {
  ArrowRight,
  ShieldCheck,
} from "lucide-react"

interface SectionPageProps {
  eyebrow: string
  title: string
  description: string
  features: string[]
}

export function SectionPage({
  eyebrow,
  title,
  description,
  features,
}: SectionPageProps) {
  return (
    <section className="page">
      <header className="page-heading">
        <div>
          <p className="page-heading__eyebrow">
            {eyebrow}
          </p>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </header>

      <div className="section-grid">
        {features.map((feature, index) => (
          <article
            className="section-card"
            key={feature}
          >
            <span className="section-card__number">
              {String(index + 1).padStart(2, "0")}
            </span>

            <ShieldCheck size={22} />

            <h3>{feature}</h3>

            <p>
              This control is part of GreyGuard’s
              protected multi-agent security plane.
            </p>

            <button type="button">
              Inspect control
              <ArrowRight size={16} />
            </button>
          </article>
        ))}
      </div>
    </section>
  )
}
