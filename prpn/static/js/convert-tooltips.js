
function convertTooltip(node) {
  new bootstrap.Tooltip(node);
}

function convertAllTooltips() {
  var nodes = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  Array.prototype.forEach.call(nodes, convertTooltip);
}

window.addEventListener('load', convertAllTooltips);
