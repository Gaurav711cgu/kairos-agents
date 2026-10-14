import type { HTMLAttributes, ReactNode } from "react";

interface AntigravityCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  className?: string;
  depth?: number;
}

export function AntigravityCard({
  children,
  className = "",
  ...props
}: AntigravityCardProps) {
  const attributes = { ...props };
  delete attributes.depth;
  return (
    <div className={`antigravity-card-root ${className}`} {...attributes}>
      {children}
    </div>
  );
}
