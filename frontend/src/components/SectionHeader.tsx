import type { ReactNode } from "react";

interface SectionHeaderProps {
  title: string;
  children?: ReactNode;
}

export default function SectionHeader({ title, children }: SectionHeaderProps) {
  return (
    <div className="flex justify-between items-center mb-6">
      <h2 className="text-3xl font-bold text-text-primary">{title}</h2>
      {children && <div className="flex gap-4">{children}</div>}
    </div>
  );
}
