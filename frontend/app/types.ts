export type Source = {
	url: string;
	title: string;
};

export type Message = {
	id: string;
	createdAt?: Date;
	content: string;
	type: "system" | "human" | "ai" | "function";
	sources?: Source[];
	name?: string;
	function_call?: { name: string };
};

export type Feedback = {
	feedback_id: string;
	score: number;
	comment?: string;
};

export type ModelOptions = "anthropic_claude_3_5_sonnet" | "anthropic_claude_3_7_sonnet" | "anthropic_claude_4_sonnet" | 'anthropic_claude_4_opus'
	| "openai/gpt-4o-mini"
	| "anthropic/claude-3-5-haiku-20241022"
	| "groq/llama3-70b-8192"
	| "google_genai/gemini-pro";
