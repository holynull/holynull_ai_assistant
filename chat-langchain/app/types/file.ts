// types/file.ts

export interface UploadedImageFile {
	id: string;
	file: File;
	previewUrl: string;
	base64: string;
}

export interface UploadedImageUrl {
	id: string;
	url: string;
	base64: string;
}

export interface UploadedPDFFile {
	id: string;
	file: File;
	name: string;
	size: number;
	base64: string;
}

// 如果有其他相关的类型定义也可以放在这里
export interface FileUploadState {
	imageFiles: UploadedImageFile[];
	imageUrls: UploadedImageUrl[];
	pdfFiles: UploadedPDFFile[];
}

