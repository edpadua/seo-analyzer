// static/js/ui-animations.js
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('form').forEach(form => {
        form.onsubmit = function() {
            // Verifica qual rota o formulário está chamando
            const action = form.getAttribute('action');
            const isAudit = action === '/audit';
            const isBattle = action === '/battle';

            // Só executa se for um dos formulários de análise
            if (isAudit || isBattle) {
                const btnId = isAudit ? 'btn-audit' : 'btn-battle';
                const txtId = isAudit ? 'txt-audit' : 'txt-battle';
                const loadId = isAudit ? 'load-audit' : 'load-battle';

                const btn = document.getElementById(btnId);
                const txt = document.getElementById(txtId);
                const load = document.getElementById(loadId);

                // Verifica se os elementos existem na página antes de modificar
                if (btn && txt && load) {
                    txt.innerText = isAudit ? "A analisar..." : "A batalhar...";
                    load.classList.remove('d-none');
                    btn.classList.add('disabled');
                }
            }
        };
    });
});