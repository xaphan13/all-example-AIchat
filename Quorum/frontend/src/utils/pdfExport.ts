/**
 * PDF Export Utility
 * Exports message content to PDF format
 */
import { jsPDF } from 'jspdf';

export interface ExportPDFOptions {
  title?: string;
  author?: string;
  subject?: string;
}

/**
 * Exports text content to PDF
 * Handles markdown formatting by converting to plain text
 */
export function exportToPDF(
  content: string,
  filename: string = 'executive-summary.pdf',
  options: ExportPDFOptions = {}
): void {
  try {
    // Create new PDF document
    const doc = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });

    // Set document properties
    if (options.title) doc.setProperties({ title: options.title });
    if (options.author) doc.setProperties({ creator: options.author });
    if (options.subject) doc.setProperties({ subject: options.subject });

    // PDF dimensions
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 20;
    const maxWidth = pageWidth - 2 * margin;
    const lineHeight = 7;
    const maxLinesPerPage = Math.floor((pageHeight - 2 * margin) / lineHeight);

    // Clean markdown formatting for better PDF rendering
    let cleanedContent = content
      // Remove markdown headers but keep the text
      .replace(/^#{1,6}\s+/gm, '')
      // Remove bold/italic markers
      .replace(/\*\*\*(.*?)\*\*\*/g, '$1')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/\_\_(.*?)\_\_/g, '$1')
      .replace(/\_(.*?)\_/g, '$1')
      // Remove code blocks
      .replace(/```[\s\S]*?```/g, '[Code Block]')
      .replace(/`([^`]+)`/g, '$1')
      // Remove links but keep text
      .replace(/\[([^\]]+)\]\([^\)]+\)/g, '$1')
      // Clean up extra whitespace
      .replace(/\n{3,}/g, '\n\n')
      .trim();

    // Add title
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text(options.title || 'Executive Summary', margin, margin);

    // Add timestamp
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    const timestamp = new Date().toLocaleString();
    doc.text(`Generated: ${timestamp}`, margin, margin + 7);

    // Add separator line
    doc.setLineWidth(0.5);
    doc.line(margin, margin + 12, pageWidth - margin, margin + 12);

    // Add content
    doc.setFontSize(11);
    doc.setFont('helvetica', 'normal');

    let yPosition = margin + 20;
    const lines = doc.splitTextToSize(cleanedContent, maxWidth);
    let currentPage = 1;
    let lineCount = 0;

    for (let i = 0; i < lines.length; i++) {
      if (lineCount >= maxLinesPerPage) {
        // Add new page
        doc.addPage();
        currentPage++;
        yPosition = margin;
        lineCount = 0;
      }

      doc.text(lines[i], margin, yPosition);
      yPosition += lineHeight;
      lineCount++;
    }

    // Add page numbers
    const totalPages = currentPage;
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.text(
        `Page ${i} of ${totalPages}`,
        pageWidth / 2,
        pageHeight - 10,
        { align: 'center' }
      );
    }

    // Save the PDF
    doc.save(filename);
  } catch (error) {
    console.error('Error exporting to PDF:', error);
    throw new Error('Failed to export PDF. Please try again.');
  }
}

/**
 * Generate a filename for the PDF based on timestamp and content
 */
export function generatePDFFilename(prefix: string = 'summary'): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  return `${prefix}-${timestamp}.pdf`;
}

