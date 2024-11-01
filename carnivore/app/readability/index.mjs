import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

// Read HTML content from stdin
let html = '';

process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  html += chunk;
});

process.stdin.on('end', () => {
  if (!html) {
    console.error('No HTML content provided.');
    process.exit(1);
  }

  // Parse the HTML content
  const doc = new JSDOM(html);
  const reader = new Readability(doc.window.document);
  const article = reader.parse();

  if (!article) {
    console.error('Failed to parse the article.');
    process.exit(1);
  }

  // Output the HTML content and metadata to stdout
  console.log(JSON.stringify({
    html: article.content,
    metadata: {
      title: article.title,
      byline: article.byline,
      length: article.length,
      excerpt: article.excerpt,
      siteName: article.siteName,
    }
  }));
});
