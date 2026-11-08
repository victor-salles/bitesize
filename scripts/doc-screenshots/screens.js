// What capture.js shoots. Edit this list, not the script, when a screen changes.

// Dashboard tabs, shot at a laptop viewport against a dashboard with an empty data/ folder.
const dashboard = [
  { file: 'dashboard-settings.png', tab: 'settings' },
  { file: 'dashboard-sources.png', tab: 'sources' },
  { file: 'dashboard-jev.png', tab: 'jev' },
  { file: 'dashboard-kindle.png', tab: 'kindle' },
];

// Pages of the demo EPUB, shown on a Kindle-sized screen. Paths are inside the unzipped book.
const book = [
  { file: 'book-library-cover.png', page: 'EPUB/cover.jpg', caption: 'Library cover' },
  { file: 'book-cover.png', page: 'EPUB/cover.xhtml', caption: 'Edition cover' },
  { file: 'book-section.png', page: 'EPUB/cover_tecnologia.xhtml', caption: 'Section cover' },
  { file: 'book-index.png', page: 'EPUB/index_tecnologia.xhtml', caption: 'Section index' },
  { file: 'book-article.png', page: 'EPUB/article_tecnologia_01.xhtml', caption: 'Article' },
];

module.exports = { dashboard, book };
