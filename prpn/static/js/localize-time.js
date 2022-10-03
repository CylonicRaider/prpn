// BEFORE: convert-tooltips.js

function leftpad(string, length, fill) {
  string = String(string);
  while (string.length < length) string = fill + string;
  return string;
}

function formatLocalDateTime(date) {
  function zpad(s, l) {
    return leftpad(s, l, '0');
  }
  return zpad(date.getFullYear(), 4) + '-' + zpad(date.getMonth() + 1, 2) +
         '-' + zpad(date.getDate(), 2) + ' ' + zpad(date.getHours(), 2) +
         ':' + zpad(date.getMinutes(), 2) + ':' + zpad(date.getSeconds(), 2);
}

function localizeDatetime(node) {
  node.title = '(' + node.dateTime.replace(/T/, ' ').replace(/Z$/, ' UTC') +
               ')';
  node.dataset.bsToggle = 'tooltip';
  node.textContent = formatLocalDateTime(new Date(node.dateTime));
}

function localizeAllDatetimes() {
  var nodes = document.querySelectorAll('time.localize');
  Array.prototype.forEach.call(nodes, localizeDatetime);
}

window.addEventListener('load', localizeAllDatetimes);
