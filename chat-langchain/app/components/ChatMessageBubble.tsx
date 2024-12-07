import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { emojisplosion } from "emojisplosion";
import { useState, useRef } from "react";
import * as DOMPurify from "dompurify";
import { SourceBubble, Source } from "./SourceBubble";
import {
	VStack,
	Flex,
	Heading,
	HStack,
	Box,
	Button,
	Divider,
	Spacer,
	Image,
	Grid,
	styled,
	chakra
} from "@chakra-ui/react";
import { sendFeedback } from "../utils/sendFeedback";
import { apiBaseUrl } from "../utils/constants";
import { InlineCitation } from "./InlineCitation";

export type Message = {
	id: string;
	createdAt?: Date;
	content: string;
	role: "system" | "user" | "assistant" | "function";
	runId?: string;
	sources?: Source[];
	name?: string;
	function_call?: { name: string };
	images?: string[]; // 添加图片数组字段
};
export type Feedback = {
	feedback_id: string;
	run_id: string;
	key: string;
	score: number;
	comment?: string;
};

const filterSources = (sources: Source[]) => {
	const filtered: Source[] = [];
	const urlMap = new Map<string, number>();
	const indexMap = new Map<number, number>();
	sources.forEach((source, i) => {
		const { url } = source;
		const index = urlMap.get(url);
		if (index === undefined) {
			urlMap.set(url, i);
			indexMap.set(i, filtered.length);
			filtered.push(source);
		} else {
			const resolvedIndex = indexMap.get(index);
			if (resolvedIndex !== undefined) {
				indexMap.set(i, resolvedIndex);
			}
		}
	});
	return { filtered, indexMap };
};

const createAnswerElements = (
	content: string,
	filteredSources: Source[],
	sourceIndexMap: Map<number, number>,
	highlighedSourceLinkStates: boolean[],
	setHighlightedSourceLinkStates: React.Dispatch<
		React.SetStateAction<boolean[]>
	>,
) => {
	console.log(content)
	const matches = Array.from(content.matchAll(/\[\^?(\d+)\^?\]/g));
	const elements: JSX.Element[] = [];
	let prevIndex = 0;
	DOMPurify.setConfig({
		ALLOWED_TAGS: ['iframe', 'pre', 'code', 'p', 'ol', 'li', 'ul','span'],
		ALLOWED_ATTR: ['src', 'width', 'height', 'frameborder', 'allowfullscreen', 'style', 'class']
	});
	matches.forEach((match) => {
		const sourceNum = parseInt(match[1], 10);
		const resolvedNum = sourceIndexMap.get(sourceNum) ?? 10;
		if (match.index !== null && resolvedNum < filteredSources.length) {
			elements.push(
				<span
					key={`content:${prevIndex}`}
					dangerouslySetInnerHTML={{
						__html: DOMPurify.sanitize(content.slice(prevIndex, match.index)),
					}}
				></span>,
			);
			elements.push(
				<InlineCitation
					key={`citation:${prevIndex}`}
					source={filteredSources[resolvedNum]}
					sourceNumber={resolvedNum}
					highlighted={highlighedSourceLinkStates[resolvedNum]}
					onMouseEnter={() =>
						setHighlightedSourceLinkStates(
							filteredSources.map((_, i) => i === resolvedNum),
						)
					}
					onMouseLeave={() =>
						setHighlightedSourceLinkStates(filteredSources.map(() => false))
					}
				/>,
			);
			prevIndex = (match?.index ?? 0) + match[0].length;
		}
	});
	elements.push(
		<span
			key={`content:${prevIndex}`}
			dangerouslySetInnerHTML={{
				__html: DOMPurify.sanitize(content.slice(prevIndex)),
			}}
		></span>,
	);
	return elements;
};

export function ChatMessageBubble(props: {
	message: Message;
	aiEmoji?: string;
	isMostRecent: boolean;
	messageCompleted: boolean;
}) {
	const { role, content, runId } = props.message;
	const isUser = role === "user";
	const [isLoading, setIsLoading] = useState(false);
	const [traceIsLoading, setTraceIsLoading] = useState(false);
	const [feedback, setFeedback] = useState<Feedback | null>(null);
	const [comment, setComment] = useState("");
	const [feedbackColor, setFeedbackColor] = useState("");
	const upButtonRef = useRef(null);
	const downButtonRef = useRef(null);

	const cumulativeOffset = function (element: HTMLElement | null) {
		var top = 0,
			left = 0;
		do {
			top += element?.offsetTop || 0;
			left += element?.offsetLeft || 0;
			element = (element?.offsetParent as HTMLElement) || null;
		} while (element);

		return {
			top: top,
			left: left,
		};
	};

	const sendUserFeedback = async (score: number, key: string) => {
		let run_id = runId;
		if (run_id === undefined) {
			return;
		}
		if (isLoading) {
			return;
		}
		setIsLoading(true);
		try {
			const data = await sendFeedback({
				score,
				runId: run_id,
				key,
				feedbackId: feedback?.feedback_id,
				comment,
				isExplicit: true,
			});
			if (data.code === 200) {
				setFeedback({ run_id, score, key, feedback_id: data.feedbackId });
				score == 1 ? animateButton("upButton") : animateButton("downButton");
				if (comment) {
					setComment("");
				}
			}
		} catch (e: any) {
			console.error("Error:", e);
			toast.error(e.message);
		}
		setIsLoading(false);
	};
	const viewTrace = async () => {
		try {
			setTraceIsLoading(true);
			const response = await fetch(apiBaseUrl + "/get_trace", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify({
					run_id: runId,
				}),
			});

			const data = await response.json();

			if (data.code === 400) {
				toast.error("Unable to view trace");
				throw new Error("Unable to view trace");
			} else {
				const url = data.replace(/['"]+/g, "");
				window.open(url, "_blank");
				setTraceIsLoading(false);
			}
		} catch (e: any) {
			console.error("Error:", e);
			setTraceIsLoading(false);
			toast.error(e.message);
		}
	};

	const sources = props.message.sources ?? [];
	const { filtered: filteredSources, indexMap: sourceIndexMap } =
		filterSources(sources);

	// Use an array of highlighted states as a state since React
	// complains when creating states in a loop
	const [highlighedSourceLinkStates, setHighlightedSourceLinkStates] = useState(
		filteredSources.map(() => false),
	);
	const answerElements =
		role === "assistant"
			? createAnswerElements(
				content,
				filteredSources,
				sourceIndexMap,
				highlighedSourceLinkStates,
				setHighlightedSourceLinkStates,
			)
			: [];

	const animateButton = (buttonId: string) => {
		let button: HTMLButtonElement | null;
		if (buttonId === "upButton") {
			button = upButtonRef.current;
		} else if (buttonId === "downButton") {
			button = downButtonRef.current;
		} else {
			return;
		}
		if (!button) return;
		let resolvedButton = button as HTMLButtonElement;
		resolvedButton.classList.add("animate-ping");
		setTimeout(() => {
			resolvedButton.classList.remove("animate-ping");
		}, 500);

		emojisplosion({
			emojiCount: 10,
			uniqueness: 1,
			position() {
				const offset = cumulativeOffset(button);

				return {
					x: offset.left + resolvedButton.clientWidth / 2,
					y: offset.top + resolvedButton.clientHeight / 2,
				};
			},
			emojis: buttonId === "upButton" ? ["👍"] : ["👎"],
		});
	};
	const MessageContent = chakra(Box, {
		baseStyle: {
			'.markdown-content': {
				'h1, h2, h3, h4, h5, h6': {
					marginTop: '1.5em',
					marginBottom: '0.5em',
					fontWeight: 600,
					color: '#cdd6f4'
				},
				'h1': { fontSize: '2em' },
				'h2': { fontSize: '1.5em' },
				'h3': { fontSize: '1.3em' },
				'h4': { fontSize: '1.1em' },
				'p': {
					margin: '0.5em 0',  // 减小段落间距
					lineHeight: 1.4     // 减小行间距
				},
				// 统一使用相同的符号样式
				'ul': {
					listStyle: 'none',
					margin: '0.5em 0',  // 减小列表间距
					paddingLeft: '1.5em',
					'& > li': {
						position: 'relative',
						marginBottom: '0.3em',  // 减小列表项间距
						paddingLeft: '3em',
						'&::before': {
							content: '"▪"',  // 使用实心方块作为列表符号
							position: 'absolute',
							left: 0,
							color: '#89b4fa',
							fontWeight: 'bold',
							paddingLeft: '1.5em',
						}
					}
				},
				'ol': {
					listStyle: 'none',
					margin: '0.5em 0',  // 减小列表间距
					'& > li': {
						position: 'relative',
						marginBottom: '0.3em',  // 减小列表项间距
						paddingLeft: '1.5em',
						'&::before': {
							content: '"▶"',  // 使用实心方块作为列表符号
							position: 'absolute',
							left: 0,
							color: '#89b4fa',
							fontWeight: 'bold',
						}
					},
					// 为ol下的ul添加额外的缩进
					'& ul': {
						paddingLeft: '1.5em',  // 增加缩进
						marginTop: '0.3em',
						marginBottom: '0.3em',
					}
				},
				'li > ul, li > ol': {
					marginTop: '0.3em',    // 减小嵌套列表间距
					marginBottom: '0.3em', // 减小嵌套列表间距
				},
				'img': {
					maxWidth: '100%',
					borderRadius: '4px',
					margin: '1em 0'
				},
				'hr': {
					border: 'none',
					borderTop: '1px solid #45475a',
					margin: '1.5em 0'
				},
				'blockquote': {
					borderLeft: '4px solid #89b4fa',
					padding: '0.5em 1em',
					margin: '1em 0',
					backgroundColor: 'rgba(137, 180, 250, 0.1)',
					borderRadius: '0 4px 4px 0',
				},
				'code': {
					backgroundColor: '#1e1e2e',
					padding: '0.2em 0.4em',
					borderRadius: '3px',
					fontSize: '0.9em',
					fontFamily: 'monospace',
					color: '#f38ba8'
				},
				'pre': {
					backgroundColor: '#1e1e2e',
					padding: '1em',
					borderRadius: '8px',
					overflow: 'auto',
					margin: '1em 0',
					border: '1px solid #313244',
					'& code': {
						backgroundColor: 'transparent',
						padding: 0,
						color: '#cdd6f4'
					}
				},
				'table': {
					width: '100%',
					marginTop: '1em',
					marginBottom: '1em',
					borderCollapse: 'collapse',
					'th, td': {
						border: '1px solid #45475a',
						padding: '0.75em',
						textAlign: 'left'
					},
					'th': {
						backgroundColor: '#313244',
						color: '#cdd6f4'
					},
					'tr:nth-of-type(even)': {
						backgroundColor: 'rgba(137, 180, 250, 0.05)'
					}
				},
				'a': {
					color: '#89b4fa',
					textDecoration: 'none',
					transition: 'color 0.2s',
					'&:hover': {
						color: '#b4befe',
						textDecoration: 'underline'
					}
				}
			}
		}
	});

	return (
		<VStack align="start" spacing={5} pb={5}>
			{/* 在消息内容之前添加图片显示区域 */}
			{props.message.images && props.message.images.length > 0 && (
				<Grid
					templateColumns={{
						base: "repeat(auto-fill, minmax(120px, 1fr))",
						md: "repeat(auto-fill, minmax(150px, 1fr))"
					}}
					gap={4}
					width="100%"
					padding={2}
				>
					{props.message.images.map((imageUrl, index) => (
						<Box key={index}>
							<Image
								src={imageUrl}
								alt={`User uploaded image ${index + 1}`}
								maxH="200px"
								objectFit="contain"
								width="100%"
								borderRadius="md"
							/>
						</Box>
					))}
				</Grid>
			)}
			{!isUser && filteredSources.length > 0 && (
				<>
					<Flex direction={"column"} width={"100%"}>
						<VStack spacing={"5px"} align={"start"} width={"100%"}>
							<Heading
								fontSize="lg"
								fontWeight={"medium"}
								mb={1}
								color={"blue.300"}
								paddingBottom={"10px"}
							>
								Sources
							</Heading>
							<HStack spacing={"10px"} maxWidth={"100%"} overflow={"auto"}>
								{filteredSources.map((source, index) => (
									<Box key={index} alignSelf={"stretch"} width={40}>
										<SourceBubble
											source={source}
											highlighted={highlighedSourceLinkStates[index]}
											onMouseEnter={() =>
												setHighlightedSourceLinkStates(
													filteredSources.map((_, i) => i === index),
												)
											}
											onMouseLeave={() =>
												setHighlightedSourceLinkStates(
													filteredSources.map(() => false),
												)
											}
											runId={runId}
										/>
									</Box>
								))}
							</HStack>
						</VStack>
					</Flex>

					<Heading size="lg" fontWeight="medium" color="blue.300">
						Answer
					</Heading>
				</>
			)}
			{isUser ? (
				<Heading size="lg" fontWeight="medium" color="white">
					{content}
				</Heading>
			) : (
				<MessageContent width="100%" className="whitespace-pre-wrap" color="white">
					<div className="markdown-content">
						{answerElements}
					</div>
				</MessageContent>
			)}

			{props.message.role !== "user" &&
				props.isMostRecent &&
				props.messageCompleted && (
					<HStack spacing={2}>
						<Button
							ref={upButtonRef}
							size="sm"
							variant="outline"
							colorScheme={feedback === null ? "green" : "gray"}
							onClick={() => {
								if (feedback === null && props.message.runId) {
									sendUserFeedback(1, "user_score");
									animateButton("upButton");
									setFeedbackColor("border-4 border-green-300");
								} else {
									toast.error("You have already provided your feedback.");
								}
							}}
						>
							👍
						</Button>
						<Button
							ref={downButtonRef}
							size="sm"
							variant="outline"
							colorScheme={feedback === null ? "red" : "gray"}
							onClick={() => {
								if (feedback === null && props.message.runId) {
									sendUserFeedback(0, "user_score");
									animateButton("downButton");
									setFeedbackColor("border-4 border-red-300");
								} else {
									toast.error("You have already provided your feedback.");
								}
							}}
						>
							👎
						</Button>
						<Spacer />
						<Button
							size="sm"
							variant="outline"
							colorScheme={runId === null ? "blue" : "gray"}
							onClick={(e) => {
								e.preventDefault();
								viewTrace();
							}}
							isLoading={traceIsLoading}
							loadingText="🔄"
							color="white"
						>
							🦜🛠️ View trace
						</Button>
					</HStack>
				)}

			{/* {isUser && showProcessingTip(props.processingTip)} */}
			{!isUser && <Divider mt={4} mb={4} />}
		</VStack>
	);
}
