import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { withBasePath } from "@/lib/base-path";

const LOGO_SRC = withBasePath("/logo.png");
const LOGO_DIMENSION = 600;

interface ControlBoxLogoProps {
  className?: string;
  size?: number;
  priority?: boolean;
  href?: string;
}

export function ControlBoxLogo({
  className,
  size = 40,
  priority = false,
  href,
}: ControlBoxLogoProps) {
  const image = (
    <Image
      src={LOGO_SRC}
      alt="ControlBox — Manage. Deploy. Scale."
      width={LOGO_DIMENSION}
      height={LOGO_DIMENSION}
      className={cn("object-contain", className)}
      style={{ width: size, height: size }}
      priority={priority}
    />
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex shrink-0" aria-label="ControlBox home">
        {image}
      </Link>
    );
  }

  return image;
}
