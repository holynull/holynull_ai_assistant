"use client";

import { Button, Image, Input, VStack, Text, Grid, Center, Tooltip } from "@chakra-ui/react";
import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { RemoteRunnable } from "langchain/runnables/remote";
import { applyPatch } from "@langchain/core/utils/json_patch";

import { EmptyState } from "../components/EmptyState";
import { ChatMessageBubble, Message } from "../components/ChatMessageBubble";
import { AutoResizeTextarea } from "./AutoResizeTextarea";
import { marked } from "marked";
import { Renderer } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/gradient-dark.css";

import "react-toastify/dist/ReactToastify.css";
import {
	Heading,
	Flex,
	IconButton,
	InputGroup,
	InputRightElement,
	Spinner,
	Box,
} from "@chakra-ui/react";
import { ArrowUpIcon, CloseIcon, DeleteIcon, Icon, } from "@chakra-ui/icons";
import { Select, Link } from "@chakra-ui/react";
import { Source } from "./SourceBubble";
import { apiBaseUrl } from "../utils/constants";
import { ChatPromptValue } from "@langchain/core/prompt_values"
import { AIMessage, FunctionMessage, AIMessageChunk, FunctionMessageChunk } from "@langchain/core/messages"
import { forEach } from "lodash";
import { FaCircleNotch, FaTools, FaKeyboard, FaCheck, FaUpload, FaFilePdf, FaEye, FaLightbulb, FaPlus, FaTimes } from 'react-icons/fa';
import { BiBot } from 'react-icons/bi';
import { Document, Page, pdfjs } from 'react-pdf';
// import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.entry';

// 重要：在组件外部配置 worker
if (typeof window !== "undefined") {
	pdfjs.GlobalWorkerOptions.workerSrc = `//cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js`;
}
// 设置pdf.js worker路径
// pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.js`
// pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;
// pdfjs.GlobalWorkerOptions.workerSrc = pdfjsWorker;
// pdfjs.GlobalWorkerOptions.workerSrc = `//cdn.jsdelivr.net/npm/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;


const init_msg = "Please input your question."
const typing_msg = "Typing answer...."
const processing_msg = "Processing..."
const processing_end_msg = "Processing end."
const synthesizing_question_msg = "Synthesizing question..."
const invoking_tool_msg = "Invoking tool..."
function showProcessingTip(processingTip: string) {
	if (processingTip != "" && processingTip != init_msg) {
		return <Box className="whitespace-pre-wrap" color="green" padding={".2em"}>
			{processingTip}
		</Box>
	} else {
		return <Box className="whitespace-pre-wrap" color="red">
			{processingTip}
		</Box>
	}
}

enum ProcessingStatus {
	Idle = "idle",
	SynthesizingQuestion = "synthesizing_question",
	InvokingTool = "invoking_tool",
	Processing = "processing",
	Typing = "typing",
	Completed = "completed"
}

interface ImageFile {
	id: string;
	file: File;
	previewUrl: string;
	base64: string;
}

interface ImageUrl {
	id: string;
	url: string;
	base64: string;
}

interface PDFFile {
	id: string;
	file: File;
	name: string;
	size: number;
	base64: string;  // 添加 base64 字段
}

export function ChatWindow(props: { conversationId: string }) {
	const conversationId = props.conversationId;

	const searchParams = useSearchParams();

	const messageContainerRef = useRef<HTMLDivElement | null>(null);
	const [messages, setMessages] = useState<Array<Message>>([]);
	const [input, setInput] = useState("");
	const [imageData, setImageData] = useState<string | null>(null);

	const [isLoading, setIsLoading] = useState(false);
	const [llm, setLlm] = useState(
		searchParams.get("llm") ?? "anthropic_claude_3_5_sonnet",
	);
	const [processingTip, setProcessingTip] = useState("Please input your question.")

	const [chatHistory, setChatHistory] = useState<
		{ type: string; content: string }[]
	>([]);

	const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>(ProcessingStatus.Idle);

	// 添加一个标志来追踪图片是否已经被使用
	const [usedImages, setUsedImages] = useState<Set<string>>(new Set());

	const [isDragging, setIsDragging] = useState(false);

	const [showFileUpload, setShowFileUpload] = useState(false);

	const openFileUpload = () => {
		if (!showFileUpload)
			setShowFileUpload(!showFileUpload);
	};

	const closeFileUpload = () => {
		if (showFileUpload) {
			// 如果当前是显示状态，在隐藏之前清空所有文件
			clearAllFiles();
		}
		if (showFileUpload)
			setShowFileUpload(!showFileUpload);
	};

	// 添加处理拖拽的函数
	const handleDragEnter = (e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setIsDragging(true);
	};

	const handleDragLeave = (e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setIsDragging(false);
	};

	const handleDragOver = (e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
	};

	const handleDrop = async (e: React.DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		setIsDragging(false);

		const files = Array.from(e.dataTransfer.files);
		const totalFiles = imageFiles.length + imageUrls.length + pdfFiles.length + files.length;

		if (totalFiles > MAX_FILES) {
			alert(`You can only upload up to ${MAX_FILES} files in total`);
			return;
		}

		for (const file of files) {
			if (file.size > MAX_FILE_SIZE) {
				alert(`File ${file.name} exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit`);
				continue;
			}

			try {
				const base64 = await convertToBase64(file);

				if (file.type.startsWith('image/')) {
					const previewUrl = URL.createObjectURL(file);
					const newImageFile: ImageFile = {
						id: Math.random().toString(),
						file: file,
						previewUrl: previewUrl,
						base64: base64
					};
					setImageFiles(prev => [...prev, newImageFile]);
				} else if (file.type === 'application/pdf') {
					const newPDFFile: PDFFile = {
						id: Math.random().toString(),
						file: file,
						name: file.name,
						size: file.size,
						base64: base64
					};
					setPdfFiles(prev => [...prev, newPDFFile]);
				}
			} catch (error) {
				console.error("Error handling file:", error);
			}
		}
	};

	function showProcessingStatus(status: ProcessingStatus) {
		switch (status) {
			case ProcessingStatus.Idle:
				return null;
			case ProcessingStatus.SynthesizingQuestion:
				return (
					<div className="flex items-center text-blue-500">
						<FaCircleNotch className="animate-spin mr-2" size={20} />
						<span>Thinking</span>
					</div>
				);
			case ProcessingStatus.InvokingTool:
				return (
					<div className="flex items-center text-purple-500">
						<FaTools className="mr-2" size={20} />
						<span>Using Tools</span>
					</div>
				);
			case ProcessingStatus.Processing:
				return (
					<div className="flex items-center text-orange-500">
						<FaCircleNotch className="animate-spin mr-2" size={20} />
						<span>Processing</span>
					</div>
				);
			case ProcessingStatus.Typing:
				return (
					<div className="flex items-center text-green-500">
						<FaKeyboard className="mr-2" size={20} />
						<span>Typing</span>
					</div>
				);
			case ProcessingStatus.Completed:
				return (
					<div className="flex items-center text-green-500">
						<FaCheck className="mr-2" size={20} />
						<span>Completed</span>
					</div>
				);
		}
	}

	const [imageFiles, setImageFiles] = useState<ImageFile[]>([]);
	const [imageUrls, setImageUrls] = useState<ImageUrl[]>([]);
	const [uploadType, setUploadType] = useState<"file" | "url" | "pdf">("file");
	const [isConverting, setIsConverting] = useState(false);


	const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
	const MAX_FILES = 100; // 最多上传10张图片

	const convertToBase64 = (file: File): Promise<string> => {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.readAsDataURL(file);
			reader.onload = () => {
				resolve(reader.result as string);
			};
			reader.onerror = error => reject(error);
		});
	};

	// 修改文件上传处理函数
	const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
		const files = event.target.files;
		if (!files) return;

		const totalFiles = imageFiles.length + imageUrls.length + pdfFiles.length + files.length;
		if (totalFiles > MAX_FILES) {
			alert(`You can only upload up to ${MAX_FILES} files in total`);
			return;
		}

		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			if (file.size > MAX_FILE_SIZE) {
				alert(`File ${file.name} exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit`);
				continue;
			}

			try {
				const base64 = await convertToBase64(file);

				if (file.type.startsWith('image/')) {
					// 处理图片文件
					const previewUrl = URL.createObjectURL(file);
					const newImageFile: ImageFile = {
						id: Math.random().toString(),
						file: file,
						previewUrl: previewUrl,
						base64: base64
					};
					setImageFiles(prev => [...prev, newImageFile]);
				} else if (file.type === 'application/pdf') {
					// 处理PDF文件
					const newPDFFile: PDFFile = {
						id: Math.random().toString(),
						file: file,
						name: file.name,
						size: file.size,
						base64: base64
					};
					setPdfFiles(prev => [...prev, newPDFFile]);
				}
			} catch (error) {
				console.error("Error handling file:", error);
			}
		}

		event.target.value = '';
	};

	const urlToBase64 = async (url: string): Promise<string> => {
		try {
			const response = await fetch(url);
			const blob = await response.blob();
			return new Promise((resolve, reject) => {
				const reader = new FileReader();
				reader.onload = () => resolve(reader.result as string);
				reader.onerror = reject;
				reader.readAsDataURL(blob);
			});
		} catch (error) {
			console.error("Error converting URL to base64:", error);
			throw error;
		}
	};

	const isValidImageUrl = (url: string): boolean => {
		return /\.(jpg|jpeg|png|gif|webp)$/i.test(url);
	};

	const handleUrlInput = async (url: string) => {
		const totalImages = imageFiles.length + imageUrls.length;
		if (totalImages >= MAX_FILES) {
			alert(`You can only add up to ${MAX_FILES} images in total`);
			return;
		}

		if (url && isValidImageUrl(url)) {
			try {
				setIsConverting(true);
				const base64 = await urlToBase64(url);
				const newImageUrl: ImageUrl = {
					id: Math.random().toString(),
					url: url,
					base64: base64
				};
				setImageUrls(prev => {
					const newUrls = [...prev, newImageUrl];
					// 更新 currentImages
					setCurrentImages([
						...imageFiles.map(img => img.base64),
						...newUrls.map(img => img.base64)
					]);
					return newUrls;
				});
			} catch (error) {
				console.error("Error converting URL to base64:", error);
				alert("Error loading image from URL");
			} finally {
				setIsConverting(false);
			}
		}
	};

	// 添加新的状态来跟踪当前图片数据
	const [currentImages, setCurrentImages] = useState<string[]>([]);

	useEffect(() => {
		console.log('Current images updated:', currentImages);
	}, [currentImages]);

	const removeImage = (id: string, type: "file" | "url") => {
		if (type === "file") {
			setImageFiles(prev => {
				const newFiles = prev.filter(img => img.id !== id);
				const removedFile = prev.find(img => img.id === id);
				if (removedFile) {
					URL.revokeObjectURL(removedFile.previewUrl);
				}
				// 更新 currentImages
				setCurrentImages([
					...newFiles.map(img => img.base64),
					...imageUrls.map(img => img.base64)
				]);
				return newFiles;
			});
		} else {
			setImageUrls(prev => {
				const newUrls = prev.filter(img => img.id !== id);
				// 更新 currentImages
				setCurrentImages([
					...imageFiles.map(img => img.base64),
					...newUrls.map(img => img.base64)
				]);
				return newUrls;
			});
		}
	};

	const clearAllFiles = () => {
		imageFiles.forEach(img => URL.revokeObjectURL(img.previewUrl));
		setImageFiles([]);
		setImageUrls([]);
		setPdfFiles([]);
		setCurrentImages([]);
		setImageData(null);
	};

	// 在ChatWindow组件中添加粘贴处理函数
	useEffect(() => {
		const handlePaste = async (e: ClipboardEvent) => {
			const items = e.clipboardData?.items;
			if (!items) return;

			for (const item of Array.from(items)) {
				if (item.type.startsWith('image/')) {
					e.preventDefault(); // 阻止默认粘贴行为

					const file = item.getAsFile();
					if (!file) continue;

					if (imageFiles.length + imageUrls.length >= MAX_FILES) {
						alert(`You can only upload up to ${MAX_FILES} images in total`);
						return;
					}

					if (file.size > MAX_FILE_SIZE) {
						alert(`File exceeds 5MB limit`);
						return;
					}

					try {
						const previewUrl = URL.createObjectURL(file);
						const base64 = await convertToBase64(file);
						const newImageFile: ImageFile = {
							id: Math.random().toString(),
							file: file,
							previewUrl: previewUrl,
							base64: base64
						};

						setImageFiles(prev => {
							const newFiles = [...prev, newImageFile];
							// 更新 currentImages
							setCurrentImages([
								...newFiles.map(img => img.base64),
								...imageUrls.map(img => img.base64)
							]);
							return newFiles;
						});

						// 显示粘贴成功提示
						// 你可以使用 toast 或其他提示组件
						console.log('Image pasted successfully');
					} catch (error) {
						console.error("Error handling pasted image:", error);
						alert("Error processing pasted image");
					}
				}
			}
		};

		document.addEventListener('paste', handlePaste);
		return () => document.removeEventListener('paste', handlePaste);
	}, [imageFiles, imageUrls, MAX_FILES, MAX_FILE_SIZE]); // 只依赖图片数组，移除 uploadType 依赖

	const sendMessage = async (message?: string) => {
		if (messageContainerRef.current) {
			messageContainerRef.current.classList.add("grow");
		}
		if (isLoading) {
			return;
		}
		const messageValue = message ?? input;
		if (messageValue === "") return;
		setInput("");

		// 收集当前所有图片
		const currentImages = [
			...imageFiles.map(img => img.base64),
			...imageUrls.map(img => img.base64),
		].filter(Boolean);

		const currentPDFs = pdfFiles.map(pdf => pdf.base64).filter(Boolean);

		setMessages((prevMessages) => {
			const newMessages = [
				...prevMessages,
				{
					id: Math.random().toString(),
					content: messageValue,
					role: "user" as const, // 明确指定类型
					images: currentImages,
				} as Message
			];
			setTimeout(scrollToBottom, 0);
			return newMessages;
		});
		setIsLoading(true);

		let accumulatedMessage = "";
		let runId: string | undefined = undefined;
		let sources: Source[] | undefined = undefined;
		let messageIndex: number | null = null;

		let renderer = new Renderer();
		renderer.paragraph = (text) => {
			return text + "\n";
		};
		renderer.list = (text) => {
			return `${text}\n\n`;
		};
		renderer.listitem = (text) => {
			return `\n• ${text}`;
		};
		renderer.code = (code, language) => {
			const validLanguage = hljs.getLanguage(language || "")
				? language
				: "plaintext";
			const highlightedCode = hljs.highlight(
				validLanguage || "plaintext",
				code,
			).value;
			return `<pre class="highlight bg-gray-700" style="padding: 5px; border-radius: 5px; overflow: auto; overflow-wrap: anywhere; white-space: pre-wrap; max-width: 100%; display: block; line-height: 1.2"><code class="${language}" style="color: #d6e2ef; font-size: 12px; ">${highlightedCode}</code></pre>`;
		};
		marked.setOptions({ renderer });
		try {
			const sourceStepName = "FindDocs";
			let streamedResponse: Record<string, any> = {};

			const remoteChain = new RemoteRunnable({
				url: process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL : "",
				options: {
					timeout: 3000000,
				},
			});
			const llmDisplayName = llm ?? "openai_gpt_3_5_turbo";
			const streams = await remoteChain.stream(
				{
					input: messageValue,
					// chat_history: chatHistory,
					chat_history: [],
					image_urls: currentImages,
					pdf_files: currentPDFs
				},
				{
					configurable: {
						llm: llmDisplayName,
					},
					tags: ["model:" + llmDisplayName],
					metadata: {
						conversation_id: conversationId,
						llm: llmDisplayName,
						is_multimodal: currentImages.length > 0 || currentPDFs.length > 0, // 当有图片时为 true
						images_size: currentImages.length,
					},
				},
				// {
				//   includeNames: [sourceStepName],
				// },
			);
			var chunk_buff = "";
			var buff_size = 100;
			var n = 0;
			for await (const chunk of streams) {
				console.log(chunk)
				var _chunk: object
				if (typeof chunk === "object") {
					_chunk = chunk as object;
					if ("run_id" in _chunk) {
						runId = _chunk.run_id as string;
					}
					var kind = "event" in _chunk ? _chunk.event : "";
					switch (kind) {
						case "on_chain_start":
							setProcessingStatus(ProcessingStatus.SynthesizingQuestion);
							break;
						case "on_chain_end":
							setProcessingStatus(ProcessingStatus.Processing);
							break;
						case "on_chain_stream":
							break
						case "on_chat_model_start":
							setProcessingStatus(ProcessingStatus.Processing);
							break;
						case "on_chat_model_end":
							setProcessingStatus(ProcessingStatus.Completed);
							break;
						case "on_chat_model_stream":
							setProcessingStatus(ProcessingStatus.Typing);
							if ("data" in _chunk) {
								var data = _chunk.data as object
								if ("chunk" in data && data.chunk instanceof AIMessageChunk) {
									var aichunk = data.chunk as AIMessageChunk;
									if (typeof (aichunk.content) == "string")
										accumulatedMessage += aichunk.content.toString();
									else if (Array.isArray(aichunk.content) && aichunk.content[0] && "text" in aichunk.content[0]) {
										var c_t = aichunk.content[0]['text'] as string;
										// const regex = /^<thinking>.*<\/thinking>$/;
										// if (!regex.test(c_t))
										accumulatedMessage += c_t;
										// else
										// 	console.log(c_t)
									}
									else
										console.log(_chunk)
								}
							}
							var parsedResult = marked.parse(accumulatedMessage);
							if (parsedResult != undefined) {
								setMessages((prevMessages) => {
									let newMessages = [...prevMessages];
									if (
										messageIndex === null ||
										newMessages[messageIndex] === undefined
									) {
										messageIndex = newMessages.length;
										newMessages.push({
											id: Math.random().toString(),
											content: parsedResult.trim(),
											runId: runId,
											sources: sources,
											role: "assistant",
										});
									} else if (newMessages[messageIndex] !== undefined) {
										newMessages[messageIndex].content = parsedResult.trim();
										newMessages[messageIndex].runId = runId;
										// newMessages[messageIndex].sources = sources;
									}
									// 使用 setTimeout 确保在 DOM 更新后执行滚动
									setTimeout(scrollToBottom, 0);
									return newMessages;
								});
							}
							break
						case "on_tool_start":
							setProcessingStatus(ProcessingStatus.InvokingTool);
							break;
						case "on_tool_end":
							setProcessingStatus(ProcessingStatus.Processing);
							// if ("name" in _chunk && _chunk.name == "googleSerperSearch") {
							// 	if ("data" in _chunk) {
							// 		var data = _chunk.data as object;
							// 		if ("output" in data) {
							// 			var output = eval('(' + data.output + ')');
							// 			sources = output.map((doc: Record<string, any>) => ({
							// 				url: doc.link,
							// 				title: doc.title,
							// 			}));
							// 		}
							// 	}
							// }
							let currentSources: Source[] = [];
							if ("name" in _chunk && _chunk.name == 'search') {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										var _output = data.output as Array<any>
										currentSources = _output.map((doc: Record<string, any>) => ({
											url: doc.value.url,
											title: doc.value.title,
											img_src: doc.value.imageUrl,
										}));
									}
								}
							}
							if ("name" in _chunk && (_chunk.name == "searchWebPageToAnswer" || _chunk.name == "searchNewsToAnswer")) {

								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										var output = eval('(' + data.output + ')');
										sources = output.map((doc: Record<string, any>) => ({
											url: doc.link,
											title: doc.title,
											img_src: doc.imageUrl,
										}));
									}
								}
							}
							sources = [...sources ? sources : [], ...currentSources];
							setMessages((prevMessages) => {
								let newMessages = [...prevMessages];
								if (
									messageIndex === null ||
									newMessages[messageIndex] === undefined
								) {
									messageIndex = newMessages.length;
									newMessages.push({
										id: Math.random().toString(),
										content: parsedResult ? parsedResult.trim() : "",
										runId: runId,
										sources: sources,
										role: "assistant",
									});
								} else if (newMessages[messageIndex] !== undefined) {
									// newMessages[messageIndex].content = parsedResult.trim();
									newMessages[messageIndex].runId = runId;
									newMessages[messageIndex].sources = sources;
								}
								// 使用 setTimeout 确保在 DOM 更新后执行滚动
								setTimeout(scrollToBottom, 0);
								return newMessages;
							});
							break
						default:
							break
					}

				}
			}
			setChatHistory((prevChatHistory) => [
				...prevChatHistory,
				{ type: "human", content: messageValue },
				{ type: "ai", content: accumulatedMessage },
			]);
			setIsLoading(false);
			setProcessingStatus(ProcessingStatus.Idle);
		} catch (e) {
			setMessages((prevMessages) => prevMessages.slice(0, -1));
			setIsLoading(false);
			setInput(messageValue);
			setProcessingStatus(ProcessingStatus.Idle);
			throw e;
		}
	};

	const sendInitialQuestion = async (question: string) => {
		await sendMessage(question);
	};

	const insertUrlParam = (key: string, value?: string) => {
		if (window.history.pushState) {
			const searchParams = new URLSearchParams(window.location.search);
			searchParams.set(key, value ?? "");
			const newurl =
				window.location.protocol +
				"//" +
				window.location.host +
				window.location.pathname +
				"?" +
				searchParams.toString();
			window.history.pushState({ path: newurl }, "", newurl);
		}
	};
	const scrollToBottom = () => {
		if (messageContainerRef.current) {
			messageContainerRef.current.scrollTop = messageContainerRef.current.scrollHeight;
		}
	};
	useEffect(() => {
		scrollToBottom();
	}, [messages]);
	// 在组件顶部添加全局粘贴提示
	// 修改 GlobalPasteHint 组件的定义
	interface GlobalPasteHintProps {
		onClose?: () => void;  // 将 onClose 设为可选属性
	}
	// 处理关闭提示的函数
	const handleClosePasteHint = () => {
		setShowPasteHint(false);
	};
	// 添加鼠标悬停时暂停隐藏的功能
	const [isPaused, setIsPaused] = useState(false);
	const GlobalPasteHint = ({ onClose }: GlobalPasteHintProps) => (
		<Box
			position="fixed"
			top={0}
			left={0}
			right={0}
			bg="rgba(0, 0, 0, 0.9)"
			color="white"
			py={2}
			zIndex={1000}
			backdropFilter="blur(8px)"
			borderBottom="1px solid rgba(255, 255, 255, 0.1)"
			transition="all 0.3s ease"
			onMouseEnter={() => setIsPaused(true)}
			onMouseLeave={() => {
				setIsPaused(false);
				setTimeout(() => setShowPasteHint(false), 3000);
			}}
		>
			<Flex
				maxW="container.xl"
				mx="auto"
				px={4}
				justify="center"
				align="center"
				gap={2}
			>
				<Icon as={FaLightbulb} color="yellow.400" />
				<Text fontSize="sm" fontWeight="medium">
					You can paste images from clipboard at any time (Ctrl/Cmd + V)
				</Text>
				{!isPaused && (
					<Box
						position="absolute"
						bottom={0}
						left={0}
						height="2px"
						bg="blue.400"
						animation="progressBar 8s linear"
						sx={{
							'@keyframes progressBar': {
								'0%': { width: '100%' },
								'100%': { width: '0%' },
							},
						}}
					/>
				)}
				<IconButton
					aria-label="Close hint"
					icon={<CloseIcon />}
					size="xs"
					variant="ghost"
					colorScheme="whiteAlpha"
					onClick={onClose}
					ml={2}
					_hover={{
						bg: 'whiteAlpha.200'
					}}
				/>
			</Flex>
		</Box>
	);
	// 添加粘贴状态提示组件
	const [isPasting, setIsPasting] = useState(false);

	// 修改粘贴处理函数中的相关部分
	const handlePaste = async (e: ClipboardEvent) => {
		// ... 其他代码 ...
		try {
			setIsPasting(true);
			// ... 处理粘贴逻辑 ...
		} catch (error) {
			// ... 错误处理 ...
		} finally {
			setIsPasting(false);
		}
	};
	// 添加状态控制提示的显示
	const [showPasteHint, setShowPasteHint] = useState(true);
	// 组件挂载时启动定时器，几秒后隐藏提示
	useEffect(() => {
		const timer = setTimeout(() => {
			setShowPasteHint(false);
		}, 8000); // 8秒后自动隐藏

		return () => clearTimeout(timer);
	}, []);

	// 当用户开始拖拽文件时显示提示
	useEffect(() => {
		if (isDragging) {
			setShowPasteHint(true);
			// 拖拽结束后几秒隐藏提示
			const timer = setTimeout(() => {
				setShowPasteHint(false);
			}, 8000);
			return () => clearTimeout(timer);
		}
	}, [isDragging]);

	const [pdfFiles, setPdfFiles] = useState<PDFFile[]>([]);
	const [selectedPdf, setSelectedPdf] = useState<PDFFile | null>(null);
	const [numPages, setNumPages] = useState<number>(0);
	return (
		<div className="min-h-screen w-full bg-[#131318]">
			{showPasteHint && <GlobalPasteHint onClose={handleClosePasteHint} />}
			<div className="flex flex-col min-h-screen w-full bg-[#131318] overflow-x-hidden">
				<div className="flex flex-col items-center p-4 md:p-8 grow w-full max-w-[1200px] mx-auto">
					<Flex
						direction={"column"}
						alignItems={"center"}
						marginTop={messages.length > 0 ? "2" : "8"}
						mb={6}
						position="sticky"
						top={0}
						bg="rgba(19, 19, 24, 0.95)"
						backdropFilter="blur(8px)"
						zIndex={10}
						width="100%"
						py={4}
					>
						<Heading
							fontSize={messages.length > 0 ? "2xl" : "3xl"}
							fontWeight={"medium"}
							mb={2}
							color={"white"}
							textAlign="center"
						>
							🍺 Eddie's Assistant 🥩
						</Heading>
						<Heading
							fontSize="xl"
							fontWeight={"normal"}
							color={"white"}
							marginTop={"10px"}
							textAlign={"center"}
						>
							Ask me anything!{" "}
						</Heading>

						<div className="text-white flex flex-wrap items-center mt-4">
							<div className="flex items-center mb-2">
								<span className="shrink-0 mr-2">Powered by</span>
								<Select
									value={llm}
									onChange={(e) => {
										insertUrlParam("llm", e.target.value);
										setLlm(e.target.value);
									}}
									width={"240px"}
								>
									{/* <option value="anthropic_claude_3_opus">Anthropic-Claude-3-Opus</option> */}
									{/* <option value="openai_gpt_4_turbo_preview">GPT-4-Turbo</option> */}
									<option value="anthropic_claude_3_5_sonnet">Anthropic-Claude-3.5-Sonnet</option>
									<option value="openai_gpt_4o">GPT-4o</option>
									<option value="openai_gpt_4o_mini">GPT-4o-mini</option>
									{/* <option value="openai_gpt_3_5_turbo_1106">GPT-3.5-Turbo</option> */}
									{/* <option value="pplx_sonar_medium_chat">PPLX_sonar_medium_chat</option> */}
									{/* <option value="mistral_large">Mistral-Large</option> */}
									{/* <option value="command_r_plus">Command R+</option> */}
								</Select>
							</div>
						</div>
						<div className="ml-4">
							{showProcessingStatus(processingStatus)}
						</div>
					</Flex>
					<div
						className="flex flex-col-reverse w-full mb-2 overflow-y-auto overflow-x-hidden scroll-smooth bg-[#131318]"
						ref={messageContainerRef}
						style={{
							maxHeight: "calc(100vh - 350px)",
							minHeight: "200px",
							scrollBehavior: "smooth",
							flex: 1,
						}}
					>
						{
							[...messages]
								.reverse()
								.map((m, index) => (
									<ChatMessageBubble
										key={m.id}
										message={{ ...m }}
										aiEmoji="🦜"
										isMostRecent={index === 0}
										messageCompleted={!isLoading}
									></ChatMessageBubble>
								))
						}
					</div>
					<InputGroup size="md" alignItems={"center"} className="w-full bg-[#131318] mb-8">
						<AutoResizeTextarea
							value={input}
							maxRows={5}
							className="pr-24"
							marginRight={"112px"}
							sx={{
								maxWidth: "100%",
								overflowX: "hidden",
								"&::-webkit-scrollbar": {
									width: "4px",
								},
								"&::-webkit-scrollbar-track": {
									background: "transparent",
								},
								"&::-webkit-scrollbar-thumb": {
									background: "gray.500",
									borderRadius: "2px",
								},
							}}
							placeholder="Hello, World!"
							textColor={"white"}
							borderColor={"rgb(58, 58, 61)"}
							onChange={(e) => setInput(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									sendMessage();
								} else if (e.key === "Enter" && e.shiftKey) {
									e.preventDefault();
									setInput(input + "\n");
								}
							}}
						/>
						<InputRightElement width="auto" right="2">
							<Flex gap={2}>
								<Tooltip
									label="Upload files"
									placement="top"
								>
									<IconButton
										colorScheme={showFileUpload ? "gray" : "blue"}
										rounded={"full"}
										aria-label="Toggle file upload"
										icon={<Icon as={FaPlus} />}
										onClick={openFileUpload}
										isDisabled={showFileUpload}
										_disabled={{
											opacity: 0.6,
											cursor: "not-allowed",
											bg: "gray.600",
											_hover: {
												bg: "gray.600"
											}
										}}
									/>
								</Tooltip>
								<IconButton
									colorScheme="blue"
									rounded={"full"}
									aria-label="Send"
									icon={isLoading ? <Spinner /> : <ArrowUpIcon />}
									type="submit"
									onClick={(e) => {
										e.preventDefault();
										sendMessage();
									}}
								/>
							</Flex>
						</InputRightElement>
					</InputGroup>
					{/* 文件上传区域 */}
					{showFileUpload && (
						<Flex
							direction="column"
							width="100%"
							mt={4}
							bg="whiteAlpha.50" // 添加略微可见的背景色
							borderRadius="xl" // 增加圆角
							p={4} // 添加内边距
							boxShadow="0 4px 6px rgba(0, 0, 0, 0.1)" // 添加微妙的阴影
							border="1px solid"
							borderColor="whiteAlpha.200" // 添加边框
						>
							<Flex
								justify="space-between"
								align="center"
								mb={4}
								borderBottom="2px"
								borderColor="whiteAlpha.300"
								pb={3}
							>
								<Select
									value={uploadType}
									onChange={(e) => {
										setUploadType(e.target.value as "file" | "url");
									}}
									width={"240px"}
									bg="whiteAlpha.50"
									border="1px solid"
									borderColor="whiteAlpha.200"
									color="white"
									_hover={{
										borderColor: "whiteAlpha.400",
										bg: "whiteAlpha.100"
									}}
									_focus={{
										borderColor: "whiteAlpha.500",
										boxShadow: "none"
									}}
									sx={{
										"& option": {
											bg: "#131318",
											color: "white"
										}
									}}
								>
									<option value="file">Upload Files</option>
									<option value="url">Input Image URLs</option>
								</Select>

								<IconButton
									aria-label="Close upload area"
									icon={<Icon as={FaTimes} />}
									size="md"
									variant="solid"
									bg="whiteAlpha.200"
									color="white"
									_hover={{
										bg: 'whiteAlpha.400',
										transform: 'scale(1.05)'
									}}
									_active={{
										bg: 'whiteAlpha.500'
									}}
									onClick={closeFileUpload}
									transition="all 0.2s"
									borderRadius="full"
									boxShadow="md"
								/>
							</Flex>

							{/* 图片预览网格 */}
							{showFileUpload && (imageFiles.length > 0 || imageUrls.length > 0 || pdfFiles.length > 0) && (
								<Box mt={4} mb={4} position="relative" className="bg-[#131318] w-full">
									<Box
										position="relative"
										borderWidth="1px"
										borderColor="gray.600"
										borderRadius="md"
										p={4}
										className="bg-[#131318]"
									>
										<Flex
											position="absolute"
											top={2}
											right={2}
											zIndex={2}
										>
											<Button
												leftIcon={<DeleteIcon />}
												size="sm"
												variant="solid"
												colorScheme="red"
												onClick={clearAllFiles}
												transition="all 0.2s"
												_hover={{
													transform: 'scale(1.05)',
													bg: 'red.600'
												}}
												_active={{
													bg: 'red.700'
												}}
												borderRadius="md"
												px={4}
												opacity={0.9}
												backdropFilter="blur(8px)"
											>
												Clear All ({imageFiles.length + imageUrls.length + pdfFiles.length})
											</Button>
										</Flex>

										{/* 图片网格 */}
										<Grid
											templateColumns={{
												base: "repeat(auto-fill, minmax(100px, 1fr))",
												sm: "repeat(auto-fill, minmax(120px, 1fr))",
												md: "repeat(auto-fill, minmax(150px, 1fr))"
											}}
											gap={2}
											mt={2}
											className="bg-[#131318] w-full"
										>
											{/* 显示上传的图片文件 */}
											{imageFiles.map((img) => (
												<Box
													key={img.id}
													position="relative"
													borderRadius="md"
													overflow="hidden"
													borderWidth="1px"
													borderColor="gray.600"
												>
													<Image
														src={img.previewUrl}
														alt="Uploaded image"
														width="100%"
														height="150px"
														objectFit="cover"
													/>
													<IconButton
														aria-label="Remove image"
														icon={<CloseIcon />}
														size="sm"
														position="absolute"
														top={1}
														right={1}
														colorScheme="red"
														opacity={0.8}
														_hover={{ opacity: 1 }}
														onClick={() => removeImage(img.id, "file")}
													/>
												</Box>
											))}

											{/* 显示URL图片 */}
											{imageUrls.map((img) => (
												<Box
													key={img.id}
													position="relative"
													borderRadius="md"
													overflow="hidden"
													borderWidth="1px"
													borderColor="gray.600"
												>
													<Image
														src={img.url}
														alt="URL image"
														width="100%"
														height="150px"
														objectFit="cover"
														fallback={<Box
															width="100%"
															height="150px"
															bg="gray.700"
															display="flex"
															alignItems="center"
															justifyContent="center"
														>
															<Text color="gray.400">Failed to load</Text>
														</Box>}
													/>
													<IconButton
														aria-label="Remove image"
														icon={<CloseIcon />}
														size="sm"
														position="absolute"
														top={1}
														right={1}
														colorScheme="red"
														opacity={0.8}
														_hover={{ opacity: 1 }}
														onClick={() => removeImage(img.id, "url")}
													/>
												</Box>
											))}
										</Grid>

										{/* PDF文件网格 */}
										{pdfFiles.length > 0 && (
											<Box mt={4}>
												<Text color="white" fontWeight="bold" mb={3}>PDF Files</Text>
												<Grid
													templateColumns={{
														base: "repeat(auto-fill, minmax(180px, 1fr))",
														sm: "repeat(auto-fill, minmax(200px, 1fr))",
														md: "repeat(auto-fill, minmax(250px, 1fr))"
													}}
													gap={3}
													width="100%"
												>
													{pdfFiles.map((pdf) => (
														<Box
															key={pdf.id}
															bg="whiteAlpha.50"
															borderRadius="lg"
															overflow="hidden"
															borderWidth="1px"
															borderColor="gray.600"
															transition="all 0.2s"
															_hover={{
																transform: 'translateY(-2px)',
																shadow: 'lg',
																borderColor: 'blue.400'
															}}
														>
															<Box p={4} position="relative">
																{/* PDF 图标和文件名区域 */}
																<Flex align="center" mb={2}>
																	<Box
																		bg="red.500"
																		p={3}
																		borderRadius="md"
																		mr={3}
																	>
																		<Icon as={FaFilePdf} color="white" boxSize={6} />
																	</Box>
																	<VStack align="start" spacing={0} flex={1}>
																		<Text
																			color="white"
																			fontSize="sm"
																			fontWeight="medium"
																			noOfLines={1}
																			title={pdf.name}
																		>
																			{pdf.name}
																		</Text>
																		<Text color="gray.400" fontSize="xs">
																			{(pdf.size / 1024 / 1024).toFixed(2)} MB
																		</Text>
																	</VStack>
																</Flex>

																{/* PDF 预览区域 */}
																<Box
																	bg="whiteAlpha.100"
																	p={3}
																	borderRadius="md"
																	mb={2}
																	height="150px"
																	overflow="hidden"
																>
																	<Document
																		file={URL.createObjectURL(pdf.file)}
																		onLoadSuccess={({ numPages }) => setNumPages(numPages)}
																		loading={
																			<Center h="full">
																				<Spinner />
																			</Center>
																		}
																		error={
																			<Center h="full">
																				<Text color="red.400">Failed to load PDF</Text>
																			</Center>
																		}
																	>
																		<Page
																			pageNumber={1}
																			width={200}
																			renderTextLayer={false}
																			renderAnnotationLayer={false}
																		/>
																	</Document>
																</Box>

																{/* 操作按钮区域 */}
																<Flex justify="space-between" align="center">
																	<Button
																		size="sm"
																		leftIcon={<Icon as={FaEye} />}
																		variant="ghost"
																		colorScheme="blue"
																		onClick={() => {
																			// 使用浏览器内置PDF查看器打开
																			window.open(URL.createObjectURL(pdf.file), '_blank');
																		}}
																	>
																		Preview
																	</Button>
																	<IconButton
																		aria-label="Remove PDF"
																		icon={<CloseIcon />}
																		size="sm"
																		variant="ghost"
																		colorScheme="red"
																		onClick={() => {
																			setPdfFiles(prev => prev.filter(file => file.id !== pdf.id));
																		}}
																	/>
																</Flex>
															</Box>
														</Box>
													))}
												</Grid>
											</Box>
										)}
									</Box>
								</Box>
							)}
							{uploadType === "file" && (
								<Box
									className={`w-full ${isDragging ? 'border-2 border-dashed border-blue-500 bg-blue-500/10' : 'border-2 border-dashed border-gray-600'}`}
									borderRadius="lg"
									p={6}
									mb={4}
									transition="all 0.3s ease"
									onDragEnter={handleDragEnter}
									onDragLeave={handleDragLeave}
									onDragOver={handleDragOver}
									onDrop={handleDrop}
								>
									<VStack spacing={4} justify="center" align="center" minHeight="200px">
										<input
											type="file"
											accept="image/*,.pdf"
											onChange={handleFileUpload}
											style={{ display: 'none' }}
											id="image-upload"
											multiple
										/>
										<Box textAlign="center">
											<Text color="gray.400" mb={2}>
												{isDragging
													? 'Drop your files here'
													: 'Drag & drop images or PDFs here or'}
											</Text>
											<Button
												as="label"
												htmlFor="image-upload"
												colorScheme="blue"
												size="lg"
												leftIcon={<FaUpload />}
												isDisabled={imageFiles.length + imageUrls.length + pdfFiles.length >= MAX_FILES}
											>
												Choose Files
											</Button>
										</Box>
										<Text fontSize="sm" color="gray.400" textAlign="center">
											{`${imageFiles.length + imageUrls.length + pdfFiles.length}/${MAX_FILES} files uploaded`}
										</Text>
										<Text fontSize="sm" color="gray.400">
											Supports: JPG, PNG, GIF, WEBP (Max 5MB) | PDF (Max 10MB)
										</Text>
										<Text fontSize="sm" color="gray.400">
											You can also paste images from clipboard
										</Text>
									</VStack>
								</Box>
							)}

							{uploadType === "url" && (
								<VStack spacing={2} width="100%">
									<InputGroup>
										<Input
											placeholder="Enter image URL"
											color="white"
											onKeyDown={(e) => {
												if (e.key === 'Enter') {
													const input = e.target as HTMLInputElement;
													handleUrlInput(input.value);
													input.value = '';
												}
											}}
											isDisabled={isConverting || imageFiles.length + imageUrls.length >= MAX_FILES}
										/>
										{isConverting && (
											<InputRightElement>
												<Spinner size="sm" />
											</InputRightElement>
										)}
									</InputGroup>
									<Text fontSize="sm" color="gray.400">
										Press Enter to add URL ({imageFiles.length + imageUrls.length}/{MAX_FILES})
									</Text>
								</VStack>
							)}

						</Flex>)}
				</div>
			</div >
		</div>
	);
}
