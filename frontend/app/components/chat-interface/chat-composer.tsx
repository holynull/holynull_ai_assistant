"use client";

import { ComposerPrimitive, ThreadPrimitive, useAttachment, useAttachmentRuntime, useComposerRuntime, SimpleImageAttachmentAdapter } from "@assistant-ui/react";
import { ComponentType, useMemo, type FC, useState, useEffect } from "react";

import { PaperclipIcon, SendHorizontalIcon } from "lucide-react";
import { BaseMessage } from "@langchain/core/messages";
import { TooltipIconButton } from "../ui/assistant-ui/tooltip-icon-button";
import { cn } from "@/app/utils/cn";
import Image from "next/image";


export interface ChatComposerProps {
	currentThreadId: string | null;
	messages: BaseMessage[];
	submitDisabled: boolean;
}

const CircleStopIcon = () => {
	return (
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 16 16"
			fill="currentColor"
			width="16"
			height="16"
		>
			<rect width="10" height="10" x="3" y="3" rx="2" />
		</svg>
	);
};
// Add proper types
interface AttachmentPanelProps {
	file: File | Blob;
	name?: string;
}
const getFileDataURL = (file: File) =>
	new Promise<string>((resolve, reject) => {
		const reader = new FileReader();

		reader.onload = () => resolve(reader.result as string);
		reader.onerror = (error) => reject(error);

		reader.readAsDataURL(file);
	});
export const ImagePanel: ComponentType<any> = (data) => {
	// const composerRuntime = useComposerRuntime();
	// let attachments = composerRuntime.getState().attachments
	const state = useAttachment();
	const attachmentsRuntime = useAttachmentRuntime();

	const [imageUrl, setImageUrl] = useState<string | null>(null);

	useEffect(() => {
		if (state.file) {
			getFileDataURL(state.file)
				.then(url => setImageUrl(url))
				.catch(err => console.error('Error getting file data URL:', err));
		}
	}, [state.file]);


	// let file=data['file']
	// const imageUrl = useMemo(() => {
	// 	try {
	// 		return URL.createObjectURL(file);
	// 	} catch (error) {
	// 		console.error('Error creating object URL:', error);
	// 		return '';
	// 	}
	// }, [file]);
	// const { remove, subscribe, getState } = useAttachmentRuntime()
	// const _state = getState()
	// subscribe(() => {
	// 	console.log("lllllll")
	// })
	// remove()

	return (
		<div className="relative group flex flex-col items-center p-2 hover:bg-gray-700/30 rounded-md transition-colors">
			<div className="w-32 h-32 relative rounded-md overflow-hidden border border-gray-600">
				{imageUrl && (
					<Image
						src={imageUrl}
						alt={state.file?.name || 'Image attachment'}
						fill
						className="object-cover"
					/>
				)}
			</div>
			<div className="flex flex-col w-full mt-2">
				<div className="text-xs text-gray-300 truncate max-w-[128px]">
					{state.file?.name || 'Image attachment'}
				</div>
				<div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
					<button
						onClick={() => attachmentsRuntime.remove()}
						className="p-1 rounded-full bg-gray-800/80 hover:bg-gray-700 text-gray-300"
						aria-label="Remove attachment"
					>
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
							<line x1="18" y1="6" x2="6" y2="18"></line>
							<line x1="6" y1="6" x2="18" y2="18"></line>
						</svg>
					</button>
				</div>
			</div>
		</div>
	);
};

export const DocumentPanel: ComponentType<any> = ({ }) => {
	const state = useAttachment();
	const attachmentsRuntime = useAttachmentRuntime();
	return (
		<div className="relative group flex items-center gap-2 p-3 hover:bg-gray-700/30 rounded-md transition-colors w-full max-w-[200px]">
			<div className="w-10 h-10 flex items-center justify-center bg-gray-700 rounded">
				<span className="text-xs">DOC</span>
			</div>
			<div className="flex-1 min-w-0">
				<div className="text-sm truncate" title={state.file?.name || 'Document'}>
					{state.file?.name || 'Document'}
				</div>
			</div>
			<div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
				<button
					onClick={() => attachmentsRuntime.remove()}
					className="p-1 rounded-full bg-gray-800/80 hover:bg-gray-700 text-gray-300"
					aria-label="Remove attachment"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
		</div>
	);
};

export const FilePanel: ComponentType<any> = ({ file }) => {
	const state = useAttachment();
	const attachmentsRuntime = useAttachmentRuntime();
	return (
		<div className="relative group flex items-center gap-2 p-3 hover:bg-gray-700/30 rounded-md transition-colors w-full max-w-[200px]">
			<div className="w-10 h-10 flex items-center justify-center bg-gray-700 rounded">
				<span className="text-xs">FILE</span>
			</div>
			<div className="flex-1 min-w-0">
				<div className="text-sm truncate" title={state.file?.name || 'File'}>
					{state.file?.name || 'File'}
				</div>
			</div>
			<div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity">
				<button
					onClick={() => attachmentsRuntime.remove()}
					className="p-1 rounded-full bg-gray-800/80 hover:bg-gray-700 text-gray-300"
					aria-label="Remove attachment"
				>
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
		</div>
	);
};

export const ChatComposer: FC<ChatComposerProps> = (
	props: ChatComposerProps,
) => {
	const isEmpty = props.messages.length === 0;

	return (
		<>
			<ComposerPrimitive.Root
				className={cn(
					"focus-within:border-aui-ring/20 flex w-full items-center md:justify-left justify-center rounded-lg border px-2.5 py-2.5 shadow-sm transition-all duration-300 ease-in-out bg-[#282828] border-gray-600",
					isEmpty ? "" : "md:ml-24 ml-3 mb-6",
					isEmpty ? "w-full" : "md:w-[70%] w-[95%] md:max-w-[832px]",
				)}
			>

				<ComposerPrimitive.Input
					autoFocus
					placeholder="How can I..."
					rows={1}
					className="placeholder:text-gray-400 text-gray-100 max-h-40 flex-1 resize-none border-none bg-transparent px-2 py-2 text-sm outline-none focus:ring-0 disabled:cursor-not-allowed"
				/>
				<div className="flex-shrink-0">
					<ThreadPrimitive.If running={false} >
						<ComposerPrimitive.AddAttachment asChild>
							<TooltipIconButton
								tooltip="Add Attachments"
								variant="default"
								// className="my-1 size-8 p-2 transition-opacity ease-in hover:bg-gray-700/50 rounded-full"
								className="my-1 size-8 p-2 transition-opacity ease-in"
							>
								<PaperclipIcon />
							</TooltipIconButton>
						</ComposerPrimitive.AddAttachment>
					</ThreadPrimitive.If>
					<ThreadPrimitive.If running={false} disabled={props.submitDisabled}>
						<ComposerPrimitive.Send asChild>
							<TooltipIconButton
								tooltip="Send"
								variant="default"
								className="my-1 size-8 p-2 transition-opacity ease-in"
							>
								<SendHorizontalIcon />
							</TooltipIconButton>
						</ComposerPrimitive.Send>
					</ThreadPrimitive.If>
					<ThreadPrimitive.If running>
						<ComposerPrimitive.Cancel asChild>
							<TooltipIconButton
								tooltip="Cancel"
								variant="default"
								className="my-1 size-8 p-2 transition-opacity ease-in"
							>
								<CircleStopIcon />
							</TooltipIconButton>
						</ComposerPrimitive.Cancel>
					</ThreadPrimitive.If>
				</div>

			</ComposerPrimitive.Root>
			<div className="flex flex-wrap gap-2 p-2 max-h-[200px] overflow-y-auto w-full">
				<ComposerPrimitive.Attachments
					components={{
						Image: ImagePanel,
						Document: DocumentPanel,
						File: FilePanel,
						Attachment: FilePanel,
					}}
				/>
			</div>
		</>
	);
};
