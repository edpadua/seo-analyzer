function initRadarChart(userScores, compScores) {
    const ctx = document.getElementById('radarChart').getContext('2d');
    
    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Performance', 'On-Page', 'Semântica', 'Autoridade', 'Schema'],
            datasets: [
                {
                    label: 'Seu Site',
                    data: [userScores.performance, userScores.on_page, userScores.semantic, userScores.authority, userScores.schema],
                    backgroundColor: 'rgba(37, 99, 235, 0.2)',
                    borderColor: '#2563eb',
                    borderWidth: 2,
                    pointBackgroundColor: '#2563eb'
                },
                {
                    label: 'Concorrente',
                    data: [compScores.performance, compScores.on_page, compScores.semantic, compScores.authority, compScores.schema],
                    backgroundColor: 'rgba(220, 38, 38, 0.2)',
                    borderColor: '#dc2626',
                    borderWidth: 2,
                    pointBackgroundColor: '#dc2626'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { stepSize: 20 }
                }
            },
            plugins: {
                legend: { position: 'top' }
            }
        }
    });
}

function gerarPDF(keyword) {
    const btn = document.querySelector('.btn-export');
    btn.style.display = 'none';

    const elemento = document.getElementById("conteudo-batalha");
    const opt = {
        margin: 10,
        filename: `Batalha_SEO_${keyword}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    html2pdf().set(opt).from(elemento).save().then(() => {
        btn.style.display = 'block';
    });
}