"""The site's pages, by page type (MMS-776): tools/build_site.py builds them.

  common       paths, the documents in work, labels, prose, what is loaded once
  model        a section as the site shows it (SectionView), L4's rendering
  layout       the page shell and the navigation tree
  documents    a document's pages, its sections, a collection's page
  home         index.html
  findings     findings.html
  sources      calculator.html, contradictions.html, laws/, findings.json
  checks       index.json, diagnostics.html, coverage.html
  conventions  conventions.html

Each module imports the ones listed above it and none below it.
"""
