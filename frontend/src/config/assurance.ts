export const frontendAssuranceControls = [
  "authentication",
  "authorization",
  "restricted navigation",
  "audit integrity",
  "execution isolation",
  "incident workflows",
] as const

export const hasAssuranceControl = (control: string) =>
  frontendAssuranceControls.includes(control as typeof frontendAssuranceControls[number])
