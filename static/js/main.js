(function () {
    const button = document.getElementById('accessibilityToggle');
    const savedMode = localStorage.getItem('accessibleMode');

    function applyMode(enabled) {
        document.body.classList.toggle('accessible', enabled);
        if (button) {
            button.textContent = enabled ? 'Обычная версия сайта' : 'Версия для слабовидящих';
        }
    }

    applyMode(savedMode === 'on');

    if (button) {
        button.addEventListener('click', function () {
            const enabled = !document.body.classList.contains('accessible');
            localStorage.setItem('accessibleMode', enabled ? 'on' : 'off');
            applyMode(enabled);
        });
    }
})();
