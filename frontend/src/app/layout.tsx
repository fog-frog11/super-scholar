import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Super Scholar — Find where your research belongs",
  description: "Evidence-grounded publication venue discovery for computer science research."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
