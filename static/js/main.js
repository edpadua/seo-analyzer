// static/js/main.js
document.addEventListener('submit', function(e) {
    const btn = e.target.querySelector('button[type="submit"]');
    // Verifica se o botão existe e se não deve ser ignorado
    if (btn && !btn.classList.contains('no-spin')) {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Processando...';
        
        // Opcional: timeout de segurança caso a requisição falhe sem retornar erro
        setTimeout(() => {
            if (btn.disabled) {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        }, 30000); 
    }
});