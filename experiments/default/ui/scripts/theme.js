(function(){
  function applyTheme(mode, accent){
    const root = document.documentElement;
    if (mode === 'light') root.setAttribute('data-theme','light'); else root.removeAttribute('data-theme');
    root.classList.remove('accent-teal','accent-violet','accent-rose');
    root.classList.add('accent-' + (accent || 'teal'));
  }

  function save(k,v){ try{ localStorage.setItem(k, v); }catch(e){} }
  function load(k, d){ try{ return localStorage.getItem(k) || d; }catch(e){ return d; } }

  function buildUI(){
    const modeKey = 'def.theme.mode';
    const accentKey = 'def.theme.accent';
    let mode = load(modeKey, 'dark');
    let accent = load(accentKey, 'teal');
    applyTheme(mode, accent);

    const fab = document.createElement('button');
    fab.className = 'theme-fab';
    fab.type = 'button';
    fab.title = 'Theme settings';
    fab.innerHTML = mode === 'light' ? '☀️' : '🌙';

    const panel = document.createElement('div');
    panel.className = 'theme-panel';
    panel.innerHTML = [
      '<div class="row">',
      '  <button type="button" data-mode="dark" class="theme-toggle">Dark</button>',
      '  <button type="button" data-mode="light" class="theme-toggle">Light</button>',
      '</div>',
      '<div class="row" style="margin-top:8px">',
      '  <button type="button" data-accent="teal" class="accent-dot teal" title="Teal"></button>',
      '  <button type="button" data-accent="violet" class="accent-dot violet" title="Violet"></button>',
      '  <button type="button" data-accent="rose" class="accent-dot rose" title="Rose"></button>',
      '</div>'
    ].join('');

    function setActive(){
      fab.innerHTML = mode === 'light' ? '☀️' : '🌙';
      panel.querySelectorAll('[data-mode]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
      });
      panel.querySelectorAll('[data-accent]').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-accent') === accent);
      });
    }
    setActive();

    fab.addEventListener('click', () => {
      panel.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!panel.contains(e.target) && e.target !== fab) panel.classList.remove('open');
    });

    panel.addEventListener('click', (e) => {
      const t = e.target.closest('[data-mode],[data-accent]');
      if (!t) return;
      if (t.hasAttribute('data-mode')) {
        mode = t.getAttribute('data-mode');
        save(modeKey, mode);
      } else if (t.hasAttribute('data-accent')) {
        accent = t.getAttribute('data-accent');
        save(accentKey, accent);
      }
      applyTheme(mode, accent);
      setActive();
    });

    document.body.appendChild(fab);
    document.body.appendChild(panel);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildUI);
  } else {
    buildUI();
  }
})();

