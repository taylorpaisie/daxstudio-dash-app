// No remote editor or telemetry. Keep keyboard interactions local to the page.
document.addEventListener('keydown', function(event) {
    if (event.target.id !== 'editor') return;
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        const run = document.getElementById('run-query');
        if (run && !run.disabled) run.click();
    }
    if (event.key === 'Tab') {
        event.preventDefault();
        const el = event.target, start = el.selectionStart, end = el.selectionEnd;
        const value = el.value.slice(0, start) + '    ' + el.value.slice(end);
        window.dash_clientside.set_props('editor', {value: value});
        setTimeout(() => el.setSelectionRange(start + 4, start + 4), 0);
    }
});
window.dashAgGridFunctions = window.dashAgGridFunctions || {};
window.dashAgGridFunctions.studioTheme = function(themeQuartz) {
    return themeQuartz.withParams({
        backgroundColor: 'var(--panel)', foregroundColor: 'var(--text)',
        headerBackgroundColor: 'var(--raised)', borderColor: 'var(--border)',
        headerTextColor: 'var(--muted)', fontFamily: 'Segoe UI, sans-serif',
        fontSize: 12, headerHeight: 36, rowHeight: 30,
        accentColor: '#287bd4', browserColorScheme: 'inherit'
    });
};
window.dashAgGridFunctions.formatNumber = function(value) {
    return value == null ? '' : Number(value).toLocaleString(undefined, {maximumFractionDigits: 12});
};
let queryStarted = null;
document.addEventListener('click', function(event) {
    if (event.target.closest('#run-query')) queryStarted = performance.now();
});
setInterval(function() {
    const button = document.getElementById('run-query');
    const clock = document.getElementById('elapsed');
    if (!clock || queryStarted === null) return;
    if (button && button.disabled) {
        clock.textContent = ((performance.now() - queryStarted) / 1000).toFixed(1) + ' s elapsed';
    } else if (performance.now() - queryStarted > 1000) {
        queryStarted = null;
        clock.textContent = '';
    }
}, 100);
