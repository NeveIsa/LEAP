// Theme management script for Monte Carlo experiment
(function() {
    'use strict';
    
    const STORAGE_KEY = 'montecarlo-theme';
    const DEFAULT_THEME = 'dark';
    const DEFAULT_ACCENT = 'teal';
    
    // Theme configuration
    const themes = {
        dark: { name: 'Dark', class: '' },
        light: { name: 'Light', class: 'theme-light' }
    };
    
    const accents = {
        teal: { name: 'Teal', class: 'accent-teal' },
        violet: { name: 'Violet', class: 'accent-violet' },
        rose: { name: 'Rose', class: 'accent-rose' }
    };
    
    // Get current theme from storage or default
    function getCurrentTheme() {
        return localStorage.getItem(STORAGE_KEY + '-theme') || DEFAULT_THEME;
    }
    
    // Get current accent from storage or default
    function getCurrentAccent() {
        return localStorage.getItem(STORAGE_KEY + '-accent') || DEFAULT_ACCENT;
    }
    
    // Apply theme to document
    function applyTheme(themeName) {
        const html = document.documentElement;
        const body = document.body;
        
        // Remove all theme classes
        Object.values(themes).forEach(theme => {
            html.classList.remove(theme.class);
            body.classList.remove(theme.class);
        });
        
        // Apply new theme
        const theme = themes[themeName];
        if (theme && theme.class) {
            html.classList.add(theme.class);
            body.classList.add(theme.class);
        }
        
        // Store theme preference
        localStorage.setItem(STORAGE_KEY + '-theme', themeName);
    }
    
    // Apply accent to document
    function applyAccent(accentName) {
        const html = document.documentElement;
        const body = document.body;
        
        // Remove all accent classes
        Object.values(accents).forEach(accent => {
            html.classList.remove(accent.class);
            body.classList.remove(accent.class);
        });
        
        // Apply new accent
        const accent = accents[accentName];
        if (accent && accent.class) {
            html.classList.add(accent.class);
            body.classList.add(accent.class);
        }
        
        // Store accent preference
        localStorage.setItem(STORAGE_KEY + '-accent', accentName);
    }
    
    // Create theme control panel
    function createThemePanel() {
        // Check if panel already exists
        if (document.getElementById('theme-panel')) return;
        
        const fab = document.createElement('div');
        fab.className = 'theme-fab';
        fab.textContent = 'Theme';
        fab.title = 'Theme Settings';
        
        const panel = document.createElement('div');
        panel.id = 'theme-panel';
        panel.className = 'theme-panel';
        
        // Theme selection
        const themeRow = document.createElement('div');
        themeRow.className = 'row';
        themeRow.innerHTML = '<span style="font-size: 12px; color: var(--muted-color);">Theme</span>';
        
        Object.entries(themes).forEach(([key, theme]) => {
            const btn = document.createElement('button');
            btn.className = 'theme-toggle';
            btn.textContent = theme.name;
            btn.addEventListener('click', () => {
                applyTheme(key);
                updateThemeButtons();
            });
            themeRow.appendChild(btn);
        });
        
        // Accent selection
        const accentRow = document.createElement('div');
        accentRow.className = 'row';
        accentRow.style.marginTop = '8px';
        accentRow.innerHTML = '<span style="font-size: 12px; color: var(--muted-color);">Accent</span>';
        
        Object.entries(accents).forEach(([key, accent]) => {
            const dot = document.createElement('div');
            dot.className = `accent-dot ${key}`;
            dot.title = accent.name;
            dot.addEventListener('click', () => {
                applyAccent(key);
                updateAccentDots();
            });
            accentRow.appendChild(dot);
        });
        
        panel.appendChild(themeRow);
        panel.appendChild(accentRow);
        
        // Toggle panel visibility
        fab.addEventListener('click', (e) => {
            e.stopPropagation();
            panel.classList.toggle('open');
        });
        
        // Close panel when clicking outside
        document.addEventListener('click', (e) => {
            if (!panel.contains(e.target) && !fab.contains(e.target)) {
                panel.classList.remove('open');
            }
        });
        
        document.body.appendChild(fab);
        document.body.appendChild(panel);
        
        // Update button states
        updateThemeButtons();
        updateAccentDots();
    }
    
    // Update theme button states
    function updateThemeButtons() {
        const currentTheme = getCurrentTheme();
        const buttons = document.querySelectorAll('#theme-panel .theme-toggle');
        buttons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.textContent === themes[currentTheme].name) {
                btn.classList.add('active');
            }
        });
    }
    
    // Update accent dot states
    function updateAccentDots() {
        const currentAccent = getCurrentAccent();
        const dots = document.querySelectorAll('#theme-panel .accent-dot');
        dots.forEach(dot => {
            dot.classList.remove('active');
            if (dot.classList.contains(currentAccent)) {
                dot.classList.add('active');
            }
        });
    }
    
    // Initialize theme system
    function init() {
        // Apply saved theme and accent
        applyTheme(getCurrentTheme());
        applyAccent(getCurrentAccent());
        
        // Create theme control panel
        createThemePanel();
        
        // Add keyboard shortcut (Ctrl/Cmd + Shift + T)
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'T') {
                e.preventDefault();
                const currentTheme = getCurrentTheme();
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                applyTheme(newTheme);
                updateThemeButtons();
            }
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Export functions for external use
    window.EulerTheme = {
        applyTheme,
        applyAccent,
        getCurrentTheme,
        getCurrentAccent
    };
})();
