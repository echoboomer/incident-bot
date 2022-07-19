export function titleCase(string) {
  var cased = string.toLowerCase().split(' ');
  for (var i = 0; i < cased.length; i++) {
    cased[i] = cased[i][0].toUpperCase() + cased[i].slice(1);
  }
  return cased;
}
