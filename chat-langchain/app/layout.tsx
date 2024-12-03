import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "Eddie's Assitant",
	description: "Chatbot for Assistant",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className="h-full">
			{process.env.ENV_NAME == 'prod' ? <head>
				<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests" />
			</head> : ""}

			<body className={`${inter.className} h-full`}>
				<div
					className="flex flex-col h-full md:p-8 bg-[#131318]"
				>
					{children}
				</div>
			</body>
		</html>
	);
}
