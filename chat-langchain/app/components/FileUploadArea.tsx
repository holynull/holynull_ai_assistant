// FileUploadArea.tsx
import React, { useState, useCallback, useEffect } from 'react';
import {
	Box,
	Button,
	Flex,
	Grid,
	Icon,
	IconButton,
	Image,
	Input,
	InputGroup,
	InputRightElement,
	Select,
	Spinner,
	Text,
	VStack,
	Center,
	Tooltip,
	AspectRatio,
	Modal,
	ModalOverlay,
	ModalContent,
	ModalHeader,
	ModalBody,
	ModalCloseButton,
	ButtonGroup,
	useDisclosure,
	chakra,
	keyframes,
} from '@chakra-ui/react';
import {
	CloseIcon,
	DeleteIcon,
	ChevronLeftIcon,
	ChevronRightIcon,
} from '@chakra-ui/icons';
import {
	FaUpload,
	FaFilePdf,
	FaEye,
	FaTimes,
	FaImage,
} from 'react-icons/fa';
import { Document, Page, pdfjs } from 'react-pdf';

// PDF.js worker配置
if (typeof window !== "undefined") {
	pdfjs.GlobalWorkerOptions.workerSrc = `//cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js`;
}

// 类型定义
interface UploadedImageFile {
	id: string;
	file: File;
	previewUrl: string;
	base64: string;
}

interface UploadedImageUrl {
	id: string;
	url: string;
	base64: string;
}

interface UploadedPDFFile {
	id: string;
	file: File;
	name: string;
	size: number;
	base64: string;
}

interface FileUploadAreaProps {
	imageFiles: UploadedImageFile[];
	imageUrls: UploadedImageUrl[];
	pdfFiles: UploadedPDFFile[];
	onImageFilesChange: (files: UploadedImageFile[]) => void;
	onImageUrlsChange: (urls: UploadedImageUrl[]) => void;
	onPdfFilesChange: (files: UploadedPDFFile[]) => void;
	maxFiles?: number;
	maxFileSize?: number;
	show: boolean;
	onClose: () => void;
}

interface PDFPreviewModalProps {
	isOpen: boolean;
	onClose: () => void;
	pdfUrl: string;
}

// 动画定义
const fadeIn = keyframes`
    from { opacity: 0; }
    to { opacity: 1; }
`;

const slideIn = keyframes`
    from { transform: translateY(10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
`;

// 样式常量
const styles = {
	container: {
		position: 'relative' as const,
		width: '100%', // 确保容器占满可用宽度
		minWidth: '500px', // 设置最小宽度
		maxWidth: '800px', // 设置最大宽度，避免过宽
		margin: '0 auto', // 水平居中
		marginBottom: 2,
		backgroundColor: '#131318',  // 更新背景色以匹配
		borderRadius: 'xl',  // 增加圆角
		p: 4,
		color: 'white',
		zIndex: 1000,
		boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
		border: '1px solid',
		borderColor: 'whiteAlpha.200',
	},
	dropzone: {
		transition: 'all 0.3s ease',
		border: '2px dashed',
		borderRadius: 'lg',
		marginTop: '1em',
		padding: 6,
		textAlign: 'center' as const,
		minHeight: '200px',
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
		backgroundColor: 'whiteAlpha.50',
	},
	preview: {
		aspectRatio: '1',
		objectFit: 'cover' as const,
		width: '100%',
		height: '100%',
	},
	previewContainer: {
		position: 'relative' as const,
		borderRadius: 'md',
		overflow: 'hidden',
		backgroundColor: 'whiteAlpha.100',
		border: '1px solid',
		borderColor: 'whiteAlpha.200',
		transition: 'all 0.2s',
		_hover: {
			transform: 'translateY(-2px)',
			shadow: 'lg',
			borderColor: 'blue.400',
		},
	},
	closeButton: {
		position: 'absolute' as const,
		top: 1,
		right: 1,
		backgroundColor: 'blackAlpha.600',
		_hover: { backgroundColor: 'blackAlpha.800' },
	},
	grid: {
		'&::-webkit-scrollbar': {
			width: '4px',
		},
		'&::-webkit-scrollbar-track': {
			background: 'rgba(0, 0, 0, 0.1)',
		},
		'&::-webkit-scrollbar-thumb': {
			background: 'rgba(255, 255, 255, 0.2)',
			borderRadius: '2px',
		},
	},
};

// 动画组件
const AnimatedBox = chakra(Box, {
	baseStyle: {
		animation: `${fadeIn} 0.3s ease-out`,
	},
});

const AnimatedGrid = chakra(Grid, {
	baseStyle: {
		animation: `${slideIn} 0.3s ease-out`,
	},
});

// 辅助组件
const ErrorMessage: React.FC<{ message: string }> = ({ message }) => (
	<Text color="red.400" fontSize="sm" mt={2}>
		{message}
	</Text>
);

const LoadingOverlay: React.FC = () => (
	<Center
		position="absolute"
		top={0}
		left={0}
		right={0}
		bottom={0}
		bg="blackAlpha.700"
		zIndex={2}
	>
		<Spinner color="white" />
	</Center>
);

// PDF预览模态框组件
const PDFPreviewModal: React.FC<PDFPreviewModalProps> = ({ isOpen, onClose, pdfUrl }) => {
	const [numPages, setNumPages] = useState<number | null>(null);
	const [pageNumber, setPageNumber] = useState(1);

	const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
		setNumPages(numPages);
	};

	return (
		<Modal isOpen={isOpen} onClose={onClose} size="xl">
			<ModalOverlay />
			<ModalContent bg="#1A1A1A">
				<ModalHeader color="white">PDF Preview</ModalHeader>
				<ModalCloseButton color="white" />
				<ModalBody>
					<Center>
						<Document
							file={pdfUrl}
							onLoadSuccess={onDocumentLoadSuccess}
							options={{
								cMapUrl: 'cmaps/',
								cMapPacked: true,
							}}
						>
							<Page
								pageNumber={pageNumber}
								width={500}
								renderTextLayer={false}
								renderAnnotationLayer={false}
							/>
						</Document>
					</Center>
					{numPages && (
						<Flex justify="center" mt={4}>
							<ButtonGroup size="sm" isAttached variant="outline">
								<IconButton
									aria-label="Previous page"
									icon={<ChevronLeftIcon />}
									onClick={() => setPageNumber(Math.max(1, pageNumber - 1))}
									isDisabled={pageNumber <= 1}
								/>
								<Button>
									Page {pageNumber} of {numPages}
								</Button>
								<IconButton
									aria-label="Next page"
									icon={<ChevronRightIcon />}
									onClick={() => setPageNumber(Math.min(numPages!, pageNumber + 1))}
									isDisabled={pageNumber >= (numPages || 0)}
								/>
							</ButtonGroup>
						</Flex>
					)}
				</ModalBody>
			</ModalContent>
		</Modal>
	);
};

// 工具函数
const formatFileSize = (bytes: number): string => {
	if (bytes === 0) return '0 Bytes';
	const k = 1024;
	const sizes = ['Bytes', 'KB', 'MB', 'GB'];
	const i = Math.floor(Math.log(bytes) / Math.log(k));
	return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const validateFile = (file: File, maxSize: number): { isValid: boolean; error?: string } => {
	if (file.size > maxSize) {
		return {
			isValid: false,
			error: `File size exceeds ${formatFileSize(maxSize)} limit`
		};
	}

	if (!file.type.match(/^(image\/|application\/pdf)/)) {
		return {
			isValid: false,
			error: 'Only images and PDF files are allowed'
		};
	}

	return { isValid: true };
};

// 主组件
const FileUploadArea: React.FC<FileUploadAreaProps> = ({
	imageFiles,
	imageUrls,
	pdfFiles,
	onImageFilesChange,
	onImageUrlsChange,
	onPdfFilesChange,
	maxFiles = 100,
	maxFileSize = 10 * 1024 * 1024,
	show,
	onClose
}) => {
	const [isDragging, setIsDragging] = useState(false);
	const [uploadType, setUploadType] = useState<"file" | "url">("file");
	const [imageUrl, setImageUrl] = useState('');
	const [isConverting, setIsConverting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
	const { isOpen, onOpen, onClose: onModalClose } = useDisclosure();

	// 文件转Base64
	const convertToBase64 = (file: File): Promise<string> => {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.readAsDataURL(file);
			reader.onload = () => resolve(reader.result as string);
			reader.onerror = error => reject(error);
		});
	};

	// 清除所有文件
	const clearAllFiles = () => {
		imageFiles.forEach(img => URL.revokeObjectURL(img.previewUrl));
		onImageFilesChange([]);
		onImageUrlsChange([]);
		onPdfFilesChange([]);
		setError(null);
	};
	const close = () => {
		clearAllFiles();
		onClose();
	}

	// 拖拽事件处理
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
		setError(null);

		const files = Array.from(e.dataTransfer.files);
		const totalFiles = imageFiles.length + imageUrls.length + pdfFiles.length + files.length;

		if (totalFiles > maxFiles) {
			setError(`You can only upload up to ${maxFiles} files in total`);
			return;
		}
		let new_images: any[] = []
		let new_pdf: any[] = []
		for (const file of files) {
			const validation = validateFile(file, maxFileSize);
			if (!validation.isValid) {
				setError(validation.error || 'Invalid file');
				continue;
			}

			try {
				const base64 = await convertToBase64(file);

				if (file.type.startsWith('image/')) {
					const previewUrl = URL.createObjectURL(file);
					const newImageFile: UploadedImageFile = {
						id: Math.random().toString(),
						file: file,
						previewUrl: previewUrl,
						base64: base64
					};
					new_images = [...new_images, newImageFile]
				} else if (file.type === 'application/pdf') {
					const newPDFFile: UploadedPDFFile = {
						id: Math.random().toString(),
						file: file,
						name: file.name,
						size: file.size,
						base64: base64
					};
					new_pdf = [...new_pdf, newPDFFile]
				}
			} catch (error) {
				console.error("Error processing file:", error);
				setError("Error processing file. Please try again.");
			}
		}
		onImageFilesChange([...imageFiles, ...new_images])
		onPdfFilesChange([...pdfFiles, ...new_pdf])
	};

	// 文件上传处理
	const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
		const files = event.target.files;
		if (!files) return;

		const totalFiles = imageFiles.length + imageUrls.length + pdfFiles.length + files.length;
		if (totalFiles > maxFiles) {
			setError(`You can only upload up to ${maxFiles} files in total`);
			return;
		}
		let new_images: any[] = []
		let new_pdf: any[] = []
		for (let i = 0; i < files.length; i++) {
			const file = files[i];
			if (file.size > maxFileSize) {
				setError(`File ${file.name} exceeds ${maxFileSize / 1024 / 1024}MB limit`);
				continue;
			}

			try {
				const base64 = await convertToBase64(file);

				if (file.type.startsWith('image/')) {
					const previewUrl = URL.createObjectURL(file);
					const newImageFile: UploadedImageFile = {
						id: Math.random().toString(),
						file: file,
						previewUrl: previewUrl,
						base64: base64
					};
					new_images = [...new_images, newImageFile]
				} else if (file.type === 'application/pdf') {
					const newPDFFile: UploadedPDFFile = {
						id: Math.random().toString(),
						file: file,
						name: file.name,
						size: file.size,
						base64: base64
					};
					new_pdf = [...new_pdf, newPDFFile]
				}
			} catch (error) {
				console.error("Error processing file:", error);
				setError("Error processing file. Please try again.");
			}
		}
		onImageFilesChange([...imageFiles, ...new_images])
		onPdfFilesChange([...pdfFiles, ...new_pdf])

		// 清空input的value,允许重复上传相同文件
		event.target.value = '';
	};

	// URL上传处理
	const handleUrlSubmit = async () => {
		if (!imageUrl) return;
		setError(null);

		try {
			setIsConverting(true);
			const response = await fetch(imageUrl);
			const blob = await response.blob();

			if (!blob.type.startsWith('image/')) {
				setError('URL must point to an image file');
				return;
			}

			const base64 = await convertToBase64(blob as File);
			const newImageUrl: UploadedImageUrl = {
				id: Math.random().toString(),
				url: imageUrl,
				base64: base64
			};

			onImageUrlsChange([...imageUrls, newImageUrl]);
			setImageUrl('');
		} catch (error) {
			console.error("Error processing URL:", error);
			setError("Error processing URL. Please check the URL and try again.");
		} finally {
			setIsConverting(false);
		}
	};

	// 删除文件处理
	const removeImageFile = (id: string) => {
		const file = imageFiles.find(f => f.id === id);
		if (file) {
			URL.revokeObjectURL(file.previewUrl);
		}
		onImageFilesChange(imageFiles.filter(f => f.id !== id));
	};

	const removeImageUrl = (id: string) => {
		onImageUrlsChange(imageUrls.filter(u => u.id !== id));
	};

	const removePdfFile = (id: string) => {
		onPdfFilesChange(pdfFiles.filter(f => f.id !== id));
	};

	// 键盘事件处理
	const handleKeyPress = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter' && uploadType === 'url') {
			handleUrlSubmit();
		}
	};

	// 清理effect
	useEffect(() => {
		return () => {
			// 组件卸载时清理预览URL
			imageFiles.forEach(img => {
				if (img.previewUrl) {
					URL.revokeObjectURL(img.previewUrl);
				}
			});
		};
	}, [imageFiles]);
	const DropzoneContent = () => (
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
					isDisabled={imageFiles.length + imageUrls.length + pdfFiles.length >= maxFiles}
				>
					Choose Files
				</Button>
			</Box>
			<Text fontSize="sm" color="gray.400" textAlign="center">
				{`${imageFiles.length + imageUrls.length + pdfFiles.length}/${maxFiles} files uploaded`}
			</Text>
			<Text fontSize="sm" color="gray.400">
				Supports: JPG, PNG, GIF, WEBP (Max 5MB) | PDF (Max 10MB)
			</Text>
		</VStack>
	);
	// 在FileUploadArea组件中添加粘贴处理
	useEffect(() => {
		const handlePaste = async (e: ClipboardEvent) => {
			const items = e.clipboardData?.items;
			if (!items) return;

			for (const item of Array.from(items)) {
				if (item.type.startsWith('image/')) {
					e.preventDefault();

					const file = item.getAsFile();
					if (!file) continue;

					const totalFiles = imageFiles.length + imageUrls.length + pdfFiles.length;
					if (totalFiles >= maxFiles) {
						setError(`You can only upload up to ${maxFiles} files in total`);
						return;
					}

					if (file.size > maxFileSize) {
						setError(`File exceeds ${formatFileSize(maxFileSize)} limit`);
						return;
					}

					try {
						const previewUrl = URL.createObjectURL(file);
						const base64 = await convertToBase64(file);
						const newImageFile: UploadedImageFile = {
							id: Math.random().toString(),
							file: file,
							previewUrl: previewUrl,
							base64: base64
						};

						onImageFilesChange([...imageFiles, newImageFile]);
						console.log('Image pasted successfully');
					} catch (error) {
						console.error("Error handling pasted image:", error);
						setError("Error processing pasted image");
					}
				}
			}
		};

		document.addEventListener('paste', handlePaste);
		return () => document.removeEventListener('paste', handlePaste);
	}, [imageFiles, imageUrls, pdfFiles, maxFiles, maxFileSize]);
	return show && (
		<Box {...styles.container}>
			<Flex justifyContent="space-between" mb={4}>
				<Select
					value={uploadType}
					onChange={(e) => setUploadType(e.target.value as "file" | "url")}
					width="240px"  // 增加宽度
					variant="filled"
					bg="whiteAlpha.50"
					borderColor="whiteAlpha.200"
					color="white"
					_hover={{
						borderColor: "whiteAlpha.400",
						bg: "whiteAlpha.100"
					}}
					_focus={{
						borderColor: "blue.500",
						bg: "whiteAlpha.100"
					}}
				>
					<option value="file">Upload File</option>
					<option value="url">Image URL</option>
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
					onClick={close}
					transition="all 0.2s"
					borderRadius="full"
					boxShadow="md"
				/>
			</Flex>


			{error && (
				<ErrorMessage message={error} />
			)}

			{(imageFiles.length > 0 || imageUrls.length > 0 || pdfFiles.length > 0) && (
				<Box mt={4}>
					<Flex justifyContent="space-between" alignItems="center" mb={2}>
						<Text fontSize="sm">
							{imageFiles.length + imageUrls.length + pdfFiles.length} file(s) selected
						</Text>
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

					<AnimatedGrid
						templateColumns={{
							base: "repeat(auto-fill, minmax(100px, 1fr))",
							sm: "repeat(auto-fill, minmax(120px, 1fr))",
							md: "repeat(auto-fill, minmax(150px, 1fr))"
						}}
						gap={2}
						maxH="300px"
						overflowY="auto"
						mt={4}
						{...styles.grid}
					>
						{/* 图片文件预览 */}
						{imageFiles.map((file) => (
							<Box
								key={file.id}
								{...styles.previewContainer}
							>
								<AspectRatio ratio={1}>
									<Image
										src={file.previewUrl}
										alt={file.file.name}
										objectFit="cover"
									/>
								</AspectRatio>
								<IconButton
									aria-label="Remove image"
									icon={<FaTimes />}
									size="xs"
									{...styles.closeButton}
									onClick={() => removeImageFile(file.id)}
								/>
								<Text
									fontSize="xs"
									position="absolute"
									bottom={0}
									left={0}
									right={0}
									bg="blackAlpha.600"
									p={1}
									textAlign="center"
									isTruncated
								>
									{file.file.name}
								</Text>
							</Box>
						))}

						{/* URL图片预览 */}
						{imageUrls.map((item) => (
							<Box
								key={item.id}
								{...styles.previewContainer}
							>
								<AspectRatio ratio={1}>
									<Image
										src={item.url}
										alt="URL Image"
										objectFit="cover"
									/>
								</AspectRatio>
								<IconButton
									aria-label="Remove image"
									icon={<FaTimes />}
									size="xs"
									{...styles.closeButton}
									onClick={() => removeImageUrl(item.id)}
								/>
							</Box>
						))}

						{/* PDF文件预览 */}
						{pdfFiles.map((file) => (
							<Box
								key={file.id}
								{...styles.previewContainer}
							>
								<AspectRatio ratio={1}>
									<Center bg="gray.700" position="relative">
										<Icon as={FaFilePdf} w={8} h={8} color="red.400" />
										<Tooltip label="Preview PDF">
											<IconButton
												aria-label="Preview PDF"
												icon={<FaEye />}
												size="sm"
												position="absolute"
												bottom={2}
												left="50%"
												transform="translateX(-50%)"
												onClick={() => {
													setSelectedPdf(file.base64);
													onOpen();
												}}
												bg="blackAlpha.600"
												_hover={{ bg: "blackAlpha.800" }}
											/>
										</Tooltip>
									</Center>
								</AspectRatio>
								<IconButton
									aria-label="Remove PDF"
									icon={<FaTimes />}
									size="xs"
									{...styles.closeButton}
									onClick={() => removePdfFile(file.id)}
								/>
								<Text
									fontSize="xs"
									position="absolute"
									bottom={0}
									left={0}
									right={0}
									bg="blackAlpha.600"
									p={1}
									textAlign="center"
									isTruncated
								>
									{file.name}
								</Text>
							</Box>
						))}
					</AnimatedGrid>
				</Box>
			)}

			{/* PDF预览模态框 */}
			{selectedPdf && (
				<PDFPreviewModal
					isOpen={isOpen}
					onClose={() => {
						onModalClose();
						setSelectedPdf(null);
					}}
					pdfUrl={selectedPdf}
				/>
			)}
			{uploadType === "file" ? (
				<Box
					onDragEnter={handleDragEnter}
					onDragLeave={handleDragLeave}
					onDragOver={handleDragOver}
					onDrop={handleDrop}
					{...styles.dropzone}
					borderColor={isDragging ? "blue.400" : "whiteAlpha.300"}
					bg={isDragging ? "whiteAlpha.100" : "transparent"}
				>
					<DropzoneContent />
				</Box>
			) : (
				<InputGroup size="md">
					<Input
						value={imageUrl}
						onChange={(e) => setImageUrl(e.target.value)}
						onKeyPress={handleKeyPress}
						placeholder="Enter image URL"
						pr="4.5rem"
						bg="whiteAlpha.100"
						border="1px solid"
						borderColor="whiteAlpha.300"
						_hover={{ borderColor: "whiteAlpha.400" }}
					/>
					<InputRightElement width="4.5rem">
						<Button
							h="1.75rem"
							size="sm"
							onClick={handleUrlSubmit}
							isLoading={isConverting}
						>
							Add
						</Button>
					</InputRightElement>
				</InputGroup>
			)}

		</Box>
	);
};

// 导出组件
export default FileUploadArea;

// 导出常量配置
export const FILE_UPLOAD_CONSTANTS = {
	maxFileSize: 10 * 1024 * 1024, // 10MB
	maxFiles: 100,
	acceptedFileTypes: "image/*,application/pdf",
	gridMinWidth: "100px",
	maxPreviewHeight: "300px",
};