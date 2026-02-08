// static/js/charts-manager.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Lógica do Gráfico de Auditoria (Barra)
    const reportCanvas = document.getElementById('scoreChart');
    if (reportCanvas && reportCanvas.dataset.scores) {
        const scores = JSON.parse(reportCanvas.dataset.scores);
        new Chart(reportCanvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Performance', 'On-Page', 'Semântica', 'Autoridade', 'Schema'],
                datasets: [{
                    label: 'Pontuação (%)',
                    data: [scores.performance, scores.on_page, scores.semantic, scores.authority, scores.schema],
                    backgroundColor: ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ec4899'],
                    borderRadius: 8
                }]
            },
            options: { indexAxis: 'y', maintainAspectRatio: false, scales: { x: { min: 0, max: 100 } } }
        });
    }

    // 2. Lógica do Gráfico de Batalha (Radar)
    const radarCanvas = document.getElementById('radarChart');
    if (radarCanvas && radarCanvas.dataset.user && radarCanvas.dataset.comp) {
        const s1 = JSON.parse(radarCanvas.dataset.user);
        const s2 = JSON.parse(radarCanvas.dataset.comp);
        new Chart(radarCanvas.getContext('2d'), {
            type: 'radar',
            data: {
                labels: ['Performance', 'On-Page', 'Semântica', 'Autoridade', 'Schema'],
                datasets: [
                    { label: 'Seu Site', data: [s1.performance, s1.on_page, s1.semantic, s1.authority, s1.schema], backgroundColor: 'rgba(59, 130, 246, 0.2)', borderColor: '#3b82f6' },
                    { label: 'Concorrente', data: [s2.performance, s2.on_page, s2.semantic, s2.authority, s2.schema], backgroundColor: 'rgba(239, 68, 68, 0.2)', borderColor: '#ef4444' }
                ]
            },
            options: { maintainAspectRatio: false, scales: { r: { min: 0, max: 100 } } }
        });
    }
});

// 3. Função Global de Exportação de PDF
function gerarPDF(nomeArquivo = 'relatorio-seo') {
    const elemento = document.querySelector('.report-container');
    if (!elemento) return;
    
    const opt = {
        margin: 1,
        filename: `${nomeArquivo}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2 },
        jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(elemento).save();
}