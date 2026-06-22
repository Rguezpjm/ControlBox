import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";
import logoImage from "../../../public/logo.png";

interface ControlBoxLogoProps {
  className?: string;
  size?: number;
  priority?: boolean;
  href?: string;
  /** Muestra solo la parte superior (icono) en tamaños pequeños */
  markOnly?: boolean;
}

export function ControlBoxLogo({
  className,
  size = 40,
  priority = false,
  href,
  markOnly = true,
}: ControlBoxLogoProps) {
  const image = (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md bg-white p-0.5 shadow-sm ring-1 ring-black/5 dark:bg-white",
        markOnly && size <= 48 && "aspect-square"
      )}
      style={markOnly && size <= 48 ? { width: size, height: size } : undefined}
    >
      <Image
        src={logoImage}
        alt="ControlBox — Manage. Deploy. Scale."
        width={600}
        height={600}
        className={cn(
          markOnly && size <= 48 ? "h-auto w-full object-cover object-top" : "object-contain",
          className
        )}
        style={
          markOnly && size <= 48
            ? undefined
            : { width: size, height: size }
        }
        priority={priority}
      />
    </span>
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
