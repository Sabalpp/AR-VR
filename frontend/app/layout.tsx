import "./globals.css";
export const metadata = {
  title: "Reach · A little further, together",
  description: "Connected physical therapy for home and clinic.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
