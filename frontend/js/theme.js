const STORAGE_KEY = 'manochitra-theme-v1';

export function initialiseTheme() {
  const savedTheme = localStorage.getItem(STORAGE_KEY);
  const preferred = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  setTheme(savedTheme || preferred);

  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
  });
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const button = document.getElementById('theme-toggle');
  if (button) {
    button.setAttribute('aria-pressed', String(theme === 'dark'));
    button.querySelector('.theme-icon').textContent = theme === 'dark' ? '☾' : '☼';
    button.querySelector('.theme-label').textContent = theme === 'dark' ? 'Night mode' : 'Daylight';
  }
}
