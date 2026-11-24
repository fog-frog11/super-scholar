"use client";

import JSZip from "jszip";
import * as XLSX from "xlsx";
import * as mammoth from "mammoth";
import { normalizeText } from "./utils";
import type { MaterialAnalysis, MaterialKind } from "./types";

type Progress = (analysis: Partial<MaterialAnalysis>) => void;

const TEXT_EXTENSIONS = new Set([
  "txt", "md", "tex", "bib", "py", "js", "jsx", "ts", "tsx", "java", "c", "cc", "cpp", "h", "hpp", "rs", "go", "rb", "php", "swift", "kt", "kts", "scala", "sh", "bash", "zsh", "yaml", "yml", "json", "toml", "ini", "cfg", "sql", "r", "m", "html", "css", "scss", "xml"
]);

const CODE_EXTENSIONS = new Set(["py", "js", "jsx", "ts", "tsx", "java", "c", "cc", "cpp", "h", "hpp", "rs", "go", "rb", "php", "swift", "kt", "kts", "scala", "sh", "sql", "r", "m"]);

export function fileExtension(name: string) {
  return name.toLowerCase().split(".").pop() ?? "";
}

export function inferMaterialKind(file: File): MaterialKind {
  const ext = fileExtension(file.name);
  if (["pdf", "docx", "tex", "md", "txt"].includes(ext)) return "manuscript";
  if (["zip"].includes(ext) || CODE_EXTENSIONS.has(ext)) return "source";
  if (["csv", "xlsx", "xls", "tsv"].includes(ext)) return "data";
  if (file.type.startsWith("image/") || ["png", "jpg", "jpeg", "webp", "gif"].includes(ext)) return "image";
  return "other";
}

async function parsePdf(file: Blob, onProgress: Progress) {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
  const data = await file.arrayBuffer();
  const task = pdfjs.getDocument({ data });
  const pdf = await task.promise;
  const chunks: string[] = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const text = content.items
      .map((item) => ("str" in item ? item.str : ""))
      .join(" ");
    chunks.push(text);
    onProgress({
      status: "parsing",
      progress: 12 + Math.round((i / pdf.numPages) * 65),
      stage: "pdf_pages",
      message: `正在读取 PDF 第 ${i} / ${pdf.numPages} 页`,
      pages: pdf.numPages
    });
  }
  return { text: normalizeText(chunks.join("\n\n")), pages: pdf.numPages };
}

async function parseDocx(file: Blob, onProgress: Progress) {
  onProgress({ status: "parsing", progress: 28, stage: "docx_xml", message: "正在解析 DOCX 文档结构" });
  const arrayBuffer = await file.arrayBuffer();
  const result = await mammoth.extractRawText({ arrayBuffer });
  onProgress({ status: "parsing", progress: 76, stage: "docx_text", message: "DOCX 正文已提取" });
  return { text: normalizeText(result.value) };
}

async function parseSpreadsheet(file: Blob, extension: string, onProgress: Progress) {
  onProgress({ status: "parsing", progress: 24, stage: "workbook", message: "正在读取表格工作簿" });
  const arrayBuffer = await file.arrayBuffer();
  const workbook = XLSX.read(arrayBuffer, { type: "array", cellDates: true });
  let rows = 0;
  const textParts: string[] = [];
  for (let i = 0; i < workbook.SheetNames.length; i++) {
    const name = workbook.SheetNames[i];
    const sheet = workbook.Sheets[name];
    const csv = XLSX.utils.sheet_to_csv(sheet, { blankrows: false });
    const nonEmpty = csv.split(/\r?\n/).filter(Boolean);
    rows += Math.max(0, nonEmpty.length - 1);
    textParts.push(`[Sheet: ${name}]\n${csv}`);
    onProgress({
      status: "parsing",
      progress: 24 + Math.round(((i + 1) / workbook.SheetNames.length) * 52),
      stage: "sheets",
      message: `正在读取表格 ${i + 1} / ${workbook.SheetNames.length}`,
      sheets: workbook.SheetNames.length,
      rows
    });
  }
  return { text: normalizeText(textParts.join("\n\n")), sheets: workbook.SheetNames.length, rows, extension };
}

async function parseZip(file: Blob, onProgress: Progress) {
  onProgress({ status: "parsing", progress: 20, stage: "archive", message: "正在打开 ZIP 归档" });
  const zip = await JSZip.loadAsync(file);
  const entries = (Object.values(zip.files) as Array<{ dir: boolean; name: string; async(type: "string"): Promise<string> }>).filter((entry) => !entry.dir);
  const readable = entries.filter((entry) => TEXT_EXTENSIONS.has(fileExtension(entry.name)));
  const textParts: string[] = [];
  let codeFiles = 0;
  const maxCharsPerFile = 120_000;
  const maxTotalChars = 1_500_000;
  let totalChars = 0;

  for (let i = 0; i < readable.length; i++) {
    const entry = readable[i];
    const ext = fileExtension(entry.name);
    if (CODE_EXTENSIONS.has(ext)) codeFiles += 1;
    let text = await entry.async("string");
    if (text.length > maxCharsPerFile) text = text.slice(0, maxCharsPerFile);
    if (totalChars + text.length > maxTotalChars) {
      text = text.slice(0, Math.max(0, maxTotalChars - totalChars));
    }
    if (text) {
      textParts.push(`[File: ${entry.name}]\n${text}`);
      totalChars += text.length;
    }
    onProgress({
      status: "parsing",
      progress: 20 + Math.round(((i + 1) / Math.max(1, readable.length)) * 58),
      stage: "archive_files",
      message: `正在读取归档文件 ${i + 1} / ${readable.length}`,
      codeFiles
    });
    if (totalChars >= maxTotalChars) break;
  }

  return { text: normalizeText(textParts.join("\n\n")), codeFiles };
}

async function parseImage(file: Blob, onProgress: Progress) {
  onProgress({ status: "parsing", progress: 45, stage: "image_metadata", message: "正在读取图片元数据" });
  let result: { width: number; height: number };
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(file);
    result = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
  } else {
    result = await new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const image = new Image();
      image.onload = () => { URL.revokeObjectURL(url); resolve({ width: image.naturalWidth, height: image.naturalHeight }); };
      image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("浏览器无法读取该图片格式。")); };
      image.src = url;
    });
  }
  onProgress({ status: "parsing", progress: 78, stage: "image_metadata", message: "图片尺寸已读取", imageWidth: result.width, imageHeight: result.height });
  return { text: "", ...result };
}

function countDocumentSignals(text: string) {
  const lower = text.toLowerCase();
  const headings = text.match(/(?:^|\n)\s*(?:\d+(?:\.\d+)*\s+)?(?:abstract|introduction|related work|background|method(?:ology)?|experiments?|results?|discussion|conclusion|references|摘要|引言|相关工作|方法|实验|结果|讨论|结论|参考文献)\b/gim) ?? [];
  const references = text.match(/(?:\[\d+\]|\(\w+(?: et al\.)?,?\s*20\d{2}\))/g) ?? [];
  const figures = text.match(/(?:figure|fig\.|图)\s*\d+/gi) ?? [];
  return {
    sections: new Set(headings.map((x) => x.trim().toLowerCase())).size,
    references: Math.min(references.length, 5000),
    figures: Math.min(figures.length, 1000),
    hasAbstract: lower.includes("abstract") || text.includes("摘要")
  };
}

export async function parseMaterialFile(file: Blob & { name?: string; type?: string }, onProgress: Progress) {
  const name = file.name ?? "material";
  const ext = fileExtension(name);
  onProgress({ status: "reading", progress: 8, stage: "read", message: "材料已进入浏览器本地解析流程" });

  let parsed: { text: string; pages?: number; sheets?: number; rows?: number; codeFiles?: number; width?: number; height?: number };
  if (ext === "pdf") parsed = await parsePdf(file, onProgress);
  else if (ext === "docx") parsed = await parseDocx(file, onProgress);
  else if (["xlsx", "xls", "csv", "tsv"].includes(ext)) parsed = await parseSpreadsheet(file, ext, onProgress);
  else if (ext === "zip") parsed = await parseZip(file, onProgress);
  else if ((file.type ?? "").startsWith("image/") || ["png", "jpg", "jpeg", "webp", "gif"].includes(ext)) parsed = await parseImage(file, onProgress);
  else if (TEXT_EXTENSIONS.has(ext) || (file.type ?? "").startsWith("text/")) {
    onProgress({ status: "parsing", progress: 38, stage: "plain_text", message: "正在读取文本内容" });
    parsed = { text: normalizeText(await file.text()) };
    onProgress({ status: "parsing", progress: 78, stage: "plain_text", message: "文本内容已读取" });
  } else {
    throw new Error(`暂不支持解析 .${ext || "unknown"} 文件。可保留该材料，但无法提取文本。`);
  }

  onProgress({ status: "understanding", progress: 84, stage: "document_signals", message: "正在提取文档结构与研究信号" });
  const signals = countDocumentSignals(parsed.text);
  onProgress({ status: "indexing", progress: 94, stage: "local_index", message: "正在写入本地研究索引" });

  return {
    text: parsed.text,
    analysis: {
      status: "ready" as const,
      progress: 100,
      stage: "ready",
      message: "解析完成",
      pages: parsed.pages,
      sheets: parsed.sheets,
      rows: parsed.rows,
      codeFiles: parsed.codeFiles,
      imageWidth: parsed.width,
      imageHeight: parsed.height,
      sections: signals.sections,
      references: signals.references,
      figures: signals.figures,
      textChars: parsed.text.length
    }
  };
}
