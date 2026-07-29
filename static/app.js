function togglePilotMenu() {
  document.getElementById('pilot-left').classList.toggle('open');
  document.getElementById('pilot-overlay').classList.toggle('visible');
}
function toggleCanvas() {
  document.getElementById('pilot-canvas').classList.toggle('open');
  if (window.innerWidth < 900) document.getElementById('pilot-overlay').classList.toggle('visible');
}
function closePilotPanels() {
  document.getElementById('pilot-left').classList.remove('open');
  document.getElementById('pilot-canvas').classList.remove('open');
  document.getElementById('pilot-overlay').classList.remove('visible');
}
function pilotSuggest(value) {
  const input = document.getElementById('pilot-input');
  input.value = value;
  input.focus();
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closePilotPanels();
});
