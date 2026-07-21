import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const badgeVariants = cva("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2", {
  variants: { variant: { ww2: "border-amber-200 bg-amber-50 text-amber-800", usa: "border-blue-200 bg-blue-50 text-blue-800", science: "border-emerald-200 bg-emerald-50 text-emerald-800", art: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-800", popCulture: "border-rose-200 bg-rose-50 text-rose-800" } },
  defaultVariants: { variant: "science" },
})

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}
function Badge({ className, variant, ...props }: BadgeProps) { return <div className={cn(badgeVariants({ variant }), className)} {...props} /> }
export { Badge, badgeVariants }
