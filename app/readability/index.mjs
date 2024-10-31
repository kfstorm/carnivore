import fetch from 'node-fetch';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

// Get the URL from the command line arguments
const [,, url] = process.argv;

if (!url) {
  console.error('Please provide a URL as a command line argument.');
  process.exit(1);
}

(async () => {
  try {
    // Fetch the HTML content from the URL
    const response = await fetch(url);
    const html = await response.text();

    // Parse the HTML content
    const doc = new JSDOM(html, { url });
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
  } catch (error) {
    console.error('Error fetching the URL:', error);
    process.exit(1);
  }
})();
