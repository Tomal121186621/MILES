window.MathJax = {
  loader: { load: ["[tex]/boldsymbol", "[tex]/ams"] },
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
    packages: { "[+]": ["boldsymbol", "ams"] }
  },
  options: { ignoreHtmlClass: ".*|", processHtmlClass: "arithmatex" }
};
document$.subscribe(() => {
  if (MathJax.startup && MathJax.typesetPromise) {
    MathJax.startup.output.clearCache && MathJax.startup.output.clearCache();
    MathJax.typesetClear && MathJax.typesetClear();
    MathJax.texReset && MathJax.texReset();
    MathJax.typesetPromise();
  }
});
