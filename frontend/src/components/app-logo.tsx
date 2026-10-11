import Image from "next/image";

export function AppLogo({ className, width = 44, height = 32 }: {
  className?: string;
  width?: number;
  height?: number;
}) {
  return <Image src="/aeroroute-logo.png" alt="" aria-hidden="true" width={width} height={height}
    className={className} priority />;
}
