// Type definitions for ChatGPT Apps SDK window.openai API

export interface OpenAiGlobals {
  // Tool data
  toolInput: Record<string, unknown>;
  toolOutput: ToolOutput;
  toolResponseMetadata: Record<string, unknown>;

  // Widget state
  widgetState: WidgetState | null;

  // Environment
  theme: 'light' | 'dark';
  displayMode: 'inline' | 'pip' | 'fullscreen';
  maxHeight: number;
  safeArea: { top: number; bottom: number; left: number; right: number };
  view: 'mobile' | 'desktop';
  userAgent: string;
  locale: string;
}

export interface ToolOutput {
  file_id?: string;
  page_count?: number;
  boxes?: DetectedBox[];
  total_boxes?: number;
  processed_file_id?: string;
  replaced_count?: number;
  error?: string;
  [key: string]: unknown;
}

export interface DetectedBox {
  x: number;
  y: number;
  width: number;
  height: number;
  page?: number;
}

export interface WidgetState {
  phase: 'upload' | 'detecting' | 'results' | 'processing' | 'compare';
  originalFileId?: string;
  processedFileId?: string;
  detectedBoxes?: DetectedBox[];
  replacementText?: string;
  pageCount?: number;
  currentPage?: number;
  [key: string]: unknown;
}

export interface FileUploadResult {
  fileId: string;
}

export interface FileDownloadResult {
  downloadUrl: string;
}

export interface OpenAiApi extends OpenAiGlobals {
  // Methods
  setWidgetState: (state: WidgetState) => void;
  callTool: (name: string, args: Record<string, unknown>) => Promise<void>;
  sendFollowUpMessage: (options: { prompt: string }) => Promise<void>;
  uploadFile: (file: File) => Promise<FileUploadResult>;
  getFileDownloadUrl: (options: { fileId: string }) => Promise<FileDownloadResult>;
  requestDisplayMode: (options: { mode: 'inline' | 'pip' | 'fullscreen' }) => Promise<void>;
  requestClose: () => void;
  notifyIntrinsicHeight: (height: number) => void;
  openExternal: (options: { href: string }) => void;
}

declare global {
  interface Window {
    openai: OpenAiApi;
  }
}
